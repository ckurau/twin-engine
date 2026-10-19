"""Research copy of twin_engine.step() with switches for idea tests. With every switch at its default it must
reproduce twin_engine.step() exactly (checked by test_lab.py). Helpers (trade, set_targets, ledger, LDS math)
come from the production module, so only the decision logic differs.

Switches (all in te.P, defaults = production v1.3):
  9Sig:  growth (tuple of growth ETFs), derisk_asset (where the vol switch parks the de-risked growth money; None =
         defensive), def_trend (defensive assets below their SMA -> BIL), growth_trend_cap (cap TQQQ weight when QQQ
         < 200d SMA), nine_dip (full TQQQ while QQQ RSI2 < th in an uptrend), tom_before (last N days of month),
         swap_9sig (bullish-day swap also sets 9Sig TQQQ to full)
  LDS:   lds_freq (week/day/month/2week), overlay_long_only, core_topk, mom_months, extra assets via lds_assets
  Swap:  swap_fomc (on), fomc_pre (sessions before decision, 1), fomc_lag (sessions after, 0), swap_tom, swap_preholiday,
         swap_dip, swap_asset ({ticker: weight})
  Split: rebal_band (rebalance when 9Sig share drifts beyond 50% +/- band, checked at month end), tilt (year-end
         split tilted toward last year's lagging engine)
"""
import math, numpy as np, pandas as pd
from collections import defaultdict
import twin_engine as te
from twin_engine import P, ETF, trade, set_targets, sleeve_value, total_value

# extra LDS assets: (underlying, leverage) -> ETF; no inverse ETFs in the panel for these, so overlay is long-only
EXTRA = {("IEF", 1): "IEF", ("IEF", 3): "TYD", ("EEM", 1): "EEM", ("EEM", 3): "EDC", ("IWM", 1): "IWM", ("IWM", 3): "TNA",
         ("SOXX", 1): "SOXX", ("SOXX", 3): "SOXL", ("XLK", 1): "XLK", ("XLK", 3): "TECL", ("XLU", 1): "XLU", ("XLU", 3): "UTSL"}
ETF.update(EXTRA)
LEVS = defaultdict(set)
for (a, L) in ETF: LEVS[a].add(L)

DEFAULTS = dict(growth=("TQQQ",), derisk_asset=None, def_trend=False, def_sma=200, growth_trend_cap=None, nine_dip=None,
                tom_before=1, swap_9sig=False, lds_freq="week", overlay_long_only=False, core_topk=None, mom_months=(1, 3, 6, 12),
                swap_fomc=True, fomc_pre=1, fomc_lag=0, swap_tom=False, swap_preholiday=False, swap_dip=None,
                swap_asset=(("TQQQ", 1.0),), rebal_band=None, tilt=0.0,
                nine_dip_exit=None, swap_fomc_trend=False, swap_frac=1.0, vol_target_winter=None, vol_ewm_hl=None, vol_vix=False,
                core_ew=False, tom_trend=False)

def p(k): return P.get(k, DEFAULTS[k])

class Calendar(te.Calendar):
    def __init__(self, idx):
        self.days = pd.DatetimeIndex(idx); self._pos = {d: i for i, d in enumerate(self.days)}
    def next_day(self, d):
        i = self._pos.get(d)
        if i is not None and i + 1 < len(self.days): return self.days[i + 1]
        j = self.days.searchsorted(d, side="right")
        return self.days[j] if j < len(self.days) else d + pd.offsets.BDay(1)
    def is_tom(self, d):
        i = self._pos.get(d, self.days.searchsorted(d)); k = p("tom_before")
        for j in range(1, k + 1):
            if i + j >= len(self.days) or self.days[i + j].month != d.month: return True
        kk = 0
        while i - kk - 1 >= 0 and self.days[i - kk - 1].month == d.month: kk += 1
        return kk < P["tom_after"]
    def is_pre_holiday(self, d):
        n = self.next_day(d); gap = (n - d).days
        return gap > 1 and not (d.weekday() == 4 and gap == 3)
    def is_fomc_window(self, d):
        """session d is inside [decision - (fomc_pre-1), decision + fomc_lag]"""
        i = self._pos.get(d)
        if i is None: return False
        for j in range(-p("fomc_lag"), p("fomc_pre")):
            k = i + j
            if 0 <= k < len(self.days) and self.days[k] in te.FOMC_DATES: return True
        return False

def vol_switch(px, adj, date):
    r = px.pct_change().dropna()
    if p("vol_vix"): v = float(adj["VIXLVL"].iloc[-1]) / 100 * 3
    elif p("vol_ewm_hl"): v = float(np.sqrt(r.iloc[-200:].ewm(halflife=p("vol_ewm_hl")).var().iloc[-1] * 252))
    else:
        r = r.iloc[-P["vol_lookback"]:]; v = float(r.std(ddof=1) * math.sqrt(252)) if len(r) >= P["vol_lookback"] else float("nan")
    tgt = p("vol_target_winter") if p("vol_target_winter") and date.month in (11, 12, 1, 2, 3, 4) else P["vol_target"]
    if not v or math.isnan(v): return 1.0, v
    return float(min(max((tgt / v) ** P["vol_power"], 0.0), 1.0)), v

def rsi2(s):
    r = s.diff().iloc[-3:]
    up = r.clip(lower=0).ewm(alpha=1 / 2, adjust=False).mean().iloc[-1]; dn = (-r.clip(upper=0)).ewm(alpha=1 / 2, adjust=False).mean().iloc[-1]
    return 100.0 if dn == 0 else 100 - 100 / (1 + up / dn)

def _mom(px, months): k = 21 * months; return float(px.iloc[-1] / px.iloc[-1 - k] - 1) if len(px) > k else float("nan")

def lds_exposures(adj):
    A = list(P["lds_assets"]); px = adj[A].dropna(); r = px.pct_change().dropna(); n = P["cov_days"]
    diag, core = {}, {}
    for a in A:
        s = px[a]; sma = float(s.iloc[-P["sma_days"]:].mean()); up = float(s.iloc[-1]) >= sma
        v = te._vol(r[a], n); bm = np.nanmean([_mom(s, k) for k in p("mom_months")])
        diag[a] = dict(price=float(s.iloc[-1]), sma=sma, trend="UP" if up else "DOWN", vol63=v, mom_blend=float(bm))
        if up: core[a] = 1.0 if p("core_ew") else 1 / v
    if p("core_topk") and len(core) > p("core_topk"):
        keep = sorted(core, key=lambda a: -diag[a]["mom_blend"])[:p("core_topk")]; core = {a: core[a] for a in keep}
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
        if bm <= 0 and (p("overlay_long_only") or not any(L < 0 for L in LEVS[a])): continue
        ov[a] = (1 if bm > 0 else -1) / diag[a]["vol63"]
    ov = scale(ov, P["lds_overlay_vol"])
    ex = defaultdict(float)
    for a, e in core.items(): ex[a] += P["lds_core"] * e
    for a, e in ov.items(): ex[a] += P["lds_overlay"] * e
    return dict(ex), diag

def implement(expo):
    expo = {a: e for a, e in expo.items() if abs(e) > 1e-6}
    if not expo: return {}
    def lev_for(a, e, k):
        if a in te.LMAX_LONG:
            lm = te.LMAX_LONG[a] if e > 0 else te.LMAX_SHORT[a]; L = min(k, lm)
            if e < 0 and a == "GLD": L = 2
            return L if e > 0 else -L
        ok = sorted(L for L in LEVS[a] if L > 0 and L <= k) or [1]          # extra assets: 1x or 3x only
        return ok[-1]
    for k in (1, 2, 3):
        caps = {}
        for a, e in expo.items():
            L = lev_for(a, e, k); caps[ETF[(a, L)]] = caps.get(ETF[(a, L)], 0) + abs(e) / abs(L)
        if sum(caps.values()) <= 1 + 1e-9: return caps
    caps = {}
    for a, e in expo.items():
        L = lev_for(a, e, 3); caps[ETF[(a, L)]] = caps.get(ETF[(a, L)], 0) + abs(e) / abs(L)
    s = sum(caps.values()); return {t: c / max(s, 1.0) for t, c in caps.items()}

def lds_review_due(cal, d):
    f = p("lds_freq")
    if f == "week": return cal.is_week_end(d)
    if f == "day": return True
    if f == "month": return cal.is_month_end(d)
    if f == "2week": return cal.is_week_end(d) and d.isocalendar()[1] % 2 == 0
    raise ValueError(f)

def step(st, date, adj, close, cal, divs=None, splits=None):
    nine, lds = st["nine"], st["lds"]
    ev = []
    growth = list(p("growth")); deff = list(P["defensive"])
    prev = st["prev_close"]
    if nine["initialized"] and prev:
        rq = np.mean([close[t] / prev[t] - 1 for t in growth])
        dh = nine.get("def_hold") or deff
        rd = np.mean([close[t] / prev[t] - 1 for t in dh])
        rx = close[p("derisk_asset")] / prev[p("derisk_asset")] - 1 if p("derisk_asset") else rd
        a = nine["w"] * rq + (1 - nine["w"]) * rx
        nine["S"] *= 1 + a; nine["B"] *= 1 + rd; nine["growth_index"] *= 1 + a
        v9 = sleeve_value(st, "9SIG", close); f = v9 / max(nine["S"] + nine["B"], 1e-9)
        nine["S"] *= f; nine["B"] *= f
    q_end = cal.is_quarter_end(date)
    nine_trade = not nine["initialized"]
    if q_end and nine["initialized"]:
        qr = nine["growth_index"] / nine["q_anchor"] - 1; nine["q_anchor"] = nine["growth_index"]
        if qr <= P["crash_qtr"]: nine["skips"] = P["skip_after_crash"]
        target = nine["last_target"] * (1 + P["sig_rate"]) + 0.5 * nine["new_cash"]
        diff = target - nine["S"]
        if diff < 0 and nine["skips"] > 0: nine["skips"] -= 1
        elif diff < 0: nine["S"] += diff; nine["B"] -= diff
        else: buy = min(diff, nine["B"]); nine["S"] += buy; nine["B"] -= buy
        nine["last_target"] = nine["S"]; nine["new_cash"] = 0.0; nine_trade = True
    # --- split between engines
    lds_force = not st["last_date"]
    rebal = cal.is_rebalance_day(date)
    split = P["split_9sig"]
    if rebal and p("tilt") and st.get("year_mark"):
        ym = st["year_mark"]; r9 = sleeve_value(st, "9SIG", close) / ym[0]; rl = sleeve_value(st, "LDS", close) / ym[1]
        split = split + (p("tilt") if r9 < rl else -p("tilt"))
    if p("rebal_band") is not None and st["last_date"] and cal.is_month_end(date):
        sh = sleeve_value(st, "9SIG", close) / total_value(st, close)
        if abs(sh - P["split_9sig"]) > p("rebal_band"): rebal = True
    if rebal and st["last_date"]:
        v9, vl = sleeve_value(st, "9SIG", close), sleeve_value(st, "LDS", close)
        tot = v9 + vl; t9 = tot * split; move = t9 - v9
        if abs(move) > P["min_order"]:
            fl = (tot - t9) / vl
            tg = {t: sh * close[t] * fl for t, sh in st["sleeves"]["LDS"]["holdings"].items()}
            if move > 0:
                set_targets(st, "LDS", tg, close, date, "Year-end 50/50 rebalance")
                move = min(move, max(st["sleeves"]["LDS"]["cash"], 0.0))
            st["sleeves"]["LDS"]["cash"] -= move; st["sleeves"]["9SIG"]["cash"] += move
            if move < 0: set_targets(st, "LDS", tg, close, date, "Year-end 50/50 rebalance")
            f9 = (v9 + move) / v9; nine["S"] *= f9; nine["B"] *= f9; nine["last_target"] *= f9
            nine_trade = True
    if cal.is_rebalance_day(date) or not st.get("year_mark"):
        st["year_mark"] = None  # set after trades below
    # --- 9Sig weight for tomorrow
    vt = adj[growth[0]].dropna()
    raw, v20 = vol_switch(vt, adj, date)
    if abs(raw - nine["w_base"]) > P["vol_band"] or not nine["initialized"]: nine["w_base"] = raw
    base = nine["w_base"]
    qqq = adj["QQQ"].dropna()
    if p("growth_trend_cap") is not None and float(qqq.iloc[-1]) < float(qqq.iloc[-200:].mean()): base = min(base, p("growth_trend_cap"))
    tomorrow = cal.next_day(date); tom = cal.is_tom(tomorrow)
    bull = _bullish(st, cal, date, tomorrow, adj)
    uptrend = float(qqq.iloc[-1]) > float(qqq.iloc[-200:].mean())
    if p("tom_trend") and not uptrend: tom = False
    full = tom or (p("swap_9sig") and bull)
    if p("nine_dip") is not None:
        r2 = rsi2(qqq); on = nine.get("dip_on", False)
        if p("nine_dip_exit") is None: on = uptrend and r2 < p("nine_dip")
        elif not on and uptrend and r2 < p("nine_dip"): on = True
        elif on and r2 > p("nine_dip_exit"): on = False
        nine["dip_on"] = on; full = full or on
    w_new = 1.0 if full else base
    def_new = deff
    if p("def_trend"):
        def_new = [t for t in deff if float(adj[t].iloc[-1]) >= float(adj[t].iloc[-p("def_sma"):].mean())] or ["BIL"]
        if len(def_new) < len(deff) and "BIL" not in def_new: def_new = def_new + ["BIL"] * (len(deff) - len(def_new))
    def_changed = (nine.get("def_hold") or deff) != def_new
    if abs(w_new - nine["w"]) > 1e-9 or nine_trade or def_changed:
        nine["w"] = w_new; nine["def_hold"] = def_new
        v9 = sleeve_value(st, "9SIG", close)
        if not nine["initialized"]: nine["S"], nine["B"] = v9 * P["w0_growth"], v9 * (1 - P["w0_growth"]); nine["last_target"] = nine["S"]
        tg = defaultdict(float)
        for g in growth: tg[g] += nine["w"] * nine["S"] / len(growth)
        rest = (1 - nine["w"]) * nine["S"]
        if p("derisk_asset"): tg[p("derisk_asset")] += rest; dfn = nine["B"]
        else: dfn = rest + nine["B"]
        for t in def_new: tg[t] += dfn / len(def_new)
        set_targets(st, "9SIG", dict(tg), close, date, "9Sig rebalance")
        nine["initialized"] = True
    # --- LDS: bullish-session swap (Fed day and optional calendar/dip days)
    ex, diag = lds_exposures(adj)
    sw = lds.get("swap") or {}
    swapped_back = False
    if sw.get("active") and not bull:
        caps = implement(ex); vl = sleeve_value(st, "LDS", close)
        set_targets(st, "LDS", {t: c * vl for t, c in caps.items()}, close, date, "Swap ends: LDS positions restored")
        lds["exposures"] = ex; lds["swap"] = dict(active=False); swapped_back = True
    if (lds_review_due(cal, date) or lds_force) and not swapped_back and not sw.get("active"):
        caps = implement(ex); vl = sleeve_value(st, "LDS", close)
        tg = {t: c * vl for t, c in caps.items()}
        cur = {t: sh * close[t] for t, sh in st["sleeves"]["LDS"]["holdings"].items()}
        turn = sum(abs(tg.get(t, 0) - cur.get(t, 0)) for t in set(tg) | set(cur))
        if turn > P["lds_threshold"] * vl or lds_force:
            set_targets(st, "LDS", tg, close, date, "LDS rebalance"); lds["exposures"] = ex
    if bull and not (lds.get("swap") or {}).get("active"):
        vl = sleeve_value(st, "LDS", close)
        f = p("swap_frac"); tg = defaultdict(float)
        for t, w in p("swap_asset"): tg[t] += w * vl * f
        if f < 1:
            for t, sh in st["sleeves"]["LDS"]["holdings"].items(): tg[t] += sh * close[t] * (1 - f)
        set_targets(st, "LDS", dict(tg), close, date, "Swap: LDS into TQQQ")
        lds["swap"] = dict(active=True, entered=str(date.date()))
    # --- bookkeeping
    tot = total_value(st, close)
    if st["spy_units"] is None: st["spy_units"] = st["start_capital"] / close["SPY"]
    st["equity"].append(dict(date=str(date.date()), value=round(tot, 2), nine=round(sleeve_value(st, "9SIG", close), 2), lds=round(sleeve_value(st, "LDS", close), 2)))
    if st.get("year_mark") is None: st["year_mark"] = (sleeve_value(st, "9SIG", close), sleeve_value(st, "LDS", close))
    st["prev_close"] = close; st["last_date"] = str(date.date())
    return ev

def _bullish(st, cal, date, tomorrow, adj):
    """should the LDS sleeve hold the swap asset during session `tomorrow`? (dip state updates every day)"""
    dip = False
    if p("swap_dip") is not None:
        q = adj["QQQ"].dropna(); th, ex_th = p("swap_dip")
        lds = st["lds"]; on = lds.get("dip_on", False); r = rsi2(q)
        if not on and r < th and float(q.iloc[-1]) > float(q.iloc[-200:].mean()): on = True
        elif on and r > ex_th: on = False
        lds["dip_on"] = dip = on
    if p("swap_fomc") and P["fomc_swap"] and cal.is_fomc_window(tomorrow):
        q = adj["QQQ"].dropna()
        if not p("swap_fomc_trend") or float(q.iloc[-1]) > float(q.iloc[-200:].mean()): return True
    if p("swap_tom") and cal.is_tom(tomorrow): return True
    if p("swap_preholiday") and cal.is_pre_holiday(tomorrow): return True
    return dip
