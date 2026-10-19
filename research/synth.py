"""Build a daily total-return price panel back to 1999 for every ticker the engine (and the research ideas) can trade.

Underlyings use the ETF where it exists and a long-history proxy before that:
  QQQ <- ^NDX (+0.6%/yr dividends)   SPY <- ^GSPC (+1.5%/yr)   TLT <- VUSTX   IEF <- VFITX   SHY/BIL <- VFISX / T-bill
  GLD <- GC=F, and before Aug 2000 ^XAU (gold miners) scaled to gold's volatility (rough, ~18 months only)
Leveraged / inverse ETFs before inception: L x underlying daily return - (L-1) x T-bill - fee, plus a drag
calibrated so the synthetic series matches the real ETF's CAGR over their overlap. Real ETF returns are used after inception.
"""
import os, numpy as np, pandas as pd

D = os.path.join(os.path.dirname(__file__), "data")
START = "1998-06-01"

def _ret(s): return s.pct_change()

def splice(primary, proxy, scale=1.0, add=0.0):
    """daily returns: proxy (scaled, + daily drift `add`) before primary starts, primary after"""
    p, q = _ret(primary.dropna()), _ret(proxy.dropna()) * scale + add / 252
    first = primary.first_valid_index()
    out = pd.concat([q[q.index < first], p[p.index >= first].iloc[1:]])
    return out[~out.index.duplicated()].sort_index()

def build(verbose=True):
    adj = pd.read_pickle(os.path.join(D, "adj.pkl")).loc[START:]
    days = adj["^GSPC"].dropna().index
    adj = adj.reindex(days)
    rf = (adj["^IRX"].ffill() / 100 / 252).fillna(0.0)                     # daily T-bill
    R = {}
    R["QQQ"] = splice(adj["QQQ"], adj["^NDX"], add=0.006)
    R["SPY"] = splice(adj["SPY"], adj["^GSPC"], add=0.015)
    R["TLT"] = splice(adj["TLT"], adj["VUSTX"])
    R["IEF"] = splice(adj["IEF"], adj["VFITX"])
    R["SHY"] = splice(adj["SHY"], adj["VFISX"])
    R["BIL"] = splice(adj["BIL"], rf.cumsum().add(1.0))
    gold = adj["GC=F"].dropna()
    xr, gr = _ret(adj["^XAU"]), _ret(gold)
    k = float(gr.loc["2000-09":"2004-12"].std() / xr.loc["2000-09":"2004-12"].std())   # vol-match miners to gold
    g = pd.concat([xr[xr.index <= gold.index[0]] * k, gr[gr.index > gold.index[0]]])
    g = g[~g.index.duplicated()]
    R["GLD"] = splice(adj["GLD"], (1 + g.fillna(0)).cumprod())
    # extra underlyings for idea tests
    R["EFA"] = _ret(adj["EFA"])
    R["EEM"] = splice(adj["EEM"], adj["VEIEX"])
    R["XLK"] = _ret(adj["XLK"]); R["SOXX"] = splice(adj["SOXX"], adj["^SOX"]); R["XLU"] = _ret(adj["XLU"])
    R["IWM"] = splice(adj["IWM"], adj["^RUT"], add=0.012); R["VNQ"] = splice(adj["VNQ"], adj["VGSIX"])
    R["XLE"] = _ret(adj["XLE"]); R["XLV"] = _ret(adj["XLV"]); R["XLF"] = _ret(adj["XLF"]); R["DBC"] = _ret(adj["DBC"])
    R = pd.DataFrame(R).reindex(days)

    # leveraged / inverse ETFs: (ticker, underlying, L, fee)
    LEV = [("TQQQ", "QQQ", 3, .0086), ("QLD", "QQQ", 2, .0095), ("SQQQ", "QQQ", -3, .0095), ("QID", "QQQ", -2, .0095), ("PSQ", "QQQ", -1, .0095),
           ("UPRO", "SPY", 3, .0091), ("SSO", "SPY", 2, .0089), ("SPXU", "SPY", -3, .0090), ("SDS", "SPY", -2, .0090), ("SH", "SPY", -1, .0089),
           ("TMF", "TLT", 3, .0106), ("UBT", "TLT", 2, .0095), ("TMV", "TLT", -3, .0095), ("TBT", "TLT", -2, .0090), ("TBF", "TLT", -1, .0092),
           ("UGL", "GLD", 2, .0095), ("GLL", "GLD", -2, .0095), ("TYD", "IEF", 3, .0109), ("TECL", "XLK", 3, .0094), ("SOXL", "SOXX", 3, .0076),
           ("EDC", "EEM", 3, .0110), ("UTSL", "XLU", 3, .0095), ("TNA", "IWM", 3, .0110)]
    real = pd.read_pickle(os.path.join(D, "adj.pkl")).reindex(days)
    calib = []
    for tk, u, L, fee in LEV:
        # long: borrow (L-1) at the T-bill rate; inverse: collateral earns the T-bill rate
        model = L * R[u] - (L - 1) * rf - fee / 252 if L > 0 else L * R[u] + (1 - L) * rf - fee / 252
        act = _ret(real[tk].dropna()) if tk in real else None
        drag = 0.0
        if act is not None and len(act) > 500:
            ix = act.index.intersection(model.dropna().index)[1:]
            a, m = act.loc[ix], model.loc[ix]
            yrs = len(ix) / 252
            ca, cm = np.prod(1 + a) ** (1 / yrs) - 1, np.prod(1 + m) ** (1 / yrs) - 1
            drag = np.log1p(cm) - np.log1p(ca)                                   # annual log drag to remove
            calib.append((tk, ix[0].date(), round(ca * 100, 2), round(cm * 100, 2), round(float(np.corrcoef(a, m)[0, 1]), 4)))
            model = model - drag / 252
            first = real[tk].first_valid_index()
            s = pd.concat([model[model.index <= first], act[act.index > first]])
        else:
            s = model
        R[tk] = s.reindex(days)
    if verbose:
        print("calibration vs real ETF (overlap):  ticker  since  real CAGR  model CAGR(before drag fix)  corr")
        for c in calib: print("  ", c)
        print(f"gold proxy before {gold.index[0].date()}: ^XAU x {k:.2f}")
    R = R.loc[R["QQQ"].first_valid_index():]
    px = (1 + R.fillna(0.0)).cumprod() * 100.0
    # mask series before their underlying has data (e.g. EFA 2001, XLK 1998-12)
    for c in px.columns:
        fv = R[c].first_valid_index(); px.loc[:fv, c] = np.nan
    return px, rf.reindex(px.index)

if __name__ == "__main__":
    px, rf = build()
    px.to_pickle(os.path.join(D, "panel.pkl")); rf.to_pickle(os.path.join(D, "rf.pkl"))
    print(px.shape, px.index[0].date(), px.index[-1].date())
    print(px[["QQQ", "SPY", "TLT", "GLD", "TQQQ", "UPRO", "TMF", "UGL"]].apply(lambda s: s.first_valid_index().date()))
