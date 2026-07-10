# overheat70_v100_full_features_overheat70_runtimefix

## 목적
오류 전 전체 기능을 유지하면서 `확장형 과열회피 6개월 +70%` 메뉴/함수를 살린 안정 배포판입니다.

## 포함 기능
- 기존 매직스플릿 전체 메뉴 유지
- `7-1. T100 하이브리드 운용모드` 유지
- `9. 미국 ETF T100 백테스트` 내 과열회피/급등회피 계열 유지
- `확장형 과열회피 6개월 +70%` 자산선택 로직 유지
- 대장주 4슬롯 / Donchian 보조전략 코드 유지
- Google Sheets 저장 구조 유지

## 안정화
- Python `3.11` 고정: `runtime.txt`
- Streamlit `1.39.0` 고정
- numpy/pandas/FinanceDataReader/gspread/google-auth 버전 고정
- Streamlit file watcher OFF

## 배포 파일
GitHub에 아래 파일/폴더를 그대로 올리세요.

```text
app.py
requirements.txt
runtime.txt
README.md
sector_leader_universe_20260629.csv
.streamlit/config.toml
```

## 주의
직전 v85 안정 requirements 패키지는 v84 하이브리드 복구판이라 `6개월 +70% 과열회피` 메뉴가 빠져 있었습니다. 이 v100은 v99 전체기능 코드를 기준으로 런타임/패키지만 안정화한 버전입니다.
