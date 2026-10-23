"""Research harness: run the PRODUCTION engine (twin_engine.step) day by day over the synthetic 1999-2026 panel.

run(overrides, ...) temporarily sets twin_engine.P values (and optional module attributes for idea hooks),
replays every trading day, and returns stats. Costs: slippage_bps per fill (default 5 bp = 0.05%, the stricter
setting used for the v1.3 numbers).
"""
import os, sys, math, json, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.dirname(HERE))
import twin_engine as te
import te_lab

PANEL = pd.read_pickle(os.path.join(HERE, "data", "panel.pkl"))
PANEL["VIXLVL"] = pd.read_pickle(os.path.join(HERE, "data", "adj.pkl"))["^VIX"].reindex(PANEL.index).ffill()   # signal only, not traded
_X = pd.read_pickle(os.path.join(HERE, "data", "extra.pkl")).reindex(PANEL.index)
_A = pd.read_pickle(os.path.join(HERE, "data", "adj.pkl")).reindex(PANEL.index)
for _c, _src in [("VIX3M", _X["^VIX3M"]), ("VVIX", _X["^VVIX"]), ("VWEHX", _X["VWEHX"]), ("VBMFX", _X["VBMFX"]), ("VFITX", _A["VFITX"]),
                 ("QQQ_H", _X["QQQ_H"]), ("QQQ_L", _X["QQQ_L"]), ("QQQ_C", _X["QQQ_C"])]:
    PANEL[_c] = _src.ffill() if not _c.startswith("QQQ_") else _src      # signals only, never traded
PANEL["RF"] = pd.read_pickle(os.path.join(HERE, "data", "rf.pkl")).reindex(PANEL.index).fillna(0.0)   # daily T-bill return (cash yield)

def add_signal_cols(px):
    """round 10 signal series (never traded)"""
    x3 = pd.read_pickle(os.path.join(HERE, "data", "extra3.pkl")).reindex(px.index)
    for c, src in [("DJT", "^DJT"), ("DJI", "^DJI"), ("HG", "HG=F"), ("GCF", "GC=F"), ("DXY", "DX-Y.NYB"), ("TNX", "^TNX"), ("IRXL", "^IRX")]: px[c] = x3[src].ffill(limit=5)
    for c, src in [("QQQ_V", "QQQ_V"), ("NDX_V", "^NDX_V"), ("NDX_H", "^NDX_H"), ("NDX_L", "^NDX_L"), ("NDX_C", "^NDX_C")]: px[c] = x3[src]
    return px
PANEL = add_signal_cols(PANEL)
WIN = 300                                     # history rows each step needs (210d SMA, 12m momentum, 63d cov)
_BASE_P = dict(te.P)

def stats(eq: pd.Series, trade_days=None):
    v = eq.values; yrs = (eq.index[-1] - eq.index[0]).days / 365.25
    dd = v / np.maximum.accumulate(v) - 1
    r = eq.pct_change().dropna()
    out = dict(cagr=(v[-1] / v[0]) ** (1 / yrs) - 1, maxdd=float(dd.min()), final=float(v[-1]),
               vol=float(r.std() * math.sqrt(252)), sharpe=float(r.mean() / r.std() * math.sqrt(252)) if r.std() > 0 else 0.0)
    out["mar"] = out["cagr"] / -out["maxdd"] if out["maxdd"] < 0 else float("nan")
    if trade_days is not None: out["trade_days_yr"] = trade_days / yrs
    return out

def run(overrides=None, start="2000-01-03", end=None, capital=20000.0, slippage_bps=5.0, panel=None, hooks=None, lab=True, lag=False):
    px = PANEL if panel is None else panel
    te.P.clear(); te.P.update(_BASE_P); te.P.update(dict(slippage_bps=slippage_bps, min_order=0.0, fractional=True))
    te_lab.LDS_MEM.clear(); te_lab.ENSF.clear()
    if overrides: te.P.update(overrides)
    saved = {}
    for k, v in (hooks or {}).items(): saved[k] = getattr(te, k, None); setattr(te, k, v)
    try:
        cols = [c for c in px.columns]
        A = px[cols]
        idx = A.index; i0 = idx.searchsorted(pd.Timestamp(start)); i1 = len(idx) if end is None else idx.searchsorted(pd.Timestamp(end), side="right")
        cal = te_lab.Calendar(idx[:i1]) if lab else te.Calendar(idx[:i1])
        stepf = te_lab.step if lab else te.step
        win = (overrides or {}).get("win", WIN)
        st = te.new_state(capital, idx[i0], 0.0)
        vals = A.values
        for i in range(i0, i1):
            d = idx[i]
            close = dict(zip(cols, vals[i]))
            if lag: close = dict(zip(cols, vals[i])); stepf(st, d, A.iloc[max(0, i - 1 - win):i], close, cal) if i > i0 else stepf(st, d, A.iloc[max(0, i - win):i + 1], close, cal)
            else: stepf(st, d, A.iloc[max(0, i - win):i + 1], close, cal)
        eq = pd.Series([e["value"] for e in st["equity"]], index=pd.to_datetime([e["date"] for e in st["equity"]]))
        tdays = len({t["date"] for t in st["trades"]})
        s = stats(eq, tdays); s["equity"] = eq; s["n_trades"] = len(st["trades"])
        s["expo"] = pd.DataFrame([e.get("x", {}) for e in st["equity"]], index=eq.index).fillna(0.0)
        s["trades"] = st["trades"]
        return s
    finally:
        for k, v in saved.items(): setattr(te, k, v)
        te.P.clear(); te.P.update(_BASE_P)

def fmt(s): return f"CAGR {s['cagr']*100:5.1f}%  maxDD {s['maxdd']*100:6.1f}%  final ${s['final']:,.0f}  trade days/yr {s.get('trade_days_yr', 0):.0f}"

if __name__ == "__main__":
    import time
    t = time.time(); s = run(); print("baseline v1.3 (80% vol target):", fmt(s), f"  [{time.time()-t:.0f}s]")
