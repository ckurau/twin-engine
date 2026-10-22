"""Round 7 (vs v1.6): less reliance on tech. 9Sig growth engine mixes with non-tech 3x ETFs, vol switch on the whole mix.
Scored 2000-26 and 2010-26 plus tech-hostile stretches (2000-02 crash, 2000-12 lost decade for tech, 2022)."""
import os, time, pickle, multiprocessing as mp
import numpy as np, pandas as pd
from ideas import _one, windows, OUT
from round4 import V15
from round6 import metrics
V16 = {**V15, "lds_assets": ("SPY", "TLT", "GLD")}
B = dict(growth_vol_blend=True)
IDEAS = [
    ("TQQQ 75% / UPRO 25%, switch reads TQQQ vol", dict(growth=("TQQQ", "TQQQ", "TQQQ", "UPRO"))),
    ("TQQQ 50% / UPRO 50%, switch reads TQQQ vol", dict(growth=("TQQQ", "UPRO"))),
    ("TQQQ 75% / UDOW 25%, switch reads TQQQ vol", dict(growth=("TQQQ", "TQQQ", "TQQQ", "UDOW"))),
    ("TQQQ 50% / UPRO 50%, mix vol, target 60%", dict(growth=("TQQQ", "UPRO"), vol_target=0.60, **B)),
    ("TQQQ 50% / UPRO 50%, mix vol, target 65%", dict(growth=("TQQQ", "UPRO"), vol_target=0.65, **B)),
]
def seg(e, a, b): x = e.loc[a:b]; return (x.iloc[-1] / x.iloc[0]) ** (365.25 / (x.index[-1] - x.index[0]).days) - 1 if (x.index[-1] - x.index[0]).days > 400 else x.iloc[-1] / x.iloc[0] - 1
if __name__ == "__main__":
    jobs = []
    for start in ("2000-01-03", "2010-03-12"):
        jobs.append((("v1.6 (TQQQ only)", start), V16, dict(start=start)))
        jobs += [((n, start), {**V16, **ov}, dict(start=start)) for n, ov in IDEAS]
    res = {}; t = time.time()
    with mp.Pool(15) as pool:
        for i, (k, s, eq) in enumerate(pool.imap_unordered(_one, jobs), 1): res[k] = (s, eq); print(f"[{i}/{len(jobs)} {time.time()-t:4.0f}s] {k}", flush=True)
    pickle.dump(res, open(os.path.join(OUT, "round7b.pkl"), "wb"))
    rows = []; bw = windows(res[("v1.6 (TQQQ only)", "2000-01-03")][1])
    for n in ["v1.6 (TQQQ only)"] + [n for n, _ in IDEAS]:
        e0, e10 = res[(n, "2000-01-03")][1], res[(n, "2010-03-12")][1]; m0, m10 = metrics(e0), metrics(e10); w = windows(e0)
        rows.append(dict(idea=n, cagr=m0["cagr"], maxdd=m0["maxdd"], martin=m0["martin"], cagr10=m10["cagr"], maxdd10=m10["maxdd"], martin10=m10["martin"],
                         crash_00_02=e0.loc["2000-03-24":"2002-10-09"].pipe(lambda x: x.iloc[-1] / x.iloc[0] - 1), lost_00_12=seg(e0, "2000-01-01", "2012-12-31"),
                         y2022=e0.loc["2021-12-31":"2022-12-31"].pipe(lambda x: x.iloc[-1] / x.iloc[0] - 1), wins=sum(w[y] > bw[y] for y in bw)))
    df = pd.DataFrame(rows); df.to_csv(os.path.join(OUT, "round7b.csv"), index=False)
    for c in ["cagr", "maxdd", "cagr10", "maxdd10", "crash_00_02", "lost_00_12", "y2022"]: df[c] = (df[c] * 100).round(1)
    for c in ["martin", "martin10"]: df[c] = df[c].round(2)
    pd.set_option("display.width", 260); print(df.to_string(index=False))
