"""Round 12 stress test: vol target set by stock/bond correlation (+ neighbours in levels, lookback, threshold) vs v1.7."""
import os, sys, pickle, multiprocessing as mp
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); OUT = os.path.join(HERE, "out")
from round9 import V17
from round9b import SC, mc
from round10 import work
from round6 import metrics
C = {"v1.7": {}}
for hi, lo in ((0.85, 0.75), (0.85, 0.80), (0.80, 0.75), (0.90, 0.75), (0.85, 0.70), (0.90, 0.70)): C[f"corr60<0: {hi:.0%}/{lo:.0%}"] = dict(vt_sig=(("sbc", 60, 0.0), hi, lo))
for lb in (20, 40, 120, 250): C[f"corr{lb}<0: 85/75"] = dict(vt_sig=(("sbc", lb, 0.0), 0.85, 0.75))
for th in (-0.2, 0.2): C[f"corr60<{th}: 85/75"] = dict(vt_sig=(("sbc", 60, th), 0.85, 0.75))
C["Combo: wRSI cap + breadth VT 90/70"] = dict(cap_sig=(("wrsi", 70), 0.5), vt_sig=(("breadth", 0.5), 0.90, 0.70))
C["Breadth VT 90/70 alone"] = dict(vt_sig=(("breadth", 0.5), 0.90, 0.70))
if __name__ == "__main__":
    jobs = [((c, s), {**V17, **ov}, kw, lg) for c, ov in C.items() for s, (kw, lg) in SC.items()]
    with mp.Pool(15) as p: R = dict(p.map(work, jobs))
    pickle.dump(R, open(os.path.join(OUT, "round12b.pkl"), "wb"))
    bm = R[("v1.7", "1988-2026")].resample("ME").last().pct_change().dropna(); rows = []
    for c in C:
        r = {"candidate": c}
        for s in SC: m = metrics(R[(c, s)]); r[s] = f"{m['cagr']*100:.1f}/{m['maxdd']*100:.0f}"
        med, p50 = mc(R[(c, "1988-2026")]); r["20y med"] = f"${med/1e6:.2f}M"; r[">50%"] = f"{p50:.0%}"
        y = R[(c, "1988-2026")].resample("YE").last().pct_change().dropna(); yb = R[("v1.7", "1988-2026")].resample("YE").last().pct_change().dropna()
        dm = R[(c, "1988-2026")].resample("ME").last().pct_change().dropna() - bm
        r["yrs +/-"] = f"{int((y > yb + 1e-6).sum())}/{int((y < yb - 1e-6).sum())}"; r["t"] = f"{dm.mean()/dm.std()*np.sqrt(len(dm)):.2f}" if dm.std() > 0 else "-"
        rows.append(r)
    df = pd.DataFrame(rows); df.to_csv(os.path.join(OUT, "round12b.csv"), index=False); pd.set_option("display.width", 320); print(df.to_string(index=False))
