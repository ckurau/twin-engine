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
                nine_buy_only=False, vol_target_trend=None, lds_max_lev=False, core_mom_weight=False, growth_vol_blend=False,
                vol_semi=False, vol_park=False, vol_off_high=None, vrp=None, vol_hyst=None, vol_floor=None, cppi=None,
                regime_split=None, santa=False, nfp=False, wk_dip=None, nine_tp=None, nine_bd=None, sig_rate_trend=None,
                def_invvol=False, lds_corr_cut=False, lds_idle=None, dual_fast=50,
                dual_ema=False, tri_fast=None, dual_band=None, overlay_dual=False, lds_exit_check=None, core_strength=None,
                nine_dual_cap=None, def_dual=False, lds_crash=None, dd_boost=None, swap_fomc_dual=False, q_gate=None, q_sell_skip_dual=False,
                mom_skip1=False, dip_lev=None,
                cap_sig=None, boost_sig=None, split_sig=None, tlt_carry=False, overlay_bear=False, chand=None, trend_params=None,
                res_swap=None, split_dyn=None,
                lds_sig=None, swap_sig=None, dip_sig=None, tom_sig=None, vt_sig=None, res_sig=None, qsell_sig=None, swap_asset_sig=None,
                vol_ens=None, overlay_vix=None)
LDS_MEM = {}      # per-run memory for hysteresis (reset by bt.run)
ENSF = {}
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
        if p("vol_semi") and len(rr) >= 10: v = float(math.sqrt(2 * (np.minimum(rr.values, 0) ** 2).mean()) * math.sqrt(252))
        if p("vol_park"):
            h, l = adj["QQQ_H"].iloc[-P["vol_lookback"]:], adj["QQQ_L"].iloc[-P["vol_lookback"]:]
            x = np.log(h / l).dropna()
            if len(x) >= 10: v = float(3 * math.sqrt((x ** 2).mean() / (4 * math.log(2)) * 252))
        if p("vol_fast") and len(r) >= 10: v = max(v, float(r.iloc[-10:].std(ddof=1) * math.sqrt(252)))
        if p("vol_ens") and len(r) >= max(p("vol_ens")): v = float(np.mean([r.iloc[-n:].std(ddof=1) for n in p("vol_ens")]) * math.sqrt(252))
    tgt = p("vol_target_winter") if p("vol_target_winter") and date.month in (11, 12, 1, 2, 3, 4) else P["vol_target"]
    if p("vol_target_trend"):
        q = adj["QQQ"].dropna(); tgt = p("vol_target_trend")[0] if float(q.iloc[-1]) > float(q.iloc[-200:].mean()) else p("vol_target_trend")[1]
    if p("vrp"):
        ratio, hi = p("vrp"); s_ = adj["SPY"].dropna().pct_change().iloc[-20:]; rv = float(s_.std() * math.sqrt(252) * 100)
        if rv > 0 and float(adj["VIXLVL"].iloc[-1]) / rv > ratio: tgt = hi
    if p("vol_off_high") is not None:
        q = adj["QQQ"].dropna()
        if float(q.iloc[-1]) >= (1 - p("vol_off_high")) * float(q.iloc[-252:].max()): return 1.0, v
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

def _col(adj, *names):
    for n in names:
        if n in adj and adj[n].notna().sum() > 30: return adj[n].dropna()
    return None

def _hlc(adj):
    h, l, c = _col(adj, "QQQ_H"), _col(adj, "QQQ_L"), _col(adj, "QQQ_C")
    if h is None or len(h) < 30: h, l, c = _col(adj, "NDX_H"), _col(adj, "NDX_L"), _col(adj, "NDX_C")
    return h, l, c

def sig(spec, adj, st, date, cal, tomorrow):
    """True = favourable / risk-on, False = unfavourable / risk-off, None = no data (neutral); cached per day"""
    cache = st.setdefault("sigcache", {}); key = repr(spec)
    if key in cache and cache[key][0] == date: return cache[key][1]
    v = _sig(spec, adj, st, date, cal, tomorrow); cache[key] = (date, v); return v

def _sig(spec, adj, st, date, cal, tomorrow):
    name = spec[0]; a = spec[1:] if len(spec) > 1 else ()
    q = adj["QQQ"].dropna(); mem = st.setdefault("sigmem", {})
    def above(x, n=200): return bool(float(x.iloc[-1]) > float(x.iloc[-n:].mean())) if x is not None and len(x) >= n else None
    if name == "fomc_even":
        past = [d for d in te.FOMC_DATES if d <= tomorrow]
        if not past: return None
        w = (tomorrow - max(past)).days // 7; return w in (0, 2, 4, 6)
    if name == "dist":
        v = _col(adj, "QQQ_V") if _col(adj, "QQQ_V") is not None and len(_col(adj, "QQQ_V")) > 30 else _col(adj, "NDX_V")
        if v is None or len(v) < 30 or float(v.iloc[-25:].min()) <= 0: return None
        c = q.reindex(v.index).dropna(); r = c.pct_change(); dv = v.reindex(c.index).diff()
        n = int(((r.iloc[-25:] < -0.002) & (dv.iloc[-25:] > 0)).sum()); return n < a[0]
    if name == "vcp":
        if len(q) < 260: return None
        rr = q.pct_change(); near = float(q.iloc[-1]) >= 0.95 * float(q.iloc[-252:].max())
        return bool(near and float(rr.iloc[-10:].std()) < a[0] * float(rr.iloc[-60:].std()))
    if name == "holy":
        h, l, c = _hlc(adj)
        if c is None or len(c) < 210: return None
        e20 = float(c.ewm(span=20).mean().iloc[-1])
        return bool(float(c.iloc[-1]) > float(c.iloc[-50:].mean()) > float(c.iloc[-200:].mean()) and float(l.iloc[-1]) <= e20 * (1 + a[0]) and float(c.iloc[-1]) > e20)
    if name == "willr":
        h, l, c = _hlc(adj)
        if c is None or len(c) < 210: return None
        hh, ll = float(h.iloc[-10:].max()), float(l.iloc[-10:].min())
        wr = -100 * (hh - float(c.iloc[-1])) / (hh - ll) if hh > ll else -50
        return bool(wr < a[0] and float(c.iloc[-1]) > float(c.iloc[-200:].mean()))
    if name == "dow":
        x, y = above(_col(adj, "DJI")), above(_col(adj, "DJT"))
        return None if x is None or y is None else bool(x and y)
    if name == "cu_au":
        c, g = _col(adj, "HG"), _col(adj, "GCF")
        if c is None or g is None: return None
        r = (c / g.reindex(c.index)).dropna(); return above(r)
    if name == "usd_down":
        x = above(_col(adj, "DXY")); return None if x is None else not x
    if name == "easing":
        x = _col(adj, "IRXL")
        if x is None or len(x) < 130: return None
        return bool(float(x.iloc[-1]) < float(x.iloc[-127]) - a[0])
    if name == "small_lead":
        return above((adj["IWM"] / adj["SPY"]).dropna())
    if name == "semi_lead":
        return above((adj["SOXX"] / adj["QQQ"]).dropna())
    if name == "corr":
        r = adj[["SPY", "QQQ", "IWM", "EEM"]].dropna().pct_change().iloc[-20:]
        if len(r) < 20: return None
        c = r.corr().values; m = (c.sum() - 4) / 12; return bool(m < a[0])
    if name == "pres": return tomorrow.year % 4 == 3
    if name == "qtr_end":
        i = cal._pos.get(tomorrow)
        if i is None: return None
        return not any(i + k < len(cal.days) and (cal.days[i + k].month - 1) // 3 != (tomorrow.month - 1) // 3 for k in range(1, 6))
    if name == "weekend": return not ((tomorrow - date).days > 1)
    if name == "chand":
        h, l, c = _hlc(adj)
        if c is None or len(c) < 30: return None
        k, n = a; tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
        atr = float(tr.iloc[-n:].mean()); hi = float(c.iloc[-n:].max()); off = mem.get("chand_off", False)
        if not off and float(c.iloc[-1]) < hi - k * atr: off = True
        elif off and float(c.iloc[-1]) >= hi: off = False
        mem["chand_off"] = off; return not off
    if name == "stage2":     # Weinstein: above a rising 150d (30-week) average
        if len(q) < 175: return None
        m = q.rolling(150).mean(); return bool(float(q.iloc[-1]) > float(m.iloc[-1]) > float(m.iloc[-21]))
    if name == "template":   # Minervini trend template on QQQ
        if len(q) < 225: return None
        m50, m150, m200 = (float(q.iloc[-n:].mean()) for n in (50, 150, 200)); m200b = float(q.iloc[-221:-21].mean())
        return bool(float(q.iloc[-1]) > m50 > m150 > m200 > m200b)
    if name == "zweig4":     # Zweig 4% rule on weekly closes
        if len(q) < 10: return None
        on = mem.get("z4", True); lw = mem.get("z4w"); wk = date.isocalendar()[:2]
        if lw is None: mem["z4w"] = wk; mem["z4c"] = float(q.iloc[-1]); return on
        if wk != lw:
            prev = float(q.iloc[-2]); ch = prev / mem["z4c"] - 1
            if ch >= 0.04: on = True
            elif ch <= -0.04: on = False
            mem["z4"] = on; mem["z4w"] = wk; mem["z4c"] = prev
        return on
    if name == "rates_calm":
        x = _col(adj, "TNX")
        if x is None or len(x) < 130: return None
        return bool(float(x.iloc[-1]) - float(x.iloc[-127]) < a[0])
    if name == "djt": return above(_col(adj, "DJT"))
    if name == "ichi":       # Ichimoku: close above the cloud
        h, l, c = _hlc(adj)
        if c is None or len(c) < 80: return None
        mid = lambda n, k=0: (float(h.iloc[-n - k:len(h) - k].max()) + float(l.iloc[-n - k:len(l) - k].min())) / 2
        sa = (mid(9, 26) + mid(26, 26)) / 2; sb = mid(52, 26); return bool(float(c.iloc[-1]) > max(sa, sb))
    if name == "macd":       # weekly MACD above its signal line
        w = q.resample("W-FRI").last().dropna()
        if len(w) < 40: return None
        m = w.ewm(span=12).mean() - w.ewm(span=26).mean(); return bool(float(m.iloc[-1]) > float(m.ewm(span=9).mean().iloc[-1]))
    # ---- round 11 -------------------------------------------------------------------------------------------
    sma = lambda x, n: float(x.iloc[-n:].mean())
    r1 = lambda x, n: float(x.iloc[-1] / x.iloc[-1 - n] - 1) if x is not None and len(x) > n else None
    def ratio_above(t, n=200):
        if t not in adj or "SPY" not in adj: return None
        x = (adj[t] / adj["SPY"]).dropna(); return above(x, n)
    key = repr(spec)
    if name == "vote":
        k, specs = a; vals = [sig(sp, adj, st, date, cal, tomorrow) for sp in specs]; vals = [v for v in vals if v is not None]
        return None if len(vals) < 2 else sum(vals) >= k * len(vals) / len(specs)
    if name == "ath": return bool(float(q.iloc[-1]) >= (1 - a[0]) * float(q.iloc[-252:].max())) if len(q) > 252 else None
    if name == "notdeep": return bool(float(q.iloc[-1]) > (1 - a[0]) * float(q.iloc[-252:].max())) if len(q) > 252 else None
    if name == "notover": return bool(float(q.iloc[-1]) < (1 + a[0]) * sma(q, 200)) if len(q) > 200 else None
    if name == "skew":
        r = q.pct_change().iloc[-60:]; return bool(float(r.skew()) > a[0]) if len(q) > 61 else None
    if name == "sharpe":
        r = q.pct_change().iloc[-252:]; return bool(float(r.mean() / r.std() * 15.87) > a[0]) if len(q) > 253 else None
    if name == "vol_fall":
        r = q.pct_change(); return bool(float(r.iloc[-20:].std()) < float(r.iloc[-60:].std())) if len(q) > 61 else None
    if name == "accel":
        a3, a12 = r1(q, 63), r1(q, 252); return None if a12 is None else bool(a3 > 0 and a3 > a12 / 4)
    if name == "vr":
        if len(q) < 260: return None
        lr = np.log(q.iloc[-253:]).diff().dropna(); r5 = lr.rolling(5).sum().dropna()
        return bool(float(r5.var()) / (5 * float(lr.var())) > 1)
    if name == "ac":
        r = q.pct_change().iloc[-63:]; return bool(float(r.autocorr(1)) > 0) if len(q) > 64 else None
    if name == "dbc_calm":
        x = _col(adj, "DBC"); v = r1(x, 126); return None if v is None else v < a[0]
    if name in ("tlt_calm", "gold_calm", "usd_calm"):
        x = _col(adj, {"tlt_calm": "TLT", "gold_calm": "GLD", "usd_calm": "DXY"}[name]); v = r1(x, 20); return None if v is None else v < a[0]
    if name == "lag": x = ratio_above(a[0]); return None if x is None else not x
    if name == "lead": return ratio_above(a[0])
    if name == "tech_lead": return ratio_above("QQQ")
    if name == "gold_tsy":
        g, t = _col(adj, "GLD"), _col(adj, "TLT"); x, y = r1(g, 63), r1(t, 63); return None if x is None or y is None else x > y
    if name == "copper": return above(_col(adj, "HG"))
    if name == "yld_down": x = above(_col(adj, "TNX")); return None if x is None else not x
    if name == "tlt_down": x = above(_col(adj, "TLT")); return None if x is None else not x
    if name == "vix_low": x = _col(adj, "VIXLVL"); return None if x is None else float(x.iloc[-1]) < a[0]
    if name == "hiking":
        x = _col(adj, "IRXL"); return None if x is None or len(x) < 130 else float(x.iloc[-1]) - float(x.iloc[-127]) < a[0]
    if name == "sb_corr":
        r = adj[["SPY", "TLT"]].dropna().pct_change().iloc[-60:]; return bool(float(r.corr().iloc[0, 1]) < 0) if len(r) >= 60 else None
    if name == "sbc":       # stock/bond correlation over lb days below th
        lb, th = a; r = adj[["SPY", "TLT"]].dropna().pct_change().iloc[-lb:]
        return bool(float(r.corr().iloc[0, 1]) < th) if len(r) >= lb else None
    if name == "breadth":
        cols = [c for c in ("SPY", "QQQ", "IWM", "DIA", "EFA", "EEM", "XLK", "XLU", "XLE", "XLV", "XLF", "VNQ") if c in adj]
        res = [above(adj[c].dropna()) for c in cols]; res = [x for x in res if x is not None]
        return None if len(res) < 5 else sum(res) / len(res) >= a[0]
    if name == "turb":
        R = adj[["SPY", "TLT", "GLD", "QQQ", "IWM"]].iloc[-260:].dropna().pct_change().dropna()
        h_ = mem.setdefault(key, [])
        if len(R) < 200: return None
        x = (R.iloc[-1] - R.iloc[:-1].mean()).values; S = np.cov(R.iloc[:-1].values.T)
        h_.append(float(x @ np.linalg.pinv(S) @ x)); del h_[:-300]
        if len(h_) < 120: return None
        return bool(np.mean(h_[-5:]) <= np.quantile(h_[-252:], a[0]))
    if name == "absorb":
        cols = [c for c in ("SPY", "QQQ", "IWM", "EFA", "EEM", "TLT", "GLD", "XLE", "XLU", "XLF") if c in adj and adj[c].iloc[-61:].notna().all()]
        h_ = mem.setdefault(key, [])
        if len(cols) < 5: return None
        C = adj[cols].iloc[-61:].pct_change().dropna().corr().values; ev = np.sort(np.linalg.eigvalsh(C))[::-1]
        h_.append(float(ev[:2].sum() / ev.sum())); del h_[:-300]
        if len(h_) < 120: return None
        z = (np.mean(h_[-15:]) - np.mean(h_[-252:])) / (np.std(h_[-252:]) + 1e-9); return bool(z < a[0])
    if name in ("ftd", "capit", "recov"):
        m = mem.setdefault(key, {"left": 0}); m["left"] = max(0, m["left"] - 1)
        if len(q) < 253: return None
        hi = float(q.iloc[-252:].max()); dd = float(q.iloc[-1]) / hi - 1; ret = float(q.iloc[-1] / q.iloc[-2] - 1)
        vs = _col(adj, "QQQ_V") if _col(adj, "QQQ_V") is not None and len(_col(adj, "QQQ_V")) > 60 else _col(adj, "NDX_V")
        vol_ok = vs is not None and len(vs) > 60 and vs.index[-1] == q.index[-1] and float(vs.iloc[-60:].min()) > 0
        if name == "ftd":
            th, hold = a
            if dd <= -0.10 and not m.get("corr"): m["corr"] = True; m["tr"] = float(q.iloc[-1]); m["n"] = 0
            if m.get("corr"):
                if float(q.iloc[-1]) < m["tr"]: m["tr"] = float(q.iloc[-1]); m["n"] = 0
                else: m["n"] += 1
                vup = (float(vs.iloc[-1]) > float(vs.iloc[-2])) if vol_ok else True
                if m["n"] >= 4 and ret >= th / 100 and vup: m["left"] = hold; m["corr"] = False
                elif dd > -0.03: m["corr"] = False
        elif name == "capit":
            mult, hold = a
            if not vol_ok: return None
            if ret < -0.015 and float(vs.iloc[-1]) > mult * float(vs.iloc[-51:-1].mean()) and float(q.iloc[-1]) < sma(q, 200): m["left"] = hold
        else:
            if dd <= -0.20 and not m.get("bear"): m["bear"] = True; m["tr"] = float(q.iloc[-1]); m["hi"] = hi
            if m.get("bear"):
                m["tr"] = min(m["tr"], float(q.iloc[-1]))
                if float(q.iloc[-1]) >= m["tr"] + a[0] * (m["hi"] - m["tr"]): m["left"] = 63; m["bear"] = False
        return m["left"] > 0
    if name == "crashbuy":
        if len(q) < 253: return None
        return bool(float(q.iloc[-1]) <= (1 - a[0]) * float(q.iloc[-252:].max()) and float(q.iloc[-1]) > float(q.iloc[-6]))
    if name in ("nr", "dstreak", "nostreak", "pctb", "keltner", "aroon", "adx", "supertrend", "gcross"):
        h, l, c = _hlc(adj)
        if c is None or len(c) < 260 or c.index[-1] != q.index[-1]: return None
        h, l, c = h.iloc[-300:], l.iloc[-300:], c.iloc[-300:]; up200 = float(c.iloc[-1]) > sma(c, 200)
        tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
        if name == "nr": rg = (h - l).iloc[-a[0]:]; return bool(float(rg.iloc[-1]) <= float(rg.min()) and up200)
        if name == "dstreak": return bool((c.diff().iloc[-a[0]:] < 0).all() and up200)
        if name == "nostreak": return not bool((c.diff().iloc[-a[0]:] > 0).all())
        if name == "pctb":
            m20, sd = sma(c, 20), float(c.iloc[-20:].std()); return bool(float(c.iloc[-1]) < m20 - 2 * sd and up200)
        if name == "keltner": return bool(float(c.iloc[-1]) > float(c.ewm(span=20).mean().iloc[-1]) + 2 * float(tr.iloc[-10:].mean()))
        if name == "aroon":
            w = c.iloc[-26:]; up = 100 * (25 - (25 - int(np.argmax(w.values)))) / 25; dn = 100 * (25 - (25 - int(np.argmin(w.values)))) / 25
            return bool(up > 70 and dn < 30)
        if name == "adx":
            upm, dnm = h.diff(), -l.diff(); pdm = upm.where((upm > dnm) & (upm > 0), 0.0); ndm = dnm.where((dnm > upm) & (dnm > 0), 0.0)
            atr = tr.ewm(alpha=1 / 14).mean(); pdi = 100 * pdm.ewm(alpha=1 / 14).mean() / atr; ndi = 100 * ndm.ewm(alpha=1 / 14).mean() / atr
            dx = 100 * (pdi - ndi).abs() / (pdi + ndi); adx = dx.ewm(alpha=1 / 14).mean()
            return bool(float(adx.iloc[-1]) > a[0] and float(pdi.iloc[-1]) > float(ndi.iloc[-1]))
        if name == "gcross":
            m50, m200 = c.rolling(50).mean().iloc[-61:], c.rolling(200).mean().iloc[-61:]
            return bool(float(m50.iloc[-1]) > float(m200.iloc[-1]) and (m50 <= m200).any())
        # supertrend (stateful)
        n_, k_ = a; m = mem.setdefault(key, {}); atr = float(tr.iloc[-n_:].mean()); hl2 = (float(h.iloc[-1]) + float(l.iloc[-1])) / 2
        ub, lb = hl2 + k_ * atr, hl2 - k_ * atr; pc = m.get("pc", float(c.iloc[-2]))
        fub = ub if ("fub" not in m or ub < m["fub"] or pc > m["fub"]) else m["fub"]
        flb = lb if ("flb" not in m or lb > m["flb"] or pc < m["flb"]) else m["flb"]
        d_ = m.get("dir", True); cc = float(c.iloc[-1])
        if d_ and cc < flb: d_ = False
        elif not d_ and cc > fub: d_ = True
        m.update(fub=fub, flb=flb, dir=d_, pc=cc); return d_
    if name == "wrsi":
        w = q.resample("W-FRI").last().dropna().iloc[-120:]
        if len(w) < 30: return None
        d = w.diff(); g = d.clip(lower=0).ewm(alpha=1 / 14).mean(); ls = (-d.clip(upper=0)).ewm(alpha=1 / 14).mean()
        return bool(100 - 100 / (1 + float(g.iloc[-1]) / max(float(ls.iloc[-1]), 1e-12)) < a[0])
    if name == "coppock":
        mth = q.resample("ME").last().dropna().iloc[:-1]
        if len(mth) < 30: return None
        rc = (mth / mth.shift(14) - 1) + (mth / mth.shift(11) - 1); wts = np.arange(1, 11)
        cp = rc.rolling(10).apply(lambda x: float(np.dot(x, wts) / wts.sum()), raw=True)
        return bool(float(cp.iloc[-2]) < 0 and float(cp.iloc[-1]) > float(cp.iloc[-2]))
    if name == "earn": return (tomorrow.month % 3 == 1 and tomorrow.day >= 10) or (tomorrow.month % 3 == 2 and tomorrow.day <= 7)
    if name == "earnw":   # first month of the quarter from day d0 through day d1 of the second month
        d0, d1 = a; return (tomorrow.month % 3 == 1 and tomorrow.day >= d0) or (tomorrow.month % 3 == 2 and tomorrow.day <= d1)
    if name == "midq4": return tomorrow.year % 4 == 2 and tomorrow.month >= 10
    if name == "sept": return tomorrow.month != 9
    raise ValueError(name)

def uptrend_pre(q): return float(q.iloc[-1]) > float(q.iloc[-200:].mean())

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
        if p("mom_skip1") and len(s) > 253: bm = float(s.iloc[-22] / s.iloc[-253] - 1)
        diag[a] = dict(price=float(s.iloc[-1]), sma=sma, trend="UP" if up else "DOWN", vol63=v, mom_blend=float(bm))
        m12 = _mom(s, 12)
        if p("core_trend") == "or_mom": up = up or (m12 == m12 and m12 > 0)
        elif p("core_trend") in ("donchian", "breakout", "kaufman"):
            tp = p("trend_params") or ()
            if p("core_trend") == "donchian":
                n_ = tp[0]; up = float(s.iloc[-1]) > (float(s.iloc[-n_:].max()) + float(s.iloc[-n_:].min())) / 2
            elif p("core_trend") == "breakout":
                ein, eout = tp; was = LDS_MEM.get(a, float(s.iloc[-1]) >= sma)
                if not was and float(s.iloc[-1]) >= float(s.iloc[-ein:].max()): was = True
                elif was and float(s.iloc[-1]) <= float(s.iloc[-eout:].min()): was = False
                LDS_MEM[a] = was; up = was
            else:
                n_, th = tp; ch = abs(float(s.iloc[-1] - s.iloc[-n_])); path = float(s.diff().abs().iloc[-n_:].sum())
                up = up and float(s.iloc[-30:].mean()) > sma and (ch / path if path else 0) > th
        elif p("core_trend") == "ens":
            fr = float(np.mean([float(s.iloc[-1]) > float(s.iloc[-sl:].mean()) and float(s.iloc[-fa:].mean()) > float(s.iloc[-sl:].mean())
                                for sl in (150, 210, 270) for fa in (20, 30, 40)]))
            up = fr > 0 if p("trend_params") == "frac" else fr >= 0.5; ENSF[a] = fr
        elif p("core_trend") == "dual":
            f_ = float(s.iloc[-p("dual_fast"):].ewm(span=p("dual_fast")).mean().iloc[-1]) if p("dual_ema") else float(s.iloc[-p("dual_fast"):].mean())
            if p("dual_band"):
                was = LDS_MEM.get(a, False); b_ = p("dual_band")
                up = (float(s.iloc[-1]) >= sma * (1 + (0 if was else b_)) and f_ > sma * (1 + (-b_ if was else b_)))
                LDS_MEM[a] = up
            else: up = up and f_ > sma
            if p("tri_fast"): up = up and float(s.iloc[-p("tri_fast"):].mean()) > f_
            diag[a]["fast_ratio"] = f_ / sma - 1
        if p("tlt_carry") and a == "TLT" and "TNX" in adj and "IRXL" in adj:
            tn, ir = adj["TNX"].iloc[-1], adj["IRXL"].iloc[-1]
            if tn == tn and ir == ir and float(tn) - float(ir) <= 0: up = False
        if p("lds_corr_cut") and a == "TLT" and "SPY" in px:
            c = float(np.corrcoef(r["SPY"].iloc[-63:], r["TLT"].iloc[-63:])[0, 1])
            if c > 0: up = False
        elif p("core_trend") == "and_mom": up = up and (m12 == m12 and m12 > 0)
        if up: core[a] = 1.0 if p("core_ew") else (max(bm, 0.0) + 1e-4) / v if p("core_mom_weight") else 1 / v
        if up and p("core_strength") and "fast_ratio" in diag[a]: core[a] *= min(1.0, max(diag[a]["fast_ratio"], 0) / p("core_strength"))
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
    if p("core_trend") == "ens" and p("trend_params") == "frac": core = {a: e * ENSF.get(a, 1.0) for a, e in core.items()}
    ov = {}
    vix_hi = bool(p("overlay_vix")) and "VIXLVL" in adj and float(adj["VIXLVL"].iloc[-1]) > p("overlay_vix")
    for a in A:
        if vix_hi: break
        bm = diag[a]["mom_blend"]
        if np.isnan(bm): continue
        if bm <= 0 and (p("overlay_long_only") or not any(L < 0 for L in LEVS[a])): continue
        if p("overlay_bear") and "SPY" in px and len(px["SPY"]) > 505 and float(px["SPY"].iloc[-1] / px["SPY"].iloc[-505] - 1) < 0: continue
        sgn = (1 if bm > 0 else -1)
        if p("overlay_dual"): sgn = 1 if diag[a]["trend"] == "UP" else -1
        ov[a] = sgn / diag[a]["vol63"]
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
            if p("lds_idle") and sum(caps.values()) < 1 - 1e-6: caps[p("lds_idle")] = caps.get(p("lds_idle"), 0) + 1 - sum(caps.values())
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

SIG_HOOKS = ("lds_sig", "swap_sig", "dip_sig", "tom_sig", "vt_sig", "res_sig", "qsell_sig", "swap_asset_sig")
def _hook_spec(k):
    v = p(k)
    if not v: return None
    return v if k in ("swap_sig", "dip_sig", "tom_sig", "qsell_sig") else v[0]

def step(st, date, adj, close, cal, divs=None, splits=None):
    nine, lds = st["nine"], st["lds"]
    ev = []
    tm_ = cal.next_day(date)
    for k_ in SIG_HOOKS:                      # evaluate every hooked signal daily so stateful ones keep their history
        if _hook_spec(k_): sig(_hook_spec(k_), adj, st, date, cal, tm_)
    hk = lambda k_: sig(_hook_spec(k_), adj, st, date, cal, tm_) if _hook_spec(k_) else None
    growth = [nine.get("gasset") or p("growth")[0]] if p("growth_rot") else list(p("growth")); deff = list(P["defensive"])
    prev = st["prev_close"]
    if p("cash_yield") and prev:
        for sl in st["sleeves"].values():
            if sl["cash"] > 0: sl["cash"] *= 1 + close["RF"]
    if nine["initialized"] and prev:
        rq = np.mean([close[t] / prev[t] - 1 for t in growth])
        dh = nine.get("def_hold") or deff
        dw = nine.get("def_w") or {t: dh.count(t) / len(dh) for t in set(dh)}
        rd = sum(dw.get(t, 0) * (close[t] / prev[t] - 1) for t in set(dh))
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
        q_ = adj["QQQ"].dropna(); rate = P["sig_rate"]
        if p("sig_rate_trend"): rate = p("sig_rate_trend")[0] if float(q_.iloc[-1]) > float(q_.iloc[-200:].mean()) else p("sig_rate_trend")[1]
        target = nine["last_target"] * (1 + rate) + 0.5 * nine["new_cash"]
        diff = target - nine["S"]
        q_ = adj["QQQ"].dropna(); qd_ = float(q_.iloc[-30:].mean()) > float(q_.iloc[-210:].mean())
        if diff > 0 and p("q_gate") == "skip_buys" and not qd_: diff = 0.0
        if diff > 0 and p("q_gate") == "half_buys" and not qd_: diff *= 0.5
        if diff < 0 and p("q_sell_skip_dual") and qd_: diff = 0.0
        if diff < 0 and hk("qsell_sig") is True: diff = 0.0
        if diff < 0 and nine["skips"] > 0: nine["skips"] -= 1
        elif diff < 0 and p("nine_buy_only"): pass
        elif diff < 0: nine["S"] += diff; nine["B"] -= diff
        else: buy = min(diff, nine["B"]); nine["S"] += buy; nine["B"] -= buy
        nine["last_target"] = nine["S"]; nine["new_cash"] = 0.0; nine_trade = True
    if nine["initialized"] and not q_end and cal.is_month_end(date) and (p("nine_tp") or p("nine_bd")):
        tgt_q = nine["last_target"] * (1 + P["sig_rate"])
        if p("nine_tp") and nine["S"] > tgt_q * (1 + p("nine_tp")):
            x = nine["S"] - tgt_q; nine["S"] -= x; nine["B"] += x; nine_trade = True
        elif p("nine_bd") and nine["S"] < tgt_q * (1 - p("nine_bd")):
            x = min(tgt_q - nine["S"], nine["B"]); nine["S"] += x; nine["B"] -= x; nine_trade = True
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
    if p("split_sig") and st["last_date"]:
        spec, on_, off_ = p("split_sig"); ok = sig(spec, adj, st, date, cal, cal.next_day(date))
        want = P["split_9sig"] if ok is None else (on_ if ok else off_)
        if rebal: split = want
        elif cal.is_month_end(date):
            sh = sleeve_value(st, "9SIG", close) / total_value(st, close)
            if abs(sh - want) > 0.05: rebal = True; split = want
    if p("split_dyn") and st["last_date"] and len(st["equity"]) > 260:
        kd = p("split_dyn"); E = pd.DataFrame(st["equity"][-260:])[["nine", "lds"]]
        if kd[0] == "rp":
            lb, lo, hi = kd[1:]; v = E.pct_change().iloc[-lb:].std(); want = float(min(hi, max(lo, v["lds"] / (v["nine"] + v["lds"]))))
        elif kd[0] == "mom":
            lb, t_ = kd[1:]; rr = E.iloc[-1] / E.iloc[-1 - lb] - 1; want = P["split_9sig"] + (t_ if rr["nine"] > rr["lds"] else -t_)
        else:
            want = kd[1] if nine["w_base"] < 0.5 else P["split_9sig"]
        if rebal: split = want
        elif cal.is_month_end(date):
            sh = sleeve_value(st, "9SIG", close) / total_value(st, close)
            if abs(sh - want) > 0.05: rebal = True; split = want
    if p("regime_split") and st["last_date"]:
        q_ = adj["QQQ"].dropna(); want = p("regime_split")[0] if float(q_.iloc[-1]) > float(q_.iloc[-200:].mean()) else p("regime_split")[1]
        if rebal: split = want
        elif cal.is_month_end(date):
            sh = sleeve_value(st, "9SIG", close) / total_value(st, close)
            if abs(sh - want) > 0.05: rebal = True; split = want
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
    if p("vt_sig"):
        P.setdefault("_vt0", P["vol_target"]); ok_ = hk("vt_sig")
        P["vol_target"] = P["_vt0"] if ok_ is None else (p("vt_sig")[1] if ok_ else p("vt_sig")[2])
    raw, v20 = vol_switch(vt, adj, date)
    if p("cppi") and v20 == v20 and v20 > 0:
        eqv = [e["value"] for e in st["equity"][-750:]]
        dd_ = (eqv[-1] / max(eqv) - 1) if eqv else 0.0
        tgt_e = P["vol_target"] * max(0.5, 1 + p("cppi") * dd_); raw = float(min(max((tgt_e / v20) ** P["vol_power"], 0.0), 1.0))
    cut_b, add_b = p("vol_hyst") or (P["vol_band"], P["vol_band"])
    if (raw < nine["w_base"] - cut_b) or (raw > nine["w_base"] + add_b) or not nine["initialized"]: nine["w_base"] = raw
    base = nine["w_base"] if p("vol_floor") is None else max(nine["w_base"], p("vol_floor"))
    qqq = adj["QQQ"].dropna()
    if p("growth_trend_cap") is not None and float(qqq.iloc[-1]) < float(qqq.iloc[-200:].mean()): base = min(base, p("growth_trend_cap"))
    qdual = float(qqq.iloc[-30:].mean()) > float(qqq.iloc[-210:].mean()) and float(qqq.iloc[-1]) > float(qqq.iloc[-210:].mean())
    if p("nine_dual_cap") is not None and not qdual: base = min(base, p("nine_dual_cap"))
    if p("dd_boost"):
        eqv = [e["value"] for e in st["equity"][-750:]]
        if eqv and eqv[-1] / max(eqv) - 1 < -p("dd_boost")[0] and v20 == v20 and v20 > 0:
            base = max(base, float(min(1.0, (p("dd_boost")[1] / v20) ** P["vol_power"])))
    tomorrow = cal.next_day(date); tom = cal.is_tom(tomorrow)
    bull = _bullish(st, cal, date, tomorrow, adj)
    uptrend = float(qqq.iloc[-1]) > float(qqq.iloc[-200:].mean())
    if p("tom_trend") and not uptrend: tom = False
    if hk("tom_sig") is False: tom = False
    full = tom or (p("swap_9sig") and bull)
    if p("santa"):
        i_ = cal._pos.get(tomorrow)
        d0, nj = (p("santa") if isinstance(p("santa"), tuple) else (22, 2))
        if i_ is not None and ((tomorrow.month == 12 and tomorrow.day >= d0) or (tomorrow.month == 1 and sum(1 for k in range(1, 6) if i_ - k >= 0 and cal.days[i_ - k].month == 1) < nj)): full = True
    if p("nfp") and tomorrow.weekday() == 4 and tomorrow.day <= 7: full = True
    if p("wk_dip"):
        thr, n_ = p("wk_dip"); left = nine.get("wk_left", 0)
        if len(qqq) > 6 and float(qqq.iloc[-1] / qqq.iloc[-6] - 1) < -thr and uptrend_pre(qqq): left = n_
        else: left = max(0, left - 1)
        nine["wk_left"] = left; full = full or left > 0
    roff = riskoff(st, adj, cal, date)
    if p("nine_dip") is not None:
        r2 = rsi2(qqq); on = nine.get("dip_on", False)
        if p("nine_dip_exit") is None: on = dip_signal(adj, p("dip_kind"), p("nine_dip"))
        elif not on and uptrend and r2 < p("nine_dip"): on = True
        elif on and r2 > p("nine_dip_exit"): on = False
        if hk("dip_sig") is False: on = False
        nine["dip_on"] = on; full = full or on
    if p("boost_sig") and sig(p("boost_sig"), adj, st, date, cal, tomorrow) is True: full = True
    if p("chand") and sig(("chand",) + tuple(p("chand")), adj, st, date, cal, tomorrow) is False: base = 0.0; full = False
    w_new = 1.0 if full else base
    if roff: w_new = min(base, p("nine_cap")[1])
    if p("cap_sig") and sig(p("cap_sig")[0], adj, st, date, cal, tomorrow) is False: w_new = min(w_new, p("cap_sig")[1])
    def_new = deff
    if p("def_trend"):
        def_new = [t for t in deff if float(adj[t].iloc[-1]) >= float(adj[t].iloc[-p("def_sma"):].mean())] or ["BIL"]
        if len(def_new) < len(deff) and "BIL" not in def_new: def_new = def_new + ["BIL"] * (len(deff) - len(def_new))
    if p("def_dual"):
        def_new = [t if (float(adj[t].iloc[-1]) > _sma(adj[t].dropna(), 210) and _sma(adj[t].dropna(), 30) > _sma(adj[t].dropna(), 210)) else "BIL" for t in deff]
    if p("def_relmom"):
        sc = {t: _mom(adj[t].dropna(), p("def_relmom")) for t in deff}; def_new = [max(sc, key=sc.get)]
    if p("def_lev_trend"):
        lev = {"TLT": "TMF", "GLD": "UGL", "IEF": "TYD"}
        def_new = [lev.get(t, t) if float(adj[t].iloc[-1]) >= _sma(adj[t].dropna(), 200) else "BIL" for t in deff]
    if p("def_invvol") and len(set(def_new)) > 1:
        iv = {t: 1 / max(float(adj[t].pct_change().iloc[-63:].std()), 1e-6) for t in set(def_new)}; tot_ = sum(iv.values())
        new_w = {t: round(v / tot_, 2) for t, v in iv.items()}
        if new_w != nine.get("def_w") and (cal.is_month_end(date) or not nine.get("def_w")): nine["def_w"] = new_w; nine_trade = True
    if p("res_sig") and hk("res_sig") is False: def_new = list(p("res_sig")[1])
    if p("res_swap") and bull:
        ra, rf_ = p("res_swap"); def_new = [ra] if rf_ >= 1 else list(def_new) + [ra] * len(def_new)
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
        dw = nine.get("def_w") if p("def_invvol") and nine.get("def_w") else {t: def_new.count(t) / len(def_new) for t in set(def_new)}
        for t, wt in dw.items(): tg[t] += dfn * wt
        set_targets(st, "9SIG", dict(tg), close, date, "9Sig rebalance")
        nine["initialized"] = True
    # --- LDS: bullish-session swap (Fed day and optional calendar/dip days)
    ex, diag = lds_exposures(adj)
    loff = (p("lds_riskoff") and roff) or hk("lds_sig") is False
    lcash = loff and p("lds_sig") and p("lds_sig")[1] == "cash"
    kmax = 1 if loff else 3
    def caps_for(ex_, k_): return {"BIL": 1.0} if lcash else implement(ex_, k_)
    def lds_targets(caps, vl):
        tg = {t: c * vl for t, c in caps.items()}
        if p("ndx_cap") is not None and tg.get("TQQQ", 0) > 0:
            room = max(0.0, p("ndx_cap") * total_value(st, close) - st["sleeves"]["9SIG"]["holdings"].get("TQQQ", 0) * close["TQQQ"])
            if tg["TQQQ"] > room: tg["UPRO"] = tg.get("UPRO", 0) + tg["TQQQ"] - room; tg["TQQQ"] = room
        return tg
    if (p("lds_riskoff") or p("lds_sig")) and not (lds.get("swap") or {}).get("active") and st["last_date"] and bool(lds.get("delev")) != (kmax == 1):
        vl = sleeve_value(st, "LDS", close)
        set_targets(st, "LDS", lds_targets(caps_for(ex, kmax), vl), close, date, "LDS risk-off" if kmax == 1 else "LDS risk back on")
        lds["delev"] = kmax == 1
    sw = lds.get("swap") or {}
    swapped_back = False
    if sw.get("active") and not bull:
        caps = caps_for(ex, kmax); vl = sleeve_value(st, "LDS", close)
        set_targets(st, "LDS", lds_targets(caps, vl), close, date, "Swap ends: LDS positions restored")
        lds["exposures"] = ex; lds["swap"] = dict(active=False); swapped_back = True
    exit_due = False
    if p("lds_exit_check") and not lds_force and (p("lds_exit_check") == "day" or cal.is_week_end(date)):
        held_core = {a for a, e in (lds.get("exposures") or {}).items() if e > 0}
        exit_due = any(diag.get(a, {}).get("trend") == "DOWN" for a in held_core)
    if p("lds_crash") and len(adj["SPY"].dropna()) > 6 and float(adj["SPY"].iloc[-1] / adj["SPY"].iloc[-6] - 1) < -p("lds_crash") and not sw.get("active") and not lds.get("crash_out"):
        vl = sleeve_value(st, "LDS", close); set_targets(st, "LDS", {"BIL": vl}, close, date, "LDS crash cut"); lds["crash_out"] = True
    if lds.get("crash_out") and lds_review_due(cal, date): lds["crash_out"] = False
    if (lds_review_due(cal, date) or lds_force or exit_due) and not swapped_back and not sw.get("active") and not lds.get("crash_out"):
        caps = caps_for(ex, kmax); vl = sleeve_value(st, "LDS", close)
        tg = lds_targets(caps, vl)
        cur = {t: sh * close[t] for t, sh in st["sleeves"]["LDS"]["holdings"].items()}
        turn = sum(abs(tg.get(t, 0) - cur.get(t, 0)) for t in set(tg) | set(cur))
        if turn > P["lds_threshold"] * vl or lds_force:
            set_targets(st, "LDS", tg, close, date, "LDS rebalance"); lds["exposures"] = ex
    if bull and not (lds.get("swap") or {}).get("active") and not (p("lds_riskoff") and roff):
        vl = sleeve_value(st, "LDS", close)
        f = p("swap_frac"); tg = defaultdict(float)
        sa_ = p("swap_asset")
        if p("swap_asset_sig"): sa_ = p("swap_asset_sig")[1] if hk("swap_asset_sig") is not False else p("swap_asset_sig")[2]
        for t, w in sa_: tg[t] += w * vl * f
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
        q = adj["QQQ"].dropna(); s_ = adj["SPY"].dropna()
        if p("swap_fomc_dual") and not (float(s_.iloc[-30:].mean()) > float(s_.iloc[-210:].mean())): return False
        if p("swap_sig") and sig(p("swap_sig"), adj, st, date, cal, tomorrow) is False: return False
        if not p("swap_fomc_trend") or float(q.iloc[-1]) > float(q.iloc[-200:].mean()): return True
    if p("swap_tom") and cal.is_tom(tomorrow): return True
    if p("swap_preholiday") and cal.is_pre_holiday(tomorrow): return True
    return dip
