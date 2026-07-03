# v76_T100_SAVE_RESET_STREAMLIT_FIX

## 수정 내용

v75에서 `오늘 운용기록 저장/갱신` 버튼을 누를 때 Streamlit 오류가 발생하던 문제를 수정했습니다.

원인:
- `T100 누적 투입원금` 입력칸은 `t100_v65_base`라는 Streamlit widget key를 사용합니다.
- v75는 저장 버튼을 누른 같은 실행 흐름 안에서 `st.session_state["t100_v65_base"]`를 직접 바꾸려고 했습니다.
- Streamlit은 이미 생성된 위젯의 session_state key를 같은 실행 중 다시 수정하면 `StreamlitAPIException`을 냅니다.

수정:
- 저장 버튼을 누를 때는 즉시 widget key를 바꾸지 않습니다.
- `_t100_v76_pending_widget_updates`에 다음 실행 때 반영할 값을 저장합니다.
- `st.rerun()` 후 화면이 다시 시작될 때 위젯 생성 전에 값이 반영됩니다.
- 저장 후 `오늘 전략 추가입금`, `오늘 전략 인출`, `오늘 T100 실제 추가매수액`, `오늘 T100 현금화매도액` 입력칸은 0으로 초기화됩니다.

## 유지된 기능

- v74: 사용자 홈 폴더 `magic_split_data`에 T100 운용기록 영구 저장
- v75: 투입원금 / 어제 평가금 / 오늘 평가금 / 오늘 실제 추가매수액 분리 계산
- 방어판정 공식:

```text
오늘 판정기준금액 = 어제 T100 평가금액 + 오늘 T100 실제 추가매수액 - 오늘 T100 현금화매도액
1일 변동률 = 오늘 장마감 T100 평가금액 ÷ 오늘 판정기준금액 - 1
```

## 실행

```bash
streamlit run app.py
```

메뉴:

```text
7-1. T100 HYBRID 1↔3 단순 운용모드
```
