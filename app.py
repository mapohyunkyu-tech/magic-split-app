# -*- coding: utf-8 -*-
"""
매직스플릿 홀딩스캐너 백테스트 v1
- FinanceDataReader 기반 가격/거래량/차트 필터 백테스트
- 선택적으로 재무 CSV를 업로드하면 재무점수를 결합

주의: 이 앱은 '후보 압축/전략 검증'용입니다. 매수 추천/수익 보장 도구가 아닙니다.
"""

import io
import math
import re
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import streamlit as st

try:
    import FinanceDataReader as fdr
except Exception as e:  # pragma: no cover
    fdr = None
    FDR_IMPORT_ERROR = e
else:
    FDR_IMPORT_ERROR = None

APP_VERSION = "HOLDING_BACKTEST_V1_20260615"

st.set_page_config(page_title="홀딩스캐너 백테스트", layout="wide")
st.title("📊 홀딩스캐너 백테스트")
st.caption(APP_VERSION)

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

def clean_number(x, default=0.0):
    if x is None:
        return default
    if isinstance(x, (int, float, np.integer, np.floating)):
        if pd.isna(x):
            return default
        return float(x)
    s = str(x).strip().replace(",", "")
    if s in ("", "-", "None", "nan"):
        return default
    try:
        return float(s)
    except Exception:
        return default


def normalize_code(x: str) -> str:
    s = str(x).strip()
    s = re.sub(r"[^0-9]", "", s)
    if not s:
        return ""
    return s.zfill(6)[-6:]


@st.cache_data(ttl=60 * 60 * 12, show_spinner=False)
def get_krx_listing() -> pd.DataFrame:
    if fdr is None:
        raise RuntimeError(f"FinanceDataReader import 실패: {FDR_IMPORT_ERROR}")
    df = fdr.StockListing("KRX")
    cols = [c for c in ["Code", "Name", "Market", "Sector", "Industry"] if c in df.columns]
    df = df[cols].copy()
    df["Code"] = df["Code"].astype(str).str.zfill(6)
    df["Name"] = df["Name"].astype(str)
    return df.drop_duplicates("Code")


def resolve_symbols(raw_text: str, listing: pd.DataFrame, max_symbols: int) -> pd.DataFrame:
    """Parse manual ticker/name text into Code/Name rows."""
    lines = []
    for line in raw_text.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        # allow: 005930, 삼성전자, 005930 삼성전자
        token = s.split(",")[0].strip()
        if re.fullmatch(r"\d{4,6}", token):
            code = normalize_code(token)
            row = listing[listing["Code"] == code]
            name = row["Name"].iloc[0] if len(row) else s
            lines.append({"Code": code, "Name": name})
            continue
        m = re.match(r"^(\d{4,6})\s+(.+)$", s)
        if m:
            code = normalize_code(m.group(1))
            row = listing[listing["Code"] == code]
            name = row["Name"].iloc[0] if len(row) else m.group(2).strip()
            lines.append({"Code": code, "Name": name})
            continue
        # exact or contains name match
        exact = listing[listing["Name"] == s]
        if len(exact):
            r = exact.iloc[0]
            lines.append({"Code": r["Code"], "Name": r["Name"]})
        else:
            contains = listing[listing["Name"].str.contains(re.escape(s), na=False)]
            if len(contains):
                r = contains.iloc[0]
                lines.append({"Code": r["Code"], "Name": r["Name"]})
            else:
                # unknown name, still keep as Name; code missing will be dropped later
                lines.append({"Code": "", "Name": s})
    out = pd.DataFrame(lines).drop_duplicates()
    if len(out) > max_symbols:
        out = out.head(max_symbols)
    return out


def load_symbols_from_csv(upload, listing: pd.DataFrame, max_symbols: int) -> pd.DataFrame:
    raw = pd.read_csv(upload)
    df = raw.copy()
    col_code = None
    col_name = None
    for c in df.columns:
        lc = str(c).lower()
        if c in ["Code", "종목코드", "코드", "ticker", "Ticker"] or "code" in lc:
            col_code = c
        if c in ["Name", "종목명", "이름", "name", "Name"] or "name" in lc:
            col_name = c
    rows = []
    for _, r in df.iterrows():
        code = normalize_code(r[col_code]) if col_code else ""
        name = str(r[col_name]).strip() if col_name else ""
        if code:
            row = listing[listing["Code"] == code]
            if len(row):
                name = row["Name"].iloc[0]
        elif name:
            row = listing[listing["Name"] == name]
            if len(row):
                code = row["Code"].iloc[0]
        if code:
            rows.append({"Code": code, "Name": name or code})
    out = pd.DataFrame(rows).drop_duplicates()
    return out.head(max_symbols)


@st.cache_data(ttl=60 * 60 * 24, show_spinner=False)
def read_price(code: str, start: str, end: str) -> pd.DataFrame:
    if fdr is None:
        raise RuntimeError(f"FinanceDataReader import 실패: {FDR_IMPORT_ERROR}")
    df = fdr.DataReader(code, start, end)
    if df is None or len(df) == 0:
        return pd.DataFrame()
    df = df.copy()
    df.index = pd.to_datetime(df.index)
    # Normalize columns
    rename = {}
    for c in df.columns:
        lc = str(c).lower()
        if lc == "open": rename[c] = "Open"
        if lc == "high": rename[c] = "High"
        if lc == "low": rename[c] = "Low"
        if lc == "close": rename[c] = "Close"
        if lc == "volume": rename[c] = "Volume"
    df = df.rename(columns=rename)
    for c in ["Open", "High", "Low", "Close", "Volume"]:
        if c not in df.columns:
            df[c] = np.nan
    df = df[["Open", "High", "Low", "Close", "Volume"]].dropna(subset=["Close"])
    df = df.sort_index()
    return df


def nearest_on_or_before(df: pd.DataFrame, d: pd.Timestamp) -> Optional[pd.Timestamp]:
    ix = df.index[df.index <= d]
    if len(ix) == 0:
        return None
    return ix[-1]


def nearest_on_or_after(df: pd.DataFrame, d: pd.Timestamp) -> Optional[pd.Timestamp]:
    ix = df.index[df.index >= d]
    if len(ix) == 0:
        return None
    return ix[0]


def last_monthly_scan_dates(start: pd.Timestamp, end: pd.Timestamp) -> List[pd.Timestamp]:
    months = pd.date_range(start=start, end=end, freq="MS")
    return [pd.Timestamp(m) for m in months]


def pct(x):
    if pd.isna(x):
        return np.nan
    return round(float(x) * 100, 2)


def calc_features(df: pd.DataFrame, scan_date: pd.Timestamp) -> Optional[Dict]:
    idx = nearest_on_or_before(df, scan_date)
    if idx is None:
        return None
    hist = df.loc[:idx].copy()
    if len(hist) < 160:
        return None
    close = float(hist["Close"].iloc[-1])
    vol = float(hist["Volume"].iloc[-1]) if not pd.isna(hist["Volume"].iloc[-1]) else 0
    ma20 = hist["Close"].rolling(20).mean().iloc[-1]
    ma60 = hist["Close"].rolling(60).mean().iloc[-1]
    ma120 = hist["Close"].rolling(120).mean().iloc[-1]
    vol20 = hist["Volume"].rolling(20).mean().iloc[-1] if "Volume" in hist else np.nan
    high52 = hist["Close"].rolling(252).max().iloc[-1] if len(hist) >= 252 else hist["Close"].max()
    low120 = hist["Close"].rolling(120).min().iloc[-1]
    drawdown52 = (close / high52 - 1) if high52 and high52 > 0 else np.nan
    rebound_from_120_low = (close / low120 - 1) if low120 and low120 > 0 else np.nan

    # Base candle in last 30 trading days: large positive candle with volume surge.
    recent = hist.tail(35).copy()
    recent["ret"] = recent["Close"].pct_change()
    recent["vol_ma20"] = hist["Volume"].rolling(20).mean().loc[recent.index]
    base = recent[(recent["ret"] >= 0.05) & (recent["Volume"] >= recent["vol_ma20"] * 1.8)]
    has_base = len(base) > 0
    base_mid_ok = False
    base_days_ago = np.nan
    if has_base:
        bidx = base.index[-1]
        brow = recent.loc[bidx]
        base_mid = (float(brow["Open"]) + float(brow["Close"])) / 2
        base_mid_ok = close >= base_mid
        base_days_ago = int((recent.index[-1] - bidx).days)

    # Higher low approximation: latest 20d low > previous 20~80d low
    last20_low = hist["Close"].tail(20).min()
    prev60_low = hist["Close"].iloc[-80:-20].min() if len(hist) >= 100 else np.nan
    higher_low = bool(pd.notna(prev60_low) and last20_low > prev60_low * 0.98)

    # Pullback: above MA60/120, 5~15% off recent 60d high, not broken MA60 badly.
    high60 = hist["Close"].tail(60).max()
    pullback_from_60h = (close / high60 - 1) if high60 > 0 else np.nan
    pullback_ok = bool(
        pd.notna(ma60) and close >= ma60 * 0.97 and
        pd.notna(pullback_from_60h) and -0.18 <= pullback_from_60h <= -0.03
    )

    # Breakout: close near 60d high with volume expansion.
    breakout_ok = bool(close >= high60 * 0.98 and pd.notna(vol20) and vol20 > 0 and vol >= vol20 * 1.5)

    # Technical score 0~70
    tech = 0
    tech += 8 if close >= ma20 else 0
    tech += 8 if close >= ma60 else 0
    tech += 6 if close >= ma120 * 0.97 else 0
    tech += 8 if has_base and base_mid_ok else 0
    tech += 8 if pullback_ok else 0
    tech += 7 if breakout_ok else 0
    tech += 7 if higher_low else 0
    tech += 6 if pd.notna(drawdown52) and -0.55 <= drawdown52 <= -0.12 else 0
    tech += 6 if pd.notna(rebound_from_120_low) and 0.05 <= rebound_from_120_low <= 0.55 else 0
    tech += 6 if pd.notna(vol20) and vol20 > 0 and vol >= vol20 * 1.2 else 0

    # Liquidity/attention score 0~30, rank-like absolute in KRW using Close*Volume.
    amount = close * vol
    liq = 0
    if amount >= 20_000_000_000: liq = 30
    elif amount >= 10_000_000_000: liq = 25
    elif amount >= 5_000_000_000: liq = 20
    elif amount >= 2_000_000_000: liq = 15
    elif amount >= 1_000_000_000: liq = 10
    else: liq = 5

    technical_total = min(100, tech + liq)
    return {
        "scan_actual_date": idx,
        "close": close,
        "volume": vol,
        "amount": amount,
        "ma20": ma20,
        "ma60": ma60,
        "ma120": ma120,
        "drawdown52": drawdown52,
        "rebound120low": rebound_from_120_low,
        "base": has_base,
        "base_mid_ok": base_mid_ok,
        "base_days_ago": base_days_ago,
        "pullback": pullback_ok,
        "breakout": breakout_ok,
        "higher_low": higher_low,
        "technical_score": round(float(technical_total), 2),
    }


def calc_future_return(df: pd.DataFrame, entry_date: pd.Timestamp, hold_days: int) -> Tuple[float, float, Optional[pd.Timestamp]]:
    eidx = nearest_on_or_before(df, entry_date)
    if eidx is None:
        return np.nan, np.nan, None
    future_target = eidx + pd.Timedelta(days=hold_days)
    xidx = nearest_on_or_after(df, future_target)
    if xidx is None:
        return np.nan, np.nan, None
    entry = float(df.loc[eidx, "Close"])
    exitp = float(df.loc[xidx, "Close"])
    ret = exitp / entry - 1
    path = df.loc[eidx:xidx]["Close"]
    mdd = path.min() / entry - 1 if len(path) else np.nan
    return ret, mdd, xidx


def parse_finance_score(upload) -> pd.DataFrame:
    """Optional CSV score combiner.
    Supported columns:
    - Code/종목코드 and/or Name/종목명
    - 재무총점 or 재무점수, 저평가점수, 실적점수, 재무안정점수, 수급점수
    """
    if upload is None:
        return pd.DataFrame(columns=["Code", "finance_score"])
    df = pd.read_csv(upload)
    code_col = None
    name_col = None
    for c in df.columns:
        if c in ["Code", "코드", "종목코드", "ticker", "Ticker"]:
            code_col = c
        if c in ["Name", "종목명", "이름"]:
            name_col = c
    if code_col is None and name_col is None:
        return pd.DataFrame(columns=["Code", "finance_score"])

    rows = []
    score_cols = [c for c in df.columns if c in ["재무총점", "재무점수", "저평가점수", "실적점수", "재무안정점수", "수급점수", "가치점수"]]
    for _, r in df.iterrows():
        code = normalize_code(r[code_col]) if code_col else ""
        name = str(r[name_col]).strip() if name_col else ""
        if "재무총점" in df.columns:
            fs = clean_number(r["재무총점"], 0)
        elif "재무점수" in df.columns:
            fs = clean_number(r["재무점수"], 0)
        elif score_cols:
            vals = [clean_number(r[c], 0) for c in score_cols]
            fs = sum(vals)
        else:
            fs = 0
        fs = max(0, min(100, fs))
        rows.append({"Code": code, "Name": name, "finance_score": fs})
    return pd.DataFrame(rows).drop_duplicates("Code")


def run_backtest(
    symbols: pd.DataFrame,
    finance_scores: pd.DataFrame,
    start_date: date,
    end_date: date,
    hold_months: int,
    top_n: int,
    threshold: float,
    combine_mode: str,
    benchmark_code: str,
    max_symbols: int,
):
    start_ts = pd.Timestamp(start_date)
    end_ts = pd.Timestamp(end_date)
    # need warmup and forward period
    data_start = (start_ts - pd.Timedelta(days=450)).strftime("%Y-%m-%d")
    data_end = (end_ts + pd.Timedelta(days=hold_months * 35 + 20)).strftime("%Y-%m-%d")
    hold_days = int(hold_months * 30.5)

    symbols = symbols.head(max_symbols).copy()
    price_map: Dict[str, pd.DataFrame] = {}
    errors = []
    progress = st.progress(0, text="가격 데이터 다운로드 중...")
    for i, r in symbols.iterrows():
        code = str(r["Code"]).zfill(6)
        try:
            df = read_price(code, data_start, data_end)
            if len(df) >= 200:
                price_map[code] = df
            else:
                errors.append({"Code": code, "Name": r["Name"], "error": "가격데이터 부족"})
        except Exception as e:
            errors.append({"Code": code, "Name": r["Name"], "error": str(e)[:120]})
        progress.progress(min(1.0, (len(price_map) + len(errors)) / max(1, len(symbols))), text=f"가격 데이터 다운로드 중... {len(price_map)+len(errors)}/{len(symbols)}")
    progress.empty()

    bm = pd.DataFrame()
    try:
        bm = read_price(benchmark_code, data_start, data_end)
    except Exception:
        pass

    finance_scores = finance_scores.copy()
    if "Code" in finance_scores.columns:
        finance_scores["Code"] = finance_scores["Code"].astype(str).str.zfill(6)
    fs_map = {}
    if len(finance_scores):
        fs_map = dict(zip(finance_scores["Code"], finance_scores["finance_score"]))

    scan_dates = last_monthly_scan_dates(start_ts, end_ts)
    all_rows = []
    scan_progress = st.progress(0, text="월별 스캔/백테스트 중...")
    for si, sd in enumerate(scan_dates):
        candidates = []
        for _, sr in symbols.iterrows():
            code = str(sr["Code"]).zfill(6)
            name = str(sr["Name"])
            df = price_map.get(code)
            if df is None:
                continue
            feat = calc_features(df, sd)
            if feat is None:
                continue
            tech_score = feat["technical_score"]
            finance_score = fs_map.get(code, np.nan)
            if combine_mode == "기술/거래대금 전용":
                total = tech_score
            elif combine_mode == "재무CSV 60% + 기술 40%":
                if pd.isna(finance_score):
                    continue
                total = finance_score * 0.6 + tech_score * 0.4
            else:  # 재무CSV 50 + 기술 50
                if pd.isna(finance_score):
                    continue
                total = finance_score * 0.5 + tech_score * 0.5
            if total < threshold:
                continue
            fut_ret, mdd, exit_date = calc_future_return(df, feat["scan_actual_date"], hold_days)
            if pd.isna(fut_ret):
                continue
            bm_ret = np.nan
            if len(bm):
                bm_ret, _, _ = calc_future_return(bm, feat["scan_actual_date"], hold_days)
            candidates.append({
                "스캔월": sd.strftime("%Y-%m"),
                "스캔일": feat["scan_actual_date"].strftime("%Y-%m-%d"),
                "청산일": exit_date.strftime("%Y-%m-%d") if exit_date is not None else "",
                "종목코드": code,
                "종목명": name,
                "총점": round(float(total), 2),
                "기술점수": round(float(tech_score), 2),
                "재무점수": round(float(finance_score), 2) if not pd.isna(finance_score) else np.nan,
                "진입가": round(float(feat["close"]), 2),
                "거래대금": round(float(feat["amount"]), 0),
                "52주낙폭%": pct(feat["drawdown52"]),
                "120일저점반등%": pct(feat["rebound120low"]),
                "기준봉": "Y" if feat["base"] and feat["base_mid_ok"] else "",
                "눌림목": "Y" if feat["pullback"] else "",
                "돌파": "Y" if feat["breakout"] else "",
                "저점상향": "Y" if feat["higher_low"] else "",
                f"{hold_months}개월수익률%": pct(fut_ret),
                "최대하락률%": pct(mdd),
                "벤치마크수익률%": pct(bm_ret),
                "초과수익률%": pct(fut_ret - bm_ret) if not pd.isna(bm_ret) else np.nan,
                "성공_플러스": bool(fut_ret > 0),
                "성공_20퍼": bool(fut_ret >= 0.20),
                "성공_벤치초과": bool((fut_ret - bm_ret) > 0) if not pd.isna(bm_ret) else False,
            })
        if candidates:
            ranked = pd.DataFrame(candidates).sort_values("총점", ascending=False).head(top_n)
            all_rows.append(ranked)
        scan_progress.progress(min(1.0, (si + 1) / max(1, len(scan_dates))), text=f"월별 스캔/백테스트 중... {si+1}/{len(scan_dates)}")
    scan_progress.empty()

    result = pd.concat(all_rows, ignore_index=True) if all_rows else pd.DataFrame()
    errdf = pd.DataFrame(errors)
    return result, errdf


def summarize_result(result: pd.DataFrame, hold_months: int) -> Dict:
    if result.empty:
        return {}
    ret_col = f"{hold_months}개월수익률%"
    out = {
        "거래수": int(len(result)),
        "플러스승률%": round(float(result["성공_플러스"].mean() * 100), 2),
        "20%이상비율%": round(float(result["성공_20퍼"].mean() * 100), 2),
        "벤치초과비율%": round(float(result["성공_벤치초과"].mean() * 100), 2) if "성공_벤치초과" in result else np.nan,
        "평균수익률%": round(float(result[ret_col].mean()), 2),
        "중앙수익률%": round(float(result[ret_col].median()), 2),
        "평균초과수익률%": round(float(result["초과수익률%"].mean()), 2) if "초과수익률%" in result and result["초과수익률%"].notna().any() else np.nan,
        "평균최대하락률%": round(float(result["최대하락률%"].mean()), 2),
        "최악수익률%": round(float(result[ret_col].min()), 2),
        "최고수익률%": round(float(result[ret_col].max()), 2),
    }
    return out

# -----------------------------------------------------------------------------
# UI
# -----------------------------------------------------------------------------

if fdr is None:
    st.error(f"FinanceDataReader import 실패: {FDR_IMPORT_ERROR}")
    st.stop()

with st.expander("이 앱의 목적", expanded=True):
    st.write(
        """
        **홀딩스캐너 백테스트 v1**은 재무/저평가/차트 조합이 실제로 돈이 됐는지 확인하는 첫 버전입니다.  
        v1은 기본적으로 **가격·거래대금·차트 조건**을 백테스트하고, 재무 CSV를 올리면 재무점수를 결합합니다.
        """
    )
    st.code("재무만 좋음 X / 차트만 좋음 X / 재무 + 수급 + 차트 교집합을 검증", language="text")

try:
    listing = get_krx_listing()
except Exception as e:
    st.error(f"KRX 상장목록 로드 실패: {e}")
    st.stop()

left, right = st.columns([1, 1])
with left:
    st.subheader("1) 백테스트 대상")
    max_symbols = st.number_input("최대 테스트 종목수", min_value=5, max_value=300, value=50, step=5)
    default_text = """삼성전자
SK하이닉스
삼성전기
대덕전자
비에이치
DB하이텍
동진쎄미켐
심텍
이수페타시스
서진시스템
LS
LG전자
NAVER
현대백화점
한미약품
삼성E&A
"""
    raw_text = st.text_area("종목명/종목코드 직접 입력", value=default_text, height=220)
    upload_symbols = st.file_uploader("또는 종목 CSV 업로드", type=["csv"], key="symbols_csv")

with right:
    st.subheader("2) 전략 설정")
    start_date = st.date_input("백테스트 시작", value=date(2020, 1, 1))
    end_date = st.date_input("백테스트 종료", value=date.today() - timedelta(days=120))
    hold_months = st.selectbox("보유기간", [3, 6, 12], index=1)
    top_n = st.number_input("매월 상위 N개 매수 가정", min_value=1, max_value=30, value=10, step=1)
    threshold = st.slider("진입 최소 점수", min_value=40, max_value=95, value=70, step=1)
    benchmark_code = st.text_input("벤치마크 코드", value="069500", help="기본: KODEX 200 ETF")

st.subheader("3) 재무 점수 결합")
combine_mode = st.selectbox(
    "점수 방식",
    ["기술/거래대금 전용", "재무CSV 60% + 기술 40%", "재무CSV 50% + 기술 50%"],
    index=0,
)
finance_upload = st.file_uploader("재무점수 CSV 선택 업로드", type=["csv"], key="finance_csv")
st.caption("재무 CSV 컬럼 예시: 종목코드, 종목명, 재무총점 또는 재무점수/저평가점수/실적점수/재무안정점수")

if upload_symbols is not None:
    symbols = load_symbols_from_csv(upload_symbols, listing, max_symbols=max_symbols)
else:
    symbols = resolve_symbols(raw_text, listing, max_symbols=max_symbols)

symbols = symbols[symbols["Code"].astype(str).str.len() == 6].drop_duplicates("Code")
st.write(f"대상 종목수: **{len(symbols)}개**")
if len(symbols):
    st.dataframe(symbols.head(200), use_container_width=True)
else:
    st.warning("대상 종목이 없습니다. 종목명 또는 종목코드를 입력하세요.")

run = st.button("🚀 백테스트 실행", type="primary", disabled=len(symbols) == 0)

if run:
    if start_date >= end_date:
        st.error("시작일이 종료일보다 빠라야 합니다.")
        st.stop()
    with st.spinner("백테스트 실행 중입니다. 종목 수가 많으면 몇 분 걸릴 수 있습니다."):
        finance_scores = parse_finance_score(finance_upload)
        result, errdf = run_backtest(
            symbols=symbols,
            finance_scores=finance_scores,
            start_date=start_date,
            end_date=end_date,
            hold_months=hold_months,
            top_n=int(top_n),
            threshold=float(threshold),
            combine_mode=combine_mode,
            benchmark_code=benchmark_code,
            max_symbols=int(max_symbols),
        )
    st.subheader("결과 요약")
    summary = summarize_result(result, hold_months)
    if not summary:
        st.warning("결과가 없습니다. 점수 기준을 낮추거나 종목 수/기간을 조정하세요.")
    else:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("거래수", f"{summary['거래수']:,}")
        c2.metric("플러스승률", f"{summary['플러스승률%']}%")
        c3.metric("벤치초과비율", f"{summary['벤치초과비율%']}%")
        c4.metric("평균수익률", f"{summary['평균수익률%']}%")
        st.json(summary)

        st.subheader("월별 평균 수익률")
        ret_col = f"{hold_months}개월수익률%"
        monthly = result.groupby("스캔월")[[ret_col, "초과수익률%", "최대하락률%"]].mean().reset_index()
        st.line_chart(monthly.set_index("스캔월")[[ret_col, "초과수익률%"]])

        st.subheader("상세 결과")
        show_cols = [
            "스캔월", "스캔일", "청산일", "종목코드", "종목명", "총점", "기술점수", "재무점수",
            "52주낙폭%", "120일저점반등%", "기준봉", "눌림목", "돌파", "저점상향",
            ret_col, "벤치마크수익률%", "초과수익률%", "최대하락률%",
        ]
        show_cols = [c for c in show_cols if c in result.columns]
        st.dataframe(result[show_cols], use_container_width=True, height=520)

        csv = result.to_csv(index=False).encode("utf-8-sig")
        st.download_button("결과 CSV 다운로드", csv, file_name="holding_backtest_result.csv", mime="text/csv")

    if len(errdf):
        with st.expander("데이터 실패/제외 종목"):
            st.dataframe(errdf, use_container_width=True)

st.divider()
st.caption("주의: FDR 데이터/무료 데이터 기반 백테스트입니다. 생존편향·재무데이터 시차·수수료·세금·슬리피지는 v1에서 단순화되어 있습니다.")
