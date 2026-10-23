import json
import math
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pipeline as p

class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.cfg = p.read(Path(__file__).resolve().parents[1] / 'examples/variables.example.json')
    def test_lhs_strata_and_repeatability(self):
        cases = p.doe(self.cfg, 20, 42)
        self.assertEqual(cases, p.doe(self.cfg, 20, 42))
        self.assertEqual(len(cases), 21)
        for v in self.cfg['variables']:
            strata = [int((c['parameters'][v['name']] - v['lower']) / (v['upper'] - v['lower']) * 20) for c in cases[1:]]
            self.assertEqual(sorted(strata), list(range(20)))
    def test_response_values(self):
        rows = [{'outlet':n, 'mass_flow_kg_s':i+1} for i,n in enumerate(self.cfg['outlets'])]
        r = p.responses(self.cfg, rows)
        self.assertEqual(r['total_mass_flow_kg_s'],15)
        self.assertAlmostEqual(r['cv'], math.sqrt(2)/3)
        self.assertAlmostEqual(r['cv_percent'], 100*math.sqrt(2)/3)
    def test_invalid_flow_and_mapping(self):
        rows = [{'outlet':n,'mass_flow_kg_s':1} for n in self.cfg['outlets']]
        self.assertEqual(p.responses(self.cfg, rows)['cv'], 0)
        for value in [-1, float('nan'), float('inf')]:
            rows[0]['mass_flow_kg_s'] = value
            with self.assertRaises(ValueError): p.responses(self.cfg,rows)
        with self.assertRaises(ValueError): p.responses(self.cfg,rows[:4])
        rows = [{'outlet':self.cfg['outlets'][0],'mass_flow_kg_s':1}]*5
        with self.assertRaises(ValueError): p.responses(self.cfg,rows)
    def test_bounds_and_names(self):
        values = {v['name']:v['baseline'] for v in self.cfg['variables']}
        p.parameters(self.cfg, values)
        values[next(iter(values))] = 100
        with self.assertRaises(ValueError): p.parameters(self.cfg, values)
        with self.assertRaises(ValueError): p.doe(self.cfg,0,42)
    def test_stage_failure_and_stale_artifact(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); manifest=root/'local.json'
            stage={'name':'fake','command':[sys.executable,'-c',"from pathlib import Path; Path('result').write_text('ok')"],'outputs':['result']}
            manifest.write_text(json.dumps({'stages':[stage]}))
            p.run_local(manifest,True)
            with self.assertRaises(ValueError): p.run_local(manifest,True)
            (root/'result').unlink()
            stage['command']=[sys.executable,'-c','raise SystemExit(2)']
            manifest.write_text(json.dumps({'stages':[stage]}))
            with self.assertRaises(p.subprocess.CalledProcessError): p.run_local(manifest,True)

if __name__=='__main__': unittest.main()
