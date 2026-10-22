"""Is the v1.7 dual trend overfit? Five tests.
1. Out-of-sample era: 1988-1999 was never used to design anything.
2. Plateau: fast average 5..175 days, in three separate periods.
3. Walk-forward: each year pick the fast average (or none) that did best on all earlier years, apply it the next year.
4. Paired test of monthly returns v1.7 - v1.6, and calendar years won.
5. Generality: the same rule on standard trend portfolios outside this strategy."""
import os, sys, math, pickle, multiprocessing as mp
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); OUT = os.path.join(HERE, "out")
from round4 import V15
V16 = {**V15, "lds_assets": ("SPY", "TLT", "GLD")}
FASTS = [5, 10, 15, 20, 25, 30, 40, 50, 60, 75, 100, 125, 150, 175]
LONG = None

def _run(a):
    import bt
    global LONG
    if LONG is None: LONG = pd.read_pickle(os.path.join(HERE, "data", "panel_long.pkl"))
    name, ov, kw = a
    return name, bt.run(ov, panel=LONG, **kw)["equity"]

def cagr(e): return (e.iloc[-1] / e.iloc[0]) ** (365.25 / (e.index[-1] - e.index[0]).days) - 1
def mdd(e): return float((e / e.cummax() - 1).min())

def trend_portfolio(px, assets, fast, start, lev=1.0, rf=None):
    """standard trend model: month-end, equal weight in assets above their 210d average (and, if fast, fast avg > 210d avg); rest T-bills"""
    p = px[list(assets)].loc[:].dropna(); r = p.pct_change().fillna(0); idx = p.loc[start:].index
    me = set(pd.Series(idx, index=idx).resample("ME").last()); w = {}; v = 1.0; out = []
    rfd = rf.reindex(idx).fillna(0) if rf is not None else pd.Series(0.0, index=idx)
    for d in idx:
        if w: v *= 1 + sum(wt * (lev * r.at[d, a] - (lev - 1) * rfd.at[d]) for a, wt in w.items()) + (1 - sum(w.values())) * rfd.at[d]
        if d in me or not w:
            h = p.loc[:d]; on = []
            for a in assets:
                s = h[a]; sma = s.iloc[-210:].mean()
                if s.iloc[-1] > sma and (not fast or s.iloc[-fast:].mean() > sma): on.append(a)
            w = {a: 1 / len(assets) for a in on}
        out.append(v)
    return pd.Series(out, index=idx)

if __name__ == "__main__":
    jobs = [("v1.6", V16, {}), ("v1.7", {**V16, "core_trend": "dual", "dual_fast": 30}, {})]
    jobs += [(f"fast{f}", {**V16, "core_trend": "dual", "dual_fast": f}, {}) for f in FASTS if f != 30]
    with mp.Pool(15) as p: R = dict(p.map(_run, [(n, ov, dict(start="1988-01-04", **kw)) for n, ov, kw in jobs]))
    R["fast30"] = R["v1.7"]; pickle.dump(R, open(os.path.join(OUT, "overfit_runs.pkl"), "wb"))
    periods = {"1988-1999 (never used)": ("1988", "1999"), "2000-2026": ("2000", "2026"), "2010-2026": ("2010-03", "2026")}
    print("1+2. CAGR / max DD by period (fresh start each period is approximated by slicing one 1988-2026 run)")
    rows = []
    for n in ["v1.6"] + [f"fast{f}" for f in FASTS]:
        e = R[n]; row = {"rule": n}
        for lab, (a, b) in periods.items():
            x = e.loc[a:b]; row[lab] = f"{cagr(x)*100:5.1f} / {mdd(x)*100:6.1f}"; row[lab + " d"] = round((cagr(x) - cagr(R['v1.6'].loc[a:b])) * 100, 1)
        rows.append(row)
    df = pd.DataFrame(rows); pd.set_option("display.width", 250); print(df.to_string(index=False))
    # 3. walk-forward
    cands = ["v1.6"] + [f"fast{f}" for f in FASTS]
    yr = {n: R[n].resample("YE").last().pct_change().dropna() for n in cands}
    years = yr["v1.6"].index; wf = []; picks = []
    for i, y in enumerate(years):
        if y.year < 1993: continue
        past = {n: float((1 + yr[n].loc[:years[i - 1]]).prod()) for n in cands}
        best = max(past, key=past.get); picks.append((y.year, best)); wf.append(float(yr[best].loc[y]))
    wf = pd.Series(wf, index=[p[0] for p in picks])
    base = yr["v1.6"].loc[str(wf.index[0]):]; v17 = yr["fast30"].loc[str(wf.index[0]):]
    g = lambda s: float((1 + s).prod() ** (1 / len(s)) - 1)
    print(f"\n3. Walk-forward {wf.index[0]}-{wf.index[-1]}: picked-by-past-data {g(wf)*100:.1f}%/yr  vs v1.6 {g(base)*100:.1f}%  vs v1.7 {g(v17)*100:.1f}%")
    print("   picks:", ", ".join(f"{y}:{b.replace('fast', '')}" for y, b in picks if y % 3 == 0 or y >= 2020))
    # 4. paired test
    for a, b in (("1988", "2026"), ("1988", "1999"), ("2000", "2026")):
        m6 = R["v1.6"].loc[a:b].resample("ME").last().pct_change().dropna(); m7 = R["v1.7"].loc[a:b].resample("ME").last().pct_change().dropna()
        dlt = (m7 - m6).dropna(); t = dlt.mean() / dlt.std() * math.sqrt(len(dlt))
        y6 = R["v1.6"].loc[a:b].resample("YE").last().pct_change().dropna(); y7 = R["v1.7"].loc[a:b].resample("YE").last().pct_change().dropna()
        print(f"4. {a}-{b}: monthly edge {dlt.mean()*1200:+.1f} pts/yr, t-stat {t:.2f}, months better {(dlt > 0).mean():.0%}, years better {(y7 > y6).sum()} of {len(y6)}")
    # 5. generality on standard trend portfolios
    L = pd.read_pickle(os.path.join(HERE, "data", "panel_long.pkl")); rf = L["RF"]
    print("\n5. Same rule on standard trend portfolios (CAGR / max DD), without vs with the 30-day check")
    for lab, assets, start, lev in (("SPY/TLT/GLD trend, 1x, 1988-2026", ("SPY", "TLT", "GLD"), "1988-01-04", 1.0),
                                    ("SPY/TLT/GLD trend, 3x, 1988-2026", ("SPY", "TLT", "GLD"), "1988-01-04", 3.0),
                                    ("Faber 5-asset (SPY, EEM, IEF, VNQ, GLD), 1997-2026", ("SPY", "EEM", "IEF", "VNQ", "GLD"), "1997-06-02", 1.0),
                                    ("Nasdaq trend alone (QQQ), 1988-2026", ("QQQ",), "1988-01-04", 1.0),
                                    ("S&P trend alone (SPY), 1988-2026", ("SPY",), "1988-01-04", 1.0),
                                    ("SPY/IWM/EEM/TLT/GLD trend, 1x, 1997-2026", ("SPY", "IWM", "EEM", "TLT", "GLD"), "1997-06-02", 1.0)):
        e0 = trend_portfolio(L, assets, None, start, lev, rf); e1 = trend_portfolio(L, assets, 30, start, lev, rf)
        print(f"   {lab:52s} {cagr(e0)*100:5.1f} / {mdd(e0)*100:6.1f}  ->  {cagr(e1)*100:5.1f} / {mdd(e1)*100:6.1f}")
