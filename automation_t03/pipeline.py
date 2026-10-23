"""File-based T03 DOE interface. Uses Python standard library; CAD needs CadQuery."""
import argparse
import csv
import importlib.util
import json
import math
import random
import statistics
import subprocess
from pathlib import Path


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def variables(config):
    vs = config['variables']
    if len(vs) != 13 or len({v['name'] for v in vs}) != 13:
        raise ValueError('Exactly 13 uniquely named variables required')
    for v in vs:
        lo, base, hi = (v[k] for k in ('lower', 'baseline', 'upper'))
        if not all(isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) for x in (lo, base, hi)):
            raise ValueError('Bounds and baseline must be finite numbers')
        if not lo < hi or not lo <= base <= hi:
            raise ValueError('Require lower < upper and baseline inside bounds')
    return vs


def parameters(config, values):
    vs = variables(config)
    if set(values) != {v['name'] for v in vs}:
        raise ValueError('Input names must exactly match configuration')
    for v in vs:
        value = values[v['name']]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not v['lower'] <= value <= v['upper']:
            raise ValueError('Invalid or out-of-range input: ' + v['name'])
    return values


def doe(config, count, seed):
    vs = variables(config)
    if count < 1:
        raise ValueError('samples must be positive')
    rng = random.Random(seed)
    columns = []
    for v in vs:
        col = [v['lower'] + (i + rng.random()) / count * (v['upper'] - v['lower']) for i in range(count)]
        rng.shuffle(col)
        columns.append(col)
    return [{'case_id': 'baseline', 'parameters': {v['name']: v['baseline'] for v in vs}}] + [
        {'case_id': f'lhs_{i+1:05d}', 'parameters': {v['name']: columns[j][i] for j, v in enumerate(vs)}} for i in range(count)]


def responses(config, rows):
    names = config['outlets']
    if len(names) != 5 or len(set(names)) != 5:
        raise ValueError('Exactly five unique outlet names required')
    if len(rows) != 5 or {r['outlet'] for r in rows} != set(names):
        raise ValueError('Require exactly one row for each configured outlet')
    sign = config['outward_sign']
    if sign not in (-1, 1):
        raise ValueError('outward_sign must be +1 or -1')
    flows = {r['outlet']: sign * float(r['mass_flow_kg_s']) for r in rows}
    if any(not math.isfinite(v) or v < 0 for v in flows.values()):
        raise ValueError('Nonfinite or reverse flow: verify sign and Fluent convergence')
    mean = statistics.mean(flows.values())
    if mean <= 0:
        raise ValueError('CV undefined for zero total flow')
    result = {f'mdot_outlet_{i+1}_kg_s': flows[n] for i, n in enumerate(names)}
    result.update(total_mass_flow_kg_s=sum(flows.values()), cv=statistics.pstdev(flows.values()) / mean)
    result['cv_percent'] = 100 * result['cv']
    return result


def cad(config, values, builder, output):
    parameters(config, values)
    import cadquery as cq
    builder = Path(builder).resolve()
    spec = importlib.util.spec_from_file_location('t03_user_builder', builder)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    shape = module.build_geometry(values)
    value = shape.val() if isinstance(shape, cq.Workplane) else shape
    if not value.isValid() or len(value.Solids()) < 1 or value.Volume() <= 0:
        raise ValueError('Invalid or empty CAD solid')
    output = Path(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    cq.exporters.export(shape, str(output), exportType='STEP')
    restored = cq.importers.importStep(str(output)).val()
    if not restored.isValid() or restored.Volume() <= 0 or not math.isclose(restored.Volume(), value.Volume(), rel_tol=1e-5):
        raise ValueError('STEP round-trip geometry validation failed')
    return {'step': str(output), 'volume_model_units_cubed': value.Volume(), 'solid_count': len(value.Solids())}


def run_local(manifest, execute=False):
    root = Path(manifest).resolve().parent
    cfg = read(manifest)
    # Commands are argument arrays. No shell interpolation is performed.
    for stage in cfg['stages']:
        command = stage['command']
        if not isinstance(command, list) or not command or not all(isinstance(x, str) for x in command):
            raise ValueError('command must be a nonempty string array')
        cwd = (root / stage.get('cwd', '.')).resolve()
        expected = [(cwd / name).resolve() for name in stage['outputs']]
        if not expected:
            raise ValueError('Each stage requires output artifacts')
        print(json.dumps({'stage': stage['name'], 'cwd': str(cwd), 'command': command, 'execute': execute}))
        if execute:
            cwd.mkdir(parents=True, exist_ok=True)
            if any(p.exists() for p in expected):
                raise ValueError('Use a fresh case directory; existing output could mask failure')
            with (cwd / (stage['name'] + '.log')).open('w', encoding='utf-8') as log:
                subprocess.run(command, cwd=cwd, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=stage.get('timeout_seconds', 7200))
            if any(not p.is_file() or p.stat().st_size == 0 for p in expected):
                raise ValueError('Stage did not produce required nonempty outputs')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='action', required=True)
    d = sub.add_parser('doe'); d.add_argument('config'); d.add_argument('output'); d.add_argument('--samples', type=int, default=100); d.add_argument('--seed', type=int, default=42)
    r = sub.add_parser('responses'); r.add_argument('config'); r.add_argument('flows'); r.add_argument('output')
    c = sub.add_parser('cad'); c.add_argument('config'); c.add_argument('inputs'); c.add_argument('builder'); c.add_argument('output')
    l = sub.add_parser('local'); l.add_argument('manifest'); l.add_argument('--execute', action='store_true')
    a = p.parse_args()
    if a.action == 'doe':
        cfg = read(a.config); cases = doe(cfg, a.samples, a.seed)
        dest = Path(a.output); dest.mkdir(parents=True, exist_ok=True)
        with (dest / 'designs.csv').open('w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=['case_id'] + [v['name'] for v in cfg['variables']]); w.writeheader()
            for case in cases:
                w.writerow({'case_id': case['case_id'], **case['parameters']})
                write(dest / case['case_id'] / 'inputs.json', case['parameters'])
        write(dest / 'doe_metadata.json', {'method': 'Latin hypercube; independent uniform marginals', 'seed': a.seed, 'lhs_samples': a.samples, 'baseline_included': True, 'config': cfg})
    elif a.action == 'responses':
        with open(a.flows, newline='', encoding='utf-8-sig') as f:
            result = responses(read(a.config), list(csv.DictReader(f)))
        write(a.output, result)
    elif a.action == 'cad':
        print(json.dumps(cad(read(a.config), read(a.inputs), a.builder, a.output)))
    else:
        run_local(a.manifest, a.execute)

if __name__ == '__main__':
    main()
