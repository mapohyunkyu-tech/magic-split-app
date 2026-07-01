# Magic Split v30 - 미국 CTA ETF 자동조회 적용

## 버전
`v30_AUTO_US_CTA_FETCH_20260701`

## 핵심 변경
사용자가 미국 CTA ETF CSV를 직접 올리지 않아도 됩니다.

CTA 보완형 모드에서 앱이 아래 순서로 미국 상장 관리선물 ETF 데이터를 자동 조회합니다.

1. `DBMF`
2. `KMLM`
3. `CTA`

조회 실패 시에만 CSV 업로드를 백업으로 사용합니다.

## 적용 구조
기본 073/064 자산은 국내 상장 ETF 기준입니다.

- CASH: CD금리 / KOFR / 단기금리 ETF를 연수익률 가정으로 대체
- GOLD: ACE KRX금현물 / 골드선물 ETF 후보
- DOLLAR: 미국달러선물 ETF 후보
- KODEX200
- KOSDAQ150
- 국내상장 NASDAQ100 ETF

CTA 추가형은 국내 ETF 대체가 아니라 미국 상장 관리선물 ETF를 방공호 내부 보완재로 사용합니다.

## 테스트 모드

- `0/7/3 방공호형 공격복리`
- `0/7/3-C10 CTA방공호`
- `0/7/3-C15 CTA방공호`
- `0/6/4 공격형`
- `0/6/4-C10 CTA방공호`
- `0/5/5 참고공격형`
- `0/5/5-C10 CTA방공호`

## 자동조회 방식

앱 내부에서 다음 순서로 시도합니다.

1. 기존 FDR 캐시
2. FinanceDataReader 직접 호출
3. 미국 ETF는 Stooq CSV 자동 조회

Stooq CSV 형식 예시:

```text
https://stooq.com/q/d/l/?s=dbmf.us&d1=20200101&d2=20260701&i=d
```

## CTA 역할 고정
CTA는 부스터가 아닙니다.
방공호 안에 넣는 보완재입니다.
목적은 수익률 폭발이 아니라 GOLD/DOLLAR/CASH 외 위기 헤지 엔진을 추가하는 것입니다.

## CSV 업로드는 선택사항
CSV 업로드는 자동조회가 막힐 때만 사용합니다.
필요 시 형식은 아래처럼 `Date, Close`만 있으면 됩니다.

```csv
Date,Close
2020-01-02,25.13
2020-01-03,25.20
```

## 검사
`python -m py_compile app_v30_auto_us_cta_fetch.py` 통과.
