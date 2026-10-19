"""Round 6 (vs v1.6): new ideas scored on several metrics, from 2000 and from 2010 (real ETFs only).
Metrics: CAGR, max drawdown, Ulcer index (depth x duration of drawdowns), Martin ratio = CAGR / Ulcer,
worst ten-year CAGR (starts Jan 2000..2016), ten-year windows won vs v1.6, halves.
Acceptance (fixed in advance): better Martin ratio AND CAGR not lower, in BOTH the 2000 and 2010 runs,
and ahead in >= 12 of 17 windows on CAGR; or (risk-for-return trade) CAGR >= +1.0 pt in both runs with max DD no more than 3 pt worse."""
import os, time, pickle, multiprocessing as mp
import numpy as np, pandas as pd
from ideas import _one, windows, sub, OUT
from round4 import V15
V16 = {**V15, "lds_assets": ("SPY", "TLT", "GLD")}
H = lambda **lm: dict(LMAX_LONG={**dict(SPY=3, QQQ=3, TLT=3, GLD=2), **lm})
IDEAS = [  # group, name, overrides, hooks
    ("Cash", "Idle cash earns T-bill rate (park it in SGOV)", dict(cash_yield=True), None),
    ("LDS", "Core trend: above 210d OR 12-mo momentum > 0", dict(core_trend="or_mom"), None),
    ("LDS", "Core trend: above 210d AND 12-mo momentum > 0", dict(core_trend="and_mom"), None),
    ("LDS", "Core weights: equal risk contribution (uses correlations)", dict(core_erc=True), None),
    ("LDS", "Core weights: momentum / volatility", dict(core_mom_weight=True), None),
    ("LDS", "Treasuries capped at 2x (UBT, less TMF decay)", {}, H(TLT=2)),
    ("LDS", "Gold capped at 1x (GLD, no UGL)", {}, H(GLD=1)),
    ("LDS", "Always 3x ETFs, rest in T-bills", dict(lds_max_lev=True), None),
    ("LDS", "Monthly review on the 15th instead of month end", dict(lds_freq="midmonth"), None),
    ("Split", "50/50 reset in June instead of December", dict(rebalance_months=(6,)), None),
    ("9Sig", "Vol switch: higher of 10-day and 20-day vol (faster cut)", dict(vol_fast=True), None),
    ("9Sig", "Vol target 90% in uptrend, 70% in downtrend", dict(vol_target_trend=(0.90, 0.70)), None),
    ("9Sig", "Vol target 90% in uptrend, 80% in downtrend", dict(vol_target_trend=(0.90, 0.80)), None),
    ("9Sig", "Defensive: better of TLT/GLD by 6-mo momentum", dict(def_relmom=6), None),
    ("9Sig", "Defensive: better of TLT/GLD by 3-mo momentum", dict(def_relmom=3), None),
    ("9Sig", "Defensive: 3x/2x (TMF/UGL) when trending, else T-bills", dict(def_lev_trend=True), None),
    ("9Sig", "9Sig buy-only (never sells TQQQ into the reserve)", dict(nine_buy_only=True), None),
    ("Risk budget", "55/45 (spend v1.6's lower drawdown on more 9Sig)", dict(split_9sig=0.55), None),
    ("Risk budget", "60/40", dict(split_9sig=0.60), None),
    ("Risk budget", "70/30", dict(split_9sig=0.70), None),
    ("Risk budget", "Vol target 85%", dict(vol_target=0.85), None),
    ("Risk budget", "Vol target 90%", dict(vol_target=0.90), None),
    ("Risk budget", "60/40 + idle cash in T-bills", dict(split_9sig=0.60, cash_yield=True), None),
    ("Risk budget", "60/40 + defensive 2x (UBT + UGL)", dict(split_9sig=0.60, defensive=("UBT", "UGL")), None),
    ("Risk budget", "LDS core vol target 150% (more leverage)", dict(lds_vol_target=1.5), None),
]

def metrics(eq):
    yrs = (eq.index[-1] - eq.index[0]).days / 365.25; c = (eq.iloc[-1] / eq.iloc[0]) ** (1 / yrs) - 1
    dd = eq / eq.cummax() - 1; ulcer = float(np.sqrt((dd ** 2).mean()))
    under = (dd < 0).astype(int); runs = under.groupby((under != under.shift()).cumsum()).sum(); longest = int(runs.max()) if len(runs) else 0
    return dict(cagr=c, maxdd=float(dd.min()), ulcer=ulcer, martin=c / ulcer if ulcer else np.nan, underwater_days=longest)

if __name__ == "__main__":
    jobs = []
    for start in ("2000-01-03", "2010-03-12"):
        jobs.append((("BASELINE", start), V16, dict(start=start)))
        jobs += [((n, start), {**V16, **ov}, dict(start=start, **({"hooks": h} if h else {}))) for _, n, ov, h in IDEAS]
    res = {}; t = time.time()
    with mp.Pool(15) as pool:
        for i, (key, s, eq) in enumerate(pool.imap_unordered(_one, jobs), 1):
            res[key] = (s, eq); print(f"[{i}/{len(jobs)} {time.time()-t:4.0f}s] {key[0][:55]:55s} {key[1][:4]}  CAGR {s['cagr']*100:5.1f}%  DD {s['maxdd']*100:6.1f}%", flush=True)
    pickle.dump(res, open(os.path.join(OUT, "round6.pkl"), "wb"))
    grp = {"BASELINE": "Base"}; grp.update({n: g for g, n, _, _ in IDEAS})
    b0, b10 = metrics(res[("BASELINE", "2000-01-03")][1]), metrics(res[("BASELINE", "2010-03-12")][1])
    bw = windows(res[("BASELINE", "2000-01-03")][1]); bh1, bh2 = sub(res[("BASELINE", "2000-01-03")][1], "2000", "2012"), sub(res[("BASELINE", "2000-01-03")][1], "2013", "2026")
    rows = []
    for name in ["BASELINE"] + [n for _, n, _, _ in IDEAS]:
        e0, e10 = res[(name, "2000-01-03")][1], res[(name, "2010-03-12")][1]; m0, m10 = metrics(e0), metrics(e10)
        w = windows(e0); wins = sum(w[y] > bw[y] for y in bw); h1, h2 = sub(e0, "2000", "2012"), sub(e0, "2013", "2026")
        better_risk = (m0["martin"] > b0["martin"] and m10["martin"] > b10["martin"] and m0["cagr"] >= b0["cagr"] - 1e-4 and m10["cagr"] >= b10["cagr"] - 1e-4 and wins >= 12)
        more_return = (m0["cagr"] - b0["cagr"] >= 0.01 and m10["cagr"] - b10["cagr"] >= 0.01 and m0["maxdd"] - b0["maxdd"] >= -0.03 and m10["maxdd"] - b10["maxdd"] >= -0.03)
        rows.append(dict(group=grp[name], idea=name, cagr=m0["cagr"], maxdd=m0["maxdd"], ulcer=m0["ulcer"], martin=m0["martin"], underwater=m0["underwater_days"],
                         cagr10=m10["cagr"], maxdd10=m10["maxdd"], martin10=m10["martin"], worst10y=min(w.values()), wins=wins, h1=h1["cagr"], h2=h2["cagr"],
                         trade_days=res[(name, "2000-01-03")][0]["trade_days_yr"], final=res[(name, "2000-01-03")][0]["final"],
                         verdict="Pass: better risk-adjusted" if better_risk and name != "BASELINE" else ("Pass: more return" if more_return and name != "BASELINE" else "")))
    df = pd.DataFrame(rows); df.to_csv(os.path.join(OUT, "round6.csv"), index=False)
    pd.set_option("display.width", 320); pd.set_option("display.max_rows", 100)
    show = df.copy()
    for c in ["cagr", "maxdd", "ulcer", "cagr10", "maxdd10", "worst10y", "h1", "h2"]: show[c] = (show[c] * 100).round(1)
    for c in ["martin", "martin10"]: show[c] = show[c].round(2)
    print(show[["group", "idea", "cagr", "maxdd", "ulcer", "martin", "underwater", "cagr10", "maxdd10", "martin10", "worst10y", "wins", "h1", "h2", "trade_days", "verdict"]].to_string(index=False))
