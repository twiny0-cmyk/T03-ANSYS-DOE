# T03 CFD/DOE 자동화

## 조사 결과와 적용 범위

기존 저장소는 `README.md` 하나였습니다. 업로드된 STEP, JSON, 후처리 코드, 안내문과 CSV는 `reference_inputs/`에 원문 그대로 복사했으며 기존 파일은 변경하지 않았습니다. 원본 CadQuery 생성 코드와 중간보고서는 아직 제공되지 않았습니다.

첨부 JSON/STEP의 원통 매니폴드와 반모델 조건을 바탕으로 `t03_geometry.py`를 새로 작성했습니다. CadQuery 2.6.1에서 기준 STEP과 새 형상의 대칭 차집합 체적 0 mm³, 단일 유효 솔리드, 체적 11134.14091053 mm³ 및 STEP 재수입을 확인했습니다. 원본 생성 코드 실행을 검증한 것은 아닙니다. 이 검증은 메싱 적합성이나 CFD 정확도를 보장하지 않습니다.

`T03_dia_strong` 기준값과 실제 범위는 `t03_variables.json`에 연결했습니다. D_b1..5 = 4~6 mm, g1..g3 = 30~60 mm, L_b1..5 = 40~80 mm이며 g4 = 200-g1-g2-g3는 종속변수입니다. x1=100, x5=300 mm, 헤더 직경 8 mm, 끝면 x=320 mm, 출구 y=-(4+L_bi), Z>=0 반모델입니다. named selection은 face ID 대신 기하 위치로 매번 확인해야 합니다.

클라우드에서 ANSYS 계산은 실행하지 않았습니다. 로컬 journal은 팀의 경계조건, 모델, 메쉬 및 수렴 요구를 적용해 기록·검증해야 합니다. 일반 예제 설정은 형식 설명용이며 실제 작업은 `t03_variables.json`을 사용하세요.

## 실제 T03 실행과 검증

저장소 루트에서 실행합니다. 가상환경은 체크아웃 밖에 만들며, Linux 클라우드에서 설치·검증한 전체 버전을 `requirements-cad.lock`에 저장했습니다. Windows에서 잠금 파일의 휠 호환성은 별도 확인이 필요합니다.

```sh
python -m venv /workspace/t03-cad-venv
/workspace/t03-cad-venv/bin/python -m pip install -r automation_t03/requirements-cad.lock
/workspace/t03-cad-venv/bin/python automation_t03/validate_geometry.py automation_t03/reference_inputs/T03_dia_strong.step automation_t03/reference_inputs/T03_dia_strong.json automation_t03/t03_variables.json /workspace/t03-validation
python automation_t03/pipeline.py doe automation_t03/t03_variables.json /workspace/t03-validation/doe --samples 100 --seed 42
/workspace/t03-cad-venv/bin/python automation_t03/pipeline.py cad automation_t03/t03_variables.json /workspace/t03-validation/doe/baseline/inputs.json automation_t03/t03_geometry.py /workspace/t03-validation/baseline.step
python automation_t03/measured_responses.py automation_t03/t03_variables.json automation_t03/reference_inputs/fluent_results.csv /workspace/t03-validation/responses.json --design baseline --pressure 2500
```

Windows에서는 `/workspace/...`를 로컬 경로로, Python 경로를 가상환경의 `Scripts/python.exe`로 바꾸세요. 각 DOE 설계는 600, 2500 Pa를 별도 평가하고, 같은 압력의 기준 결과와 비교해야 합니다. DOE의 `baseline` 폴더는 T03 기준 형상입니다. CSV의 `baseline`은 팀의 기존 CFD 기준 설계이므로 두 이름을 물리적으로 동일한 설계로 취급하면 안 됩니다.

제공된 CSV는 baseline/2500 Pa 한 행입니다. 팀의 원본 checker와 새 adapter 모두 CV=19.6390069416%, full-flow=2.99250874 g/s를 계산합니다. 안내문의 2.9925094 g/s는 입구 유량을 2배 환산한 값이며 여기서는 출구 합을 사용합니다. 질량 불균형은 0.0000220551%입니다. 600 Pa의 기준 결과는 없으므로 해당 압력의 총유량 제약 충족은 판정할 수 없습니다. T03의 CFD 성능 역시 아직 확인되지 않았습니다.

`measured_responses.py`는 첨부 CSV의 wide 형식을 받고 반모델 출구 유량의 크기로 계산합니다. 원본 checker의 부호 관례를 유지하되 혼합 부호, 누락, 중복, 비유한 값은 거절합니다. `--design`과 `--pressure`를 함께 지정하면 optiSLang용 평면 숫자 JSON을 출력합니다. 지정하지 않으면 모든 설계의 결과와 동일 압력 baseline 존재/제약 판정(null은 판정 불가)을 출력합니다. 이는 계산만 수행하며 수렴 여부를 판단하지 않습니다.

## 파일 구조

- `pipeline.py`: 표준 라이브러리 기반 LHS DOE, 질량유량 응답, CadQuery 어댑터 호출, 로컬 순차 실행 CLI
- `examples/variables.example.json`: 13변수 설정 스키마와 5개 outlet 순서, 부호 정의
- `examples/outlet_flows.example.csv`: 후처리 입력 예제 (kg/s)
- `examples/local.example.json`: Windows ANSYS 2025 R2 실행 명령 구조
- `tests/test_pipeline.py`: LHS 층화, 응답식, 잘못된 입력과 실행 실패 검증

## 기본 실행

저장소 루트에서 Python 3.10 이상 사용. DOE/후처리는 외부 패키지가 필요 없습니다.

```sh
python -m unittest discover -s automation_t03/tests -v
python automation_t03/pipeline.py doe automation_t03/examples/variables.example.json /tmp/t03-doe --samples 100 --seed 42
python automation_t03/pipeline.py responses automation_t03/examples/variables.example.json automation_t03/examples/outlet_flows.example.csv /tmp/t03-responses.json
```

실제 작업에서는 예제 설정을 별도 파일로 복사하고 13개 실제 이름, 단위, 하한/기준/상한, outlet named selection을 입력하세요. 독립 균등분포 LHS이며 기준점 1개를 추가합니다. 기하학적 변수 간 제약은 원본 모델 기준으로 별도 검사해야 합니다. 이 코드는 민감도 계수를 추정하지 않습니다. DOE와 응답이 수집된 후 optiSLang에서 민감도/회귀 분석을 수행하세요. 표본 수는 예제일 뿐이며 분석의 수렴성에 따라 늘려야 합니다.

## CadQuery STEP 검증 연결

별도 Python 가상환경에 프로젝트 원본이 요구하는 CadQuery 버전을 설치하세요. 현재 재구성 코드는 CadQuery 2.6.1로 검증했습니다. `builder.py` 어댑터는 `build_geometry(parameters: dict)` 함수를 제공하며 CadQuery Workplane 또는 Shape를 반환해야 합니다. 어댑터에서 원본 코드를 호출하고 변수 이름을 매핑하세요. 전역변수만 바꾸고 실행하는 방식보다 명시적 함수 호출을 권장합니다.

```sh
python automation_t03/pipeline.py cad actual_variables.json cases/baseline/inputs.json builder.py cases/baseline/T03.step
```

CLI는 변수 범위, BRep 유효성, 양의 체적/솔리드 수를 확인하고 STEP을 재수입해 체적 일치까지 검사합니다. 길이 단위는 CadQuery/STEP/ANSYS 간에 별도 확인하세요. 이 검사는 유체영역의 연결성, 간극, 5개 outlet 위치나 기준 형상 치수의 일치를 증명하지 않으므로 실제 형상 확인이 추가로 필요합니다.

## 로컬 ANSYS 2025 R2 실행 구조

각 설계마다 별도 작업 디렉터리를 만들고 다음 파일을 준비합니다. 기존 결과가 있는 디렉터리는 재사용하지 않습니다.

```text
case_00001/
  inputs.json       # 13개 입력
  T03.step          # CadQuery 출력, 필요시 유체영역 추출
  mesh.wbjn        # Workbench에서 기록·검증한 Meshing journal
  solve.jou        # Fluent에서 기록·검증한 solver journal
  local.json       # examples/local.example.json에서 복사·경로 수정
  mesh.msh.h5      # Meshing 출력
  solved.cas.h5    # Fluent 출력
  solved.dat.h5
  outlet_flows.csv
  responses.json   # 후처리 출력
```

1. 로컬 설치와 라이선스 접근을 확인하세요. 예제의 `v252` 실행 파일 경로는 실제 설치에 맞게 변경하세요. 라이선스 값은 Git에 저장하지 않습니다.
2. ANSYS Workbench 2025 R2에서 기준 프로젝트의 Geometry → Meshing 작업을 journal로 기록해 `mesh.wbjn`으로 저장합니다. 새 STEP 절대경로 연결, 단위, 유체영역, named selections, mesh sizing/경계층, mesh update, Fluent mesh export를 포함하세요. Workbench의 시스템/컨테이너 이름은 프로젝트에서 확인해야 하므로 범용 journal을 임의로 생성하지 않았습니다.
3. Fluent 2025 R2에서 `mesh.msh.h5` 읽기 → mesh check → 질소 물성/압축성·난류모델/에너지/경계조건 설정 → 초기화 → 수렴 계산 → case/data 저장 → outlet 5개 mass-flow-rate report export 작업을 journal로 기록합니다. 기존 검증된 case가 있다면 설정을 재사용하되 새로운 mesh와 경계 매핑을 확인하세요. `solve.jou`는 최종 종료 명령까지 포함해 무인 실행이 가능해야 합니다.
4. Fluent 보고서를 아래 CSV 계약으로 변환하는 adapter를 원본 후처리 코드와 연결하세요. 임의의 마지막 숫자나 문자열을 추출하지 말고 outlet 이름과 단위를 검증하세요. Fluent report 파일은 바로 이 CSV 형식이라는 가정을 하지 않습니다.
5. 수렴 잔차, 질량수지, monitor 안정성, mesh quality를 별도 검사하세요. 단순 파일 생성이나 낮은 CV는 CFD 수렴 검증이 아닙니다. 실패 설계는 응답을 만들지 않고 비정상 종료해야 합니다.

```sh
python automation_t03/pipeline.py local case_00001/local.json
python automation_t03/pipeline.py local case_00001/local.json --execute
python automation_t03/pipeline.py responses actual_variables.json case_00001/outlet_flows.csv case_00001/responses.json
```

첫 명령은 명령 목록만 출력합니다. `--execute`를 지정해야 실제 실행합니다. runner는 shell 없이 인자 배열을 실행하고 단계별 로그, timeout, 종료 코드와 새 출력 파일을 검사합니다. Meshing 실패 시 Fluent를 실행하지 않습니다. 예제 실행 명령은 현재 클라우드에서 ANSYS로 검증되지 않았습니다.

## 질량유량과 CV 정의

CSV 헤더는 `outlet,mass_flow_kg_s`이며 설정된 outlet마다 정확히 한 행이 필요합니다. Fluent 원시 부호를 확인한 후 `outward_sign`을 +1 또는 -1로 설정하세요. 출구 방향으로 정규화한 값이 음수이면 역류 또는 부호 오류로 처리합니다. 절댓값 변환은 사용하지 않습니다. 단위 변환은 입력 전에 수행합니다.

5개 출구 유량 q에 대해 `total_mass_flow_kg_s = sum(q)`, `cv = population_stddev(q) / mean(q)`, `cv_percent = 100 * cv`입니다. 표본 표준편차가 아닌 모집단 표준편차를 사용합니다. 0 총유량, NaN, 무한대, 중복/누락 outlet은 실패합니다. 총 출구 유량만으로 입출구 질량수지는 계산할 수 없으므로 입구 유량을 별도 확보해야 합니다.

## optiSLang 파일 인터페이스

입력 템플릿은 DOE가 생성한 `inputs.json`입니다. JSON의 13개 숫자 값을 optiSLang의 입력 매개변수로 등록하고 설정의 단위/범위를 연결합니다. 버전별 UI 문법에 의존하는 가짜 placeholder 대신 optiSLang 텍스트 파일 매개변수화 기능으로 각 숫자를 등록하세요.

출력은 `responses.json`의 숫자 필드입니다: `mdot_outlet_1_kg_s`부터 `mdot_outlet_5_kg_s`까지 설정의 outlet 순서로 매핑되며, `total_mass_flow_kg_s`, `cv`, `cv_percent`가 추가됩니다. 출력 파서에서 JSON key별 숫자를 등록하세요. CV 최소화, 총유량 목표/제약은 팀의 실제 설계 요구에 따라 설정합니다.

각 optiSLang 평가의 독립 작업 디렉터리에 inputs.json을 작성하고 CAD → Meshing → Fluent → 보고서 변환 → responses 명령을 순차 실행하는 Process chain을 구성하세요. 각 단계의 비정상 종료를 failed design으로 전달하고, 평가 시작 시 과거 responses.json이 없음을 보장하세요. solver 라이선스 수와 메모리에 맞춰 병렬 평가 수를 제한하세요. 이 파일 계약은 예제로 검증했으며 실제 optiSLang 프로젝트 연결과 ANSYS end-to-end 실행은 로컬 검증이 남아 있습니다.

## 실제 optiSLang 출력 매핑

반모델 CSV는 `reference_inputs/fluent_results.csv`의 헤더를 그대로 사용하세요. 압력별 각 평가가 수렴 후 이 형식으로 측정 결과를 내보내도록 연결합니다. `measured_responses.py --design <설계ID> --pressure <Pa>` 출력에서 `cv_percent`를 최소화 응답으로, `full_mass_flow_g_s`를 해당 압력 baseline 이상 제약으로 등록합니다. `mass_imbalance_percent`는 별도 수렴 품질 응답으로 등록하되 허용치는 팀 기준으로 정하세요. `mdot_outlet_1_kg_s`~`mdot_outlet_5_kg_s`는 반모델 크기 값입니다. baseline이 CSV에 없으면 미리 확인한 같은 압력 기준값을 optiSLang 제약에 등록해야 하며, 기준이 없다고 통과시키면 안 됩니다.

## 검증 산출물

현재 인스턴스의 `/workspace/t03-validation/`에는 기준 STEP 재생성, 형상 검증 JSON, 100 LHS+T03 기준점 DOE, 실측 baseline 응답 JSON이 있습니다. 8개 단위 테스트를 통과했으며 Meshing/Fluent/optiSLang 실제 실행은 미검증입니다. `requirements-cad.lock`은 설치된 Python 패키지 버전을 기록합니다.
