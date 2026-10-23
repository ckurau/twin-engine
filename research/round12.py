"""Round 12 (vs v1.7): ~150 ideas. Main block = existing signals applied to parts of the strategy no signal has
controlled before (LDS leverage/cash, Fed swap, dip boost, TOM boost, vol target, 9Sig reserve, quarterly sells, mild split),
plus ensemble trend/vol rules and small structural changes. Same pass rules as rounds 9-11."""
import os, sys, time, pickle, multiprocessing as mp
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); OUT = os.path.join(HERE, "out")
from round9 import V17, SC
from round6 import metrics
from round10 import work
I = []
def add(g, n, long=True, **ov): I.append((g, n, ov, long))
def safe_work(a):
    try: return work(a)
    except Exception as e: print("FAILED", a[0], str(e)[:120], flush=True); return a[0], None
SIGS = [("Weekly RSI < 70", ("wrsi", 70)), ("Turbulence calm", ("turb", 0.90)), ("Breadth >= 50%", ("breadth", 0.5)), ("Dow Theory up", ("dow",)),
        ("Stock/bond corr < 0", ("sb_corr",)), ("Distribution days < 6", ("dist", 6)), ("Absorption calm", ("absorb", 1.0)), ("Vol falling", ("vol_fall",)),
        ("VIX < 25", ("vix_low", 25)), ("QQQ < 20% above 200d", ("notover", 0.20)), ("Semis leading", ("semi_lead",))]
for nm, sp in SIGS:
    g = nm
    add(g, f"{nm}, else LDS unleveraged", lds_sig=(sp, "lev1"))
    add(g, f"{nm}, else LDS in T-bills", lds_sig=(sp, "cash"))
    add(g, f"Fed swap only when {nm}", swap_sig=sp)
    add(g, f"Dip boost only when {nm}", dip_sig=sp)
    add(g, f"TOM boost only when {nm}", tom_sig=sp)
    add(g, f"Vol target 90% when {nm}, else 70%", vt_sig=(sp, 0.90, 0.70))
    add(g, f"Vol target 85% when {nm}, else 75%", vt_sig=(sp, 0.85, 0.75))
    add(g, f"{nm}, else 9Sig reserve in T-bills", res_sig=(sp, ("BIL",)))
    add(g, f"Skip quarterly sells when {nm}", qsell_sig=sp)
    add(g, f"Split 55/45 when {nm}, else 45/55", split_sig=(sp, 0.55, 0.45))
    add(g, f"{nm}, else TQQQ max 75% and LDS unleveraged", cap_sig=(sp, 0.75), lds_sig=(sp, "lev1"))
# other signals on new targets
add("52-week high", "Fed swap only when QQQ within 5% of high", swap_sig=("ath", 0.05)); add("52-week high", "Fed swap only when QQQ < 15% below high", swap_sig=("notdeep", 0.15))
add("52-week high", "Dip boost only when QQQ < 15% below high", dip_sig=("notdeep", 0.15)); add("52-week high", "Vol target 90% within 5% of high, else 75%", vt_sig=(("ath", 0.05), 0.90, 0.75))
add("52-week high", "QQQ < 15% below high, else LDS in T-bills", lds_sig=(("notdeep", 0.15), "cash"))
add("52-week high", "Skip quarterly sells within 5% of high", qsell_sig=("ath", 0.05)); add("Trend quality", "Skip quarterly sells when QQQ 1-yr Sharpe > 1", qsell_sig=("sharpe", 1.0))
add("Reserve", "Stock/bond corr > 0: reserve gold + T-bills", res_sig=(("sb_corr",), ("GLD", "BIL")))
add("Reserve", "Gold not beating Treasuries: reserve TLT only", res_sig=(("gold_tsy",), ("TLT",)))
add("Fed swap", "Fed swap into SOXL only when semis lead, else TQQQ", swap_asset_sig=(("semi_lead",), (("SOXL", 1.0),), (("TQQQ", 1.0),)))
add("Fed swap", "Fed swap into TQQQ when tech leads, else UPRO", swap_asset_sig=(("tech_lead",), (("TQQQ", 1.0),), (("UPRO", 1.0),)))
# ensembles (Hoffstein / Newfound "timing luck")
add("Ensemble", "LDS trend = 9-rule ensemble (150/210/270 x 20/30/40), size by share up", core_trend="ens", trend_params="frac")
add("Ensemble", "LDS trend = 9-rule ensemble, majority vote", core_trend="ens", trend_params="maj")
for e in ((10, 20, 40), (15, 20, 30), (20, 40, 60)): add("Ensemble", f"Vol switch = average of {'/'.join(map(str, e))}-day vol", vol_ens=e)
# small structural
for a in ("GLD", "IEF", "SHY"): add("LDS cash", f"Idle LDS cash into {a}", long=(a == "GLD"), lds_idle=a)
for m in (3, 6, 9): add("Reset date", f"50/50 reset at end of month {m} instead of December", rebalance_months=(m,))
for v in (25, 35): add("LDS overlay", f"LDS overlay off when VIX > {v}", overlay_vix=v)
# combos fixed in advance
add("Combo", "Weekly RSI cap 50% + turbulence LDS T-bills", cap_sig=(("wrsi", 70), 0.5), lds_sig=(("turb", 0.90), "cash"))
add("Combo", "Weekly RSI cap 50% + breadth vol target 90/70", cap_sig=(("wrsi", 70), 0.5), vt_sig=(("breadth", 0.5), 0.90, 0.70))
add("Combo", "Ensemble LDS trend (frac) + ensemble vol 10/20/40", core_trend="ens", trend_params="frac", vol_ens=(10, 20, 40))
add("Combo", "Fed swap only in turbulence calm + dip only in breadth", swap_sig=("turb", 0.90), dip_sig=("breadth", 0.5))
add("Combo", "Skip sells near highs + weekly RSI cap", qsell_sig=("ath", 0.05), cap_sig=(("wrsi", 70), 0.5))

if __name__ == "__main__":
    jobs = []
    for sk, (kw, lg) in SC.items():
        jobs.append((("BASELINE", sk), V17, kw, lg))
        for g, n, ov, long_ok in I:
            if sk == "88" and not long_ok: continue
            jobs.append(((n, sk), {**V17, **ov}, kw, lg))
    if len(sys.argv) > 1:
        jobs = [((n, "10"), {**V17, **ov}, dict(start="2023-06-01"), False) for g, n, ov, _ in I] + [((n, "88"), {**V17, **ov}, dict(start="1994-06-01", end="1995-06-30"), True) for g, n, ov, lo in I if lo]
    print(len(I), "ideas,", len(jobs), "runs", flush=True); res = {}; t = time.time()
    with mp.Pool(15) as pool:
        for i, (k, eq) in enumerate(pool.imap_unordered(safe_work, jobs), 1):
            if eq is not None: res[k] = eq
            if i % 50 == 0: print(f"[{i}/{len(jobs)} {time.time()-t:4.0f}s]", flush=True); pickle.dump(res, open(os.path.join(OUT, "round12_partial.pkl"), "wb"))
    if len(sys.argv) > 1: print("smoke ok"); sys.exit()
    pickle.dump(res, open(os.path.join(OUT, "round12.pkl"), "wb"))
    B = {sk: metrics(res[("BASELINE", sk)]) for sk in SC}
    rows = []
    for g, n, ov, long_ok in [("Base", "BASELINE", {}, True)] + I:
        m = {sk: metrics(res[(n, sk)]) if (n, sk) in res else None for sk in SC}
        if m["00"] is None or m["10"] is None: print("missing", n); continue
        d = {sk: (m[sk]["cagr"] - B[sk]["cagr"]) if m[sk] else None for sk in SC}
        dd = {sk: (m[sk]["maxdd"] - B[sk]["maxdd"]) if m[sk] else None for sk in SC}
        ret = d["00"] >= 0.005 and d["10"] >= 0.005 and (d["88"] is None or d["88"] >= -0.005) and all(x is None or x >= -0.03 for x in dd.values())
        risk = all(m[sk] is None or (m[sk]["martin"] > B[sk]["martin"] and d[sk] >= -1e-4) for sk in SC)
        rows.append(dict(group=g, idea=n, cagr00=m["00"]["cagr"], dd00=m["00"]["maxdd"], d00=d["00"], cagr10=m["10"]["cagr"], dd10=m["10"]["maxdd"], d10=d["10"],
                         cagr88=m["88"]["cagr"] if m["88"] else np.nan, dd88=m["88"]["maxdd"] if m["88"] else np.nan, d88=d["88"] if d["88"] is not None else np.nan,
                         martin00=m["00"]["martin"], verdict=("PASS return " if ret else "") + ("PASS risk" if risk else "") if n != "BASELINE" else ""))
    df = pd.DataFrame(rows); df.to_csv(os.path.join(OUT, "round12.csv"), index=False)
    show = df.copy()
    for c in ["cagr00", "dd00", "d00", "cagr10", "dd10", "d10", "cagr88", "dd88", "d88"]: show[c] = (show[c] * 100).round(1)
    show["martin00"] = show["martin00"].round(2)
    pd.set_option("display.width", 300); pd.set_option("display.max_rows", 300)
    print(show.sort_values("d00", ascending=False).to_string(index=False))
