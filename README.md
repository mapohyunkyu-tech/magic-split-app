# v103_OVERHEAT70_SHEETS_LOADFIX_MOBILE_RESTORE

## 핵심 수정
- 7-1 메뉴에서 6개월 +70% 과열회피 운용모드가 보이도록 유지했습니다.
- Google Sheets 불러오기 우선순위를 수정했습니다.
  - 이전: `T100_70_HISTORY`를 먼저 읽어서 오래된 금액이 다시 살아날 수 있음
  - 수정: 새 저장 탭 `T100_70_SIMPLE_HISTORY`를 먼저 읽고, 여러 탭 기록을 병합
- 같은 기준일 기록이 여러 탭에 있으면 `T100_70_SIMPLE_HISTORY` 값을 우선합니다.
- 모바일에서 파일 업로드 버튼이 안 눌릴 때를 대비해 CSV 내용 붙여넣기 복원 칸을 추가했습니다.
- `plotly` 누락으로 FinanceDataReader import가 죽는 문제를 requirements에 반영했습니다.

## 올릴 파일
ZIP을 풀어서 아래 파일/폴더를 GitHub에 모두 덮어쓰기 하세요.

- app.py
- requirements.txt
- runtime.txt
- README.md
- sector_leader_universe_20260629.csv
- .streamlit/config.toml

## 사용 순서
1. Streamlit에서 Manage app → Clear cache → Reboot app
2. 7-1. T100 70% 과열회피 운용모드 진입
3. `기존 Google Sheet에서 T100 기록 불러오기` 클릭
4. 금액 확인
5. 오늘 값 입력 후 `오늘 운용기록 저장/갱신` 클릭
6. 자동 백업 체크 또는 `현재 T100 기록을 Google Sheet에 백업`으로 시트 백업

## 주의
`현재 T100 기록을 Google Sheet에 백업`은 화면 입력값이 아니라 앱에 저장된 운용기록을 백업합니다. 오늘 화면 값을 먼저 반영하려면 `오늘 운용기록 저장/갱신`을 먼저 누르세요.
