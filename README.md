# Magic Split T100 Overheat 70 Persistent

T100 70% 운용기록을 Google Sheets에 저장하도록 수정한 버전입니다.
Streamlit Cloud가 재부팅되거나 하루 지나도 기록이 유지됩니다.

## Files
- app.py
- requirements.txt
- README.md

## Notes
Streamlit Secrets에 기존 Google Sheets 설정이 있어야 합니다.
저장 시 Google Sheet에 `T100_70_HISTORY` 시트가 자동 생성됩니다.
