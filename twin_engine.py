"""
Twin Engine — paper-trading engine (50% Modified 9Sig + TOM  /  50% LDS)
=======================================================================

Runs the exact backtested rules on a simulated ("paper") account and writes:
  state.json    – full engine state (holdings, tax lots, 9Sig accounting)
  summary.json  – everything the dashboard needs (positions, trades, signals, equity curve)

Usage
-----
  python twin_engine.py run                 # daily, after the 4:00 PM ET close (fills at today's close)
  python twin_engine.py run --capital 20000 --contrib 200 --start 2026-10-16   # first run: account opens at that day's close
  python twin_engine.py preview             # ~25-45 min before the close: today's orders from live prices (state not saved)
  python twin_engine.py status              # print current positions / next actions
  python twin_engine.py reset               # start over (asks for confirmation)

  # offline / testing: replay a CSV of daily closes (columns = tickers, index = date)
  python twin_engine.py replay --csv prices.csv --start 2025-10-01

Requirements: pandas, numpy, yfinance (live mode), exchange_calendars (optional, for the NYSE calendar).
Not financial advice. Paper trading only — no broker orders are sent.
"""
from __future__ import annotations
import argparse, copy, json, math, os, sys, datetime as dt
from collections import defaultdict
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
STATE_PATH = os.path.join(HERE, "state.json")
SUMMARY_PATH = os.path.join(HERE, "summary.json")
PREVIEW_PATH = os.path.join(HERE, "preview.json")
VERSION = "1.6.0"

# ----------------------------------------------------------------------------- parameters (backtested values)
P = dict(
    start_capital=20000.0,
    split_9sig=0.50,            # Twin Engine: 50% Modified 9Sig / 50% LDS
    rebalance_months=(12,),     # v1.3: reset the two engines to 50/50 at year end only (was every quarter end)
    fomc_swap=True,             # v1.3: LDS sleeve swapped for one session on each scheduled Fed decision day (close before -> close of decision day)
    fomc_asset="SOXL",          # v1.5: the Fed-day swap holds 3x semiconductors (v1.3: TQQQ)
    lds_review="month",         # v1.5: LDS trend/risk review at the last close of each month (v1.3: every week)
    dip_rsi2=20.0,              # v1.5: 9Sig dip boost - full TQQQ for the next session when QQQ's 2-day RSI < 20 and QQQ > its 200-day average
    # --- Modified 9Sig sleeve
    sig_rate=0.09,              # quarterly growth target for the TQQQ "growth" sub-sleeve
    w0_growth=0.60,             # 9Sig sleeve starts 60% growth / 40% defensive
    skip_after_crash=4,         # Kelly "30 down" rule: after a quarter <= -30%, ignore next 4 sell signals
    crash_qtr=-0.30,
    vol_target=0.80,            # volatility switch: TQQQ weight = clip((0.80 / vol20)^10, 0, 1)  (v1.1: was 0.70)
    vol_power=10.0,
    vol_lookback=20,
    vol_band=0.05,              # only change the base weight when it moves > 5 points
    tom_after=3,                # turn-of-month: full TQQQ on last trading day + first 3 trading days
    defensive=("TLT", "GLD"),   # defensive half of 9Sig, 50/50
    # --- LDS sleeve (leveraged diversification)
    lds_assets=("SPY", "TLT", "GLD"),   # v1.6: QQQ dropped - 9Sig already holds the Nasdaq (v1.5: SPY, QQQ, TLT, GLD)
    lds_core=0.85, lds_overlay=0.15,
    lds_vol_target=1.00,        # core risk parity scaled to 100% vol target -> capped by available leverage
    lds_overlay_vol=0.15,
    sma_days=210, cov_days=63,
    lds_threshold=0.05,         # LDS review trades only if total change > 5% of the sleeve
    # --- execution
    slippage_bps=2.0,
    min_order=25.0,             # ignore orders smaller than $25
    fractional=True,            # set False (or --whole-shares) to trade whole shares only; costs ~0.1 pt/yr at $20k
    contrib_monthly=0.0,
)
# leveraged / inverse ETF for (underlying, leverage)
ETF = {
    ("SPY", 1): "SPY", ("SPY", 2): "SSO", ("SPY", 3): "UPRO", ("SPY", -1): "SH", ("SPY", -2): "SDS", ("SPY", -3): "SPXU",
    ("QQQ", 1): "QQQ", ("QQQ", 2): "QLD", ("QQQ", 3): "TQQQ", ("QQQ", -1): "PSQ", ("QQQ", -2): "QID", ("QQQ", -3): "SQQQ",
    ("TLT", 1): "TLT", ("TLT", 2): "UBT", ("TLT", 3): "TMF", ("TLT", -1): "TBF", ("TLT", -2): "TBT", ("TLT", -3): "TMV",
    ("GLD", 1): "GLD", ("GLD", 2): "UGL", ("GLD", -2): "GLL",
    ("SOXX", 3): "SOXL",        # Fed-day swap only - not an LDS asset
}
LMAX_LONG = dict(SPY=3, QQQ=3, TLT=3, GLD=2)
LMAX_SHORT = dict(SPY=3, QQQ=3, TLT=3, GLD=2)
NAMES = {
    "TQQQ": "3x Nasdaq-100", "UPRO": "3x S&P 500", "TMF": "3x 20+yr Treasuries", "UGL": "2x Gold",
    "SPXU": "-3x S&P 500", "SQQQ": "-3x Nasdaq-100", "TMV": "-3x 20+yr Treasuries", "GLL": "-2x Gold",
    "TLT": "20+yr Treasuries", "GLD": "Gold", "SPY": "S&P 500", "QQQ": "Nasdaq-100", "SSO": "2x S&P 500",
    "QLD": "2x Nasdaq-100", "SOXL": "3x Semiconductors", "UBT": "2x 20+yr Treasuries", "SH": "-1x S&P 500", "SDS": "-2x S&P 500",
    "PSQ": "-1x Nasdaq-100", "QID": "-2x Nasdaq-100", "TBF": "-1x 20+yr Treasuries", "TBT": "-2x 20+yr Treasuries",
}
# Scheduled FOMC decision days (statement released ~2:00 PM ET). Source: federalreserve.gov.
# The Fed publishes next year's schedule each summer - add it here once a year (the engine warns when the list runs low).
FOMC_DATES = set(pd.to_datetime("""
    1999-02-03 1999-03-30 1999-05-18 1999-06-30 1999-08-24 1999-10-05 1999-11-16 1999-12-21
    2000-02-02 2000-03-21 2000-05-16 2000-06-28 2000-08-22 2000-10-03 2000-11-15 2000-12-19
    2001-01-31 2001-03-20 2001-05-15 2001-06-27 2001-08-21 2001-10-02 2001-11-06 2001-12-11
    2002-01-30 2002-03-19 2002-05-07 2002-06-26 2002-08-13 2002-09-24 2002-11-06 2002-12-10
    2003-01-29 2003-03-18 2003-05-06 2003-06-25 2003-08-12 2003-09-15 2003-09-16 2003-10-28 2003-12-09
    2004-01-28 2004-03-16 2004-05-04 2004-06-30 2004-08-10 2004-09-21 2004-11-10 2004-12-14
    2005-02-02 2005-03-22 2005-05-03 2005-06-30 2005-08-09 2005-09-20 2005-11-01 2005-12-13
    2006-01-31 2006-03-28 2006-05-10 2006-06-29 2006-08-08 2006-09-20 2006-10-25 2006-12-12
    2007-01-31 2007-03-21 2007-05-09 2007-06-28 2007-08-07 2007-09-18 2007-10-31 2007-12-11
    2008-01-30 2008-03-18 2008-04-30 2008-06-25 2008-08-05 2008-09-16 2008-10-29 2008-12-16
    2009-01-28 2009-03-18 2009-04-29 2009-06-24 2009-08-12 2009-09-23 2009-11-04 2009-12-16
    2010-01-27 2010-03-16 2010-04-28 2010-06-23 2010-08-10 2010-09-21 2010-11-03 2010-12-14
    2011-01-26 2011-03-15 2011-04-27 2011-06-22 2011-08-09 2011-09-21 2011-11-02 2011-12-13
    2012-01-25 2012-03-13 2012-04-25 2012-06-20 2012-08-01 2012-09-13 2012-10-24 2012-12-12
    2013-01-30 2013-03-20 2013-05-01 2013-06-19 2013-07-31 2013-09-18 2013-10-30 2013-12-18
    2014-01-29 2014-03-19 2014-04-30 2014-06-18 2014-07-30 2014-09-17 2014-10-29 2014-12-17
    2015-01-28 2015-03-18 2015-04-29 2015-06-17 2015-07-29 2015-09-17 2015-10-28 2015-12-16
    2016-01-27 2016-03-16 2016-04-27 2016-06-15 2016-07-27 2016-09-21 2016-11-02 2016-12-14
    2017-02-01 2017-03-15 2017-05-03 2017-06-14 2017-07-26 2017-09-20 2017-11-01 2017-12-13
    2018-01-31 2018-03-21 2018-05-02 2018-06-13 2018-08-01 2018-09-26 2018-11-08 2018-12-19
    2019-01-30 2019-03-20 2019-05-01 2019-06-19 2019-07-31 2019-09-18 2019-10-30 2019-12-11
    2020-01-29 2020-04-29 2020-06-10 2020-07-29 2020-09-16 2020-11-05 2020-12-16
    2021-01-27 2021-03-17 2021-04-28 2021-06-16 2021-07-28 2021-09-22 2021-11-03 2021-12-15
    2022-01-26 2022-03-16 2022-05-04 2022-06-15 2022-07-27 2022-09-21 2022-11-02 2022-12-14
    2023-02-01 2023-03-22 2023-05-03 2023-06-14 2023-07-26 2023-09-20 2023-11-01 2023-12-13
    2024-01-31 2024-03-20 2024-05-01 2024-06-12 2024-07-31 2024-09-18 2024-11-07 2024-12-18
    2025-01-29 2025-03-19 2025-05-07 2025-06-18 2025-07-30 2025-09-17 2025-10-29 2025-12-10
    2026-01-28 2026-03-18 2026-04-29 2026-06-17 2026-07-29 2026-09-16 2026-10-28 2026-12-09
    2027-01-27 2027-03-17 2027-04-28 2027-06-09 2027-07-28 2027-09-15 2027-10-27 2027-12-08
""".split()))
SIGNAL_TICKERS = ["SPY", "QQQ", "TLT", "GLD", "TQQQ"]
ALL_TICKERS = sorted(set(SIGNAL_TICKERS) | set(ETF.values()))

# ----------------------------------------------------------------------------- calendar helpers
def nyse_sessions(start, end):
    try:
        import exchange_calendars as xcals
    except Exception:
        xcals = None
    if xcals is not None:
        c = xcals.get_calendar("XNYS"); last = pd.Timestamp(c.last_session).tz_localize(None)
        days = pd.DatetimeIndex(c.sessions_in_range(start, min(pd.Timestamp(end), last))).tz_localize(None)
        if pd.Timestamp(end) > last:          # beyond the library's horizon (~1 year): weekdays only, far enough out not to matter
            days = days.append(pd.bdate_range(last + pd.Timedelta(days=1), end))
        return days
    else:
        print("WARNING: exchange_calendars not installed - market holidays are ignored for FUTURE dates "
              "(turn-of-month / quarter-end timing can be off by a day). Run: pip install exchange_calendars")
        return pd.bdate_range(start, end)

class Calendar:
    """Trading-day calendar = history index + future NYSE sessions."""
    def __init__(self, hist_index):
        fut = nyse_sessions(hist_index[-1] + pd.Timedelta(days=1), hist_index[-1] + pd.Timedelta(days=420))
        self.days = pd.DatetimeIndex(sorted(set(hist_index) | set(fut)))
    def next_day(self, d):
        i = self.days.searchsorted(d, side="right"); return self.days[i]
    def is_month_end(self, d):
        n = self.next_day(d); return n.month != d.month
    def is_quarter_end(self, d):
        n = self.next_day(d); return (n.month - 1) // 3 != (d.month - 1) // 3 or n.year != d.year
    def is_week_end(self, d):
        n = self.next_day(d); return n.isocalendar()[1] != d.isocalendar()[1] or (n - d).days > 3
    def is_first_session_of_month(self, d):
        i = self.days.searchsorted(d); return i == 0 or self.days[i - 1].month != d.month
    def is_tom(self, d):
        """last trading day of month or first 3 trading days"""
        if self.is_month_end(d): return True
        i = self.days.searchsorted(d); k = 0
        while i - k - 1 >= 0 and self.days[i - k - 1].month == d.month: k += 1
        return k < P["tom_after"]
    def is_fomc(self, d): return pd.Timestamp(d).normalize() in FOMC_DATES
    def is_pre_fomc(self, d): return self.is_fomc(self.next_day(d))
    def is_lds_review(self, d): return self.is_month_end(d) if P["lds_review"] == "month" else self.is_week_end(d)
    def is_rebalance_day(self, d): return self.is_quarter_end(d) and d.month in P["rebalance_months"]
    def upcoming(self, d, pred, n=1):
        out, x = [], d
        for _ in range(400):
            if x >= self.days[-1]: break
            x = self.next_day(x)
            if pred(x): out.append(x)
            if len(out) >= n: break
        return out

# ----------------------------------------------------------------------------- state
def new_state(capital, start_date, contrib):
    half = capital * P["split_9sig"]
    return dict(
        version=VERSION, start_date=str(start_date.date()), start_capital=capital, contrib_monthly=contrib,
        last_date=None, contributed=capital,
        sleeves={"9SIG": dict(cash=half, holdings={}), "LDS": dict(cash=capital - half, holdings={})},
        lots={},                                  # "SLEEVE|TICKER" -> [[date, shares, price], ...]  FIFO
        nine=dict(S=half * P["w0_growth"], B=half * (1 - P["w0_growth"]), w_base=1.0, w=1.0,
                  last_target=half * P["w0_growth"], growth_index=1.0, q_anchor=1.0, skips=0, new_cash=0.0,
                  initialized=False),
        lds=dict(exposures={}, last_rebalance=None),
        trades=[], equity=[], spy_units=None, prev_close={},
        dividends=0.0, events=[], fractional=P["fractional"],
    )

def load_state():
    with open(STATE_PATH) as f: return json.load(f)

def save_state(st):
    tmp = STATE_PATH + ".tmp"
    with open(tmp, "w") as f: json.dump(st, f, indent=1, default=str)
    os.replace(tmp, STATE_PATH)

# ----------------------------------------------------------------------------- signal math (identical to the backtest)
def daily_returns(adj: pd.DataFrame): return adj.pct_change()

def vol_switch_raw(tqqq_adj: pd.Series):
    r = tqqq_adj.pct_change().dropna().iloc[-P["vol_lookback"]:]
    v = float(r.std(ddof=1) * math.sqrt(252)) if len(r) >= P["vol_lookback"] else float("nan")   # ddof=1 = backtest
    if not v or math.isnan(v): return 1.0, v
    return float(min(max((P["vol_target"] / v) ** P["vol_power"], 0.0), 1.0)), v

def rsi2(px: pd.Series):
    """2-day RSI (Wilder smoothing over the last 2 changes), as in the research backtest"""
    r = px.diff().iloc[-3:]
    up = r.clip(lower=0).ewm(alpha=0.5, adjust=False).mean().iloc[-1]; dn = (-r.clip(upper=0)).ewm(alpha=0.5, adjust=False).mean().iloc[-1]
    return 100.0 if dn == 0 else float(100 - 100 / (1 + up / dn))

def dip_signal(qqq_adj: pd.Series):
    """(boost on?, RSI2, QQQ above its 200-day average?) at the last close"""
    q = qqq_adj.dropna(); r = rsi2(q); up = float(q.iloc[-1]) > float(q.iloc[-200:].mean())
    return (P["dip_rsi2"] is not None and up and r < P["dip_rsi2"]), r, up

def _vol(r, n): return float(r.iloc[-n:].std(ddof=1) * math.sqrt(252))
def _mom(px, months): k = 21 * months; return float(px.iloc[-1] / px.iloc[-1 - k] - 1) if len(px) > k else float("nan")

def lds_exposures(adj: pd.DataFrame):
    """returns (exposures dict, diagnostics) using data through the last row"""
    A = list(P["lds_assets"]); px = adj[A].dropna(); r = px.pct_change().dropna(); n = P["cov_days"]
    diag = {}
    core = {}
    for a in A:
        s = px[a]; sma = float(s.iloc[-P["sma_days"]:].mean()); up = float(s.iloc[-1]) >= sma
        v = _vol(r[a], n); bm = np.nanmean([_mom(s, k) for k in (1, 3, 6, 12)])
        diag[a] = dict(price=float(s.iloc[-1]), sma=sma, pct_vs_sma=float(s.iloc[-1] / sma - 1), trend="UP" if up else "DOWN",
                       vol63=v, mom_blend=float(bm), overlay="LONG" if bm > 0 else "SHORT")
        if up: core[a] = 1 / v
    def scale(w, V):
        if not w: return {}
        tot = sum(abs(x) for x in w.values()); w = {a: x / tot for a, x in w.items()}
        ks = list(w); C = np.atleast_2d(np.cov(r[ks].iloc[-n:].values.T) * 252); x = np.array([w[a] for a in ks])
        pv = float(np.sqrt(max(x @ C @ x, 1e-12))); return {a: w[a] * V / pv for a in ks}
    core = scale(core, P["lds_vol_target"])
    ov = {}
    for a in A:
        bm = diag[a]["mom_blend"]
        if np.isnan(bm): continue
        ov[a] = (1 if bm > 0 else -1) / diag[a]["vol63"]
    ov = scale(ov, P["lds_overlay_vol"])
    ex = defaultdict(float)
    for a, e in core.items(): ex[a] += P["lds_core"] * e
    for a, e in ov.items(): ex[a] += P["lds_overlay"] * e
    return dict(ex), diag

def implement(expo):
    """target exposures -> {ETF ticker: capital weight} using the lowest leverage tier that fits in 100% capital"""
    expo = {a: e for a, e in expo.items() if abs(e) > 1e-6}
    if not expo: return {}
    def lev_for(a, e, k):
        lm = LMAX_LONG[a] if e > 0 else LMAX_SHORT[a]; L = min(k, lm)
        if e < 0 and a == "GLD": L = 2               # only -2x gold (GLL) exists
        return L if e > 0 else -L
    for k in (1, 2, 3):
        caps = {}
        for a, e in expo.items():
            L = lev_for(a, e, k); caps[ETF[(a, L)]] = caps.get(ETF[(a, L)], 0) + abs(e) / abs(L)
        if sum(caps.values()) <= 1 + 1e-9: return caps
    caps = {}
    for a, e in expo.items():
        L = lev_for(a, e, 3); caps[ETF[(a, L)]] = caps.get(ETF[(a, L)], 0) + abs(e) / abs(L)
    s = sum(caps.values()); return {t: c / max(s, 1.0) for t, c in caps.items()}

# ----------------------------------------------------------------------------- ledger
def sleeve_value(st, sl, close):
    h = st["sleeves"][sl]; return h["cash"] + sum(sh * close[t] for t, sh in h["holdings"].items())

def total_value(st, close): return sum(sleeve_value(st, s, close) for s in st["sleeves"])

def trade(st, sl, tk, dollars, price, date, reason, force=False):
    """buy (+) / sell (-) dollars of tk at price (paper fill at close +/- slippage); FIFO lots; realized P&L"""
    if abs(dollars) < P["min_order"] and not force: return None
    if not (price > 0): raise RuntimeError(f"{date.date()}: invalid price {price} for {tk}")
    slip = P["slippage_bps"] / 1e4
    fill = price * (1 + slip) if dollars > 0 else price * (1 - slip)
    shares = dollars / fill
    if not P["fractional"]:   # whole shares: buys round down (never overspend), sells round up (always raise enough cash)
        shares = math.floor(shares + 1e-9) if shares > 0 else -math.ceil(-shares - 1e-9)
    if shares == 0: return None
    h = st["sleeves"][sl]; key = f"{sl}|{tk}"; lots = st["lots"].setdefault(key, [])
    held = h["holdings"].get(tk, 0.0)
    if shares < 0: shares = max(shares, -held)       # never sell more than held
    if abs(shares) < 1e-9: return None
    realized = 0.0; cost_out = 0.0; hold_days = []
    if shares > 0:
        lots.append([str(date.date()), shares, fill])
    else:
        need = -shares
        while need > 1e-9 and lots:
            lt = lots[0]; u = min(need, lt[1]); realized += u * (fill - lt[2]); cost_out += u * lt[2]
            hold_days.append(((date - pd.Timestamp(lt[0])).days, u)); lt[1] -= u; need -= u
            if lt[1] <= 1e-9: lots.pop(0)
    h["holdings"][tk] = held + shares
    if abs(h["holdings"][tk]) < 1e-9: h["holdings"].pop(tk, None); st["lots"].pop(key, None)
    h["cash"] -= shares * fill
    rec = dict(date=str(date.date()), sleeve=sl, ticker=tk, side="BUY" if shares > 0 else "SELL", shares=round(abs(shares), 4),
               price=round(fill, 4), value=round(abs(shares * fill), 2), reason=reason)
    if shares < 0:
        rec["realized_pl"] = round(realized, 2)
        rec["realized_pct"] = round(realized / cost_out * 100, 2) if cost_out else 0.0
        hd = sum(d * u for d, u in hold_days) / max(sum(u for _, u in hold_days), 1e-9)
        rec["hold_days"] = round(hd, 1); rec["term"] = "LONG" if hd > 365 else "SHORT"
    st["trades"].append(rec); return rec

def set_targets(st, sl, targets, close, date, reason, keep_cash=False):
    """move a sleeve to target dollar holdings (sells first, then buys)"""
    h = st["sleeves"][sl]
    cur = {t: sh * close[t] for t, sh in h["holdings"].items()}
    tickers = set(cur) | set(targets)
    plan = {t: targets.get(t, 0.0) - cur.get(t, 0.0) for t in tickers}
    exits = set()
    for t in tickers:
        if (t not in targets or targets[t] <= 0) and cur.get(t, 0) > 0: plan[t] = -cur[t] * 1.01; exits.add(t)   # full exit
    for t in sorted(tickers, key=lambda t: plan[t]):                            # sells first, then buys
        if plan[t] < 0: trade(st, sl, t, plan[t], close[t], date, reason, force=t in exits)
    for t in sorted(tickers, key=lambda t: -plan[t]):
        if plan[t] > 0: trade(st, sl, t, min(plan[t], max(h["cash"], 0.0)), close[t], date, reason)

# ----------------------------------------------------------------------------- one trading day
def step(st, date, adj: pd.DataFrame, close: dict, cal: Calendar, divs: dict | None = None, splits: dict | None = None):
    """process the close of `date`. adj = adjusted-close history through date (signals); close = today's closes."""
    nine, lds = st["nine"], st["lds"]
    ev = []
    # --- corporate actions
    for tk, ratio in (splits or {}).items():
        for sl in st["sleeves"]:
            h = st["sleeves"][sl]
            if tk in h["holdings"]:
                h["holdings"][tk] *= ratio
                for lt in st["lots"].get(f"{sl}|{tk}", []): lt[1] *= ratio; lt[2] /= ratio
                ev.append(f"Split {tk} {ratio}:1 applied")
        for ref in ("prev_close", "close_before"):
            if tk in (st.get(ref) or {}): st[ref][tk] /= ratio
    for tk, amt in (divs or {}).items():
        for sl in st["sleeves"]:
            sh = st["sleeves"][sl]["holdings"].get(tk, 0.0)
            if sh > 0: st["sleeves"][sl]["cash"] += sh * amt; st["dividends"] += sh * amt
        if tk == "SPY" and st["spy_units"] and close.get("SPY", 0) > 0:
            st["spy_units"] *= 1 + amt / close["SPY"]          # benchmark = SPY with dividends reinvested
    # --- 9Sig accounting: growth/defensive sub-sleeves evolve with their own returns
    prev = st["prev_close"]
    if nine["initialized"] and prev:
        rq = close["TQQQ"] / prev["TQQQ"] - 1
        rd = np.mean([close[t] / prev[t] - 1 for t in P["defensive"]])
        a = nine["w"] * rq + (1 - nine["w"]) * rd
        nine["S"] *= 1 + a; nine["B"] *= 1 + rd; nine["growth_index"] *= 1 + a
        v9 = sleeve_value(st, "9SIG", close); f = v9 / max(nine["S"] + nine["B"], 1e-9)
        nine["S"] *= f; nine["B"] *= f
    # --- contributions (first session of month)
    contributed_today = False
    if st["contrib_monthly"] and st["last_date"] and cal.is_first_session_of_month(date):
        contributed_today = True
        c = st["contrib_monthly"]; c9 = c * P["split_9sig"]
        st["sleeves"]["9SIG"]["cash"] += c9; st["sleeves"]["LDS"]["cash"] += c - c9
        nine["B"] += c9; nine["new_cash"] += c9; st["contributed"] += c
        if st["spy_units"]: st["spy_units"] += c / close["SPY"]
        ev.append(f"Contribution ${c:,.0f} (split 50/50)")
    q_end = cal.is_quarter_end(date)
    nine_trade = not nine["initialized"]
    # --- 9Sig quarterly signal
    if q_end and nine["initialized"]:
        qr = nine["growth_index"] / nine["q_anchor"] - 1; nine["q_anchor"] = nine["growth_index"]
        if qr <= P["crash_qtr"]: nine["skips"] = P["skip_after_crash"]; ev.append(f"30-down rule armed (quarter {qr:+.0%}): skip next 4 sells")
        target = nine["last_target"] * (1 + P["sig_rate"]) + 0.5 * nine["new_cash"]
        diff = target - nine["S"]
        if diff < 0 and nine["skips"] > 0:
            nine["skips"] -= 1; ev.append(f"9Sig SELL signal skipped (30-down rule, {nine['skips']} left)")
        elif diff < 0:
            nine["S"] += diff; nine["B"] -= diff; ev.append(f"9Sig: growth above target -> move ${-diff:,.0f} to defensive")
        else:
            buy = min(diff, nine["B"]); nine["S"] += buy; nine["B"] -= buy; ev.append(f"9Sig: growth below target -> move ${buy:,.0f} into growth")
        nine["last_target"] = nine["S"]; nine["new_cash"] = 0.0; nine_trade = True
    # --- 50/50 rebalance between sleeves (year end)
    lds_force = not st["last_date"]
    rebal = cal.is_rebalance_day(date)
    if rebal and st["last_date"]:
        v9, vl = sleeve_value(st, "9SIG", close), sleeve_value(st, "LDS", close)
        tot = v9 + vl; t9 = tot * P["split_9sig"]; move = t9 - v9
        if abs(move) > P["min_order"]:
            # scale LDS holdings proportionally, move cash between sleeves
            fl = (tot - t9) / vl
            tg = {t: sh * close[t] * fl for t, sh in st["sleeves"]["LDS"]["holdings"].items()}
            if move > 0:
                set_targets(st, "LDS", tg, close, date, "Year-end 50/50 rebalance")
                move = min(move, max(st["sleeves"]["LDS"]["cash"], 0.0))   # only transfer cash the sales actually raised
            st["sleeves"]["LDS"]["cash"] -= move; st["sleeves"]["9SIG"]["cash"] += move
            if move < 0: set_targets(st, "LDS", tg, close, date, "Year-end 50/50 rebalance")
            f9 = (v9 + move) / v9; nine["S"] *= f9; nine["B"] *= f9; nine["last_target"] *= f9
            nine_trade = True; ev.append(f"Year-end 50/50 rebalance: moved ${abs(move):,.0f} {'to' if move > 0 else 'from'} 9Sig")
    # --- 9Sig weight for TOMORROW (vol switch + TOM)
    raw, v20 = vol_switch_raw(adj["TQQQ"].dropna())
    if abs(raw - nine["w_base"]) > P["vol_band"] or not nine["initialized"]: nine["w_base"] = raw
    tomorrow = cal.next_day(date); tom = cal.is_tom(tomorrow)
    dip, r2, up200 = dip_signal(adj["QQQ"])
    boost = "TOM" if tom else ("Dip" if dip else None)
    w_new = 1.0 if boost else nine["w_base"]
    if abs(w_new - nine["w"]) > 1e-9 or nine_trade or contributed_today:
        why = []
        if abs(w_new - nine["w"]) > 1e-9:
            if boost and w_new > nine["w"]: why.append(f"{boost} boost on")
            elif nine.get("boost") and not boost: why.append(f"{nine['boost']} boost off")
            else: why.append(f"Vol switch {nine['w']:.0%}->{w_new:.0%}")
        if q_end: why.append("9Sig quarterly signal")
        if contributed_today and not q_end: why.append("Invest contribution")
        if not nine["initialized"]: why = ["Initial allocation"]
        nine["w"] = w_new
        v9 = sleeve_value(st, "9SIG", close)
        if not nine["initialized"]: nine["S"], nine["B"] = v9 * P["w0_growth"], v9 * (1 - P["w0_growth"]); nine["last_target"] = nine["S"]
        tq = nine["w"] * nine["S"]; dfn = (1 - nine["w"]) * nine["S"] + nine["B"]
        tg = {"TQQQ": tq}; tg.update({t: dfn / len(P["defensive"]) for t in P["defensive"]})
        set_targets(st, "9SIG", tg, close, date, " + ".join(why) or "9Sig rebalance")
        nine["initialized"] = True
    if dip and not tom and not nine.get("boost"): ev.append(f"Dip boost: QQQ 2-day RSI {r2:.0f} < {P['dip_rsi2']:.0f} in an uptrend -> TQQQ at full size for {tomorrow:%a %b %d}")
    nine["vol20"] = v20; nine["raw"] = raw; nine["tom_tomorrow"] = tom; nine["boost"] = boost; nine["rsi2"] = r2; nine["qqq_up"] = up200
    # --- LDS: FOMC swap back (the day after entry = decision day, or later if a run was missed)
    ex, diag = lds_exposures(adj)
    lds["diag"] = diag
    swap = lds.get("fomc_swap") or {}
    swapped_back = False
    if swap.get("active") and str(date.date()) > swap.get("entered", ""):
        caps = implement(ex); vl = sleeve_value(st, "LDS", close)
        set_targets(st, "LDS", {t: c * vl for t, c in caps.items()}, close, date, "Fed-day swap ends: LDS positions restored")
        lds["exposures"] = ex; lds["last_rebalance"] = str(date.date()); lds["last_check"] = str(date.date()); lds["target_exposures"] = ex
        lds["fomc_swap"] = dict(active=False, last=swap.get("decision")); swapped_back = True
        ev.append("Fed-day swap ended: LDS sleeve back to its trend/risk positions")
    # --- LDS review (last session of the month; v1.3: of the week) or first day
    rule_change = bool(st["last_date"]) and lds.get("assets", ["SPY", "QQQ", "TLT", "GLD"]) != list(P["lds_assets"])   # asset list changed (v1.6): rebalance once
    if (cal.is_lds_review(date) or lds_force or rule_change) and not swapped_back:
        caps = implement(ex); vl = sleeve_value(st, "LDS", close)
        tg = {t: c * vl for t, c in caps.items()}
        cur = {t: sh * close[t] for t, sh in st["sleeves"]["LDS"]["holdings"].items()}
        turn = sum(abs(tg.get(t, 0) - cur.get(t, 0)) for t in set(tg) | set(cur))
        if turn > P["lds_threshold"] * vl or lds_force or rule_change:
            set_targets(st, "LDS", tg, close, date, "Initial allocation" if lds_force else ("LDS rebalance: v1.6 rule change (no QQQ)" if rule_change else "LDS monthly rebalance"))
            lds["exposures"] = ex; lds["last_rebalance"] = str(date.date()); ev.append(f"LDS rebalanced (turnover {turn / vl:.0%})")
        else:
            ev.append(f"LDS monthly check: turnover {turn / vl:.1%} < 5%, no trade")
        lds["last_check"] = str(date.date()); lds["target_exposures"] = ex; lds["assets"] = list(P["lds_assets"])
    # --- LDS: FOMC swap in (close before a scheduled Fed decision): whole LDS sleeve into the swap ETF for one day
    if P["fomc_swap"] and cal.is_pre_fomc(date) and not (lds.get("fomc_swap") or {}).get("active"):
        vl = sleeve_value(st, "LDS", close); dec = cal.next_day(date)
        fa = P["fomc_asset"]
        set_targets(st, "LDS", {fa: vl}, close, date, f"Fed-day swap: LDS into {fa} for the Fed decision {dec:%b %d}")
        lds["fomc_swap"] = dict(active=True, entered=str(date.date()), decision=str(dec.date()))
        ev.append(f"Fed-day swap: LDS sleeve moved into {fa} for the Fed decision on {dec:%a %b %d}")
    # --- bookkeeping
    tot = total_value(st, close)
    if st["spy_units"] is None: st["spy_units"] = st["start_capital"] / close["SPY"]
    st["equity"].append(dict(date=str(date.date()), value=round(tot, 2), spy=round(st["spy_units"] * close["SPY"], 2),
                             nine=round(sleeve_value(st, "9SIG", close), 2), lds=round(sleeve_value(st, "LDS", close), 2),
                             contributed=round(st["contributed"], 2)))
    for e in ev: st["events"].append(dict(date=str(date.date()), text=e))
    st["events"] = st["events"][-400:]
    st["close_before"] = st.get("prev_close") or {}; st["prev_close"] = {t: float(close[t]) for t in close}; st["last_date"] = str(date.date())
    return ev

def next_fomc(cal, date):
    """(decision day, entry day = session before it) for the next scheduled decision after `date`, or (None, None)."""
    for dec in sorted(x for x in FOMC_DATES if x > date):
        prev = cal.days[cal.days < dec]
        if len(prev) and prev[-1] >= date: return dec, prev[-1]
        if len(prev) and prev[-1] < date: continue
    return None, None

# Important dates shown on the dashboard (Overview > Important dates). Add or edit lines here: (date, what, why/how).
CRON_TOKEN_EXPIRES = "2027-10-19"   # GitHub token used by cron-job.org (health check warns 30 days ahead)
REMINDERS = [
    ("2026-10-26", "Go live: buy the paper account's positions in the Roth as MOC orders", "Use the share counts on the Positions tab so later orders match the dashboard."),
    ("2026-10-27", "First live Fed-day swap: LDS sleeve into SOXL at the close", "Swap back at the close on Wed Oct 28."),
    ("2026-10-30", "First monthly LDS review", "Then turn-of-month window through Wed Nov 4."),
    ("2026-12-31", "First year-end 50/50 reset", "Also the 9Sig quarterly signal - expect several orders."),
    ("2027-04-15", "Last day for 2026 Roth IRA contributions", "2026 limit about $7,500; 2027 contributions open Jan 1."),
    ("2027-07-01", "Add the Fed's 2028 meeting dates to the engine", "The Fed publishes them each summer. Ask Claude, or edit FOMC_DATES in twin_engine.py."),
    ("2027-10-05", "Renew the GitHub token for cron-job.org (expires Oct 19, 2027)", "New fine-grained token, this repo only, Actions read/write; paste it into both cron-job.org jobs. README 4 step 3b."),
    ("2028-02-15", "Update the API version header in both cron-job.org jobs", "GitHub retires X-GitHub-Api-Version 2022-11-28 on Mar 10, 2028."),
]

def reminders(date):
    """upcoming REMINDERS plus the automatic Fed-dates reminder, soonest first"""
    out = [dict(date=d, what=w, note=n) for d, w, n in REMINDERS if d >= str(date.date())]
    last = max(FOMC_DATES)
    if not any("Fed's" in r["what"] for r in out):
        out.append(dict(date=f"{last.year}-07-01", what=f"Add the Fed's {last.year + 1} meeting dates to the engine",
                        note="The Fed publishes them each summer. Ask Claude, or edit FOMC_DATES in twin_engine.py."))
    return sorted(out, key=lambda r: r["date"])

def fomc_list_warning(date):
    future = [x for x in FOMC_DATES if x > date]
    if len(future) < 3:
        return ("Only %d scheduled Fed decision date(s) left in the engine's list. Add next year's dates "
                "(federalreserve.gov > FOMC calendar) to FOMC_DATES in twin_engine.py." % len(future))
    return None

# ----------------------------------------------------------------------------- summary for the dashboard
def build_summary(st, adj, close, cal, demo=False):
    date = pd.Timestamp(st["last_date"]); eq = pd.DataFrame(st["equity"])
    tot = float(eq.value.iloc[-1]); prev = float(eq.value.iloc[-2]) if len(eq) > 1 else st["start_capital"]
    v = eq.value.values; peak = np.maximum.accumulate(v); dd = v / peak - 1
    days = (pd.Timestamp(eq.date.iloc[-1]) - pd.Timestamp(eq.date.iloc[0])).days
    # time-weighted return (strip contributions)
    tw = 1.0
    for i in range(1, len(eq)):
        flow = eq.contributed.iloc[i] - eq.contributed.iloc[i - 1]
        tw *= (eq.value.iloc[i] - flow) / eq.value.iloc[i - 1]
    cagr = tw ** (365.25 / days) - 1 if days > 180 else None
    nine, lds = st["nine"], st["lds"]
    nxt_week = cal.upcoming(date, cal.is_lds_review, 1)[0]
    nxt_q = cal.upcoming(date, cal.is_quarter_end, 1)[0]
    tom_start = cal.upcoming(date, lambda d: cal.is_tom(cal.next_day(d)) and not cal.is_tom(d), 1)[0]
    tom_end = cal.upcoming(tom_start, lambda d: cal.is_tom(d) and not cal.is_tom(cal.next_day(d)), 1)[0]
    in_tom_now = cal.is_tom(cal.next_day(date))
    if in_tom_now:
        tom_end = cal.upcoming(date - pd.Timedelta(days=1), lambda d: cal.is_tom(d) and not cal.is_tom(cal.next_day(d)), 1)[0]
    q_target = nine["last_target"] * (1 + P["sig_rate"])
    diag = lds.get("diag", {})
    v20 = nine.get("vol20") or float("nan")
    positions = []
    for sl in ("9SIG", "LDS"):
        h = st["sleeves"][sl]
        for tk, sh in sorted(h["holdings"].items(), key=lambda x: -x[1] * close[x[0]]):
            lots = st["lots"].get(f"{sl}|{tk}", [])
            cost = sum(l[1] * l[2] for l in lots); val = sh * close[tk]
            pc = (st.get("close_before") or {}).get(tk, close[tk])
            und = next((a for (a, L), t in ETF.items() if t == tk), tk)
            if sl == "9SIG" and tk == "TQQQ":
                role = "Growth engine (9Sig)"
                if nine["w_base"] >= 0.999:
                    tom_txt = "Turn-of-month boost not needed (already at full size). "
                elif in_tom_now:
                    tom_txt = f"Turn-of-month boost: held at full size through the close of {tom_end:%a %b %d}, then back to {nine['w_base']:.0%}. "
                else:
                    tom_txt = f"Next turn-of-month boost: to full size at close {tom_start:%a %b %d}, back to normal size at close {tom_end:%a %b %d}. "
                if nine.get("boost") == "Dip": tom_txt = f"Dip boost on: full size for one session (QQQ 2-day RSI {nine.get('rsi2', 0):.0f}). " + tom_txt
                elif nine["w_base"] < 0.999: tom_txt += f"Dip boost: full size for a session when QQQ's 2-day RSI closes below {P['dip_rsi2']:.0f} while QQQ is above its 200-day average. "
                _t, _p = P["vol_target"], P["vol_power"]
                exit_rule = (f"Size set daily by the volatility switch: 20-day vol {v20:.0%} vs {_t:.0%} target (full size at <={_t:.0%}, about half at {_t*2**(1/_p):.0%}, near zero above {_t*10**(1/_p):.0%}); now {nine['w_base']:.0%} of the growth sub-sleeve. "
                             + tom_txt + f"Quarterly 9Sig check at close {nxt_q:%a %b %d}: growth sub-sleeve target ${q_target:,.0f}.")
                review = str((tom_start if not in_tom_now else tom_end).date()) if nine["w_base"] < 1 else str(nxt_q.date())
            elif sl == "9SIG":
                role = "9Sig defensive reserve"
                exit_rule = f"Funds TQQQ buys when the vol switch re-risks or at the quarterly signal ({nxt_q:%b %d}). No price exit."
                review = str(nxt_q.date())
            elif tk == P["fomc_asset"] and (lds.get("fomc_swap") or {}).get("active"):
                dec = pd.Timestamp(lds["fomc_swap"]["decision"])
                role = "Fed-day swap (LDS sleeve)"
                exit_rule = (f"The whole LDS sleeve is parked in {tk} for the Fed decision on {dec:%a %b %d} (statement ~2:00 PM ET). "
                             f"Sold at that day's close; the LDS trend/risk positions are bought back at the same close.")
                review = str(dec.date())
            else:
                d = diag.get(und, {})
                side = "SHORT (inverse ETF)" if any(t == tk and L < 0 for (a, L), t in ETF.items()) else "LONG"
                if side.startswith("SHORT"):
                    role = f"LDS trend overlay — short {und}"
                    exit_rule = f"Held while {und}'s blended 1/3/6/12-month momentum is negative (now {d.get('mom_blend', float('nan')):+.1%}). Reviewed at the monthly close {nxt_week:%a %b %d}."
                elif d.get("trend") == "UP":
                    role = f"LDS core — {und}"
                    exit_rule = (f"Core position: held while {und} closes above its 210-day average (now {d.get('pct_vs_sma', float('nan')):+.1%} vs avg ${d.get('sma', float('nan')):,.2f}). "
                                 f"Exits/resizes at the monthly review, close {nxt_week:%a %b %d}, if the trend breaks or weights shift >5%.")
                else:
                    role = f"LDS overlay — {und} momentum"
                    exit_rule = (f"Core trend is OFF ({und} {d.get('pct_vs_sma', float('nan')):+.1%} vs its 210-day average), so only the small momentum overlay holds it: "
                                 f"long while blended 1/3/6/12-month momentum is positive (now {d.get('mom_blend', float('nan')):+.1%}). Core returns if {und} closes above ${d.get('sma', float('nan')):,.2f} at a monthly review (next {nxt_week:%a %b %d}).")
                review = str(nxt_week.date())
            positions.append(dict(
                ticker=tk, name=NAMES.get(tk, tk), sleeve=sl, underlying=und, shares=round(sh, 4), price=round(close[tk], 4),
                value=round(val, 2), weight=round(val / tot * 100, 2), avg_cost=round(cost / sh, 4) if sh else None,
                cost=round(cost, 2), pl=round(val - cost, 2), pl_pct=round((val / cost - 1) * 100, 2) if cost else 0,
                day_pl=round(sh * (close[tk] - pc), 2), day_pct=round((close[tk] / pc - 1) * 100, 2),
                first_entry=lots[0][0] if lots else None, last_entry=lots[-1][0] if lots else None,
                held_days=(date - pd.Timestamp(lots[0][0])).days if lots else 0,
                lots=[dict(date=l[0], shares=round(l[1], 4), price=round(l[2], 4), pl_pct=round((close[tk] / l[2] - 1) * 100, 2)) for l in lots],
                role=role, exit_rule=exit_rule, next_review=review))
    for sl in ("9SIG", "LDS"):
        c = st["sleeves"][sl]["cash"]
        if abs(c) > 1: positions.append(dict(ticker="CASH", name="Cash", sleeve=sl, value=round(c, 2), weight=round(c / tot * 100, 2),
                                             role="Uninvested cash", exit_rule="", next_review="", shares=None, price=None, pl=0, pl_pct=0, lots=[]))
    realized = sum(t.get("realized_pl", 0) for t in st["trades"])
    unreal = sum(p.get("pl", 0) for p in positions)
    actions = [dict(date=str(nxt_week.date()), what="LDS monthly review (trend + risk sizing) at the close")]
    if nine["w_base"] < 0.999:
        if in_tom_now: actions.append(dict(date=str(tom_end.date()), what="Turn-of-month boost ends: TQQQ back to vol-switch size at the close"))
        else: actions.append(dict(date=str(tom_start.date()), what="Turn-of-month boost: TQQQ to full size at the close"))
    actions.append(dict(date=str(nxt_q.date()), what=f"9Sig quarterly signal (target ${q_target:,.0f})" + (" + year-end 50/50 rebalance" if nxt_q.month in P["rebalance_months"] else "")))
    fs = lds.get("fomc_swap") or {}
    f_dec, f_entry = next_fomc(cal, date)
    if fs.get("active"):
        actions.append(dict(date=fs["decision"], what=f"Fed-day swap ends: sell the LDS sleeve's {P['fomc_asset']} and restore LDS positions at the close"))
    elif f_dec is not None and P["fomc_swap"]:
        actions.append(dict(date=str(f_entry.date()), what=f"Fed-day swap: move the LDS sleeve into {P['fomc_asset']} at the close (Fed decision {f_dec:%a %b %d})"))
    warn = fomc_list_warning(date)
    if st["contrib_monthly"]:
        fm = cal.upcoming(date, cal.is_first_session_of_month, 1)[0]
        actions.append(dict(date=str(fm.date()), what=f"Monthly contribution ${st['contrib_monthly']:,.0f}"))
    actions.sort(key=lambda a: a["date"])
    # effective (actually held) exposure per underlying, as multiples of sleeve / portfolio value
    lev_of = {t: (a, L) for (a, L), t in ETF.items()}
    vl = float(eq.lds.iloc[-1]); exl = defaultdict(float); gross_tot = 0.0
    for sl in ("9SIG", "LDS"):
        for tk, sh in st["sleeves"][sl]["holdings"].items():
            a, L = lev_of[tk]; val = sh * close[tk]; gross_tot += abs(val * L)
            if sl == "LDS": exl[a] += val * L / max(vl, 1e-9)
    return dict(
        meta=dict(version=VERSION, generated=dt.datetime.now().isoformat(timespec="seconds"), as_of=st["last_date"],
                  start_date=st["start_date"], start_capital=st["start_capital"], demo=demo, mode="paper",
                  contrib_monthly=st["contrib_monthly"], warnings=[w for w in [warn] if w]),
        portfolio=dict(value=round(tot, 2), day_pl=round(tot - prev - (eq.contributed.iloc[-1] - (eq.contributed.iloc[-2] if len(eq) > 1 else eq.contributed.iloc[-1])), 2),
                       day_pct=round((tot / prev - 1) * 100, 2), contributed=round(st["contributed"], 2),
                       total_pl=round(tot - st["contributed"], 2), total_pct=round((tot / st["contributed"] - 1) * 100, 2),
                       twr_pct=round((tw - 1) * 100, 2), cagr=round(cagr * 100, 2) if cagr is not None else None,
                       max_dd=round(float(dd.min()) * 100, 2), current_dd=round(float(dd[-1]) * 100, 2),
                       spy_value=float(eq.spy.iloc[-1]), realized_pl=round(realized, 2), unrealized_pl=round(unreal, 2),
                       dividends=round(st["dividends"], 2), n_trades=len(st["trades"]),
                       gross_exposure=round(gross_tot / tot, 2)),
        sleeves=dict(
            nine=dict(value=float(eq.nine.iloc[-1]), weight=round(eq.nine.iloc[-1] / tot * 100, 2), growth=round(nine["S"], 2),
                      defensive=round(nine["B"], 2), tqqq_weight=round(nine["w"] * 100, 1), base_weight=round(nine["w_base"] * 100, 1),
                      vol20=round(v20 * 100, 1) if v20 == v20 else None, tom_active=in_tom_now, tom_start=str(tom_start.date()),
                      tom_end=str(tom_end.date()), quarter_end=str(nxt_q.date()), quarter_target=round(q_target, 2),
                      quarter_gap=round(q_target - nine["S"], 2), skips_left=nine["skips"],
                      dip_active=nine.get("boost") == "Dip", rsi2=round(nine["rsi2"], 1) if nine.get("rsi2") is not None else None,
                      qqq_uptrend=nine.get("qqq_up"), dip_threshold=P["dip_rsi2"]),
            lds=dict(value=float(eq.lds.iloc[-1]), weight=round(eq.lds.iloc[-1] / tot * 100, 2), exposures={k: round(v, 3) for k, v in exl.items()},
                     gross=round(sum(abs(e) for e in exl.values()), 2), last_rebalance=lds.get("last_rebalance"), next_review=str(nxt_week.date()),
                     fomc_active=bool(fs.get("active")), fomc_asset=P["fomc_asset"], review=P["lds_review"], fomc_decision=(fs.get("decision") if fs.get("active") else (str(f_dec.date()) if f_dec is not None else None)),
                     fomc_entry=(fs.get("entered") if fs.get("active") else (str(f_entry.date()) if f_entry is not None else None)),
                     rebalance_day=str(cal.upcoming(date, cal.is_rebalance_day, 1)[0].date()),
                     assets=[dict(sym=a, **{k: (round(v, 4) if isinstance(v, float) else v) for k, v in diag.get(a, {}).items()}) for a in P["lds_assets"]])),
        positions=positions, trades=list(reversed(st["trades"]))[:1500], equity=st["equity"], events=list(reversed(st["events"]))[:150],
        next_actions=actions, reminders=reminders(date), params={k: (list(v) if isinstance(v, tuple) else v) for k, v in P.items()},
    )

def write_summary(sm, path=SUMMARY_PATH):
    def clean(o):
        if isinstance(o, float) and (math.isnan(o) or math.isinf(o)): return None
        if isinstance(o, dict): return {k: clean(v) for k, v in o.items()}
        if isinstance(o, list): return [clean(v) for v in o]
        if isinstance(o, (np.floating,)): return clean(float(o))
        if isinstance(o, (np.integer,)): return int(o)
        if isinstance(o, (np.bool_,)): return bool(o)
        return o
    with open(path, "w") as f: json.dump(clean(sm), f, separators=(",", ":"))

# ----------------------------------------------------------------------------- data
def _naive(df):
    if df is None: return None
    df = df.copy(); ix = pd.DatetimeIndex(df.index)
    if ix.tz is not None: ix = ix.tz_convert("America/New_York").tz_localize(None)
    df.index = ix.normalize(); return df[~df.index.duplicated(keep="last")].sort_index()

def unadjust_splits(close, divs, spl):
    """Yahoo's Close and Dividends are retroactively split-adjusted. Convert them to the raw per-share values
    that existed on each date, so share counts in the ledger stay correct; the split itself is applied on its date."""
    if spl is None: return close, divs
    ratio = spl.reindex(index=close.index, columns=close.columns).fillna(0.0)
    ratio = ratio.where(ratio > 0, 1.0)
    later = ratio.iloc[::-1].cumprod().iloc[::-1].shift(-1).fillna(1.0)   # product of split ratios AFTER each date
    raw = close * later
    rdiv = divs.reindex(index=close.index, columns=close.columns).fillna(0.0) * later if divs is not None else None
    return raw, rdiv

def fetch_yf(years=3, tries=4):
    import time, yfinance as yf
    for i in range(tries):           # Yahoo sometimes throttles cloud runners: retry, then stop with a clear error
        d = yf.download(ALL_TICKERS, period=f"{years}y", auto_adjust=False, actions=True, progress=False, group_by="column")
        if d is not None and len(d) and all(t in d["Close"] and d["Close"][t].notna().any() for t in SIGNAL_TICKERS): break
        if i == tries - 1: raise RuntimeError("Price download from Yahoo failed (empty or missing tickers) - nothing was changed. Try again later.")
        time.sleep(30 * (i + 1))
    adj, close = _naive(d["Adj Close"]), _naive(d["Close"])
    divs = _naive(d["Dividends"]) if "Dividends" in d else None; spl = _naive(d["Stock Splits"]) if "Stock Splits" in d else None
    adj, close = adj.dropna(how="all"), close.dropna(how="all")
    close, divs = unadjust_splits(close, divs, spl)
    return adj, close, divs, spl

def day_prices(close_ff, d, st):
    """closes for day d (forward-filled up to 5 days for stray gaps). Abort if a held or tradable ETF has no price."""
    c = close_ff.loc[d]
    need = set(ALL_TICKERS) | {t for h in st["sleeves"].values() for t in h["holdings"]}
    missing = sorted(t for t in need if t not in c or not (c[t] > 0))
    if missing: raise RuntimeError(f"{d.date()}: no valid price for {', '.join(missing)} - data problem, run stopped (state not saved)")
    return c.to_dict()

def run_days(st, adj, close, dates, divs=None, spl=None, quiet=False):
    cal = Calendar(adj.index); cff = close.ffill(limit=5)
    for d in dates:
        if close.loc[d, SIGNAL_TICKERS].isna().any(): continue          # not a full trading day in the data
        c = day_prices(cff, d, st)
        dv = {t: float(x) for t, x in divs.loc[d].items() if x and x == x and x > 0} if divs is not None and d in divs.index else {}
        sp = {t: float(x) for t, x in spl.loc[d].items() if x and x == x and x > 0 and x != 1} if spl is not None and d in spl.index else {}
        ev = step(st, d, adj.loc[:d], c, cal, dv, sp)
        if not quiet:
            for e in ev: print(f"{d.date()}  {e}")
    return cal

def validate(adj, close, divs, spl, years=3.0, capital=20000.0, outdir=None):
    """Run the exact production engine over the last `years` of REAL prices into a separate folder,
    then run correctness checks. Does not touch state.json / summary.json."""
    outdir = outdir or os.path.join(HERE, "validation")
    os.makedirs(outdir, exist_ok=True)
    start = close.index[-1] - pd.DateOffset(years=years)
    dates = [d for d in close.index if d >= start]
    st = new_state(capital, dates[0], 0.0)
    issues = []; prev_val = None; worst_day = (0, None)
    cal = Calendar(adj.index); cff = close.ffill(limit=5)
    for d in dates:
        if close.loc[d, SIGNAL_TICKERS].isna().any(): continue
        c = pd.Series(day_prices(cff, d, st))
        dv = {t: float(x) for t, x in divs.loc[d].items() if x and x == x and x > 0} if divs is not None and d in divs.index else {}
        sp = {t: float(x) for t, x in spl.loc[d].items() if x and x == x and x > 0 and x != 1} if spl is not None and d in spl.index else {}
        step(st, d, adj.loc[:d], c.to_dict(), cal, dv, sp)
        for sl, h in st["sleeves"].items():
            if h["cash"] < -1: issues.append(f"{d.date()} {sl}: cash went negative (${h['cash']:,.2f})")
            for t, sh in h["holdings"].items():
                if sh < -1e-6: issues.append(f"{d.date()} {sl}: negative shares of {t}")
                if t not in c or not c[t] == c[t] or c[t] <= 0: issues.append(f"{d.date()} {sl}: no price for held {t}")
        v = st["equity"][-1]["value"]
        if prev_val:
            r = v / prev_val - 1
            if r < worst_day[0]: worst_day = (r, d)
        prev_val = v
        if cal.is_rebalance_day(d) and st["equity"][-1]["value"] > 0:
            share = st["equity"][-1]["nine"] / st["equity"][-1]["value"]
            if abs(share - P["split_9sig"]) > 0.02: issues.append(f"{d.date()} year-end split off target: 9Sig {share:.1%}")
        if P["fomc_swap"] and cal.is_pre_fomc(d) and set(st["sleeves"]["LDS"]["holdings"]) - {P["fomc_asset"]}:
            issues.append(f"{d.date()} FOMC swap did not open (LDS holds {sorted(st['sleeves']['LDS']['holdings'])})")
        if cal.is_fomc(d) and (st["lds"].get("fomc_swap") or {}).get("active"):
            issues.append(f"{d.date()} FOMC swap did not close on decision day")
    eq = pd.DataFrame(st["equity"]); v = eq.value.values; spy = eq.spy.values
    yrs = (pd.Timestamp(eq.date.iloc[-1]) - pd.Timestamp(eq.date.iloc[0])).days / 365.25
    tr = pd.DataFrame(st["trades"])
    no_reason = int((tr.reason.fillna("") == "").sum()) if len(tr) else 0
    if no_reason: issues.append(f"{no_reason} trades without a reason")
    yr = pd.Series(v, index=pd.to_datetime(eq.date)).resample("YE").last()
    yr = pd.concat([pd.Series({pd.Timestamp(eq.date.iloc[0]): v[0]}), yr]).pct_change().dropna()
    ys = pd.Series(spy, index=pd.to_datetime(eq.date)).resample("YE").last()
    ys = pd.concat([pd.Series({pd.Timestamp(eq.date.iloc[0]): spy[0]}), ys]).pct_change().dropna()
    lines = [f"TWIN ENGINE VALIDATION  (engine v{VERSION}, real prices {eq.date.iloc[0]} to {eq.date.iloc[-1]})", "",
             f"Start ${capital:,.0f}  ->  ${v[-1]:,.0f}   CAGR {((v[-1]/v[0])**(1/yrs)-1)*100:.1f}%   max drawdown {(v/np.maximum.accumulate(v)-1).min()*100:.1f}%",
             f"Same money in SPY ->  ${spy[-1]:,.0f}   CAGR {((spy[-1]/spy[0])**(1/yrs)-1)*100:.1f}%   max drawdown {(spy/np.maximum.accumulate(spy)-1).min()*100:.1f}%",
             f"Orders {len(tr)} ({len(tr)/yrs:.0f}/yr) on {tr.date.nunique() if len(tr) else 0} trade days ({(tr.date.nunique() if len(tr) else 0)/yrs:.0f}/yr)",
             f"Worst single day {worst_day[0]*100:.1f}% on {worst_day[1].date() if worst_day[1] is not None else '-'}", "",
             "Calendar-year returns (Twin Engine / SPY):"] + [f"  {d.year}: {a*100:+6.1f}% / {ys.get(d, float('nan'))*100:+6.1f}%" for d, a in yr.items()] + [""]
    if len(tr):
        lines += ["Orders by reason:"] + [f"  {k}: {n}" for k, n in tr.reason.str.replace(r" \d+%->\d+%", "", regex=True).value_counts().head(12).items()] + [""]
    lines += ["CHECKS:", f"  {'PASS' if not issues else 'FAIL'}: cash never negative, no negative shares, every held ETF priced, year-end 50/50 split, every trade has a reason, FOMC swaps open and close"]
    lines += [f"   - {x}" for x in issues[:50]]
    rep = "\n".join(lines)
    with open(os.path.join(outdir, "validation_report.txt"), "w") as f: f.write(rep)
    write_summary(build_summary(st, adj, cff.loc[pd.Timestamp(st["last_date"])].to_dict(), cal, demo=True), os.path.join(outdir, "summary.json"))
    tr.to_csv(os.path.join(outdir, "trades.csv"), index=False)
    print(rep); print(f"\nSaved: {os.path.join(outdir, 'validation_report.txt')}, trades.csv, summary.json")
    return not issues

# ----------------------------------------------------------------------------- preview (orders before the close)
def session_close_et(day):
    """(is_session, close time ET as naive datetime) for `day`; 4:00 PM ET without exchange_calendars."""
    try:
        import exchange_calendars as xcals
        c = xcals.get_calendar("XNYS"); ts = pd.Timestamp(day)
        if not c.is_session(ts): return False, None
        return True, c.session_close(ts).tz_convert("America/New_York").tz_localize(None).to_pydatetime()
    except ImportError:
        if pd.Timestamp(day).weekday() >= 5: return False, None
        return True, dt.datetime.combine(day, dt.time(16, 0))

def intraday_last(tickers):
    """latest 1-minute price per ticker today (used when the daily download has no row for today yet)"""
    import yfinance as yf
    d = yf.download(tickers, period="1d", interval="1m", auto_adjust=False, progress=False, group_by="column")
    c = d["Close"].ffill()
    return c.iloc[-1], _naive(c).index[-1]

def preview(a):
    """Simulate today's close with live prices on a copy of the account and list the orders it would place.
    The ledger (state.json) is never changed - the daily run after the close books the real fills."""
    from zoneinfo import ZoneInfo
    now_et = dt.datetime.now(ZoneInfo("America/New_York")).replace(tzinfo=None)
    today = now_et.date()
    is_sess, close_t = session_close_et(today)
    out = dict(generated=now_et.isoformat(timespec="seconds"), date=str(today), version=VERSION, orders=[], trades=[], events=[], warnings=[])
    if not is_sess:
        out["status"] = "closed"; return out
    mins_left = (close_t - now_et).total_seconds() / 60
    if a.window and not (5 <= mins_left <= 65):
        print(f"Outside the preview window ({mins_left:.0f} min to the {close_t:%H:%M} ET close) - skipping."); return None
    if a.window and os.path.exists(PREVIEW_PATH):             # two schedulers (cron-job.org + GitHub backup): one preview a day
        with open(PREVIEW_PATH) as f: old = json.load(f)
        if old.get("date") == str(today) and old.get("status") in ("orders", "no_orders"):
            print(f"Already previewed today at {old.get('prices_as_of')} - skipping."); return None
    out["close_time"] = close_t.strftime("%H:%M")
    adj, close, divs, spl = fetch_yf()
    if close.index[-1].date() != today:                      # no row for today yet: build it from 1-minute bars
        last, ts = intraday_last(ALL_TICKERS)
        row = pd.DataFrame([last.values], index=[pd.Timestamp(today)], columns=last.index)
        close = pd.concat([close, row.reindex(columns=close.columns)]); adj = pd.concat([adj, row.reindex(columns=adj.columns)])
    out["prices_as_of"] = now_et.strftime("%H:%M") + " ET"
    if os.path.exists(STATE_PATH):
        st = copy.deepcopy(load_state())
        missed = [d for d in close.index[:-1] if d > pd.Timestamp(st["last_date"])]
        if missed: out["warnings"].append(f"The daily run hasn't booked {len(missed)} earlier close(s) ({', '.join(str(d.date()) for d in missed)}); they are included here.")
    else:
        st = new_state(a.capital, pd.Timestamp(today), a.contrib)
        out["warnings"].append(f"No account yet: these are the opening orders for ${a.capital:,.0f}.")
    P["fractional"] = st.get("fractional", True) and not a.whole_shares
    st["fractional"] = P["fractional"]
    dates = [close.index[-1]] if st["last_date"] is None else [d for d in close.index if d > pd.Timestamp(st["last_date"])]
    n0 = len(st["trades"]); e0 = len(st["events"])
    run_days(st, adj, close, dates, divs, spl, quiet=True)
    tday = str(today)
    out["trades"] = [t for t in st["trades"][n0:] if t["date"] == tday]
    out["events"] = [e["text"] for e in st["events"][e0:] if e["date"] == tday]
    net = defaultdict(lambda: [0.0, 0.0, []])                # one real account: net the two sleeves per ticker
    for t in out["trades"]:
        s = t["shares"] if t["side"] == "BUY" else -t["shares"]
        n = net[t["ticker"]]; n[0] += s; n[1] = t["price"]; n[2].append(f"{t['sleeve']}: {t['reason']}")
    for tk, (sh, p_, why) in sorted(net.items(), key=lambda x: x[1][0]):   # sells first
        if abs(sh) < 1e-6: continue
        out["orders"].append(dict(ticker=tk, side="BUY" if sh > 0 else "SELL", shares=round(abs(sh), 4), est_price=round(p_, 2),
                                  est_value=round(abs(sh) * p_, 2), reasons=sorted(set(why))))
    out["est_value_after"] = round(st["equity"][-1]["value"], 2) if st["equity"] else None
    out["status"] = "orders" if out["orders"] else "no_orders"
    return out

def preview_markdown(pv):
    if pv.get("status") == "closed":
        return f"## Twin Engine: market closed today ({pv['date']})\n\nNo orders."
    if not pv["orders"]:
        lines = [f"## Twin Engine: no orders today ({pv['date']})", "", "Nothing to place at the close."]
    else:
        lines = [f"## Twin Engine: {len(pv['orders'])} market-on-close order(s) for {pv['date']}", "",
                 f"Place as **MOC** before the {pv.get('close_time', '16:00')} ET close (Schwab cutoff ~15 min earlier). Prices as of {pv.get('prices_as_of')}.", "",
                 "| Side | Ticker | Shares | ~Price | ~Value |", "|---|---|---:|---:|---:|"]
        lines += [f"| {o['side']} | {o['ticker']} | {o['shares']:g} | ${o['est_price']:,.2f} | ${o['est_value']:,.0f} |" for o in pv["orders"]]
        lines += ["", "Why:"] + [f"- {o['ticker']}: " + "; ".join(o["reasons"]) for o in pv["orders"]]
    lines += [f"- {e}" for e in pv["events"] if not pv["orders"]]
    lines += ["", *[f"> {w}" for w in pv["warnings"]]]
    lines += ["", "_Estimate from prices ~30 min before the close. The daily run after the close books the actual paper fills._"]
    return "\n".join(lines)

def main():
    ap = argparse.ArgumentParser(description="Twin Engine paper trader")
    ap.add_argument("cmd", choices=["run", "preview", "status", "reset", "replay", "validate"])
    ap.add_argument("--window", action="store_true", help="preview: only run 5-65 min before today's close (for schedulers)")
    ap.add_argument("--years", type=float, default=3.0)
    ap.add_argument("--capital", type=float, default=P["start_capital"])
    ap.add_argument("--contrib", type=float, default=P["contrib_monthly"])
    ap.add_argument("--csv"); ap.add_argument("--start"); ap.add_argument("--end"); ap.add_argument("--demo", action="store_true")
    ap.add_argument("--whole-shares", action="store_true")
    a = ap.parse_args()
    if a.whole_shares: P["fractional"] = False
    if a.cmd == "reset":
        if input("Delete state.json and start over? type YES: ") == "YES" and os.path.exists(STATE_PATH): os.remove(STATE_PATH)
        return
    if a.cmd == "replay":
        px = pd.read_csv(a.csv, index_col=0, parse_dates=True)
        dates = px.loc[a.start:a.end].index
        st = new_state(a.capital, dates[0], a.contrib)
        cal = run_days(st, px, px, dates)
        save_state(st); write_summary(build_summary(st, px, px.loc[dates[-1]].to_dict(), cal, demo=a.demo)); print("replay done"); return
    if a.cmd == "validate":
        adj, close, divs, spl = fetch_yf(years=max(4, int(a.years) + 2))
        ok = validate(adj, close, divs, spl, a.years, a.capital); sys.exit(0 if ok else 1)
    if a.cmd == "preview":
        pv = preview(a)
        if pv is None: return
        with open(PREVIEW_PATH, "w") as f: json.dump(pv, f, indent=1)
        if pv.get("status") in ("orders", "no_orders"):           # dated copy: the health check compares it with the booked close
            os.makedirs(os.path.join(HERE, "previews"), exist_ok=True)
            with open(os.path.join(HERE, "previews", f"{pv['date']}.json"), "w") as f: json.dump(pv, f, indent=1)
        md = preview_markdown(pv); print(md)
        with open(os.path.join(HERE, "preview.md"), "w", encoding="utf-8") as f: f.write(md)
        if os.environ.get("GITHUB_OUTPUT"):
            with open(os.environ["GITHUB_OUTPUT"], "a") as f: f.write(f"ran=1\norders={len(pv['orders'])}\ndate={pv['date']}\n")
        return
    adj, close, divs, spl = fetch_yf()
    # never treat an intraday price as a close: drop today's row until 4:15 PM ET
    try:
        from zoneinfo import ZoneInfo
        now_et = dt.datetime.now(ZoneInfo("America/New_York"))
        if close.index[-1].date() == now_et.date() and (now_et.hour, now_et.minute) < (16, 15):
            adj, close = adj.iloc[:-1], close.iloc[:-1]
            print("Market hasn't closed yet; using closes through", close.index[-1].date())
    except Exception:
        pass
    last = close.index[-1]
    if not os.path.exists(STATE_PATH):
        start_d = pd.Timestamp(a.start) if a.start else last
        dates = [d for d in close.index if d >= start_d]
        if not dates:
            print(f"No closing prices for {start_d.date()} yet. Run again after the 1:00 PM PT close."); return
        st = new_state(a.capital, dates[0], a.contrib)
        print(f"Starting new paper account: ${a.capital:,.0f} at the close of {dates[0].date()}")
    else:
        st = load_state(); dates = [d for d in close.index if d > pd.Timestamp(st["last_date"])]
        if a.whole_shares and st.get("fractional", True):
            st["fractional"] = False; print("Switched this account to whole-share mode (remembered from now on).")
        P["fractional"] = st.get("fractional", True)
    if a.cmd == "run":
        if not dates: print("Already up to date.");
        cal = run_days(st, adj, close, dates, divs, spl)
        save_state(st)
        write_summary(build_summary(st, adj, close.ffill(limit=5).loc[pd.Timestamp(st["last_date"])].to_dict(), cal))
        print(f"Portfolio value: ${st['equity'][-1]['value']:,.2f}  (summary.json written)")
        w = fomc_list_warning(pd.Timestamp(st["last_date"]))
        if w: print("WARNING:", w)
    if a.cmd == "status":
        sm = json.load(open(SUMMARY_PATH))
        print(f"As of {sm['meta']['as_of']}: ${sm['portfolio']['value']:,.2f}  ({sm['portfolio']['total_pct']:+.1f}%)")
        for p_ in sm["positions"]:
            print(f"  {p_['sleeve']:5s} {p_['ticker']:5s} ${p_['value']:>10,.2f}  {p_['weight']:5.1f}%  P&L {p_['pl_pct']:+6.1f}%  next: {p_['next_review']}")
        for x in sm["next_actions"]: print(f"  NEXT {x['date']}: {x['what']}")

if __name__ == "__main__":
    main()
