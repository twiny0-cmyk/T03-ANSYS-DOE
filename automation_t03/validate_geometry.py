"""Compare reconstructed CadQuery geometry with the supplied reference STEP."""
import argparse
import math
import cadquery as cq
from pipeline import cad, read, write
from t03_geometry import build_geometry


def validate(reference, metadata, config, output_dir):
    m=read(metadata); cfg=read(config)
    original=cq.importers.importStep(str(reference)).val()
    rebuilt=build_geometry(m['input_parameters'])
    if not original.isValid() or len(original.Solids()) != 1:
        raise ValueError('Reference STEP must contain one valid solid')
    if len(rebuilt.Solids()) != 1:
        raise ValueError('Reconstructed model must contain one solid')
    difference=original.cut(rebuilt).Volume()+rebuilt.cut(original).Volume()
    from pathlib import Path
    dest=Path(output_dir)
    report=cad(cfg,m['input_parameters'],Path(__file__).with_name('t03_geometry.py'),dest/'T03_regenerated.step')
    report.update(reference_volume_mm3=original.Volume(),metadata_volume_mm3=m['fluid_volume_half_mm3'],symmetric_difference_mm3=difference)
    b=original.BoundingBox()
    report['reference_bounds_mm']={'xmin':b.xmin,'xmax':b.xmax,'ymin':b.ymin,'ymax':b.ymax,'zmin':b.zmin,'zmax':b.zmax}
    if not math.isclose(original.Volume(),m['fluid_volume_half_mm3'],rel_tol=1e-6) or difference>1e-5*original.Volume():
        raise ValueError('Reconstruction differs from reference: '+str(report))
    write(dest/'geometry_validation.json',report)
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('reference');p.add_argument('metadata');p.add_argument('config');p.add_argument('output_dir')
    a=p.parse_args(); print(validate(a.reference,a.metadata,a.config,a.output_dir))
