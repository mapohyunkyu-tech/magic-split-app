# v27_SECTOR_BACKTEST_COMPOUND_REGIME_20260629

매직스플릿 v27 섹터전략 백테스트 증액투자 + 장세검증 버전입니다.

## 핵심 유지

- 기존 ROLE_GUARD 수익확대형 로직 유지
- 증액투자 모드 ON/OFF 유지
- 검증종목 범위: 핵심만 / 전체 유지
- 회전형 기본 OFF 유지
- 전체 CSV 묶음 다운로드 유지

## 추가 기능

### 1. 백테스트 기간 확대

- 빠른검증 60거래일
- 기본검증 120거래일
- 실전검증 240거래일
- 장세검증 480거래일
- 스트레스검증 720거래일
- 사용자지정

### 2. 연환산 수익률 표시

요약에 아래 항목을 추가했습니다.

- 단순연환산수익률
- 복리연환산수익률

### 3. 월별결과 탭 추가

월별로 아래 항목을 확인할 수 있습니다.

- 월수익률
- 월손익
- 월최저현금
- 월최대낙폭
- 매수/매도 건수

### 4. 장세별결과 탭 추가

KODEX200(069500)을 코스피 대체 벤치마크로 사용해 장세를 단순 분류합니다.

- 강한상승장
- 상승장
- 횡보장
- 조정장
- 하락장
- 급락일
- 장세불명

장세별로 아래 항목을 확인합니다.

- 전략누적수익률
- KODEX200누적수익률
- 초과수익률
- 전략최대낙폭
- 최저현금
- 최악일손익

### 5. 추가 CSV 다운로드

전체 ZIP 다운로드에 아래 CSV를 추가했습니다.

- magic_split_sector_backtest_monthly_YYYY-MM-DD.csv
- magic_split_sector_backtest_regime_YYYY-MM-DD.csv
- magic_split_sector_backtest_regime_daily_YYYY-MM-DD.csv

## 검사

- python -m py_compile app.py 통과

