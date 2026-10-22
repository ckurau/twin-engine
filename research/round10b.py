"""Round 10 stress test of the passes (Williams %R dip boost, Minervini VCP boost) + neighbours, vs v1.7."""
import os, sys, pickle, multiprocessing as mp
import pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); OUT = os.path.join(HERE, "out")
from round9 import V17
from round9b import SC, mc
from round10 import work
from round6 import metrics
C = {"v1.7": {}, "%R < -90 boost": dict(boost_sig=("willr", -90)), "%R < -85 boost": dict(boost_sig=("willr", -85)), "%R < -80 boost": dict(boost_sig=("willr", -80)),
     "%R < -95 boost": dict(boost_sig=("willr", -95)), "VCP 0.6 boost": dict(boost_sig=("vcp", 0.6)), "VCP 0.7 boost": dict(boost_sig=("vcp", 0.7))}
if __name__ == "__main__":
    jobs = [((c, s), {**V17, **ov}, kw, lg) for c, ov in C.items() for s, (kw, lg) in SC.items()]
    with mp.Pool(15) as p: R = dict(p.map(work, jobs))
    pickle.dump(R, open(os.path.join(OUT, "round10b.pkl"), "wb"))
    rows = []
    for c in C:
        r = {"candidate": c}
        for s in SC: m = metrics(R[(c, s)]); r[s] = f"{m['cagr']*100:.1f}/{m['maxdd']*100:.0f}"
        med, p50 = mc(R[(c, "1988-2026")]); r["20y median"] = f"${med/1e6:.2f}M"; r[">50% drop"] = f"{p50:.0%}"
        y = R[(c, "1988-2026")].resample("YE").last().pct_change().dropna(); yb = R[("v1.7", "1988-2026")].resample("YE").last().pct_change().dropna()
        r["yrs better/worse"] = f"{int((y > yb + 1e-6).sum())}/{int((y < yb - 1e-6).sum())}" if c != "v1.7" else "-"
        rows.append(r)
    df = pd.DataFrame(rows); df.to_csv(os.path.join(OUT, "round10b.csv"), index=False); pd.set_option("display.width", 300); print(df.to_string(index=False))
