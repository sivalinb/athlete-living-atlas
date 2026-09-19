"""Build static synthetic assets from the real importer; no personal input argument."""
import json
from pathlib import Path
import tempfile
import sqlite3
from observatory.demo import generate
from observatory.ingest import ingest
from .export import snapshot, ROOT


def stable_numbers(value):
    """Discard libm/SQLite machine-epsilon differences in public display assets."""
    if isinstance(value, float):
        return round(value, 6)
    if isinstance(value, list):
        return [stable_numbers(v) for v in value]
    if isinstance(value, dict):
        return {k: stable_numbers(v) for k, v in value.items()}
    return value


def build():
    with tempfile.TemporaryDirectory() as tmp:
        archive=Path(tmp)/'fictional.zip'
        db=Path(tmp)/'health.sqlite'
        generate(archive)
        ingest(archive,db)
        with sqlite3.connect(db) as con:
            con.execute("UPDATE meta SET value='SYNTHETIC · fictional demo' WHERE key='dataset'")
        data=stable_numbers(snapshot(db))
    # Separate each session so assets are inspectable and small in Git reviews.
    dest=ROOT/'dist/data'
    dest.mkdir(exist_ok=True)
    paths=[]
    for i,w in enumerate(data.pop('workouts')):
        name=f'session-{i+1:02}.json'
        (dest/name).write_text(json.dumps(w,separators=(',',':'))+'\n')
        paths.append('data/'+name)
    data['sessions']=paths
    (ROOT/'dist/demo.json').write_text(json.dumps(data,separators=(',',':'))+'\n')
    report=json.loads((ROOT/'docs/evidence/braintrust-evidence.json').read_text())
    cases={c['id']:c for c in json.loads((ROOT/'evals/cases.json').read_text())}
    for e in report['experiments']:
        for c in e['cases']:
            c['question']=cases[c['case_id']]['question']
            c['scenario']=cases[c['case_id']]['scenario']
    (ROOT/'dist/braintrust.json').write_text(json.dumps(report,separators=(',',':'))+'\n')

if __name__=='__main__':
    build()
