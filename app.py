# -*- coding: utf-8 -*-
"""
Magic Split v44 - T100 CAP5-R70-MIN5 현실형 백테스트 실행기

사용법:
  streamlit run app.py

입력 CSV:
  magic_split_bunker_T10_T100_TURBO_NO_CTA_daily_YYYY-MM-DD.csv
  또는 기준일/통합총자산 컬럼이 있는 T100 daily CSV
"""

import io
import zipfile
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import streamlit as st

APP_VERSION = "v44_T100_CAP5_R70_MIN5_REALISTIC_BACKTEST_20260701"
DEFAULT_SAMPLE_PATH = "magic_split_bunker_T10_T100_TURBO_NO_CTA_daily_2026-07-01.csv"

st.set_page_config(page_title="T100 CAP5-R70-MIN5 백테스트", page_icon="🛡️", layout="wide")


def _today_str() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _fmt_won(x) -> str:
    try:
        return f"{float(x):,.0f}원"
    except Exception:
        return "-"


def _safe_pct(x) -> float:
    try:
        if pd.isna(x):
            return 0.0
        return float(x)
    except Exception:
        return 0.0


def _find_col(df: pd.DataFrame, candidates: List[str]) -> Optional[str]:
    cols = list(df.columns)
    for c in candidates:
        if c in cols:
            return c
    lower_map = {str(c).lower().strip(): c for c in cols}
    for c in candidates:
        key = str(c).lower().strip()
        if key in lower_map:
            return lower_map[key]
    return None


def load_t100_daily(uploaded_file=None, sample_path: Optional[str] = None) -> pd.DataFrame:
    if uploaded_file is not None:
        try:
            df = pd.read_csv(uploaded_file, encoding="utf-8-sig")
        except Exception:
            uploaded_file.seek(0)
            df = pd.read_csv(uploaded_file, encoding="cp949")
    else:
        if sample_path is None:
            sample_path = DEFAULT_SAMPLE_PATH
        df = pd.read_csv(sample_path, encoding="utf-8-sig")

    date_col = _find_col(df, ["기준일", "Date", "date", "날짜"])
    asset_col = _find_col(df, ["통합총자산", "총자산", "수익부스터평가금액", "equity", "Equity", "Close", "close"])
    holding_col = _find_col(df, ["수익부스터보유", "마지막보유", "보유", "holding", "Holdings"])

    if date_col is None or asset_col is None:
        raise ValueError("CSV에 기준일/통합총자산 컬럼이 필요합니다. 예: 기준일, 통합총자산")

    out = pd.DataFrame()
    out["기준일"] = pd.to_datetime(df[date_col], errors="coerce")
    out["T100원본총자산"] = pd.to_numeric(df[asset_col], errors="coerce")
    if holding_col is not None:
        out["T100원본보유"] = df[holding_col].astype(str).fillna("")
    else:
        out["T100원본보유"] = ""
    out = out.dropna(subset=["기준일", "T100원본총자산"]).sort_values("기준일").reset_index(drop=True)
    out = out[out["T100원본총자산"] > 0].reset_index(drop=True)
    if len(out) < 30:
        raise ValueError("유효 데이터가 너무 적습니다. 최소 30거래일 이상 필요합니다.")
    out["T100원본일수익률"] = out["T100원본총자산"].pct_change().fillna(0.0)
    return out


def calc_drawdown(equity: pd.Series) -> pd.Series:
    eq = pd.to_numeric(equity, errors="coerce").ffill().fillna(0)
    peak = eq.cummax().replace(0, np.nan)
    return (eq / peak - 1.0).fillna(0.0)


def worst_rolling_return(equity: pd.Series, window: int) -> float:
    eq = pd.to_numeric(equity, errors="coerce").ffill().fillna(0)
    if len(eq) <= window:
        return 0.0
    ret = eq / eq.shift(window) - 1.0
    return float(ret.min())


def longest_recovery_days(equity: pd.Series) -> int:
    eq = pd.to_numeric(equity, errors="coerce").ffill().fillna(0).reset_index(drop=True)
    peak = -np.inf
    current = 0
    longest = 0
    for v in eq:
        if v >= peak:
            peak = v
            current = 0
        else:
            current += 1
            if current > longest:
                longest = current
    return int(longest)


def mdd_episode(df: pd.DataFrame, equity_col: str) -> Dict[str, object]:
    eq = pd.to_numeric(df[equity_col], errors="coerce").ffill().fillna(0).reset_index(drop=True)
    dates = pd.to_datetime(df["기준일"]).reset_index(drop=True)
    peak_eq = eq.cummax()
    dd = eq / peak_eq.replace(0, np.nan) - 1.0
    trough_idx = int(dd.idxmin()) if len(dd) else 0
    peak_value = peak_eq.iloc[trough_idx]
    peak_candidates = eq.iloc[:trough_idx + 1]
    peak_idx = int(peak_candidates[peak_candidates == peak_value].index[-1]) if len(peak_candidates) else 0
    recovery_idx = None
    for i in range(trough_idx + 1, len(eq)):
        if eq.iloc[i] >= peak_value:
            recovery_idx = i
            break
    return {
        "고점일": dates.iloc[peak_idx].date().isoformat() if len(dates) else "",
        "저점일": dates.iloc[trough_idx].date().isoformat() if len(dates) else "",
        "회복일": dates.iloc[recovery_idx].date().isoformat() if recovery_idx is not None else "미회복",
        "MDD": round(float(dd.iloc[trough_idx]) * 100.0, 2) if len(dd) else 0,
        "회복까지걸린거래일": int(recovery_idx - peak_idx) if recovery_idx is not None else int(len(eq) - 1 - peak_idx),
    }


def calc_basic_stats(df: pd.DataFrame, equity_col: str, initial: float = 100_000_000) -> Dict[str, object]:
    eq = pd.to_numeric(df[equity_col], errors="coerce").ffill().fillna(0)
    dates = pd.to_datetime(df["기준일"])
    start_dt = dates.iloc[0]
    end_dt = dates.iloc[-1]
    final = float(eq.iloc[-1])
    total_ret = final / float(initial) - 1.0
    years = max((end_dt - start_dt).days / 365.25, 1e-9)
    cagr = (final / float(initial)) ** (1 / years) - 1.0
    daily_ret = eq.pct_change().fillna(0.0)
    out = {
        "시작일": start_dt.date().isoformat(),
        "종료일": end_dt.date().isoformat(),
        "최종자산": round(final),
        "총수익률": round(total_ret * 100.0, 2),
        "CAGR": round(cagr * 100.0, 2),
        "MDD": round(float(calc_drawdown(eq).min()) * 100.0, 2),
        "최악하루": round(float(daily_ret.min()) * 100.0, 2),
        "최악3일": round(worst_rolling_return(eq, 3) * 100.0, 2),
        "최악10일": round(worst_rolling_return(eq, 10) * 100.0, 2),
        "최장회복기간": longest_recovery_days(eq),
    }
    out.update({f"MDD_{k}": v for k, v in mdd_episode(df, equity_col).items()})
    return out


@dataclass
class CapParams:
    cap_trigger: float = -0.05
    t100_defense_weight: float = 0.70
    min_defense_days: int = 5
    cash_annual_rate: float = 0.03
    trade_cost: float = 0.0
    initial: float = 100_000_000
    rebound_ma_days: int = 20
    recover_from_peak: float = -0.05


def simulate_cap5_r70_min5(base_df: pd.DataFrame, params: CapParams) -> Tuple[pd.DataFrame, pd.DataFrame]:
    df = base_df.copy().reset_index(drop=True)
    n = len(df)
    cash_daily = (1.0 + params.cash_annual_rate) ** (1.0 / 252.0) - 1.0
    t100_ret = df["T100원본일수익률"].astype(float).values
    original_equity = df["T100원본총자산"].astype(float)
    original_ma20 = original_equity.rolling(params.rebound_ma_days, min_periods=params.rebound_ma_days).mean()
    original_peak = original_equity.cummax()

    cap_equity = np.zeros(n)
    cap_ret = np.zeros(n)
    t100_weight = np.zeros(n)
    cash_weight = np.zeros(n)
    mode = []
    signal = []
    action = []

    cap_equity[0] = params.initial
    in_defense = False
    defense_days = 0
    pending_defense = False
    last_signal_date = None
    entry_cost_pending = False
    exit_cost_pending = False

    events: List[Dict[str, object]] = []
    active_entry_idx = None
    active_entry_equity = None

    for i in range(n):
        dt = pd.to_datetime(df.loc[i, "기준일"])
        sig_today = bool(t100_ret[i] <= params.cap_trigger)
        signal.append("CAP5" if sig_today else "")

        # 전일 신호가 있으면 오늘부터 방어모드. 신호 당일 손실은 그대로 맞는다.
        if i > 0 and pending_defense and not in_defense:
            in_defense = True
            defense_days = 0
            entry_cost_pending = True
            active_entry_idx = i
            active_entry_equity = cap_equity[i - 1]
            events.append({
                "전략": "CAP5-R70-MIN5",
                "이벤트": "방어모드진입",
                "일자": dt.date().isoformat(),
                "원인신호일": last_signal_date,
                "T100비중": round(params.t100_defense_weight * 100, 2),
                "CASH비중": round((1 - params.t100_defense_weight) * 100, 2),
                "비고": "전일 CAP5 신호로 다음 거래일부터 방어모드",
            })
            pending_defense = False

        # 오늘 적용 비중 결정
        if in_defense:
            w_t = params.t100_defense_weight
            w_c = 1.0 - params.t100_defense_weight
        else:
            w_t = 1.0
            w_c = 0.0
        t100_weight[i] = w_t
        cash_weight[i] = w_c
        mode.append("방어" if in_defense else "공격")

        # 일수익률 적용
        if i == 0:
            day_ret = 0.0
        else:
            day_ret = w_t * t100_ret[i] + w_c * cash_daily
            if entry_cost_pending and params.trade_cost > 0:
                # T100 30% 축소 또는 재확대에 대한 단순 회전비용. 총자산 기준 비용률로 보수 처리.
                day_ret -= params.trade_cost * abs(1.0 - params.t100_defense_weight)
                entry_cost_pending = False
            if exit_cost_pending and params.trade_cost > 0:
                day_ret -= params.trade_cost * abs(1.0 - params.t100_defense_weight)
                exit_cost_pending = False
        cap_ret[i] = day_ret
        if i > 0:
            cap_equity[i] = cap_equity[i - 1] * (1.0 + day_ret)

        act = ""

        # 방어모드 해제 판단: 오늘 수익률 반영 후 판단, 해제는 다음 거래일부터 100% 적용
        if in_defense:
            defense_days += 1
            can_exit = defense_days >= int(params.min_defense_days)
            ma_recovered = False
            peak_recovered = False
            if i < len(original_ma20) and not pd.isna(original_ma20.iloc[i]):
                ma_recovered = bool(original_equity.iloc[i] >= original_ma20.iloc[i])
            if original_peak.iloc[i] > 0:
                peak_recovered = bool((original_equity.iloc[i] / original_peak.iloc[i] - 1.0) >= params.recover_from_peak)
            if can_exit and (ma_recovered or peak_recovered):
                exit_date = dt.date().isoformat()
                duration = defense_days
                def_ret = (cap_equity[i] / active_entry_equity - 1.0) if active_entry_equity else 0.0
                events.append({
                    "전략": "CAP5-R70-MIN5",
                    "이벤트": "방어모드해제",
                    "일자": exit_date,
                    "원인신호일": last_signal_date,
                    "방어유지일": duration,
                    "방어모드수익률": round(def_ret * 100.0, 2),
                    "해제조건": "20일선회복" if ma_recovered else "전고점대비-5%이내",
                    "비고": "다음 거래일부터 T100 100% 복귀",
                })
                in_defense = False
                defense_days = 0
                exit_cost_pending = True
                act = "방어해제"
        # 신호 기록: 신호가 뜨고 공격모드라면 다음 거래일부터 방어. 방어모드 중 신호는 기록만 한다.
        if sig_today:
            last_signal_date = dt.date().isoformat()
            events.append({
                "전략": "CAP5-R70-MIN5",
                "이벤트": "CAP5신호",
                "일자": last_signal_date,
                "T100원본일수익률": round(t100_ret[i] * 100.0, 2),
                "처리": "다음거래일방어모드" if not in_defense else "이미방어모드",
                "비고": "신호 당일 손실은 그대로 반영",
            })
            if not in_defense:
                pending_defense = True
                act = "CAP5신호"
        action.append(act)

    out = df.copy()
    out["CAP5_R70_MIN5총자산"] = cap_equity
    out["CAP5_R70_MIN5일수익률"] = cap_ret
    out["T100비중"] = np.round(t100_weight * 100.0, 2)
    out["CASH비중"] = np.round(cash_weight * 100.0, 2)
    out["모드"] = mode
    out["CAP5신호"] = signal
    out["행동"] = action
    out["CAP5_R70_MIN5수익률"] = (out["CAP5_R70_MIN5총자산"] / params.initial - 1.0) * 100.0
    out["CAP5_R70_MIN5_MDD"] = calc_drawdown(out["CAP5_R70_MIN5총자산"]) * 100.0
    out["T100원본수익률"] = (out["T100원본총자산"] / float(out["T100원본총자산"].iloc[0]) - 1.0) * 100.0
    out["T100원본MDD"] = calc_drawdown(out["T100원본총자산"]) * 100.0

    ev = pd.DataFrame(events)
    return out, ev


def yearly_returns_mdd(df: pd.DataFrame, strategies: Dict[str, str]) -> pd.DataFrame:
    rows = []
    tmp = df.copy()
    tmp["연도"] = pd.to_datetime(tmp["기준일"]).dt.year
    for name, col in strategies.items():
        for year, g in tmp.groupby("연도"):
            eq = pd.to_numeric(g[col], errors="coerce").ffill().dropna()
            if len(eq) < 2:
                continue
            rows.append({
                "전략": name,
                "연도": int(year),
                "연초자산": round(float(eq.iloc[0])),
                "연말자산": round(float(eq.iloc[-1])),
                "연도수익률": round((float(eq.iloc[-1]) / float(eq.iloc[0]) - 1.0) * 100.0, 2),
                "연도MDD": round(float(calc_drawdown(eq).min()) * 100.0, 2),
            })
    return pd.DataFrame(rows)


def monthly_detail_summary(df: pd.DataFrame, strategies: Dict[str, str]) -> Tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    tmp = df.copy()
    tmp["월"] = pd.to_datetime(tmp["기준일"]).dt.to_period("M").astype(str)
    for name, col in strategies.items():
        for month, g in tmp.groupby("월"):
            eq = pd.to_numeric(g[col], errors="coerce").ffill().dropna()
            if len(eq) < 2:
                continue
            rows.append({
                "전략": name,
                "월": month,
                "월수익률": round((float(eq.iloc[-1]) / float(eq.iloc[0]) - 1.0) * 100.0, 2),
                "월MDD": round(float(calc_drawdown(eq).min()) * 100.0, 2),
            })
    detail = pd.DataFrame(rows)
    summary_rows = []
    if len(detail) > 0:
        for name, g in detail.groupby("전략"):
            best = g.loc[g["월수익률"].idxmax()]
            worst = g.loc[g["월수익률"].idxmin()]
            summary_rows.append({
                "전략": name,
                "월별최고월": best["월"],
                "월별최고수익률": best["월수익률"],
                "월별최악월": worst["월"],
                "월별최악수익률": worst["월수익률"],
            })
    return detail, pd.DataFrame(summary_rows)


def post_return_after_exit(daily: pd.DataFrame, events: pd.DataFrame, horizon: int = 20) -> pd.DataFrame:
    rows = []
    if events is None or len(events) == 0:
        return pd.DataFrame()
    exits = events[events.get("이벤트", pd.Series(dtype=str)).eq("방어모드해제")].copy()
    if len(exits) == 0:
        return pd.DataFrame()
    dates = pd.to_datetime(daily["기준일"]).reset_index(drop=True)
    eq = pd.to_numeric(daily["CAP5_R70_MIN5총자산"], errors="coerce").ffill().reset_index(drop=True)
    for _, r in exits.iterrows():
        dt = pd.to_datetime(r.get("일자"))
        idxs = dates[dates == dt].index
        if len(idxs) == 0:
            continue
        i = int(idxs[0])
        j = min(i + horizon, len(eq) - 1)
        rows.append({
            "방어해제일": dt.date().isoformat(),
            f"복귀후{horizon}거래일수익률": round((float(eq.iloc[j]) / float(eq.iloc[i]) - 1.0) * 100.0, 2),
            "측정종료일": dates.iloc[j].date().isoformat(),
        })
    return pd.DataFrame(rows)


def build_outputs(base_df: pd.DataFrame, settings: Dict[str, float]) -> Dict[str, pd.DataFrame]:
    initial = float(settings.get("initial", 100_000_000))
    cash_rate = float(settings.get("cash_rate", 3.0)) / 100.0
    cap_trigger = -abs(float(settings.get("cap_trigger", 5.0))) / 100.0
    r_weight = float(settings.get("r_weight", 70.0)) / 100.0
    min_days = int(settings.get("min_days", 5))
    cost_list = settings.get("cost_list", [0.0, 0.001, 0.002])

    # 원본은 입력 자산곡선을 1억 기준으로 리베이스한다.
    df0 = base_df.copy()
    df0["T100원본총자산"] = df0["T100원본총자산"] / float(df0["T100원본총자산"].iloc[0]) * initial
    df0["T100원본일수익률"] = df0["T100원본총자산"].pct_change().fillna(0.0)

    daily_first = None
    event_frames = []
    summary_rows = []
    mdd_rows = []

    orig_stats = calc_basic_stats(df0.rename(columns={"T100원본총자산": "eq"}), "eq", initial)
    orig_row = {"전략": "T100_ORIGINAL", "거래비용": 0.0, **orig_stats}
    orig_row.update({"CAP5신호횟수": 0, "방어모드진입횟수": 0, "방어모드총유지일": 0, "방어모드평균유지일": 0, "마지막T100비중": 100.0, "마지막CASH비중": 0.0})
    summary_rows.append(orig_row)
    ep = mdd_episode(df0.rename(columns={"T100원본총자산": "eq"}), "eq")
    mdd_rows.append({"전략": "T100_ORIGINAL", **ep})

    for cost in cost_list:
        params = CapParams(
            cap_trigger=cap_trigger,
            t100_defense_weight=r_weight,
            min_defense_days=min_days,
            cash_annual_rate=cash_rate,
            trade_cost=float(cost),
            initial=initial,
        )
        daily, events = simulate_cap5_r70_min5(df0, params)
        label = f"CAP{abs(cap_trigger)*100:.0f}-R{r_weight*100:.0f}-MIN{min_days}_COST{cost*100:.1f}%"
        daily["전략라벨"] = label
        if daily_first is None:
            daily_first = daily.copy()
        if len(events) > 0:
            events = events.copy()
            events["전략라벨"] = label
            event_frames.append(events)

        stats = calc_basic_stats(daily.rename(columns={"CAP5_R70_MIN5총자산": "eq"}), "eq", initial)
        defense_entries = events[events["이벤트"].eq("방어모드진입")] if len(events) > 0 else pd.DataFrame()
        defense_exits = events[events["이벤트"].eq("방어모드해제")] if len(events) > 0 else pd.DataFrame()
        total_defense_days = int(daily["모드"].eq("방어").sum())
        avg_defense_days = round(total_defense_days / max(len(defense_entries), 1), 2)
        defense_return = 0.0
        if daily["모드"].eq("방어").any():
            d = daily[daily["모드"].eq("방어")]
            defense_return = float((1.0 + d["CAP5_R70_MIN5일수익률"].astype(float)).prod() - 1.0) * 100.0
        post20 = post_return_after_exit(daily, events, 20)
        post20_avg = round(float(post20.iloc[:, 1].mean()), 2) if len(post20) > 0 else 0.0
        row = {"전략": label, "거래비용": round(float(cost) * 100.0, 3), **stats}
        row.update({
            "CAP5신호횟수": int((events["이벤트"].eq("CAP5신호")).sum()) if len(events) > 0 else 0,
            "방어모드진입횟수": int(len(defense_entries)),
            "방어모드해제횟수": int(len(defense_exits)),
            "방어모드총유지일": total_defense_days,
            "방어모드평균유지일": avg_defense_days,
            "방어모드중수익률": round(defense_return, 2),
            "방어모드후복귀20거래일평균수익률": post20_avg,
            "마지막총자산": round(float(daily["CAP5_R70_MIN5총자산"].iloc[-1])),
            "마지막T100비중": float(daily["T100비중"].iloc[-1]),
            "마지막CASH비중": float(daily["CASH비중"].iloc[-1]),
        })
        summary_rows.append(row)
        mdd_rows.append({"전략": label, **mdd_episode(daily.rename(columns={"CAP5_R70_MIN5총자산": "eq"}), "eq")})

    summary = pd.DataFrame(summary_rows)
    selected = summary[summary["전략"].isin(["T100_ORIGINAL", f"CAP{abs(cap_trigger)*100:.0f}-R{r_weight*100:.0f}-MIN{min_days}_COST0.0%", f"CAP{abs(cap_trigger)*100:.0f}-R{r_weight*100:.0f}-MIN{min_days}_COST0.1%", f"CAP{abs(cap_trigger)*100:.0f}-R{r_weight*100:.0f}-MIN{min_days}_COST0.2%"])].copy()
    seventy = summary[["전략", "최종자산", "총수익률", "CAGR", "MDD", "최악하루", "최장회복기간"]].copy()
    seventy["7천만원환산최종자산"] = (pd.to_numeric(seventy["최종자산"], errors="coerce") * 0.7).round(0).astype("Int64")

    strategies = {"T100_ORIGINAL": "T100원본총자산"}
    if daily_first is not None:
        strategies[f"CAP{abs(cap_trigger)*100:.0f}-R{r_weight*100:.0f}-MIN{min_days}"] = "CAP5_R70_MIN5총자산"
        yearly = yearly_returns_mdd(daily_first, strategies)
        monthly_detail, monthly_summary = monthly_detail_summary(daily_first, strategies)
    else:
        yearly = pd.DataFrame(); monthly_detail = pd.DataFrame(); monthly_summary = pd.DataFrame()
    events_all = pd.concat(event_frames, ignore_index=True) if event_frames else pd.DataFrame()
    mdd = pd.DataFrame(mdd_rows)

    return {
        "summary": summary,
        "selected_compare": selected,
        "daily": daily_first if daily_first is not None else pd.DataFrame(),
        "events": events_all,
        "mdd_episodes": mdd,
        "yearly_returns_mdd": yearly,
        "monthly_detail": monthly_detail,
        "monthly_summary": monthly_summary,
        "70m_conversion": seventy,
    }


def make_zip(outputs: Dict[str, pd.DataFrame]) -> bytes:
    buf = io.BytesIO()
    today = _today_str()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, df in outputs.items():
            if df is None:
                continue
            zf.writestr(f"magic_split_T100_CAP5_R70_MIN5_v44_{name}_{today}.csv", df.to_csv(index=False).encode("utf-8-sig"))
    buf.seek(0)
    return buf.getvalue()


st.title("🛡️ Magic Split v44 · T100-CAP5-R70-MIN5 현실형 백테스트")
st.caption(APP_VERSION)

st.info("신호 당일 손실은 그대로 반영하고, 다음 거래일부터 T100 70% + CASH 30% 방어모드로 전환합니다. 미래정보는 사용하지 않습니다.")

with st.sidebar:
    st.header("입력")
    uploaded = st.file_uploader("T100 daily CSV 업로드", type=["csv"], help="기준일/통합총자산 컬럼이 있는 T100 daily CSV")
    use_sample = st.checkbox("같은 폴더의 샘플 CSV 사용", value=True)
    st.header("설정")
    initial = st.number_input("초기자금", min_value=1_000_000, max_value=10_000_000_000, value=100_000_000, step=1_000_000, format="%d")
    cap_trigger = st.number_input("CAP 신호 기준: 하루 손실률(%)", min_value=1.0, max_value=20.0, value=5.0, step=0.5)
    r_weight = st.number_input("방어모드 T100 비중(%)", min_value=0.0, max_value=100.0, value=70.0, step=5.0)
    min_days = st.number_input("방어모드 최소 유지 거래일", min_value=1, max_value=60, value=5, step=1)
    cash_rate = st.number_input("CASH 연수익률 가정(%)", min_value=0.0, max_value=20.0, value=3.0, step=0.5)
    costs_text = st.text_input("거래비용 비교(%)", value="0,0.1,0.2", help="쉼표로 입력. 예: 0,0.1,0.2")

try:
    cost_list = [float(x.strip()) / 100.0 for x in costs_text.split(",") if x.strip() != ""]
except Exception:
    cost_list = [0.0, 0.001, 0.002]

run = st.button("T100-CAP5-R70-MIN5 백테스트 실행", type="primary", use_container_width=True)

if run:
    try:
        if uploaded is None and not use_sample:
            st.warning("CSV를 업로드하거나 샘플 CSV 사용을 켜주세요.")
            st.stop()
        base = load_t100_daily(uploaded_file=uploaded, sample_path=DEFAULT_SAMPLE_PATH if use_sample else None)
        settings = {
            "initial": initial,
            "cash_rate": cash_rate,
            "cap_trigger": cap_trigger,
            "r_weight": r_weight,
            "min_days": min_days,
            "cost_list": cost_list,
        }
        outputs = build_outputs(base, settings)
        summary = outputs["summary"]
        selected = outputs["selected_compare"]
        daily = outputs["daily"]
        events = outputs["events"]
        seventy = outputs["70m_conversion"]
        zip_bytes = make_zip(outputs)

        st.success("백테스트 완료")
        c1, c2, c3, c4 = st.columns(4)
        main = selected.iloc[1] if len(selected) > 1 else summary.iloc[-1]
        c1.metric("최종자산", _fmt_won(main.get("최종자산", 0)))
        c2.metric("총수익률", f"{main.get('총수익률', 0)}%")
        c3.metric("MDD", f"{main.get('MDD', 0)}%")
        c4.metric("최악 하루", f"{main.get('최악하루', 0)}%")

        st.download_button(
            "결과 ZIP 다운로드",
            data=zip_bytes,
            file_name=f"magic_split_v44_T100_CAP5_R70_MIN5_backtest_outputs_{_today_str()}.zip",
            mime="application/zip",
            use_container_width=True,
        )

        tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["핵심비교", "요약전체", "daily", "이벤트", "연도별", "7천만환산"])
        with tab1:
            st.dataframe(selected, use_container_width=True, hide_index=True)
            st.download_button("핵심비교 CSV", data=selected.to_csv(index=False).encode("utf-8-sig"), file_name=f"magic_split_T100_CAP5_R70_MIN5_v44_selected_compare_{_today_str()}.csv", mime="text/csv")
        with tab2:
            st.dataframe(summary, use_container_width=True, hide_index=True)
        with tab3:
            st.dataframe(daily, use_container_width=True, height=520, hide_index=True)
        with tab4:
            st.dataframe(events, use_container_width=True, height=420, hide_index=True)
        with tab5:
            st.dataframe(outputs["yearly_returns_mdd"], use_container_width=True, height=420, hide_index=True)
        with tab6:
            st.dataframe(seventy, use_container_width=True, hide_index=True)

        st.caption("실전 주의: 신호 다음날 종가/수익률부터 비중축소를 반영한 현실형입니다. 갭, 괴리, 체결, 세금은 별도 보수 조정이 필요합니다.")
    except FileNotFoundError:
        st.error(f"샘플 CSV를 찾지 못했습니다: {DEFAULT_SAMPLE_PATH}. CSV를 업로드해서 실행하세요.")
    except Exception as e:
        st.error(f"백테스트 실패: {e}")
else:
    st.markdown("""
### 실행 순서
1. T100 daily CSV를 업로드하거나, 샘플 CSV를 app.py와 같은 폴더에 둡니다.  
2. 기본값은 CAP5 / R70 / MIN5 / CASH 연 3% / 거래비용 0%, 0.1%, 0.2%입니다.  
3. **백테스트 실행**을 누르면 summary, daily, events, yearly, monthly, 7천만 환산 CSV가 ZIP으로 생성됩니다.

### 입력 CSV 필수 컬럼
- `기준일`
- `통합총자산` 또는 `수익부스터평가금액`
""")
