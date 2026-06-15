# -*- coding: utf-8 -*-
"""
홀딩스캐너 백테스트 v3
- v1: 차트/거래대금 + 선택 재무CSV
- v3 추가: 기준봉+눌림목 중심, 손절 완화/구조손절, 벤치마크 계산 수정

주의: 후보 압축/전략 검증용입니다. 매수 추천/수익 보장 도구가 아닙니다.
"""

import math
import re
from datetime import date, timedelta
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

APP_VERSION = "HOLDING_BACKTEST_V3_BASE_PULLBACK_20260615"

st.set_page_config(page_title="홀딩스캐너 백테스트 v3", layout="wide")
st.title("📊 홀딩스캐너 백테스트 v3")
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
    rows = []
    for line in raw_text.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        token = s.split(",")[0].strip()
        if re.fullmatch(r"\d{4,6}", token):
            code = normalize_code(token)
            row = listing[listing["Code"] == code]
            name = row["Name"].iloc[0] if len(row) else s
            rows.append({"Code": code, "Name": name})
            continue
        m = re.match(r"^(\d{4,6})\s+(.+)$", s)
        if m:
            code = normalize_code(m.group(1))
            row = listing[listing["Code"] == code]
            name = row["Name"].iloc[0] if len(row) else m.group(2).strip()
            rows.append({"Code": code, "Name": name})
            continue
        exact = listing[listing["Name"] == s]
        if len(exact):
            r = exact.iloc[0]
            rows.append({"Code": r["Code"], "Name": r["Name"]})
        else:
            contains = listing[listing["Name"].str.contains(re.escape(s), na=False)]
            if len(contains):
                r = contains.iloc[0]
                rows.append({"Code": r["Code"], "Name": r["Name"]})
            else:
                rows.append({"Code": "", "Name": s})
    out = pd.DataFrame(rows).drop_duplicates() if rows else pd.DataFrame(columns=["Code", "Name"])
    return out.head(max_symbols)


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
    return pd.DataFrame(rows).drop_duplicates().head(max_symbols) if rows else pd.DataFrame(columns=["Code", "Name"])


@st.cache_data(ttl=60 * 60 * 24, show_spinner=False)
def read_price(code: str, start: str, end: str) -> pd.DataFrame:
    if fdr is None:
        raise RuntimeError(f"FinanceDataReader import 실패: {FDR_IMPORT_ERROR}")
    df = fdr.DataReader(code, start, end)
    if df is None or len(df) == 0:
        return pd.DataFrame()
    df = df.copy()
    df.index = pd.to_datetime(df.index)
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
    return df[["Open", "High", "Low", "Close", "Volume"]].dropna(subset=["Close"]).sort_index()


def nearest_on_or_before(df: pd.DataFrame, d: pd.Timestamp) -> Optional[pd.Timestamp]:
    ix = df.index[df.index <= d]
    return ix[-1] if len(ix) else None


def nearest_on_or_after(df: pd.DataFrame, d: pd.Timestamp) -> Optional[pd.Timestamp]:
    ix = df.index[df.index >= d]
    return ix[0] if len(ix) else None


def monthly_scan_dates(start: pd.Timestamp, end: pd.Timestamp) -> List[pd.Timestamp]:
    return [pd.Timestamp(m) for m in pd.date_range(start=start, end=end, freq="MS")]


def pct(x):
    if pd.isna(x):
        return np.nan
    return round(float(x) * 100, 2)


def trailing_return(df: pd.DataFrame, d: pd.Timestamp, days: int) -> float:
    idx = nearest_on_or_before(df, d)
    if idx is None:
        return np.nan
    hist = df.loc[:idx]
    if len(hist) < days + 5:
        return np.nan
    cur = float(hist["Close"].iloc[-1])
    prev = float(hist["Close"].iloc[-days])
    if prev <= 0:
        return np.nan
    return cur / prev - 1


def market_state(benchmark_df: pd.DataFrame, scan_date: pd.Timestamp) -> Dict:
    idx = nearest_on_or_before(benchmark_df, scan_date)
    if idx is None:
        return {"시장필터통과": True, "시장상태": "벤치데이터없음", "벤치20일%": np.nan, "벤치60일%": np.nan, "벤치120일%": np.nan}
    hist = benchmark_df.loc[:idx].copy()
    if len(hist) < 150:
        return {"시장필터통과": True, "시장상태": "벤치데이터부족", "벤치20일%": np.nan, "벤치60일%": np.nan, "벤치120일%": np.nan}
    close = float(hist["Close"].iloc[-1])
    ma60 = float(hist["Close"].rolling(60).mean().iloc[-1])
    ma120 = float(hist["Close"].rolling(120).mean().iloc[-1])
    r20 = trailing_return(benchmark_df, idx, 20)
    r60 = trailing_return(benchmark_df, idx, 60)
    r120 = trailing_return(benchmark_df, idx, 120)
    ok = (close >= ma120) and (r60 >= -0.08)
    if close >= ma120 and r60 >= 0:
        state = "상승/정상"
    elif close >= ma120:
        state = "중립"
    elif close >= ma120 * 0.97:
        state = "경계"
    else:
        state = "하락장"
    return {"시장필터통과": bool(ok), "시장상태": state, "벤치20일%": pct(r20), "벤치60일%": pct(r60), "벤치120일%": pct(r120), "벤치종가": close, "벤치MA60": ma60, "벤치MA120": ma120}


def calc_features(df: pd.DataFrame, scan_date: pd.Timestamp, bm_df: pd.DataFrame) -> Optional[Dict]:
    idx = nearest_on_or_before(df, scan_date)
    if idx is None:
        return None
    hist = df.loc[:idx].copy()
    if len(hist) < 180:
        return None
    close = float(hist["Close"].iloc[-1])
    vol = float(hist["Volume"].iloc[-1]) if not pd.isna(hist["Volume"].iloc[-1]) else 0
    ma20 = float(hist["Close"].rolling(20).mean().iloc[-1])
    ma60 = float(hist["Close"].rolling(60).mean().iloc[-1])
    ma120 = float(hist["Close"].rolling(120).mean().iloc[-1])
    vol20 = float(hist["Volume"].rolling(20).mean().iloc[-1]) if "Volume" in hist else np.nan
    high52 = float(hist["Close"].rolling(252).max().iloc[-1]) if len(hist) >= 252 else float(hist["Close"].max())
    low120 = float(hist["Close"].rolling(120).min().iloc[-1])
    drawdown52 = close / high52 - 1 if high52 > 0 else np.nan
    rebound120 = close / low120 - 1 if low120 > 0 else np.nan

    r20 = trailing_return(df, idx, 20)
    r60 = trailing_return(df, idx, 60)
    r120 = trailing_return(df, idx, 120)
    bm_r60 = trailing_return(bm_df, idx, 60) if len(bm_df) else np.nan
    rel60 = r60 - bm_r60 if not pd.isna(r60) and not pd.isna(bm_r60) else np.nan

    recent = hist.tail(35).copy()
    recent["ret"] = recent["Close"].pct_change()
    recent["vol_ma20"] = hist["Volume"].rolling(20).mean().loc[recent.index]
    base = recent[(recent["ret"] >= 0.05) & (recent["Volume"] >= recent["vol_ma20"] * 1.8)]
    has_base = len(base) > 0
    base_mid_ok = False
    if has_base:
        bidx = base.index[-1]
        brow = recent.loc[bidx]
        base_mid = (float(brow["Open"]) + float(brow["Close"])) / 2
        base_mid_ok = close >= base_mid

    last20_low = float(hist["Close"].tail(20).min())
    prev60_low = float(hist["Close"].iloc[-80:-20].min()) if len(hist) >= 100 else np.nan
    higher_low = bool(pd.notna(prev60_low) and last20_low > prev60_low * 0.98)

    high60 = float(hist["Close"].tail(60).max())
    pullback_from_60h = close / high60 - 1 if high60 > 0 else np.nan
    pullback_ok = bool(close >= ma60 * 0.97 and -0.18 <= pullback_from_60h <= -0.03)
    breakout_ok = bool(close >= high60 * 0.98 and pd.notna(vol20) and vol20 > 0 and vol >= vol20 * 1.5)

    # v2: 너무 많이 오른 종목/너무 깨진 종목 경계 점수
    not_overheated = bool(pd.isna(rebound120) or rebound120 <= 0.85)
    not_broken = bool(pd.isna(drawdown52) or drawdown52 >= -0.65)

    tech = 0
    tech += 7 if close >= ma20 else 0
    tech += 8 if close >= ma60 else 0
    tech += 7 if close >= ma120 * 0.97 else 0
    tech += 8 if has_base and base_mid_ok else 0
    tech += 8 if pullback_ok else 0
    tech += 7 if breakout_ok else 0
    tech += 7 if higher_low else 0
    tech += 6 if -0.55 <= drawdown52 <= -0.12 else 0
    tech += 6 if 0.05 <= rebound120 <= 0.55 else 0
    tech += 6 if pd.notna(vol20) and vol20 > 0 and vol >= vol20 * 1.2 else 0
    tech += 6 if pd.notna(rel60) and rel60 > 0 else 0
    tech += 4 if not_overheated else 0
    tech += 4 if not_broken else 0

    amount = close * vol
    liq = 0
    if amount >= 20_000_000_000: liq = 22
    elif amount >= 10_000_000_000: liq = 19
    elif amount >= 5_000_000_000: liq = 16
    elif amount >= 2_000_000_000: liq = 12
    elif amount >= 1_000_000_000: liq = 8
    else: liq = 4

    score = min(100, tech + liq)
    return {
        "scan_actual_date": idx,
        "close": close,
        "volume": vol,
        "amount": amount,
        "drawdown52": drawdown52,
        "rebound120low": rebound120,
        "r20": r20,
        "r60": r60,
        "r120": r120,
        "rel60": rel60,
        "base": has_base,
        "base_mid_ok": base_mid_ok,
        "pullback": pullback_ok,
        "breakout": breakout_ok,
        "higher_low": higher_low,
        "not_overheated": not_overheated,
        "not_broken": not_broken,
        "technical_score": round(float(score), 2),
    }


def benchmark_return_between(df: pd.DataFrame, entry_date: pd.Timestamp, exit_date: Optional[pd.Timestamp]) -> float:
    """벤치마크는 종목의 실제 진입일~실제 청산일과 같은 기간으로 수익률 계산."""
    if df is None or df.empty or exit_date is None:
        return np.nan
    eidx = nearest_on_or_before(df, entry_date)
    xidx = nearest_on_or_before(df, exit_date)
    if eidx is None or xidx is None or xidx <= eidx:
        return np.nan
    entry = float(df.loc[eidx, "Close"])
    exitp = float(df.loc[xidx, "Close"])
    if entry <= 0:
        return np.nan
    return exitp / entry - 1


def simulate_exit(
    df: pd.DataFrame,
    entry_date: pd.Timestamp,
    hold_days: int,
    exit_mode: str,
    target_pct: float,
    stop_pct: float,
    stop_mode: str = "가격+60일선 이탈",
) -> Tuple[float, float, Optional[pd.Timestamp], str, int]:
    eidx = nearest_on_or_before(df, entry_date)
    if eidx is None:
        return np.nan, np.nan, None, "진입없음", 0
    future_target = eidx + pd.Timedelta(days=hold_days)
    xidx_limit = nearest_on_or_after(df, future_target)
    if xidx_limit is None:
        return np.nan, np.nan, None, "미래데이터없음", 0
    entry = float(df.loc[eidx, "Close"])
    path = df.loc[eidx:xidx_limit].copy()
    if len(path) == 0 or entry <= 0:
        return np.nan, np.nan, None, "데이터없음", 0

    full = df.loc[:xidx_limit].copy()
    full["MA60"] = full["Close"].rolling(60).mean()
    full["MA120"] = full["Close"].rolling(120).mean()

    exit_idx = xidx_limit
    reason = "기간청산"
    if exit_mode == "목표/손절/기간청산":
        target_price = entry * (1 + target_pct)
        for d, row in path.iloc[1:].iterrows():
            c = float(row["Close"])
            ret_now = c / entry - 1
            ma60 = float(full.loc[d, "MA60"]) if d in full.index and pd.notna(full.loc[d, "MA60"]) else np.nan
            ma120 = float(full.loc[d, "MA120"]) if d in full.index and pd.notna(full.loc[d, "MA120"]) else np.nan
            price_stop = ret_now <= -stop_pct
            ma60_break = pd.notna(ma60) and c < ma60
            ma120_break = pd.notna(ma120) and c < ma120 * 0.98

            stop_hit = False
            if stop_mode == "손절없음":
                stop_hit = False
            elif stop_mode == "가격손절":
                stop_hit = price_stop
            elif stop_mode == "가격+60일선 이탈":
                stop_hit = price_stop and ma60_break
            elif stop_mode == "120일선 구조붕괴":
                stop_hit = price_stop and ma120_break
            else:
                stop_hit = price_stop and ma60_break

            if stop_hit:
                exit_idx = d
                reason = "손절청산"
                break
            if c >= target_price:
                exit_idx = d
                reason = "목표청산"
                break

    exitp = float(df.loc[exit_idx, "Close"])
    ret = exitp / entry - 1
    close_path = df.loc[eidx:exit_idx]["Close"]
    mdd = close_path.min() / entry - 1 if len(close_path) else np.nan
    days = int((exit_idx - eidx).days)
    return ret, mdd, exit_idx, reason, days

def parse_finance_score(upload) -> pd.DataFrame:
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
    score_cols = [c for c in df.columns if c in ["재무총점", "재무점수", "저평가점수", "실적점수", "재무안정점수", "수급점수", "가치점수"]]
    rows = []
    for _, r in df.iterrows():
        code = normalize_code(r[code_col]) if code_col else ""
        name = str(r[name_col]).strip() if name_col else ""
        if "재무총점" in df.columns:
            fs = clean_number(r["재무총점"], 0)
        elif "재무점수" in df.columns:
            fs = clean_number(r["재무점수"], 0)
        elif score_cols:
            fs = sum(clean_number(r[c], 0) for c in score_cols)
        else:
            fs = 0
        rows.append({"Code": code, "Name": name, "finance_score": max(0, min(100, fs))})
    out = pd.DataFrame(rows)
    if len(out):
        out["Code"] = out["Code"].astype(str).str.zfill(6)
    return out.drop_duplicates("Code")


def combine_score(tech_score, finance_score, mode):
    if mode == "기술/거래대금 전용":
        return tech_score
    if pd.isna(finance_score):
        return np.nan
    if mode == "재무CSV 60% + 기술 40%":
        return finance_score * 0.6 + tech_score * 0.4
    if mode == "재무CSV 50% + 기술 50%":
        return finance_score * 0.5 + tech_score * 0.5
    return tech_score


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
    use_market_filter: bool,
    use_relative_strength_filter: bool,
    use_overheat_guard: bool,
    use_broken_guard: bool,
    exit_mode: str,
    target_pct: float,
    stop_pct: float,
    cooldown_months: int,
    entry_pattern_profile: str,
    stop_mode: str,
):
    start_ts = pd.Timestamp(start_date)
    end_ts = pd.Timestamp(end_date)
    data_start = (start_ts - pd.Timedelta(days=500)).strftime("%Y-%m-%d")
    data_end = (end_ts + pd.Timedelta(days=hold_months * 35 + 35)).strftime("%Y-%m-%d")
    hold_days = int(hold_months * 30.5)

    symbols = symbols.head(max_symbols).copy()
    price_map: Dict[str, pd.DataFrame] = {}
    errors = []
    progress = st.progress(0, text="가격 데이터 다운로드 중...")
    for i, r in enumerate(symbols.to_dict("records")):
        code = str(r["Code"]).zfill(6)
        try:
            df = read_price(code, data_start, data_end)
            if len(df) >= 220:
                price_map[code] = df
            else:
                errors.append({"Code": code, "Name": r["Name"], "error": "가격데이터 부족"})
        except Exception as e:
            errors.append({"Code": code, "Name": r["Name"], "error": str(e)[:120]})
        progress.progress(min(1.0, (i + 1) / max(1, len(symbols))), text=f"가격 데이터 다운로드 중... {i+1}/{len(symbols)}")
    progress.empty()

    try:
        bm = read_price(benchmark_code, data_start, data_end)
    except Exception:
        bm = pd.DataFrame()

    finance_scores = finance_scores.copy()
    fs_map = {}
    if len(finance_scores) and "Code" in finance_scores.columns:
        finance_scores["Code"] = finance_scores["Code"].astype(str).str.zfill(6)
        fs_map = dict(zip(finance_scores["Code"], finance_scores["finance_score"]))

    scan_dates = monthly_scan_dates(start_ts, end_ts)
    all_rows = []
    last_pick_date_by_code: Dict[str, pd.Timestamp] = {}

    scan_progress = st.progress(0, text="월별 스캔/백테스트 중...")
    for si, sd in enumerate(scan_dates):
        mstate = market_state(bm, sd) if len(bm) else {"시장필터통과": True, "시장상태": "벤치데이터없음"}
        if use_market_filter and not mstate.get("시장필터통과", True):
            scan_progress.progress(min(1.0, (si + 1) / max(1, len(scan_dates))), text=f"월별 스캔 중... {si+1}/{len(scan_dates)}")
            continue

        candidates = []
        for _, sr in symbols.iterrows():
            code = str(sr["Code"]).zfill(6)
            name = str(sr["Name"])
            if cooldown_months > 0 and code in last_pick_date_by_code:
                if sd < last_pick_date_by_code[code] + pd.DateOffset(months=cooldown_months):
                    continue
            df = price_map.get(code)
            if df is None:
                continue
            feat = calc_features(df, sd, bm)
            if feat is None:
                continue
            if use_relative_strength_filter and (pd.isna(feat["rel60"]) or feat["rel60"] <= 0):
                continue
            if use_overheat_guard and not feat["not_overheated"]:
                continue
            if use_broken_guard and not feat["not_broken"]:
                continue
            base_ok = bool(feat["base"] and feat["base_mid_ok"])
            pullback_ok = bool(feat["pullback"])
            if entry_pattern_profile == "기준봉+눌림목 중심" and not (base_ok and pullback_ok):
                continue
            if entry_pattern_profile == "기준봉 또는 눌림목" and not (base_ok or pullback_ok):
                continue
            tech_score = feat["technical_score"]
            finance_score = fs_map.get(code, np.nan)
            total = combine_score(tech_score, finance_score, combine_mode)
            if pd.isna(total) or total < threshold:
                continue
            fut_ret, mdd, exit_date, exit_reason, hold_actual_days = simulate_exit(df, feat["scan_actual_date"], hold_days, exit_mode, target_pct, stop_pct, stop_mode)
            if pd.isna(fut_ret):
                continue
            bm_ret = np.nan
            if len(bm):
                bm_ret = benchmark_return_between(bm, feat["scan_actual_date"], exit_date)
            candidates.append({
                "스캔월": sd.strftime("%Y-%m"),
                "스캔일": feat["scan_actual_date"].strftime("%Y-%m-%d"),
                "청산일": exit_date.strftime("%Y-%m-%d") if exit_date is not None else "",
                "청산사유": exit_reason,
                "보유일수": hold_actual_days,
                "종목코드": code,
                "종목명": name,
                "총점": round(float(total), 2),
                "기술점수": round(float(tech_score), 2),
                "재무점수": round(float(finance_score), 2) if not pd.isna(finance_score) else np.nan,
                "진입가": round(float(feat["close"]), 2),
                "거래대금": round(float(feat["amount"]), 0),
                "시장상태": mstate.get("시장상태", ""),
                "벤치60일%": mstate.get("벤치60일%", np.nan),
                "20일수익률%": pct(feat["r20"]),
                "60일수익률%": pct(feat["r60"]),
                "상대강도60일%": pct(feat["rel60"]),
                "52주낙폭%": pct(feat["drawdown52"]),
                "120일저점반등%": pct(feat["rebound120low"]),
                "진입패턴": "기준봉+눌림목" if (feat["base"] and feat["base_mid_ok"] and feat["pullback"]) else ("기준봉" if (feat["base"] and feat["base_mid_ok"]) else ("눌림목" if feat["pullback"] else ("돌파" if feat["breakout"] else "기타"))),
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
            for _, rr in ranked.iterrows():
                last_pick_date_by_code[str(rr["종목코드"]).zfill(6)] = sd
            all_rows.append(ranked)
        scan_progress.progress(min(1.0, (si + 1) / max(1, len(scan_dates))), text=f"월별 스캔/백테스트 중... {si+1}/{len(scan_dates)}")
    scan_progress.empty()

    result = pd.concat(all_rows, ignore_index=True) if all_rows else pd.DataFrame()
    return result, pd.DataFrame(errors)


def summarize_result(result: pd.DataFrame, hold_months: int) -> Dict:
    if result.empty:
        return {}
    ret_col = f"{hold_months}개월수익률%"
    out = {
        "거래수": int(len(result)),
        "플러스승률%": round(float(result["성공_플러스"].mean() * 100), 2),
        "20%이상비율%": round(float(result["성공_20퍼"].mean() * 100), 2),
        "벤치초과비율%": round(float(result["성공_벤치초과"].mean() * 100), 2),
        "평균수익률%": round(float(result[ret_col].mean()), 2),
        "중앙수익률%": round(float(result[ret_col].median()), 2),
        "평균초과수익률%": round(float(result["초과수익률%"].mean()), 2) if result["초과수익률%"].notna().any() else np.nan,
        "평균최대하락률%": round(float(result["최대하락률%"].mean()), 2),
        "최악수익률%": round(float(result[ret_col].min()), 2),
        "최고수익률%": round(float(result[ret_col].max()), 2),
    }
    if "청산사유" in result.columns:
        reason_counts = result["청산사유"].value_counts().to_dict()
        out.update({f"청산_{k}": int(v) for k, v in reason_counts.items()})
    return out

# -----------------------------------------------------------------------------
# UI
# -----------------------------------------------------------------------------

if fdr is None:
    st.error(f"FinanceDataReader import 실패: {FDR_IMPORT_ERROR}")
    st.stop()

with st.expander("v3에서 바뀐 것", expanded=True):
    st.write("""
    **v3 핵심:** v3에서 나온 단서였던 `기준봉 + 눌림목` 조합을 기본값으로 올리고, 손절을 가격만 보지 않도록 구조손절로 바꿨습니다.
    - 기준봉+눌림목 중심 필터 추가
    - 손절률 기본값 -22%로 완화
    - 가격손절뿐 아니라 60일선/120일선 붕괴형 손절 선택
    - 벤치마크 수익률은 종목의 실제 진입일~청산일과 같은 기간으로 계산
    - 단순 돌파형은 기본값에서 제외 가능
    """)
    st.code("재무/차트 후보 → 장세 통과 → 상대강도 통과 → 기준봉+눌림목 → 구조손절/목표청산 검증", language="text")

try:
    listing = get_krx_listing()
except Exception as e:
    st.error(f"KRX 상장목록 로드 실패: {e}")
    st.stop()

left, right = st.columns([1, 1])
with left:
    st.subheader("1) 백테스트 대상")
    max_symbols = st.number_input("최대 테스트 종목수", min_value=5, max_value=500, value=50, step=5)
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
    st.subheader("2) 기본 전략")
    start_date = st.date_input("백테스트 시작", value=date(2020, 1, 1))
    end_date = st.date_input("백테스트 종료", value=date.today() - timedelta(days=140))
    hold_months = st.selectbox("최대 보유기간", [3, 6, 12], index=1)
    top_n = st.number_input("매월 상위 N개 매수 가정", min_value=1, max_value=30, value=10, step=1)
    threshold = st.slider("진입 최소 점수", min_value=40, max_value=95, value=72, step=1)
    benchmark_code = st.text_input("벤치마크 코드", value="069500", help="기본: KODEX 200 ETF")

st.subheader("3) v3 필터/청산 설정")
c1, c2, c3, c4 = st.columns(4)
with c1:
    use_market_filter = st.checkbox("장세필터 사용", value=True, help="벤치마크가 120일선 아래이거나 60일 수익률이 약하면 신규진입 스킵")
    use_relative_strength_filter = st.checkbox("상대강도 필터", value=True, help="종목 60일 수익률이 벤치마크보다 약하면 제외")
with c2:
    use_overheat_guard = st.checkbox("과열 종목 제외", value=True, help="120일 저점 대비 과도하게 오른 종목 제외")
    use_broken_guard = st.checkbox("붕괴 종목 제외", value=True, help="52주 고점 대비 너무 크게 깨진 종목 제외")
with c3:
    entry_pattern_profile = st.selectbox("진입패턴", ["기준봉+눌림목 중심", "기준봉 또는 눌림목", "기존 v2 전체"], index=0)
    cooldown_months = st.number_input("같은 종목 재진입 쿨다운(개월)", min_value=0, max_value=24, value=6, step=1)
with c4:
    exit_mode = st.selectbox("청산 방식", ["기간보유", "목표/손절/기간청산"], index=1)
    target_pct = st.number_input("목표수익률 %", min_value=5, max_value=100, value=35, step=5) / 100
    stop_pct = st.number_input("손절률 %", min_value=3, max_value=60, value=22, step=1) / 100
    stop_mode = st.selectbox("손절 방식", ["가격+60일선 이탈", "120일선 구조붕괴", "가격손절", "손절없음"], index=0)

st.subheader("4) 재무 점수 결합")
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

run = st.button("🚀 v3 백테스트 실행", type="primary", disabled=len(symbols) == 0)

if run:
    if start_date >= end_date:
        st.error("시작일이 종료일보다 빨라야 합니다.")
        st.stop()
    with st.spinner("v3 백테스트 실행 중입니다. 종목 수가 많으면 몇 분 걸릴 수 있습니다."):
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
            use_market_filter=use_market_filter,
            use_relative_strength_filter=use_relative_strength_filter,
            use_overheat_guard=use_overheat_guard,
            use_broken_guard=use_broken_guard,
            exit_mode=exit_mode,
            target_pct=float(target_pct),
            stop_pct=float(stop_pct),
            cooldown_months=int(cooldown_months),
            entry_pattern_profile=entry_pattern_profile,
            stop_mode=stop_mode,
        )

    st.subheader("결과 요약")
    summary = summarize_result(result, hold_months)
    if not summary:
        st.warning("결과가 없습니다. 필터를 끄거나 점수 기준을 낮추거나 종목 수/기간을 조정하세요.")
    else:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("거래수", f"{summary['거래수']:,}")
        c2.metric("플러스승률", f"{summary['플러스승률%']}%")
        c3.metric("벤치초과비율", f"{summary['벤치초과비율%']}%")
        c4.metric("평균수익률", f"{summary['평균수익률%']}%")
        st.json(summary)

        ret_col = f"{hold_months}개월수익률%"
        st.subheader("월별 평균 수익률")
        monthly = result.groupby("스캔월")[[ret_col, "초과수익률%", "최대하락률%"]].mean().reset_index()
        st.line_chart(monthly.set_index("스캔월")[[ret_col, "초과수익률%"]])

        st.subheader("청산사유별 결과")
        if "청산사유" in result.columns:
            reason = result.groupby("청산사유")[[ret_col, "초과수익률%", "최대하락률%"]].agg(["count", "mean", "median"])
            st.dataframe(reason, use_container_width=True)

        st.subheader("상세 결과")
        show_cols = [
            "스캔월", "스캔일", "청산일", "청산사유", "보유일수", "종목코드", "종목명", "총점", "기술점수", "재무점수",
            "시장상태", "60일수익률%", "상대강도60일%", "52주낙폭%", "120일저점반등%",
            "진입패턴", "기준봉", "눌림목", "돌파", "저점상향", ret_col, "벤치마크수익률%", "초과수익률%", "최대하락률%",
        ]
        show_cols = [c for c in show_cols if c in result.columns]
        st.dataframe(result[show_cols], use_container_width=True, height=560)
        csv = result.to_csv(index=False).encode("utf-8-sig")
        st.download_button("결과 CSV 다운로드", csv, file_name="holding_backtest_v3_result.csv", mime="text/csv")

    if len(errdf):
        with st.expander("데이터 실패/제외 종목"):
            st.dataframe(errdf, use_container_width=True)

st.divider()
st.caption("주의: FDR/무료 데이터 기반 단순 백테스트입니다. 재무데이터 시차·수수료·세금·슬리피지·상장폐지 생존편향은 완전히 반영되지 않습니다.")
