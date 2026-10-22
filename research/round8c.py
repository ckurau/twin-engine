"""Round 8 stress test of the batch-2 passes: double costs, fresh starts 2003 / 2007, real-ETF era, and halves."""
import os, time, pickle, multiprocessing as mp
import pandas as pd
from ideas import _one, OUT
from round4 import V15
from round6 import metrics
V16 = {**V15, "lds_assets": ("SPY", "TLT", "GLD")}
S = dict(santa=True); DU = dict(core_trend="dual"); VR = dict(vrp=(1.5, 1.0))
C = {"v1.6": {}, "Dual 30d": dict(core_trend="dual", dual_fast=30), "Santa + dual": {**S, **DU}, "Santa + dual + fear": {**S, **DU, **VR},
     "Santa + dual + fear, 60/40": {**S, **DU, **VR, "split_9sig": 0.6}, "Santa + dual, 60/40": {**S, **DU, "split_9sig": 0.6},
     "Dual 30d, 60/40": dict(core_trend="dual", dual_fast=30, split_9sig=0.6), "v1.6, 60/40 (no new rules)": dict(split_9sig=0.6)}
SC = {"2000-26": dict(), "2x costs": dict(slippage_bps=10.0), "from 2003": dict(start="2003-01-02"), "from 2007": dict(start="2007-01-03"), "from 2010": dict(start="2010-03-12")}
if __name__ == "__main__":
    jobs = [((c, s), {**V16, **ov}, kw) for c, ov in C.items() for s, kw in SC.items()]
    res = {}
    with mp.Pool(15) as pool:
        for k, s, eq in pool.imap_unordered(_one, jobs): res[k] = (s, eq)
    rows = []
    for c in C:
        r = {"candidate": c}
        for s in SC: m = metrics(res[(c, s)][1]); r[s] = f"{m['cagr']*100:.1f} / {m['maxdd']*100:.1f}"
        e = res[(c, "2000-26")][1]
        for a, b in (("2000", "2012"), ("2013", "2026")):
            x = e.loc[a:b]; r[f"{a}-{b[2:]}"] = round(((x.iloc[-1] / x.iloc[0]) ** (365.25 / (x.index[-1] - x.index[0]).days) - 1) * 100, 1)
        rows.append(r)
    df = pd.DataFrame(rows); df.to_csv(os.path.join(OUT, "round8c.csv"), index=False); pd.set_option("display.width", 250); print(df.to_string(index=False))
