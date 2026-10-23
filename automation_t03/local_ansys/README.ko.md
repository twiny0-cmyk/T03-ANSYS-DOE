# Windows ANSYS 2025 R2: T03 2500 Pa부터 실행

**실행 상태: 이 코드로 실제 ANSYS Meshing 또는 Fluent 계산을 아직 수행하지 않았습니다.** 클라우드에서 검증한 범위는 CAD, 오프라인 로직, 파일 인터페이스와 배치 파일 생성입니다. 아래 보고서 비교값은 기존 팀 결과이며 새 solver 실행 결과가 아닙니다.

## 현재 상태

| 기능 | 구현 및 검증 상태 |
|---|---|
| 13변수 검증·LHS DOE·CadQuery STEP | 구현, 클라우드에서 기준 STEP 대조 및 재수입 검증 |
| PDF/CSV/JSON 출구 유량 → CV·전체 유량 | 구현, 기존 결과 산술 재계산 검증 |
| 파일 기반 DOE/optiSLang 응답 | 구현, 파일 생성·재수입 검증; optiSLang 제품 실행 미검증 |
| Workbench → Meshing → mesh export | 이번에 스크립트 추가; Windows ANSYS 실행 미검증 |
| 기하 기반 Named Selection 재생성 | 구현, 실제 CadQuery T03/변경 형상으로 14개 face 전부 분류 검증; Mechanical API 연결은 로컬 확인 필요 |
| PyFluent mesh 교체·설정·700회 계산·유량 추출 | 이번에 구현; Fluent 서버 실행 미검증 |
| 수렴/실패 처리·단계 제한·응답 반환 | 구현, 실패 시 응답 미승격 등 로직 테스트; 실제 solver 실패/timeout 동작은 로컬 검증 필요 |

기존 파일은 수정하지 않았습니다. 이 폴더와 새 테스트가 추가되었습니다. 새 Python 파일은 CPython 문법 검사와 오프라인 테스트를 수행했습니다. `mechanical_mesh.py`와 생성되는 `mesh.wbjn`은 ANSYS 내장 IronPython에서 실행하는 코드이며 클라우드에서 ANSYS API를 실행하지 않았습니다.

공식 배포 PyFluent 0.35.0의 `generated/solver/settings_252.py`와 Mechanical stubs 0.1.15의 v252 API 정의를 참고했습니다. Fluent query 반환 형식/허용 문자열, Workbench template/컨테이너, GeoData 좌표·곡면 API는 실제 설치에서 smoke test가 필요합니다. 특히 `Mesh.InternalObject.WriteFluentInputFile`은 공개 API가 아닌 버전 의존 exporter로 이 파일에만 격리했습니다. 호출이 실패하면 중단하며 다른 메셔로 자동 대체하지 않습니다.

## 구성

- `T03_inputs.json`: 실제 기준 13변수, mm. 원본 CadQuery 생성 코드는 미확보이며 STEP 대조를 통과한 재구성 생성기를 호출합니다.
- `run_design.py`: prepare / mesh / solve / validate-pilot 단계 CLI.
- `mechanical_mesh.py`: Meshing 내부 설정, 경계 분류, 메쉬 생성과 내보내기.
- `boundaries.py`: 순서/Face ID에 독립적인 기하 분류 함수.
- `fluent_worker.py`: 팀 case 설정을 읽고 새 mesh로 교체, 경계·물성 검증, 계산과 보고서 추출.
- `gates.py`: residual XY 읽기 및 공학적 수렴 판정.
- `evaluate_design.py`: optiSLang 외부 프로세스용 순차 실행 wrapper.
- `Run-T03Pilot.ps1`: T03 2500 Pa pilot용 PowerShell 진입점. 기본은 준비만, `-Execute`일 때만 ANSYS 실행.

## Meshing 설정 및 경계

새 Workbench Fluid Flow/Fluent 시스템에 해당 설계 STEP을 연결하고 유일한 body를 fluid/LiquidGas로 지정합니다. 기존 사용자 Workbench 프로젝트를 열어 수정하지 않습니다. 설정은 Physics CFD, Solver Fluent, Linear, Global Element Size 0.58 mm, Capture Curvature true, Curvature Normal Angle 10°, UseAutomaticInflation=0입니다. Local Sizing/명시적 Method는 추가하지 않으며 Minimum Size와 Adaptive Sizing은 새 시스템 기본값을 사용하고 audit에 기록합니다. 보고서의 Minimum Size 0 mm는 자동 기본값 기록이므로 임의의 물리적 최소 크기 0으로 강제하지 않습니다. 세부 기본값이 팀 환경과 다르면 재현 검사에서 확인하고 조정해야 합니다.

GeoData 좌표는 SI(m)로 기대하며 header 끝 x=0.320 m 검사로 단위 혼동을 거절합니다. 매 실행마다 다음 기준으로 Named Selection을 다시 만듭니다.

- inlet: x=0의 평면, wall_end: x=0.320 m의 평면.
- outlet_i: 입력으로 계산한 x_i, y=-(4+L_bi) mm의 y 법선 평면. x1=100, x5=300 mm이며 g4는 종속변수입니다.
- cap의 면적 πr²/2와 z centroid=4r/(3π)를 별도 검사합니다.
- symmetry: z=0의 평면 전체.
- wall: 나머지 곡면. 분류되지 않은 평면은 wall로 숨기지 않고 실패합니다.

9개 경계(inlet 1, outlet 5, symmetry 1, wall_end 1, wall 1)를 만들며 모든 face가 정확히 한 그룹에 속해야 합니다. 캡 누락·중복·잘못된 면적·단위는 즉시 실패합니다. 새 설계마다 새 STEP/프로젝트에서 다시 수행하므로 이전 Face ID를 재사용하지 않습니다. Local mesh quality filter는 최소 OQ≥0.1, 최대 skew≤0.95로 두었습니다. 이는 본 구현의 초기 필터이며 보고서가 확정한 mesh independence 기준이 아닙니다. 실제 OQ/skew 및 셀 수는 audit에 저장합니다.

## Fluent 설정과 팀 case의 역할

첨부된 `baseline_fair_600Pa_result.cas.h5`를 **설정 템플릿**으로 읽고 새 mesh로 교체합니다. 과거 `.dat.h5`나 해를 로드하지 않고 Hybrid Initialization으로 처음부터 계산합니다. 템플릿은 job 폴더에 복사해 읽으므로 원본을 저장/수정하지 않습니다. 과거 Baseline의 수렴 FAIL을 T03의 수렴 판정으로 상속하지 않습니다.

명시적으로 설정/재확인하는 조건은 Fluent 25.2, 3D double, steady pressure-based, SST k-omega, Coupled + global-time-step pseudo-time, Energy off, 질소 ρ=1.165 kg/m³, μ=1.76e-5 Pa·s, operating pressure 101325 Pa, inlet gauge total pressure 2500 또는 600 Pa, 모든 outlet gauge pressure 0 Pa입니다. Reference temperature는 293.15 K이며 operating temperature 항목이 활성 상태일 때 설정합니다. Energy off·상수 물성이므로 온도가 유동 물성에 연동되지는 않습니다.

보고서에 없는 inlet/backflow turbulence, wall 세부 설정, spatial discretization 및 pseudo-time controls는 팀 case에서 상속합니다. 따라서 보고서만으로 원래 solver 설정을 완전히 복원했다고 주장하지 않습니다. `settings_audit.json`에서 팀 기준과 직접 비교하세요. global-time-step 설정이 기존 case의 실제 pseudo-time 방식과 다르면 로컬 검토 후 양쪽 설계에 동일하게 적용해야 합니다.

Fluent로 mesh 교체 후 정확한 경계 이름/타입과 단일 fluid zone을 재검증합니다. 자동 suffix 정리나 이름 추측은 하지 않습니다. GeoData→Fluent export 단위도 cap 면적(5% 허용)과 CAD/mesh 체적(2% 허용), 양의 최소 cell volume으로 검사합니다. 미지의 서버 응답이나 설정 오류는 통과시키지 않습니다.

## Windows 준비

로컬 ANSYS Workbench/Meshing/Fluent 2025 R2, 사용 가능한 라이선스, CPython 3.11 또는 3.12가 필요합니다. 최초에는 CPU 4개를 권장하며 실제 메모리·라이선스 수에 맞춰 조정하세요. 클라우드의 Linux 가상환경을 Windows로 복사하지 않습니다.

PowerShell에서 저장소 루트로 이동한 뒤:

```powershell
py -3.12 -m venv C:\t03-env
C:\t03-env\Scripts\python.exe -m pip install -r .\automation_t03\local_ansys\requirements-local.txt
C:\t03-env\Scripts\python.exe -m pip check
$env:AWP_ROOT252 = 'C:\Program Files\ANSYS Inc\v252'
```

Windows 의존성 설치와 ANSYS API 호환성은 로컬 검증 대상입니다. `requirements-local.txt`는 핵심 라이브러리 버전 고정이며 전이 의존성 전체 lock은 아닙니다. 로컬 검증 성공 후 `pip freeze` 결과를 job 근거와 함께 별도 보존하세요.

## 첫 실행: T03 2500 Pa

**1. CAD/배치 준비만 확인** (ANSYS를 실행하지 않음):

```powershell
.\automation_t03\local_ansys\Run-T03Pilot.ps1 -Python C:\t03-env\Scripts\python.exe -Job C:\t03-runs\T03_prepare_001
```

`T03.step`, `inputs.json`, `mesh.wbjn`, 템플릿 복사본, 준비 hash와 `PREPARED_NO_ANSYS_EXECUTED` 상태를 확인합니다.

**2. 새 디렉터리에서 실제 pilot 실행:**

```powershell
.\automation_t03\local_ansys\Run-T03Pilot.ps1 -Python C:\t03-env\Scripts\python.exe -Job C:\t03-runs\T03_2500_001 -Processors 4 -Execute
```

실패 시 PowerShell과 Python은 비정상 종료합니다. 기존 job을 덮어쓰지 않습니다. 단계별로 디버그하려면 다음과 같이 실행할 수 있습니다. `$Job`은 새 경로여야 합니다.

```powershell
$Python = 'C:\t03-env\Scripts\python.exe'
$Runner = '.\automation_t03\local_ansys\run_design.py'
$Job = 'C:\t03-runs\T03_2500_debug001'
& $Python $Runner prepare --inputs .\automation_t03\local_ansys\T03_inputs.json --job $Job --template .\automation_t03\reference_inputs\team_additions\baseline_fair_600Pa_result.cas.h5
# 앞 명령의 $LASTEXITCODE=0을 확인한 후 다음 단계 실행
& $Python $Runner mesh --job $Job
# mesh 성공과 audit를 확인한 후
& $Python $Runner solve --job $Job --pressures 2500 --processors 4
# 수렴/유량/mesh 및 보고서 근사 재현 확인
& $Python $Runner validate-pilot --job $Job
```

각 단계의 성공을 확인하지 않고 다음 명령으로 넘어가지 마세요. Workbench 경로가 다르면 `mesh --workbench <RunWB2.exe 경로>` 또는 PowerShell의 `-Workbench`로 지정합니다. `.wbpj`를 열어 경계와 단위, 0.58 mm/Linear/곡률/Inflation 설정, tetra 메쉬를 시각 확인하세요. 보고서 기준 T03 cells=474676, nodes=101832, OQ≈0.201468, skew≈0.798532이며 동일 설정이어도 mesher 결과가 완전히 같지 않을 수 있습니다.

## 수렴/응답 처리

Hybrid Initialization → 600회 → inlet/5 outlets snapshot → 추가 100회 → 최종 snapshot을 수행합니다. solver의 1e-5 strict target은 기록하되 600+100회 관측을 확보하기 위해 개별 residual early-stop을 비활성화합니다. 실제 residual이 저장되지 않았거나 681..700회 20개가 없으면 실패합니다.

공학적 PASS는 최근 20회 residual 최대가 continuity/k/omega≤1e-4 및 각 velocity≤1e-5, 질량 불균형<0.1%, 600→700회 출구 변화<0.1%를 모두 만족하는 경우입니다. strict target과 공학적 gate는 별도 기록합니다. 출구 변화 분모는 최종 700회 절댓값 유량으로 명시합니다. 최종 값 하나만 보고 수렴을 통과시키지 않습니다.

2500 Pa 유량 하한은 **2.992509 g/s**입니다. 재격자 Baseline 2500 Pa 유량 **2.93047268 g/s**로 대체하지 않습니다. 600 Pa 비교 하한 **1.32315 g/s**는 수렴 실패 Baseline에 근거한 잠정값이며 1e9 placeholder는 사용하지 않습니다.

출구 signed flux는 유출 음수, 입구 양수로 기대합니다. 모든 outlet 크기로 모집단 CV를 계산하며 full flow=2×반모델 출구 합입니다. 혼합 부호·역류·NaN·빈 응답은 실패합니다.

- CFD/API/mesh/수렴 실패: 비정상 프로세스 종료, job 루트 `responses.json` 미생성, `FAILED_DO_NOT_TRAIN`; 진단 숫자를 정상 DOE 응답으로 읽지 마세요.
- 수렴했지만 유량 제약 미달: 숫자 응답과 `feasible=0`, `CONVERGED_INFEASIBLE`; 정상 최적 설계로 채택하지 않습니다. optiSLang에서 constraint로 연결합니다.
- 수렴 및 유량 통과: `feasible=1`. Mesh independence·Baseline 공정 비교 미완료이므로 최종 설계 인증은 여전히 WITHHELD입니다.

## pilot 검증 후 600 Pa / DOE 확장

`validate-pilot`은 T03 기준 입력, 로컬 수렴·유량 통과, 14개 face, 보고서 대비 셀/노드 수 ±5%, CV 상대 ±2%, 총유량 상대 ±1%와 파일 존재를 검사해 `pilot_validation.json`을 만듭니다. 이 허용오차는 최초 재현 비교를 위한 구현 기준이며 공식 설계 승인 기준은 아닙니다. 실패하면 tolerance를 임의로 늘리지 말고 mesh/settings/residual을 조사하세요. API는 실행 성공했어도 mesh 독립성이나 contour 검증을 대신하지 않습니다.

600 Pa나 다른 DOE 설계를 실행하려면 이 영수증을 제공해야 합니다. 코드/입력/설정/기준 산출물이 달라지면 기존 영수증을 거절합니다. 새 설계마다 fresh job이며, 두 압력은 같은 메쉬에서 **각각 새 Fluent 세션과 초기화**로 계산합니다.

```powershell
# 새 job을 prepare하고 mesh한 다음
& $Python $Runner solve --job C:\t03-runs\T03_both_001 --pressures 600 2500 --pilot-validation C:\t03-runs\T03_2500_001\pilot_validation.json
```

후속 코드 변경 후에는 pilot을 다시 수행하세요. 상세 지표와 contour는 사용자가 Fluent에서 확인해야 하며 이 스크립트는 contour 이미지를 생성하지 않습니다.

## optiSLang 인터페이스

각 평가마다 독립 작업 폴더와 13변수 `inputs.json`을 사용합니다. 원래 JSON과 동일한 이름(D_b1..5, g1..3, L_b1..5), mm 단위이며 압력은 별도 실행 조건입니다. T03 기준 입력 파일의 숫자를 optiSLang 입력 매개변수로 등록하고 `t03_variables.json`의 범위를 연결하세요.

외부 프로세스 명령 예시(실행 디렉터리=해당 평가 폴더):

```powershell
C:\t03-env\Scripts\python.exe C:\repo\T03-ANSYS-DOE\automation_t03\local_ansys\evaluate_design.py --inputs inputs.json --job ansys_run --output responses.json --template C:\repo\T03-ANSYS-DOE\automation_t03\reference_inputs\team_additions\baseline_fair_600Pa_result.cas.h5 --pressures 600 2500 --processors 4 --pilot-validation C:\t03-runs\T03_2500_001\pilot_validation.json
```

`C:\repo\...`는 실제 저장소 경로로 바꾸세요. 스크립트는 실패 시 출력 파일을 만들지 않습니다. optiSLang Process 노드에서 **exit code 0과 신규 responses.json**을 모두 성공 조건으로 설정하고, nonzero/missing JSON은 failed design으로 처리하세요. 누락 값에 0을 대입하거나 이전 응답을 재사용하면 안 됩니다.

응답 JSON은 pressure suffix를 가진 평면 숫자 객체입니다.

| Key 예시 | 의미 / 연결 |
|---|---|
| `cv_percent_2500Pa`, `cv_percent_600Pa` | 최소화 목적; 필요 시 가중합 또는 worst case는 optiSLang에서 정의 |
| `cv_2500Pa` | 무차원 CV |
| `full_mass_flow_g_s_2500Pa` | 전체 유량, 하한 2.992509 g/s |
| `flow_margin_g_s_2500Pa` | full flow - 2.992509; ≥0 제약 |
| `flow_margin_g_s_600Pa` | full flow - 1.32315; 잠정 제약 |
| `mdot_outlet_1_kg_s_2500Pa` ~ `mdot_outlet_5_kg_s_2500Pa` | 반모델 출구 절댓값 kg/s |
| `mass_imbalance_percent_2500Pa` | 수렴 품질 지표 |
| `feasible` | 모든 요청 압력의 유량 제약 충족=1; ≥1 제약 |

한 압력만 실행하면 그 압력 응답만 출력합니다. 600/2500 통합 평가 중 한 압력이 실패하면 통합 응답은 반환하지 않습니다. CFD 예산은 설계당 최대 2회×700회이며 solver/HPC 라이선스와 메모리에 맞춰 병렬 평가 수를 제한하세요.

## 남은 로컬 검증 및 오류 조사

1. Workbench.log에서 template/geometry import/SendCommand 정상 여부와 Meshing 라이선스 확인.
2. GeoData SurfaceType/NormalAtParam 및 단위 검증 실패 시 mesh_audit 이전 로그 조사; 자동 ID 기반 우회 금지.
3. 내부 Fluent export API 실패 시 해당 v252 로컬 API만 확인·수정 후 fresh job. 공개 API 목록만으로 내보내기 성공을 확언하지 않음.
4. PyFluent allowed-values, named query map, residual XY 형식이 다르면 worker가 중단함. worker.log와 solver.trn의 실제 응답으로 해당 어댑터만 수정하고 pilot 재검증.
5. 실제 template가 가진 난류/벽면/이산화와 보고서 팀 설정 비교. Baseline/T03 mesh·solver 조건이 공정한지 확인.
6. 셀 양의 체적·mesh quality·전체 체적·convergence gate·유량 제약 검토 후 contour 및 y+ 확인. 최종 채택 전 mesh independence는 별도 수행.

이 문서와 코드의 클라우드 검증은 로직·CAD·준비 단계까지입니다. 실제 Windows Meshing, Fluent 계산, journal API 연결, optiSLang 제품 실행 검증은 아직 수행하지 않았습니다.

## Run-T03Pilot.ps1 실행 전 설치·경로 체크리스트

1. 저장소 전체를 Windows PC에 clone/pull하세요. `local_ansys/`만 복사하면 상위 `pipeline.py`, `t03_geometry.py`, `t03_variables.json`, 팀 case가 없어 실행할 수 없습니다.
2. 64-bit CPython 3.11/3.12 및 새 가상환경을 준비하고 `requirements-local.txt` 설치 후 `pip check`를 실행하세요. Python 실행 경로는 `-Python`으로 지정합니다.
3. ANSYS 2025 R2의 **Workbench + Meshing + Fluent**와 필요한 CAD import 기능·라이선스가 설치되어 있어야 합니다. Python 패키지는 ANSYS 제품이나 라이선스를 설치하지 않습니다.
4. `RunWB2.exe` 기본 경로는 `C:\Program Files\ANSYS Inc\v252\Framework\bin\Win64\RunWB2.exe`입니다. 실제 경로가 다르면 `-Workbench`로 지정하세요.
5. `$env:AWP_ROOT252`를 실제 `v252` 디렉터리로 설정하세요. PyFluent는 이를 통해 Fluent를 찾습니다. 제품이 다른 드라이브에 있으면 해당 경로를 사용하세요.
6. 라이선스 서버/인증은 기존 로컬 ANSYS 설정을 사용하세요. 라이선스 값이나 비밀값을 Git에 기록하지 마세요.
7. `reference_inputs/team_additions/baseline_fair_600Pa_result.cas.h5`가 clone에 포함돼 있는지 확인하세요. 이 파일은 템플릿이며 새로운 T03 해는 Hybrid Initialization으로 계산하므로 `.dat.h5`가 필수는 아닙니다. 기존 해석 유동장을 복원하려면 대응 `.dat.h5`가 별도로 필요합니다.
8. `-Job`은 쓰기 가능한 **새 디렉터리**로 지정하세요. 준비만 수행한 디렉터리를 `-Execute` 실행용으로 재사용하지 마세요. CPU 수는 `-Processors`로 지정하고 라이선스·메모리에 맞추세요.
9. PowerShell이 다운로드한 스크립트 실행을 차단하면 조직의 실행 정책에 따라 신뢰한 파일을 허용하세요. 스크립트는 시스템 실행 정책을 자동 변경하지 않습니다.
10. 먼저 `-Execute` 없이 CAD/배치 생성을 검사하고, 새 Job에서 `-Execute`로 pilot을 수행하세요. 실제 결과는 로컬 로그·audit·수렴 gate 및 pilot 비교 검사를 통과한 뒤에만 사용합니다.
