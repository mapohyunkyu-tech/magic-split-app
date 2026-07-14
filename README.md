# overheat70 v105 sheets merge local fix

## 수정 목적
7월 14일 운용기록을 저장한 뒤 `기존 Google Sheet에서 T100 기록 불러오기`를 누르면 7월 14일 기록이 사라지고 7월 9일 기록으로 돌아가는 문제를 막는 버전입니다.

## 핵심 수정
- Google Sheet 불러오기 시, Sheet 기록만으로 로컬 기록을 덮어쓰지 않습니다.
- 현재 앱 로컬에 저장된 T100 기록도 함께 병합합니다.
- 같은 기준일이 있으면 로컬 앱 기록을 최종 우선합니다.
- 병합 후 `T100_70_SIMPLE_HISTORY` 탭에 다시 저장해 다음 불러오기에서도 14일 기록이 유지되도록 했습니다.
- 저장 후 바로 rerun되어 "저장했습니다" 메시지가 사라지는 문제를 줄이기 위해, 저장 결과를 session_state에 넣고 다음 화면에서 표시합니다.
- Sheets 설정이 있으면 자동백업 체크 기본값을 ON으로 둡니다.
- `로컬 최신기록을 Google Sheet 저장탭에 강제 덮어쓰기` 버튼을 추가했습니다.

## 배포 파일
- app.py
- requirements.txt
- runtime.txt
- README.md
- sector_leader_universe_20260629.csv
- .streamlit/config.toml
