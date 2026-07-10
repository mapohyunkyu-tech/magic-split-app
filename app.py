# -*- coding: utf-8 -*-
"""
T100 70% 운용모드 전용 안정판 + 기존 Google Sheets 기록 복구
- 외부 시세 자동수집 없음
- 기존 Google Sheets에서 T100 기록 자동 탐색/복구
- 저장은 새 탭(T100_70_SIMPLE_HISTORY)에 우선 저장해 기존 원본 탭을 덮어쓰지 않음
"""
from __future__ import annotations

import io
from datetime import date
from typing import Optional, List, Dict, Any

import pandas as pd
import streamlit as st

st.set_page_config(page_title="T100 70% 운용모드", layout="wide")

HISTORY_COLUMNS = [
    "date", "state", "principal", "eval_amount", "prev_eval",
    "daily_return_pct", "rolling_5d_return_pct", "defense_signal", "memo"
]

RECOVERY_TABS_TO_TRY = [
    "T100_70_SIMPLE_HISTORY",
    "T100_70_HISTORY",
    "t100_hybrid_live_history",
    "T100_HYBRID_HISTORY",
    "Sheet1",
    "시트1",
]
SAVE_TAB = "T100_70_SIMPLE_HISTORY"

KNOWN_RECOVERY = pd.DataFrame([
    {
        "date": "2026-07-06",
        "state": "1순위 운용중",
        "principal": 18836850,
        "eval_amount": 18706710,
        "prev_eval": 18836850,
        "daily_return_pct": round((18706710 / 18836850 - 1) * 100, 4),
        "rolling_5d_return_pct": None,
        "defense_signal": "기록부족",
        "memo": "대화기록 복구값: TIGER 미국나스닥100 46주 + TIGER 미국S&P500 332주",
    }
])


def _num(x):
    if x is None:
        return None
    if isinstance(x, str):
        x = x.replace(",", "").replace("원", "").replace("%", "").strip()
        if x == "":
            return None
    return pd.to_numeric(x, errors="coerce")


def normalize_history(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=HISTORY_COLUMNS)
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]

    # v94 큰 앱의 한글 컬럼 + 이 안정판의 영문 컬럼 모두 허용
    rename_map = {
        "날짜": "date", "기준일": "date", "Date": "date", "DATE": "date",
        "상태": "state", "운용모드": "state", "권장모드": "state", "state": "state",
        "누적투입원금": "principal", "투입원금": "principal", "원금": "principal", "principal": "principal",
        "평가금액": "eval_amount", "오늘평가금액": "eval_amount", "당일평가금액": "eval_amount",
        "T100평가금액": "eval_amount", "eval_amount": "eval_amount",
        "이전평가금액": "prev_eval", "전일평가금액": "prev_eval", "판정기준금액": "prev_eval",
        "운용기준금액": "prev_eval", "prev_eval": "prev_eval",
        "일간수익률": "daily_return_pct", "1일변동률": "daily_return_pct", "daily_return_pct": "daily_return_pct",
        "5일수익률": "rolling_5d_return_pct", "5일누적변동률": "rolling_5d_return_pct",
        "rolling_5d_return_pct": "rolling_5d_return_pct",
        "방어신호": "defense_signal", "실전방어신호": "defense_signal", "원시방어신호": "defense_signal",
        "defense_signal": "defense_signal",
        "메모": "memo", "계좌예수금메모": "memo", "memo": "memo",
    }

    # 첫 번째 매칭만 선택되게 수동 구성
    out = pd.DataFrame()
    for target in HISTORY_COLUMNS:
        candidates = [c for c, t in rename_map.items() if t == target and c in df.columns]
        if target in df.columns and target not in candidates:
            candidates.insert(0, target)
        if candidates:
            # 중복된 의미 컬럼이 있으면 앞 컬럼 기준, 빈 값은 뒤 컬럼으로 보완
            s = df[candidates[0]]
            for c in candidates[1:]:
                s = s.where(~s.isna() & (s.astype(str).str.strip() != ""), df[c])
            out[target] = s
        else:
            out[target] = None

    out["date"] = pd.to_datetime(out["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    for c in ["principal", "eval_amount", "prev_eval", "daily_return_pct", "rolling_5d_return_pct"]:
        out[c] = out[c].apply(_num)
    for c in ["state", "defense_signal", "memo"]:
        out[c] = out[c].fillna("").astype(str)
    out = out.dropna(subset=["date"])
    out = out.sort_values("date").drop_duplicates(subset=["date"], keep="last").reset_index(drop=True)
    return out[HISTORY_COLUMNS]


def to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")


def fmt_money(x) -> str:
    try:
        if pd.isna(x):
            return "-"
        return f"{int(round(float(x))):,}원"
    except Exception:
        return "-"


def fmt_pct(x) -> str:
    try:
        if pd.isna(x):
            return "-"
        return f"{float(x):+.2f}%"
    except Exception:
        return "-"


def calc_5d_return(hist: pd.DataFrame, today_eval: float) -> Optional[float]:
    if hist is None or len(hist) < 4:
        return None
    base = pd.to_numeric(hist.iloc[-4]["eval_amount"], errors="coerce")
    if pd.isna(base) or base <= 0:
        return None
    return (today_eval / float(base) - 1) * 100


def decide_defense(daily: Optional[float], r5: Optional[float]) -> str:
    daily_hit = daily is not None and daily <= -5.0
    r5_hit = r5 is not None and r5 <= -6.0
    if daily_hit and r5_hit:
        return "방어: 하루 -5% + 5일 -6%"
    if daily_hit:
        return "방어: 하루 -5%"
    if r5_hit:
        return "방어: 5일 -6%"
    if r5 is None:
        return "정상/5일 기록부족"
    return "정상"


def get_gsheet_client():
    try:
        import gspread
        from google.oauth2.service_account import Credentials
    except Exception as e:
        return None, f"gspread/google-auth 설치 또는 import 실패: {e}"

    try:
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        sa = None
        if "gcp_service_account" in st.secrets:
            sa = dict(st.secrets["gcp_service_account"])
        elif "service_account" in st.secrets:
            sa = dict(st.secrets["service_account"])
        if not sa:
            return None, "Streamlit secrets에 gcp_service_account가 없습니다."
        creds = Credentials.from_service_account_info(sa, scopes=scopes)
        return gspread.authorize(creds), None
    except Exception as e:
        return None, f"Google 인증 실패: {e}"


def get_spreadsheet():
    try:
        spreadsheet_id = st.secrets.get("spreadsheet_id", "")
    except Exception:
        spreadsheet_id = ""
    if not spreadsheet_id:
        return None, "Streamlit secrets에 spreadsheet_id가 없습니다."
    gc, err = get_gsheet_client()
    if err:
        return None, err
    try:
        return gc.open_by_key(spreadsheet_id), None
    except Exception as e:
        return None, f"스프레드시트 열기 실패: {e}"


def list_worksheets() -> List[str]:
    sh, err = get_spreadsheet()
    if err:
        return []
    try:
        return [ws.title for ws in sh.worksheets()]
    except Exception:
        return []


def load_history_from_gsheet() -> tuple[pd.DataFrame, str]:
    sh, err = get_spreadsheet()
    if err:
        return pd.DataFrame(columns=HISTORY_COLUMNS), err
    tried = []
    worksheets = []
    try:
        worksheets = sh.worksheets()
    except Exception as e:
        return pd.DataFrame(columns=HISTORY_COLUMNS), f"워크시트 목록 읽기 실패: {e}"

    # 이름 우선, 그 다음 전체 탐색
    titles = [ws.title for ws in worksheets]
    ordered_titles = []
    for t in RECOVERY_TABS_TO_TRY:
        if t in titles and t not in ordered_titles:
            ordered_titles.append(t)
    for t in titles:
        if t not in ordered_titles:
            ordered_titles.append(t)

    for title in ordered_titles:
        tried.append(title)
        try:
            ws = sh.worksheet(title)
            values = ws.get_all_records()
            if not values:
                continue
            raw = pd.DataFrame(values)
            hist = normalize_history(raw)
            # 기준일/평가금액이 있으면 기록으로 인정
            if not hist.empty and hist["eval_amount"].notna().any():
                return hist, f"'{title}' 탭에서 {len(hist)}건 복구"
        except Exception:
            continue
    return pd.DataFrame(columns=HISTORY_COLUMNS), "기록 탭을 찾지 못했습니다. 확인한 탭: " + ", ".join(tried)


def save_history_to_gsheet(df: pd.DataFrame) -> tuple[bool, str]:
    sh, err = get_spreadsheet()
    if err:
        return False, err
    try:
        try:
            ws = sh.worksheet(SAVE_TAB)
        except Exception:
            ws = sh.add_worksheet(title=SAVE_TAB, rows="1000", cols="20")
        save_df = normalize_history(df).fillna("")
        values = [HISTORY_COLUMNS] + save_df.astype(str).values.tolist()
        ws.clear()
        ws.update(values, value_input_option="USER_ENTERED")
        return True, f"Google Sheets '{SAVE_TAB}' 탭에 {len(save_df)}건 저장"
    except Exception as e:
        return False, f"Google Sheets 저장 실패: {e}"


def parse_recommendation_csv(file) -> Optional[pd.DataFrame]:
    if file is None:
        return None
    try:
        df = pd.read_csv(file)
    except UnicodeDecodeError:
        file.seek(0)
        df = pd.read_csv(file, encoding="cp949")
    df = df.copy()
    colmap = {}
    for c in df.columns:
        lc = str(c).strip().lower()
        if c in ["자산", "asset", "Asset"] or lc == "asset":
            colmap[c] = "asset"
        elif c in ["점수", "score", "Score"] or lc == "score":
            colmap[c] = "score"
        elif c in ["편입판정", "candidate", "판정"]:
            colmap[c] = "candidate"
        elif c in ["과열판정", "overheat"]:
            colmap[c] = "overheat"
        elif c in ["6개월%", "6m%", "ret_6m", "6개월"]:
            colmap[c] = "ret_6m"
        elif c in ["1개월%", "1m%", "ret_1m"]:
            colmap[c] = "ret_1m"
        elif c in ["3개월%", "3m%", "ret_3m"]:
            colmap[c] = "ret_3m"
        elif c in ["추세선", "ma"]:
            colmap[c] = "ma"
        elif c in ["종가", "close"]:
            colmap[c] = "close"
    df = df.rename(columns=colmap)
    if "asset" not in df.columns or "score" not in df.columns:
        st.warning("추천자산 CSV에는 최소한 '자산'과 '점수' 컬럼이 있어야 합니다.")
        return None
    for c in ["score", "ret_6m", "ret_1m", "ret_3m"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    if "candidate" not in df.columns:
        df["candidate"] = "편입후보"
    if "overheat" not in df.columns:
        df["overheat"] = "정상"
    if "ret_6m" not in df.columns:
        df["ret_6m"] = pd.NA
    return df


if "history" not in st.session_state:
    st.session_state.history = pd.DataFrame(columns=HISTORY_COLUMNS)

st.title("T100 70% 운용모드 전용 안정판 + Google Sheets 복구")
st.caption("원래 쓰던 Google Sheet가 있으면 읽어서 복구하고, 새 탭 T100_70_SIMPLE_HISTORY에 저장합니다.")

with st.sidebar:
    st.header("기록 복구/저장")
    st.write("Google Sheets 상태")
    try:
        has_sheet_secret = bool(st.secrets.get("spreadsheet_id", ""))
        has_sa_secret = ("gcp_service_account" in st.secrets) or ("service_account" in st.secrets)
    except Exception:
        has_sheet_secret = False
        has_sa_secret = False
    st.caption(f"spreadsheet_id: {'있음' if has_sheet_secret else '없음'} / service_account: {'있음' if has_sa_secret else '없음'}")

    if st.button("기존 Google Sheet에서 기록 불러오기"):
        hist, msg = load_history_from_gsheet()
        if hist.empty:
            st.error(msg)
        else:
            st.session_state.history = hist
            st.success(msg)

    if st.button("현재 기록을 Google Sheet에 저장"):
        ok, msg = save_history_to_gsheet(st.session_state.history)
        if ok:
            st.success(msg)
        else:
            st.error(msg)

    uploaded_history = st.file_uploader("운용기록 CSV 불러오기", type=["csv"], key="history_upload")
    if uploaded_history is not None:
        try:
            loaded = pd.read_csv(uploaded_history)
        except UnicodeDecodeError:
            uploaded_history.seek(0)
            loaded = pd.read_csv(uploaded_history, encoding="cp949")
        st.session_state.history = normalize_history(loaded)
        st.success(f"CSV 기록 {len(st.session_state.history)}건을 불러왔습니다.")

    if st.button("대화기록 기준 2026-07-06 복구값 넣기"):
        st.session_state.history = normalize_history(pd.concat([st.session_state.history, KNOWN_RECOVERY], ignore_index=True))
        st.success("복구값을 넣었습니다.")

    if st.button("현재 세션 기록 전체 삭제"):
        st.session_state.history = pd.DataFrame(columns=HISTORY_COLUMNS)
        st.warning("현재 세션 기록을 비웠습니다.")

    st.download_button(
        "운용기록 CSV 다운로드",
        data=to_csv_bytes(normalize_history(st.session_state.history)),
        file_name="t100_70_live_history.csv",
        mime="text/csv",
        disabled=normalize_history(st.session_state.history).empty,
    )

hist = normalize_history(st.session_state.history)
st.session_state.history = hist

st.subheader("1. 현재 운용기록")
if hist.empty:
    st.info("저장된 기록이 없습니다. 왼쪽에서 Google Sheet/CSV를 불러오거나 오늘 기록을 저장하세요.")
else:
    last = hist.iloc[-1]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("최신 기준일", str(last["date"]))
    c2.metric("누적 투입원금", fmt_money(last["principal"]))
    c3.metric("평가금액", fmt_money(last["eval_amount"]))
    principal_val = float(last["principal"] or 0)
    eval_val = float(last["eval_amount"] or 0)
    pnl = eval_val - principal_val
    c4.metric("단순 손익", fmt_money(pnl), fmt_pct((pnl / principal_val) * 100) if principal_val > 0 else None)
    st.dataframe(hist.tail(30), width="stretch", hide_index=True)

st.subheader("2. 오늘 평가금액 저장")
colA, colB = st.columns(2)
with colA:
    today = st.date_input("기준일", value=date.today())
    state = st.selectbox("현재 상태", ["1순위 운용중", "방어모드", "6310", "대기", "기타"], index=0)
    default_principal = int(hist.iloc[-1]["principal"]) if not hist.empty and pd.notna(hist.iloc[-1]["principal"]) else 18836850
    principal = st.number_input("누적 투입원금", min_value=0, step=10000, value=default_principal)
with colB:
    default_prev = int(hist.iloc[-1]["eval_amount"]) if not hist.empty and pd.notna(hist.iloc[-1]["eval_amount"]) else principal
    prev_eval = st.number_input("판정기준 평가금액 / 전일 평가금액", min_value=0, step=10000, value=default_prev)
    today_eval = st.number_input("오늘 평가금액", min_value=0, step=10000, value=default_prev)
    memo = st.text_input("메모", value="")

daily_ret = (today_eval / prev_eval - 1) * 100 if prev_eval > 0 else None
r5_ret = calc_5d_return(hist, today_eval)
defense = decide_defense(daily_ret, r5_ret)

m1, m2, m3 = st.columns(3)
m1.metric("1일 변동률", fmt_pct(daily_ret))
m2.metric("5일 누적", fmt_pct(r5_ret) if r5_ret is not None else "기록부족")
m3.metric("방어판정", defense)

if today_eval > 0:
    if defense.startswith("방어"):
        st.error(f"방어 신호: 목표는 T100 70% / 현금 30%입니다. 현재 평가금액 기준 T100 목표 {fmt_money(today_eval * 0.70)}, 현금 목표 {fmt_money(today_eval * 0.30)}")
    else:
        st.success("방어 신호 없음: 기존 운용 유지")

if st.button("오늘 기록 저장", type="primary"):
    new_row = pd.DataFrame([{
        "date": today.strftime("%Y-%m-%d"),
        "state": state,
        "principal": principal,
        "eval_amount": today_eval,
        "prev_eval": prev_eval,
        "daily_return_pct": round(daily_ret, 4) if daily_ret is not None else None,
        "rolling_5d_return_pct": round(r5_ret, 4) if r5_ret is not None else None,
        "defense_signal": defense,
        "memo": memo,
    }])
    st.session_state.history = normalize_history(pd.concat([hist, new_row], ignore_index=True))
    st.success("저장했습니다. Google Sheets 저장 버튼 또는 CSV 다운로드로 백업하세요.")
    st.rerun()

st.subheader("3. 추천자산 CSV 확인")
st.caption("기존 70% 과열회피 앱에서 내보낸 자산 점수 CSV가 있으면 업로드하세요. 예: 자산, 편입판정, 과열판정, 점수, 6개월%")
rec_file = st.file_uploader("추천자산 CSV 업로드", type=["csv"], key="rec_upload")
rec = parse_recommendation_csv(rec_file)
if rec is not None:
    def is_ok(row):
        cand = str(row.get("candidate", ""))
        over = str(row.get("overheat", ""))
        score = row.get("score", pd.NA)
        r6 = row.get("ret_6m", pd.NA)
        if "탈락" in cand:
            return False
        if "과열" in over and "정상" not in over:
            return False
        if pd.isna(score) or float(score) <= 0:
            return False
        if pd.notna(r6) and float(r6) >= 70:
            return False
        return True

    rec["후보사용"] = rec.apply(is_ok, axis=1)
    rec["과열근접"] = rec["ret_6m"].apply(lambda x: "경고" if pd.notna(x) and 65 <= float(x) < 70 else "")
    show_cols = [c for c in ["asset", "candidate", "overheat", "score", "ret_1m", "ret_3m", "ret_6m", "ma", "close", "후보사용", "과열근접"] if c in rec.columns]
    st.dataframe(rec[show_cols].sort_values("score", ascending=False), width="stretch", hide_index=True)
    top = rec[rec["후보사용"]].sort_values("score", ascending=False).head(2)
    if len(top) >= 2:
        assets = top["asset"].tolist()
        st.success("목표 상위 2개: " + " + ".join(map(str, assets)))
        warn = top[top["과열근접"] == "경고"]
        if not warn.empty:
            st.warning("과열근접 경고: " + ", ".join(warn["asset"].astype(str).tolist()) + " / 65~70%는 탈락이 아니라 경고만 표시")
    elif len(top) == 1:
        st.warning("후보가 1개뿐입니다: " + str(top.iloc[0]["asset"]))
    else:
        st.error("사용 가능한 후보가 없습니다.")

st.subheader("4. 50:50 리밸런싱 계산")
assets_text = st.text_input("목표자산 2개", value="KODEX200,NASDAQ100")
assets = [a.strip() for a in assets_text.split(",") if a.strip()]
if len(assets) != 2:
    st.info("목표자산 2개를 쉼표로 입력하세요. 예: KODEX200,NASDAQ100")
else:
    total_default = int(today_eval if today_eval else (hist.iloc[-1]["eval_amount"] if not hist.empty else 0))
    total_for_rebal = st.number_input("리밸런싱 기준 총 평가금액", min_value=0, step=10000, value=total_default)
    c1, c2 = st.columns(2)
    cur1 = c1.number_input(f"현재 {assets[0]} 평가금액", min_value=0, step=10000, value=0)
    cur2 = c2.number_input(f"현재 {assets[1]} 평가금액", min_value=0, step=10000, value=0)
    target_each = total_for_rebal / 2 if total_for_rebal else 0
    rb = pd.DataFrame([
        {"자산": assets[0], "현재": cur1, "목표": target_each, "매수/매도 필요": target_each - cur1},
        {"자산": assets[1], "현재": cur2, "목표": target_each, "매수/매도 필요": target_each - cur2},
    ])
    st.dataframe(rb.assign(**{
        "현재": rb["현재"].map(fmt_money),
        "목표": rb["목표"].map(fmt_money),
        "매수/매도 필요": rb["매수/매도 필요"].map(fmt_money),
    }), width="stretch", hide_index=True)

with st.expander("Google Sheets secrets 예시"):
    st.code('''
spreadsheet_id = "구글시트_ID"

[gcp_service_account]
type = "service_account"
project_id = "..."
private_key_id = "..."
private_key = "-----BEGIN PRIVATE KEY-----\\n...\\n-----END PRIVATE KEY-----\\n"
client_email = "서비스계정이메일@프로젝트.iam.gserviceaccount.com"
client_id = "..."
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "..."
universe_domain = "googleapis.com"
''')

st.caption("주의: Google Sheets 저장이 안 되면 CSV 다운로드로 백업하세요. 원본 시트 보호를 위해 저장은 T100_70_SIMPLE_HISTORY 새 탭에 합니다.")
