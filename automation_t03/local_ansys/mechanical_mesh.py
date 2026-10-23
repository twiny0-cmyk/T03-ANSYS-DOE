# Run INSIDE ANSYS Meshing 2025 R2 via the generated Workbench journal.
# T03_JOB and T03_CODE are supplied by the journal, not environment credentials.
import os
import sys
import json
sys.path.insert(0, T03_CODE)
from boundaries import classify

with open(os.path.join(T03_JOB, 'inputs.json'), 'r') as f:
    inputs = json.load(f)
model = ExtAPI.DataModel.Project.Model
mesh = model.Mesh
mesh.PhysicsPreference = MeshPhysicsPreferenceType.CFD
mesh.SolverPreference = MeshSolverPreferenceType.Fluent
mesh.ElementOrder = ElementOrder.Linear
mesh.ElementSize = Quantity('0.58 [mm]')
mesh.CaptureCurvature = True
mesh.CurvatureNormalAngle = Quantity('10 [deg]')
mesh.UseAutomaticInflation = 0
model_bodies = list(model.Geometry.GetChildren(DataModelObjectCategory.Body, True))
if len(model_bodies) != 1: raise RuntimeError('Expected one model body')
model_bodies[0].Name = 'fluid'
model_bodies[0].FluidSolidPhase = PhaseType.LiquidGas
if model_bodies[0].FluidSolidPhase != PhaseType.LiquidGas:
    raise RuntimeError('Fluid-domain phase not applied')

# Read back the supported public settings; errors abort the batch.
if mesh.PhysicsPreference != MeshPhysicsPreferenceType.CFD or mesh.SolverPreference != MeshSolverPreferenceType.Fluent:
    raise RuntimeError('CFD/Fluent preference not applied')
if not mesh.CaptureCurvature: raise RuntimeError('Curvature capture not enabled')
if mesh.ElementOrder != ElementOrder.Linear or mesh.UseAutomaticInflation != 0:
    raise RuntimeError('Linear/no-inflation setting not applied')
if abs(mesh.ElementSize.ConvertUnit('mm').Value-0.58) > 1e-9:
    raise RuntimeError('Element size mismatch')
if abs(mesh.CurvatureNormalAngle.ConvertUnit('deg').Value-10) > 1e-9:
    raise RuntimeError('Curvature angle mismatch')

bodies = [b for a in ExtAPI.DataModel.GeoData.Assemblies for p in a.Parts for b in p.Bodies]
if len(bodies) != 1: raise RuntimeError('Expected one fluid-domain body')
faces = []
for face in bodies[0].Faces:
    planar = 'plane' in str(face.SurfaceType).lower()
    faces.append(dict(id=int(face.Id), planar=planar, centroid=list(face.Centroid),
                      normal=list(face.NormalAtParam(0,0)) if planar else [0,0,0],
                      vertices=[[v.X,v.Y,v.Z] for v in face.Vertices], area=float(face.Area)))
selections = classify(faces, inputs)
# Fresh Workbench project for each design; never mutate user's open project.
for old in list(model.NamedSelections.Children): old.Delete()
for name, ids in selections.items():
    ns = model.AddNamedSelection()
    ns.Name = name
    info = ExtAPI.SelectionManager.CreateSelectionInfo(SelectionTypeEnum.GeometryEntities)
    info.Ids = ids
    ns.Location = info
    ns.SendToSolver = True
mesh.GenerateMesh()
md = ExtAPI.DataModel.MeshDataByName('Global')
if md.ElementCount < 1 or md.NodeCount < 1: raise RuntimeError('Empty mesh')
mesh.MeshMetric = MeshMetricType.OrthogonalQuality
minimum_oq = float(mesh.Minimum.Value)
mesh.MeshMetric = MeshMetricType.Skewness
maximum_skew = float(mesh.Maximum.Value)
if not (minimum_oq >= 0.1 and maximum_skew <= 0.95):
    raise RuntimeError('Mesh quality gate failed (OQ>=0.1, skew<=0.95)')
# Meshing's v252 exporter is internal: deliberately isolated here and not
# replaced with a different mesher on failure. Local API smoke test required.
mesh.InternalObject.WriteFluentInputFile(os.path.join(T03_JOB, 'mesh.msh'))
path = os.path.join(T03_JOB, 'mesh.msh')
if not os.path.isfile(path) or os.path.getsize(path) == 0: raise RuntimeError('Mesh export missing')
with open(os.path.join(T03_JOB, 'mesh_audit.json'), 'w') as f:
    json.dump(dict(status='MESH_EXPORTED',ansys_version='252',faces=faces,named_selections=selections,
                   face_count=len(faces),cells=md.ElementCount,nodes=md.NodeCount,minimum_orthogonal_quality=minimum_oq,maximum_skewness=maximum_skew,
                   settings=dict(size_mm=0.58,curvature_deg=10,physics='CFD',solver='Fluent',order='Linear',automatic_inflation=0,capture_curvature=True,minimum_size=str(mesh.MinimumSize),adaptive_sizing=bool(mesh.UseAdaptiveSizing)),
                   export_api='Mesh.InternalObject.WriteFluentInputFile; v252 local verification required'),f,indent=2)
