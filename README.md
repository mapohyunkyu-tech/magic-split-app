# v82 US ETF 데이터 로더 디버그/수정

기준: v79 T100 실전운용판 보존 + 미국 ETF T100 백테스트 메뉴 유지.

## 수정 내용

- 7-1 T100 하이브리드 실전운용판 유지
- 미국 ETF 데이터 로더 재수정
- FDR → Stooq → YahooChart → yfinance 순서로 시도
- 실패 시 상태표에 HTTP 오류, 빈값, 모듈 없음 등 원인을 표시
- Stooq는 `QQQ.us`, `QQQ` 양쪽 시도
- Yahoo는 query1/query2 둘 다 시도

## 실행

```bash
streamlit run app.py
```

미국 ETF 테스트:

```text
9. 미국 ETF T100 백테스트
→ 미국 ETF T100 백테스트 실행
```

결과가 없으면 화면의 `데이터 로딩 상태` 표에서 `시도/실패원인` 컬럼을 확인한다.

## 주의

Streamlit Cloud/배포 환경에서 외부 인터넷 요청이 막히거나 Yahoo/Stooq가 차단되면 자동 데이터 수집이 실패할 수 있다. v82는 실패 원인을 화면에 보여주도록 수정했다.
