"""Round 10 (vs v1.7): ~100 ideas from famous traders / quant research, same pass rules as round 9
(2000-26, 2010-26 and out-of-sample 1988-99). Signals: research/te_lab.py sig()."""
import os, sys, time, pickle, multiprocessing as mp
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); OUT = os.path.join(HERE, "out")
from round9 import V17, SC
from round6 import metrics
I = []
def add(g, n, long=True, **ov): I.append((g, n, ov, long))
def three(g, label, spec, long=True, cap=0.5, split=(0.6, 0.4)):
    add(g, f"{label}: TQQQ max {cap:.0%} when off", long, cap_sig=(spec, cap))
    add(g, f"{label}: full TQQQ when on", long, boost_sig=spec)
    add(g, f"{label}: split {split[0]:.0%}/{split[1]:.0%} by signal", long, split_sig=(spec, *split))
# Fed cycle (Cieslak, Morse & Vissing-Jorgensen: stock returns earned in even weeks of the FOMC cycle)
three("Fed cycle", "FOMC even weeks", ("fomc_even",), split=(0.6, 0.5)); add("Fed cycle", "FOMC even weeks: TQQQ max 75% in odd weeks", cap_sig=(("fomc_even",), 0.75))
# Zweig "don't fight the Fed"
for b in (0.0, 0.5): three("Zweig", f"Fed easing (3m bill down >{b} pt in 6m)", ("easing", b), split=(0.6, 0.5))
# O'Neil / IBD distribution days
for n in (5, 6, 7): add("O'Neil", f"Distribution days >= {n} in 25: TQQQ max 50%", cap_sig=(("dist", n), 0.5))
add("O'Neil", "Distribution days >= 6: TQQQ max 0%", cap_sig=(("dist", 6), 0.0)); add("O'Neil", "Distribution days >= 6: split 50/40", split_sig=(("dist", 6), 0.5, 0.4))
add("O'Neil", "Distribution days < 2: full TQQQ", boost_sig=("dist", 2))
# Minervini VCP, Raschke Holy Grail, Larry Williams %R
for k in (0.5, 0.6, 0.7): add("Minervini", f"Volatility contraction near highs (10d vol < {k}x 60d): full TQQQ", boost_sig=("vcp", k))
for t in (0.0, 0.005, 0.01): add("Raschke", f"Holy Grail pullback to 20 EMA (+{t:.1%}): full TQQQ", boost_sig=("holy", t))
for w in (-80, -90, -95): add("L. Williams", f"%R(10) < {w} in uptrend: full TQQQ", boost_sig=("willr", w))
# Dow Theory
three("Dow Theory", "Dow Industrials + Transports above 200d", ("dow",)); add("Dow Theory", "Dow Theory: TQQQ max 0% when off", cap_sig=(("dow",), 0.0)); add("Dow Theory", "Dow Theory: TQQQ max 75% when off", cap_sig=(("dow",), 0.75))
# Intermarket (Murphy / Gundlach)
three("Intermarket", "Copper/gold ratio above 200d", ("cu_au",), long=False)
three("Intermarket", "Dollar below 200d", ("usd_down",)); add("Intermarket", "Dollar below 200d: TQQQ max 0% when off", cap_sig=(("usd_down",), 0.0))
three("Intermarket", "Small caps leading (IWM/SPY > 200d)", ("small_lead",)); add("Intermarket", "Small caps leading: TQQQ max 75% when off", cap_sig=(("small_lead",), 0.75))
three("Intermarket", "Semis leading (SOXX/QQQ > 200d)", ("semi_lead",)); add("Intermarket", "Semis leading: TQQQ max 75% when off", cap_sig=(("semi_lead",), 0.75))
# Correlation spike (risk-off regime when everything moves together)
for c in (0.6, 0.7, 0.8): add("Correlation", f"Avg 20d stock correlation > {c}: TQQQ max 50%", cap_sig=(("corr", c), 0.5))
add("Correlation", "Avg correlation > 0.7: split 60/40", split_sig=(("corr", 0.7), 0.6, 0.4))
# Calendar / flows not tested before
add("Calendar", "Presidential pre-election year: full TQQQ", boost_sig=("pres",)); add("Calendar", "Pre-election year: split 60/50", split_sig=(("pres",), 0.6, 0.5))
add("Calendar", "Quarter-end rebalancing week: TQQQ max 50%", cap_sig=(("qtr_end",), 0.5)); add("Calendar", "Weekend risk: TQQQ max 50% over weekends", cap_sig=(("weekend",), 0.5))
# Chandelier exit (Chuck LeBeau) on 9Sig's TQQQ
for k, n in ((2.5, 22), (3, 22), (4, 22), (5, 22), (3, 10), (3, 50)): add("LeBeau", f"Chandelier exit {k}x ATR({n}) on TQQQ", chand=(k, n))
# LDS trend rules from famous trend followers
for n in (100, 150, 200, 252): add("Seykota/Donchian", f"LDS trend = above {n}d Donchian midpoint", core_trend="donchian", trend_params=(n,))
for e, x in ((20, 10), (55, 20), (100, 50), (200, 100), (252, 126)): add("Dennis/Darvas", f"LDS breakout in {e}d high / out {x}d low", core_trend="breakout", trend_params=(e, x))
for n, th in ((60, 0.1), (120, 0.1), (60, 0.2), (120, 0.2), (252, 0.1)): add("Kaufman", f"Dual trend + efficiency ratio({n}) > {th}", core_trend="kaufman", trend_params=(n, th))
# Carry / momentum-crash (AQR, Daniel & Moskowitz)
add("Carry", "TLT only when yield curve positive (10y > 3m)", tlt_carry=True)
add("Mom crash", "LDS overlay off when S&P 2-year return < 0", overlay_bear=True)
add("Mom crash", "Overlay off in bear + TLT carry", overlay_bear=True, tlt_carry=True)
# More legends: Weinstein stage 2, Minervini trend template, Zweig 4% rule, rates shock, transports, Ichimoku, weekly MACD
add("Weinstein", "Stage 2 (QQQ above rising 30-week avg): TQQQ max 50% when off", cap_sig=(("stage2",), 0.5)); add("Weinstein", "Stage 2: full TQQQ when on", boost_sig=("stage2",))
add("Minervini", "Trend template (50>150>200, 200 rising): full TQQQ", boost_sig=("template",)); add("Minervini", "Trend template: TQQQ max 50% when off", cap_sig=(("template",), 0.5))
add("Zweig", "4% weekly rule: TQQQ max 50% when off", cap_sig=(("zweig4",), 0.5)); add("Zweig", "4% weekly rule: TQQQ max 0% when off", cap_sig=(("zweig4",), 0.0)); add("Zweig", "4% weekly rule: split 60/40", split_sig=(("zweig4",), 0.6, 0.4))
for b in (1.0, 0.5): add("Rates", f"10y yield up > {b} pt in 6m: TQQQ max 50%", cap_sig=(("rates_calm", b), 0.5))
add("Rates", "10y yield up > 1 pt in 6m: split 60/40", split_sig=(("rates_calm", 1.0), 0.6, 0.4))
add("Dow Theory", "Transports below 200d: TQQQ max 50%", cap_sig=(("djt",), 0.5))
add("Ichimoku", "QQQ below the cloud: TQQQ max 50%", cap_sig=(("ichi",), 0.5)); add("Ichimoku", "QQQ above the cloud: full TQQQ", boost_sig=("ichi",))
add("Elder", "Weekly MACD below signal: TQQQ max 50%", cap_sig=(("macd",), 0.5)); add("Elder", "Weekly MACD: split 60/40", split_sig=(("macd",), 0.6, 0.4))
add("O'Neil", "Distribution days >= 5: TQQQ max 75%", cap_sig=(("dist", 5), 0.75))
add("Calendar", "Weekend risk: TQQQ max 75% over weekends", cap_sig=(("weekend",), 0.75))
# Combos fixed in advance
add("Combo", "Dow Theory cap 50% + chandelier 3x22", cap_sig=(("dow",), 0.5), chand=(3, 22))
add("Combo", "FOMC even weeks boost + Fed easing split", boost_sig=("fomc_even",), split_sig=(("easing", 0.0), 0.6, 0.5))
add("Combo", "Williams %R boost + distribution-day cap", boost_sig=("willr", -90), cap_sig=(("dist", 6), 0.5))
add("Combo", "VCP boost + Dow cap", boost_sig=("vcp", 0.6), cap_sig=(("dow",), 0.5))
add("Combo", "Semis-lead split + easing boost", split_sig=(("semi_lead",), 0.6, 0.4), boost_sig=("easing", 0.0))
add("Combo", "Breakout 55/20 + TLT carry", core_trend="breakout", trend_params=(55, 20), tlt_carry=True)

LONG = None
def work(a):
    import bt
    global LONG
    key, ov, kw, use_long = a
    if use_long:
        if LONG is None: LONG = bt.add_signal_cols(pd.read_pickle(os.path.join(HERE, "data", "panel_long.pkl")))
        s = bt.run(ov, panel=LONG, **kw)
    else: s = bt.run(ov, **kw)
    return key, s["equity"]

if __name__ == "__main__":
    jobs = []
    for sk, (kw, lg) in SC.items():
        jobs.append((("BASELINE", sk), V17, kw, lg))
        for g, n, ov, long_ok in I:
            if sk == "88" and not long_ok: continue
            jobs.append(((n, sk), {**V17, **ov}, kw, lg))
    if len(sys.argv) > 1:   # smoke test: one run per idea on the short 2010-26 window
        jobs = [((n, "10"), {**V17, **ov}, dict(start="2024-01-02"), False) for g, n, ov, _ in I] + [((n, "88"), {**V17, **ov}, dict(start="1995-01-03", end="1995-12-29"), True) for g, n, ov, lo in I if lo]
    print(len(I), "ideas,", len(jobs), "runs", flush=True); res = {}; t = time.time()
    with mp.Pool(15) as pool:
        for i, (k, eq) in enumerate(pool.imap_unordered(work, jobs), 1):
            res[k] = eq
            if i % 25 == 0: print(f"[{i}/{len(jobs)} {time.time()-t:4.0f}s]", flush=True)
    if len(sys.argv) > 1: print("smoke ok"); sys.exit()
    pickle.dump(res, open(os.path.join(OUT, "round10.pkl"), "wb"))
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
    df = pd.DataFrame(rows); df.to_csv(os.path.join(OUT, "round10.csv"), index=False)
    show = df.copy()
    for c in ["cagr00", "dd00", "d00", "cagr10", "dd10", "d10", "cagr88", "dd88", "d88"]: show[c] = (show[c] * 100).round(1)
    show["martin00"] = show["martin00"].round(2)
    pd.set_option("display.width", 300); pd.set_option("display.max_rows", 200)
    print(show.sort_values("d00", ascending=False).to_string(index=False))
