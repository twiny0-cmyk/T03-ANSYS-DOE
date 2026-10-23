import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from verify_report_evidence import verify
from pipeline import read

class ReportEvidenceTests(unittest.TestCase):
    def test_outlet_recalculation_and_file_replay(self):
        with tempfile.TemporaryDirectory() as d:
            results,j=verify(d)
            self.assertEqual(len(results),6)
            self.assertFalse(j['convergence_gate_from_recorded_metrics'])
            self.assertTrue(j['mass_balance_gate_recomputed'])
            for p,cv,flow in [(600,6.613249882355158,1.36513888),(2500,5.307971968141562,3.0143638)]:
                case=Path(d)/f'T03_{p}Pa'
                r=read(case/'responses.json')
                self.assertAlmostEqual(r['cv_percent'],cv)
                self.assertAlmostEqual(r['full_mass_flow_g_s'],flow)
                self.assertEqual(len(read(case/'inputs.json')),13)
                self.assertFalse(read(case/'provenance.json')['fluent_rerun'])
            self.assertFalse(read(Path(d)/'source_manifest.json')['data_file_available'])
