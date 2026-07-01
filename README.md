# Magic Split v50 - BAA/VAA Yahoo Adj Close 정확검증

## 목적
v49의 BAA/VAA 결과가 T100 대비 약하게 나와서, 데이터 문제가 아닌지 확인하기 위한 정확검증 버전입니다.

## 핵심 변경
- 미국 원규칙 BAA/VAA는 기본값을 `Yahoo Adj Close 전용(정확검증)`으로 변경했습니다.
- Yahoo 조정종가가 없는 미국 ETF는 FDR/Stooq로 자동 대체하지 않고 실패 처리합니다.
- 필요하면 `Yahoo 우선 + FDR/Stooq 백업`을 선택해 근사 데이터 확보용으로 돌릴 수 있습니다.
- 한국 ETF 프록시는 계속 별도 비교용으로 유지합니다.

## 실행 위치
`6. 섹터전략 백테스트` → `1-0-2) BAA / VAA 정확형 + Yahoo Adj Close 전용 + 한국 ETF 프록시 백테스트`

## 추천 실행값
- 기간: `2010부터 장기검증`
- 미국 원규칙: 체크
- 한국 ETF 프록시: 체크
- BAA Balanced도 같이: 체크
- 미국 BAA/VAA 데이터 모드: `Yahoo Adj Close 전용(정확검증)`
- 버튼: `BAA/VAA Yahoo Adj Close 정확검증 실행`

## 해석
- `Yahoo Adj Close 전용` 결과가 여전히 낮으면, BAA/VAA는 이번 2010~2026 구간에서 T100 방어형보다 약한 것으로 판단합니다.
- `Yahoo Adj Close 전용`에서 실패 자산이 많으면, 데이터 상태 CSV를 보고 해당 ETF 데이터를 별도 CSV로 보강해야 합니다.
- `Yahoo 우선 + FDR/Stooq 백업`은 정확검증이 아니라 데이터 확보용 근사 백테스트입니다.

## 검사
`python -m py_compile app.py` 통과.
