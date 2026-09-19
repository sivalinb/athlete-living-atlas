"""Deterministic fictional Apple Health export. Never reads personal data."""

import argparse
import datetime as dt
import math
from pathlib import Path
import random
import xml.etree.ElementTree as ET
import zipfile
from .ingest import ingest

REFERENCE = dt.datetime(2026, 9, 18, 12, tzinfo=dt.timezone.utc)


def generate(path):
    rng = random.Random(42)
    root = ET.Element("HealthData", locale="en_US")
    ET.SubElement(root, "ExportDate", value=REFERENCE.isoformat())
    source = {"sourceName": "Fictional Apple Watch", "device": "name:Demo, hardware:WatchDemo, software:1.0"}
    routes = {}

    def sample(kind, t, value, unit, end=None):
        ET.SubElement(
            root,
            "Record",
            type="HKQuantityTypeIdentifier" + kind,
            startDate=t.isoformat(),
            endDate=(end or t).isoformat(),
            value=str(value),
            unit=unit,
            **source,
        )

    for day in range(120):
        t = REFERENCE - dt.timedelta(days=119 - day, hours=5)
        for kind, val, unit in [
            ("RestingHeartRate", 53 + 3 * math.sin(day / 9) + rng.random() * 2, "count/min"),
            ("HeartRateVariabilitySDNN", 48 + 9 * math.cos(day / 11) + rng.random() * 8, "ms"),
            ("VO2Max", 46 + day / 120, "mL/min·kg"),
        ]:
            sample(kind, t, val, unit)
        if day > 110:
            sample("HeartRateVariabilityRMSSD", t, 42 + rng.random() * 5, "ms")
        wake = t - dt.timedelta(hours=1)
        start = wake - dt.timedelta(hours=7 + rng.random())
        mid = start + (wake - start) * 0.5
        for stage, a, b in [
            ("AsleepCore", start, mid),
            ("AsleepDeep", mid, mid + dt.timedelta(hours=1)),
            ("AsleepREM", mid + dt.timedelta(hours=1), wake),
        ]:
            ET.SubElement(
                root,
                "Record",
                type="HKCategoryTypeIdentifierSleepAnalysis",
                startDate=a.isoformat(),
                endDate=b.isoformat(),
                value="HKCategoryValueSleepAnalysis" + stage,
                **source,
            )
        ET.SubElement(
            root,
            "ActivitySummary",
            dateComponents=t.date().isoformat(),
            activeEnergyBurned=str(300 + day % 5 * 80),
            activeEnergyBurnedUnit="Cal",
            appleExerciseTime=str(25 + day % 5 * 10),
            appleStandHours="12",
        )
        if day % 3 == 0:
            continue
        km = 5 + day % 13
        seconds = int(km * (355 + 30 * math.sin(day / 8)))
        end = t + dt.timedelta(seconds=seconds)
        w = ET.SubElement(
            root,
            "Workout",
            workoutActivityType="HKWorkoutActivityTypeRunning",
            startDate=t.isoformat(),
            endDate=end.isoformat(),
            duration=str(seconds - 90),
            durationUnit="s",
            **source,
        )
        ET.SubElement(
            w,
            "WorkoutStatistics",
            type="HKQuantityTypeIdentifierDistanceWalkingRunning",
            sum=str(km),
            unit="km",
        )
        ET.SubElement(
            w,
            "WorkoutStatistics",
            type="HKQuantityTypeIdentifierActiveEnergyBurned",
            sum=str(km * 65),
            unit="kcal",
        )
        ET.SubElement(w, "MetadataEntry", key="HKElevationAscended", value=f"{km * 14} m")
        ET.SubElement(
            w,
            "WorkoutEvent",
            type="HKWorkoutEventTypePause",
            date=(t + dt.timedelta(seconds=600)).isoformat(),
        )
        ET.SubElement(
            w,
            "WorkoutEvent",
            type="HKWorkoutEventTypeResume",
            date=(t + dt.timedelta(seconds=690)).isoformat(),
        )
        fname = f"route_demo_{day}.gpx"
        r = ET.SubElement(w, "WorkoutRoute")
        ET.SubElement(r, "FileReference", path="/workout-routes/" + fname)
        g = ET.Element("gpx", xmlns="http://www.topografix.com/GPX/1/1", version="1.1")
        seg = ET.SubElement(ET.SubElement(g, "trk"), "trkseg")
        for sec in range(0, seconds, 5):
            progress = (sec if sec < 600 else 600 if sec <= 690 else sec - 90) / max(1, seconds - 90)
            angle = progress * 2 * math.pi
            # Fictional loop, unrelated to the user's locations.
            lat = 39.95 + 0.011 * math.sin(angle)
            lon = -105.05 + 0.015 * math.cos(angle)
            point = ET.SubElement(seg, "trkpt", lat=str(lat), lon=str(lon))
            ET.SubElement(point, "time").text = (t + dt.timedelta(seconds=sec)).isoformat()
            ET.SubElement(point, "ele").text = str(1600 + 30 * math.sin(angle))
            sample(
                "HeartRate",
                t + dt.timedelta(seconds=sec),
                135 + 12 * math.sin(sec / 300) + rng.random() * 5,
                "count/min",
            )
        routes[fname] = ET.tostring(g)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("apple_health_export/export.xml", ET.tostring(root))
        for n, b in routes.items():
            z.writestr("apple_health_export/workout-routes/" + n, b)
    return path


def main():
    import sqlite3

    p = argparse.ArgumentParser()
    p.add_argument("--db", default="data/health.sqlite")
    a = p.parse_args()
    path = Path(a.db).with_suffix(".demo.zip")
    generate(path)
    ingest(path, a.db)
    con = sqlite3.connect(a.db)
    con.execute("UPDATE meta SET value='SYNTHETIC · fictional demo' WHERE key='dataset'")
    con.commit()
    con.close()
    path.unlink()


if __name__ == "__main__":
    main()
