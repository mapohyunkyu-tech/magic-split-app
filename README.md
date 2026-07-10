# v101_OVERHEAT70_VISIBLE_DEFAULT_20260710

## 목적
전체 기능을 유지하면서 `7-1` 메뉴에서 6개월 +70% 과열회피가 바로 보이도록 만든 버전입니다.

## 변경
- 사이드바 메뉴명: `7-1. T100 70% 과열회피 운용모드`
- 7-1 화면 기본 선택값: `확장형 과열회피 6개월 +70% 단독`
- 기존 v84 방어/6310 금액판단 유지
- 기존 Google Sheet T100 기록 복구/백업 버튼 유지
- 대장주 4슬롯 / Donchian 보조전략 유지

## 배포
ZIP을 풀어서 아래 파일/폴더를 GitHub에 모두 덮어쓰기 하세요.

- app.py
- requirements.txt
- runtime.txt
- README.md
- sector_leader_universe_20260629.csv
- .streamlit/config.toml

Streamlit Cloud에서는 `Manage app → Clear cache → Reboot app`을 실행하세요.
