# v70 T100 A분할 + 5% 익절 + 1차 재진입 백테스트

## 추가/수정 내용

`10. T100 A분할 백테스트` 메뉴에 아래 규칙을 반영했습니다.

- 월초 T100 상위 2개 ETF 선택
- 종목당 1차 3,000만원 진입
- 각 종목이 월초 기준가 대비 -5%, -10%, -15%, -20%, -25%, -30% 도달 시 500만원씩 추가매수
- 종목별 최대 추가 6회
- 각 차수별 매수가 대비 +5% 도달 시 해당 차수만 익절
- 1차는 익절되면 같은 날 1차 금액으로 즉시 재진입
- 2차 이상은 해당 월 안에서 단계별 1회만 추가매수
- 다음 달 리밸런싱 시 남은 포지션 전량 정리 후 새 상위 2개 ETF로 교체

## 메뉴 위치

```text
streamlit run app.py
→ 10. T100 A분할 백테스트
→ T100 A분할 v70 백테스트 실행
```

## 기본값

```text
총자금: 120,000,000원
월초 1종목당 진입금: 30,000,000원
-5%마다 1회 추가금: 5,000,000원
추가매수 간격: 5%
최대 추가횟수: 6회
차수별 익절률: 5%
1차 익절 후 즉시 재진입: ON
수수료/세금 비율: 0.0003
```

## 출력 파일

ZIP 다운로드 안에 다음 CSV가 들어갑니다.

- `magic_split_T100_A_SCALEIN_TP5_REBUY_summary_YYYY-MM-DD.csv`
- `magic_split_T100_A_SCALEIN_TP5_REBUY_daily_YYYY-MM-DD.csv`
- `magic_split_T100_A_SCALEIN_TP5_REBUY_trades_YYYY-MM-DD.csv`
- `magic_split_T100_A_SCALEIN_TP5_REBUY_monthly_YYYY-MM-DD.csv`
- `magic_split_T100_A_SCALEIN_TP5_REBUY_data_status_YYYY-MM-DD.csv`

## 해석 포인트

- `익절건수`: 모든 차수 익절 횟수
- `1차재진입건수`: 1차가 +5% 익절 후 다시 산 횟수
- `추가매수건수`: -5% 단계별 추가매수 횟수
- `실현손익합계`: 익절 및 월말정리로 확정된 손익 합계

