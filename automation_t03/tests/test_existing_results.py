import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from verify_existing_results import verify
from pipeline import read

class ExistingResultsTests(unittest.TestCase):
    def test_failed_baseline_is_not_qualified(self):
        with tempfile.TemporaryDirectory() as d:
            records=verify(d)
            t03=next(r for r in records if r['design_id']=='T03' and r['pressure_pa']==600)
            self.assertTrue(t03['flow_comparison_pass'])
            self.assertIsNone(t03['qualified_design_pass'])
            self.assertFalse(t03['cv_recomputed_from_outlets'])
            self.assertFalse(t03['fluent_rerun'])
    def test_report_file_interface_and_raw_evidence(self):
        with tempfile.TemporaryDirectory() as d:
            records=verify(d)
            for pressure,cv in [(600,6.61325),(2500,5.30797)]:
                root=Path(d)/f'T03_{pressure}Pa'
                self.assertEqual(len(read(root/'inputs.json')),13)
                self.assertEqual(read(root/'responses.json')['cv_percent'],cv)
                self.assertEqual(read(root/'provenance.json')['source_kind'],'user_transcribed_report_not_inspected')
            raw=next(r for r in records if r['design_id']=='baseline' and r['pressure_pa']==2500)
            self.assertTrue(raw['cv_recomputed_from_outlets'])
            self.assertEqual(raw['convergence'],'UNKNOWN')
            self.assertAlmostEqual(raw['cv_percent'],19.63900694158)
