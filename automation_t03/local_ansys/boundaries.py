"""Geometry classifier shared with IronPython in Meshing; all lengths SI metres."""
import math


def expected(parameters):
    xs = [0.100]
    for i in range(1, 4):
        xs.append(xs[-1] + parameters['g' + str(i)] / 1000.0)
    xs.append(0.300)
    return [(xs[i], -(4.0 + parameters['L_b' + str(i+1)]) / 1000.0,
             parameters['D_b' + str(i+1)] / 2000.0) for i in range(5)]


def classify(faces, parameters, tolerance=2e-6):
    """faces: id, planar, centroid[m], normal, vertices[m], area[m2]."""
    result = dict((name, []) for name in ['inlet', 'wall_end', 'symmetry', 'wall'] + ['outlet_' + str(i) for i in range(1,6)])
    ids = [f['id'] for f in faces]
    if not ids or len(set(ids)) != len(ids):
        raise ValueError('Empty geometry or duplicate face identifiers')
    all_vertices = [v for f in faces for v in f['vertices']]
    if not all_vertices or abs(max(v[0] for v in all_vertices) - 0.320) > tolerance:
        raise ValueError('Geometry extent/unit mismatch: expected 0.320 m header')
    for f in faces:
        if (math.isnan(f['area']) or math.isinf(f['area'])) or f['area'] <= 0:
            raise ValueError('Invalid face area')
        matches = []
        if f['planar']:
            n = f['normal']
            vertices = f['vertices']
            if not vertices: raise ValueError('Planar face without vertices')
            def plane(axis, value):
                return abs(abs(n[axis])-1) < 1e-5 and all(abs(v[axis]-value) <= tolerance for v in vertices)
            if plane(0, 0): matches.append(('inlet', 0.004))
            if plane(0, 0.320): matches.append(('wall_end', 0.004))
            if plane(2, 0): matches.append(('symmetry', None))
            for i, (x,y,r) in enumerate(expected(parameters), 1):
                if plane(1,y) and abs(f['centroid'][0]-x) <= tolerance:
                    matches.append(('outlet_'+str(i),r))
            if len(matches) != 1:
                raise ValueError('Unclassified/ambiguous planar face: ' + str(f['id']))
            name, radius = matches[0]
            if radius is not None:
                if abs(f['area'] - math.pi*radius*radius/2) > 0.002 * math.pi*radius*radius/2:
                    raise ValueError('Cap area mismatch: ' + name)
                if abs(f['centroid'][2] - 4*radius/(3*math.pi)) > tolerance:
                    raise ValueError('Half cap centroid mismatch: ' + name)
        else:
            name = 'wall'
        result[name].append(f['id'])
    for name in ['inlet','wall_end'] + ['outlet_'+str(i) for i in range(1,6)]:
        if len(result[name]) != 1: raise ValueError('Require one cap for ' + name)
    if not result['symmetry'] or not result['wall']: raise ValueError('Missing symmetry/wall')
    assigned = [i for group in result.values() for i in group]
    if sorted(assigned) != sorted(ids): raise ValueError('Face coverage is not exactly once')
    return result
