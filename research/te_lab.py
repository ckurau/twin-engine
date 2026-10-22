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
                core_ew=False, tom_trend=False,
                growth_rot=None, nine_cap=None, lds_riskoff=False, ndx_cap=None, dip_kind="rsi2",
                cash_yield=False, core_trend="sma", core_erc=False, vol_fast=False, def_relmom=None, def_lev_trend=False,
                nine_buy_only=False, vol_target_trend=None, lds_max_lev=False, core_mom_weight=False, growth_vol_blend=False)
LEV_OF = {t: (a, L) for (a, L), t in ETF.items()}

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
        rr = r.iloc[-P["vol_lookback"]:]; v = float(rr.std(ddof=1) * math.sqrt(252)) if len(rr) >= P["vol_lookback"] else float("nan")
        if p("vol_fast") and len(r) >= 10: v = max(v, float(r.iloc[-10:].std(ddof=1) * math.sqrt(252)))
    tgt = p("vol_target_winter") if p("vol_target_winter") and date.month in (11, 12, 1, 2, 3, 4) else P["vol_target"]
    if p("vol_target_trend"):
        q = adj["QQQ"].dropna(); tgt = p("vol_target_trend")[0] if float(q.iloc[-1]) > float(q.iloc[-200:].mean()) else p("vol_target_trend")[1]
    if not v or math.isnan(v): return 1.0, v
    return float(min(max((tgt / v) ** P["vol_power"], 0.0), 1.0)), v

def _sma(s, n): return float(s.iloc[-n:].mean())

def _m13612(s):
    s = s.dropna()
    if len(s) < 253: return float("nan")
    r = lambda k: float(s.iloc[-1] / s.iloc[-1 - 21 * k] - 1)
    return (12 * r(1) + 4 * r(3) + 2 * r(6) + r(12)) / 4

def riskoff(st, adj, cal, date):
    """True when the chosen crash-warning signal is on (evaluated at today's close)"""
    nc = p("nine_cap")
    if not nc: return False
    sig = nc[0]; arg = nc[2] if len(nc) > 2 else None; nine = st["nine"]
    if sig == "ts":
        v, v3 = adj["VIXLVL"].iloc[-1], adj["VIX3M"].iloc[-1]
        return bool(v3 == v3 and v > v3 * (arg or 1.0))
    if sig == "vixspike":
        v = adj["VIXLVL"].dropna(); left = nine.get("spike_left", 0)
        if len(v) > 11 and v.iloc[-1] >= (arg or 1.25) * float(v.iloc[-11:-1].mean()): left = 5
        else: left = max(0, left - 1)
        nine["spike_left"] = left; return left > 0
    if sig == "vvix":
        v = adj["VVIX"].iloc[-1]; return bool(v == v and v > (arg or 120))
    if sig == "canary":
        if cal.is_month_end(date) or "canary_on" not in nine:
            nine["canary_on"] = any(_m13612(adj[c]) < 0 for c in ("EEM", "VBMFX"))
        return nine["canary_on"]
    if sig == "credit":
        r = (adj["VWEHX"] / adj["VFITX"]).dropna(); n = arg or 50
        return bool(len(r) >= n and float(r.iloc[-1]) < _sma(r, n))
    raise ValueError(sig)

def dip_signal(adj, kind, th):
    q = adj["QQQ"].dropna(); up = float(q.iloc[-1]) > _sma(q, 200)
    if not up: return False
    hits = []
    if "rsi2" in kind: hits.append(rsi2(q) < th)
    if "ibs" in kind:
        h, l, c = adj["QQQ_H"].iloc[-1], adj["QQQ_L"].iloc[-1], adj["QQQ_C"].iloc[-1]
        hits.append(bool(h > l and (c - l) / (h - l) < 0.2))
    if "vixstretch" in kind:
        v = adj["VIXLVL"].dropna()
        hits.append(len(v) > 13 and all(v.iloc[-1 - j] >= 1.05 * float(v.iloc[-11 - j:-1 - j].mean()) for j in range(3)))
    return any(hits)

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
        m12 = _mom(s, 12)
        if p("core_trend") == "or_mom": up = up or (m12 == m12 and m12 > 0)
        elif p("core_trend") == "and_mom": up = up and (m12 == m12 and m12 > 0)
        if up: core[a] = 1.0 if p("core_ew") else (max(bm, 0.0) + 1e-4) / v if p("core_mom_weight") else 1 / v
    if p("core_topk") and len(core) > p("core_topk"):
        keep = sorted(core, key=lambda a: -diag[a]["mom_blend"])[:p("core_topk")]; core = {a: core[a] for a in keep}
    def scale(w, V):
        if not w: return {}
        tot = sum(abs(x) for x in w.values()); w = {a: x / tot for a, x in w.items()}
        ks = list(w); C = np.atleast_2d(np.cov(r[ks].iloc[-n:].values.T) * 252); x = np.array([w[a] for a in ks])
        pv = float(np.sqrt(max(x @ C @ x, 1e-12))); return {a: w[a] * V / pv for a in ks}
    if p("core_erc") and len(core) > 1:                      # equal risk contribution using the covariance matrix
        ks = list(core); C = np.cov(r[ks].iloc[-n:].values.T) * 252; w = np.array([core[a] for a in ks]); w = w / w.sum()
        for _ in range(100):
            rc = w * (C @ w); w = w * (rc.mean() / np.maximum(rc, 1e-12)) ** 0.5; w = w / w.sum()
        core = dict(zip(ks, w))
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

def implement(expo, kmax=3):
    expo = {a: e for a, e in expo.items() if abs(e) > 1e-6}
    if not expo: return {}
    def lev_for(a, e, k):
        if a in te.LMAX_LONG:
            lm = te.LMAX_LONG[a] if e > 0 else te.LMAX_SHORT[a]; L = min(k, lm)
            if e < 0 and a == "GLD": L = 2
            return L if e > 0 else -L
        ok = sorted(L for L in LEVS[a] if L > 0 and L <= k) or [1]          # extra assets: 1x or 3x only
        return ok[-1]
    for k in ([kmax] if p("lds_max_lev") else [k for k in (1, 2, 3) if k <= kmax]):
        caps = {}
        for a, e in expo.items():
            L = lev_for(a, e, k); caps[ETF[(a, L)]] = caps.get(ETF[(a, L)], 0) + abs(e) / abs(L)
        if sum(caps.values()) <= 1 + 1e-9:
            if p("lds_max_lev") and sum(caps.values()) < 1 - 1e-6: caps["BIL"] = caps.get("BIL", 0) + 1 - sum(caps.values())
            return caps
    caps = {}
    for a, e in expo.items():
        L = lev_for(a, e, kmax); caps[ETF[(a, L)]] = caps.get(ETF[(a, L)], 0) + abs(e) / abs(L)
    s = sum(caps.values()); return {t: c / max(s, 1.0) for t, c in caps.items()}

def lds_review_due(cal, d):
    f = p("lds_freq")
    if f == "week": return cal.is_week_end(d)
    if f == "day": return True
    if f == "month": return cal.is_month_end(d)
    if f == "2week": return cal.is_week_end(d) and d.isocalendar()[1] % 2 == 0
    if f == "midmonth":
        i = cal._pos.get(d); return d.day >= 15 and (i is None or i == 0 or cal.days[i - 1].day < 15 or cal.days[i - 1].month != d.month)
    raise ValueError(f)

def step(st, date, adj, close, cal, divs=None, splits=None):
    nine, lds = st["nine"], st["lds"]
    ev = []
    growth = [nine.get("gasset") or p("growth")[0]] if p("growth_rot") else list(p("growth")); deff = list(P["defensive"])
    prev = st["prev_close"]
    if p("cash_yield") and prev:
        for sl in st["sleeves"].values():
            if sl["cash"] > 0: sl["cash"] *= 1 + close["RF"]
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
        elif diff < 0 and p("nine_buy_only"): pass
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
    # --- 9Sig growth ETF rotation (month end): best relative momentum among the candidates
    if p("growth_rot") and (cal.is_month_end(date) or not nine.get("gasset")):
        cands, months, mode = p("growth_rot"); und = {"TQQQ": "QQQ", "UPRO": "SPY", "TNA": "IWM", "TECL": "XLK", "SOXL": "SOXX"}
        if mode == "ratio200":
            r = (adj["QQQ"] / adj["SPY"]).dropna(); pick = "TQQQ" if float(r.iloc[-1]) > _sma(r, 200) else "UPRO"
        else:
            sc = {c: _mom(adj[und[c]].dropna(), months) for c in cands}; sc = {c: v for c, v in sc.items() if v == v}
            pick = max(sc, key=sc.get) if sc else cands[0]
        if pick != nine.get("gasset"):
            nine["gasset"] = pick; growth = [pick]; nine_trade = True
    # --- 9Sig weight for tomorrow
    if len(set(growth)) > 1 and p("growth_vol_blend"):     # mixed growth sub-sleeve: volatility of the mix (weights = repeats in the tuple)
        vt = (1 + adj[growth].pct_change().fillna(0).mean(axis=1)).cumprod()
    else:
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
    roff = riskoff(st, adj, cal, date)
    if p("nine_dip") is not None:
        r2 = rsi2(qqq); on = nine.get("dip_on", False)
        if p("nine_dip_exit") is None: on = dip_signal(adj, p("dip_kind"), p("nine_dip"))
        elif not on and uptrend and r2 < p("nine_dip"): on = True
        elif on and r2 > p("nine_dip_exit"): on = False
        nine["dip_on"] = on; full = full or on
    w_new = 1.0 if full else base
    if roff: w_new = min(base, p("nine_cap")[1])
    def_new = deff
    if p("def_trend"):
        def_new = [t for t in deff if float(adj[t].iloc[-1]) >= float(adj[t].iloc[-p("def_sma"):].mean())] or ["BIL"]
        if len(def_new) < len(deff) and "BIL" not in def_new: def_new = def_new + ["BIL"] * (len(deff) - len(def_new))
    if p("def_relmom"):
        sc = {t: _mom(adj[t].dropna(), p("def_relmom")) for t in deff}; def_new = [max(sc, key=sc.get)]
    if p("def_lev_trend"):
        lev = {"TLT": "TMF", "GLD": "UGL", "IEF": "TYD"}
        def_new = [lev.get(t, t) if float(adj[t].iloc[-1]) >= _sma(adj[t].dropna(), 200) else "BIL" for t in deff]
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
    kmax = 1 if (p("lds_riskoff") and roff) else 3
    def lds_targets(caps, vl):
        tg = {t: c * vl for t, c in caps.items()}
        if p("ndx_cap") is not None and tg.get("TQQQ", 0) > 0:
            room = max(0.0, p("ndx_cap") * total_value(st, close) - st["sleeves"]["9SIG"]["holdings"].get("TQQQ", 0) * close["TQQQ"])
            if tg["TQQQ"] > room: tg["UPRO"] = tg.get("UPRO", 0) + tg["TQQQ"] - room; tg["TQQQ"] = room
        return tg
    if p("lds_riskoff") and not (lds.get("swap") or {}).get("active") and st["last_date"] and bool(lds.get("delev")) != (kmax == 1):
        vl = sleeve_value(st, "LDS", close)
        set_targets(st, "LDS", lds_targets(implement(ex, kmax), vl), close, date, "LDS risk-off" if kmax == 1 else "LDS risk back on")
        lds["delev"] = kmax == 1
    sw = lds.get("swap") or {}
    swapped_back = False
    if sw.get("active") and not bull:
        caps = implement(ex, kmax); vl = sleeve_value(st, "LDS", close)
        set_targets(st, "LDS", lds_targets(caps, vl), close, date, "Swap ends: LDS positions restored")
        lds["exposures"] = ex; lds["swap"] = dict(active=False); swapped_back = True
    if (lds_review_due(cal, date) or lds_force) and not swapped_back and not sw.get("active"):
        caps = implement(ex, kmax); vl = sleeve_value(st, "LDS", close)
        tg = lds_targets(caps, vl)
        cur = {t: sh * close[t] for t, sh in st["sleeves"]["LDS"]["holdings"].items()}
        turn = sum(abs(tg.get(t, 0) - cur.get(t, 0)) for t in set(tg) | set(cur))
        if turn > P["lds_threshold"] * vl or lds_force:
            set_targets(st, "LDS", tg, close, date, "LDS rebalance"); lds["exposures"] = ex
    if bull and not (lds.get("swap") or {}).get("active") and not (p("lds_riskoff") and roff):
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
    ex_u = defaultdict(float)
    for sl in st["sleeves"].values():
        for t, sh in sl["holdings"].items():
            if t in LEV_OF: a, L = LEV_OF[t]; ex_u[a] += sh * close[t] * L / tot
            else: ex_u[t] += sh * close[t] / tot
    st["equity"].append(dict(date=str(date.date()), value=round(tot, 2), nine=round(sleeve_value(st, "9SIG", close), 2), lds=round(sleeve_value(st, "LDS", close), 2), x=dict(ex_u)))
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
