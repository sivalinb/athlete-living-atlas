"""Local, streaming Apple Health importer. No network or clinical/identity fields."""

import argparse
import collections
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import time
import xml.etree.ElementTree as ET
import zipfile
from zoneinfo import ZoneInfo

METRICS = {
    "HeartRate": ("heart_rate", "bpm"),
    "RestingHeartRate": ("resting_hr", "bpm"),
    "HeartRateVariabilitySDNN": ("hrv_sdnn", "ms"),
    "HeartRateVariabilityRMSSD": ("hrv_rmssd", "ms"),
    "VO2Max": ("vo2max", "ml/kg/min"),
    "RunningPower": ("running_power", "W"),
    "RunningSpeed": ("running_speed", "m/s"),
    "RunningStrideLength": ("stride_length", "m"),
    "RunningGroundContactTime": ("ground_contact", "ms"),
    "RunningVerticalOscillation": ("vertical_oscillation", "cm"),
    "RespiratoryRate": ("respiratory_rate", "breaths/min"),
    "HeartRateRecoveryOneMinute": ("hr_recovery", "bpm"),
}
SCHEMA = """
CREATE TABLE meta(key TEXT PRIMARY KEY,value TEXT);
CREATE TABLE samples(id TEXT PRIMARY KEY,metric TEXT,ts INTEGER,end_ts INTEGER,day TEXT,source TEXT,value REAL,unit TEXT);
CREATE TABLE workouts(id TEXT PRIMARY KEY,activity TEXT,start_ts INTEGER,end_ts INTEGER,day TEXT,source TEXT,active_s REAL,elapsed_s REAL,distance_km REAL,energy_kcal REAL,elevation_m REAL,route_km REAL,route_points INTEGER DEFAULT 0,stop_s REAL,route_coverage REAL);
CREATE TABLE sleep(id TEXT PRIMARY KEY,start_ts INTEGER,end_ts INTEGER,day TEXT,source TEXT,stage TEXT);
CREATE TABLE sleep_daily(day TEXT PRIMARY KEY,ts INTEGER,source TEXT,total_h REAL,deep_h REAL,rem_h REAL,core_h REAL);
CREATE TABLE daily_metrics(metric TEXT,day TEXT,ts INTEGER,source TEXT,value REAL,n INTEGER,PRIMARY KEY(metric,day,source));
CREATE TABLE route_points(workout_id TEXT,ts INTEGER,latitude REAL,longitude REAL,elevation REAL,distance_km REAL,speed_mps REAL,PRIMARY KEY(workout_id,ts));
CREATE TABLE stops(workout_id TEXT,start_ts INTEGER,end_ts INTEGER,duration_s REAL,PRIMARY KEY(workout_id,start_ts));
CREATE TABLE workout_events(workout_id TEXT,ts INTEGER,event TEXT,PRIMARY KEY(workout_id,ts,event));
CREATE TABLE daily_activity(day TEXT PRIMARY KEY,ts INTEGER,move_kcal REAL,exercise_min REAL,stand_hours REAL);
CREATE INDEX sample_lookup ON samples(metric,ts,source);
CREATE INDEX sample_source ON samples(source,metric,ts);
CREATE INDEX workout_time ON workouts(start_ts);
"""


def epoch(s):
    return int(dt.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp())


def digest(*parts):
    return hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()[:24]


def source_label(a):
    match = re.search(r"hardware:([^,>]+(?:,[0-9]+)?)", a.get("device", ""))
    if match:
        hardware = match.group(1).strip()
        return ("Watch " if hardware.startswith("Watch") else "Device ") + hardware
    if "watch" in a.get("sourceName", "").lower():
        return "Apple Watch (unspecified)"
    return "Source " + digest(a.get("sourceName", "unknown"))[:6]


def convert(value, unit, target):
    x = float(value)
    if not math.isfinite(x):
        raise ValueError("Nonfinite measurement")
    factors = {
        "km": {"km": 1, "mi": 1.609344, "m": 0.001, "ft": 0.0003048},
        "m": {"m": 1, "cm": 0.01, "ft": 0.3048, "in": 0.0254, "km": 1000},
        "s": {"s": 1, "min": 60, "hr": 3600},
        "kcal": {"Cal": 1, "kcal": 1, "kJ": 1 / 4.184},
        "m/s": {"m/s": 1, "mi/hr": 0.44704, "km/hr": 1 / 3.6},
        "bpm": {"count/min": 1},
        "ms": {"ms": 1, "s": 1000},
        "ml/kg/min": {"mL/min·kg": 1, "mL/kg/min": 1},
        "W": {"W": 1},
        "cm": {"cm": 1, "m": 100},
        "breaths/min": {"count/min": 1},
    }
    return x * factors[target][unit]


def union_seconds(intervals):
    total = 0
    end = None
    for a, b in sorted(intervals):
        if b <= a:
            continue
        if end is None or b > end:
            total += b - max(a, end if end is not None else a)
        end = max(b, end if end is not None else b)
    return total


def distance(a, b):
    la, lb = map(math.radians, (a[1], b[1]))
    p = (
        math.sin((lb - la) / 2) ** 2
        + math.cos(la) * math.cos(lb) * math.sin(math.radians(b[2] - a[2]) / 2) ** 2
    )
    return 6371000 * 2 * math.asin(min(1, math.sqrt(p)))


def analyze_route(points):
    """Low motion is a candidate observation; gaps never count as stops."""
    clean = []
    stops = []
    cumulative = 0
    slow = None
    prev = None
    valid_s = 0
    for p in sorted(points):
        if not (-90 <= p[1] <= 90 and -180 <= p[2] <= 180):
            continue
        speed = None
        if prev:
            delta = p[0] - prev[0]
            if delta <= 0:
                continue
            meters = distance(prev, p)
            if delta <= 30 and meters / delta <= 12:
                cumulative += meters
                speed = meters / delta
                valid_s += delta
                if speed < 0.5:
                    if slow is None:
                        slow = prev[0]
                else:
                    if slow is not None and prev[0] - slow >= 30:
                        stops.append((slow, prev[0], prev[0] - slow))
                    slow = None
            else:
                if slow is not None and prev[0] - slow >= 30:
                    stops.append((slow, prev[0], prev[0] - slow))
                slow = None
        clean.append((*p, cumulative / 1000, speed))
        prev = p
    if prev and slow is not None and prev[0] - slow >= 30:
        stops.append((slow, prev[0], prev[0] - slow))
    return clean, stops, valid_s


def finalize(con, tz):
    con.execute(
        "INSERT INTO daily_metrics SELECT metric,day,CAST(AVG(ts) AS INTEGER),source,AVG(value),COUNT(*) FROM samples GROUP BY metric,day,source"
    )
    groups = collections.defaultdict(list)
    for a, b, day, source, stage in con.execute("SELECT start_ts,end_ts,day,source,stage FROM sleep"):
        groups[(day, source)].append((a, b, stage))
    byday = collections.defaultdict(list)
    for (day, source), rows in groups.items():
        asleep = [
            (a, b)
            for a, b, s in rows
            if s in ("Asleep", "AsleepUnspecified", "AsleepCore", "AsleepDeep", "AsleepREM")
        ]
        if not asleep:
            continue
        total = union_seconds(asleep)
        parts = {
            stage: union_seconds([(a, b) for a, b, s in rows if s == stage]) / 3600
            for stage in ("AsleepDeep", "AsleepREM", "AsleepCore")
        }
        priority = (any(s in ("AsleepCore", "AsleepDeep", "AsleepREM") for _, _, s in rows), total)
        byday[day].append((priority, source, total / 3600, parts))
    for day, choices in byday.items():
        _, source, total, parts = max(choices, key=lambda x: (x[0], x[1]))
        con.execute(
            "INSERT INTO sleep_daily VALUES(?,?,?,?,?,?,?)",
            (
                day,
                int(dt.datetime.fromisoformat(day).replace(tzinfo=tz).timestamp()),
                source,
                total,
                parts["AsleepDeep"],
                parts["AsleepREM"],
                parts["AsleepCore"],
            ),
        )
    con.commit()


def ingest(archive, target, timezone="America/Denver"):
    begin = time.monotonic()
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(target.name + ".building")
    tmp.unlink(missing_ok=True)
    tz = ZoneInfo(timezone)
    counters = collections.Counter()
    refs = collections.defaultdict(list)
    con = sqlite3.connect(tmp)
    con.executescript(SCHEMA)
    con.execute("PRAGMA synchronous=OFF")
    seen = 0
    latest = 0
    try:
        with zipfile.ZipFile(archive) as z:
            names = set(z.namelist())
            xmls = [n for n in names if n.endswith("/export.xml") or n == "export.xml"]
            if len(xmls) != 1:
                raise ValueError("Expected exactly one export.xml")
            xml = xmls[0]
            prefix = xml.rsplit("/", 1)[0] + "/" if "/" in xml else ""
            with z.open(xml) as stream:
                events = ET.iterparse(stream, events=("start", "end"))
                _, root = next(events)
                depth = 1
                for event, e in events:
                    if event == "start":
                        depth += 1
                        continue
                    depth -= 1
                    if depth != 1:
                        continue
                    a = e.attrib
                    try:
                        if e.tag == "ExportDate":
                            latest = epoch(a["value"])
                        elif e.tag == "Record":
                            seen += 1
                            metric = a.get("type", "").replace("HKQuantityTypeIdentifier", "")
                            if metric in METRICS or a.get("type") == "HKCategoryTypeIdentifierSleepAnalysis":
                                start, end = epoch(a["startDate"]), epoch(a["endDate"])
                                source = source_label(a)
                                if end < start:
                                    raise ValueError("Reversed interval")
                                day = dt.datetime.fromtimestamp(start, tz).date().isoformat()
                                if metric in METRICS:
                                    name, unit = METRICS[metric]
                                    value = convert(a["value"], a.get("unit"), unit)
                                    key = digest(name, start, end, source, value)
                                    con.execute(
                                        "INSERT OR IGNORE INTO samples VALUES(?,?,?,?,?,?,?,?)",
                                        (key, name, start, end, day, source, value, unit),
                                    )
                                    counters["selected_records"] += 1
                                else:
                                    day = (
                                        (dt.datetime.fromtimestamp(end, tz) + dt.timedelta(hours=12))
                                        .date()
                                        .isoformat()
                                    )
                                    stage = a["value"].replace("HKCategoryValueSleepAnalysis", "")
                                    con.execute(
                                        "INSERT OR IGNORE INTO sleep VALUES(?,?,?,?,?,?)",
                                        (digest(start, end, source, stage), start, end, day, source, stage),
                                    )
                            else:
                                counters["excluded_records"] += 1
                            if seen % 250000 == 0:
                                con.commit()
                                print(f"Inspected {seen:,} records", flush=True)
                        elif e.tag == "Workout":
                            start, end = epoch(a["startDate"]), epoch(a["endDate"])
                            activity = a["workoutActivityType"].replace("HKWorkoutActivityType", "")
                            source = source_label(a)
                            key = digest(activity, start, end)
                            stats = {
                                s.attrib.get("type", "").replace("HKQuantityTypeIdentifier", ""): s.attrib
                                for s in e.findall("WorkoutStatistics")
                            }

                            def stat(types, target_unit):
                                for t in types:
                                    if t in stats and "sum" in stats[t]:
                                        return convert(stats[t]["sum"], stats[t]["unit"], target_unit)
                                return None

                            km = stat(("DistanceWalkingRunning", "DistanceCycling"), "km")
                            if km is None and "totalDistance" in a:
                                km = convert(a["totalDistance"], a["totalDistanceUnit"], "km")
                            kcal = stat(("ActiveEnergyBurned",), "kcal")
                            if kcal is None and "totalEnergyBurned" in a:
                                kcal = convert(a["totalEnergyBurned"], a["totalEnergyBurnedUnit"], "kcal")
                            meta = {m.get("key"): m.get("value") for m in e.findall("MetadataEntry")}
                            elev = None
                            if meta.get("HKElevationAscended"):
                                n, u = meta["HKElevationAscended"].split()
                                elev = convert(n, u, "m")
                            con.execute(
                                "INSERT OR IGNORE INTO workouts(id,activity,start_ts,end_ts,day,source,active_s,elapsed_s,distance_km,energy_kcal,elevation_m) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                                (
                                    key,
                                    activity,
                                    start,
                                    end,
                                    dt.datetime.fromtimestamp(start, tz).date().isoformat(),
                                    source,
                                    convert(a["duration"], a["durationUnit"], "s"),
                                    end - start,
                                    km,
                                    kcal,
                                    elev,
                                ),
                            )
                            for f in e.findall(".//FileReference"):
                                refs[key].append(prefix + f.attrib["path"].lstrip("/"))
                            for ev in e.findall("WorkoutEvent"):
                                if ev.get("date"):
                                    con.execute(
                                        "INSERT OR IGNORE INTO workout_events VALUES(?,?,?)",
                                        (
                                            key,
                                            epoch(ev.get("date")),
                                            ev.get("type", "").replace("HKWorkoutEventType", ""),
                                        ),
                                    )
                        elif e.tag == "ActivitySummary":
                            day = a["dateComponents"]
                            ts = int(dt.datetime.fromisoformat(day).replace(tzinfo=tz).timestamp())
                            con.execute(
                                "INSERT OR REPLACE INTO daily_activity VALUES(?,?,?,?,?)",
                                (
                                    day,
                                    ts,
                                    convert(
                                        a["activeEnergyBurned"],
                                        a.get("activeEnergyBurnedUnit", "Cal"),
                                        "kcal",
                                    ),
                                    float(a["appleExerciseTime"]),
                                    float(a["appleStandHours"]),
                                ),
                            )
                    except (ValueError, KeyError, OverflowError):
                        counters["invalid_elements"] += 1
                    root.remove(e)
            con.commit()
            print("Parsing workout routes", flush=True)
            for key, files in refs.items():
                points = []
                for name in files:
                    if name not in names:
                        counters["missing_routes"] += 1
                        continue
                    with z.open(name) as f:
                        for _, e in ET.iterparse(f, events=("end",)):
                            if e.tag.rsplit("}", 1)[-1] != "trkpt":
                                continue
                            vals = {c.tag.rsplit("}", 1)[-1]: c.text for c in e}
                            try:
                                points.append(
                                    (
                                        epoch(vals["time"]),
                                        float(e.get("lat")),
                                        float(e.get("lon")),
                                        float(vals["ele"]) if vals.get("ele") else None,
                                    )
                                )
                            except (ValueError, KeyError, TypeError):
                                counters["invalid_route_points"] += 1
                            e.clear()
                wstart, wend = con.execute(
                    "SELECT start_ts,end_ts FROM workouts WHERE id=?", (key,)
                ).fetchone()
                points = [p for p in points if wstart <= p[0] <= wend]
                clean, stops, coverage = analyze_route(points)
                if not clean:
                    continue
                last = None
                for i, row in enumerate(clean):
                    if last is None or row[0] - last >= 5 or i == len(clean) - 1:
                        con.execute("INSERT OR IGNORE INTO route_points VALUES(?,?,?,?,?,?,?)", (key, *row))
                        last = row[0]
                con.executemany("INSERT OR IGNORE INTO stops VALUES(?,?,?,?)", [(key, *s) for s in stops])
                con.execute(
                    "UPDATE workouts SET route_km=?,route_points=?,stop_s=?,route_coverage=? WHERE id=?",
                    (
                        clean[-1][-2],
                        len(clean),
                        sum(s[2] for s in stops),
                        min(1, coverage / max(1, wend - wstart)),
                        key,
                    ),
                )
            counters["inspected_records"] = seen
            finalize(con, tz)
            for table in ("samples", "workouts", "route_points", "sleep", "sleep_daily"):
                counters[table] = con.execute("SELECT COUNT(*) FROM " + table).fetchone()[0]
            values = {
                "dataset": "PERSONAL · local only",
                "export_ts": latest,
                "timezone": timezone,
                "import_seconds": round(time.monotonic() - begin, 2),
                "schema_version": 1,
                **counters,
            }
            con.executemany("INSERT INTO meta VALUES(?,?)", [(k, str(v)) for k, v in values.items()])
            con.commit()
            con.execute("ANALYZE")
            con.commit()
            if con.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("Database integrity failed")
        con.close()
        os.chmod(tmp, 0o600)
        os.replace(tmp, target)
        print(json.dumps(dict(counters), indent=2))
        return dict(counters)
    except BaseException:
        con.close()
        tmp.unlink(missing_ok=True)
        raise


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("archive")
    p.add_argument("--db", required=True)
    p.add_argument("--timezone", default="America/Denver")
    a = p.parse_args()
    ingest(a.archive, a.db, a.timezone)
