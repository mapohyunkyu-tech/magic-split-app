# v74 T100 운용기록 고정 저장 패치

## 핵심 수정
- T100 하이브리드 운용기록 `t100_hybrid_live_history.csv`를 앱 실행 폴더가 아니라 사용자 홈 폴더의 `magic_split_data` 폴더에 저장합니다.
- 새 ZIP/app.py를 덮어써도 기록이 유지됩니다.
- 예전 앱 폴더에 있던 `t100_hybrid_live_history.csv`가 발견되면 새 저장 위치로 1회 자동 복사합니다.
- 7-1 T100 하이브리드 운용모드에 저장 위치 표시, 백업 CSV 다운로드, 백업 CSV 복원 기능을 추가했습니다.

## 저장 위치 예시
- Windows: `C:\Users\사용자명\magic_split_data\t100_hybrid_live_history.csv`
- macOS/Linux: `/Users/사용자명/magic_split_data/t100_hybrid_live_history.csv` 또는 `/home/사용자명/magic_split_data/t100_hybrid_live_history.csv`

## 사용법
1. 새 app.py로 교체
2. `streamlit run app.py`
3. `7-1. T100 하이브리드 운용모드`
4. `운용기록 저장 위치 / 백업`에서 저장 위치 확인
5. 장마감 후 `오늘 운용기록 저장/갱신`

## 주의
- 기존 기록이 앱 폴더에 남아 있다면 첫 실행 때 자동 이전됩니다.
- 그래도 안전하게 백업 CSV 다운로드를 가끔 눌러 보관하세요.
