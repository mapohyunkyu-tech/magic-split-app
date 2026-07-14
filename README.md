# overheat70 v104 sheets direct upsert

## 수정 목적
T100 운용기록을 7월 14일로 저장했는데 Google Sheet에서 다시 불러오면 7월 9일 기록으로 되돌아가는 문제를 수정한 버전입니다.

## 핵심 수정
- `오늘 운용기록 저장/갱신` 시 Google Sheets 자동백업이 켜져 있으면, 방금 만든 오늘 기록을 `T100_70_SIMPLE_HISTORY` 탭에 직접 upsert합니다.
- 로컬 CSV를 다시 읽어서 백업하지 않으므로, 이전 기록이 다시 백업되는 문제를 줄였습니다.
- Google Sheet 불러오기는 `T100_70_SIMPLE_HISTORY` 값을 최우선 기준으로 사용합니다.
- 기존 탭 기록은 보조로 병합하되, 같은 날짜는 저장탭 값이 이깁니다.
- 불러오기 후 병합본을 다시 `T100_70_SIMPLE_HISTORY`에 저장해 오래된 탭 회귀를 막습니다.
- `Google Sheet 저장탭만 다시 확인` 버튼을 추가했습니다.

## 배포 파일
- app.py
- requirements.txt
- runtime.txt
- README.md
- sector_leader_universe_20260629.csv
- .streamlit/config.toml
