"""Typed, read-only, parameterized tools. The planner never supplies SQL or file paths."""

from pathlib import Path
import sqlite3


class HealthTools:
    def __init__(self, db):
        self.con = sqlite3.connect(Path(db).resolve().as_uri() + "?mode=ro", uri=True)
        self.con.execute("PRAGMA query_only=ON")
        self.con.row_factory = sqlite3.Row

    def close(self):
        self.con.close()

    def run(self, name, days=180):
        if type(days) is not int or not 1 <= days <= 366:
            raise ValueError("Window must be an integer from 1 to 366 days")
        maximum = int(self.con.execute("SELECT value FROM meta WHERE key='export_ts'").fetchone()[0])
        cutoff = maximum - days * 86400
        if name == "training_summary":
            row = dict(
                self.con.execute(
                    "SELECT COUNT(*) AS sessions,ROUND(SUM(distance_km),2) AS distance_km,ROUND(SUM(active_s)/3600,2) AS active_hours,COUNT(distance_km) AS sessions_with_distance FROM workouts WHERE start_ts BETWEEN ? AND ?",
                    (cutoff, maximum),
                ).fetchone()
            )
            row["window_days"] = days
        elif name == "latest_workout":
            found = self.con.execute(
                "SELECT activity,ROUND(distance_km,2) AS distance_km,ROUND(elapsed_s/60,2) AS elapsed_minutes,ROUND(active_s/60,2) AS active_minutes,ROUND(stop_s,1) AS candidate_stop_seconds,ROUND(route_coverage*100,1) AS route_coverage_percent FROM workouts ORDER BY (activity='Running' AND route_points>0) DESC,start_ts DESC LIMIT 1"
            ).fetchone()
            row = dict(found) if found else {}
        elif name == "signal_inventory":
            row = {
                "metrics": [
                    dict(r)
                    for r in self.con.execute(
                        "SELECT metric,COUNT(*) AS samples,COUNT(DISTINCT source) AS source_count FROM samples WHERE ts BETWEEN ? AND ? GROUP BY metric ORDER BY metric",
                        (cutoff, maximum),
                    )
                ],
                "window_days": days,
            }
        else:
            raise ValueError("Tool is not allowlisted")
        return {
            "id": "tool:" + name,
            "facts": row,
            "source": "local SQLite snapshot",
            "as_of_epoch": maximum,
            "dashboard": "/?scene=" + {"training_summary": "heart", "latest_workout": "trail", "signal_inventory": "recovery"}[name],
        }
