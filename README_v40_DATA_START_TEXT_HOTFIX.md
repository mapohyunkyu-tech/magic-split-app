# Magic Split v40 - data_start_text 빠른 실행 오류 수정

## 수정 내용

v39 프록시/Turbo 빠른 실행에서 다음 오류가 발생하던 문제를 수정했습니다.

```text
방공호/Turbo 빠른 실행 실패: name 'data_start_text' is not defined
```

원인은 빠른 실행 경로에서 summary CSV를 만들 때 `자산별데이터기간`, `자산별사용가능일수`에 들어갈 문자열 변수가 생성되지 않은 상태로 참조된 것입니다.

v40에서는 `bunker_price_status_df`가 있든 없든 아래 변수를 항상 생성합니다.

- `data_start_text`
- `data_usable_text`

## 사용법

1. 기존 `app.py`를 이 파일로 교체
2. Streamlit 앱 재시작/재배포
3. `2010부터 장기검증` 선택
4. `T10/T100 Turbo 공격ETF 100% NO CTA - 지수/환율 프록시` 선택
5. `방공호/Turbo만 빠른 실행` 클릭

## 검사

```text
python -m py_compile app.py
```

통과.
