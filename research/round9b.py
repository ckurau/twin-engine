"""Round 9 stress test: 'LDS core = top 2 by momentum' (+ neighbours) and Santa, vs v1.7."""
import os, sys, pickle, multiprocessing as mp
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); OUT = os.path.join(HERE, "out")
from round9 import V17, work
from round6 import metrics
C = {"v1.7": {}, "Top 2 by momentum": dict(core_topk=2), "Top 1 by momentum": dict(core_topk=1),
     "Top 2, momentum 3/6/12": dict(core_topk=2, mom_months=(3, 6, 12)), "Top 2, momentum 6/12": dict(core_topk=2, mom_months=(6, 12)),
     "Top 2, momentum 1/3/6": dict(core_topk=2, mom_months=(1, 3, 6)), "Top 2, momentum 12 only": dict(core_topk=2, mom_months=(12,)),
     "Santa Claus rally": dict(santa=True), "Top 2 + Santa": dict(core_topk=2, santa=True)}
SC = {"2000-26": (dict(start="2000-01-03"), False), "2x costs": (dict(start="2000-01-03", slippage_bps=10.0), False), "from 2003": (dict(start="2003-01-02"), False),
      "from 2007": (dict(start="2007-01-03"), False), "from 2010": (dict(start="2010-03-12"), False), "1988-2026": (dict(start="1988-01-04"), True),
      "1988-99": (dict(start="1988-01-04", end="1999-12-31"), True)}
def mc(eq):
    m = eq.resample("ME").last(); r = m.pct_change().dropna().values; c = (m.iloc[-1] / m.iloc[0]) ** (12 / len(r)) - 1
    rng = np.random.default_rng(7); bl = np.array([r[i:i + 12] for i in range(len(r) - 11)]); paths = bl[rng.integers(0, len(bl), size=(20000, 20))].reshape(20000, 240)
    Rm = (1 + paths) * ((1 + c - 0.08) / (1 + c)) ** (1 / 12) - 1; v = np.full(20000, 20000.0); pk = v.copy(); w = np.zeros(20000)
    for k in range(240): v = (v + 200) * (1 + Rm[:, k]); pk = np.maximum(pk, v); w = np.minimum(w, v / pk - 1)
    return float(np.median(v)), float(np.mean(w < -0.5))
if __name__ == "__main__":
    jobs = [((c, s), {**V17, **ov}, kw, lg) for c, ov in C.items() for s, (kw, lg) in SC.items()]
    with mp.Pool(15) as p: R = dict(p.map(work, jobs))
    pickle.dump(R, open(os.path.join(OUT, "round9b.pkl"), "wb"))
    rows = []
    for c in C:
        r = {"candidate": c}
        for s in SC: m = metrics(R[(c, s)]); r[s] = f"{m['cagr']*100:.1f}/{m['maxdd']*100:.0f}"
        med, p50 = mc(R[(c, "1988-2026")]); r["20y median (1988-2026 sim)"] = f"${med/1e6:.2f}M"; r[">50% drop"] = f"{p50:.0%}"
        e = R[(c, "1988-2026")]; y = e.resample("YE").last().pct_change().dropna(); yb = R[("v1.7", "1988-2026")].resample("YE").last().pct_change().dropna()
        r["yrs better"] = f"{int((y > yb + 1e-9).sum())}/{len(y)}" if c != "v1.7" else "-"
        rows.append(r)
    df = pd.DataFrame(rows); df.to_csv(os.path.join(OUT, "round9b.csv"), index=False); pd.set_option("display.width", 300); print(df.to_string(index=False))
