# Magic Split v31 - 064-C10 진짜 방공호 수정

## 버전
v31_TRUE_DEFENSE_CTA_064_FIX_20260701

## 수정 배경
기존 v30의 `0/6/4-C10 CTA방공호` 모드에서 064 계열 방공호가 `aggressive_dual` 로직으로 떨어져 `KODEX200`, `NASDAQ100` 같은 주식형 ETF를 보유하는 문제가 있었습니다.

이 경우 064-C10은 방공호 50% + CTA 10% + 부스터 40%가 아니라, 사실상 주식형 ETF 비중이 과도하게 커진 구조가 되어 수익률이 과대평가됩니다.

## 핵심 수정
064/064-C10/055/055-C10 계열도 기존 073과 동일하게 방공호는 `defensive_dual`만 사용하도록 수정했습니다.

```python
if split_702010 or split_532 or split_073 or split_064 or split_055:
    safe_mode = "defensive_dual"
```

## 방공호 허용 자산
- CASH
- GOLD
- DOLLAR
- BOND
- CTA

## 방공호 금지 자산
- KODEX200
- KOSDAQ150
- NASDAQ100
- 기타 주식형 ETF

## 부스터 허용 자산
- KODEX200
- KOSDAQ150
- NASDAQ100
- GOLD
- DOLLAR

## 064-C10 수정 구조
- 대장주 0%
- 기존방공호 50% = CASH/GOLD/DOLLAR/BOND 안에서만 운용
- CTA 10% = DBMF/KMLM/CTA 미국 상장 관리선물 ETF 자동조회
- 수익부스터 40% = KODEX200/KOSDAQ150/NASDAQ100/GOLD/DOLLAR
- 방어구역 합계 60%

## 출력 검증 포인트
마지막 출력에서 아래를 확인하세요.

1. `진짜방공호보유`에 KODEX200/NASDAQ100이 없어야 합니다.
2. `수익부스터보유`에만 KODEX200/NASDAQ100이 허용됩니다.
3. `CTA보유`는 별도 칸에 분리됩니다.
4. summary CSV에 `방공호허용자산`, `방공호금지자산`, `부스터허용자산`이 표시됩니다.

## 문법 검사
`python -m py_compile app_v31_true_defense_cta_064_fix.py` 통과
