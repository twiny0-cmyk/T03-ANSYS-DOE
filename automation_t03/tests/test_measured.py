import csv
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from measured_responses import calculate
from pipeline import read

class MeasuredTests(unittest.TestCase):
    def setUp(self):
        root=Path(__file__).resolve().parents[1]
        self.cfg=read(root/'t03_variables.json')
        with (root/'reference_inputs/fluent_results.csv').open(encoding='utf-8-sig',newline='') as f: self.rows=list(csv.DictReader(f))
    def test_team_baseline(self):
        r=calculate(self.cfg,self.rows)[0]
        self.assertAlmostEqual(r['cv_percent'],19.63900694,places=7)
        self.assertAlmostEqual(r['full_mass_flow_g_s'],2.99250874,places=8)
        self.assertLess(r['mass_imbalance_percent'],0.001)
        self.assertTrue(r['flow_constraint_pass'])
    def test_pressure_baseline_and_duplicates(self):
        self.rows[0]['design_id']='T03'
        self.assertIsNone(calculate(self.cfg,self.rows)[0]['flow_constraint_pass'])
        with self.assertRaises(ValueError): calculate(self.cfg,self.rows*2)
    def test_mixed_signs(self):
        self.rows[0]['outlet_1_half_kg_s']='0.001'
        with self.assertRaises(ValueError): calculate(self.cfg,self.rows)
