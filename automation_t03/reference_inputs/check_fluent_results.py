"""Check measured Fluent half-domain outlet mass-flow CV and throughput.

Usage: python check_fluent_results.py fluent_results.csv
Convention: population CV = 100*sqrt(mean((abs(q_i)-mean)^2))/mean.
Do not interpret surrogate calculations as CFD measurements.
"""
import csv, math, sys
from collections import defaultdict

path = sys.argv[1] if len(sys.argv)>1 else 'fluent_results.csv'
with open(path,encoding='utf-8-sig',newline='') as f:
    records = list(csv.DictReader(f))
calc=[]
for r in records:
    try:
        q=[abs(float(r[f'outlet_{i}_half_kg_s'])) for i in range(1,6)]
        inlet=abs(float(r['inlet_half_kg_s']))
        p=int(float(r['pressure_pa']))
    except (ValueError, KeyError) as ex:
        print('Skip incomplete row',r.get('design_id'),ex)
        continue
    if inlet==0 or sum(q)==0:
        print('Skip zero flow',r.get('design_id'));continue
    mean=sum(q)/5
    cv=100*math.sqrt(sum((v-mean)**2 for v in q)/5)/mean
    qtotal=sum(q)
    mass=abs(inlet-qtotal)/inlet*100
    calc.append(dict(design_id=r['design_id'],p=p,cv=cv,full_gs=2*qtotal*1000,mass_pct=mass))
base={r['p']:r for r in calc if r['design_id'].lower()=='baseline'}
print(f"{'id':<23}{'Pa':>7}{'CV %':>12}{'full g/s':>13}{'balance %':>14}{'flow vs baseline':>18}")
for r in calc:
    b=base.get(r['p'])
    flow_ok= 'baseline' if r['design_id'].lower()=='baseline' else 'NO MATCHING BASELINE' if b is None else ('PASS' if r['full_gs']>=b['full_gs']-1e-10 else 'FAIL')
    print(f"{r['design_id']:<23}{r['p']:>7}{r['cv']:>12.6f}{r['full_gs']:>13.6f}{r['mass_pct']:>14.6f}{flow_ok:>18}")
