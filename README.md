# v80_US_ETF_T100_BACKTEST

## 핵심

`9. 미국 ETF T100 백테스트` 메뉴를 추가했습니다.

미국 상장 ETF 후보군으로 월간 상위 2개 T100 전략을 테스트합니다.

- 월 1회 리밸런싱
- 후보군 중 모멘텀 상위 2개 선택
- 1일 -5% CAP 방어
- 5일 누적 -6% CAP 방어
- 방어 시 T100 70% / 현금 30%
- 여러 미국 ETF 후보군 일괄 비교

## 기본 후보군

1. US 균형형 6종
   - QQQ, SPY, GLD, IEF, SHY, UUP

2. US 공격형 7종
   - QQQ, SPY, VTI, GLD, TLT, UUP, SHY

3. US 안정형 7종
   - SPY, QQQ, GLD, IEF, SHY, UUP, TLT

4. US 올웨더식 8종
   - QQQ, SPY, IWM, GLD, TLT, IEF, SHY, UUP

5. US 성장+방어 8종
   - QQQ, XLK, SOXX, SPY, GLD, IEF, SHY, UUP

## 사용 방법

```text
streamlit run app.py
→ 9. 미국 ETF T100 백테스트
→ 후보군 5개 전부 비교 체크
→ 미국 ETF T100 백테스트 실행
```

## 출력

- 요약표
- 일별 자산곡선 CSV
- 월별 리밸런싱 CSV
- 데이터 로딩 상태 CSV
- 전체 결과 ZIP 다운로드

## 주의

- 앱에서 Stooq 일별 가격 데이터를 불러옵니다.
- 가격 기준 백테스트라 배당, 세금, 환전수수료, 미국 ETF 양도세는 별도 고려해야 합니다.
- 인터넷 연결이 막힌 환경에서는 데이터 로딩이 실패할 수 있습니다.
