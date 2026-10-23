GP-MF-010 - Morning CV Sprint (initial geometry candidates)

SAFE START: THESE ARE GEOMETRY SCREENING CANDIDATES, NOT FLUENT RESULTS.
No evidence yet that any has CV below baseline or meets the total flow constraint.

Measured 2500 Pa baseline (2026-10-21) in fluent_results.csv:
Population CV (ddof=0) = 19.63900694%; full-flow = 2.9925094 g/s
Reference fluid-domain half model, inlet mass flow 0.00149625470 kg/s.
Case L baseline from matching CFD must be added independently before assessing L.

14 pre-generated candidate STEP + JSON sets are in candidate_step/.
Start with T02_dia_balanced, T06_len_balanced, T07_len_open.
- T02 isolates a diameter effect. 2500 Pa first.
- T06 changes length + diameter jointly.
- T07 aims to preserve/improve total throughput. Not guaranteed.
Use comparable mesh settings and identical boundary conditions for baseline and tests.
Check geometric face Named Selections after every STEP import; DO NOT assume indices.

In existing VS Code project, if desired, copy fast_screening_designs.csv into:
C:\Users\155\Desktop\manifold_project\GP_MF010_CadQuery_13param\
Then in PowerShell (while cd to this folder):
  python gp_mf010_parametric.py --batch-csv fast_screening_designs.csv --outdir sprint_generated_step
Alternatively simply import the already-generated STEP candidates from candidate_step/.
No modifications to old baseline / A / B / C are necessary.

To compute CFD CV after entering measured outlet and inlet flows in fluent_results.csv:
  python check_fluent_results.py fluent_results.csv
You may enter signed negatives or absolute outlet flows; script uses magnitudes.
Strongly recommend: copy report output in a CSV row; run after Fluent convergence,
checking pressure condition and mass balance.

Design bounds from drawing: D_b1..5 4..6 mm; g1..g3 30..60 mm;
L_b1..5 40..80 mm; branch centers x1=100 mm and x5=300 mm;
derived g4=200-g1-g2-g3. g4 need not be in 30..60 (drawing example).
The official objective is uniformity + total flow no less than baseline
at EACH relevant pressure condition (600 and 2500 Pa separately).

Note: The Fluent solver and Workbench auto-mesh pipeline are NOT implemented
by the CadQuery generator. Mesh compatibility, boundary labels and volume
changes must be confirmed in ANSYS. The generated STEP files are not
compared against the team's A/B/C results.
