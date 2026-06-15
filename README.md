# MAGIC SPLIT V20 GROUP LOT INPUT

- v19 보유차수 판단기 유지
- 평균단가 직접 입력 없음
- 종목명을 반복해서 쓰지 않는 묶음수동입력 추가
- 입력 예시:

```text
[삼성E&A]
1,64800,3
2,58400,3

[대덕전자]
1,23000,10
2,20700,10
```

- 기존 한 줄 입력 `삼성E&A,1,64800,3`도 계속 지원
- Google Sheets에는 `보유차수` 탭으로 저장
- 프로그램이 `종목평균단가_자동`, `종목전체손익률_자동`을 계산
- TOP50에는 보유차수 종목을 강제 포함

GitHub/Streamlit에는 app.py, requirements.txt, runtime.txt를 올리세요.
Google 서비스 계정 JSON은 절대 GitHub에 올리지 말고 Streamlit Secrets에만 넣으세요.
