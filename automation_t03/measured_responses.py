"""Strict adapter for the team's wide half-model CSV, preserving magnitude convention."""
import argparse
import csv
import math
from pathlib import Path
from pipeline import read, responses, write


def calculate(config, records):
    converted=[]
    seen=set()
    for row in records:
        key=(row['design_id'],float(row['pressure_pa']))
        if key in seen: raise ValueError('Duplicate design/pressure result')
        seen.add(key)
        if not math.isfinite(key[1]) or key[1] <= 0: raise ValueError('Invalid pressure')
        inlet=abs(float(row['inlet_half_kg_s']))
        if not math.isfinite(inlet) or inlet <= 0: raise ValueError('Invalid inlet')
        flows=[float(row[f'outlet_{i}_half_kg_s']) for i in range(1,6)]
        if any(not math.isfinite(q) for q in flows): raise ValueError('Nonfinite outlet')
        # Existing team checker accepts signed or magnitude reports. Mixed signs
        # remain ambiguous and are rejected rather than hiding potential backflow.
        if any(q < 0 for q in flows) and any(q > 0 for q in flows):
            raise ValueError('Mixed outlet signs; inspect backflow/report convention')
        cfg=dict(config, outward_sign=1)
        result=responses(cfg,[{'outlet':name,'mass_flow_kg_s':abs(q)} for name,q in zip(cfg['outlets'],flows)])
        total=result.pop('total_mass_flow_kg_s')
        result.update(design_id=key[0],pressure_pa=key[1],half_mass_flow_kg_s=total,full_mass_flow_kg_s=2*total,full_mass_flow_g_s=2000*total,mass_imbalance_percent=100*abs(inlet-total)/inlet)
        converted.append(result)
    baselines={r['pressure_pa']:r for r in converted if r['design_id'].lower()=='baseline'}
    for r in converted:
        baseline=baselines.get(r['pressure_pa'])
        r['flow_constraint_pass']=None if baseline is None else r['full_mass_flow_kg_s']>=baseline['full_mass_flow_kg_s']-1e-13
        r['baseline_available']=baseline is not None
    return converted

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('config');p.add_argument('csv');p.add_argument('output')
    p.add_argument('--design'); p.add_argument('--pressure',type=float)
    a=p.parse_args()
    with open(a.csv,encoding='utf-8-sig',newline='') as f: result=calculate(read(a.config),list(csv.DictReader(f)))
    if a.design is not None or a.pressure is not None:
        if a.design is None or a.pressure is None: p.error('--design and --pressure are required together')
        selected=[r for r in result if r['design_id']==a.design and r['pressure_pa']==a.pressure]
        if len(selected)!=1: raise ValueError('Exactly one matching measured result required')
        # Flat numeric JSON for optiSLang response registration.
        write(a.output,{k:v for k,v in selected[0].items() if isinstance(v,(int,float)) and not isinstance(v,bool)})
    else:
        write(a.output,{'results':result})
