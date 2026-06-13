# 매직스플릿 Streamlit 안정형 앱

요양원 목록을 Streamlit 서버 내부 CSV가 아니라 **구글시트**에 저장하는 안정형 버전입니다.
서버가 재시작되거나 재배포되어도 요양원 목록은 구글시트에 남습니다.

## 구성

- `app.py` : Streamlit 앱 본체
- `requirements.txt` : 설치 라이브러리
- `.streamlit/secrets.example.toml` : Streamlit secrets 예시

## 앱 메뉴

1. 요양원
   - 목록 보기
   - 요양원 추가
   - 요양원 졸업 처리
   - 변경 로그 기록
   - CSV 다운로드

2. 운영판단기
   - 예수금 / 매입금액 / 평가손익 / 보유종목수 / 요양원수 입력
   - 장부자산 기준 단계 판단
   - 신규매수 가능 개수 판단

3. TOP50
   - 장세 자동 판단
   - 요양원/졸업후재진입금지 종목 자동 제외
   - 후보 TOP50 생성
   - TOP50 결과 구글시트 저장 및 CSV 다운로드

## 구글시트 준비

1. 구글시트 새 파일 생성
2. URL에서 시트 ID 복사
   - `https://docs.google.com/spreadsheets/d/여기가_시트_ID/edit`
3. 구글 클라우드에서 서비스 계정 생성
4. 서비스 계정 JSON 키 발급
5. JSON 안의 `client_email`을 구글시트에 공유하고 **편집자 권한** 부여

## Streamlit secrets 설정

Streamlit Community Cloud에서 앱 배포 후:

`Settings` → `Secrets`에 `.streamlit/secrets.example.toml` 형식으로 입력합니다.

핵심은 아래 두 가지입니다.

```toml
spreadsheet_id = "구글시트_ID"

[gcp_service_account]
type = "service_account"
project_id = "..."
private_key_id = "..."
private_key = """-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"""
client_email = "..."
client_id = "..."
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "..."
universe_domain = "googleapis.com"
```

## GitHub 업로드

1. GitHub 새 저장소 생성
2. `app.py`, `requirements.txt` 업로드
3. Streamlit Community Cloud에서 New app 생성
4. 저장소 선택
5. Main file path: `app.py`
6. Deploy

## 주의

- 무료 Streamlit은 리소스 제한이 있어 TOP50 계산이 느릴 수 있습니다.
- 처음에는 TOP50 계산 종목수를 150~250개로 두고 테스트하세요.
- 요양원 목록은 구글시트에 저장되므로 서버 재시작으로 날아가지 않습니다.
- 삭제 기능은 일부러 넣지 않았습니다. 실수 방지를 위해 졸업 처리와 변경로그만 둡니다.
