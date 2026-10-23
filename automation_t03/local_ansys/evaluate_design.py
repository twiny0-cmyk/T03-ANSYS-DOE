"""optiSLang external process: success-only flat numeric response JSON."""
import argparse
from pathlib import Path
import shutil
import sys
from run_design import prepare, mesh, solve, ensure_windows


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--inputs',default='inputs.json');p.add_argument('--job',default='ansys_run');p.add_argument('--output',default='responses.json')
    p.add_argument('--template',required=True)
    p.add_argument('--workbench',default='C:/Program Files/ANSYS Inc/v252/Framework/bin/Win64/RunWB2.exe')
    p.add_argument('--pressures',nargs='+',type=int,choices=[600,2500],default=[2500])
    p.add_argument('--processors',type=int,default=4);p.add_argument('--pilot-validation')
    a=p.parse_args()
    ensure_windows()
    if len(set(a.pressures))!=len(a.pressures):p.error('duplicate pressure')
    output=Path(a.output).resolve();job=Path(a.job).resolve()
    if output.exists():raise ValueError('Output already exists; use an isolated fresh evaluation directory')
    if output==Path(a.inputs).resolve() or output==Path(a.template).resolve() or output==job/'responses.json': raise ValueError('Output path must be separate from inputs/template/internal output')
    # No placeholder outputs and no copying on exceptions. Caller must treat
    # a nonzero process exit as failed design and ignore all diagnostic numbers.
    prepare(a.inputs,job,a.template)
    mesh(job,a.workbench,7200)
    solve(job,a.pressures,a.processors,14400,a.pilot_validation)
    output.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(job/'responses.json',output)

if __name__=='__main__':
    try:main()
    except Exception as e:
        print('FAILED_DO_NOT_TRAIN: '+str(e),file=sys.stderr)
        sys.exit(1)
