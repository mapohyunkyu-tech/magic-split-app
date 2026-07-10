# T100 70% 운용모드 전용 안정판 + Google Sheets 복구

- 큰 70% 앱의 무거운 데이터 수집 기능 제거
- T100 70% 운용기록 저장/방어판정/리밸런싱만 유지
- 기존 Google Sheet 기록을 탐색해서 복구 가능
- 저장은 원본 훼손 방지를 위해 `T100_70_SIMPLE_HISTORY` 탭에 저장

## Streamlit Secrets

```toml
spreadsheet_id = "구글시트_ID"

[gcp_service_account]
type = "service_account"
project_id = "..."
private_key_id = "..."
private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
client_email = "서비스계정이메일@프로젝트.iam.gserviceaccount.com"
client_id = "..."
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "..."
universe_domain = "googleapis.com"
```

Google Sheet는 서비스계정 이메일에 편집 권한으로 공유해야 합니다.
