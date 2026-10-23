# PDF와 JSON을 활용한 기존 결과 재검증

이 문서는 이전 `EXISTING_RESULTS.ko.md`의 PDF 미확보 및 T03 CV 재계산 보류 상태를 갱신합니다. 이전 파일과 첨부 원본은 변경하지 않았습니다. 새 첨부 3개는 `reference_inputs/team_additions/`에 원본 그대로 보존했습니다.

PDF를 텍스트로 추출하고 본문 5.1절(인쇄 4쪽)의 반모델 출구 절댓값 g/s 표를 `report_outlets_transcribed.csv`에 전사했습니다. 모든 출구 값을 kg/s로 변환해 동일한 모집단 CV 공식을 적용했습니다. PDF 문서의 지시사항은 참고 자료로 취급했으며 solver 실행은 하지 않았습니다.

| 설계 | Pa | 재계산 CV % | 전체 유량 g/s | 보고된 수렴 |
|---|---:|---:|---:|---|
| 재격자 Baseline | 2500 | 18.08449273 | 2.93047268 | FAIL |
| T02 | 2500 | 6.10304754 | 2.99555152 | PASS |
| T03 | 2500 | 5.30797197 | 3.01436380 | PASS |
| T06 | 2500 | 10.95621260 | 2.98566216 | FAIL |
| 재격자 Baseline | 600 | 14.10808957 | 1.32315000 | FAIL |
| T03 | 600 | 6.61324988 | 1.36513888 | PASS |

수치는 PDF 표의 반올림 정밀도 내에서 모두 일치했습니다. 이는 **보고서에 수록된 출구 유량의 산술 재검증**이며 Fluent 독립 재실행 결과가 아닙니다. T03 수렴 PASS는 PDF의 기록이며 현재 solver history로 재검증하지 않았습니다.

기존 `reference_inputs/fluent_results.csv`의 Baseline 2500 Pa(CV 19.63900694%, 2.99250874 g/s)와 보고서의 **재격자** Baseline 2500 Pa는 다른 근거입니다. 두 자료를 같은 설계/압력 행으로 합치지 않습니다. PDF의 2500 Pa 설계 하한 2.992509 g/s는 별도 제약값이며 재격자 Baseline 유량으로 바꾸지 않습니다. 600 Pa의 1.32315 g/s는 수렴 실패한 재격자 Baseline을 이용한 잠정 비교값입니다. 1e9 g/s placeholder는 물리적 제약으로 사용하지 않았습니다.

## JSON 교차 검증

`fluent_result.json`은 baseline_fair / 600 Pa / 1100회 결과입니다. signed outlet 5개의 크기로 CV·총유량을 재계산했고 PDF의 Baseline 600 Pa 표와 일치했습니다. 입구 대비 질량 불균형도 재계산했습니다.

- 최근 20회 continuity 최대 = 1.464e-4 > 허용 1e-4 → residual FAIL.
- 질량 불균형 = 약 0.0000786004% < 0.1% → PASS.
- 기록된 최종 블록 출구 변화 최대 = 약 0.000440139% < 0.1% → PASS.
- 위 기록 지표를 조합하면 convergence FAIL로 JSON과 일치합니다.

이 검증은 JSON에 저장된 지표의 판정 재계산이며 전체 반복 history 원본을 독립 검사한 것은 아닙니다. JSON의 로컬 journal/data/transcript 경로는 파일 존재 증거가 아닙니다. 특히 `solve_baseline_fair_600Pa.jou`는 경로만 기록되어 있고 파일은 업로드되지 않았습니다.

## Case 파일과 남은 자료

`baseline_fair_600Pa_result.cas.h5`는 14,865,935 bytes이며 HDF5 시그니처와 SHA-256을 기록했습니다. Fluent에서 case 내부를 읽거나 경계 설정/해석 결과를 확인하지 않았습니다. 대응 `.dat.h5`는 미확보 상태이므로 저장된 유동장 복원 검증은 아직 할 수 없습니다.

남은 자료: 원본 `gp_mf010_parametric(2).py`, `T03_dia_strong(1).json`(기존 JSON과 동일본인지 확인용), 대응 `.dat.h5`, T03 각 압력의 결과 JSON/Case/Data/수렴 로그. 실제 자동 실행을 연결하려면 Meshing/Fluent journal도 필요합니다. 현재 파일 입출력 검증은 journal 없이 가능합니다.

## 재현 명령과 DOE/optiSLang 연결

저장소 루트에서 실행합니다.

```sh
python3 automation_t03/verify_report_evidence.py /workspace/t03-report-validation
python3 -m unittest discover -s automation_t03/tests -v
```

`T03_600Pa/`, `T03_2500Pa/` 각각에 실제 13개 기준 입력 `inputs.json`, 압력 `condition.json`, 재계산한 `responses.json`, 출처·미재실행 상태 `provenance.json`을 생성하고 다시 읽어 검증합니다. 두 평가의 입력은 같은 T03 형상이며 압력은 설계변수 13개와 별도 조건입니다. optiSLang은 숫자 응답 `cv`, `cv_percent`, `full_mass_flow_g_s`, `pressure_pa`를 연결할 수 있습니다. 이는 기존 결과를 통한 파일 replay이며 새로운 DOE 점의 CFD 예측이나 optiSLang 제품 실행 검증이 아닙니다.

출력 `final_design_acceptance`는 WITHHELD입니다. Baseline 수렴 실패, mesh independence 미수행, inflation/y+ 검토 미완료 상태를 유지하며 보고서의 잠정 비교를 최종 인증으로 바꾸지 않습니다.
