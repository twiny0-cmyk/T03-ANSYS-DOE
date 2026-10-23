"""Write reference T03 inputs without changing the source metadata."""
import argparse
from pathlib import Path
from run_design import baseline_inputs, write
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('output');a=p.parse_args()
    if Path(a.output).exists():raise ValueError('Refusing to overwrite existing input file')
    write(a.output,baseline_inputs())
