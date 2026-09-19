import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from living.export import snapshot, write_public
from observatory.demo import generate
from observatory.ingest import ingest

ROOT=Path(__file__).resolve().parents[1]


class VisualDataTests(unittest.TestCase):
    def test_public_assets_are_synthetic_and_no_absolute_coordinates(self):
        manifest=json.loads((ROOT/'dist/demo.json').read_text())
        self.assertTrue(manifest['synthetic'])
        self.assertEqual(len(manifest['nights']),30)
        for name in manifest['sessions']:
            raw=(ROOT/'dist'/name).read_text()
            self.assertNotIn('latitude',raw)
            self.assertNotIn('longitude',raw)
            data=json.loads(raw)
            self.assertTrue(all(0<=p['x']<=1 and 0<=p['y']<=1 for p in data['route']))
            self.assertEqual([s['t'] for s in data['hr']],sorted(s['t'] for s in data['hr']))

    def test_all_120_braintrust_cases_preserved(self):
        report=json.loads((ROOT/'dist/braintrust.json').read_text())
        self.assertEqual([sum(c['case_pass'] for c in e['cases']) for e in report['experiments']],[30,40,36])
        for e in report['experiments']:
            self.assertEqual(len({c['case_id'] for c in e['cases']}),40)
            self.assertEqual(e['verified_case_count'],40)
            self.assertEqual(sum(c['status']=='blocked' for c in e['cases']),6)

    def test_personal_export_is_rejected_and_local_read_does_not_mutate(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=Path(tmp)/'health.sqlite'; generate(Path(tmp)/'demo.zip');ingest(Path(tmp)/'demo.zip',db)
            before=db.read_bytes()
            data=snapshot(db)
            self.assertFalse(data['synthetic'])
            self.assertEqual(before,db.read_bytes())
            dest=Path(tmp)/'public.json'
            with self.assertRaises(ValueError):write_public(db,dest)
            self.assertFalse(dest.exists())
