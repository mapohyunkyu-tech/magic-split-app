# =====================================================
# 매직스플릿 Streamlit 안정형 앱
# 저장소: Google Sheets
# 메뉴: 1. 요양원 2. 운영판단기 3. TOP50
# =====================================================

import re
import time
from datetime import datetime

import numpy as np
import pandas as pd
import streamlit as st

from google.oauth2.service_account import Credentials
import gspread
from pykrx import stock

# =====================================================
# 기본 설정
# =====================================================

st.set_page_config(
    page_title="매직스플릿 관리기",
    page_icon="📈",
    layout="wide"
)


APP_VERSION = "v5_UNIVERSE_FALLBACK_20260614"

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
    "거래대금60억", "눌림률", "20일수익률", "60일수익률", "회전점수",
    "장세", "운영모드", "장세매수코멘트"
]

NAME_ALIAS = {
    "금호석유화학": "금호석유",
    "금호석화": "금호석유",
}

# 이름으로 안 잡히는 종목은 여기에 수동 등록
MANUAL_CODE_MAP = {
    "성광벤드": ("014620", "성광벤드"),
    "성광벤드 014620": ("014620", "성광벤드"),
    "태광": ("023160", "태광"),
    "태광 023160": ("023160", "태광"),
}

# TOP50 유니버스에 강제로 포함하고 싶은 종목
FORCE_UNIVERSE = {
    "014620": "성광벤드",
    "023160": "태광",
}

# =====================================================
# Streamlit / Google Sheets 연결
# =====================================================

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


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
private_key = """-----BEGIN PRIVATE KEY-----\\n...\\n-----END PRIVATE KEY-----\\n"""
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

    # Streamlit Secrets는 AttrDict 형태라 Google 인증 함수가 바로 못 읽는 경우가 있어
    # 일반 dict로 바꾸고, private_key의 \n 줄바꿈을 실제 줄바꿈으로 보정한다.
    service_account_info = dict(st.secrets["gcp_service_account"])

    private_key = str(service_account_info.get("private_key", ""))

    # 실수로 JSON의 따옴표까지 같이 붙여넣은 경우 제거
    private_key = private_key.strip()
    if (private_key.startswith('"') and private_key.endswith('"')) or (private_key.startswith("'") and private_key.endswith("'")):
        private_key = private_key[1:-1]

    # JSON에서 온 \n을 실제 줄바꿈으로 변환
    private_key = private_key.replace("\\n", "\n")
    private_key = private_key.replace("\r\n", "\n")
    private_key = private_key.strip()

    service_account_info["private_key"] = private_key

    credentials = Credentials.from_service_account_info(
        service_account_info,
        scopes=SCOPES
    )
    return gspread.authorize(credentials)


@st.cache_resource(show_spinner=False)
def get_spreadsheet():
    client = get_gspread_client()
    spreadsheet_id = st.secrets["spreadsheet_id"]
    return client.open_by_key(spreadsheet_id)


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
            # 기존 데이터 보존하면서 누락 헤더만 맞춤
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
    s = str(x).strip()
    s = s.replace(",", "").replace("원", "").replace(" ", "")

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


@st.cache_data(ttl=60 * 60 * 6, show_spinner=False)
def find_valid_krx_date(end_date=None, max_back=30):
    """
    실제 OHLCV 거래대금이 잡히는 최근 거래일을 찾는다.
    주말/휴일에는 ticker list만으로는 날짜가 유효해 보일 수 있어서
    get_market_ohlcv_by_ticker의 거래대금 합계로 검증한다.
    """
    if end_date is None:
        end_date = datetime.today().strftime("%Y%m%d")

    d = pd.to_datetime(str(end_date))

    for _ in range(max_back):
        ds = d.strftime("%Y%m%d")
        try:
            snap = stock.get_market_ohlcv_by_ticker(ds, market="KOSPI")
            if snap is not None and len(snap) > 100:
                amount_sum = 0
                if "거래대금" in snap.columns:
                    amount_sum = pd.to_numeric(snap["거래대금"], errors="coerce").fillna(0).sum()
                if amount_sum > 0:
                    return ds
        except Exception:
            pass

        try:
            snap = stock.get_market_ohlcv_by_ticker(ds, market="KOSDAQ")
            if snap is not None and len(snap) > 100:
                amount_sum = 0
                if "거래대금" in snap.columns:
                    amount_sum = pd.to_numeric(snap["거래대금"], errors="coerce").fillna(0).sum()
                if amount_sum > 0:
                    return ds
        except Exception:
            pass

        d = d - pd.Timedelta(days=1)

    return (pd.to_datetime(str(end_date)) - pd.Timedelta(days=1)).strftime("%Y%m%d")


@st.cache_data(ttl=60 * 60 * 24, show_spinner=False)
def load_krx_master(asof_date):
    rows = []
    for market in ["KOSPI", "KOSDAQ"]:
        try:
            tickers = stock.get_market_ticker_list(asof_date, market=market)
            for code in tickers:
                name = stock.get_market_ticker_name(code)
                rows.append({
                    "Code": str(code).zfill(6),
                    "Name": str(name),
                    "Market": market
                })
        except Exception:
            pass
    krx = pd.DataFrame(rows)
    if len(krx) == 0:
        return pd.DataFrame(columns=["Code", "Name", "Market"])
    return krx.drop_duplicates(subset=["Code"], keep="first").reset_index(drop=True)


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
        return {
            "단계": "15만원 / 120종목 구간",
            "기본매수금액": 150000,
            "목표종목수": 120,
            "최대종목수": 120,
            "20만원슬롯한도": 0
        }
    if book_asset < 120_000_000:
        return {
            "단계": "15만원 / 120~150종목 확장 구간",
            "기본매수금액": 150000,
            "목표종목수": 140,
            "최대종목수": 150,
            "20만원슬롯한도": 10
        }
    if book_asset < 150_000_000:
        return {
            "단계": "15만원 기본 + 20만원 슬롯 확대 구간",
            "기본매수금액": 150000,
            "목표종목수": 160,
            "최대종목수": 170,
            "20만원슬롯한도": 40
        }
    if book_asset < 200_000_000:
        return {
            "단계": "20만원 기본 검토 구간",
            "기본매수금액": 200000,
            "목표종목수": 180,
            "최대종목수": 200,
            "20만원슬롯한도": 999
        }
    if book_asset < 300_000_000:
        return {
            "단계": "25만원 기본 검토 구간",
            "기본매수금액": 250000,
            "목표종목수": 210,
            "최대종목수": 240,
            "20만원슬롯한도": 999
        }
    return {
        "단계": "30만원 이상 금액확대 구간",
        "기본매수금액": 300000,
        "목표종목수": 230,
        "최대종목수": 280,
        "20만원슬롯한도": 999
    }


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
# 주가 / 점수 / TOP50
# =====================================================


def ms_prepare_indicator_df(raw_df):
    df = raw_df.copy()
    rename_map = {
        "시가": "open", "고가": "high", "저가": "low", "종가": "close",
        "거래량": "volume", "거래대금": "amount"
    }
    df = df.rename(columns=rename_map)
    for c in ["open", "high", "low", "close", "volume", "amount"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
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
def get_ohlcv_by_date_cached(start_date, end_date, code):
    try:
        df = stock.get_market_ohlcv_by_date(start_date, end_date, code)
        return df.copy()
    except Exception:
        return pd.DataFrame()


def ms_regime_asof_from_etf(asof_date):
    etf_code = "069500"
    start = (pd.to_datetime(asof_date) - pd.DateOffset(days=300)).strftime("%Y%m%d")
    try:
        raw = get_ohlcv_by_date_cached(start, asof_date, etf_code)
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


def liquid500_score_candidate(df, name, regime="장세불명", high_price_limit=160000):
    if df is None or len(df) < 160:
        return None
    if liquid500_excluded(name):
        return None
    clean = df.dropna()
    if len(clean) < 120:
        return None
    last = clean.iloc[-1]
    price = float(last["close"])
    if price <= 0 or price > high_price_limit:
        return None
    amount60 = float(last.get("amount_ma60", 0))
    amount20 = float(last.get("amount_ma20", 0))
    if amount60 < 300_000_000:
        return None

    ret20 = float(last.get("ret20", 0))
    ret60 = float(last.get("ret60", 0))
    ret120 = float(last.get("ret120", 0))
    pullback = float(last.get("pullback120", 0))
    close = float(last["close"])
    ma20 = float(last.get("ma20", np.nan))
    ma60 = float(last.get("ma60", np.nan))
    ma120 = float(last.get("ma120", np.nan))

    trading_score = min(amount60 / 10_000_000_000 * 25, 25)

    temp = df.copy()
    temp["r20"] = temp["close"].pct_change(20) * 100
    recent = temp.tail(750)
    rotate_count = int((recent["r20"] >= 10).sum())
    rotate_score = min(rotate_count / 25 * 25, 25)

    tech_score = 0
    if close > ma20:
        tech_score += 5
    if close > ma60:
        tech_score += 7
    if close > ma120:
        tech_score += 7
    if ret20 > 0:
        tech_score += 3
    if ret60 > 0:
        tech_score += 3
    tech_score = min(tech_score, 25)

    if -18 <= pullback <= -3:
        pullback_score = 15
    elif -25 <= pullback < -18:
        pullback_score = 10
    elif -3 < pullback <= 0:
        pullback_score = 8
    elif pullback < -25:
        pullback_score = 4
    else:
        pullback_score = 5

    if "상승" in str(regime):
        regime_score = 8
    elif "폭등" in str(regime):
        regime_score = 6
    elif "횡보" in str(regime):
        regime_score = 7
    elif "약세" in str(regime):
        regime_score = 4
    elif "하락" in str(regime):
        regime_score = 2
    else:
        regime_score = 5

    total_score = trading_score + rotate_score + tech_score + pullback_score + regime_score
    if total_score >= 85:
        grade = "A"
    elif total_score >= 70:
        grade = "B"
    elif total_score >= 60:
        grade = "C"
    else:
        grade = "D"

    return {
        "종목": name,
        "등급": grade,
        "점수": round(total_score, 2),
        "현재가": int(price),
        "거래대금60억": round(amount60 / 100_000_000, 1),
        "거래대금20억": round(amount20 / 100_000_000, 1),
        "회전점수": round(rotate_score, 2),
        "거래대금점수": round(trading_score, 2),
        "기술점수": round(tech_score, 2),
        "눌림점수": round(pullback_score, 2),
        "눌림률": round(pullback, 2),
        "20일수익률": round(ret20, 2),
        "60일수익률": round(ret60, 2),
        "120일수익률": round(ret120, 2)
    }


def relaxed_score_candidate(df, name, regime="장세불명", high_price_limit=160000):
    """
    엄격 필터에서 후보가 0개일 때 쓰는 완화 점수.
    Colab처럼 일단 TOP50이 보이게 만드는 안전장치.
    """
    try:
        if df is None or len(df) < 80:
            return None
        if liquid500_excluded(name):
            return None
        clean = df.dropna(subset=["close"]).copy()
        if len(clean) < 60:
            return None
        # 지표가 NaN이어도 마지막 유효값 기준으로 처리
        last = clean.iloc[-1]
        price = float(last.get("close", 0))
        if price <= 0 or price > high_price_limit:
            return None

        amount60 = float(last.get("amount_ma60", 0) or 0)
        amount20 = float(last.get("amount_ma20", 0) or 0)
        ret20 = float(last.get("ret20", 0) or 0)
        ret60 = float(last.get("ret60", 0) or 0)
        ret120 = float(last.get("ret120", 0) or 0)
        pullback = float(last.get("pullback120", 0) or 0)
        close = float(last.get("close", 0))
        ma20 = float(last.get("ma20", np.nan))
        ma60 = float(last.get("ma60", np.nan))
        ma120 = float(last.get("ma120", np.nan))

        trading_score = min(max(amount60, amount20) / 5_000_000_000 * 25, 25)

        temp = clean.copy()
        temp["r20"] = temp["close"].pct_change(20) * 100
        recent = temp.tail(750)
        rotate_count = int((recent["r20"] >= 8).sum()) if "r20" in recent.columns else 0
        rotate_score = min(rotate_count / 20 * 25, 25)

        tech_score = 0
        if np.isfinite(ma20) and close > ma20: tech_score += 6
        if np.isfinite(ma60) and close > ma60: tech_score += 7
        if np.isfinite(ma120) and close > ma120: tech_score += 7
        if ret20 > -3: tech_score += 3
        if ret60 > -5: tech_score += 2
        tech_score = min(tech_score, 25)

        if -25 <= pullback <= -2:
            pullback_score = 15
        elif -35 <= pullback < -25:
            pullback_score = 10
        elif -2 < pullback <= 5:
            pullback_score = 8
        else:
            pullback_score = 5

        if "상승" in str(regime): regime_score = 8
        elif "폭등" in str(regime): regime_score = 6
        elif "횡보" in str(regime): regime_score = 7
        elif "약세" in str(regime): regime_score = 4
        elif "하락" in str(regime): regime_score = 2
        else: regime_score = 5

        total_score = trading_score + rotate_score + tech_score + pullback_score + regime_score
        if total_score >= 85: grade = "A"
        elif total_score >= 70: grade = "B"
        elif total_score >= 60: grade = "C"
        else: grade = "D"

        return {
            "종목": name,
            "등급": grade,
            "점수": round(total_score, 2),
            "현재가": int(price),
            "거래대금60억": round(amount60 / 100_000_000, 1),
            "거래대금20억": round(amount20 / 100_000_000, 1),
            "회전점수": round(rotate_score, 2),
            "거래대금점수": round(trading_score, 2),
            "기술점수": round(tech_score, 2),
            "눌림점수": round(pullback_score, 2),
            "눌림률": round(pullback, 2),
            "20일수익률": round(ret20, 2),
            "60일수익률": round(ret60, 2),
            "120일수익률": round(ret120, 2)
        }
    except Exception:
        return None


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
def build_universe(asof_date, price_limit, max_codes):
    """TOP50 계산 대상 유니버스 생성.

    Streamlit 서버에서 pykrx의 get_market_ohlcv_by_ticker()가 빈 값으로
    떨어지는 경우가 있어, 1차 스냅샷 방식 실패 시 2차 티커 리스트 방식으로
    강제 유니버스를 만든다.
    """
    max_codes = int(max_codes)

    debug = {
        "KOSPI_rows": 0,
        "KOSDAQ_rows": 0,
        "merged_rows": 0,
        "price_filtered": 0,
        "amount_filtered": 0,
        "final_universe": 0,
        "fallback_used": False,
        "KOSPI_ticker_list": 0,
        "KOSDAQ_ticker_list": 0,
        "fallback_selected": 0,
    }

    rows = []

    # 1차: 시장 전체 스냅샷 방식
    for market in ["KOSPI", "KOSDAQ"]:
        try:
            snap = stock.get_market_ohlcv_by_ticker(asof_date, market=market)

            if snap is None or len(snap) == 0:
                continue

            snap = snap.reset_index()

            # pykrx 버전마다 첫 컬럼명이 티커/인덱스 등으로 달라질 수 있어 첫 컬럼을 Code로 통일
            first_col = snap.columns[0]
            snap = snap.rename(columns={first_col: "Code", "종가": "Close", "거래대금": "Amount"})

            if "Code" not in snap.columns or "Close" not in snap.columns:
                continue

            if "Amount" not in snap.columns:
                if "거래량" in snap.columns:
                    snap["Amount"] = pd.to_numeric(snap["Close"], errors="coerce") * pd.to_numeric(snap["거래량"], errors="coerce")
                else:
                    snap["Amount"] = 0

            snap["Code"] = snap["Code"].astype(str).str.zfill(6)
            snap["Name"] = snap["Code"].apply(lambda c: stock.get_market_ticker_name(c))
            snap["Market"] = market
            snap["Close"] = pd.to_numeric(snap["Close"], errors="coerce")
            snap["Amount"] = pd.to_numeric(snap["Amount"], errors="coerce").fillna(0)
            snap = snap.dropna(subset=["Close"])

            debug[f"{market}_rows"] = len(snap)
            rows.append(snap[["Code", "Name", "Market", "Close", "Amount"]])

        except Exception:
            pass

    universe = {}

    if len(rows) > 0:
        df = pd.concat(rows, ignore_index=True)
        debug["merged_rows"] = len(df)

        df = df[df["Close"] <= float(price_limit)].copy()
        debug["price_filtered"] = len(df)

        # 거래대금 필터는 후보가 너무 줄면 자동 완화
        filtered = df[df["Amount"] >= 300_000_000].copy()
        if len(filtered) < 80:
            filtered = df[df["Amount"] >= 100_000_000].copy()
        if len(filtered) < 80:
            filtered = df[df["Amount"] >= 50_000_000].copy()
        if len(filtered) < 80:
            filtered = df.copy()

        df = filtered
        debug["amount_filtered"] = len(df)

        df = df[~df["Name"].apply(liquid500_excluded)].copy()
        df = df.sort_values("Amount", ascending=False).head(max_codes).copy()

        universe = dict(zip(df["Code"], df["Name"]))

    # 2차 fallback: 스냅샷이 0개거나 결과가 너무 적으면 티커 리스트로 강제 생성
    if len(universe) < 50:
        debug["fallback_used"] = True
        universe = {}

        try:
            kospi_codes = stock.get_market_ticker_list(asof_date, market="KOSPI")
        except Exception:
            kospi_codes = []

        try:
            kosdaq_codes = stock.get_market_ticker_list(asof_date, market="KOSDAQ")
        except Exception:
            kosdaq_codes = []

        kospi_codes = [str(c).zfill(6) for c in kospi_codes]
        kosdaq_codes = [str(c).zfill(6) for c in kosdaq_codes]

        debug["KOSPI_ticker_list"] = len(kospi_codes)
        debug["KOSDAQ_ticker_list"] = len(kosdaq_codes)

        # 회전주는 KOSDAQ 쪽 비중이 커서 KOSDAQ 65%, KOSPI 35%로 구성
        kosdaq_quota = int(max_codes * 0.65)
        kospi_quota = max_codes - kosdaq_quota

        selected = kosdaq_codes[:kosdaq_quota] + kospi_codes[:kospi_quota]
        debug["fallback_selected"] = len(selected)

        for code in selected:
            try:
                name = stock.get_market_ticker_name(code)
            except Exception:
                name = code

            if liquid500_excluded(name):
                continue

            universe[str(code).zfill(6)] = name

    # 강제 포함 종목
    for code, name in FORCE_UNIVERSE.items():
        universe[str(code).zfill(6)] = name

    debug["final_universe"] = len(universe)

    return universe, debug

    df = pd.concat(rows, ignore_index=True)
    debug["merged_rows"] = len(df)

    # 1차: 매수 가능 가격대
    df = df[df["Close"] <= float(price_limit)].copy()
    debug["price_filtered"] = len(df)

    # 2차: 너무 빡세면 후보가 0이 되므로 거래대금 필터 완화
    amount_cut = 300_000_000
    filtered = df[df["Amount"] >= amount_cut].copy()
    if len(filtered) < 80:
        amount_cut = 100_000_000
        filtered = df[df["Amount"] >= amount_cut].copy()
    if len(filtered) < 80:
        filtered = df.copy()

    df = filtered
    debug["amount_filtered"] = len(df)

    df = df[~df["Name"].apply(liquid500_excluded)].copy()
    df = df.sort_values("Amount", ascending=False).head(int(max_codes)).copy()

    universe = dict(zip(df["Code"], df["Name"]))
    for code, name in FORCE_UNIVERSE.items():
        universe[str(code).zfill(6)] = name

    debug["final_universe"] = len(universe)
    return universe, debug

# =====================================================
# 화면
# =====================================================

st.title("📈 매직스플릿 관리기 안정형")
st.caption(APP_VERSION)
st.caption("요양원 목록은 Google Sheets에 저장됩니다. 서버가 재시작돼도 목록은 유지됩니다.")

# 연결 상태 확인
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

    asof = find_valid_krx_date()
    krx = load_krx_master(asof)

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
        st.download_button(
            "요양원 목록 CSV 다운로드",
            data=df.to_csv(index=False).encode("utf-8-sig"),
            file_name="magic_split_nursing_list.csv",
            mime="text/csv"
        )

    st.divider()
    st.subheader("요양원 추가")
    add_text = st.text_area("추가할 종목명", placeholder="예: 금호석유화학, 동진쎄미켐, 성광벤드 014620", height=100)
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
                    "코드": found["코드"],
                    "종목": found["종목"],
                    "입력명": found["입력명"],
                    "상태": "요양원",
                    "차수": 5,
                    "등록일": today_str(),
                    "졸업일": "",
                    "재진입금지해제일": "",
                    "메모": "자동 5차 요양원"
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
    grad_text = st.text_area("졸업 처리할 종목명", placeholder="예: 금호석유화학, 동진쎄미켐", height=80)
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
    st.caption(APP_VERSION)
    st.caption("요양원/졸업후재진입금지 종목은 Google Sheets에서 읽어 자동 제외합니다.")

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
        max_codes = st.number_input("계산 종목수", min_value=50, max_value=700, value=700, step=50)

    st.info("v5는 시장 스냅샷이 0개일 때 티커 리스트 fallback으로 유니버스를 강제 생성합니다. 엄격 후보가 0개면 완화 후보를 자동으로 보여줍니다.")

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

        universe, universe_debug = build_universe(asof_date, price_limit, int(max_codes))
        codes = list(universe.keys())

        st.write("유니버스 진단:", universe_debug)
        st.write("계산 대상 종목수:", len(codes))

        data_start = (pd.to_datetime(asof_date) - pd.DateOffset(days=1400)).strftime("%Y%m%d")
        rows = []
        relaxed_rows = []
        fail_counts = {"가격데이터없음": 0, "지표/점수탈락": 0, "수량계산탈락": 0, "예외": 0}
        prog = st.progress(0)
        status_box = st.empty()

        for idx, code in enumerate(codes, 1):
            code = str(code).zfill(6)
            if code in exclude_codes:
                continue
            name = universe.get(code, "")
            status_box.text(f"계산 중: {idx}/{len(codes)} {name}")
            raw_df = get_ohlcv_by_date_cached(data_start, asof_date, code)
            if raw_df is None or len(raw_df) == 0:
                fail_counts["가격데이터없음"] += 1
                prog.progress(idx / max(len(codes), 1))
                continue
            try:
                df = ms_prepare_indicator_df(raw_df)
                info = liquid500_score_candidate(df, name, regime=regime, high_price_limit=price_limit)
                if info is None:
                    fail_counts["지표/점수탈락"] += 1
                    # 엄격 필터 탈락이어도 완화 후보에는 보관
                    rinfo = relaxed_score_candidate(df, name, regime=regime, high_price_limit=price_limit)
                    if rinfo is not None:
                        rprice = rinfo["현재가"]
                        rshares, rbuy_amount, rbuy_status = calc_magic_buy_amount(rprice, target_amount)
                        if rbuy_status == "OK":
                            rinfo["코드"] = code
                            rinfo["추천수량"] = rshares
                            rinfo["실제매수금액"] = rbuy_amount
                            rinfo["목표매수금액"] = target_amount
                            rinfo["허용상한"] = price_limit
                            rinfo["장세"] = regime
                            rinfo["운영모드"] = mode_name
                            rinfo["장세매수코멘트"] = regime_buy_comment + " / 완화후보"
                            relaxed_rows.append(rinfo)
                    prog.progress(idx / max(len(codes), 1))
                    continue
                price = info["현재가"]
                shares, buy_amount, buy_status = calc_magic_buy_amount(price, target_amount)
                if buy_status != "OK":
                    fail_counts["수량계산탈락"] += 1
                    prog.progress(idx / max(len(codes), 1))
                    continue
                info["코드"] = code
                info["추천수량"] = shares
                info["실제매수금액"] = buy_amount
                info["목표매수금액"] = target_amount
                info["허용상한"] = price_limit
                info["장세"] = regime
                info["운영모드"] = mode_name
                info["장세매수코멘트"] = regime_buy_comment
                rows.append(info)
            except Exception:
                fail_counts["예외"] += 1
                pass
            prog.progress(idx / max(len(codes), 1))
            time.sleep(0.01)

        status_box.empty()

        st.write("탈락 진단:", fail_counts)
        st.write("엄격 후보 수:", len(rows))
        st.write("완화 후보 수:", len(relaxed_rows))

        if len(rows) == 0 and len(relaxed_rows) > 0:
            st.warning("엄격 필터 후보는 0개라서, 완화 후보 TOP50을 표시합니다.")
            rows = relaxed_rows

        if len(rows) == 0:
            st.error("후보 없음")
            st.info("여기까지 오면 가격데이터 자체가 안 들어온 가능성이 큽니다. 위의 유니버스 진단/탈락 진단 숫자를 확인하세요.")
        else:
            result_df = pd.DataFrame(rows)
            result_df = result_df.sort_values(["점수", "거래대금점수", "회전점수", "기술점수"], ascending=False).reset_index(drop=True)
            result_df["순위"] = np.arange(1, len(result_df) + 1)
            if new_buy_limit <= 0:
                result_df["오늘매수"] = "참고만"
            else:
                result_df["오늘매수"] = np.where(result_df["순위"] <= new_buy_limit, "매수가능", "대기")
            top50 = result_df[TOP50_COLUMNS].head(50).copy()
            save_top50_df(top50)
            st.success("TOP50 생성 완료. Google Sheets의 TOP50 탭에도 저장했습니다.")
            if new_buy_limit <= 0:
                st.warning("현재 신규매수 0개. 아래 후보는 참고용입니다.")
            st.dataframe(top50, use_container_width=True)
            st.download_button(
                "TOP50 CSV 다운로드",
                data=top50.to_csv(index=False).encode("utf-8-sig"),
                file_name=f"magic_split_top50_{asof_date}.csv",
                mime="text/csv"
            )

# =====================================================
# 4. 도움말
# =====================================================

else:
    st.header("4. 도움말")
    st.markdown("""
### 저장 구조

- 요양원 목록은 앱 서버가 아니라 **Google Sheets**에 저장됩니다.
- 서버가 재시작되거나 재배포돼도 요양원 목록은 유지됩니다.
- 삭제 기능은 일부러 넣지 않았습니다. 실수 방지를 위해 **졸업 처리 + 변경로그** 구조로 갑니다.

### 사용 순서

1. 요양원 메뉴에서 요양원 등록/졸업 관리
2. 운영판단기에서 오늘 모드 확인
3. TOP50에서 후보 출력

### 요양원 규칙

- 현재 요양원: TOP50에서 무조건 제외
- 졸업후재진입금지: 해제일 전까지 TOP50 제외
- 해제일 이후: 다시 점수 통과하면 TOP50에 등장 가능

### TOP50 계산이 느릴 때

무료 서버에서는 계산 종목수를 150~250으로 두고 테스트하세요.
캐시가 쌓이면 같은 날 재실행은 더 빨라집니다.
""")
