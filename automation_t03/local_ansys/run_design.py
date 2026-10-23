"""T03 pilot-first local orchestration. No CFD action is the default."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
sys.path.insert(0,str(ROOT))
from pipeline import cad, read, write, parameters


def digest(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def fingerprint():
    paths=list(HERE.glob('*.py'))+[HERE/'requirements-local.txt']+[ROOT/'t03_geometry.py',ROOT/'t03_variables.json',ROOT/'pipeline.py']
    return {p.name:digest(p) for p in sorted(paths)}


def baseline_inputs():
    return {v['name']:v['baseline'] for v in read(ROOT/'t03_variables.json')['variables']}


def ensure_windows():
    if os.name!='nt': raise RuntimeError('ANSYS execution is Windows-only; cloud mode supports prepare/tests only')


def check_job(job):
    job=Path(job).resolve()
    p=read(job/'prepared.json')
    if p['code_fingerprint']!=fingerprint(): raise ValueError('Code changed: prepare a fresh job')
    for name,value in p['file_hashes'].items():
        if digest(job/name)!=value: raise ValueError('Prepared input artifact changed: '+name)
    return job,p


def owned_process(command,cwd,log,timeout):
    # Kill only this command's own process tree after a timeout, never all ANSYS processes.
    with Path(log).open('w',encoding='utf-8') as f:
        proc=subprocess.Popen(command,cwd=cwd,stdout=f,stderr=subprocess.STDOUT)
        try:
            code=proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            subprocess.run(['taskkill','/PID',str(proc.pid),'/T','/F'],check=False,stdout=f,stderr=subprocess.STDOUT)
            proc.wait(timeout=30)
            raise RuntimeError('Owned ANSYS process timed out; see '+str(log))
        if code: raise RuntimeError('Command exited '+str(code)+'; see '+str(log))


def prepare(inputs,job,template):
    values=parameters(read(ROOT/'t03_variables.json'),read(inputs))
    job=Path(job).resolve()
    job.mkdir(parents=True,exist_ok=False)
    write(job/'status.json',{'status':'PREPARING','fluent_executed':False})
    try:
        write(job/'inputs.json',values)
        source=Path(template).resolve()
        if not source.is_file(): raise ValueError('Team settings case is required')
        with source.open('rb') as stream:
            if stream.read(8)!=b'\x89HDF\r\n\x1a\n': raise ValueError('Template is not an HDF5 case file')
        shutil.copyfile(source,job/'settings_template.cas.h5')
        geometry=cad(read(ROOT/'t03_variables.json'),values,ROOT/'t03_geometry.py',job/'T03.step')
        # Workbench uses IronPython. repr produces a valid quoted literal, and
        # forward slashes avoid Windows string escape ambiguities.
        mech_command='T03_JOB = '+repr(job.as_posix())+'\nT03_CODE = '+repr(HERE.as_posix())+'\nexec(compile(open('+repr((HERE/'mechanical_mesh.py').as_posix())+').read(), "mechanical_mesh.py", "exec"))'
        journal='''# ANSYS Workbench 2025 R2 batch journal; fresh project only.
SetScriptVersion(Version="25.2.0")
system = GetTemplate(TemplateName="Fluid Flow", Solver="Fluent").CreateSystem()
geometry = system.GetContainer(ComponentName="Geometry")
geometry.SetFile(FilePath=%s)
system.GetComponent(Name="Geometry").Update(AllDependencies=True)
system.GetComponent(Name="Mesh").Refresh()
container = system.GetContainer(ComponentName="Mesh")
try:
    container.Edit()
    container.SendCommand(Language="Python", Command=%s)
finally:
    container.Exit()
Save(FilePath=%s, Overwrite=True)
''' % (repr((job/'T03.step').as_posix()),repr(mech_command),repr((job/'meshing.wbpj').as_posix()))
        (job/'mesh.wbjn').write_text(journal,encoding='utf-8')
        write(job/'prepared.json',dict(schema=1,geometry=geometry,code_fingerprint=fingerprint(),
              file_hashes={n:digest(job/n) for n in ['inputs.json','T03.step','settings_template.cas.h5','mesh.wbjn']}))
        write(job/'status.json',{'status':'PREPARED_NO_ANSYS_EXECUTED','fluent_executed':False})
    except Exception as e:
        write(job/'status.json',{'status':'FAILED_PREPARATION','error':str(e),'fluent_executed':False})
        raise


def mesh(job,workbench,timeout):
    ensure_windows()
    job,p=check_job(job)
    if any((job/n).exists() for n in ['mesh.msh','mesh_audit.json','mesh_receipt.json']): raise ValueError('Mesh outputs already exist; prepare a fresh job')
    owned_process([str(Path(workbench).resolve()),'-B','-R',str(job/'mesh.wbjn')],job,job/'workbench.log',timeout)
    audit=read(job/'mesh_audit.json')
    if audit['status']!='MESH_EXPORTED' or audit['minimum_orthogonal_quality']<0.1 or audit['maximum_skewness']>0.95:
        raise ValueError('Meshing audit gate failed')
    for n in ['mesh.msh','mesh_audit.json']:
        if (job/n).stat().st_size==0: raise ValueError('Empty mesh artifact')
    write(job/'mesh_receipt.json',dict(inputs_sha256=digest(job/'inputs.json'),mesh_sha256=digest(job/'mesh.msh'),audit_sha256=digest(job/'mesh_audit.json'),code_fingerprint=fingerprint()))
    write(job/'status.json',{'status':'MESHED_NOT_SOLVED','fluent_executed':False})


def pilot_receipt(path):
    receipt=read(path)
    pilot=Path(receipt['job'])
    if receipt['code_fingerprint']!=fingerprint(): raise ValueError('Pilot uses different code/config')
    if receipt['validation_status']!='LOCAL_T03_2500_REPRODUCTION_PASS': raise ValueError('Invalid pilot validation')
    for name,sha in receipt['artifact_hashes'].items():
        if digest(pilot/name)!=sha: raise ValueError('Pilot evidence changed')
    return receipt


def solve(job,pressures,processors,timeout,pilot):
    ensure_windows()
    job,p=check_job(job)
    if processors<1: raise ValueError('processors must be positive')
    values=read(job/'inputs.json')
    if pressures!=[2500] or values!=baseline_inputs():
        if pilot is None: raise ValueError('Validate T03 2500 pilot before 600 Pa or non-T03 DOE')
        pilot_receipt(pilot)
    receipt=read(job/'mesh_receipt.json')
    if receipt['inputs_sha256']!=digest(job/'inputs.json') or receipt['mesh_sha256']!=digest(job/'mesh.msh') or receipt['audit_sha256']!=digest(job/'mesh_audit.json') or receipt['code_fingerprint']!=fingerprint(): raise ValueError('Mesh evidence changed')
    if (job/'responses.json').exists() or any((job/(str(p)+'Pa')).exists() for p in pressures):
        raise ValueError('Solver outputs exist; use a fresh job, never reuse DOE output')
    write(job/'status.json',{'status':'RUNNING','requested_pressures_pa':pressures})
    combined={}
    try:
        for pressure in pressures:
            owned_process([sys.executable,str(HERE/'fluent_worker.py'),str(job),str(pressure),str(job/'settings_template.cas.h5'),'--processors',str(processors)],job,job/(str(pressure)+'Pa-worker.log'),timeout)
            result=read(job/(str(pressure)+'Pa')/'responses.json')
            diagnostic=read(job/(str(pressure)+'Pa')/'diagnostics.json')
            if not diagnostic['fluent_executed'] or not diagnostic['convergence']['pass_convergence']: raise ValueError('No successful convergence evidence')
            for key,value in result.items():
                if not isinstance(value,(int,float)) or not math.isfinite(value): raise ValueError('Invalid numeric response')
                combined[key+'_'+str(pressure)+'Pa']=value
        # Converged designs below the throughput bound retain numeric responses
        # as infeasible constraints, while solver/convergence failures emit none.
        combined['feasible']=int(all(combined['flow_constraint_met_'+str(p)+'Pa'] for p in pressures))
        write(job/'responses.json',combined)
        write(job/'status.json',{'status':'CONVERGED_FEASIBLE' if combined['feasible'] else 'CONVERGED_INFEASIBLE','fluent_executed':True,'final_design_acceptance':'WITHHELD'})
    except Exception as e:
        (job/'responses.json').unlink(missing_ok=True)
        write(job/'status.json',{'status':'FAILED_DO_NOT_TRAIN','error':str(e),'requested_pressures_pa':pressures})
        raise


def validate_pilot(job):
    job,p=check_job(job)
    if read(job/'inputs.json')!=baseline_inputs(): raise ValueError('Pilot must be T03 reference parameters')
    if read(job/'status.json')['status']!='CONVERGED_FEASIBLE': raise ValueError('Pilot must converge and meet throughput')
    audit=read(job/'mesh_audit.json')
    if audit['face_count']!=14 or not math.isclose(audit['cells'],474676,rel_tol=0.05) or not math.isclose(audit['nodes'],101832,rel_tol=0.05):
        raise ValueError('Pilot topology/counts differ materially from report; investigate mesh settings')
    result=read(job/'2500Pa/responses.json')
    diagnostic=read(job/'2500Pa/diagnostics.json')
    if not diagnostic['fluent_executed'] or not diagnostic['convergence']['pass_convergence']: raise ValueError('Pilot CFD evidence missing')
    # Engineering reproduction tolerances for the first local check, not report
    # acceptance requirements. Explicit and intentionally recorded in receipt.
    if not math.isclose(result['cv_percent'],5.30797196814,rel_tol=0.02) or not math.isclose(result['full_mass_flow_g_s'],3.0143638,rel_tol=0.01):
        raise ValueError('Pilot differs from report (CV 2%, throughput 1% relative tolerances); inspect before expansion')
    artifacts=['inputs.json','T03.step','mesh.msh','mesh_audit.json','mesh_receipt.json','settings_template.cas.h5','responses.json','status.json',
               '2500Pa/responses.json','2500Pa/diagnostics.json','2500Pa/settings_audit.json','2500Pa/mesh_checks.json','2500Pa/residuals.xy','2500Pa/flux_600.json','2500Pa/flux_700.json','2500Pa/solved.cas.h5','2500Pa/solved.dat.h5']
    write(job/'pilot_validation.json',dict(validation_status='LOCAL_T03_2500_REPRODUCTION_PASS',job=str(job),code_fingerprint=fingerprint(),
          tolerances=dict(cv_relative=0.02,full_flow_relative=0.01,mesh_counts_relative=0.05),artifact_hashes={n:digest(job/n) for n in artifacts},
          note='Reproduction gate only; no final design or mesh-independence certification'))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='action',required=True)
    p=sub.add_parser('prepare');p.add_argument('--inputs',required=True);p.add_argument('--job',required=True);p.add_argument('--template',required=True)
    p=sub.add_parser('mesh');p.add_argument('--job',required=True);p.add_argument('--workbench',default='C:/Program Files/ANSYS Inc/v252/Framework/bin/Win64/RunWB2.exe');p.add_argument('--timeout',type=int,default=7200)
    p=sub.add_parser('solve');p.add_argument('--job',required=True);p.add_argument('--pressures',nargs='+',choices=[600,2500],type=int,default=[2500]);p.add_argument('--processors',type=int,default=4);p.add_argument('--timeout',type=int,default=14400);p.add_argument('--pilot-validation')
    p=sub.add_parser('validate-pilot');p.add_argument('--job',required=True)
    a=parser.parse_args()
    if a.action=='prepare':prepare(a.inputs,a.job,a.template)
    elif a.action=='mesh':mesh(a.job,a.workbench,a.timeout)
    elif a.action=='solve':
        if len(set(a.pressures))!=len(a.pressures):parser.error('duplicate pressure')
        solve(a.job,a.pressures,a.processors,a.timeout,a.pilot_validation)
    else:validate_pilot(a.job)

if __name__=='__main__':
    try:main()
    except Exception as exc:
        print('FAILED: '+str(exc),file=sys.stderr)
        sys.exit(1)
