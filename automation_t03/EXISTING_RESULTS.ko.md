# 기존 CFD 결과의 근거와 추가할 자료

이 문서는 이전 README의 “T03/600 Pa 결과 미확보”를 현재 정보에 맞게 보완합니다. 팀에 결과가 없다는 뜻이 아니라 당시 클라우드에 제공된 자료에 결과가 없었다는 의미입니다. PDF 자체는 아직 없으며 아래 보고서 값은 사용자가 채팅으로 전달한 기록입니다.

| 설계/압력 | CV % | 전체 유량 g/s | 수렴 상태 | 현재 근거 |
|---|---:|---:|---|---|
| T03 / 600 Pa | 6.61325 | 1.365139 | PASS (보고값) | 사용자가 전달한 보고서 수치 |
| T03 / 2500 Pa | 5.30797 | 3.014364 | PASS (보고값) | 사용자가 전달한 보고서 수치 |
| Baseline / 600 Pa | 14.10809 | 1.323150 | FAIL (보고값) | 사용자가 전달한 보고서 수치 |
| Baseline / 2500 Pa | 19.6390069416 | 2.99250874 | 확인 불가 | 제공 CSV의 5개 출구 유량에서 직접 재계산 |

보고서의 T03 CV를 독립 재계산하려면 각 압력의 출구 5개 원시 질량유량이 필요합니다. CV와 총유량만으로 5개 유량을 복원하거나 새로운 CFD 측정값을 만들지 않습니다. 현재 수행한 것은 보고된 응답의 JSON 전달 검증과 제공된 Baseline 2500 Pa 원시 CSV의 CV 재계산입니다. 실제 Fluent 재실행은 전혀 수행하지 않았습니다.

600 Pa에서 T03 출구 합계 유량은 보고된 Baseline보다 0.041989 g/s 큽니다. 수치상 유량 비교와 별개로 Baseline이 수렴 FAIL이므로 이를 검증된 기준으로 최종 설계 PASS라고 판단하지 않습니다. Baseline 2500 Pa 역시 원시 CSV만으로 수렴 상태를 알 수 없습니다. 보고서의 압력 정의, 반모델/전체 환산, 경계조건 및 mesh 비교 가능성은 PDF를 확인한 뒤 조정해야 합니다.

## 저장소 확인 및 추가할 파일

현재 저장소와 /workspace 전체를 파일명으로 검색했습니다.

- `GP_MF010_ANSYS_CFD_Interim_Report_2026-10-22.pdf`: 없음. 보고서의 조건·표·수렴 근거 검토용으로 추가 필요.
- `gp_mf010_parametric(2).py`: 없음. 원본 CadQuery 파라미터 매핑과 재구성 코드 비교용으로 추가 필요.
- `T03_dia_strong(1).json`: 해당 파일명 없음. 기존 업로드 `T03_dia_strong.json`은 있음. 동일본인지 확인하려면 원본 추가 필요.
- `fluent_results.csv`: 있음. `reference_inputs/fluent_results.csv`에는 Baseline 2500 Pa 한 행만 있음. 팀의 최신 CSV를 **다른 파일명**으로 추가 필요. T03 600/2500 Pa와 Baseline 600 Pa의 입구/출구 5개 유량, 압력, 설계 ID가 필요함.
- `baseline_fair_600Pa_result.cas.h5`: 없음. case 검토 및 재시작 준비용으로 추가 필요.
- 대응하는 `baseline_fair_600Pa_result.dat.h5`: 없음. 저장된 해석 필드 복원에는 대응 data 파일도 필요함. case 파일 하나만으로 저장된 유동 결과가 확보되었다고 판단하지 않음.
- 가능한 경우 T03 각 압력의 대응 case/data, residual/monitor/질량수지 로그: 기존 결과와 수렴 상태 검증용.

추가 파일은 예를 들어 `automation_t03/reference_inputs/team_additions/`에 원본 이름을 유지해 저장하세요. 기존 CSV를 덮어쓰지 마세요. Meshing/Fluent journal은 현재 미확보 상태를 유지하며 파일 인터페이스 검증의 선행조건은 아닙니다.

## 파일 인터페이스 검증 실행

저장소 루트에서:

```sh
python3 automation_t03/verify_existing_results.py /workspace/t03-existing-results
python3 -m unittest discover -s automation_t03/tests -v
```

`reported_summary_user_provided.csv`는 원본 보고서에서 직접 추출한 파일이 아니라 사용자 전달 수치를 별도로 기록한 파일입니다. 스크립트는 기존 13개 변수 DOE의 T03 기준점과 첨부 JSON을 비교하고 600/2500 Pa별 `inputs.json`, `condition.json`, `responses.json`, `provenance.json`을 생성·재수입해 검증합니다. `responses.json`은 optiSLang에 등록할 수 있는 숫자 응답이며 `provenance.json`은 보고값/원시 유량 재계산/재실행 여부를 구분합니다. 응답 파일 replay는 optiSLang 제품 자체에서 프로젝트를 실행한 검증이 아닙니다.

생성 결과에서 `qualified_design_pass: null`은 최종 판정 보류입니다. `flow_comparison_pass`는 같은 압력에서 기록된 유량의 산술 비교만 나타냅니다. `reported_convergence_pass`는 보고된 수렴 상태를 숫자로 옮긴 값이며 재검증된 수렴 상태가 아닙니다.

현재 10개 테스트 통과. PDF 확인, T03/600 Pa 원시 유량 CV 재계산, 원본 CadQuery 실행, Fluent/Workbench/optiSLang 실환경 실행은 미수행입니다.
