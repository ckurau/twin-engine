"""Crash insurance study (vs v1.5 and v1.5 with LDS = SPY/TLT/GLD):
 1. Nasdaq concentration: average exposure to each index, as a multiple of the account.
 2. 1987-style day stress test: apply a one-day shock to the exposures held on every day 2000-2026.
 3. Hedge overlays: VIXY sleeve (2011+), Cambria TAIL sleeve (2017+), QQQ puts bought monthly (always / only when VIX < 15).
Overlays sit beside the strategy (rebalanced monthly / premium paid from the account); put prices are Black-Scholes
on VIX x 1.25 + 5 vol points of skew, so they are estimates, not quotes."""
import os, sys, math, pickle, multiprocessing as mp
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, "out")
from round4 import V15
SHOCK = dict(SPY=-0.205, QQQ=-0.20, IWM=-0.20, EEM=-0.15, SOXX=-0.25, XLK=-0.20, XLU=-0.15, TLT=0.02, IEF=0.01, GLD=0.0, BIL=0.0, SHY=0.0)
CONFIGS = {"v1.5": V15, "v1.5, LDS without QQQ": {**V15, "lds_assets": ("SPY", "TLT", "GLD")}}

def _run(args):
    name, ov = args
    import bt
    s = bt.run(ov); return name, s["equity"], s["expo"]

def stats(eq):
    yrs = (eq.index[-1] - eq.index[0]).days / 365.25
    return (eq.iloc[-1] / eq.iloc[0]) ** (1 / yrs) - 1, float((eq / eq.cummax() - 1).min())

def sleeve(eq, asset, x):
    """strategy + x in `asset`, rebalanced to x at each month end"""
    r = pd.concat([eq.pct_change(), asset.pct_change()], axis=1).dropna(); r.columns = ["s", "h"]
    v_s, v_h, out = 1 - x, x, []
    for d, (rs, rh) in r.iterrows():
        v_s *= 1 + rs; v_h *= 1 + rh; out.append(v_s + v_h)
        if d.is_month_end or (d + pd.offsets.BDay(1)).month != d.month: t = v_s + v_h; v_s, v_h = t * (1 - x), t * x
    return pd.Series(out, index=r.index)

def bs_put(S, K, T, r, sig):
    from math import log, sqrt, exp, erf
    N = lambda z: 0.5 * (1 + erf(z / sqrt(2)))
    d1 = (log(S / K) + (r + sig * sig / 2) * T) / (sig * sqrt(T)); d2 = d1 - sig * sqrt(T)
    return K * exp(-r * T) * N(-d2) - S * N(-d1)

def puts(eq, qqq, vix, rf, budget_yr, otm=0.10, cheap=None):
    """buy 1-month QQQ puts at each month start (budget_yr/12 of the account; if `cheap`, only when VIX < cheap
    and then spend 3 months' budget); payoff at expiry. Returns hedged equity and the live put notional (x account)."""
    idx = eq.index; v = 1.0; out = []; notional = pd.Series(0.0, index=idx); pos = None
    rs = eq.pct_change().fillna(0.0)
    for i, d in enumerate(idx):
        v *= 1 + rs.iloc[i]
        if pos and d >= pos["exp"]:
            v += pos["n"] * max(pos["K"] - qqq.loc[d], 0.0); pos = None
        first = i == 0 or idx[i - 1].month != d.month
        if first and pos is None and vix.loc[d] == vix.loc[d]:
            spend = budget_yr / 12
            if cheap is not None: spend = budget_yr / 4 if vix.loc[d] < cheap else 0.0
            if spend > 0:
                S = qqq.loc[d]; K = S * (1 - otm); sig = vix.loc[d] / 100 * 1.25 + 0.05
                prem = bs_put(S, K, 21 / 252, rf.loc[d] * 252, sig)
                n = spend * v / prem; v -= spend * v
                pos = dict(n=n, K=K, exp=idx[min(i + 21, len(idx) - 1)])
        if pos: notional.iloc[i] = pos["n"] * qqq.loc[d] / v
        out.append(v)
    return pd.Series(out, index=idx), notional

if __name__ == "__main__":
    with mp.Pool(2) as pool: runs = {n: (e, x) for n, e, x in pool.map(_run, CONFIGS.items())}
    px = pd.read_pickle(os.path.join(HERE, "data", "panel.pkl")); ex = pd.read_pickle(os.path.join(HERE, "data", "extra.pkl"))
    adj = pd.read_pickle(os.path.join(HERE, "data", "adj.pkl")); rf = pd.read_pickle(os.path.join(HERE, "data", "rf.pkl"))
    lines = []
    pickle.dump(runs, open(os.path.join(OUT, "insurance_runs.pkl"), "wb"))
    for name, (eq, xp) in runs.items():
        xp = xp.reindex(columns=sorted(set(xp.columns) | set(SHOCK))).fillna(0.0)
        c, dd = stats(eq)
        lines.append(f"\n=== {name}: {c*100:.1f}% CAGR, {dd*100:.1f}% max DD")
        avg = xp.mean().sort_values(ascending=False)
        lines.append("average exposure (x account): " + ", ".join(f"{a} {v:.2f}" for a, v in avg.items() if abs(v) > 0.01))
        q = xp["QQQ"]; lines.append(f"Nasdaq exposure > 2x the account on {(q > 2).mean():.0%} of days; share of total stock exposure from Nasdaq: {(q.sum() / sum(xp[a].sum() for a in ('SPY','QQQ','IWM','EEM','SOXX','XLK','XLU'))):.0%}")
        loss = sum(xp[a] * s for a, s in SHOCK.items()).clip(lower=-1.0)
        lines.append(f"1987-style day (S&P -20.5%, Nasdaq -20%, semis -25%, TLT +2%): median loss {loss.median()*100:.0f}%, 90th pct {loss.quantile(0.10)*100:.0f}%, worst {loss.min()*100:.0f}%")
        # hedges
        for lab, a, x, start in [("VIXY 3%", ex["VIXY"], 0.03, "2011-01-04"), ("VIXY 5%", ex["VIXY"], 0.05, "2011-01-04"),
                                 ("TAIL 10%", ex["TAIL"], 0.10, "2017-04-06"), ("TAIL 20%", ex["TAIL"], 0.20, "2017-04-06")]:
            e0 = eq.loc[start:]; h = sleeve(e0, a.reindex(e0.index).ffill(), x); c0, d0 = stats(e0); c1, d1 = stats(h)
            lines.append(f"  {lab:9s} since {start[:4]}: {c0*100:.1f}% / {d0*100:.1f}%  ->  {c1*100:.1f}% / {d1*100:.1f}%")
        qqq = px["QQQ"].reindex(eq.index); vix = adj["^VIX"].reindex(eq.index).ffill(); r = rf.reindex(eq.index).ffill()
        for lab, b, cheap in [("QQQ puts 1%/yr, always", 0.01, None), ("QQQ puts 2%/yr, always", 0.02, None), ("QQQ puts 1%/yr, only when VIX<15", 0.01, 15), ("QQQ puts 2%/yr, only when VIX<15", 0.02, 15)]:
            h, notl = puts(eq, qqq, vix, r, b, cheap=cheap); c1, d1 = stats(h)
            # stress with puts: intrinsic value of live puts after a -20% Nasdaq day (strike 10% below purchase price; ignores time value)
            prot = (notl * np.maximum(0, 0.9 - 0.8) / 1.0).reindex(loss.index).fillna(0)   # approx: puts bought near spot
            l2 = loss + prot
            lines.append(f"  {lab:34s}: {c1*100:.1f}% / {d1*100:.1f}%   1987-day median loss {l2.median()*100:.0f}% (vs {loss.median()*100:.0f}%), puts held {(notl > 0).mean():.0%} of days")
    txt = "\n".join(lines); print(txt); open(os.path.join(OUT, "insurance.txt"), "w").write(txt)
    pickle.dump(runs, open(os.path.join(OUT, "insurance_runs.pkl"), "wb"))
