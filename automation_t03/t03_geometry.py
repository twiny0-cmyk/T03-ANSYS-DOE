"""Reconstructed geometry from supplied STEP/metadata; original generator unavailable."""
import cadquery as cq


def build_geometry(p):
    gaps = [p[f'g{i}'] for i in range(1,4)]
    g4 = 200 - sum(gaps)
    if g4 <= 0:
        raise ValueError('Nonpositive derived gap g4')
    xs = [100]
    for gap in gaps:
        xs.append(xs[-1] + gap)
    xs.append(300)
    for i in range(4):
        if xs[i+1]-xs[i] <= (p[f'D_b{i+1}']+p[f'D_b{i+2}'])/2:
            raise ValueError('Overlapping adjacent branches')
    header = cq.Solid.makeCylinder(4, 320, cq.Vector(0,0,0), cq.Vector(1,0,0))
    shape = header
    for i,x in enumerate(xs,1):
        branch = cq.Solid.makeCylinder(p[f'D_b{i}']/2, 4+p[f'L_b{i}'], cq.Vector(x,0,0), cq.Vector(0,-1,0))
        shape = shape.fuse(branch)
    clip = cq.Solid.makeBox(400,200,100,cq.Vector(-10,-100,0))
    return shape.intersect(clip).clean()
