# MAGIC SPLIT V19 LOT HOLDINGS JUDGE

- v18 기능 유지
- 보유종목 판단기를 차수별 입력 방식으로 변경
- 평균단가를 직접 입력하지 않음
- 입력 예시: `삼성E&A,1,64800,3`, `삼성E&A,2,58400,3`
- Google Sheets에는 `보유차수` 탭으로 저장
- 프로그램이 참고용으로 `종목평균단가_자동`, `종목전체손익률_자동`을 계산
- TOP50에는 보유차수 종목을 강제 포함

GitHub/Streamlit에는 app.py, requirements.txt, runtime.txt를 올리세요.
Google 서비스 계정 JSON은 절대 GitHub에 올리지 말고 Streamlit Secrets에만 넣으세요.
