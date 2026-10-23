# T03 ANSYS CFD/DOE 자동화

**이 코드로 실제 ANSYS Meshing·Fluent 계산을 아직 수행하지 않았습니다.**
클라우드에서는 STEP 생성/비교, 경계 분류 로직, 기존 결과의 CV 재계산, 파일 인터페이스 및 실패 처리만 검증했습니다. Windows ANSYS 2025 R2와 optiSLang에서의 실제 실행·API 호환성은 로컬 검증이 남아 있습니다.

Windows 사용자는 [실행 지침](local_ansys/README.ko.md)부터 읽으세요. 저장소 전체가 필요합니다. `local_ansys` 폴더만 복사해서는 실행할 수 없습니다.

## 포함된 실행 경로

13개 입력 JSON → CadQuery STEP → Workbench/Meshing → Fluent → 출구 유량 → CV·전체 유량 → optiSLang 응답 JSON입니다. 먼저 T03 2500 Pa pilot을 검증하고 영수증을 생성한 뒤 600 Pa/DOE로 확장합니다. 실제 자동화 API는 Windows에서 검증해야 하며 Meshing의 내부 Fluent exporter는 버전 의존 부분입니다.

- 진입점: [Run-T03Pilot.ps1](local_ansys/Run-T03Pilot.ps1)
- 입력: [T03_inputs.json](local_ansys/T03_inputs.json), [변수 범위](t03_variables.json)
- 의존성: [requirements-local.txt](local_ansys/requirements-local.txt)
- 실행 구현: [run_design.py](local_ansys/run_design.py), [mechanical_mesh.py](local_ansys/mechanical_mesh.py), [fluent_worker.py](local_ansys/fluent_worker.py)
- optiSLang 외부 프로세스: [evaluate_design.py](local_ansys/evaluate_design.py)
- 검증 코드: `tests/`

2500 Pa 유량 하한은 **2.992509 g/s**이며 재격자 Baseline의 2.93047268 g/s와 구분합니다. CFD/수렴 실패 시 정상 DOE 응답을 반환하지 않습니다. 기존 보고서의 PASS 기록이나 파일 replay를 새 CFD 실행 성공으로 표시하지 않습니다.

## 원본 및 근거

`reference_inputs/`에는 업로드한 팀 원본 8개와 별도로 작성한 전사 CSV가 있습니다. 업로드 원본 8개는 바이트 단위로 일치함을 확인했습니다. [원본 무결성 목록](validation/upload_original_integrity.json)을 참고하세요. 원래 저장소 루트의 README도 변경하지 않았습니다.

최신 문서는 이 README와 `local_ansys/README.ko.md`입니다. 이전 `README.ko.md`, `EXISTING_RESULTS.ko.md`, `REPORT_VERIFIED.ko.md`는 당시 확보한 자료와 계산 근거를 보존한 문서이므로 현재 실행 가능 상태는 최신 지침을 따르세요. `validation/`은 기존 결과 재계산 및 오프라인 검사 자료이며, Windows의 새 CFD 결과가 아닙니다. 기록의 `/workspace/...`는 당시 클라우드 경로입니다.

## GitHub 반영 범위

`automation_t03/`를 새로 추가합니다. 팀 원본은 수정 없이 참조용으로 포함하며, case 파일 크기는 약 14.9 MB입니다. 설치 가상환경·Python 캐시·실제 로컬 run 디렉터리는 반영 대상이 아닙니다. Job 디렉터리는 저장소 밖(예: `C:\t03-runs\...`)을 사용하세요. 현재 GitHub commit/push 여부는 Git 기록으로 확인해야 하며 코드 준비 완료가 원격 반영을 뜻하지 않습니다.
