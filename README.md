# HOLDING_BACKTEST_V2_MARKET_FILTER_20260615

홀딩스캐너 백테스트 v2입니다.

## v2 추가 기능
- 장세필터: KODEX200 기준 120일선/60일 수익률로 하락장 진입 회피
- 상대강도 필터: 종목 60일 수익률이 벤치마크보다 약하면 제외
- 과열/붕괴 가드
- 목표/손절/기간청산 시뮬레이션
- 같은 종목 재진입 쿨다운

## 설치 파일
- app.py
- requirements.txt
- runtime.txt

기존 매직스플릿 앱에 덮어쓰지 말고, 별도 GitHub repo/Streamlit 앱으로 실행하세요.
