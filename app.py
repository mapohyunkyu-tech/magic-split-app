#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IDIO 300 v3 Champion Backtester
비체계적 과락 반등 포트 전략 백테스터

Input CSV required columns:
    date, code, name, market, sector, open, high, low, close, volume, trading_value, market_cap

Example:
    python idio_300_v3_champion_backtester.py \
        --input kr_stock_daily.csv \
        --outdir ./idio_results \
        --start 2010-01-04 \
        --end 2026-07-06

Outputs:
    idio_300_v3_summary.csv
    idio_300_v3_trades.csv
    idio_300_v3_equity_curve.csv
    idio_300_v3_yearly_return.csv
    idio_300_v3_signals.csv
    idio_300_v3_benchmarks.csv

Design notes:
- This script is a local backtest engine. Results are only as good as the input data.
- If the input data contains only currently listed stocks, survivorship bias can make results look better.
- For strict research, include delisted stocks, historical trading halts, management issue history,
  historical market cap, corrected OHLCV, and stable historical sector classification.
"""

from __future__ import annotations

import argparse
import math
import os
import re
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=RuntimeWarning)

REQUIRED_COLUMNS = [
    "date", "code", "name", "market", "sector", "open", "high", "low", "close",
    "volume", "trading_value", "market_cap",
]

EXCLUDE_NAME_PATTERNS = [
    r"스팩", r"SPAC", r"ETF", r"ETN", r"인버스", r"레버리지",
    r"선물", r"채권", r"원유", r"금선물", r"달러", r"리츠",  # 필요 시 --allow-reits 로 완화 가능
]

PREFERRED_SHARE_PATTERNS = [
    r"우$", r"우B$", r"우선주", r"\d우B$", r"\d우$",
]


@dataclass
class BacktestConfig:
    portfolio_size: int
    slot_cash: float
    exit_rule: str  # fixed20, tp12_sl10_max40, tp15_sl15_max60
    commission_rate: float = 0.0
    sell_tax_rate: float = 0.0
    entry_price_col: str = "close"
    exit_price_col: str = "close"

    @property
    def initial_cash(self) -> float:
        return self.portfolio_size * self.slot_cash


@dataclass
class Position:
    code: str
    name: str
    entry_date: pd.Timestamp
    entry_price: float
    shares: int
    invested: float
    slot_cash: float
    score: float
    entry_signal: Dict[str, float]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="IDIO 300 v3 Champion backtester")
    p.add_argument("--input", required=True, help="Input daily stock CSV path")
    p.add_argument("--outdir", default="./idio_300_v3_output", help="Output directory")
    p.add_argument("--start", default="2010-01-04", help="Backtest start date")
    p.add_argument("--end", default=None, help="Backtest end date")
    p.add_argument("--slot-cash", type=float, default=3_000_000, help="Cash per stock slot")
    p.add_argument("--portfolio-sizes", default="10,20", help="Comma-separated portfolio sizes")
    p.add_argument("--reg-window", type=int, default=120, help="Rolling regression window")
    p.add_argument("--min-reg-obs", type=int, default=80, help="Minimum observations for regression")
    p.add_argument("--market-crisis-mode", default="block", choices=["block", "shrink", "penalty"],
                   help="block=new buys banned in crisis, shrink=20->10, penalty=allow but penalize")
    p.add_argument("--commission-rate", type=float, default=0.0,
                   help="Commission rate per buy/sell side. Example 0.00015 for 0.015%%")
    p.add_argument("--sell-tax-rate", type=float, default=0.0,
                   help="Sell tax rate. Example 0.0018 for 0.18%%. Default 0 for pure strategy test")
    p.add_argument("--entry-price", default="close", choices=["open", "close"], help="Entry price column")
    p.add_argument("--exit-price", default="close", choices=["open", "close"], help="Exit price column")
    p.add_argument("--allow-reits", action="store_true", help="Do not exclude names containing 리츠")
    p.add_argument("--save-all-signals", action="store_true", help="Save all candidate rows, not only filtered rows")
    return p.parse_args()


def safe_float(x) -> float:
    try:
        if pd.isna(x):
            return np.nan
        return float(x)
    except Exception:
        return np.nan


def load_data(path: str, start: str, end: Optional[str], allow_reits: bool = False) -> pd.DataFrame:
    df = pd.read_csv(path, dtype={"code": str})
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Input CSV missing columns: {missing}")

    df = df[REQUIRED_COLUMNS].copy()
    df["date"] = pd.to_datetime(df["date"])
    for c in ["open", "high", "low", "close", "volume", "trading_value", "market_cap"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["code"] = df["code"].astype(str).str.zfill(6)
    df["name"] = df["name"].astype(str)
    df["market"] = df["market"].astype(str).str.upper()
    df["sector"] = df["sector"].fillna("UNKNOWN").astype(str)

    df = df[(df["date"] >= pd.to_datetime(start))]
    if end:
        df = df[df["date"] <= pd.to_datetime(end)]

    # Basic common-stock universe filter
    df = df[df["market"].isin(["KOSPI", "KOSDAQ"])]
    patterns = EXCLUDE_NAME_PATTERNS.copy()
    if allow_reits:
        patterns = [x for x in patterns if x != r"리츠"]
    exclude_regex = re.compile("|".join(patterns), flags=re.IGNORECASE)
    pref_regex = re.compile("|".join(PREFERRED_SHARE_PATTERNS), flags=re.IGNORECASE)
    df = df[~df["name"].str.contains(exclude_regex, na=False)]
    df = df[~df["name"].str.contains(pref_regex, na=False)]

    df = df.dropna(subset=["date", "code", "open", "high", "low", "close"])
    df = df[(df["close"] > 0) & (df["open"] > 0)]
    df = df.sort_values(["date", "code"]).reset_index(drop=True)
    return df


def weighted_average_return(group: pd.DataFrame, ret_col: str) -> float:
    r = group[ret_col].astype(float)
    w = group["market_cap"].astype(float).replace([np.inf, -np.inf], np.nan)
    mask = r.notna() & w.notna() & (w > 0)
    if mask.sum() == 0:
        return np.nan
    return np.average(r[mask], weights=w[mask])


def add_market_sector_returns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values(["code", "date"]).copy()
    g = df.groupby("code", group_keys=False)
    df["ret_1d"] = g["close"].pct_change()
    df["ret_5d"] = g["close"].pct_change(5)

    # Market and sector broad returns derived from the supplied universe.
    # If you have official index daily returns, merge them before this stage and replace these fields.
    m1 = df.groupby(["date", "market"]).apply(lambda x: weighted_average_return(x, "ret_1d")).rename("market_ret_1d").reset_index()
    m5 = df.groupby(["date", "market"]).apply(lambda x: weighted_average_return(x, "ret_5d")).rename("market_ret_5d").reset_index()
    s1 = df.groupby(["date", "sector"]).apply(lambda x: weighted_average_return(x, "ret_1d")).rename("sector_ret_1d").reset_index()
    s5 = df.groupby(["date", "sector"]).apply(lambda x: weighted_average_return(x, "ret_5d")).rename("sector_ret_5d").reset_index()

    df = df.merge(m1, on=["date", "market"], how="left")
    df = df.merge(m5, on=["date", "market"], how="left")
    df = df.merge(s1, on=["date", "sector"], how="left")
    df = df.merge(s5, on=["date", "sector"], how="left")
    return df


def rolling_ols_residuals_one_stock(x: pd.DataFrame, reg_window: int, min_obs: int) -> pd.DataFrame:
    x = x.sort_values("date").copy()
    y = x["ret_1d"].to_numpy(dtype=float)
    xm = x["market_ret_1d"].to_numpy(dtype=float)
    xs = x["sector_ret_1d"].to_numpy(dtype=float)
    n = len(x)

    alpha = np.full(n, np.nan)
    beta_m = np.full(n, np.nan)
    beta_s = np.full(n, np.nan)
    expected_1d = np.full(n, np.nan)
    resid_1d = np.full(n, np.nan)

    # Regress using observations strictly before t to reduce look-ahead.
    for i in range(n):
        start = max(0, i - reg_window)
        end = i
        if end - start < min_obs:
            continue
        yy = y[start:end]
        mm = xm[start:end]
        ss = xs[start:end]
        mask = np.isfinite(yy) & np.isfinite(mm) & np.isfinite(ss)
        if mask.sum() < min_obs:
            continue
        X = np.column_stack([np.ones(mask.sum()), mm[mask], ss[mask]])
        try:
            coef, *_ = np.linalg.lstsq(X, yy[mask], rcond=None)
        except np.linalg.LinAlgError:
            continue
        alpha[i], beta_m[i], beta_s[i] = coef
        if np.isfinite(y[i]) and np.isfinite(xm[i]) and np.isfinite(xs[i]):
            expected_1d[i] = alpha[i] + beta_m[i] * xm[i] + beta_s[i] * xs[i]
            resid_1d[i] = y[i] - expected_1d[i]

    x["alpha"] = alpha
    x["beta_market"] = beta_m
    x["beta_sector"] = beta_s
    x["expected_ret_1d"] = expected_1d
    x["resid_1d"] = resid_1d

    resid_vol_1d = pd.Series(resid_1d, index=x.index).rolling(60, min_periods=30).std().shift(1)
    x["resid_vol_5d"] = resid_vol_1d * math.sqrt(5)
    x["expected_ret_5d"] = (x["alpha"] * 5) + (x["beta_market"] * x["market_ret_5d"]) + (x["beta_sector"] * x["sector_ret_5d"])
    x["resid_5d"] = x["ret_5d"] - x["expected_ret_5d"]
    x["resid_z"] = x["resid_5d"] / x["resid_vol_5d"]
    return x


def add_technical_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values(["code", "date"]).copy()
    g = df.groupby("code", group_keys=False)

    df["avg_tv_20"] = g["trading_value"].transform(lambda s: s.rolling(20, min_periods=10).mean())
    tv_mean_prev20 = g["trading_value"].transform(lambda s: s.rolling(20, min_periods=10).mean().shift(1))
    tv_std_prev20 = g["trading_value"].transform(lambda s: s.rolling(20, min_periods=10).std().shift(1))
    df["tv_z"] = (df["trading_value"] - tv_mean_prev20) / tv_std_prev20.replace(0, np.nan)

    vol20 = g["ret_1d"].transform(lambda s: s.rolling(20, min_periods=10).std().shift(1))
    df["vol_adj_drop"] = df["ret_5d"] / (vol20 * math.sqrt(5)).replace(0, np.nan)

    high60 = g["close"].transform(lambda s: s.rolling(60, min_periods=20).max())
    df["drawdown_from_60h"] = df["close"] / high60 - 1
    ma120 = g["close"].transform(lambda s: s.rolling(120, min_periods=60).mean())
    df["ma120_gap"] = df["close"] / ma120 - 1

    df["simple_excess"] = df["ret_5d"] - df["market_ret_5d"] - df["sector_ret_5d"]
    return df


def add_rebound_memory_one_stock(x: pd.DataFrame, signal_threshold: float = -2.0, rebound_days: int = 20,
                                 rebound_target: float = 0.08) -> pd.DataFrame:
    x = x.sort_values("date").copy()
    close = x["close"].to_numpy(dtype=float)
    resid_z = x["resid_z"].to_numpy(dtype=float)
    n = len(x)
    signal = np.isfinite(resid_z) & (resid_z <= signal_threshold)
    success = np.zeros(n, dtype=float)
    for i in range(n):
        if not signal[i] or not np.isfinite(close[i]) or close[i] <= 0:
            continue
        end = min(n, i + rebound_days + 1)
        if i + 1 >= end:
            continue
        future_max = np.nanmax(close[i + 1:end])
        if np.isfinite(future_max) and (future_max / close[i] - 1 >= rebound_target):
            success[i] = 1.0

    # At date t, only use events whose 20-day future is already known.
    known_signal = pd.Series(signal.astype(float), index=x.index).shift(rebound_days).fillna(0.0)
    known_success = pd.Series(success, index=x.index).shift(rebound_days).fillna(0.0)
    cum_sig = known_signal.cumsum()
    cum_suc = known_success.cumsum()
    memory = np.where(cum_sig > 0, cum_suc / cum_sig, 0.5)  # neutral before enough history
    count = cum_sig
    x["rebound_memory"] = memory
    x["rebound_memory_count"] = count
    return x


def add_market_crisis_flags(df: pd.DataFrame) -> pd.DataFrame:
    # Daily universe-level 20d returns by market based on cap-weighted 1d returns.
    m1 = df.groupby(["date", "market"]).apply(lambda x: weighted_average_return(x, "ret_1d")).rename("mkt_daily").reset_index()
    m1 = m1.sort_values(["market", "date"])
    m1["mkt_20d"] = m1.groupby("market")["mkt_daily"].transform(lambda s: (1 + s).rolling(20, min_periods=10).apply(np.prod, raw=True) - 1)
    kospi = m1[m1["market"] == "KOSPI"][["date", "mkt_20d"]].rename(columns={"mkt_20d": "kospi_20d"})
    kosdaq = m1[m1["market"] == "KOSDAQ"][["date", "mkt_20d"]].rename(columns={"mkt_20d": "kosdaq_20d"})
    flags = pd.merge(kospi, kosdaq, on="date", how="outer")
    flags["market_crisis"] = (flags["kospi_20d"] <= -0.08) | (flags["kosdaq_20d"] <= -0.10)
    flags["market_warning"] = (flags["kospi_20d"] <= -0.05) | (flags["kosdaq_20d"] <= -0.07)
    df = df.merge(flags[["date", "kospi_20d", "kosdaq_20d", "market_crisis", "market_warning"]], on="date", how="left")
    df["market_crisis"] = df["market_crisis"].fillna(False)
    df["market_warning"] = df["market_warning"].fillna(False)
    return df


def prepare_features(df: pd.DataFrame, reg_window: int, min_obs: int) -> pd.DataFrame:
    print("[1/5] Adding market/sector returns...")
    df = add_market_sector_returns(df)
    print("[2/5] Rolling regression residuals. This can take time on large universes...")
    df = df.groupby("code", group_keys=False).apply(
        lambda x: rolling_ols_residuals_one_stock(x, reg_window=reg_window, min_obs=min_obs)
    )
    print("[3/5] Adding technical features...")
    df = add_technical_features(df)
    print("[4/5] Adding rebound memory...")
    df = df.groupby("code", group_keys=False).apply(add_rebound_memory_one_stock)
    print("[5/5] Adding market crisis flags...")
    df = add_market_crisis_flags(df)
    df = add_signal_and_score(df)
    return df.sort_values(["date", "code"]).reset_index(drop=True)


def add_signal_and_score(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # Entry filters
    df["pass_base"] = (
        (df["ret_5d"] <= -0.10) &
        (df["market_ret_5d"] > -0.05) &
        (df["sector_ret_5d"] > -0.06) &
        (df["simple_excess"] <= -0.06) &
        (df["resid_z"] <= -2.0) &
        (df["avg_tv_20"] >= 3_000_000_000) &
        (df["market_cap"] >= 100_000_000_000) &
        (df["drawdown_from_60h"].between(-0.45, -0.15))
    )

    # Optional extra quality flags
    df["pass_tv_z"] = df["tv_z"].between(1.5, 4.0)
    df["pass_vol_adj"] = df["vol_adj_drop"] <= -2.0

    # Champion score components. Use clipped/normalized terms so one field does not dominate too hard.
    resid_score = (-df["resid_z"]).clip(0, 6) * 12
    excess_score = (-df["simple_excess"] * 100).clip(0, 25) * 2
    tv_score = np.where(df["tv_z"].between(1.5, 4.0), 15 - (df["tv_z"] - 2.5).abs() * 3, 0)
    tv_score = pd.Series(tv_score, index=df.index).clip(0, 15)
    memory_score = df["rebound_memory"].fillna(0.5).clip(0, 1) * 25
    cap_score = np.log10(df["market_cap"].replace(0, np.nan)).replace([np.inf, -np.inf], np.nan).fillna(0)
    cap_score = ((cap_score - 11) * 5).clip(0, 15)  # roughly 1,000억+ gets points

    trend_penalty = np.where(df["ma120_gap"] <= -0.30, 20, 0)
    liquidity_penalty = np.where((df["avg_tv_20"] < 3_000_000_000) | (df["tv_z"] < 0), 15, 0)
    crisis_penalty = np.where(df["market_crisis"], 25, np.where(df["market_warning"], 10, 0))

    df["idio_score"] = (
        resid_score.fillna(0) + excess_score.fillna(0) + tv_score.fillna(0) +
        memory_score.fillna(0) + cap_score.fillna(0) -
        trend_penalty - liquidity_penalty - crisis_penalty
    )

    df["pass_champion"] = df["pass_base"] & df["pass_tv_z"] & df["pass_vol_adj"]
    return df


def rebalance_dates(df: pd.DataFrame) -> List[pd.Timestamp]:
    d = pd.DataFrame({"date": sorted(df["date"].unique())})
    d["date"] = pd.to_datetime(d["date"])
    iso = d["date"].dt.isocalendar()
    d["year"] = iso.year.astype(int)
    d["week"] = iso.week.astype(int)
    # first trading day of each ISO week; handles Monday holidays.
    return d.groupby(["year", "week"])["date"].min().tolist()


def get_exit_rule_params(exit_rule: str) -> Tuple[Optional[float], Optional[float], int, bool]:
    if exit_rule == "fixed20":
        return None, None, 20, False
    if exit_rule == "tp12_sl10_max40":
        return 0.12, -0.10, 40, True
    if exit_rule == "tp15_sl15_max60":
        return 0.15, -0.15, 60, True
    raise ValueError(f"Unknown exit_rule: {exit_rule}")


def max_drawdown(equity: pd.Series) -> float:
    eq = equity.astype(float)
    peak = eq.cummax()
    dd = eq / peak - 1
    return float(dd.min()) if len(dd) else np.nan


def longest_recovery_days(equity_df: pd.DataFrame) -> int:
    eq = equity_df["equity"].astype(float).to_numpy()
    dates = pd.to_datetime(equity_df["date"]).to_numpy()
    peak = -np.inf
    peak_date = None
    current_underwater_start = None
    max_days = 0
    for v, d in zip(eq, dates):
        if v >= peak:
            if current_underwater_start is not None:
                days = (pd.Timestamp(d) - pd.Timestamp(current_underwater_start)).days
                max_days = max(max_days, days)
                current_underwater_start = None
            peak = v
            peak_date = d
        else:
            if current_underwater_start is None:
                current_underwater_start = peak_date
    if current_underwater_start is not None:
        days = (pd.Timestamp(dates[-1]) - pd.Timestamp(current_underwater_start)).days
        max_days = max(max_days, days)
    return int(max_days)


def run_backtest(df: pd.DataFrame, config: BacktestConfig, market_crisis_mode: str) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, float]]:
    dates = sorted(pd.to_datetime(df["date"].unique()))
    date_set = set(dates)
    rb_dates = set(rebalance_dates(df))
    by_date = {d: x.set_index("code") for d, x in df.groupby("date")}
    signal_by_date = {d: x for d, x in df[df["pass_champion"]].groupby("date")}

    cash = config.initial_cash
    positions: List[Position] = []
    trades: List[Dict] = []
    equity_rows: List[Dict] = []
    tp, sl, max_hold, check_tp_sl = get_exit_rule_params(config.exit_rule)

    for current_date in dates:
        day_df = by_date[current_date]

        # 1) exits first
        still_positions: List[Position] = []
        for pos in positions:
            if pos.code not in day_df.index:
                # no price; hold but mark stale
                still_positions.append(pos)
                continue
            row = day_df.loc[pos.code]
            current_price = safe_float(row[config.exit_price_col])
            if not np.isfinite(current_price) or current_price <= 0:
                still_positions.append(pos)
                continue
            hold_days = sum(1 for d in dates if pos.entry_date < d <= current_date)
            ret = current_price / pos.entry_price - 1
            exit_reason = None
            if config.exit_rule == "fixed20" and hold_days >= max_hold:
                exit_reason = "FIXED_20D"
            elif check_tp_sl:
                if ret >= tp:
                    exit_reason = "TAKE_PROFIT"
                elif ret <= sl:
                    exit_reason = "STOP_LOSS"
                elif hold_days >= max_hold:
                    exit_reason = "MAX_HOLD"
            if exit_reason:
                gross = pos.shares * current_price
                sell_cost = gross * (config.commission_rate + config.sell_tax_rate)
                net = gross - sell_cost
                cash += net
                pnl = net - pos.invested
                trades.append({
                    "portfolio_size": config.portfolio_size,
                    "exit_rule": config.exit_rule,
                    "code": pos.code,
                    "name": pos.name,
                    "entry_date": pos.entry_date,
                    "exit_date": current_date,
                    "entry_price": pos.entry_price,
                    "exit_price": current_price,
                    "shares": pos.shares,
                    "invested": pos.invested,
                    "gross_exit_value": gross,
                    "sell_cost": sell_cost,
                    "pnl": pnl,
                    "return_pct": pnl / pos.invested if pos.invested else np.nan,
                    "hold_days": hold_days,
                    "exit_reason": exit_reason,
                    "entry_score": pos.score,
                    **{f"entry_{k}": v for k, v in pos.entry_signal.items()},
                })
            else:
                still_positions.append(pos)
        positions = still_positions

        # 2) weekly new entries, fill empty slots only
        if current_date in rb_dates:
            market_crisis = False
            market_warning = False
            if current_date in by_date:
                tmp = by_date[current_date]
                if "market_crisis" in tmp.columns:
                    market_crisis = bool(tmp["market_crisis"].any())
                if "market_warning" in tmp.columns:
                    market_warning = bool(tmp["market_warning"].any())

            effective_slots = config.portfolio_size
            if market_crisis_mode == "block" and market_crisis:
                effective_slots = len(positions)  # no new entries
            elif market_crisis_mode == "shrink":
                if market_crisis:
                    effective_slots = 0
                elif market_warning:
                    effective_slots = min(config.portfolio_size, 10)

            empty_slots = max(0, effective_slots - len(positions))
            if empty_slots > 0 and current_date in signal_by_date:
                held = {p.code for p in positions}
                candidates = signal_by_date[current_date].copy()
                candidates = candidates[~candidates["code"].isin(held)]
                candidates = candidates.sort_values(["idio_score", "avg_tv_20", "market_cap"], ascending=[False, False, False])
                for _, row in candidates.head(empty_slots).iterrows():
                    entry_price = safe_float(row[config.entry_price_col])
                    if not np.isfinite(entry_price) or entry_price <= 0:
                        continue
                    shares = int(config.slot_cash // entry_price)
                    if shares <= 0:
                        continue
                    gross = shares * entry_price
                    buy_cost = gross * config.commission_rate
                    total_cost = gross + buy_cost
                    if total_cost > cash:
                        continue
                    cash -= total_cost
                    positions.append(Position(
                        code=row["code"],
                        name=row["name"],
                        entry_date=current_date,
                        entry_price=entry_price,
                        shares=shares,
                        invested=total_cost,
                        slot_cash=config.slot_cash,
                        score=safe_float(row["idio_score"]),
                        entry_signal={
                            "ret_5d": safe_float(row["ret_5d"]),
                            "market_ret_5d": safe_float(row["market_ret_5d"]),
                            "sector_ret_5d": safe_float(row["sector_ret_5d"]),
                            "simple_excess": safe_float(row["simple_excess"]),
                            "resid_z": safe_float(row["resid_z"]),
                            "tv_z": safe_float(row["tv_z"]),
                            "vol_adj_drop": safe_float(row["vol_adj_drop"]),
                            "rebound_memory": safe_float(row["rebound_memory"]),
                            "drawdown_from_60h": safe_float(row["drawdown_from_60h"]),
                            "ma120_gap": safe_float(row["ma120_gap"]),
                        },
                    ))

        # 3) equity mark-to-market
        stock_value = 0.0
        held_codes = []
        for pos in positions:
            if pos.code in day_df.index:
                px = safe_float(day_df.loc[pos.code, "close"])
                if np.isfinite(px) and px > 0:
                    stock_value += pos.shares * px
                    held_codes.append(pos.code)
        equity = cash + stock_value
        equity_rows.append({
            "date": current_date,
            "portfolio_size": config.portfolio_size,
            "exit_rule": config.exit_rule,
            "cash": cash,
            "stock_value": stock_value,
            "equity": equity,
            "positions": len(positions),
            "held_codes": ";".join(held_codes),
        })

    equity_df = pd.DataFrame(equity_rows)
    trades_df = pd.DataFrame(trades)
    if equity_df.empty:
        summary = {}
    else:
        start_eq = config.initial_cash
        end_eq = float(equity_df["equity"].iloc[-1])
        start_date = pd.to_datetime(equity_df["date"].iloc[0])
        end_date = pd.to_datetime(equity_df["date"].iloc[-1])
        years = (end_date - start_date).days / 365.25
        total_ret = end_eq / start_eq - 1
        cagr = (end_eq / start_eq) ** (1 / years) - 1 if years > 0 and start_eq > 0 else np.nan
        daily_ret = equity_df["equity"].pct_change()
        win_trades = (trades_df["pnl"] > 0).sum() if not trades_df.empty else 0
        total_trades = len(trades_df) if not trades_df.empty else 0
        summary = {
            "portfolio_size": config.portfolio_size,
            "exit_rule": config.exit_rule,
            "initial_cash": start_eq,
            "final_equity": end_eq,
            "total_return_pct": total_ret * 100,
            "cagr_pct": cagr * 100,
            "mdd_pct": max_drawdown(equity_df["equity"]) * 100,
            "worst_daily_pct": float(daily_ret.min() * 100),
            "longest_recovery_days": longest_recovery_days(equity_df),
            "total_trades": total_trades,
            "win_trades": int(win_trades),
            "win_rate_pct": (win_trades / total_trades * 100) if total_trades else np.nan,
            "avg_trade_return_pct": float(trades_df["return_pct"].mean() * 100) if total_trades else np.nan,
            "median_trade_return_pct": float(trades_df["return_pct"].median() * 100) if total_trades else np.nan,
        }
    return equity_df, trades_df, summary


def yearly_returns(equity_df: pd.DataFrame) -> pd.DataFrame:
    if equity_df.empty:
        return pd.DataFrame()
    x = equity_df.copy()
    x["date"] = pd.to_datetime(x["date"])
    x["year"] = x["date"].dt.year
    rows = []
    for (ps, er, y), g in x.groupby(["portfolio_size", "exit_rule", "year"]):
        g = g.sort_values("date")
        start = g["equity"].iloc[0]
        end = g["equity"].iloc[-1]
        rows.append({
            "portfolio_size": ps,
            "exit_rule": er,
            "year": y,
            "start_equity": start,
            "end_equity": end,
            "year_return_pct": (end / start - 1) * 100 if start else np.nan,
        })
    return pd.DataFrame(rows)


def build_benchmarks(df: pd.DataFrame, start_cash: float = 100_000_000) -> pd.DataFrame:
    # Universe-derived cap-weight benchmarks, not official indices.
    daily = df.groupby(["date", "market"]).apply(lambda x: weighted_average_return(x, "ret_1d")).rename("ret_1d").reset_index()
    daily = daily.dropna(subset=["ret_1d"]).sort_values(["market", "date"])
    daily["equity"] = daily.groupby("market")["ret_1d"].transform(lambda s: start_cash * (1 + s).cumprod())
    daily["benchmark"] = daily["market"] + "_UNIVERSE_CAP_WEIGHTED"
    return daily[["date", "benchmark", "ret_1d", "equity"]]


def save_outputs(outdir: str, df: pd.DataFrame, all_equity: pd.DataFrame, all_trades: pd.DataFrame,
                 summary_rows: List[Dict], args: argparse.Namespace) -> None:
    Path(outdir).mkdir(parents=True, exist_ok=True)
    pd.DataFrame(summary_rows).to_csv(os.path.join(outdir, "idio_300_v3_summary.csv"), index=False, encoding="utf-8-sig")
    all_trades.to_csv(os.path.join(outdir, "idio_300_v3_trades.csv"), index=False, encoding="utf-8-sig")
    all_equity.to_csv(os.path.join(outdir, "idio_300_v3_equity_curve.csv"), index=False, encoding="utf-8-sig")
    yr = yearly_returns(all_equity)
    yr.to_csv(os.path.join(outdir, "idio_300_v3_yearly_return.csv"), index=False, encoding="utf-8-sig")

    signal_cols = [
        "date", "code", "name", "market", "sector", "close", "ret_5d", "market_ret_5d", "sector_ret_5d",
        "simple_excess", "resid_z", "tv_z", "vol_adj_drop", "rebound_memory", "rebound_memory_count",
        "avg_tv_20", "market_cap", "drawdown_from_60h", "ma120_gap", "kospi_20d", "kosdaq_20d",
        "market_warning", "market_crisis", "pass_base", "pass_tv_z", "pass_vol_adj", "pass_champion", "idio_score",
    ]
    signal_df = df[signal_cols].copy()
    if not args.save_all_signals:
        signal_df = signal_df[signal_df["pass_base"] | signal_df["pass_champion"]]
    signal_df.to_csv(os.path.join(outdir, "idio_300_v3_signals.csv"), index=False, encoding="utf-8-sig")

    bench = build_benchmarks(df)
    bench.to_csv(os.path.join(outdir, "idio_300_v3_benchmarks.csv"), index=False, encoding="utf-8-sig")


def main() -> None:
    args = parse_args()
    portfolio_sizes = [int(x.strip()) for x in args.portfolio_sizes.split(",") if x.strip()]
    exit_rules = ["fixed20", "tp12_sl10_max40", "tp15_sl15_max60"]

    print("Loading data...")
    raw = load_data(args.input, args.start, args.end, allow_reits=args.allow_reits)
    if raw.empty:
        raise ValueError("No data after filters. Check date range and universe filters.")

    features = prepare_features(raw, reg_window=args.reg_window, min_obs=args.min_reg_obs)

    all_equity = []
    all_trades = []
    summary_rows = []
    for ps in portfolio_sizes:
        for er in exit_rules:
            print(f"Running backtest: {ps} slots / {er}")
            cfg = BacktestConfig(
                portfolio_size=ps,
                slot_cash=args.slot_cash,
                exit_rule=er,
                commission_rate=args.commission_rate,
                sell_tax_rate=args.sell_tax_rate,
                entry_price_col=args.entry_price,
                exit_price_col=args.exit_price,
            )
            eq, tr, sm = run_backtest(features, cfg, market_crisis_mode=args.market_crisis_mode)
            if not eq.empty:
                all_equity.append(eq)
            if not tr.empty:
                all_trades.append(tr)
            if sm:
                summary_rows.append(sm)

    eq_all = pd.concat(all_equity, ignore_index=True) if all_equity else pd.DataFrame()
    tr_all = pd.concat(all_trades, ignore_index=True) if all_trades else pd.DataFrame()
    save_outputs(args.outdir, features, eq_all, tr_all, summary_rows, args)

    print("\nDone.")
    print(f"Output directory: {args.outdir}")
    if summary_rows:
        print(pd.DataFrame(summary_rows).to_string(index=False))





# =====================================================
# Streamlit UI + Auto Data Builder
# =====================================================
import io
import tempfile
import zipfile
import time
from datetime import datetime
import streamlit as st

APP_TITLE = "IDIO 300 v3 Champion 자동수집 백테스터"

EXIT_RULE_LABELS = {
    "fixed20": "20거래일 고정 보유",
    "tp12_sl10_max40": "+12% 익절 / -10% 손절 / 최대 40거래일",
    "tp15_sl15_max60": "+15% 익절 / -15% 손절 / 최대 60거래일",
}

KOR_COL_RENAME = {
    "시가": "open",
    "고가": "high",
    "저가": "low",
    "종가": "close",
    "거래량": "volume",
    "거래대금": "trading_value",
    "시가총액": "market_cap",
    "상장주식수": "shares_outstanding",
}


def _to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8-sig")


def _normalize_code(x) -> str:
    return str(x).strip().zfill(6)


def _load_sector_map(uploaded_sector_file) -> dict:
    """Optional CSV: code,sector. If absent, sector falls back to market."""
    if uploaded_sector_file is None:
        return {}
    mp = pd.read_csv(uploaded_sector_file, dtype={"code": str})
    if "code" not in mp.columns or "sector" not in mp.columns:
        raise ValueError("섹터맵 CSV는 code, sector 컬럼이 필요합니다.")
    mp["code"] = mp["code"].map(_normalize_code)
    mp["sector"] = mp["sector"].fillna("UNKNOWN").astype(str)
    return dict(zip(mp["code"], mp["sector"]))


@st.cache_data(show_spinner=False)
def _ticker_name_cached(code: str) -> str:
    try:
        from pykrx import stock
        return stock.get_market_ticker_name(code) or code
    except Exception:
        return code


def _safe_pykrx_import():
    try:
        from pykrx import stock
        return stock
    except Exception as e:
        raise RuntimeError(
            "pykrx가 설치되어 있지 않습니다. 터미널에서 `pip install pykrx` 실행 후 다시 켜세요."
        ) from e


def collect_krx_daily_panel(
    start: str,
    end: str,
    markets: list[str],
    sector_map: dict,
    sleep_sec: float = 0.15,
    cache_dir: str | Path = "./idio_krx_cache",
    max_dates: int | None = None,
) -> pd.DataFrame:
    """
    Build an IDIO-compatible daily panel using pykrx.

    Notes:
    - This is a free-data quick-test builder, not a perfect institutional database.
    - Sector falls back to market when no sector map is supplied.
    - Management issue / trading halt history is not perfectly reconstructed here.
    """
    stock = _safe_pykrx_import()
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)

    dates = pd.bdate_range(pd.to_datetime(start), pd.to_datetime(end))
    if max_dates:
        dates = dates[-int(max_dates):]

    frames = []
    progress = st.progress(0)
    status = st.empty()
    total_steps = len(dates) * max(len(markets), 1)
    step = 0
    name_cache: dict[str, str] = {}

    for d in dates:
        ymd = d.strftime("%Y%m%d")
        for market in markets:
            step += 1
            progress.progress(step / max(total_steps, 1))
            status.write(f"KRX 자동수집 중: {ymd} / {market}")
            cache_path = cache_dir / f"krx_{ymd}_{market}.csv"
            if cache_path.exists():
                day = pd.read_csv(cache_path, dtype={"code": str})
                if not day.empty:
                    frames.append(day)
                continue

            try:
                ohlcv = stock.get_market_ohlcv_by_ticker(ymd, market=market)
                if ohlcv is None or ohlcv.empty:
                    continue
                ohlcv = ohlcv.reset_index().rename(columns={"티커": "code", **KOR_COL_RENAME})
                if "code" not in ohlcv.columns:
                    ohlcv = ohlcv.rename(columns={ohlcv.columns[0]: "code"})
                ohlcv["code"] = ohlcv["code"].map(_normalize_code)

                # Market cap by ticker. If this call fails, market_cap remains NaN.
                try:
                    cap = stock.get_market_cap_by_ticker(ymd, market=market)
                    cap = cap.reset_index().rename(columns={"티커": "code", **KOR_COL_RENAME})
                    if "code" not in cap.columns:
                        cap = cap.rename(columns={cap.columns[0]: "code"})
                    cap["code"] = cap["code"].map(_normalize_code)
                    cap_cols = [c for c in ["code", "market_cap"] if c in cap.columns]
                    day = ohlcv.merge(cap[cap_cols], on="code", how="left", suffixes=("", "_cap"))
                    if "market_cap_cap" in day.columns and "market_cap" not in day.columns:
                        day = day.rename(columns={"market_cap_cap": "market_cap"})
                    elif "market_cap_cap" in day.columns:
                        day["market_cap"] = day["market_cap"].fillna(day["market_cap_cap"])
                        day = day.drop(columns=["market_cap_cap"])
                except Exception:
                    day = ohlcv.copy()
                    if "market_cap" not in day.columns:
                        day["market_cap"] = np.nan

                day["date"] = pd.to_datetime(d)
                day["market"] = market
                # name lookup is slow, so cache per code.
                codes = day["code"].dropna().unique().tolist()
                for c in codes:
                    if c not in name_cache:
                        name_cache[c] = _ticker_name_cached(c)
                day["name"] = day["code"].map(name_cache).fillna(day["code"])
                day["sector"] = day["code"].map(sector_map).fillna(day["market"])

                # Column cleanup
                for col in ["open", "high", "low", "close", "volume", "trading_value", "market_cap"]:
                    if col not in day.columns:
                        day[col] = np.nan
                day = day[["date", "code", "name", "market", "sector", "open", "high", "low", "close", "volume", "trading_value", "market_cap"]]
                for col in ["open", "high", "low", "close", "volume", "trading_value", "market_cap"]:
                    day[col] = pd.to_numeric(day[col], errors="coerce")
                day = day[(day["close"] > 0) & (day["open"] > 0)]
                day.to_csv(cache_path, index=False, encoding="utf-8-sig")
                if not day.empty:
                    frames.append(day)
                if sleep_sec > 0:
                    time.sleep(float(sleep_sec))
            except Exception as e:
                # Market holiday or temporary KRX failure. Skip but keep going.
                status.write(f"건너뜀: {ymd} / {market} / {e}")
                continue

    progress.empty()
    status.empty()
    if not frames:
        return pd.DataFrame(columns=REQUIRED_COLUMNS)
    out = pd.concat(frames, ignore_index=True)
    out["date"] = pd.to_datetime(out["date"])
    out["code"] = out["code"].map(_normalize_code)
    out = out.drop_duplicates(["date", "code"], keep="last")
    out = out.sort_values(["date", "code"]).reset_index(drop=True)
    return out


def run_idio_from_dataframe(
    data: pd.DataFrame,
    start: str,
    end: Optional[str],
    slot_cash: float,
    portfolio_sizes: List[int],
    exit_rules: List[str],
    reg_window: int,
    min_reg_obs: int,
    market_crisis_mode: str,
    commission_rate: float,
    sell_tax_rate: float,
    entry_price: str,
    exit_price: str,
    allow_reits: bool,
    save_all_signals: bool,
):
    with tempfile.TemporaryDirectory() as td:
        input_path = Path(td) / "idio_input.csv"
        data.to_csv(input_path, index=False, encoding="utf-8-sig")
        return run_idio_streamlit_uploaded(
            uploaded_file=type("UploadedLike", (), {"getvalue": lambda self: input_path.read_bytes()})(),
            start=start,
            end=end,
            slot_cash=slot_cash,
            portfolio_sizes=portfolio_sizes,
            exit_rules=exit_rules,
            reg_window=reg_window,
            min_reg_obs=min_reg_obs,
            market_crisis_mode=market_crisis_mode,
            commission_rate=commission_rate,
            sell_tax_rate=sell_tax_rate,
            entry_price=entry_price,
            exit_price=exit_price,
            allow_reits=allow_reits,
            save_all_signals=save_all_signals,
        )


def run_idio_streamlit_uploaded(
    uploaded_file,
    start: str,
    end: Optional[str],
    slot_cash: float,
    portfolio_sizes: List[int],
    exit_rules: List[str],
    reg_window: int,
    min_reg_obs: int,
    market_crisis_mode: str,
    commission_rate: float,
    sell_tax_rate: float,
    entry_price: str,
    exit_price: str,
    allow_reits: bool,
    save_all_signals: bool,
):
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        input_path = td_path / "idio_input.csv"
        input_path.write_bytes(uploaded_file.getvalue())

        st.info("데이터 로딩 및 기본 필터 적용 중")
        raw = load_data(str(input_path), start, end, allow_reits=allow_reits)
        if raw.empty:
            raise ValueError("필터 후 데이터가 없습니다. 기간/컬럼/유니버스를 확인하세요.")

        st.success(f"로드 완료: {len(raw):,}행 / {raw['code'].nunique():,}종목")
        if raw["sector"].nunique() <= 2:
            st.warning("섹터맵이 없어서 sector가 시장명(KOSPI/KOSDAQ) 위주입니다. 회귀의 섹터 효과가 약해진 v3-lite 결과로 보세요.")
        st.info("지표 계산 중: 시장·섹터 수익률 → 회귀잔차 Z점수 → 반등기억 → 시장위기 필터")
        features = prepare_features(raw, reg_window=reg_window, min_obs=min_reg_obs)

        all_equity = []
        all_trades = []
        summary_rows = []
        total_runs = len(portfolio_sizes) * len(exit_rules)
        progress = st.progress(0)
        run_no = 0

        for ps in portfolio_sizes:
            for er in exit_rules:
                run_no += 1
                st.write(f"백테스트 실행 중: {ps}종 / {EXIT_RULE_LABELS.get(er, er)}")
                cfg = BacktestConfig(
                    portfolio_size=ps,
                    slot_cash=slot_cash,
                    exit_rule=er,
                    commission_rate=commission_rate,
                    sell_tax_rate=sell_tax_rate,
                    entry_price_col=entry_price,
                    exit_price_col=exit_price,
                )
                eq, tr, sm = run_backtest(features, cfg, market_crisis_mode=market_crisis_mode)
                if not eq.empty:
                    all_equity.append(eq)
                if not tr.empty:
                    all_trades.append(tr)
                if sm:
                    summary_rows.append(sm)
                progress.progress(run_no / max(total_runs, 1))

        eq_all = pd.concat(all_equity, ignore_index=True) if all_equity else pd.DataFrame()
        tr_all = pd.concat(all_trades, ignore_index=True) if all_trades else pd.DataFrame()
        summary_df = pd.DataFrame(summary_rows)
        yearly_df = yearly_returns(eq_all)

        signal_cols = [
            "date", "code", "name", "market", "sector", "close", "ret_5d", "market_ret_5d", "sector_ret_5d",
            "simple_excess", "resid_z", "tv_z", "vol_adj_drop", "rebound_memory", "rebound_memory_count",
            "avg_tv_20", "market_cap", "drawdown_from_60h", "ma120_gap", "kospi_20d", "kosdaq_20d",
            "market_warning", "market_crisis", "pass_base", "pass_tv_z", "pass_vol_adj", "pass_champion", "idio_score",
        ]
        existing_signal_cols = [c for c in signal_cols if c in features.columns]
        signals_df = features[existing_signal_cols].copy()
        if not save_all_signals and "pass_base" in signals_df.columns and "pass_champion" in signals_df.columns:
            signals_df = signals_df[signals_df["pass_base"] | signals_df["pass_champion"]]
        bench_df = build_benchmarks(features)

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("idio_300_v3_summary.csv", _to_csv_bytes(summary_df))
            zf.writestr("idio_300_v3_trades.csv", _to_csv_bytes(tr_all))
            zf.writestr("idio_300_v3_equity_curve.csv", _to_csv_bytes(eq_all))
            zf.writestr("idio_300_v3_yearly_return.csv", _to_csv_bytes(yearly_df))
            zf.writestr("idio_300_v3_signals.csv", _to_csv_bytes(signals_df))
            zf.writestr("idio_300_v3_benchmarks.csv", _to_csv_bytes(bench_df))
        zip_buffer.seek(0)
        return summary_df, tr_all, eq_all, yearly_df, signals_df, bench_df, zip_buffer, raw


def render_results(summary_df, tr_all, eq_all, yearly_df, signals_df, bench_df, zip_buffer):
    st.success("백테스트 완료")
    if not summary_df.empty:
        show_cols = [
            "portfolio_size", "exit_rule", "initial_cash", "final_equity", "total_return_pct",
            "cagr_pct", "mdd_pct", "worst_daily_pct", "longest_recovery_days",
            "total_trades", "win_rate_pct", "avg_trade_return_pct", "median_trade_return_pct",
        ]
        show_cols = [c for c in show_cols if c in summary_df.columns]
        st.subheader("요약 결과")
        st.dataframe(summary_df[show_cols], use_container_width=True)

        best = summary_df.sort_values(["cagr_pct", "mdd_pct"], ascending=[False, False]).head(1).iloc[0]
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("최고 CAGR 조합", f"{int(best['portfolio_size'])}종 / {best['exit_rule']}")
        m2.metric("CAGR", f"{best['cagr_pct']:.2f}%")
        m3.metric("MDD", f"{best['mdd_pct']:.2f}%")
        m4.metric("최종자산", f"{best['final_equity']:,.0f}원")

    tab1, tab2, tab3, tab4, tab5 = st.tabs(["연도별", "매매내역", "자산곡선", "신호", "벤치마크"])
    with tab1:
        st.dataframe(yearly_df, use_container_width=True)
    with tab2:
        st.dataframe(tr_all.tail(1000), use_container_width=True)
    with tab3:
        st.dataframe(eq_all.tail(1000), use_container_width=True)
    with tab4:
        st.dataframe(signals_df.tail(1000), use_container_width=True)
    with tab5:
        st.dataframe(bench_df.tail(1000), use_container_width=True)

    st.download_button(
        "IDIO 결과 ZIP 다운로드",
        data=zip_buffer.getvalue(),
        file_name="idio_300_v3_champion_results.zip",
        mime="application/zip",
    )


def render_streamlit_app():
    st.set_page_config(page_title=APP_TITLE, layout="wide")
    st.title(APP_TITLE)
    st.caption("CSV가 없어도 pykrx로 KRX 데이터를 자동수집해서 1차 백테스트를 돌립니다. 정밀 검증은 별도 생존편향 제거 DB가 필요합니다.")

    with st.expander("중요: 자동수집 모드 한계", expanded=True):
        st.markdown(
            """
- 자동수집은 무료 데이터 기반 **1차 테스트용**입니다.
- 상장폐지 종목, 관리종목/거래정지 이력, 정확한 과거 섹터 분류가 완벽히 복원되지 않을 수 있습니다.
- 섹터맵 CSV를 넣지 않으면 `sector = KOSPI/KOSDAQ`으로 대체되어 **v3-lite** 결과가 됩니다.
- 2010년부터 전체 KOSPI/KOSDAQ을 받으면 오래 걸릴 수 있습니다. 먼저 최근 3~5년으로 테스트 후 전체 기간을 돌리세요.
            """
        )
        st.code("pip install streamlit pandas numpy pykrx")

    source_mode = st.radio("데이터 방식", ["자동수집(pykrx)", "CSV 업로드"], horizontal=True)

    st.subheader("백테스트 설정")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        start = st.text_input("시작일", value="2010-01-04")
        end = st.text_input("종료일", value=datetime.today().strftime("%Y-%m-%d"))
        end_arg = end.strip() or None
    with c2:
        slot_cash = st.number_input("종목당 투자금", value=3_000_000, step=100_000, format="%d")
        ps_options = st.multiselect("포트 구성", options=[10, 20], default=[10, 20])
    with c3:
        selected_exit_labels = st.multiselect(
            "매도 방식",
            options=list(EXIT_RULE_LABELS.values()),
            default=list(EXIT_RULE_LABELS.values()),
        )
        selected_exit_rules = [k for k, v in EXIT_RULE_LABELS.items() if v in selected_exit_labels]
    with c4:
        market_crisis_mode = st.selectbox("시장위기 필터", options=["block", "shrink", "penalty"], index=0,
                                          format_func=lambda x: {"block": "위기장 신규진입 금지", "shrink": "위기/주의장 슬롯 축소", "penalty": "점수 패널티만"}[x])

    st.subheader("고급 설정")
    a1, a2, a3, a4 = st.columns(4)
    with a1:
        reg_window = st.number_input("회귀 윈도우", value=120, min_value=40, max_value=300, step=10)
        min_reg_obs = st.number_input("최소 회귀 관측치", value=80, min_value=30, max_value=250, step=10)
    with a2:
        commission_rate = st.number_input("수수료율/회", value=0.00015, step=0.00001, format="%.5f", help="예: 0.00015 = 0.015%")
        sell_tax_rate = st.number_input("매도세율", value=0.0018, step=0.0001, format="%.4f", help="일반주식 매도세 반영. ETF 아님")
    with a3:
        entry_price = st.selectbox("매수가 기준", options=["close", "open"], index=0)
        exit_price = st.selectbox("매도가 기준", options=["close", "open"], index=0)
    with a4:
        allow_reits = st.checkbox("리츠 제외 안 함", value=False)
        save_all_signals = st.checkbox("전체 신호행 저장", value=False, help="끄면 pass_base/pass_champion 후보만 저장")

    uploaded = None
    sector_uploaded = None
    auto_df = None

    if source_mode == "CSV 업로드":
        st.subheader("CSV 업로드")
        with st.expander("필요 CSV 컬럼", expanded=False):
            st.code("date,code,name,market,sector,open,high,low,close,volume,trading_value,market_cap")
        uploaded = st.file_uploader("코스피·코스닥 일봉 CSV 업로드", type=["csv"])
        can_run = uploaded is not None
    else:
        st.subheader("자동수집 설정")
        b1, b2, b3, b4 = st.columns(4)
        with b1:
            markets = st.multiselect("시장", options=["KOSPI", "KOSDAQ"], default=["KOSPI", "KOSDAQ"])
        with b2:
            sleep_sec = st.number_input("호출 간 대기초", value=0.15, min_value=0.0, max_value=2.0, step=0.05)
        with b3:
            max_dates_raw = st.number_input("최근 N영업일만 수집(0=전체)", value=0, min_value=0, step=50)
            max_dates = None if int(max_dates_raw) == 0 else int(max_dates_raw)
        with b4:
            cache_dir = st.text_input("캐시 폴더", value="./idio_krx_cache")
        sector_uploaded = st.file_uploader("선택: 섹터맵 CSV 업로드(code,sector)", type=["csv"], help="없으면 sector=market으로 대체됩니다.")
        st.warning("처음 전체 기간 수집은 매우 오래 걸릴 수 있습니다. 캐시가 쌓이면 다음 실행부터 빨라집니다.")
        can_run = True

    st.divider()
    run = st.button("IDIO 300 v3 Champion 실행", type="primary", disabled=not can_run)

    if run:
        if not ps_options:
            st.warning("포트 구성을 하나 이상 선택하세요.")
            return
        if not selected_exit_rules:
            st.warning("매도 방식을 하나 이상 선택하세요.")
            return
        try:
            if source_mode == "CSV 업로드":
                result = run_idio_streamlit_uploaded(
                    uploaded_file=uploaded,
                    start=start,
                    end=end_arg,
                    slot_cash=float(slot_cash),
                    portfolio_sizes=ps_options,
                    exit_rules=selected_exit_rules,
                    reg_window=int(reg_window),
                    min_reg_obs=int(min_reg_obs),
                    market_crisis_mode=market_crisis_mode,
                    commission_rate=float(commission_rate),
                    sell_tax_rate=float(sell_tax_rate),
                    entry_price=entry_price,
                    exit_price=exit_price,
                    allow_reits=allow_reits,
                    save_all_signals=save_all_signals,
                )
                summary_df, tr_all, eq_all, yearly_df, signals_df, bench_df, zip_buffer, raw = result
            else:
                sector_map = _load_sector_map(sector_uploaded)
                raw = collect_krx_daily_panel(
                    start=start,
                    end=end_arg or datetime.today().strftime("%Y-%m-%d"),
                    markets=markets,
                    sector_map=sector_map,
                    sleep_sec=float(sleep_sec),
                    cache_dir=cache_dir,
                    max_dates=max_dates,
                )
                if raw.empty:
                    raise ValueError("자동수집 결과가 없습니다. 날짜/시장/pykrx 상태를 확인하세요.")
                st.success(f"자동수집 완료: {len(raw):,}행 / {raw['code'].nunique():,}종목 / {raw['date'].nunique():,}거래일")
                st.download_button(
                    "수집 데이터 CSV 다운로드",
                    data=_to_csv_bytes(raw),
                    file_name="idio_auto_collected_krx_daily.csv",
                    mime="text/csv",
                )
                result = run_idio_from_dataframe(
                    data=raw,
                    start=start,
                    end=end_arg,
                    slot_cash=float(slot_cash),
                    portfolio_sizes=ps_options,
                    exit_rules=selected_exit_rules,
                    reg_window=int(reg_window),
                    min_reg_obs=int(min_reg_obs),
                    market_crisis_mode=market_crisis_mode,
                    commission_rate=float(commission_rate),
                    sell_tax_rate=float(sell_tax_rate),
                    entry_price=entry_price,
                    exit_price=exit_price,
                    allow_reits=allow_reits,
                    save_all_signals=save_all_signals,
                )
                summary_df, tr_all, eq_all, yearly_df, signals_df, bench_df, zip_buffer, raw2 = result

            render_results(summary_df, tr_all, eq_all, yearly_df, signals_df, bench_df, zip_buffer)
        except Exception as e:
            st.exception(e)


render_streamlit_app()
