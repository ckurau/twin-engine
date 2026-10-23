"""Round 13 stress test: finalists vs v1.7 in synthetic disaster panels (2000-26) and execution stresses."""
import os, sys, pickle, multiprocessing as mp
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); OUT = os.path.join(HERE, "out")
from round9 import V17
from round6 import metrics
C = {"v1.7": {},
     "Corr vol target + gold/T-bill reserve (passed)": dict(vt_sig=(("sbc", 60, 0.0), 0.85, 0.75), res_sig=(("sbc", 60, 0.0), ("GLD", "BIL"))),
     "Corr vol target alone (watchlist)": dict(vt_sig=(("sbc", 60, 0.0), 0.85, 0.75)),
     "Weekly RSI cap (watchlist)": dict(cap_sig=(("wrsi", 70), 0.5)),
     "Vol switch after 2 days": dict(vol_persist=2), "Reserve 2 gold : 1 IEF": dict(defensive=("GLD", "GLD", "IEF")),
     "Beta cap 2.25x": dict(beta_cap=2.25), "TQQQ ceiling 90%": dict(nine_wmax=0.9), "LDS max 2x": dict(lds_kmax=2),
     "Crash-day brake 5%": dict(daycrash=(0.05, 5, "cap")), "Fed swap 75%": dict(swap_frac=0.75), "QLD when T-bill > 5%": dict(growth_rot=(("TQQQ", "QLD"), 5.0, "rate"))}
PANELS = ["normal", "lost_tech", "flat_stocks", "bond_bear", "stagflation", "crash_days", "financing", "high_vol"]
EXEC = {"slippage 0.30%": dict(slippage_bps=30.0), "orders 1 day late": dict(lag=True), "whole shares, $20k": "whole"}
PX = {}
def work(a):
    import bt, stress
    key, ov, kind, kw = a
    if kind in ("normal",) + tuple(EXEC): panel = bt.PANEL
    else:
        if kind not in PX: PX[kind] = stress.make(kind, bt.PANEL)
        panel = PX[kind]
    if kw == "whole": ov = {**ov, "fractional": False, "min_order": bt._BASE_P.get("min_order", 0.0)}; kw = {}
    return key, bt.run(ov, panel=panel, start="2000-01-03", **kw)["equity"]
if __name__ == "__main__":
    import bt, stress
    jobs = [((c, k), {**V17, **ov}, k, {}) for c, ov in C.items() for k in PANELS] + [((c, k), {**V17, **ov}, k, kw) for c, ov in C.items() for k, kw in EXEC.items()]
    with mp.Pool(15) as p: R = dict(p.map(work, jobs))
    pickle.dump(R, open(os.path.join(OUT, "round13b.pkl"), "wb"))
    # blends with the market (sub-accounts reset monthly), computed in each stressed panel
    from round13 import blend
    for k in PANELS:
        px = bt.PANEL if k == "normal" else stress.make(k, bt.PANEL)
        for nm, w, col in (("80% v1.7 + 20% VOO", 0.8, "SPY"), ("80% v1.7 + 20% gold", 0.8, "GLD")):
            R[(nm, k)] = blend(R[("v1.7", k)], px[col].pct_change(), w)
    cols = PANELS + list(EXEC); names = list(C) + ["80% v1.7 + 20% VOO", "80% v1.7 + 20% gold"]
    rows = []
    for c in names:
        r = {"candidate": c}
        for k in cols:
            if (c, k) in R: m = metrics(R[(c, k)]); r[k] = f"{m['cagr']*100:.1f}/{m['maxdd']*100:.0f}"
        rows.append(r)
    df = pd.DataFrame(rows); df.to_csv(os.path.join(OUT, "round13b.csv"), index=False)
    pd.set_option("display.width", 400); print(df.to_string(index=False))
