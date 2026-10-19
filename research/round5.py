"""Round 5: stress tests for 'LDS without QQQ' and replacements for the Nasdaq leg (vs v1.5), same scenarios as round 3."""
import os, pickle, time, multiprocessing as mp
import pandas as pd
from ideas import _one, windows, OUT
from round4 import V15
CANDS = {
    "v1.5 (baseline)": V15,
    "LDS: SPY, TLT, GLD": {**V15, "lds_assets": ("SPY", "TLT", "GLD")},
    "LDS: SPY, TLT, GLD + Fed swap into TQQQ": {**V15, "lds_assets": ("SPY", "TLT", "GLD"), "swap_asset": (("TQQQ", 1.0),)},
    "LDS: SPY, IWM, TLT, GLD (small caps for QQQ)": {**V15, "lds_assets": ("SPY", "IWM", "TLT", "GLD")},
    "LDS: SPY, EEM, TLT, GLD (EM for QQQ)": {**V15, "lds_assets": ("SPY", "EEM", "TLT", "GLD")},
    "LDS: SPY, TLT, IEF, GLD (bonds for QQQ)": {**V15, "lds_assets": ("SPY", "TLT", "IEF", "GLD")},
    "LDS: SPY, TLT, GLD, trend 240d": {**V15, "lds_assets": ("SPY", "TLT", "GLD"), "sma_days": 240},
    "LDS: SPY, TLT, GLD, core vol 120%": {**V15, "lds_assets": ("SPY", "TLT", "GLD"), "lds_vol_target": 1.2},
}
SCEN = {"2000-26": dict(), "2x costs": dict(slippage_bps=10.0), "from 2003": dict(start="2003-01-02"),
        "from 2007": dict(start="2007-01-03"), "from 2010 (real ETFs)": dict(start="2010-03-12")}
if __name__ == "__main__":
    jobs = [((c, s), ov, kw) for c, ov in CANDS.items() for s, kw in SCEN.items()]
    res = {}; t = time.time()
    with mp.Pool(15) as pool:
        for i, (key, s, eq) in enumerate(pool.imap_unordered(_one, jobs), 1):
            res[key] = (s, eq); print(f"[{i}/{len(jobs)} {time.time()-t:4.0f}s] {key}", flush=True)
    pickle.dump(res, open(os.path.join(OUT, "round5.pkl"), "wb"))
    rows = []
    for c in CANDS:
        r = {"candidate": c}
        for s in SCEN: r[s] = f"{res[(c, s)][0]['cagr']*100:.1f} / {res[(c, s)][0]['maxdd']*100:.1f}"
        bw = windows(res[("v1.5 (baseline)", "2000-26")][1]); w = windows(res[(c, "2000-26")][1]); r["wins"] = f"{sum(w[y] > bw[y] for y in bw)}/17"
        eq = res[(c, "2000-26")][1]; be = res[("v1.5 (baseline)", "2000-26")][1]
        h = lambda e, a, b: (e.loc[a:b].iloc[-1] / e.loc[a:b].iloc[0]) ** (1 / ((e.loc[a:b].index[-1] - e.loc[a:b].index[0]).days / 365.25)) - 1
        r["2000-12"] = f"{h(eq,'2000','2012')*100:.1f}"; r["2013-26"] = f"{h(eq,'2013','2026')*100:.1f}"
        r["days/yr"] = round(res[(c, "2000-26")][0]["trade_days_yr"])
        rows.append(r)
    df = pd.DataFrame(rows); df.to_csv(os.path.join(OUT, "round5.csv"), index=False)
    pd.set_option("display.width", 300); print(df.to_string(index=False))
