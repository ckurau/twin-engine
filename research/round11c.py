"""Weekly-RSI overbought cap: threshold grid on 2000-26, 2010-26, 1988-99 (+ monthly-difference t-stat on 1988-2026)."""
import os, sys, pickle, multiprocessing as mp
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); OUT = os.path.join(HERE, "out")
from round9 import V17, SC
from round10 import work
from round6 import metrics
SC2 = {**SC, "all": (dict(start="1988-01-04"), True)}
G = {"v1.7": {}}
for th in (60, 65, 68, 70, 72, 75, 80, 85): G[f"RSI<{th} cap50"] = dict(cap_sig=(("wrsi", th), 0.5))
for c in (0.0, 0.25, 0.75): G[f"RSI<70 cap{int(c*100)}"] = dict(cap_sig=(("wrsi", 70), c))
if __name__ == "__main__":
    jobs = [((g, s), {**V17, **ov}, kw, lg) for g, ov in G.items() for s, (kw, lg) in SC2.items()]
    with mp.Pool(15) as p: R = dict(p.map(work, jobs))
    pickle.dump(R, open(os.path.join(OUT, "round11c.pkl"), "wb"))
    B = {s: metrics(R[("v1.7", s)]) for s in SC2}; bm = R[("v1.7", "all")].resample("ME").last().pct_change().dropna()
    for g in G:
        m = {s: metrics(R[(g, s)]) for s in SC2}
        dm = R[(g, "all")].resample("ME").last().pct_change().dropna() - bm; t = dm.mean() / dm.std() * np.sqrt(len(dm)) if dm.std() > 0 else 0
        print(f"{g:16s}", "  ".join(f"{s}: {(m[s]['cagr']-B[s]['cagr'])*100:+.1f} / {m[s]['maxdd']*100:.0f}" for s in SC2), f"  t={t:.2f}")
