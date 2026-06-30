# BUNKER_70_30_DUAL_NAVER_FALLBACK_FIX_20260630

방공호 듀얼모멘텀이 계속 CASH:100%로 떨어지는 문제를 한 번 더 보강한 버전입니다.

## 수정
- 국내 ETF 6자리 코드가 FinanceDataReader에서 실패하면 네이버 차트 API로 백업 로딩
- QQQ/GLD 같은 해외 ETF가 FinanceDataReader에서 실패하면 Stooq CSV로 백업 로딩
- KODEX200/KOSDAQ150/NASDAQ100/GOLD/DOLLAR 후보 데이터 로딩 실패 시 전부 CASH로 조용히 떨어지는 문제 완화
- 기존 DatetimeArray sort_values 수정 유지

## 정상 확인
백테스트 결과에서 아래가 나와야 정상입니다.
- 방공호가격데이터자산수 > 0
- 비현금방공호일수 > 0
- 방공호보유가 CASH:100%만 반복되지 않음

예: NASDAQ100:50%,GOLD:50% / GOLD:50%,DOLLAR:50%
