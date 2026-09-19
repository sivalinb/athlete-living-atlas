"""Read-only projection from Athlete Observatory to visual scenes; no identity fields."""

import argparse
import json
from pathlib import Path
import sqlite3

ROOT = Path(__file__).resolve().parents[1]


def snapshot(db):
    con = sqlite3.connect(Path(db).resolve().as_uri() + '?mode=ro', uri=True)
    con.row_factory = sqlite3.Row
    try:
        meta = dict(con.execute('SELECT key,value FROM meta'))
        workouts = []
        for r in con.execute("SELECT * FROM workouts ORDER BY (activity='Running' AND route_points>0) DESC,start_ts DESC LIMIT 8"):
            start = r['start_ts']
            points = [dict(x) for x in con.execute('SELECT ts,latitude,longitude,speed_mps,elevation FROM route_points WHERE workout_id=? ORDER BY ts', (r['id'],))]
            # Preserve route aspect ratio in local Cartesian coordinates; remove absolute GPS.
            if points:
                import math
                lat0 = sum(p['latitude'] for p in points)/len(points)
                cosine = math.cos(math.radians(lat0))
                xs = [p['longitude']*cosine for p in points]
                ys = [p['latitude'] for p in points]
                x0, y0 = (max(xs)+min(xs))/2, (max(ys)+min(ys))/2
                span = max(max(xs)-min(xs), max(ys)-min(ys), 1e-8)
                route = [{'t':p['ts']-start,'x':round(.5+(x-x0)/span*.75,5),'y':round(.5-(y-y0)/span*.75,5),'speed':p['speed_mps'],'elevation':p['elevation']} for p,x,y in zip(points,xs,ys)][::max(1,len(points)//700)]
            else:
                route = []
            hr = [{'t':x[0]-start,'bpm':round(x[1],1)} for x in con.execute("SELECT (ts/5)*5,AVG(value) FROM samples WHERE metric='heart_rate' AND source=? AND ts BETWEEN ? AND ? GROUP BY (ts/5)*5 ORDER BY ts", (r['source'], start, r['end_ts']))]
            workouts.append({'id':r['id'],'date':r['day'],'activity':r['activity'],'duration':r['elapsed_s'],'active':r['active_s'],'distance':r['distance_km'],'climbing':r['elevation_m'],'hr':hr,'route':route,'stops':[{'start':s[0]-start,'end':s[1]-start} for s in con.execute('SELECT start_ts,end_ts FROM stops WHERE workout_id=? ORDER BY start_ts',(r['id'],))]})
        nights = [dict(r) for r in con.execute('SELECT day,total_h,deep_h,rem_h,core_h FROM sleep_daily ORDER BY day DESC LIMIT 30')][::-1]
        return {'schema':1,'synthetic':meta.get('dataset','').startswith('SYNTHETIC'),'export_ts':int(meta['export_ts']),'workouts':workouts,'nights':nights,'scope':'Recorded snapshot. Illustrative animation; not live monitoring or a physiological simulation.'}
    finally:
        con.close()


def write_public(db, destination):
    data = snapshot(db)
    if not data['synthetic']:
        raise ValueError('Public export accepts only the fictional dataset. Use the loopback server for personal data.')
    Path(destination).write_text(json.dumps(data,separators=(',',':'))+'\n')


if __name__ == '__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--db',required=True)
    p.add_argument('--out',default='dist/demo.json')
    a=p.parse_args()
    write_public(a.db,a.out)
