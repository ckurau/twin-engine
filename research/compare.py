"""Twin Engine v1.6 vs well-known strategies on the same 1999-2026 panel (0.05% per trade, daily data).
Periods: 2000-2026 and 2010-2026 (real leveraged ETFs only)."""
import os, sys, math, pickle, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
PX = pd.read_pickle(os.path.join(HERE, "data", "panel.pkl")); RF = pd.read_pickle(os.path.join(HERE, "data", "rf.pkl"))
R = PX.pct_change(); COST = 0.0005

def rebal(weights_fn, start, freq="QE"):
    """portfolio of daily returns; weights from weights_fn(date) applied at each rebalance date (end of period), drift between"""
    idx = R.loc[start:].index; v = 1.0; w = None; out = []
    reb = set(pd.Series(idx, index=idx).resample(freq).last().dropna()) if freq else set()
    for i, d in enumerate(idx):
        if w is not None:
            r = R.loc[d, list(w.index)].fillna(0.0); g = (w * (1 + r)); v *= g.sum() if w.sum() > 0 else 1.0; w = g / g.sum() if g.sum() > 0 else w
        if w is None or d in reb:
            nw = pd.Series(weights_fn(d)); nw = nw[nw > 0]
            turn = (nw.reindex(set(nw.index) | set(w.index if w is not None else [])).fillna(0) - (w if w is not None else pd.Series(dtype=float)).reindex(set(nw.index) | set(w.index if w is not None else [])).fillna(0)).abs().sum()
            v *= 1 - turn * COST; w = nw / nw.sum() if nw.sum() > 0 else nw
        out.append(v)
    return pd.Series(out, index=idx)

def mom(t, d, months): s = PX[t].loc[:d].dropna(); k = 21 * months; return s.iloc[-1] / s.iloc[-1 - k] - 1 if len(s) > k else np.nan
def above(t, d, n=200): s = PX[t].loc[:d].dropna(); return s.iloc[-1] > s.iloc[-n:].mean()

STRATS = {
    "S&P 500 (SPY)": (lambda d: {"SPY": 1}, "QE"),
    "Nasdaq-100 (QQQ)": (lambda d: {"QQQ": 1}, "QE"),
    "60/40 (SPY/IEF)": (lambda d: {"SPY": .6, "IEF": .4}, "QE"),
    "TQQQ buy & hold": (lambda d: {"TQQQ": 1}, None),
    "UPRO buy & hold": (lambda d: {"UPRO": 1}, None),
    "HFEA (55% UPRO / 45% TMF)": (lambda d: {"UPRO": .55, "TMF": .45}, "QE"),
    "TQQQ when QQQ > 200-day avg, else T-bills": (lambda d: {"TQQQ": 1} if above("QQQ", d) else {"BIL": 1}, "W-FRI"),
    "Dual Momentum (Antonacci GEM)": (lambda d: ({"SPY": 1} if mom("SPY", d, 12) >= mom("EEM", d, 12) else {"EEM": 1}) if mom("SPY", d, 12) > mom("BIL", d, 12) else {"IEF": 1}, "ME"),
    "Faber trend (5 assets, 10-mo avg)": (lambda d: {t: .2 if above(t, d, 210) else 0 for t in ("SPY", "EEM", "IEF", "VNQ", "GLD")} | {"BIL": .2 * sum(not above(t, d, 210) for t in ("SPY", "EEM", "IEF", "VNQ", "GLD"))}, "ME"),
    "Golden Butterfly": (lambda d: {"SPY": .2, "IWM": .2, "TLT": .2, "SHY": .2, "GLD": .2}, "YE"),
}

def metrics(e):
    yrs = (e.index[-1] - e.index[0]).days / 365.25; c = (e.iloc[-1] / e.iloc[0]) ** (1 / yrs) - 1
    dd = e / e.cummax() - 1; r = e.pct_change().dropna(); rf = RF.reindex(r.index).fillna(0)
    ulcer = float(np.sqrt((dd ** 2).mean()))
    return dict(cagr=c, maxdd=float(dd.min()), sharpe=float((r - rf).mean() / r.std() * math.sqrt(252)), martin=c / ulcer, final=20000 * e.iloc[-1] / e.iloc[0])

if __name__ == "__main__":
    import bt
    from round4 import V15
    rows = []
    for start, lab in (("2000-01-03", "2000-26"), ("2010-03-12", "2010-26")):
        te_eq = bt.run({**V15, "lds_assets": ("SPY", "TLT", "GLD")}, start=start)["equity"]
        nine = bt.run({**V15, "lds_assets": ("SPY", "TLT", "GLD"), "split_9sig": 1.0, "vol_target": 99.0, "tom_after": 0, "tom_before": 0, "nine_dip": None, "fomc_swap": False}, start=start)["equity"]
        res = {"Twin Engine v1.6": te_eq, "Plain 9Sig (TQQQ + bonds/gold, no switches)": nine}
        for n, (fn, fq) in STRATS.items():
            s0 = "2003-06-01" if ("Dual" in n or "Faber" in n) and start < "2003" else start
            res[n] = rebal(fn, s0, fq)
        for n, e in res.items(): rows.append(dict(period=lab, strategy=n, **metrics(e)))
        print("done", lab)
    df = pd.DataFrame(rows); df.to_csv(os.path.join(HERE, "out", "compare.csv"), index=False)
    for lab in ("2000-26", "2010-26"):
        x = df[df.period == lab].sort_values("martin", ascending=False)
        print(f"\n{lab}: strategy | CAGR | max DD | Sharpe | Martin | $20k became")
        for _, r in x.iterrows(): print(f"  {r.strategy:45s} {r.cagr*100:6.1f}% {r.maxdd*100:7.1f}% {r.sharpe:6.2f} {r.martin:6.2f}  ${r.final:,.0f}")
