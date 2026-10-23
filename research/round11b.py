"""Round 11 stress test: earnings-season boost, weekly-RSI cap, overextension cap, Fed reserve swap (+ neighbours) vs v1.7."""
import os, sys, pickle, multiprocessing as mp
import pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); OUT = os.path.join(HERE, "out")
from round9 import V17
from round9b import SC, mc
from round10 import work
from round6 import metrics
C = {"v1.7": {},
     "Earnings season d10-d7 (tested)": dict(boost_sig=("earn",)), "Earnings d1-d0 (1st month)": dict(boost_sig=("earnw", 1, 0)),
     "Earnings d5-d0": dict(boost_sig=("earnw", 5, 0)), "Earnings d15-d7": dict(boost_sig=("earnw", 15, 7)), "Earnings d10-d15": dict(boost_sig=("earnw", 10, 15)),
     "Weekly RSI<70 cap 50%": dict(cap_sig=(("wrsi", 70), 0.5)), "Weekly RSI<65 cap 50%": dict(cap_sig=(("wrsi", 65), 0.5)),
     "Weekly RSI<75 cap 50%": dict(cap_sig=(("wrsi", 75), 0.5)), "Weekly RSI<70 cap 75%": dict(cap_sig=(("wrsi", 70), 0.75)),
     "Overextension 20% cap": dict(cap_sig=(("notover", 0.20), 0.5)), "Overextension 15% cap": dict(cap_sig=(("notover", 0.15), 0.5)),
     "Fed reserve swap SOXL 100%": dict(res_swap=("SOXL", 1.0)), "Fed reserve swap SOXL 50%": dict(res_swap=("SOXL", 0.5))}
if __name__ == "__main__":
    jobs = [((c, s), {**V17, **ov}, kw, lg) for c, ov in C.items() for s, (kw, lg) in SC.items()]
    with mp.Pool(15) as p: R = dict(p.map(work, jobs))
    pickle.dump(R, open(os.path.join(OUT, "round11b.pkl"), "wb"))
    rows = []
    for c in C:
        r = {"candidate": c}
        for s in SC: m = metrics(R[(c, s)]); r[s] = f"{m['cagr']*100:.1f}/{m['maxdd']*100:.0f}"
        med, p50 = mc(R[(c, "1988-2026")]); r["20y median"] = f"${med/1e6:.2f}M"; r[">50% drop"] = f"{p50:.0%}"
        y = R[(c, "1988-2026")].resample("YE").last().pct_change().dropna(); yb = R[("v1.7", "1988-2026")].resample("YE").last().pct_change().dropna()
        r["yrs +/-"] = f"{int((y > yb + 1e-6).sum())}/{int((y < yb - 1e-6).sum())}" if c != "v1.7" else "-"
        rows.append(r)
    df = pd.DataFrame(rows); df.to_csv(os.path.join(OUT, "round11b.csv"), index=False); pd.set_option("display.width", 300); print(df.to_string(index=False))
