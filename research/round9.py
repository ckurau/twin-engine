"""Round 9 (vs v1.7): ~100 ideas, each scored on 2000-26, 2010-26 AND 1988-99 (data never used in development).
Pass (fixed in advance): "return" = CAGR >= +0.5 pt in 2000-26 and 2010-26, >= -0.5 pt in 1988-99, max DD no more than 3 pts worse in any;
"risk" = Martin ratio better in all three periods with CAGR not lower in any. Ideas whose assets lack pre-2000 data skip 1988-99 (n/a)."""
import os, sys, time, pickle, multiprocessing as mp
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); OUT = os.path.join(HERE, "out")
from round4 import V15
from round6 import metrics
V17 = {**V15, "lds_assets": ("SPY", "TLT", "GLD"), "core_trend": "dual", "dual_fast": 30}
BA = ("SPY", "TLT", "GLD")
I = []
def add(g, n, long=True, **ov): I.append((g, n, ov, long))
# LDS trend refinements (on top of dual trend)
add("LDS trend", "Fast average is exponential (EMA) not simple", dual_ema=True)
add("LDS trend", "Also 10d > 30d (triple trend)", tri_fast=10); add("LDS trend", "Also 5d > 30d (triple trend)", tri_fast=5)
for b in (0.005, 0.01, 0.02): add("LDS trend", f"Trend hysteresis band {b:.1%}", dual_band=b)
add("LDS trend", "Overlay follows the dual trend instead of momentum", overlay_dual=True)
add("LDS trend", "Overlay momentum 12-1 months", mom_skip1=True)
for x in (0.02, 0.05): add("LDS trend", f"Core size scales with trend strength (full at {x:.0%})", core_strength=x)
for f in (20, 40): add("LDS trend", f"Dual trend with {f}-day fast average", dual_fast=f)
for s_ in (150, 180, 200, 240, 270): add("LDS trend", f"Slow average {s_}d (fast 30d)", sma_days=s_)
add("LDS timing", "Exit check every Friday (entries monthly)", lds_exit_check="week"); add("LDS timing", "Exit check every day (entries monthly)", lds_exit_check="day")
for f_ in ("week", "2week", "midmonth"): add("LDS timing", f"LDS review {f_}", lds_freq=f_)
for c in (0.05, 0.07, 0.10): add("LDS timing", f"LDS to T-bills after a {c:.0%} S&P week (until next review)", lds_crash=c)
add("LDS assets", "Add QQQ back (with dual trend)", lds_assets=BA + ("QQQ",)); add("LDS assets", "Add small caps (IWM)", lds_assets=BA + ("IWM",))
add("LDS assets", "Add 7-10yr Treasuries (IEF)", long=False, lds_assets=BA + ("IEF",)); add("LDS assets", "Add emerging markets (EEM)", long=False, lds_assets=BA + ("EEM",))
add("LDS assets", "Add utilities (XLU)", long=False, lds_assets=BA + ("XLU",))
for v_ in (0.8, 1.2): add("LDS sizing", f"Core vol target {v_:.0%}", lds_vol_target=v_)
add("LDS sizing", "Core 100% / no overlay", lds_core=1.0, lds_overlay=0.0); add("LDS sizing", "Core 70 / overlay 30", lds_core=0.7, lds_overlay=0.3)
for th in (0.025, 0.10): add("LDS sizing", f"Trade threshold {th:.1%}", lds_threshold=th)
add("LDS sizing", "Overlay vol 10%", lds_overlay_vol=0.10); add("LDS sizing", "Overlay long-only", overlay_long_only=True)
add("LDS sizing", "Momentum 3/6/12", mom_months=(3, 6, 12)); add("LDS sizing", "Core equal risk contribution", core_erc=True)
add("LDS sizing", "Core top 2 by momentum", core_topk=2); add("LDS sizing", "Idle LDS cash into SPY", lds_idle="SPY"); add("LDS sizing", "Always 3x + T-bills", lds_max_lev=True)
add("LDS sizing", "Drop Treasuries when correlated with stocks", lds_corr_cut=True)
# 9Sig
for c in (0.0, 0.5, 0.75): add("9Sig", f"TQQQ max {c:.0%} when QQQ dual trend is down", nine_dual_cap=c)
add("9Sig", "Reserve TLT/GLD only in dual uptrend, else T-bills", def_dual=True)
add("9Sig", "Quarterly buys skipped when QQQ dual trend is down", q_gate="skip_buys"); add("9Sig", "Quarterly buys halved when QQQ dual trend is down", q_gate="half_buys")
add("9Sig", "Quarterly sells skipped when QQQ dual trend is up", q_sell_skip_dual=True)
for d_, t_ in ((0.25, 0.9), (0.30, 1.0)): add("9Sig", f"After a {d_:.0%} account drawdown, vol target {t_:.0%}", dd_boost=(d_, t_))
for v_ in (0.75, 0.85, 0.90): add("9Sig", f"Vol target {v_:.0%}", vol_target=v_)
add("9Sig", "Vol power 15", vol_power=15.0)
for lb in (15, 30): add("9Sig", f"Vol lookback {lb}d", vol_lookback=lb)
for d_ in (15, 25): add("9Sig", f"Dip boost RSI2 < {d_}", nine_dip=d_)
add("9Sig", "Dip boost RSI2 or IBS", dip_kind="rsi2ibs"); add("9Sig", "Dip boost held until RSI2 > 50", nine_dip_exit=50)
for t_ in (2, 4): add("9Sig", f"TOM: first {t_} days", tom_after=t_)
for r_ in (0.08, 0.10): add("9Sig", f"Quarterly growth {r_:.0%}", sig_rate=r_)
add("9Sig", "Reserve TLT + GLD + T-bills", defensive=("TLT", "GLD", "BIL")); add("9Sig", "Reserve gold only", defensive=("GLD",))
add("9Sig", "Reserve by inverse volatility", def_invvol=True); add("9Sig", "Reserve trend filter (200d)", def_trend=True)
add("9Sig", "Reserve leveraged when trending", def_lev_trend=True)
add("9Sig", "Mid-quarter take-profit 30%", nine_tp=0.3); add("9Sig", "Mid-quarter buy 30%", nine_bd=0.3)
add("9Sig", "Switch hysteresis 2% / 10%", vol_hyst=(0.02, 0.10)); add("9Sig", "CPPI x0.5", cppi=0.5)
add("9Sig", "Weekly reversal 5%, 5 days", wk_dip=(0.05, 5)); add("9Sig", "TQQQ max 50% below 200d", growth_trend_cap=0.5)
add("9Sig", "Growth TQQQ 75 / UPRO 25 (switch on TQQQ)", growth=("TQQQ", "TQQQ", "TQQQ", "UPRO"))
add("9Sig", "Santa Claus rally", santa=True); add("9Sig", "Fear premium 1.5x", vrp=(1.5, 1.0))
# swaps / split / other
add("Swap", "Fed swap only when S&P dual trend is up", swap_fomc_dual=True); add("Swap", "Fed swap into TQQQ", swap_asset=(("TQQQ", 1.0),))
add("Swap", "Fed swap into TQQQ + SOXL", swap_asset=(("TQQQ", 0.5), ("SOXL", 0.5))); add("Swap", "Fed swap 2 days", fomc_pre=2); add("Swap", "Fed swap 50% of LDS", swap_frac=0.5)
for sp in (0.45, 0.55, 0.60): add("Split", f"{sp:.0%} / {1-sp:.0%}", split_9sig=sp)
add("Split", "Reset twice a year", rebalance_months=(6, 12)); add("Split", "Regime split 60/40 up, 40/60 down", regime_split=(0.6, 0.4))
add("Other", "Idle cash earns T-bills", cash_yield=True)
add("Combo", "Reserve dual + TQQQ max 50% in QQQ dual downtrend", def_dual=True, nine_dual_cap=0.5)
add("Combo", "Weekly exit check + 1% hysteresis", lds_exit_check="week", dual_band=0.01)
add("Combo", "Overlay dual + weekly exit check", overlay_dual=True, lds_exit_check="week")
add("Combo", "Triple trend 10d + weekly exit check", tri_fast=10, lds_exit_check="week")

LONG = None
def work(a):
    import bt
    global LONG
    key, ov, kw, use_long = a
    if use_long:
        if LONG is None: LONG = pd.read_pickle(os.path.join(HERE, "data", "panel_long.pkl"))
        s = bt.run(ov, panel=LONG, **kw)
    else: s = bt.run(ov, **kw)
    return key, s["equity"]

SC = {"00": (dict(start="2000-01-03"), False), "10": (dict(start="2010-03-12"), False), "88": (dict(start="1988-01-04", end="1999-12-31"), True)}
if __name__ == "__main__":
    jobs = []
    for sk, (kw, lg) in SC.items():
        jobs.append((("BASELINE", sk), V17, kw, lg))
        for g, n, ov, long_ok in I:
            if sk == "88" and not long_ok: continue
            jobs.append(((n, sk), {**V17, **ov}, kw, lg))
    print(len(I), "ideas,", len(jobs), "runs", flush=True); res = {}; t = time.time()
    with mp.Pool(15) as pool:
        for i, (k, eq) in enumerate(pool.imap_unordered(work, jobs), 1):
            res[k] = eq
            if i % 25 == 0: print(f"[{i}/{len(jobs)} {time.time()-t:4.0f}s]", flush=True)
    pickle.dump(res, open(os.path.join(OUT, "round9.pkl"), "wb"))
    B = {sk: metrics(res[("BASELINE", sk)]) for sk in SC}
    rows = []
    for g, n, ov, long_ok in [("Base", "BASELINE", {}, True)] + I:
        m = {sk: metrics(res[(n, sk)]) if (n, sk) in res else None for sk in SC}
        d = {sk: (m[sk]["cagr"] - B[sk]["cagr"]) if m[sk] else None for sk in SC}
        dd = {sk: (m[sk]["maxdd"] - B[sk]["maxdd"]) if m[sk] else None for sk in SC}
        ret = d["00"] >= 0.005 and d["10"] >= 0.005 and (d["88"] is None or d["88"] >= -0.005) and all(x is None or x >= -0.03 for x in dd.values())
        risk = all(m[sk] is None or (m[sk]["martin"] > B[sk]["martin"] and d[sk] >= -1e-4) for sk in SC)
        rows.append(dict(group=g, idea=n, cagr00=m["00"]["cagr"], dd00=m["00"]["maxdd"], d00=d["00"], cagr10=m["10"]["cagr"], dd10=m["10"]["maxdd"], d10=d["10"],
                         cagr88=m["88"]["cagr"] if m["88"] else np.nan, dd88=m["88"]["maxdd"] if m["88"] else np.nan, d88=d["88"] if d["88"] is not None else np.nan,
                         martin00=m["00"]["martin"], verdict=("PASS return " if ret else "") + ("PASS risk" if risk else "") if n != "BASELINE" else ""))
    df = pd.DataFrame(rows); df.to_csv(os.path.join(OUT, "round9.csv"), index=False)
    show = df.copy()
    for c in ["cagr00", "dd00", "d00", "cagr10", "dd10", "d10", "cagr88", "dd88", "d88"]: show[c] = (show[c] * 100).round(1)
    show["martin00"] = show["martin00"].round(2)
    pd.set_option("display.width", 300); pd.set_option("display.max_rows", 200)
    print(show.sort_values("d00", ascending=False).to_string(index=False))
