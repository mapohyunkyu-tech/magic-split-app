# v27_SECTOR_LIVE_OPERATION_BOARD_HOLDING_LEDGER_PERSIST_FIX_20260629

## 수정 내용

- `8. 실전 보유장부`가 앱 폴더가 아니라 사용자 홈 폴더의 `MagicSplitData`에 자동 저장됩니다.
- 새 버전 zip을 새로 깔아도 같은 PC에서는 보유장부/매도기록을 자동으로 다시 불러옵니다.
- 저장 위치가 화면에 표시됩니다.
- `현재 장부 즉시 자동저장`, `자동저장 파일 다시 불러오기` 버튼을 추가했습니다.
- 매수 기록 추가, 매도/축소 기록, 장부 수정/삭제, CSV 불러오기 후 자동 저장됩니다.
- 삼성SDI 종목명 보정과 회전형 OFF 신규매수 제외 룰은 유지됩니다.

## 자동저장 위치

- Windows 예시: `C:\Users\사용자명\MagicSplitData`
- macOS/Linux 예시: `/Users/사용자명/MagicSplitData` 또는 `/home/사용자명/MagicSplitData`

저장 파일:

- `magic_split_live_holding_ledger.csv`
- `magic_split_live_sell_history.csv`

## 사용법

1. `8. 실전 보유장부`로 이동
2. 매수/매도 기록 입력
3. 앱이 자동으로 `MagicSplitData`에 저장
4. 다음 버전을 새로 받아도 같은 PC면 자동 불러오기

## 검사

`python -m py_compile app.py` 통과
