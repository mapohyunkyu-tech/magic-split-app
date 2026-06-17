# MAGIC v27 PINNED STOCK COLUMN

v27_LIVE_TRIGGER_PRICE_HINT 기반 안정 패치입니다.

수정 내용:
- TOP50 표에서 `종목`/`코드` 컬럼을 왼쪽 고정
- 보유차수 판단표에서 `종목`/`코드` 컬럼을 왼쪽 고정
- 저장된 보유차수 편집표에서 `삭제`/`종목`/`코드` 고정
- 표 인덱스 숨김 처리로 모바일 화면에서 공간 절약
- Streamlit 구버전에서 pinned/hide_index 미지원 시 앱이 죽지 않도록 fallback 처리

목적:
- 모바일에서 오른쪽으로 가로 스크롤해도 어떤 종목인지 계속 보이게 함
- `추가매수기준가`, `현재장도달시`, `차수손익률` 등을 볼 때 종목명을 일일이 되돌아가서 확인하지 않게 함

배포:
- GitHub 루트에 app.py, requirements.txt, runtime.txt를 올리세요.
- Streamlit Cloud에서 Reboot/Clear cache 후 실행하세요.
