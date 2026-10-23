"""Verify file coupling without claiming a Fluent rerun or inspecting unavailable PDF."""
import argparse
import csv
import math
from pathlib import Path
from measured_responses import calculate
from pipeline import doe, parameters, read, write

ROOT = Path(__file__).resolve().parent


def assess(summary_rows, raw_results):
    records=[]
    keys=set()
    for row in summary_rows:
        r=dict(row)
        for key in ('pressure_pa','cv_percent','full_mass_flow_g_s'):
            r[key]=float(row[key])
            if not math.isfinite(r[key]) or r[key]<0: raise ValueError('Invalid summary number')
        if r['convergence'] not in ('PASS','FAIL'): raise ValueError('Unknown convergence')
        key=(r['design_id'].lower(),r['pressure_pa'])
        if key in keys: raise ValueError('Duplicate summary design/pressure')
        keys.add(key)
        r.update(cv_recomputed_from_outlets=False,fluent_rerun=False,pdf_inspected=False)
        records.append(r)
    for raw in raw_results:
        key=(raw['design_id'].lower(),raw['pressure_pa'])
        if key in keys: raise ValueError('Raw/report collision requires explicit reconciliation')
        records.append({'design_id':raw['design_id'],'pressure_pa':raw['pressure_pa'],'cv_percent':raw['cv_percent'],'full_mass_flow_g_s':raw['full_mass_flow_g_s'],'convergence':'UNKNOWN','source_kind':'uploaded_outlet_csv_recomputed','cv_recomputed_from_outlets':True,'fluent_rerun':False,'pdf_inspected':False})
    baselines={r['pressure_pa']:r for r in records if r['design_id'].lower()=='baseline'}
    for r in records:
        if r['design_id'].lower()=='baseline': continue
        b=baselines.get(r['pressure_pa'])
        if b is None:
            r.update(flow_difference_g_s=None,flow_difference_percent=None,flow_comparison_pass=None)
        else:
            r['flow_difference_g_s']=r['full_mass_flow_g_s']-b['full_mass_flow_g_s']
            r['flow_difference_percent']=None if b['full_mass_flow_g_s']==0 else 100*r['flow_difference_g_s']/b['full_mass_flow_g_s']
            r['flow_comparison_pass']=r['flow_difference_g_s']>=0
        # A numeric comparison is not a convergence-qualified design decision.
        r['qualified_design_pass']=None
        r['qualification_note']='No Fluent rerun; baseline convergence must be PASS and source evidence reviewed before design qualification.'
    return records


def verify(output):
    dest=Path(output)
    cfg=read(ROOT/'t03_variables.json')
    with (ROOT/'reference_inputs/fluent_results.csv').open(encoding='utf-8-sig',newline='') as f:
        raw=calculate(cfg,list(csv.DictReader(f)))
    with (ROOT/'reference_inputs/reported_summary_user_provided.csv').open(encoding='utf-8',newline='') as f:
        records=assess(list(csv.DictReader(f)),raw)
    write(dest/'evidence_assessment.json',{'records':records,'note':'Report numbers were transcribed by user, not extracted from PDF. No CFD performed.'})
    # The existing DOE baseline is T03_dia_strong, not the team's CFD baseline.
    t03=doe(cfg,4,42)[0]['parameters']
    if t03 != read(ROOT/'reference_inputs/T03_dia_strong.json')['input_parameters']:
        raise ValueError('DOE baseline does not match supplied T03 metadata')
    parameters(cfg,t03)
    for r in records:
        if r['design_id']!='T03': continue
        case=dest/f"T03_{int(r['pressure_pa'])}Pa"
        write(case/'inputs.json',t03)
        write(case/'condition.json',{'pressure_pa':r['pressure_pa'],'design_id':'T03_dia_strong','role':'file_interface_replay_only'})
        numeric={'cv':r['cv_percent']/100,'cv_percent':r['cv_percent'],'full_mass_flow_g_s':r['full_mass_flow_g_s'],'pressure_pa':r['pressure_pa'],'reported_convergence_pass':int(r['convergence']=='PASS')}
        write(case/'responses.json',numeric)
        write(case/'provenance.json',r)
        # Read back both sides to exercise the file interface.
        parameters(cfg,read(case/'inputs.json'))
        if read(case/'responses.json')!=numeric: raise ValueError('Response round trip failed')
    return records

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('output')
    a=p.parse_args();verify(a.output)
    print('Verified CSV CV calculation and T03 DOE input/report-response file replay; no Fluent execution.')
