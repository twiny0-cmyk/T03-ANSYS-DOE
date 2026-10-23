"""Windows-only Fluent 25.2 worker. Called by run_design.py, never by import."""
import argparse
import csv
import json
import math
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from pipeline import read, write, responses
from gates import parse_residual_xy, evaluate, OUTLETS


def scalar(result, name):
    # v252 surface-integral queries return a named map. Do not take an arbitrary
    # first/last number when a server API response differs from this contract.
    if not isinstance(result,dict) or name not in result:
        raise ValueError('Unexpected named surface query result: '+repr(result))
    value=result[name]
    if not isinstance(value,(int,float)) or not math.isfinite(value):
        raise ValueError('Expected finite scalar for '+name)
    return float(value)


def sample(s):
    return {n:scalar(s.results.report.surface_integrals.get_mass_flow_rate(surface_names=[n]),n) for n in ['inlet']+OUTLETS}


def run(job, pressure, template, processors):
    import ansys.fluent.core as pyfluent
    job=Path(job).resolve()
    path=job/(str(pressure)+'Pa')
    path.mkdir(exist_ok=False)
    cfg=read(Path(__file__).resolve().parents[1]/'t03_variables.json')
    s=None
    try:
        s=pyfluent.launch_fluent(product_version='25.2.0',dimension=3,precision='double',mode='solver',
                                processor_count=processors,ui_mode='no_gui',cwd=str(path),start_timeout=180,start_transcript=False)
        s.transcript.start(file_name=str(path/'solver.trn'),write_to_stdout=False)
        # Only read the supplied case, never its stale solution. Replace by the
        # newly generated mesh, then validate zones and initialize from scratch.
        s.settings.file.read_case(file_name=str(Path(template).resolve()))
        s.settings.file.replace_mesh(file_name=str(job/'mesh.msh'))
        if not str(s.get_fluent_version()).startswith('25.2'): raise ValueError('Fluent 2025 R2 required')
        st=s.settings
        bc=st.setup.boundary_conditions
        expected={'pressure_inlet':['inlet'],'pressure_outlet':OUTLETS,'symmetry':['symmetry'],'wall':['wall','wall_end']}
        # Gather all actual noninterior zone names. Refuse suffix normalization
        # or additional unidentified boundary zones.
        actual={}
        for kind in bc.child_names:
            group=getattr(bc,kind)
            if hasattr(group,'get_object_names'):
                names=group.get_object_names()
                if names and kind!='interior': actual[kind]=names
        initial_names=[n for names in actual.values() for n in names]
        expected_names=[n for names in expected.values() for n in names]
        if sorted(initial_names)!=sorted(expected_names):
            raise ValueError('Boundary names after replace_mesh differ: '+repr(actual))
        for kind,names in expected.items():
            bc.set_zone_type(zone_list=names,new_type=kind.replace('_','-'))
        for kind,names in expected.items():
            if sorted(getattr(bc,kind).get_object_names())!=sorted(names): raise ValueError('Boundary type mismatch')
        st.setup.general.solver.type='pressure-based'
        st.setup.general.solver.time='steady'
        st.setup.general.operating_conditions.operating_pressure=101325
        if st.setup.general.operating_conditions.operating_temperature.is_active():
            st.setup.general.operating_conditions.operating_temperature=293.15
        st.setup.general.operating_conditions.gravity.enable=False
        st.setup.models.energy.enabled=False
        st.setup.models.viscous.model='k-omega'
        st.setup.models.viscous.k_omega_model='sst'
        if 'nitrogen' not in st.setup.materials.fluid.get_object_names():
            st.setup.materials.database.copy_by_name(type='fluid',name='nitrogen')
        fluid=st.setup.materials.fluid['nitrogen']
        fluid.density={'option':'constant','value':1.165}
        fluid.viscosity={'option':'constant','value':1.76e-5}
        zones=st.setup.cell_zone_conditions.fluid.get_object_names()
        if len(zones)!=1 or st.setup.cell_zone_conditions.solid.get_object_names(): raise ValueError('Expected one fluid zone')
        st.setup.cell_zone_conditions.fluid[zones[0]].general.material='nitrogen'
        bc.pressure_inlet['inlet'].momentum.gauge_total_pressure.value=pressure
        for n in OUTLETS: bc.pressure_outlet[n].momentum.gauge_pressure.value=0
        st.solution.methods.p_v_coupling.flow_scheme='Coupled'
        st.solution.methods.pseudo_time_method.formulation.coupled_solver='global-time-step'
        # Turbulence inlet/backflow, wall and discretization details absent from
        # the PDF are retained from the team case and recorded in settings audit.
        residual=st.solution.monitor.residual
        for name in ['continuity','x-velocity','y-velocity','z-velocity','k','omega']:
            residual.equations[name].absolute_criteria=1e-5
            # Fixed 600+100 iterations are needed for the engineering gate.
            # Keep the strict target as recorded metadata; disable early stop.
            residual.equations[name].check_convergence=False
        residual.options.n_save=1000
        residual.options.residual_values.scale_residuals=True
        residual.options.normalize=True
        residual.reset()
        # Read back every explicit scalar critical to the intended physics.
        for obj,value in [(st.setup.general.solver.type,'pressure-based'),(st.setup.general.solver.time,'steady'),
                          (st.setup.models.energy.enabled,False),(st.setup.models.viscous.model,'k-omega'),
                          (st.setup.models.viscous.k_omega_model,'sst'),(fluid.density.value,1.165),
                          (fluid.viscosity.value,1.76e-5),(st.setup.general.operating_conditions.operating_pressure,101325),
                          (st.solution.methods.p_v_coupling.flow_scheme,'Coupled'),
                          (st.solution.methods.pseudo_time_method.formulation.coupled_solver,'global-time-step'),
                          (bc.pressure_inlet['inlet'].momentum.gauge_total_pressure.value,pressure)]:
            if obj.get_state()!=value: raise ValueError('Physics setting readback mismatch: '+repr(obj))
        for n in OUTLETS:
            if bc.pressure_outlet[n].momentum.gauge_pressure.value.get_state()!=0: raise ValueError('Outlet pressure mismatch')
        write(path/'settings_audit.json',dict(version=str(s.get_fluent_version()),boundary_names=actual,
              setup=st.setup.get_state(),methods=st.solution.methods.get_state(),residual=residual.get_state(),
              template_settings_inherited=['inlet and backflow turbulence','wall details','spatial discretization','pseudo-time controls']))
        # Detect a 1000x export scale error before any iterations (mesh is linear
        # and curved caps are polygonal, so use 5% area tolerance).
        for name,radius in [('inlet',0.004)]+[(n,read(job/'inputs.json')['D_b'+str(i)]/2000) for i,n in enumerate(OUTLETS,1)]:
            area=scalar(st.results.report.surface_integrals.get_area(surface_names=[name]),name)
            if not math.isclose(area,math.pi*radius*radius/2,rel_tol=0.05): raise ValueError('Export unit/cap area mismatch '+name)
        st.mesh.check()
        min_volume=scalar(st.results.report.volume_integrals.get_minimum(cell_zones=zones,cell_function='cell-volume'),zones[0])
        domain_volume=scalar(st.results.report.volume_integrals.get_volume(cell_zones=zones),zones[0])
        geometric_volume=read(job/'prepared.json')['geometry']['volume_model_units_cubed']*1e-9
        if min_volume<=0 or not math.isclose(domain_volume,geometric_volume,rel_tol=0.02):
            raise ValueError('Nonpositive cell or mesh/CAD volume-unit mismatch')
        write(path/'mesh_checks.json',dict(minimum_cell_volume_m3=min_volume,mesh_volume_m3=domain_volume,cad_volume_m3=geometric_volume,volume_relative_tolerance=0.02))
        st.solution.initialization.hybrid_initialize()
        st.solution.run_calculation.iterate(iter_count=600)
        at600=sample(st)
        write(path/'flux_600.json',at600)
        st.solution.run_calculation.iterate(iter_count=100)
        at700=sample(st)
        write(path/'flux_700.json',at700)
        residual.write(file_name=str(path/'residuals.xy'))
        history=parse_residual_xy((path/'residuals.xy').read_text(encoding='utf-8',errors='strict'))
        gate=evaluate(history,at600,at700)
        # Preserve both failed and passed solver states for diagnosis/restart.
        st.file.write_case_data(file_name=str(path/'solved.cas.h5'))
        if any(not (path/n).is_file() or (path/n).stat().st_size==0 for n in ['solved.cas.h5','solved.dat.h5']):
            raise ValueError('Case/data write incomplete')
        result=responses(cfg,[{'outlet':n,'mass_flow_kg_s':at700[n]} for n in OUTLETS])
        result['full_mass_flow_g_s']=2000*result.pop('total_mass_flow_kg_s')
        result['pressure_pa']=pressure
        result['mass_imbalance_percent']=gate['mass_imbalance_percent']
        result['flow_lower_bound_g_s']=2.992509 if pressure==2500 else 1.32315
        result['flow_margin_g_s']=result['full_mass_flow_g_s']-result['flow_lower_bound_g_s']
        result['flow_constraint_met']=int(result['flow_margin_g_s']>=0)
        with (path/'outlet_flows.csv').open('w',newline='',encoding='utf-8') as f:
            w=csv.writer(f);w.writerow(['outlet','mass_flow_kg_s'])
            for n in OUTLETS:w.writerow([n,at700[n]])
        write(path/'diagnostics.json',dict(convergence=gate,responses=result,fluent_executed=True,
              source='this local solver run',full_flow_bound_source='fixed 2500Pa requirement' if pressure==2500 else 'provisional baseline_fair600; convergence FAIL',
              final_design_acceptance='WITHHELD; mesh independence and fair baseline pending'))
        if not gate['pass_convergence']: raise ValueError('Convergence gate FAIL: no normal DOE response emitted')
        write(path/'responses.json',result)
    finally:
        if s is not None: s.exit()

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('job');p.add_argument('pressure',type=int,choices=[600,2500]);p.add_argument('template');p.add_argument('--processors',type=int,default=4)
    a=p.parse_args();run(a.job,a.pressure,a.template,a.processors)
