"""Synthetic fixtures below test logic only; none represent a CFD calculation."""
import math
from pathlib import Path
import sys
import unittest
sys.path[:0]=[str(Path(__file__).resolve().parents[1]/'local_ansys'),str(Path(__file__).resolve().parents[1])]
from boundaries import classify, expected
from gates import parse_residual_xy, evaluate, LIMITS, OUTLETS
from fluent_worker import scalar
from run_design import baseline_inputs

class BoundaryTests(unittest.TestCase):
    def fixtures(self):
        p=baseline_inputs();faces=[]
        def cap(name,axis,value,r,x):
            c=[x,0,4*r/(3*math.pi)]
            c[axis]=value
            n=[0,0,0];n[axis]=1
            vertices=[list(c),list(c)]
            faces.append(dict(id=len(faces),planar=True,centroid=c,normal=n,vertices=vertices,area=math.pi*r*r/2))
        cap('inlet',0,0,.004,0)
        cap('wall_end',0,.320,.004,.320)
        for x,y,r in expected(p):cap('outlet',1,y,r,x)
        faces.append(dict(id=7,planar=True,centroid=[.16,0,0],normal=[0,0,1],vertices=[[0,0,0],[.320,0,0]],area=.002))
        faces.append(dict(id=8,planar=False,centroid=[.1,0,.002],normal=[0,0,0],vertices=[[0,0,0],[.320,0,0]],area=.002))
        return p,faces
    def test_named_selection_coverage(self):
        p,f=self.fixtures();groups=classify(list(reversed(f)),p)
        self.assertEqual(groups['outlet_1'],[2]);self.assertEqual(groups['outlet_5'],[6])
        self.assertEqual(sum(map(len,groups.values())),len(f))
    def test_cap_area_and_duplicate_detection(self):
        p,f=self.fixtures();f[2]['area']*=2
        with self.assertRaises(ValueError):classify(f,p)
        p,f=self.fixtures()
        with self.assertRaises(ValueError):classify(f+f[:1],p)
    def test_wrong_units_or_missing_boundary(self):
        p,f=self.fixtures()
        with self.assertRaises(ValueError):classify(f[1:],p)
        p,f=self.fixtures()
        for face in f:face['vertices']=[[1000*x for x in v] for v in face['vertices']]
        with self.assertRaises(ValueError):classify(f,p)

class ConvergenceTests(unittest.TestCase):
    def history(self):return {n:[(i,1e-6) for i in range(681,701)] for n in LIMITS}
    def flows(self):return dict(inlet=.0005,**{n:-.0001 for n in OUTLETS})
    def test_converged_gate(self):self.assertTrue(evaluate(self.history(),self.flows(),self.flows())['pass_convergence'])
    def test_sustained_residual_not_just_last(self):
        h=self.history();h['continuity'][0]=(681,1.4e-4)
        self.assertFalse(evaluate(h,self.flows(),self.flows())['pass_convergence'])
    def test_mass_balance_and_final_block_stability(self):
        f=self.flows();f['inlet']*=1.01
        self.assertFalse(evaluate(self.history(),self.flows(),f)['pass_convergence'])
        f=self.flows();f['outlet_1']*=1.002
        self.assertFalse(evaluate(self.history(),f,self.flows())['flow_stability_pass'])
    def test_stale_history_and_reverse_flow(self):
        h=self.history();h['k']=h['k'][:-1]
        with self.assertRaises(ValueError):evaluate(h,self.flows(),self.flows())
        f=self.flows();f['outlet_1']=.0001
        with self.assertRaises(ValueError):evaluate(self.history(),f,self.flows())
    def test_residual_xy_parser(self):
        text='\n'.join('((xy/key/label "'+n+'")\n'+'\n'.join(str(i)+' 1e-6' for i in range(681,701))+'\n)' for n in LIMITS)
        self.assertTrue(evaluate(parse_residual_xy(text),self.flows(),self.flows())['pass_convergence'])
        with self.assertRaises(ValueError):parse_residual_xy(text.replace('"omega"','"unknown"'))
    def test_no_arbitrary_query_number(self):
        self.assertEqual(scalar({'outlet_1':.01},'outlet_1'),.01)
        for value in [{'other':.01},{'outlet_1':float('nan')},[.01]]:
            with self.assertRaises(ValueError):scalar(value,'outlet_1')

try:
    import cadquery
except ImportError:
    cadquery=None

@unittest.skipIf(cadquery is None,'CadQuery geometry validation requires CAD venv')
class CadBoundaryTests(unittest.TestCase):
    def test_real_t03_and_changed_design(self):
        from t03_geometry import build_geometry
        p=baseline_inputs()
        changed=dict(p,g1=30,g2=60,g3=40,L_b1=40,L_b5=80,D_b1=6,D_b5=4)
        for values in [p,changed]:
            solid=build_geometry(values)
            faces=[]
            for i,f in enumerate(solid.Faces()):
                faces.append(dict(id=i,planar=f.geomType()=='PLANE',centroid=[x/1000 for x in f.Center().toTuple()],normal=list(f.normalAt().toTuple()),vertices=[[x/1000 for x in v.toTuple()] for v in f.Vertices()],area=f.Area()/1e6))
            groups=classify(faces,values)
            self.assertEqual(len(faces),14)
            self.assertEqual(len(set(i for group in groups.values() for i in group)),14)

class OrchestrationFailureTests(unittest.TestCase):
    def make_job(self,root):
        import run_design as r
        job=Path(root)
        from pipeline import write
        write(job/'inputs.json',r.baseline_inputs())
        (job/'mesh.msh').write_text('synthetic test mesh artifact; not CFD')
        write(job/'mesh_audit.json',{'synthetic_test_fixture':True})
        write(job/'mesh_receipt.json',dict(inputs_sha256=r.digest(job/'inputs.json'),mesh_sha256=r.digest(job/'mesh.msh'),audit_sha256=r.digest(job/'mesh_audit.json'),code_fingerprint=r.fingerprint()))
        return job
    def test_solver_failure_emits_no_master_response(self):
        import tempfile
        from unittest.mock import patch
        import run_design as r
        with tempfile.TemporaryDirectory() as d:
            job=self.make_job(d)
            with patch.object(r,'ensure_windows'),patch.object(r,'check_job',return_value=(job,{})),patch.object(r,'owned_process',side_effect=RuntimeError('synthetic solver failure')):
                with self.assertRaises(RuntimeError):r.solve(job,[2500],4,1,None)
            self.assertFalse((job/'responses.json').exists())
            self.assertEqual(r.read(job/'status.json')['status'],'FAILED_DO_NOT_TRAIN')
    def test_failed_convergence_cannot_promote_response(self):
        import tempfile
        from unittest.mock import patch
        import run_design as r
        def fake_worker(command,*args):
            case=Path(command[2])/'2500Pa';case.mkdir()
            r.write(case/'responses.json',{'cv_percent':0})
            r.write(case/'diagnostics.json',{'fluent_executed':False,'convergence':{'pass_convergence':False}})
        with tempfile.TemporaryDirectory() as d:
            job=self.make_job(d)
            with patch.object(r,'ensure_windows'),patch.object(r,'check_job',return_value=(job,{})),patch.object(r,'owned_process',side_effect=fake_worker):
                with self.assertRaises(ValueError):r.solve(job,[2500],4,1,None)
            self.assertFalse((job/'responses.json').exists())
    def test_600_requires_validated_pilot(self):
        import tempfile
        from unittest.mock import patch
        import run_design as r
        with tempfile.TemporaryDirectory() as d:
            job=self.make_job(d)
            with patch.object(r,'ensure_windows'),patch.object(r,'check_job',return_value=(job,{})),patch.object(r,'owned_process') as launch:
                with self.assertRaises(ValueError):r.solve(job,[600],4,1,None)
                launch.assert_not_called()
