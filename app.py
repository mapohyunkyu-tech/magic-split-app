# =====================================================
# 매직스플릿 Streamlit 안정형 앱
# v9_COLAB12_STYLE_FDR_20260614
# 핵심: FinanceDataReader 기반 + 20260612 Colab 원본 190개 후보풀/점수식 반영
# 저장소: Google Sheets
# 메뉴: 1. 요양원 2. 운영판단기 3. TOP50 4. 도움말
# =====================================================

import re
import time
from datetime import datetime

import numpy as np
import pandas as pd
import streamlit as st

from google.oauth2.service_account import Credentials
import gspread
import FinanceDataReader as fdr

# =====================================================
# 기본 설정
# =====================================================

APP_VERSION = "v9_COLAB12_STYLE_FDR_20260614"

st.set_page_config(
    page_title="매직스플릿 관리기",
    page_icon="📈",
    layout="wide"
)

NURSING_COLUMNS = [
    "코드", "종목", "입력명", "상태", "차수",
    "등록일", "졸업일", "재진입금지해제일", "메모"
]

LOG_COLUMNS = [
    "시간", "작업", "코드", "종목", "입력명", "상태", "메모"
]

TOP50_COLUMNS = [
    "순위", "오늘매수", "코드", "종목", "등급", "점수",
    "현재가", "추천수량", "실제매수금액", "목표매수금액", "허용상한",
    "매수상태", "그룹", "거래대금60억", "눌림률", "20일수익률", "60일수익률",
    "거래대금점수", "회전점수", "기술점수", "모멘텀점수",
    "장세", "운영모드", "장세매수코멘트"
]

NAME_ALIAS = {
    "금호석유화학": "금호석유",
    "금호석화": "금호석유",
}

MANUAL_CODE_MAP = {
    "성광벤드": ("014620", "성광벤드"),
    "성광벤드 014620": ("014620", "성광벤드"),
    "태광": ("023160", "태광"),
    "태광 023160": ("023160", "태광"),
}

FORCE_UNIVERSE = {
    "014620": "성광벤드",
    "023160": "태광",
}

# 2026-06-12 Colab 원본 후보 190개를 "강제 매수"가 아니라 "반드시 계산 대상"으로 포함한다.
# Streamlit에서는 FDR로 현재 가격을 다시 가져와 점수를 재계산하지만,
# 후보풀과 점수 구조는 12일 Colab 원본에 최대한 맞춘다.
COLAB12_SEED_UNIVERSE = {
    "007810": "코리아써키트",
    "183300": "코미코",
    "064290": "인텍플러스",
    "052710": "아모텍",
    "080220": "제주반도체",
    "178320": "서진시스템",
    "067310": "하나마이크론",
    "170920": "엘티씨",
    "161390": "한국타이어앤테크놀로지",
    "457370": "한켐",
    "001820": "삼화콘덴서",
    "388790": "라이콤",
    "446540": "메가터치",
    "160980": "싸이맥스",
    "420770": "기가비스",
    "007390": "네이처셀",
    "200470": "에이팩트",
    "031980": "피에스케이홀딩스",
    "037460": "삼지전자",
    "417840": "저스템",
    "085620": "미래에셋생명",
    "252990": "샘씨엔에스",
    "336370": "솔루스첨단소재",
    "001740": "SK네트웍스",
    "290690": "소룩스",
    "281820": "케이씨텍",
    "031330": "에스에이엠티",
    "192080": "더블유게임즈",
    "083500": "에프엔에스테크",
    "219130": "타이거일렉",
    "212710": "아이에스티이",
    "089030": "테크윙",
    "074600": "원익QnC",
    "242040": "나무기술",
    "098460": "고영",
    "053610": "프로텍",
    "008060": "대덕",
    "319400": "현대무벡스",
    "089970": "브이엠",
    "011790": "SKC",
    "122640": "예스티",
    "001450": "현대해상",
    "241770": "메카로",
    "144960": "뉴파워프라즈마",
    "000430": "대원강업",
    "064400": "LG씨엔에스",
    "456010": "아이씨티케이",
    "204320": "HL만도",
    "033160": "엠케이전자",
    "417860": "오브젠",
    "033640": "네패스",
    "083450": "GST",
    "005950": "이수화학",
    "093370": "후성",
    "166090": "하나머티리얼즈",
    "330860": "네패스아크",
    "005290": "동진쎄미켐",
    "043260": "성호전자",
    "003690": "코리안리",
    "271830": "팸텍",
    "085910": "네오티스",
    "036010": "아비코전자",
    "195870": "해성디에스",
    "061970": "LB세미콘",
    "077500": "유니퀘스트",
    "004100": "태양금속",
    "356860": "티엘비",
    "126730": "코칩",
    "036200": "유니셈",
    "187870": "디바이스",
    "005430": "한국공항",
    "295310": "에이치브이엠",
    "051600": "한전KPS",
    "092200": "디아이씨",
    "440110": "파두",
    "036710": "심텍홀딩스",
    "004710": "한솔테크닉스",
    "010170": "대한광통신",
    "086670": "비엠티",
    "012750": "에스원",
    "307180": "아이엘",
    "020150": "롯데에너지머티리얼즈",
    "059090": "미코",
    "123010": "알엔티엑스",
    "336260": "두산퓨얼셀",
    "001800": "오리온홀딩스",
    "000240": "한국앤컴퍼니",
    "089890": "코세스",
    "041830": "인바디",
    "005090": "SGC에너지",
    "000720": "현대건설",
    "425040": "티이엠씨",
    "055550": "신한지주",
    "357880": "SKAI",
    "110990": "디아이티",
    "019210": "와이지-원",
    "086790": "하나금융지주",
    "340570": "티앤엘",
    "045100": "한양이엔지",
    "383220": "F&F",
    "052900": "KX하이텍",
    "049070": "인탑스",
    "003490": "대한항공",
    "265520": "AP시스템",
    "018880": "한온시스템",
    "017670": "SK텔레콤",
    "031430": "신세계인터내셔날",
    "272110": "케이엔제이",
    "081660": "미스토홀딩스",
    "437730": "삼현",
    "114810": "한솔아이원스",
    "102710": "이엔에프테크놀로지",
    "005850": "에스엘",
    "016360": "삼성증권",
    "078930": "GS",
    "214320": "이노션",
    "088350": "한화생명",
    "006340": "대원전선",
    "149950": "아바텍",
    "203650": "드림시큐리티",
    "104830": "원익머트리얼즈",
    "093320": "케이아이엔엑스",
    "007070": "GS리테일",
    "006110": "삼아알미늄",
    "028050": "삼성E&A",
    "142210": "유니트론텍",
    "320000": "한울반도체",
    "030000": "제일기획",
    "168360": "펨트론",
    "037440": "희림",
    "451220": "아이엠티",
    "321260": "프로이천",
    "052690": "한전기술",
    "173130": "오파스넷",
    "161890": "한국콜마",
    "030530": "원익홀딩스",
    "445090": "에이직랜드",
    "039440": "에스티아이",
    "008770": "호텔신라",
    "111770": "영원무역",
    "021240": "코웨이",
    "489790": "한화비전",
    "034220": "LG디스플레이",
    "180640": "한진칼",
    "092870": "엑시콘",
    "271560": "오리온",
    "112290": "와이씨켐",
    "090460": "비에이치",
    "041960": "코미팜",
    "356680": "엑스게이트",
    "003550": "LG",
    "125020": "티씨머티리얼즈",
    "229640": "LS에코에너지",
    "002350": "넥센타이어",
    "254490": "미래반도체",
    "010950": "S-Oil",
    "024840": "KBI메탈",
    "425420": "티에프이",
    "007660": "이수페타시스",
    "462870": "시프트업",
    "100790": "미래에셋벤처투자",
    "060980": "HL홀딩스",
    "452260": "한화갤러리아",
    "067170": "오텍",
    "069540": "빛과전자",
    "323410": "카카오뱅크",
    "248070": "솔루엠",
    "120110": "코오롱인더",
    "322310": "오로스테크놀로지",
    "012030": "DB",
    "181710": "NHN",
    "462350": "이노스페이스",
    "212560": "네오오토",
    "382800": "지앤비에스 에코",
    "083650": "비에이치아이",
    "322000": "HD현대에너지솔루션",
    "178920": "PI첨단소재",
    "017550": "수산세보틱스",
    "078600": "대주전자재료",
    "005940": "NH투자증권",
    "036540": "SFA반도체",
    "006220": "제주은행",
    "007340": "DN오토모티브",
    "065710": "서호전기",
    "033790": "피노",
    "094170": "동운아나텍",
    "200710": "에이디테크놀로지",
    "001440": "대한전선",
    "078350": "한양디지텍",
    "439090": "마녀공장",
}

COLAB12_GROUP_BY_CODE = {
    "007810": "기타",
    "183300": "기타",
    "064290": "기타",
    "052710": "기타",
    "080220": "반도체/전자",
    "178320": "기타",
    "067310": "반도체/전자",
    "170920": "기타",
    "161390": "반도체/전자",
    "457370": "기타",
    "001820": "기타",
    "388790": "기타",
    "446540": "기타",
    "160980": "기타",
    "420770": "기타",
    "007390": "기타",
    "200470": "기타",
    "031980": "반도체/전자",
    "037460": "반도체/전자",
    "417840": "기타",
    "085620": "기타",
    "252990": "기타",
    "336370": "기타",
    "001740": "기타",
    "290690": "기타",
    "281820": "기타",
    "031330": "기타",
    "192080": "기타",
    "083500": "반도체/전자",
    "219130": "기타",
    "212710": "기타",
    "089030": "반도체/전자",
    "074600": "반도체/전자",
    "242040": "기타",
    "098460": "기타",
    "053610": "기타",
    "008060": "PCB",
    "319400": "자동차",
    "089970": "기타",
    "011790": "기타",
    "122640": "기타",
    "001450": "자동차",
    "241770": "기타",
    "144960": "기타",
    "000430": "기타",
    "064400": "기타",
    "456010": "기타",
    "204320": "기타",
    "033160": "반도체/전자",
    "417860": "기타",
    "033640": "기타",
    "083450": "기타",
    "005950": "기타",
    "093370": "기타",
    "166090": "기타",
    "330860": "기타",
    "005290": "기타",
    "043260": "반도체/전자",
    "003690": "기타",
    "271830": "기타",
    "085910": "기타",
    "036010": "반도체/전자",
    "195870": "기타",
    "061970": "반도체/전자",
    "077500": "기타",
    "004100": "기타",
    "356860": "기타",
    "126730": "기타",
    "036200": "기타",
    "187870": "기타",
    "005430": "기타",
    "295310": "기타",
    "051600": "기타",
    "092200": "기타",
    "440110": "기타",
    "036710": "PCB",
    "004710": "반도체/전자",
    "010170": "기타",
    "086670": "기타",
    "012750": "기타",
    "307180": "기타",
    "020150": "기타",
    "059090": "기타",
    "123010": "기타",
    "336260": "기타",
    "001800": "기타",
    "000240": "기타",
    "089890": "기타",
    "041830": "기타",
    "005090": "기타",
    "000720": "자동차",
    "425040": "기타",
    "055550": "기타",
    "357880": "기타",
    "110990": "기타",
    "019210": "기타",
    "086790": "기타",
    "340570": "기타",
    "045100": "기타",
    "383220": "기타",
    "052900": "반도체/전자",
    "049070": "기타",
    "003490": "기타",
    "265520": "기타",
    "018880": "기타",
    "017670": "기타",
    "031430": "기타",
    "272110": "기타",
    "081660": "기타",
    "437730": "기타",
    "114810": "기타",
    "102710": "반도체/전자",
    "005850": "기타",
    "016360": "기타",
    "078930": "기타",
    "214320": "기타",
    "088350": "방산",
    "006340": "전력",
    "149950": "기타",
    "203650": "기타",
    "104830": "반도체/전자",
    "093320": "기타",
    "007070": "기타",
    "006110": "기타",
    "028050": "기타",
    "142210": "기타",
    "320000": "반도체/전자",
    "030000": "기타",
    "168360": "기타",
    "037440": "기타",
    "451220": "기타",
    "321260": "기타",
    "052690": "반도체/전자",
    "173130": "기타",
    "161890": "기타",
    "030530": "반도체/전자",
    "445090": "기타",
    "039440": "기타",
    "008770": "기타",
    "111770": "기타",
    "021240": "기타",
    "489790": "방산",
    "034220": "기타",
    "180640": "기타",
    "092870": "기타",
    "271560": "기타",
    "112290": "기타",
    "090460": "PCB",
    "041960": "기타",
    "356680": "기타",
    "003550": "기타",
    "125020": "기타",
    "229640": "전력",
    "002350": "기타",
    "254490": "반도체/전자",
    "010950": "기타",
    "024840": "기타",
    "425420": "기타",
    "007660": "PCB",
    "462870": "기타",
    "100790": "기타",
    "060980": "기타",
    "452260": "방산",
    "067170": "기타",
    "069540": "반도체/전자",
    "323410": "인터넷/소프트웨어",
    "248070": "기타",
    "120110": "기타",
    "322310": "반도체/전자",
    "012030": "기타",
    "181710": "기타",
    "462350": "기타",
    "212560": "기타",
    "382800": "기타",
    "083650": "PCB",
    "322000": "자동차",
    "178920": "기타",
    "017550": "기타",
    "078600": "반도체/전자",
    "005940": "기타",
    "036540": "반도체/전자",
    "006220": "기타",
    "007340": "기타",
    "065710": "반도체/전자",
    "033790": "기타",
    "094170": "기타",
    "200710": "반도체/전자",
    "001440": "전력",
    "078350": "기타",
    "439090": "기타",
}

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# =====================================================
# Google Sheets 연결
# =====================================================

def require_secrets():
    if "spreadsheet_id" not in st.secrets or "gcp_service_account" not in st.secrets:
        st.error("Google Sheets 설정이 없습니다. Streamlit Secrets에 spreadsheet_id와 gcp_service_account를 넣어야 합니다.")
        with st.expander("Secrets 예시 보기", expanded=True):
            st.code('''
spreadsheet_id = "구글시트_ID"

[gcp_service_account]
type = "service_account"
project_id = "..."
private_key_id = "..."
private_key = ''' + '"""' + '''-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n''' + '"""' + '''
client_email = "서비스계정이메일"
client_id = "..."
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "..."
universe_domain = "googleapis.com"
''', language="toml")
        st.stop()


@st.cache_resource(show_spinner=False)
def get_gspread_client():
    require_secrets()
    service_account_info = dict(st.secrets["gcp_service_account"])

    private_key = str(service_account_info.get("private_key", "")).strip()
    if (private_key.startswith('"') and private_key.endswith('"')) or (private_key.startswith("'") and private_key.endswith("'")):
        private_key = private_key[1:-1]
    private_key = private_key.replace("\\n", "\n").replace("\r\n", "\n").strip()
    service_account_info["private_key"] = private_key

    credentials = Credentials.from_service_account_info(service_account_info, scopes=SCOPES)
    return gspread.authorize(credentials)


@st.cache_resource(show_spinner=False)
def get_spreadsheet():
    client = get_gspread_client()
    spreadsheet_id = st.secrets["spreadsheet_id"]
    return client.open_by_key(spreadsheet_id)


def clean_value(v):
    if pd.isna(v):
        return ""
    if isinstance(v, (np.integer, int)):
        return int(v)
    if isinstance(v, (np.floating, float)):
        if float(v).is_integer():
            return int(v)
        return float(v)
    return str(v)


def write_worksheet(ws, df, headers):
    out = df.copy()
    for c in headers:
        if c not in out.columns:
            out[c] = ""
    out = out[headers]
    values = [headers]
    for _, row in out.iterrows():
        values.append([clean_value(row[c]) for c in headers])
    ws.clear()
    ws.update(values)


def ensure_worksheet(sheet, title, headers):
    try:
        ws = sheet.worksheet(title)
    except gspread.WorksheetNotFound:
        ws = sheet.add_worksheet(title=title, rows=1000, cols=max(len(headers), 10))
        ws.update([headers])
        return ws

    values = ws.get_all_values()
    if len(values) == 0:
        ws.update([headers])
    else:
        current_header = values[0]
        if current_header != headers:
            all_rows = values[1:]
            old_df = pd.DataFrame(all_rows, columns=current_header) if current_header else pd.DataFrame()
            for c in headers:
                if c not in old_df.columns:
                    old_df[c] = ""
            old_df = old_df[headers]
            write_worksheet(ws, old_df, headers)
    return ws


def get_ws(title, headers):
    sheet = get_spreadsheet()
    return ensure_worksheet(sheet, title, headers)


def read_worksheet_df(ws, headers):
    records = ws.get_all_records()
    df = pd.DataFrame(records)
    for c in headers:
        if c not in df.columns:
            df[c] = ""
    df = df[headers].copy()
    if "코드" in df.columns and len(df) > 0:
        df["코드"] = df["코드"].astype(str).str.replace(".0", "", regex=False).str.zfill(6)
    return df


def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def today_str():
    return datetime.today().strftime("%Y-%m-%d")


def load_nursing_df():
    ws = get_ws("요양원목록", NURSING_COLUMNS)
    df = read_worksheet_df(ws, NURSING_COLUMNS)
    if len(df) > 0:
        df["코드"] = df["코드"].astype(str).str.zfill(6)
    return df


def save_nursing_df(df):
    ws = get_ws("요양원목록", NURSING_COLUMNS)
    if len(df) > 0:
        df["코드"] = df["코드"].astype(str).str.zfill(6)
        df = df.drop_duplicates(subset=["코드"], keep="last").reset_index(drop=True)
    write_worksheet(ws, df, NURSING_COLUMNS)


def append_log(action, code, name, input_name, status, memo):
    ws = get_ws("변경로그", LOG_COLUMNS)
    row = [now_str(), action, str(code).zfill(6), name, input_name, status, memo]
    ws.append_row(row, value_input_option="USER_ENTERED")


def save_top50_df(df):
    ws = get_ws("TOP50", TOP50_COLUMNS)
    write_worksheet(ws, df, TOP50_COLUMNS)

# =====================================================
# 공통 유틸
# =====================================================

def parse_won(x):
    s = str(x).strip().replace(",", "").replace("원", "").replace(" ", "")
    if s == "":
        return 0
    neg = False
    if s.startswith("-"):
        neg = True
        s = s[1:]
    total = 0
    if "억" in s:
        a, b = s.split("억", 1)
        if a:
            total += float(a) * 100_000_000
        s = b
    if "만" in s:
        a = s.replace("만", "")
        if a:
            total += float(a) * 10_000
    else:
        if total == 0 and s:
            total += float(s)
    total = int(total)
    return -total if neg else total


def fmt_won(n):
    try:
        return f"{int(round(n)):,}원"
    except Exception:
        return str(n)


def normalize_name_text(text):
    text = str(text).replace(",", "\n")
    return [x.strip() for x in text.split("\n") if x.strip()]


def get_allowed_amount(target_amount):
    target_amount = int(target_amount)
    if target_amount == 150000:
        return 160000
    if target_amount == 200000:
        return 215000
    if target_amount == 250000:
        return 270000
    if target_amount == 300000:
        return 320000
    return int(target_amount * 1.07)


def calc_magic_buy_amount(price, target_amount):
    price = float(price)
    target_amount = int(target_amount)
    max_allowed = get_allowed_amount(target_amount)
    if price <= 0:
        return 0, 0, "가격오류"
    if price > max_allowed:
        return 0, 0, "매수불가"
    floor_shares = int(target_amount // price)
    if floor_shares < 1:
        floor_shares = 1
    floor_amount = floor_shares * price
    ceil_shares = floor_shares + 1
    ceil_amount = ceil_shares * price
    if ceil_amount <= max_allowed:
        shares = ceil_shares
        amount = ceil_amount
    else:
        shares = floor_shares
        amount = floor_amount
    if amount > max_allowed:
        return 0, 0, "매수불가"
    return int(shares), int(amount), "OK"

# =====================================================
# FinanceDataReader 데이터 엔진
# =====================================================

@st.cache_data(ttl=60 * 60 * 6, show_spinner=False)
def load_krx_master_fdr():
    try:
        krx = fdr.StockListing("KRX")
    except Exception:
        return pd.DataFrame(columns=["Code", "Name", "Market", "Close", "Amount", "Marcap", "Volume"])

    if krx is None or len(krx) == 0:
        return pd.DataFrame(columns=["Code", "Name", "Market", "Close", "Amount", "Marcap", "Volume"])

    krx = krx.copy()

    if "Code" not in krx.columns and "Symbol" in krx.columns:
        krx = krx.rename(columns={"Symbol": "Code"})
    if "Code" not in krx.columns:
        first_col = krx.columns[0]
        krx = krx.rename(columns={first_col: "Code"})

    if "Name" not in krx.columns:
        krx["Name"] = krx["Code"].astype(str)
    if "Market" not in krx.columns:
        krx["Market"] = "KRX"
    if "Close" not in krx.columns:
        krx["Close"] = np.nan
    if "Amount" not in krx.columns:
        krx["Amount"] = 0
    if "Marcap" not in krx.columns:
        krx["Marcap"] = 0
    if "Volume" not in krx.columns:
        krx["Volume"] = 0

    krx["Code"] = krx["Code"].astype(str).str.replace(".0", "", regex=False).str.zfill(6)
    krx["Name"] = krx["Name"].astype(str)
    krx["Market"] = krx["Market"].astype(str)

    for c in ["Close", "Amount", "Marcap", "Volume"]:
        krx[c] = pd.to_numeric(krx[c], errors="coerce").fillna(0)

    krx = krx.drop_duplicates(subset=["Code"], keep="first").reset_index(drop=True)
    return krx[["Code", "Name", "Market", "Close", "Amount", "Marcap", "Volume"]]


def find_valid_krx_date(end_date=None, max_back=30):
    # FDR은 날짜를 굳이 거래일로 강제하지 않아도 마지막 거래일까지 반환한다.
    if end_date is None:
        return datetime.today().strftime("%Y%m%d")
    return pd.to_datetime(str(end_date)).strftime("%Y%m%d")


def find_stock_by_name(input_name, krx):
    raw = str(input_name).strip()

    if raw in MANUAL_CODE_MAP:
        code, name = MANUAL_CODE_MAP[raw]
        return {"코드": str(code).zfill(6), "종목": name, "입력명": input_name}

    code_match = re.search(r"\b\d{6}\b", raw)
    if code_match:
        code = code_match.group(0).zfill(6)
        hit = krx[krx["Code"].astype(str).str.zfill(6) == code]
        if len(hit) > 0:
            r = hit.iloc[0]
            return {"코드": str(r["Code"]).zfill(6), "종목": str(r["Name"]), "입력명": input_name}
        name_only = re.sub(r"\b\d{6}\b", "", raw).strip()
        if name_only == "":
            name_only = code
        return {"코드": code, "종목": name_only, "입력명": input_name}

    search_name = NAME_ALIAS.get(raw, raw)
    hit = krx[krx["Name"] == search_name]

    if len(hit) == 0:
        hit = krx[krx["Name"].str.contains(search_name, regex=False, na=False)]

    if len(hit) == 0:
        temp = []
        for _, r in krx.iterrows():
            krx_name = str(r["Name"])
            if krx_name in search_name:
                temp.append(r)
        if len(temp) > 0:
            hit = pd.DataFrame(temp)

    if len(hit) == 0:
        return None

    r = hit.iloc[0]
    return {"코드": str(r["Code"]).zfill(6), "종목": str(r["Name"]), "입력명": input_name}


def get_nursing_exclude_codes():
    df = load_nursing_df()
    if len(df) == 0:
        return set()

    today = pd.Timestamp.today().normalize()
    exclude_codes = set()

    for _, r in df.iterrows():
        code = str(r["코드"]).zfill(6)
        status = str(r["상태"])
        if status == "요양원":
            exclude_codes.add(code)
        elif status == "졸업후재진입금지":
            release_raw = str(r.get("재진입금지해제일", "")).strip()
            if release_raw == "":
                exclude_codes.add(code)
            else:
                try:
                    release_dt = pd.to_datetime(release_raw)
                    if today <= release_dt:
                        exclude_codes.add(code)
                except Exception:
                    exclude_codes.add(code)
    return exclude_codes

# =====================================================
# 운영판단기
# =====================================================

def get_account_stage(book_asset):
    book_asset = int(book_asset)
    if book_asset < 90_000_000:
        return {"단계": "15만원 / 120종목 구간", "기본매수금액": 150000, "목표종목수": 120, "최대종목수": 120, "20만원슬롯한도": 0}
    if book_asset < 120_000_000:
        return {"단계": "15만원 / 120~150종목 확장 구간", "기본매수금액": 150000, "목표종목수": 140, "최대종목수": 150, "20만원슬롯한도": 10}
    if book_asset < 150_000_000:
        return {"단계": "15만원 기본 + 20만원 슬롯 확대 구간", "기본매수금액": 150000, "목표종목수": 160, "최대종목수": 170, "20만원슬롯한도": 40}
    if book_asset < 200_000_000:
        return {"단계": "20만원 기본 검토 구간", "기본매수금액": 200000, "목표종목수": 180, "최대종목수": 200, "20만원슬롯한도": 999}
    if book_asset < 300_000_000:
        return {"단계": "25만원 기본 검토 구간", "기본매수금액": 250000, "목표종목수": 210, "최대종목수": 240, "20만원슬롯한도": 999}
    return {"단계": "30만원 이상 금액확대 구간", "기본매수금액": 300000, "목표종목수": 230, "최대종목수": 280, "20만원슬롯한도": 999}


def downgrade_mode(current_mode, new_mode):
    rank = {"정상운용": 1, "제한매수모드": 2, "회수모드": 3, "강한 회수모드": 4}
    return new_mode if rank[new_mode] > rank[current_mode] else current_mode


def decide_operation(cash, cost, unrealized, total_holdings, nursing_count, target_holdings_input=None, used_20_slots=0):
    book_asset = cash + cost
    stage = get_account_stage(book_asset)
    base_amount = stage["기본매수금액"]
    stage_target = stage["목표종목수"]
    max_holdings = stage["최대종목수"]
    target_holdings = stage_target if target_holdings_input is None or target_holdings_input <= 0 else int(target_holdings_input)
    active_count = max(total_holdings - nursing_count, 0)

    mode = "정상운용"
    reasons = []

    if cash < 10_000_000:
        mode = downgrade_mode(mode, "강한 회수모드")
        reasons.append("예수금 1,000만원 미만")
    elif cash < 12_000_000:
        mode = downgrade_mode(mode, "회수모드")
        reasons.append("예수금 1,200만원 미만")
    elif cash < 15_000_000:
        mode = downgrade_mode(mode, "제한매수모드")
        reasons.append("예수금 1,500만원 미만")
    elif cash < 20_000_000:
        mode = downgrade_mode(mode, "제한매수모드")
        reasons.append("예수금 2,000만원 미만")

    if unrealized <= -10_000_000:
        mode = downgrade_mode(mode, "강한 회수모드")
        reasons.append("평가손익 -1,000만원 이하")
    elif unrealized <= -7_000_000:
        mode = downgrade_mode(mode, "회수모드")
        reasons.append("평가손익 -700만원 이하")
    elif unrealized <= -5_000_000:
        mode = downgrade_mode(mode, "제한매수모드")
        reasons.append("평가손익 -500만원 이하")

    if total_holdings > target_holdings:
        mode = downgrade_mode(mode, "회수모드")
        reasons.append("현재 보유종목수가 목표종목수 초과")
    if total_holdings >= max_holdings:
        mode = downgrade_mode(mode, "강한 회수모드")
        reasons.append("현재 보유종목수가 최대종목수 이상")

    room_to_target = max(target_holdings - total_holdings, 0)
    if mode in ["강한 회수모드", "회수모드"]:
        new_buy_count = 0
    elif mode == "제한매수모드":
        new_buy_count = min(room_to_target, 3)
        if cash < 15_000_000:
            cash_room = max((cash - 10_000_000) // base_amount, 0)
            new_buy_count = min(new_buy_count, int(cash_room))
    else:
        new_buy_count = min(room_to_target, 10)

    slot_limit = stage["20만원슬롯한도"]
    if slot_limit <= 0 or cash < 15_000_000:
        slot20_possible = 0
    elif slot_limit >= 999:
        slot20_possible = 999
    else:
        remaining_slot = max(slot_limit - used_20_slots, 0)
        if cash < 18_000_000:
            slot20_possible = min(remaining_slot, 3)
        elif cash < 22_000_000:
            slot20_possible = min(remaining_slot, 5)
        else:
            slot20_possible = min(remaining_slot, 10)

    reduce_need = max(total_holdings - target_holdings, 0)

    return {
        "예수금": cash,
        "매입금액": cost,
        "평가손익": unrealized,
        "장부자산": book_asset,
        "총보유종목수": total_holdings,
        "요양원종목수": nursing_count,
        "액티브종목수": active_count,
        "단계": stage["단계"],
        "기본매수금액": base_amount,
        "허용상한": get_allowed_amount(base_amount),
        "목표종목수": target_holdings,
        "최대종목수": max_holdings,
        "운영모드": mode,
        "신규매수가능개수": int(new_buy_count),
        "20만원슬롯가능개수": int(slot20_possible) if slot20_possible != 999 else 999,
        "회수필요종목수": int(reduce_need),
        "판단이유": reasons
    }

# =====================================================
# TOP50 계산
# =====================================================

def ms_prepare_indicator_df(raw_df):
    df = raw_df.copy()
    rename_map = {
        "Open": "open", "High": "high", "Low": "low", "Close": "close",
        "Volume": "volume", "Change": "change",
        "시가": "open", "고가": "high", "저가": "low", "종가": "close",
        "거래량": "volume", "거래대금": "amount"
    }
    df = df.rename(columns=rename_map)
    for c in ["open", "high", "low", "close", "volume", "amount"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    if "volume" not in df.columns:
        df["volume"] = 0
    if "amount" not in df.columns:
        df["amount"] = df["close"] * df["volume"]
    df = df.dropna(subset=["close"]).copy()
    df["ma20"] = df["close"].rolling(20).mean()
    df["ma60"] = df["close"].rolling(60).mean()
    df["ma120"] = df["close"].rolling(120).mean()
    df["amount_ma20"] = df["amount"].rolling(20).mean()
    df["amount_ma60"] = df["amount"].rolling(60).mean()
    df["ret20"] = df["close"].pct_change(20) * 100
    df["ret60"] = df["close"].pct_change(60) * 100
    df["ret120"] = df["close"].pct_change(120) * 100
    df["high120"] = df["close"].rolling(120).max()
    df["pullback120"] = (df["close"] / df["high120"] - 1) * 100
    return df


@st.cache_data(ttl=60 * 60 * 6, show_spinner=False)
def get_ohlcv_fdr_cached(code, start_date, end_date):
    try:
        start = pd.to_datetime(str(start_date)).strftime("%Y-%m-%d")
        end = pd.to_datetime(str(end_date)).strftime("%Y-%m-%d")
        df = fdr.DataReader(str(code).zfill(6), start, end)
        return df.copy()
    except Exception:
        return pd.DataFrame()


def ms_regime_asof_from_etf(asof_date):
    start = (pd.to_datetime(asof_date) - pd.DateOffset(days=300)).strftime("%Y%m%d")
    try:
        raw = get_ohlcv_fdr_cached("069500", start, asof_date)
        df = ms_prepare_indicator_df(raw)
        if len(df) < 120:
            return "장세불명"
        last = df.iloc[-1]
        close = float(last["close"])
        ma60 = float(last["ma60"])
        ma120 = float(last["ma120"])
        ret20 = float(last["ret20"])
        ret60 = float(last["ret60"])
        if close < ma120 and ret60 < -3:
            return "하락장"
        if ret20 < -5:
            return "약세장"
        if ret20 > 12:
            return "폭등장"
        if close > ma60 and ret60 > 5:
            return "상승장"
        return "횡보장"
    except Exception:
        return "장세불명"


def liquid500_excluded(name):
    bad_words = [
        "스팩", "SPAC", "리츠", "ETN", "ETF", "우선주", "우B", "우C",
        "제약", "바이오", "생명과학", "헬스케어", "진단", "백신", "치료제"
    ]
    n = str(name)
    return any(w.lower() in n.lower() for w in bad_words)


def infer_group_by_name(name):
    n = str(name)
    if any(k in n for k in ["전자", "반도체", "하이닉스", "마이크론", "테크", "칩", "세미", "피에스케이", "원익", "네패스", "코미코", "테스", "고영"]):
        return "반도체/전자"
    if any(k in n for k in ["써키트", "PCB", "대덕", "심텍", "이수페타시스", "비에이치"]):
        return "PCB"
    if any(k in n for k in ["현대차", "기아", "만도", "타이어", "모비스", "자동차"]):
        return "자동차"
    if any(k in n for k in ["한화", "현대로템", "LIG", "풍산", "방산"]):
        return "방산"
    if any(k in n for k in ["LS", "전선", "전력", "일진", "효성중공업", "제룡"]):
        return "전력"
    if any(k in n for k in ["NAVER", "카카오", "소프트", "인텔리", "웹"]):
        return "인터넷/소프트웨어"
    return "기타"


def score_candidate_core(df, name, regime="장세불명", high_price_limit=160000, strict=True):
    if df is None or len(df) < 80:
        return None
    if liquid500_excluded(name):
        return None

    clean = df.dropna(subset=["close"]).copy()
    if len(clean) < 60:
        return None

    last = clean.iloc[-1]
    price = float(last["close"])
    if price <= 0 or price > high_price_limit:
        return None

    amount60 = float(last.get("amount_ma60", 0)) if pd.notna(last.get("amount_ma60", np.nan)) else 0
    amount20 = float(last.get("amount_ma20", 0)) if pd.notna(last.get("amount_ma20", np.nan)) else 0

    # 12일 Colab은 거래대금 영향이 컸다. 다만 Streamlit/FDR에서는 amount가 약할 수 있어
    # 엄격 기준도 너무 높게 잡지 않는다.
    if strict and amount60 < 30_000_000:
        return None

    ret20 = float(last.get("ret20", 0)) if pd.notna(last.get("ret20", np.nan)) else 0
    ret60 = float(last.get("ret60", 0)) if pd.notna(last.get("ret60", np.nan)) else 0
    ret120 = float(last.get("ret120", 0)) if pd.notna(last.get("ret120", np.nan)) else 0
    pullback = float(last.get("pullback120", 0)) if pd.notna(last.get("pullback120", np.nan)) else 0

    close = float(last["close"])
    ma20 = float(last.get("ma20", np.nan)) if pd.notna(last.get("ma20", np.nan)) else np.nan
    ma60 = float(last.get("ma60", np.nan)) if pd.notna(last.get("ma60", np.nan)) else np.nan
    ma120 = float(last.get("ma120", np.nan)) if pd.notna(last.get("ma120", np.nan)) else np.nan

    # Colab 12일 파일 구조 복제: 총점 ≈ 20 + 거래대금점수(25) + 회전점수(15) + 기술점수(25) + 모멘텀점수(20)
    base_score = 20
    trading_score = min(amount60 / 10_000_000_000 * 25, 25)

    temp = df.copy()
    temp["r20"] = temp["close"].pct_change(20) * 100
    recent = temp.tail(750)
    rotate_count = int((recent["r20"] >= 10).sum())
    rotate_score = min(rotate_count / 25 * 15, 15)

    tech_score = 0
    if pd.notna(ma20) and close > ma20:
        tech_score += 5
    if pd.notna(ma60) and close > ma60:
        tech_score += 7
    if pd.notna(ma120) and close > ma120:
        tech_score += 7
    if ret20 > 0:
        tech_score += 3
    if ret60 > 0:
        tech_score += 3
    tech_score = min(tech_score, 25)

    # 12일 Colab의 모멘텀점수는 ret20과 ret60이 좋을수록 20점에 가까운 구조로 보정
    momentum_score = max(0, min(ret20 / 30 * 10, 10)) + max(0, min(ret60 / 100 * 10, 10))
    momentum_score = min(momentum_score, 20)

    total_score = base_score + trading_score + rotate_score + tech_score + momentum_score

    if strict:
        if total_score >= 85:
            grade = "A"
        elif total_score >= 75:
            grade = "B"
        elif total_score >= 65:
            grade = "C"
        else:
            grade = "D"
    else:
        grade = "완화"

    return {
        "종목": name,
        "등급": grade,
        "점수": round(total_score, 2),
        "현재가": int(price),
        "거래대금60억": round(amount60 / 100_000_000, 1),
        "거래대금20억": round(amount20 / 100_000_000, 1),
        "거래대금점수": round(trading_score, 2),
        "회전점수": round(rotate_score, 2),
        "기술점수": round(tech_score, 2),
        "모멘텀점수": round(momentum_score, 2),
        "눌림률": round(pullback, 2),
        "20일수익률": round(ret20, 2),
        "60일수익률": round(ret60, 2),
        "120일수익률": round(ret120, 2)
    }


def liquid500_score_candidate(df, name, regime="장세불명", high_price_limit=160000):
    return score_candidate_core(df, name, regime, high_price_limit, strict=True)


def relaxed_score_candidate(df, name, regime="장세불명", high_price_limit=160000):
    return score_candidate_core(df, name, regime, high_price_limit, strict=False)


def adjust_new_buy_by_regime(new_buy_limit, regime):
    regime_text = str(regime)
    if new_buy_limit <= 0:
        return 0, "회수모드/매수불가"
    if "급락" in regime_text or "하락" in regime_text:
        return 0, "하락장 신규매수 금지"
    if "약세" in regime_text:
        return min(new_buy_limit, 1), "약세장 1개 이하"
    if "횡보" in regime_text:
        return min(new_buy_limit, 3), "횡보장 3개 이하"
    if "상승" in regime_text:
        return min(new_buy_limit, 7), "상승장 정상 매수"
    if "폭등" in regime_text:
        return min(new_buy_limit, 5), "폭등장 과열 추격 제한"
    return min(new_buy_limit, 3), "장세 불명 3개 이하"


@st.cache_data(ttl=60 * 60 * 6, show_spinner=False)
def build_universe_fdr(price_limit, max_codes):
    diag = {
        "engine": "FinanceDataReader + Colab12Seed190",
        "listing_rows": 0,
        "market_filtered": 0,
        "price_filtered": 0,
        "excluded_name_filtered": 0,
        "sort_proxy": "",
        "seed_candidates": len(COLAB12_SEED_UNIVERSE),
        "seed_included": 0,
        "listing_included": 0,
        "final_universe": 0,
        "error": ""
    }

    max_codes = int(max_codes)
    universe = {}

    def add_code(code, name, source="listing"):
        code = str(code).replace(".0", "").zfill(6)
        name = str(name)
        if code in universe:
            return False
        if liquid500_excluded(name):
            return False
        universe[code] = name
        if source == "seed":
            diag["seed_included"] += 1
        else:
            diag["listing_included"] += 1
        return True

    # 1) Colab에서 이미 검증된 후보풀은 반드시 계산 대상으로 먼저 넣는다.
    #    단, 여기서 바로 TOP50 확정이 아니라 아래 루프에서 현재 데이터로 다시 점수 계산한다.
    for code, name in COLAB12_SEED_UNIVERSE.items():
        if len(universe) >= max_codes:
            break
        add_code(code, name, source="seed")

    # 2) FDR 상장목록에서 추가 후보를 만든다.
    try:
        krx = load_krx_master_fdr()
        diag["listing_rows"] = len(krx)
        if len(krx) == 0:
            raise RuntimeError("FDR StockListing KRX 0 rows")

        df = krx.copy()

        # Market 컬럼이 제대로 있으면 KOSPI/KOSDAQ 위주. 전부 KRX로만 오면 그대로 사용.
        if "Market" in df.columns:
            market_values = set(df["Market"].astype(str).unique())
            if len(market_values.intersection({"KOSPI", "KOSDAQ"})) > 0:
                df = df[df["Market"].isin(["KOSPI", "KOSDAQ"])]
        diag["market_filtered"] = len(df)

        for c in ["Close", "Amount", "Marcap", "Volume"]:
            if c not in df.columns:
                df[c] = 0
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)

        # 가격 데이터가 상장목록에 있으면 가격 필터 적용. 없으면 개별 OHLCV에서 걸러진다.
        if df["Close"].sum() > 0:
            df = df[(df["Close"] > 0) & (df["Close"] <= price_limit)]
        diag["price_filtered"] = len(df)

        before_excl = len(df)
        df = df[~df["Name"].apply(liquid500_excluded)]
        diag["excluded_name_filtered"] = before_excl - len(df)

        # Colab은 거래대금 영향이 크므로 가능한 한 거래대금/거래량 proxy로 정렬한다.
        # Amount가 없으면 Close*Volume, 그것도 없으면 Volume, 마지막으로 Marcap.
        if df["Amount"].sum() > 0:
            df["SortProxy"] = df["Amount"]
            diag["sort_proxy"] = "Amount"
        elif (df["Close"] * df["Volume"]).sum() > 0:
            df["SortProxy"] = df["Close"] * df["Volume"]
            diag["sort_proxy"] = "Close*Volume"
        elif df["Volume"].sum() > 0:
            df["SortProxy"] = df["Volume"]
            diag["sort_proxy"] = "Volume"
        elif df["Marcap"].sum() > 0:
            df["SortProxy"] = df["Marcap"]
            diag["sort_proxy"] = "Marcap"
        else:
            df["SortProxy"] = 0
            diag["sort_proxy"] = "original_order"

        df = df.sort_values("SortProxy", ascending=False).copy()

        for _, r in df.iterrows():
            if len(universe) >= max_codes:
                break
            add_code(r["Code"], r["Name"], source="listing")

    except Exception as e:
        diag["error"] = str(e)

    # 3) 사용자가 따로 넣은 강제 계산 종목
    for code, name in FORCE_UNIVERSE.items():
        if len(universe) >= max_codes and str(code).zfill(6) not in universe:
            # max를 넘더라도 수동 강제종목은 넣는다.
            pass
        add_code(code, name, source="seed")

    diag["final_universe"] = len(universe)
    return universe, diag

# =====================================================
# 화면
# =====================================================

st.title("📈 매직스플릿 관리기 안정형")
st.caption(f"{APP_VERSION}")
st.caption("요양원 목록은 Google Sheets에 저장됩니다. 서버가 재시작돼도 목록은 유지됩니다.")

try:
    sheet = get_spreadsheet()
    get_ws("요양원목록", NURSING_COLUMNS)
    get_ws("변경로그", LOG_COLUMNS)
    get_ws("TOP50", TOP50_COLUMNS)
    st.success("Google Sheets 연결 완료")
except Exception as e:
    st.error("Google Sheets 연결 실패")
    st.exception(e)
    st.stop()

menu = st.sidebar.radio("메뉴", ["1. 요양원", "2. 운영판단기", "3. TOP50", "4. 도움말"])

# =====================================================
# 1. 요양원
# =====================================================

if menu == "1. 요양원":
    st.header("1. 요양원")
    krx = load_krx_master_fdr()
    df = load_nursing_df()
    nursing_count = int((df["상태"] == "요양원").sum()) if len(df) else 0
    grad_count = int((df["상태"] == "졸업후재진입금지").sum()) if len(df) else 0

    col1, col2, col3 = st.columns(3)
    col1.metric("현재 요양원", nursing_count)
    col2.metric("졸업후재진입금지", grad_count)
    col3.metric("전체 기록", len(df))

    st.subheader("목록")
    if len(df) == 0:
        st.info("등록된 요양원 종목이 없습니다.")
    else:
        st.dataframe(df, use_container_width=True)
        st.download_button("요양원 목록 CSV 다운로드", data=df.to_csv(index=False).encode("utf-8-sig"), file_name="magic_split_nursing_list.csv", mime="text/csv")

    st.divider()
    st.subheader("요양원 추가")
    add_text = st.text_area("추가할 종목명", placeholder="예: 금호석유화학, 동진쎄미켐, 성광벤드 014620, 태광 023160", height=100)
    if st.button("요양원 추가", type="primary"):
        names = normalize_name_text(add_text)
        if len(names) == 0:
            st.warning("입력 없음")
        else:
            current = load_nursing_df()
            rows = []
            not_found = []
            for name in names:
                found = find_stock_by_name(name, krx)
                if found is None:
                    not_found.append(name)
                    continue
                rows.append({
                    "코드": found["코드"], "종목": found["종목"], "입력명": found["입력명"],
                    "상태": "요양원", "차수": 5, "등록일": today_str(), "졸업일": "",
                    "재진입금지해제일": "", "메모": "자동 5차 요양원"
                })
            if len(rows) == 0:
                st.error("추가된 종목 0개")
                if not_found:
                    st.write("못 찾은 종목:", not_found)
            else:
                add_df = pd.DataFrame(rows)
                combined = pd.concat([current, add_df], ignore_index=True)
                save_nursing_df(combined)
                for r in rows:
                    append_log("요양원추가", r["코드"], r["종목"], r["입력명"], "요양원", r["메모"])
                st.success(f"요양원 추가 완료: {len(rows)}개")
                st.dataframe(add_df, use_container_width=True)
                if not_found:
                    st.warning("못 찾은 종목: " + ", ".join(not_found))
                st.rerun()

    st.divider()
    st.subheader("요양원 졸업 처리")
    grad_text = st.text_area("졸업 처리할 종목명", placeholder="예: 금호석유화학, 동진쎄미켐, 태광 023160", height=80)
    if st.button("요양원 졸업 처리"):
        names = normalize_name_text(grad_text)
        if len(names) == 0:
            st.warning("입력 없음")
        else:
            current = load_nursing_df()
            if len(current) == 0:
                st.error("요양원 목록이 비어 있습니다.")
            else:
                release_date = (pd.Timestamp.today() + pd.offsets.BDay(20)).strftime("%Y-%m-%d")
                changed = []
                not_found = []
                for name in names:
                    found = find_stock_by_name(name, krx)
                    if found is None:
                        not_found.append(name)
                        continue
                    code = found["코드"]
                    mask = current["코드"].astype(str).str.zfill(6) == code
                    if mask.sum() == 0:
                        not_found.append(name)
                        continue
                    current.loc[mask, "상태"] = "졸업후재진입금지"
                    current.loc[mask, "졸업일"] = today_str()
                    current.loc[mask, "재진입금지해제일"] = release_date
                    current.loc[mask, "메모"] = "요양원 졸업 후 20거래일 재진입 금지"
                    changed.append(found)
                if len(changed) == 0:
                    st.error("졸업 처리된 종목 0개")
                    if not_found:
                        st.write("못 찾은 종목:", not_found)
                else:
                    save_nursing_df(current)
                    for r in changed:
                        append_log("요양원졸업", r["코드"], r["종목"], r["입력명"], "졸업후재진입금지", f"해제일 {release_date}")
                    st.success(f"졸업 처리 완료: {len(changed)}개 / 해제일 {release_date}")
                    if not_found:
                        st.warning("못 찾은 종목: " + ", ".join(not_found))
                    st.rerun()

    with st.expander("변경로그 보기"):
        log_ws = get_ws("변경로그", LOG_COLUMNS)
        log_df = read_worksheet_df(log_ws, LOG_COLUMNS)
        st.dataframe(log_df.tail(100), use_container_width=True)

# =====================================================
# 2. 운영판단기
# =====================================================

elif menu == "2. 운영판단기":
    st.header("2. 운영판단기")
    nursing_df = load_nursing_df()
    auto_nursing_count = int((nursing_df["상태"] == "요양원").sum()) if len(nursing_df) else 0

    col1, col2, col3 = st.columns(3)
    with col1:
        cash_text = st.text_input("예수금", value="849만")
    with col2:
        cost_text = st.text_input("매입금액", value="7607만")
    with col3:
        unreal_text = st.text_input("평가손익", value="-915만")

    col4, col5, col6, col7 = st.columns(4)
    with col4:
        total_holdings = st.number_input("총 보유종목수", min_value=0, value=126, step=1)
    with col5:
        nursing_count = st.number_input("요양원 종목수", min_value=0, value=auto_nursing_count, step=1)
    with col6:
        target_holdings = st.number_input("목표종목수 0이면 자동", min_value=0, value=0, step=1)
    with col7:
        used_20_slots = st.number_input("20만원 슬롯 사용개수", min_value=0, value=0, step=1)

    if st.button("운영판단 실행", type="primary"):
        cash = parse_won(cash_text)
        cost = parse_won(cost_text)
        unrealized = parse_won(unreal_text)
        result = decide_operation(cash, cost, unrealized, int(total_holdings), int(nursing_count), int(target_holdings), int(used_20_slots))

        st.subheader("결과")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("운영모드", result["운영모드"])
        c2.metric("장부자산", fmt_won(result["장부자산"]))
        c3.metric("신규매수 가능", f"{result['신규매수가능개수']}개")
        c4.metric("회수필요", f"{result['회수필요종목수']}개")

        st.write("현재 단계:", result["단계"])
        st.write("기본매수금액:", fmt_won(result["기본매수금액"]), "/ 허용상한:", fmt_won(result["허용상한"]))
        st.write("목표종목수:", result["목표종목수"], "/ 최대종목수:", result["최대종목수"])
        st.write("액티브종목수:", result["액티브종목수"], "/ 요양원종목수:", result["요양원종목수"])

        if result["판단이유"]:
            st.warning("판단이유: " + " / ".join(result["판단이유"]))
        else:
            st.info("특이사항 없음")

        if result["운영모드"] in ["강한 회수모드", "회수모드"]:
            st.error("신규매수 금지. 익절/본전/요양원 차수 매도 후 재매수하지 말고 예수금 회복.")
        elif result["운영모드"] == "제한매수모드":
            st.warning(f"신규매수 최대 {result['신규매수가능개수']}개. TOP50 상위권만 제한 진입.")
        else:
            st.success(f"정상운용 가능. 신규매수 최대 {result['신규매수가능개수']}개.")

# =====================================================
# 3. TOP50
# =====================================================

elif menu == "3. TOP50":
    st.header("3. TOP50")
    st.caption(f"TOP50 엔진: {APP_VERSION}")
    st.caption("FDR로 계산하되, 2026-06-12 Colab 원본 후보 190개를 먼저 포함하고 Colab식 점수 구조로 계산하는 v9입니다.")

    nursing_df = load_nursing_df()
    auto_nursing_count = int((nursing_df["상태"] == "요양원").sum()) if len(nursing_df) else 0

    col1, col2, col3 = st.columns(3)
    with col1:
        cash_text = st.text_input("예수금", value="849만", key="top_cash")
    with col2:
        cost_text = st.text_input("매입금액", value="7607만", key="top_cost")
    with col3:
        unreal_text = st.text_input("평가손익", value="-915만", key="top_unreal")

    col4, col5, col6, col7, col8 = st.columns(5)
    with col4:
        total_holdings = st.number_input("총 보유종목수", min_value=0, value=126, step=1, key="top_total")
    with col5:
        nursing_count = st.number_input("요양원 종목수", min_value=0, value=auto_nursing_count, step=1, key="top_nursing")
    with col6:
        target_holdings = st.number_input("목표종목수 0이면 자동", min_value=0, value=0, step=1, key="top_target")
    with col7:
        used_20_slots = st.number_input("20만원 슬롯 사용개수", min_value=0, value=0, step=1, key="top_slot")
    with col8:
        max_codes = st.number_input("계산 종목수", min_value=50, max_value=700, value=300, step=50)

    st.info("v9는 12일 Colab 원본 후보 190개를 먼저 계산하고, 나머지는 FDR 거래대금/거래량 후보로 채웁니다. 처음엔 300개, 괜찮으면 500~700으로 올리세요.")

    if st.button("TOP50 생성", type="primary"):
        cash = parse_won(cash_text)
        cost = parse_won(cost_text)
        unrealized = parse_won(unreal_text)
        op = decide_operation(cash, cost, unrealized, int(total_holdings), int(nursing_count), int(target_holdings), int(used_20_slots))

        target_amount = op["기본매수금액"]
        price_limit = op["허용상한"]
        new_buy_limit = op["신규매수가능개수"]
        mode_name = op["운영모드"]

        exclude_codes = get_nursing_exclude_codes()
        asof_date = find_valid_krx_date()
        regime = ms_regime_asof_from_etf(asof_date)
        original_new_buy_limit = new_buy_limit
        new_buy_limit, regime_buy_comment = adjust_new_buy_by_regime(new_buy_limit, regime)

        st.write("기준일:", asof_date)
        st.write("장세:", regime)
        st.write("운영모드:", mode_name)
        st.write("신규매수:", original_new_buy_limit, "→", new_buy_limit, "/", regime_buy_comment)
        st.write("요양원/재진입금지 제외 종목수:", len(exclude_codes))

        universe, universe_diag = build_universe_fdr(price_limit, int(max_codes))
        codes = list(universe.keys())
        st.write("유니버스 진단:", universe_diag)
        st.write("계산 대상 종목수:", len(codes))

        data_start = (pd.to_datetime(asof_date) - pd.DateOffset(days=1400)).strftime("%Y%m%d")
        rows = []
        relaxed_rows = []
        diag = {
            "요양원제외": 0,
            "가격데이터없음": 0,
            "지표계산실패": 0,
            "엄격점수탈락": 0,
            "엄격수량탈락": 0,
            "엄격후보통과": 0,
            "완화후보통과": 0,
            "예외": 0,
        }

        prog = st.progress(0)
        status_box = st.empty()

        for idx, code in enumerate(codes, 1):
            code = str(code).zfill(6)
            if code in exclude_codes:
                diag["요양원제외"] += 1
                prog.progress(idx / max(len(codes), 1))
                continue
            name = universe.get(code, "")
            status_box.text(f"계산 중: {idx}/{len(codes)} {name}")
            try:
                raw_df = get_ohlcv_fdr_cached(code, data_start, asof_date)
                if raw_df is None or len(raw_df) == 0:
                    diag["가격데이터없음"] += 1
                    prog.progress(idx / max(len(codes), 1))
                    continue
                try:
                    df = ms_prepare_indicator_df(raw_df)
                except Exception:
                    diag["지표계산실패"] += 1
                    prog.progress(idx / max(len(codes), 1))
                    continue

                info = liquid500_score_candidate(df, name, regime=regime, high_price_limit=price_limit)
                if info is not None:
                    price = info["현재가"]
                    shares, buy_amount, buy_status = calc_magic_buy_amount(price, target_amount)
                    if buy_status == "OK":
                        info["코드"] = code
                        info["그룹"] = COLAB12_GROUP_BY_CODE.get(code, infer_group_by_name(name))
                        info["매수상태"] = "OK"
                        info["추천수량"] = shares
                        info["실제매수금액"] = buy_amount
                        info["목표매수금액"] = target_amount
                        info["허용상한"] = price_limit
                        info["장세"] = regime
                        info["운영모드"] = mode_name
                        info["장세매수코멘트"] = regime_buy_comment
                        rows.append(info)
                        diag["엄격후보통과"] += 1
                    else:
                        diag["엄격수량탈락"] += 1
                else:
                    diag["엄격점수탈락"] += 1
                    relaxed = relaxed_score_candidate(df, name, regime=regime, high_price_limit=price_limit)
                    if relaxed is not None:
                        price = relaxed["현재가"]
                        shares, buy_amount, buy_status = calc_magic_buy_amount(price, target_amount)
                        if buy_status == "OK":
                            relaxed["코드"] = code
                            relaxed["그룹"] = COLAB12_GROUP_BY_CODE.get(code, infer_group_by_name(name))
                            relaxed["매수상태"] = "OK"
                            relaxed["추천수량"] = shares
                            relaxed["실제매수금액"] = buy_amount
                            relaxed["목표매수금액"] = target_amount
                            relaxed["허용상한"] = price_limit
                            relaxed["장세"] = regime
                            relaxed["운영모드"] = mode_name
                            relaxed["장세매수코멘트"] = "완화후보"
                            relaxed_rows.append(relaxed)
                            diag["완화후보통과"] += 1
            except Exception:
                diag["예외"] += 1
            prog.progress(idx / max(len(codes), 1))
            time.sleep(0.02)

        status_box.empty()
        st.write("탈락 진단:", diag)
        st.write("엄격 후보 수:", len(rows))
        st.write("완화 후보 수:", len(relaxed_rows))

        use_relaxed = False
        if len(rows) > 0:
            result_df = pd.DataFrame(rows)
        elif len(relaxed_rows) > 0:
            result_df = pd.DataFrame(relaxed_rows)
            use_relaxed = True
            st.warning("엄격 후보가 0개라서 완화 후보를 표시합니다.")
        else:
            st.error("후보 없음. 위 진단에서 listing_rows/가격데이터없음 숫자를 확인해야 합니다.")
            st.stop()

        result_df = result_df.sort_values(["점수", "거래대금점수", "모멘텀점수", "회전점수", "기술점수"], ascending=False).reset_index(drop=True)
        result_df["순위"] = np.arange(1, len(result_df) + 1)

        if use_relaxed:
            result_df["오늘매수"] = "완화후보"
        elif new_buy_limit <= 0:
            result_df["오늘매수"] = "참고만"
        else:
            result_df["오늘매수"] = np.where(result_df["순위"] <= new_buy_limit, "매수가능", "대기")

        for c in TOP50_COLUMNS:
            if c not in result_df.columns:
                result_df[c] = ""

        top50 = result_df[TOP50_COLUMNS].head(50).copy()
        save_top50_df(top50)
        st.success("TOP50 생성 완료. Google Sheets의 TOP50 탭에도 저장했습니다.")
        if new_buy_limit <= 0 and not use_relaxed:
            st.warning("현재 신규매수 0개. 아래 후보는 참고용입니다.")
        if use_relaxed:
            st.warning("완화후보는 필터를 낮춘 참고용입니다. 실제 매수는 차트/보유 여부 확인 후 판단.")
        st.dataframe(top50, use_container_width=True)
        st.download_button("TOP50 CSV 다운로드", data=top50.to_csv(index=False).encode("utf-8-sig"), file_name=f"magic_split_top50_{asof_date}.csv", mime="text/csv")

# =====================================================
# 4. 도움말
# =====================================================

else:
    st.header("4. 도움말")
    st.markdown(f"""
### 버전

`{APP_VERSION}`

### 이번 버전 핵심

- Colab 없이 Streamlit 안에서 TOP50을 계산합니다.
- pykrx가 아니라 `FinanceDataReader`를 씁니다.
- 2026-06-12 Colab 원본 후보 190개를 먼저 계산 대상에 포함합니다.
- 점수 구조는 12일 Colab 파일의 104점대 방식에 맞췄습니다.
- 포함된 후보도 현재 FDR 데이터로 다시 점수 계산하므로, 무조건 고정 순위는 아닙니다.

### 사용 순서

1. 요양원 메뉴에서 요양원 등록/졸업 관리
2. 운영판단기에서 오늘 모드 확인
3. TOP50에서 후보 출력

### 주의

무료 Streamlit 서버에서는 700개 계산이 오래 걸릴 수 있습니다. 처음에는 300개로 테스트하세요.
""")
