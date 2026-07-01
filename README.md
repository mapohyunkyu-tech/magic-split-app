# Magic Split v49 - BAA/VAA 정확형 + 한국 ETF 프록시 통합

## 핵심 변경
기존 BAA/VAA 근사판을 보강해 다음 두 계열을 한 번에 테스트할 수 있게 했습니다.

1. 미국 원규칙형
   - BAA Aggressive Exact US
   - BAA Balanced Exact US
   - VAA G4 Exact US

2. 한국 ETF 프록시형
   - BAA Aggressive KR Proxy
   - BAA Balanced KR Proxy
   - VAA G4 KR Proxy

## 미국 원규칙형 처리
- Yahoo Chart API의 Adj Close를 우선 사용합니다.
- 실패 시 FDR Adj Close/Close, Stooq Close 순으로 백업합니다.
- 월말 종가 기준 신호를 만들고 다음 거래일부터 반영합니다.
- BAA는 Canary 13612W + p0/avg(p0..p12) 상대모멘텀을 사용합니다.
- VAA-G4는 13612W breadth momentum을 사용합니다.
- BIL/SHY는 앱에서 CASH/CD/KOFR 프록시로 처리합니다.

## 한국 ETF 프록시형 처리
미국 ETF와 완전히 같은 상품이 국내에 없으므로 별도 KR Proxy 전략명으로 표시합니다.

주요 대체축:
- KOSPI200: 069500
- KOSDAQ150: 229200 / 233740
- NASDAQ100: 133690 / 379810 / 381170
- S&P500: 360750 / 379800 / 143850
- GOLD: 411060 / 132030 / 319640
- DOLLAR: 261240 / 138230
- BOND: 114260 / 148070 / 153130 / 152380
- CASH: 연 3% 일복리 프록시

## 실행 위치
6. 섹터전략 백테스트
→ 1-0-2) BAA / VAA 정확형 + 한국 ETF 프록시 백테스트
→ BAA/VAA 정확형 빠른 백테스트 실행

## 출력
- magic_split_BAA_VAA_summary_YYYY-MM-DD.csv
- magic_split_BAA_VAA_data_status_YYYY-MM-DD.csv
- 전략별 daily / signals / rebalances CSV

## 주의
- 미국 원규칙형은 가능한 한 원 규칙에 맞춘 백테스트입니다.
- 한국 ETF 프록시형은 국내 상장 ETF 대체 전략이므로 미국 원규칙과 동일 결과를 기대하면 안 됩니다.
- 배당/분배금 조정은 미국 Yahoo Adj Close가 잡힐 때 가장 정확합니다. 한국 ETF는 FDR/Naver 가격 기준이라 분배금 총수익과 차이가 날 수 있습니다.
