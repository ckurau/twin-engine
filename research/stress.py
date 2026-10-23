"""Synthetic stress panels: change the underlying returns and re-derive every leveraged/inverse ETF from the change
(r_lev' = r_lev + L * (r_u' - r_u)), so ETF calibration and daily-reset decay are kept."""
import numpy as np, pandas as pd
LEV = {"TQQQ": ("QQQ", 3), "QLD": ("QQQ", 2), "SQQQ": ("QQQ", -3), "QID": ("QQQ", -2), "PSQ": ("QQQ", -1), "UPRO": ("SPY", 3), "SSO": ("SPY", 2),
       "SPXU": ("SPY", -3), "SDS": ("SPY", -2), "SH": ("SPY", -1), "TMF": ("TLT", 3), "UBT": ("TLT", 2), "TMV": ("TLT", -3), "TBT": ("TLT", -2),
       "TBF": ("TLT", -1), "UGL": ("GLD", 2), "GLL": ("GLD", -2), "TYD": ("IEF", 3), "TECL": ("XLK", 3), "SOXL": ("SOXX", 3), "EDC": ("EEM", 3),
       "UTSL": ("XLU", 3), "TNA": ("IWM", 3), "UDOW": ("DIA", 3), "FAS": ("XLF", 3), "ERX": ("XLE", 3), "CURE": ("XLV", 3)}
TECH = ["QQQ", "XLK", "SOXX"]
STOCKS = TECH + ["SPY", "IWM", "DIA", "EFA", "EEM", "XLU", "XLE", "XLV", "XLF", "VNQ"]
BONDS = ["TLT", "IEF"]

def _apply(px, newr):
    """newr: dict underlying -> new daily simple returns; returns modified price panel"""
    out = px.copy(); R = px.pct_change()
    for u, r2 in newr.items():
        d = (r2 - R[u]).fillna(0.0)
        out[u] = _rebuild(px[u], r2)
        for t, (uu, L) in LEV.items():
            if uu == u and t in px: out[t] = _rebuild(px[t], (R[t] + L * d).clip(lower=-0.99))
        if u == "QQQ":
            k = out["QQQ"] / px["QQQ"]
            for c in ("QQQ_H", "QQQ_L", "QQQ_C"): out[c] = px[c] * k.reindex(px.index)
    return out

def _rebuild(p0, r):
    fv = p0.first_valid_index(); r = r.copy(); r[r.index <= fv] = 0.0
    s = p0.loc[fv] * (1 + r.fillna(0.0)).cumprod(); s[s.index < fv] = np.nan; return s

def drift(px, cols, ann, since="2000-01-03"):
    """shift daily log returns so each column's log growth since `since` is `ann` per year"""
    R = px.pct_change(); new = {}
    for c in cols:
        if c not in px: continue
        lr = np.log1p(R[c]); m = lr.loc[since:].mean(); new[c] = np.expm1(lr - m + np.log1p(ann) / 252)
    return _apply(px, new)

def scale_vol(px, cols, k):
    R = px.pct_change(); new = {}
    for c in cols:
        if c not in px: continue
        m = R[c].mean(); new[c] = (R[c] - m) * k + m
    return _apply(px, new)

def crash_days(px, dates=("2000-03-27", "2007-10-10", "2021-11-22")):
    R = px.pct_change(); shock = dict(QQQ=-0.25, XLK=-0.25, SOXX=-0.30, SPY=-0.20, DIA=-0.20, IWM=-0.22, EFA=-0.15, EEM=-0.15, TLT=0.05, IEF=0.03, GLD=0.0)
    new = {}
    for u, sh in shock.items():
        if u not in px: continue
        r = R[u].copy()
        for d in dates:
            ix = px.index[px.index.searchsorted(pd.Timestamp(d))]; r.loc[ix] = (1 + r.loc[ix]) * (1 + sh) - 1
        new[u] = r
    return _apply(px, new)

def financing(px, extra=0.02):
    out = px.copy(); R = px.pct_change()
    for t in LEV:
        if t in px: out[t] = _rebuild(px[t], R[t] - extra / 252)
    return out

def make(kind, px):
    if kind == "lost_tech": return drift(px, TECH, 0.0)
    if kind == "flat_stocks": return drift(px, STOCKS, 0.0)
    if kind == "bond_bear": return drift(px, BONDS, -0.03)
    if kind == "stagflation": return drift(drift(px, STOCKS, -0.02), BONDS, -0.03)
    if kind == "crash_days": return crash_days(px)
    if kind == "financing": return financing(px, 0.02)
    if kind == "high_vol": return scale_vol(px, STOCKS, 1.3)
    raise ValueError(kind)
