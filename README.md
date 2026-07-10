# 70% 과열회피 v95 Optional Sheets

- Google Sheets secrets가 있으면 T100_70_HISTORY 시트에 영구저장합니다.
- secrets가 없어도 앱이 죽지 않고 임시 로컬 저장으로 실행됩니다.
- Streamlit Cloud의 임시 로컬 저장은 재부팅/재배포/시간 경과 후 사라질 수 있으므로 CSV 백업을 내려받아 두세요.

## 실행

```bash
pip install -r requirements.txt
streamlit run app.py
```
