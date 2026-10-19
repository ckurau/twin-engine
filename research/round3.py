"""Round 3: stress tests for the round-2 finalists.
 - costs doubled (0.10% per fill)
 - fresh starts in 2003, 2007 and 2010-03-12 (from then on every leveraged ETF series is the real ETF, incl. SOXL)
 - neighbouring settings (dip threshold, review timing, swap asset mix)
"""
import os, pickle, time, multiprocessing as mp
import numpy as np, pandas as pd
from ideas import _one, windows, sub, OUT

X = dict(swap_asset=(("SOXL", 1.0),)); XT = dict(swap_asset=(("TQQQ", 0.5), ("SOXL", 0.5)))
M = dict(lds_freq="month")
def c(*ds):
    o = {}
    for d in ds: o.update(d)
    return o
CANDS = {
    "Baseline v1.3": {},
    "A: SOXL swap + monthly + dip 20": c(X, M, dict(nine_dip=20)),
    "A, dip 15": c(X, M, dict(nine_dip=15)), "A, dip 10": c(X, M, dict(nine_dip=10)), "A, dip 25": c(X, M, dict(nine_dip=25)),
    "A, swap TQQQ+SOXL": c(XT, M, dict(nine_dip=20)),
    "B: SOXL swap + monthly": c(X, M),
    "C: monthly + dip 20 + GLD defensive": c(M, dict(nine_dip=20, defensive=("GLD",))),
    "D: monthly + dip 20": c(M, dict(nine_dip=20)), "D, dip 15": c(M, dict(nine_dip=15)), "D, dip 25": c(M, dict(nine_dip=25)),
    "Monthly only": M, "Dip 20 only": dict(nine_dip=20), "SOXL swap only": X,
}
SCEN = {"2000-26": dict(), "2000-26, 2x costs": dict(slippage_bps=10.0), "from 2003": dict(start="2003-01-02"),
        "from 2007": dict(start="2007-01-03"), "from 2010 (real ETFs)": dict(start="2010-03-12")}

if __name__ == "__main__":
    jobs = [((cn, sn), ov, kw) for cn, ov in CANDS.items() for sn, kw in SCEN.items()]
    res = {}; t = time.time()
    with mp.Pool(15) as pool:
        for i, (key, s, eq) in enumerate(pool.imap_unordered(_one, jobs), 1):
            res[key] = (s, eq); print(f"[{i}/{len(jobs)} {time.time()-t:4.0f}s] {key}", flush=True)
    pickle.dump(res, open(os.path.join(OUT, "round3.pkl"), "wb"))
    rows = []
    for cn in CANDS:
        r = {"candidate": cn}
        for sn in SCEN:
            s, eq = res[(cn, sn)]; r[f"{sn} CAGR"] = round(s["cagr"] * 100, 1); r[f"{sn} DD"] = round(s["maxdd"] * 100, 1)
        bw = windows(res[("Baseline v1.3", "2000-26")][1]); w = windows(res[(cn, "2000-26")][1])
        r["wins"] = sum(w[y] > bw[y] for y in bw)
        bw2 = windows(res[("Baseline v1.3", "2000-26, 2x costs")][1]); w2 = windows(res[(cn, "2000-26, 2x costs")][1])
        r["wins 2x"] = sum(w2[y] > bw2[y] for y in bw2)
        r["trade days/yr"] = round(res[(cn, "2000-26")][0]["trade_days_yr"])
        rows.append(r)
    df = pd.DataFrame(rows); df.to_csv(os.path.join(OUT, "round3.csv"), index=False)
    pd.set_option("display.width", 300); pd.set_option("display.max_columns", 40)
    print(df.to_string(index=False))
