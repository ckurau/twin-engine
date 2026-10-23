"""Controls for the correlation vol target: constant 82.5% / 85% targets and the inverted rule."""
import os, sys, pickle, multiprocessing as mp
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); OUT = os.path.join(HERE, "out")
from round9 import V17
from round9b import SC
from round10 import work
from round6 import metrics
import round12b
C = {"v1.7": {}, "corr60<0: 85/75": dict(vt_sig=(("sbc", 60, 0.0), 0.85, 0.75)), "constant 82.5%": dict(vol_target=0.825), "constant 85%": dict(vol_target=0.85),
     "inverted: 75 when corr<0, 85 else": dict(vt_sig=(("sbc", 60, 0.0), 0.75, 0.85))}
if __name__ == "__main__":
    jobs = [((c, s), {**V17, **ov}, kw, lg) for c, ov in C.items() for s, (kw, lg) in SC.items()]
    with mp.Pool(15) as p: R = dict(p.map(work, jobs))
    pickle.dump(R, open(os.path.join(OUT, "round12c.pkl"), "wb"))
    for c in C: print(f"{c:36s}", "  ".join(f"{s}: {metrics(R[(c, s)])['cagr']*100:.1f}/{metrics(R[(c, s)])['maxdd']*100:.0f}" for s in SC))
    ex = R[("corr60<0: 85/75", "2000-26")]
