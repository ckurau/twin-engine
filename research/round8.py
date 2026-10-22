"""Round 8 (vs v1.6): ~100 new ideas aimed at more CAGR (goal 40%) without a much deeper drawdown.
Scored like round 6: 2000-26 and 2010-26 runs, Martin ratio, ten-year windows.
Pass (fixed in advance): better Martin AND CAGR not lower in both runs AND >= 12/17 windows ("better risk-adjusted"),
or CAGR +1.0 pt in both runs with max DD no more than 3 pts worse in both ("more return")."""
import os, sys, time, pickle, multiprocessing as mp
import numpy as np, pandas as pd
from ideas import _one, windows, sub, OUT
from round4 import V15
from round6 import metrics
V16 = {**V15, "lds_assets": ("SPY", "TLT", "GLD")}
I = []
def add(g, n, **ov): I.append((g, n, ov))
# A. crash detection / volatility estimators
for t in (0.70, 0.80, 0.90): add("Vol estimator", f"Downside-only volatility, target {t:.0%}", vol_semi=True, vol_target=t)
for t in (0.60, 0.70, 0.80): add("Vol estimator", f"High-low range volatility (Parkinson), target {t:.0%}", vol_park=True, vol_target=t)
for x in (0.01, 0.02, 0.05): add("Vol estimator", f"Ignore the switch within {x:.0%} of a 52-week high", vol_off_high=x)
for r_, hi in ((1.2, 0.9), (1.3, 0.9), (1.2, 1.0), (1.5, 1.0)): add("Vol estimator", f"Fear premium: VIX > {r_}x realized vol -> target {hi:.0%}", vrp=(r_, hi))
for cb, ab in ((0.05, 0.10), (0.05, 0.15), (0.02, 0.10), (0.10, 0.05)): add("Vol estimator", f"Switch hysteresis: cut at {cb:.0%} moves, add at {ab:.0%}", vol_hyst=(cb, ab))
for f in (0.2, 0.3, 0.5): add("Vol estimator", f"Never below {f:.0%} TQQQ (switch floor)", vol_floor=f)
for k in (0.5, 1.0): add("Vol estimator", f"CPPI: volatility target shrinks with drawdown (x{k})", cppi=k)
# B. regime split
for up, dn in ((0.55, 0.45), (0.60, 0.40), (0.65, 0.35), (0.70, 0.30), (0.60, 0.50), (0.70, 0.50), (0.50, 0.30), (0.60, 0.30)):
    add("Regime split", f"9Sig {up:.0%} when Nasdaq > 200d, {dn:.0%} below (monthly)", regime_split=(up, dn))
# C. 9Sig mechanics
for tp in (0.2, 0.3, 0.5): add("9Sig", f"Mid-quarter take-profit when growth {tp:.0%} above target", nine_tp=tp)
for bd in (0.2, 0.3, 0.5): add("9Sig", f"Mid-quarter buy when growth {bd:.0%} below target", nine_bd=bd)
add("9Sig", "Mid-quarter take-profit and buy at 30%", nine_tp=0.3, nine_bd=0.3)
for up, dn in ((0.09, 0.06), (0.10, 0.06), (0.12, 0.09), (0.09, 0.03), (0.12, 0.06)): add("9Sig", f"Growth target {up:.0%} in uptrends, {dn:.0%} in downtrends", sig_rate_trend=(up, dn))
add("9Sig", "Reserve TLT/GLD weighted by inverse volatility", def_invvol=True)
# D. calendar / short-term reversal
add("Calendar", "Santa Claus rally: full TQQQ Dec 22 - 2nd January session", santa=True)
add("Calendar", "Jobs-report Fridays: full TQQQ", nfp=True)
for thr, n in ((0.05, 5), (0.04, 5), (0.06, 3), (0.03, 5), (0.05, 10)): add("Calendar", f"Weekly reversal: after a {thr:.0%} Nasdaq week (uptrend), full TQQQ {n} days", wk_dip=(thr, n))
# E. LDS
add("LDS", "Drop Treasuries from LDS when stocks and bonds move together", lds_corr_cut=True)
add("LDS", "LDS trend needs 50d > 210d too (dual average)", core_trend="dual")
add("LDS", "Drop Treasuries when correlated + dual average", lds_corr_cut=True, core_trend="dual")
for a in ("SPY", "QQQ", "UPRO"): add("LDS", f"Idle LDS cash into {a}", lds_idle=a)

def runjobs(ideas, tag):
    jobs = []
    for start in ("2000-01-03", "2010-03-12"):
        jobs.append((("BASELINE", start), V16, dict(start=start)))
        jobs += [((n, start), {**V16, **ov}, dict(start=start)) for _, n, ov in ideas]
    res = {}; t = time.time()
    with mp.Pool(15) as pool:
        for i, (k, s, eq) in enumerate(pool.imap_unordered(_one, jobs), 1):
            res[k] = (s, eq)
            if i % 10 == 0: print(f"[{tag} {i}/{len(jobs)} {time.time()-t:4.0f}s]", flush=True)
    pickle.dump(res, open(os.path.join(OUT, f"{tag}.pkl"), "wb"))
    grp = {"BASELINE": "Base"}; grp.update({n: g for g, n, _ in ideas})
    b0, b10 = metrics(res[("BASELINE", "2000-01-03")][1]), metrics(res[("BASELINE", "2010-03-12")][1]); bw = windows(res[("BASELINE", "2000-01-03")][1])
    rows = []
    for _, n, _ in [("Base", "BASELINE", {})] + ideas:
        e0, e10 = res[(n, "2000-01-03")][1], res[(n, "2010-03-12")][1]; m0, m10 = metrics(e0), metrics(e10); w = windows(e0); wins = sum(w[y] > bw[y] for y in bw)
        risk = m0["martin"] > b0["martin"] and m10["martin"] > b10["martin"] and m0["cagr"] >= b0["cagr"] - 1e-4 and m10["cagr"] >= b10["cagr"] - 1e-4 and wins >= 12
        ret = m0["cagr"] - b0["cagr"] >= 0.01 and m10["cagr"] - b10["cagr"] >= 0.01 and m0["maxdd"] - b0["maxdd"] >= -0.03 and m10["maxdd"] - b10["maxdd"] >= -0.03
        rows.append(dict(group=grp[n], idea=n, cagr=m0["cagr"], maxdd=m0["maxdd"], martin=m0["martin"], cagr10=m10["cagr"], maxdd10=m10["maxdd"], martin10=m10["martin"],
                         dc=m0["cagr"] - b0["cagr"], dc10=m10["cagr"] - b10["cagr"], wins=wins, h1=sub(e0, "2000", "2012")["cagr"], h2=sub(e0, "2013", "2026")["cagr"],
                         days=res[(n, "2000-01-03")][0]["trade_days_yr"], verdict=("PASS risk-adj" if risk else "") + (" PASS return" if ret else "") if n != "BASELINE" else ""))
    df = pd.DataFrame(rows); df.to_csv(os.path.join(OUT, f"{tag}.csv"), index=False)
    show = df.copy()
    for c in ["cagr", "maxdd", "cagr10", "maxdd10", "dc", "dc10", "h1", "h2"]: show[c] = (show[c] * 100).round(1)
    for c in ["martin", "martin10"]: show[c] = show[c].round(2)
    pd.set_option("display.width", 300); pd.set_option("display.max_rows", 200)
    print(show.sort_values("dc", ascending=False)[["group", "idea", "cagr", "maxdd", "martin", "cagr10", "maxdd10", "martin10", "dc", "dc10", "wins", "h1", "h2", "days", "verdict"]].to_string(index=False))
    return df

if __name__ == "__main__":
    runjobs(I, "round8")
