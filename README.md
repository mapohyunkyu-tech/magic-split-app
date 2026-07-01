# v57 T100 HYBRID 1↔3 LIVE NO MAGIC TERNARY FIX

## 수정 내용

운용모드에서 표를 표시할 때 아래처럼 삼항 표현식으로 Streamlit 객체가 화면에 출력되던 문제를 제거했습니다.

- `show_pinned_dataframe(...) if ... else st.dataframe(...)` 제거
- 명시적인 `if/else` 블록으로 변경
- Streamlit magic 표시 방지용 `.streamlit/config.toml` 포함

## 실행

반드시 ZIP을 통째로 풀고, 압축을 푼 폴더 안에서 실행하세요.

```bash
cd magic_split_v57_T100_HYBRID_13_LIVE_NO_MAGIC_TERNARY_FIX_package
streamlit run app.py
```

## 운용 기준

- 천만원 시작 기준 총자산 1,500만원 전까지는 6310 전환 불가
- 그 전에는 1순위 T100 실전형만 운용
- +50% 수익 도달 시 3순위 6310 잠금 가능
