# MAGIC v27 FDR LISTING FALLBACK FIX

## 수정명
v27_FDR_LISTING_FALLBACK_FIX_20260617

## 수정 이유
TOP50에서 `계산 종목수 700`으로 실행했는데 유니버스 진단이 아래처럼 뜨는 문제가 있었습니다.

```text
listing_rows: 0
final_universe: 10
error: FDR StockListing KRX 0 rows
```

이 상태는 700개를 계산한 것이 아니라, FinanceDataReader의 `StockListing("KRX")`가 0행으로 실패해서 강제포함/보유종목만 계산한 상태입니다.

## 수정 내용
1. FDR `StockListing("KRX")` 1차 시도
2. 실패 또는 0행/소량/가격·거래대금 비어 있음 감지
3. KRX 직접 CSV 다운로드 백업으로 전종목 시세 복구
4. KRX 직접 CSV도 실패하면 FDR `KOSPI` + `KOSDAQ` 개별 목록으로 최소 전체 코드 목록 복구
5. 유니버스 진단 engine 문구 변경
   - `FDR KRX + KRX CSV + KOSPI/KOSDAQ fallback`
6. TOP50 설명 문구 변경
   - FDR 실패 시 백업 유니버스로 복구한다고 표시

## 정상 확인 기준
TOP50 실행 후 유니버스 진단에서 아래처럼 나와야 합니다.

```text
listing_rows: 2000 이상 권장
market_filtered: 2000 이상 권장
final_universe: 계산 종목수 + 강제포함/보유종목 근처
error: 빈값
```

계산 종목수를 700으로 넣었다면 `final_universe`가 10개 수준이면 안 됩니다.

## 설치
GitHub 루트에 아래 파일을 덮어쓰기하세요.

- app.py
- requirements.txt
- runtime.txt

Streamlit Cloud에서는 배포 후 반드시 아래를 권장합니다.

1. Manage app
2. Clear cache
3. Reboot app
4. TOP50 재실행

## 참고
KRX/FDR 외부 데이터가 모두 막히면 그래도 0개가 될 수 있습니다. 그 경우에는 Streamlit Cloud 네트워크/일시적 KRX 응답 문제일 수 있으니 Reboot 후 재실행하세요.
