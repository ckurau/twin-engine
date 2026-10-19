"""Round 4 (vs v1.5): Nasdaq concentration, crash-warning signals, dip-rule variants. Same acceptance rules as rounds 1-3.
Ideas checked against Idea Labs I-III so nothing is repeated. Signals that need VIX3M/VVIX run from mid-2007 with their own baseline."""
import os, sys, time, pickle, multiprocessing as mp
import pandas as pd
from ideas import _one, evaluate, OUT

V15 = dict(swap_asset=(("SOXL", 1.0),), lds_freq="month", nine_dip=20)   # v1.5 rules in the lab
LMAX_Q2 = dict(LMAX_LONG=dict(SPY=3, QQQ=2, TLT=3, GLD=2))
IDEAS_00 = [  # (group, name, overrides, hooks)
    ("Nasdaq", "LDS without QQQ (SPY, TLT, GLD only)", dict(lds_assets=("SPY", "TLT", "GLD")), None),
    ("Nasdaq", "LDS: Nasdaq leg capped at 2x (QLD)", {}, LMAX_Q2),
    ("Nasdaq", "Account-wide cap: TQQQ <= 40% of account", dict(ndx_cap=0.40), None),
    ("Nasdaq", "Account-wide cap: TQQQ <= 50% of account", dict(ndx_cap=0.50), None),
    ("Nasdaq", "Account-wide cap: TQQQ <= 60% of account", dict(ndx_cap=0.60), None),
    ("Nasdaq", "9Sig growth: TQQQ or UPRO by 3-mo momentum", dict(growth_rot=(("TQQQ", "UPRO"), 3, "mom")), None),
    ("Nasdaq", "9Sig growth: TQQQ or UPRO by 6-mo momentum", dict(growth_rot=(("TQQQ", "UPRO"), 6, "mom")), None),
    ("Nasdaq", "9Sig growth: TQQQ or UPRO by 12-mo momentum", dict(growth_rot=(("TQQQ", "UPRO"), 12, "mom")), None),
    ("Nasdaq", "9Sig growth: TQQQ/UPRO by QQQ:SPY ratio vs 200d", dict(growth_rot=(("TQQQ", "UPRO"), 0, "ratio200")), None),
    ("Nasdaq", "9Sig growth: best of TQQQ/UPRO/TNA, 6-mo", dict(growth_rot=(("TQQQ", "UPRO", "TNA"), 6, "mom")), None),
    ("Crash signal", "Keller canary (EM + bonds momentum) -> 9Sig TQQQ 0", dict(nine_cap=("canary", 0.0)), None),
    ("Crash signal", "Keller canary -> 9Sig TQQQ max 50%", dict(nine_cap=("canary", 0.5)), None),
    ("Crash signal", "Keller canary -> 9Sig 0 + LDS 1x", dict(nine_cap=("canary", 0.0), lds_riskoff=True), None),
    ("Crash signal", "Credit stress (junk/Treasury < 50d) -> 9Sig max 50%", dict(nine_cap=("credit", 0.5, 50)), None),
    ("Crash signal", "Credit stress (< 50d) -> 9Sig TQQQ 0", dict(nine_cap=("credit", 0.0, 50)), None),
    ("Crash signal", "Credit stress (< 200d) -> 9Sig TQQQ 0", dict(nine_cap=("credit", 0.0, 200)), None),
    ("Crash signal", "Credit stress (< 50d) -> 9Sig 0 + LDS 1x", dict(nine_cap=("credit", 0.0, 50), lds_riskoff=True), None),
    ("Crash signal", "VIX spike (+25% vs 10d avg) -> 9Sig max 50% for 5 days", dict(nine_cap=("vixspike", 0.5, 1.25)), None),
    ("Crash signal", "VIX spike (+50% vs 10d avg) -> 9Sig 0 for 5 days", dict(nine_cap=("vixspike", 0.0, 1.5)), None),
    ("Crash signal", "VIX spike (+25%) -> 9Sig 0 + LDS 1x for 5 days", dict(nine_cap=("vixspike", 0.0, 1.25), lds_riskoff=True), None),
    ("Dip rule", "Dip boost on IBS < 0.2 instead of RSI2", dict(dip_kind="ibs"), None),
    ("Dip rule", "Dip boost on RSI2 < 20 or IBS < 0.2", dict(dip_kind="rsi2ibs"), None),
    ("Dip rule", "Dip boost on Connors VIX stretch instead of RSI2", dict(dip_kind="vixstretch"), None),
    ("Dip rule", "Dip boost on RSI2 or VIX stretch", dict(dip_kind="rsi2vixstretch"), None),
]
IDEAS_07 = [
    ("Crash signal", "VIX term structure inverted (VIX > VIX3M) -> 9Sig TQQQ 0", dict(nine_cap=("ts", 0.0, 1.0)), None),
    ("Crash signal", "VIX term structure inverted -> 9Sig max 50%", dict(nine_cap=("ts", 0.5, 1.0)), None),
    ("Crash signal", "VIX > 1.05 x VIX3M -> 9Sig TQQQ 0", dict(nine_cap=("ts", 0.0, 1.05)), None),
    ("Crash signal", "VIX term structure inverted -> 9Sig 0 + LDS 1x", dict(nine_cap=("ts", 0.0, 1.0), lds_riskoff=True), None),
    ("Crash signal", "VVIX > 110 -> 9Sig max 50%", dict(nine_cap=("vvix", 0.5, 110)), None),
    ("Crash signal", "VVIX > 120 -> 9Sig max 50%", dict(nine_cap=("vvix", 0.5, 120)), None),
    ("Crash signal", "VVIX > 130 -> 9Sig TQQQ 0", dict(nine_cap=("vvix", 0.0, 130)), None),
]

def batch(ideas, tag, start):
    jobs = [("BASELINE", V15, dict(start=start))] + [(n, {**V15, **ov}, dict(start=start, **({"hooks": h} if h else {}))) for _, n, ov, h in ideas]
    grp = {"BASELINE": "Base"}; grp.update({n: g for g, n, _, _ in ideas})
    res = {}; t = time.time()
    with mp.Pool(15) as pool:
        for i, (name, s, eq) in enumerate(pool.imap_unordered(_one, jobs), 1):
            res[name] = (s, eq, grp[name]); print(f"[{tag} {i}/{len(jobs)} {time.time()-t:4.0f}s] {name:58s} CAGR {s['cagr']*100:5.1f}%  DD {s['maxdd']*100:6.1f}%", flush=True)
    pickle.dump(res, open(os.path.join(OUT, f"{tag}.pkl"), "wb"))
    df = evaluate(res); df["start"] = start[:4]; df.to_csv(os.path.join(OUT, f"{tag}.csv"), index=False)
    return df

if __name__ == "__main__":
    a = batch(IDEAS_00, "round4a", "2000-01-03"); b = batch(IDEAS_07, "round4b", "2007-07-02")
    df = pd.concat([a, b]); pd.set_option("display.width", 260); pd.set_option("display.max_rows", 200)
    show = df.assign(**{k: (df[k] * 100).round(1) for k in ["cagr", "maxdd", "cagr07", "maxdd07", "h1", "h2", "d_cagr", "d_dd", "d_dd07"]})
    print(show[["start", "group", "idea", "cagr", "maxdd", "maxdd07", "d_cagr", "d_dd", "d_dd07", "wins", "nwin", "h1", "h2", "trade_days", "passed"]].to_string(index=False))
