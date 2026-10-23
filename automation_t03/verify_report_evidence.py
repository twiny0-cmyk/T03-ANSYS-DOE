"""Recalculate published outlet table and supplied JSON; never launches ANSYS."""
import argparse
import csv
import hashlib
import math
from pathlib import Path
from pipeline import doe, parameters, read, responses, write

ROOT=Path(__file__).resolve().parent
SOURCE=ROOT/'reference_inputs/team_additions'


def verify(output):
    dest=Path(output)
    cfg=read(ROOT/'t03_variables.json')
    report_cfg=dict(cfg,outward_sign=1)
    with (SOURCE/'report_outlets_transcribed.csv').open(newline='',encoding='utf-8') as f: rows=list(csv.DictReader(f))
    results=[]
    for row in rows:
        flows=[{'outlet':f'outlet_{i}','mass_flow_kg_s':float(row[f'outlet_{i}_half_g_s'])/1000} for i in range(1,6)]
        r=responses(report_cfg,flows)
        r.update(design_id=row['design_id'],pressure_pa=float(row['pressure_pa']),full_mass_flow_g_s=2000*r['total_mass_flow_kg_s'],reported_convergence=row['reported_convergence'],source='PDF section 5.1, printed page 4; manually transcribed rounded outlet values',fluent_rerun=False)
        # Allow rounding of the published five-decimal CV and eight-decimal flows.
        if not math.isclose(r['cv_percent'],float(row['reported_cv_percent']),abs_tol=0.000006): raise ValueError('Report CV mismatch')
        if not math.isclose(r['full_mass_flow_g_s'],float(row['reported_full_g_s']),abs_tol=0.00000002): raise ValueError('Report flow mismatch')
        r['flow_threshold_g_s']=2.992509 if r['pressure_pa']==2500 else 1.32315
        r['flow_threshold_kind']='specified_2500Pa_lower_bound' if r['pressure_pa']==2500 else 'provisional_failed_baseline_comparison'
        r['numeric_flow_threshold_met']=r['full_mass_flow_g_s']>=r['flow_threshold_g_s']-1e-12
        r['final_design_acceptance']='WITHHELD'
        results.append(r)
    data=read(SOURCE/'fluent_result.json')
    signed=data['mass_flow']['signed_kg_s']
    if signed['inlet']<=0 or any(signed[n]>=0 for n in cfg['outlets']): raise ValueError('Unexpected signed mass-flow convention')
    j=responses(cfg,[{'outlet':n,'mass_flow_kg_s':signed[n]} for n in cfg['outlets']])
    j['full_mass_flow_g_s']=2000*j['total_mass_flow_kg_s']
    j['mass_imbalance_percent']=100*abs(signed['inlet']-j['total_mass_flow_kg_s'])/abs(signed['inlet'])
    for field,key in [('cv_percent','outlet_population_cv_percent'),('full_mass_flow_g_s','full_model_total_g_s')]:
        if not math.isclose(j[field],data['mass_flow'][key],abs_tol=1e-10): raise ValueError('JSON arithmetic mismatch')
    c=data['convergence']
    residual_pass=all(c['sustained_last_20_residual_max'][k]<=limit for k,limit in c['residual_acceptance_limits'].items())
    j['residual_gate_recomputed']=residual_pass
    j['mass_balance_gate_recomputed']=j['mass_imbalance_percent']<c['mass_imbalance_limit_percent']
    j['flow_stability_gate_from_recorded_changes']=max(c['outlet_change_percent_over_final_block'].values())<c['flow_stability_limit_percent']
    j['convergence_gate_from_recorded_metrics']=all([residual_pass,j['mass_balance_gate_recomputed'],j['flow_stability_gate_from_recorded_changes']])
    if j['convergence_gate_from_recorded_metrics'] != c['pass']: raise ValueError('JSON convergence gate mismatch')
    j.update(source='uploaded fluent_result.json; not a solver rerun',fluent_rerun=False,history_independently_verified=False)
    b=next(r for r in results if r['design_id']=='baseline_fair' and r['pressure_pa']==600)
    if not math.isclose(j['cv_percent'],b['cv_percent'],abs_tol=1e-10): raise ValueError('Report/JSON mismatch')
    write(dest/'baseline_600_json_recalculated.json',j)
    write(dest/'report_outlets_recalculated.json',{'results':results})
    t03=doe(cfg,4,42)[0]['parameters']
    for r in results:
        if r['design_id']!='T03': continue
        case=dest/f"T03_{int(r['pressure_pa'])}Pa"
        write(case/'inputs.json',parameters(cfg,t03))
        write(case/'condition.json',{'pressure_pa':r['pressure_pa'],'pressure_type':'inlet_gauge_total','source':'PDF section 4'})
        output_values={k:r[k] for k in ['cv','cv_percent','full_mass_flow_g_s','pressure_pa']}
        write(case/'responses.json',output_values)
        write(case/'provenance.json',r)
        if read(case/'responses.json')!=output_values or read(case/'inputs.json')!=t03: raise ValueError('File replay failed')
    manifest=[]
    for p in sorted(SOURCE.iterdir()):
        if p.is_file(): manifest.append({'file':p.name,'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
    case=SOURCE/'baseline_fair_600Pa_result.cas.h5'
    with case.open('rb') as f:
        if f.read(8)!=b'\x89HDF\r\n\x1a\n': raise ValueError('Case HDF5 signature mismatch')
    write(dest/'source_manifest.json',{'files':manifest,'case_check':'HDF5 signature only; Fluent contents not loaded','data_file_available':False,'fluent_rerun':False})
    return results,j

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('output');a=p.parse_args()
    results,j=verify(a.output)
    for r in results: print(r['design_id'],r['pressure_pa'],r['cv_percent'],r['full_mass_flow_g_s'],r['reported_convergence'])
    print('Baseline 600 convergence from recorded metrics:',j['convergence_gate_from_recorded_metrics'])
