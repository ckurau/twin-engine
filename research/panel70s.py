"""1970s-80s panel (stagflation test, 1971-1991). Approximations, all built from public index data:
  QQQ <- Nasdaq Composite (^IXIC) + 1%/yr dividends     SPY <- S&P 500 (^GSPC) + 3.5%/yr dividends
  TLT <- 20-year par bond priced from yields (^TYX from 1977, ^TNX + 0.15 before)   IEF <- 8-year bond from ^TNX
  BIL / RF <- 3-month T-bill (^IRX)   GLD <- monthly gold price (datasets/gold-prices) filled daily with a Brownian bridge
  scaled to the month's volatility (random but seeded; gold was not legal for US citizens to own before 1975)
  Leveraged / inverse ETFs: L x underlying - (L-1) x T-bill - 1.45%/yr (fee + typical swap drag)."""
import os, sys, io, numpy as np, pandas as pd, requests
HERE = os.path.dirname(os.path.abspath(__file__)); D = os.path.join(HERE, "data")
CA = os.environ.get("CURL_CA_BUNDLE")

def bond_returns(y, n):
    """daily total return of an n-year par bond from a yield series in percent"""
    y = y.ffill() / 100; dy = y.diff().fillna(0.0); yp = y.shift(1).fillna(y.iloc[0])
    D_ = (1 - (1 + yp / 2) ** (-2 * n)) / yp; C = D_ ** 2 * 0.9
    return yp / 252 - D_ * dy + 0.5 * C * dy ** 2

def gold_daily(days, seed=7):
    g = pd.read_csv(io.StringIO(requests.get("https://raw.githubusercontent.com/datasets/gold-prices/main/data/monthly.csv", timeout=60, verify=CA or True).text))
    g["Date"] = pd.to_datetime(g["Date"]) + pd.offsets.MonthEnd(0); g = g.set_index("Date")["Price"].astype(float)
    g = g[(g.index >= days[0] - pd.offsets.MonthEnd(2)) & (g.index <= days[-1] + pd.offsets.MonthEnd(1))]
    lr = np.log(g).diff(); vol_m = lr.rolling(12, min_periods=3).std().bfill()
    rng = np.random.default_rng(seed); out = pd.Series(np.nan, index=days)
    anchors = [(d, v) for d, v in g.items()]
    for (d0, v0), (d1, v1) in zip(anchors[:-1], anchors[1:]):
        seg = days[(days > d0) & (days <= d1)]
        if not len(seg): continue
        n = len(seg); sd = float(vol_m.loc[d1]) / np.sqrt(21)
        w = np.cumsum(rng.normal(0, sd, n)); w = w - np.arange(1, n + 1) / n * w[-1]          # bridge: ends at 0
        path = np.log(v0) + np.arange(1, n + 1) / n * (np.log(v1) - np.log(v0)) + w
        out.loc[seg] = np.exp(path)
    return out.ffill().bfill()

def build(seed=7):
    import yfinance as yf
    raw = {t: yf.download(t, start="1970-01-01", end="1992-01-01", progress=False, auto_adjust=False)["Close"].squeeze() for t in ["^IXIC", "^GSPC", "^TNX", "^IRX", "^TYX"]}
    days = raw["^GSPC"].loc["1971-02-05":].index
    for k in raw: raw[k] = raw[k].reindex(days).ffill()
    rf = (raw["^IRX"] / 100 / 252).fillna(0.0)
    R = pd.DataFrame(index=days)
    R["QQQ"] = raw["^IXIC"].pct_change() + 0.01 / 252
    R["SPY"] = raw["^GSPC"].pct_change() + 0.035 / 252
    long_y = raw["^TYX"].combine_first(raw["^TNX"] + 0.15)
    R["TLT"] = bond_returns(long_y, 20); R["IEF"] = bond_returns(raw["^TNX"], 8)
    R["BIL"] = rf; R["SHY"] = rf + 0.003 / 252
    R["GLD"] = gold_daily(days, seed).pct_change()
    LEV = [("TQQQ", "QQQ", 3), ("QLD", "QQQ", 2), ("SQQQ", "QQQ", -3), ("QID", "QQQ", -2), ("PSQ", "QQQ", -1), ("UPRO", "SPY", 3), ("SSO", "SPY", 2),
           ("SPXU", "SPY", -3), ("SDS", "SPY", -2), ("SH", "SPY", -1), ("TMF", "TLT", 3), ("UBT", "TLT", 2), ("TMV", "TLT", -3), ("TBT", "TLT", -2),
           ("TBF", "TLT", -1), ("UGL", "GLD", 2), ("GLL", "GLD", -2), ("TYD", "IEF", 3)]
    for tk, u, L in LEV:
        R[tk] = (L * R[u] - (L - 1) * rf if L > 0 else L * R[u] + (1 - L) * rf) - 0.0145 / 252
    px = (1 + R.fillna(0.0)).cumprod() * 100.0
    px["RF"] = rf
    # signal columns the lab can read
    px["TNX"] = raw["^TNX"]; px["IRXL"] = raw["^IRX"]; px["QQQ_C"] = px["QQQ"]; px["QQQ_H"] = px["QQQ"]; px["QQQ_L"] = px["QQQ"]
    return px

if __name__ == "__main__":
    px = build(); px.to_pickle(os.path.join(D, "panel_70s.pkl")); print(px.shape, px.index[0].date(), px.index[-1].date())
    # check bond model against VUSTX where both exist
    L = pd.read_pickle(os.path.join(D, "panel_long.pkl"))
    a = L["TLT"].loc["1986-06-05":"1991-12-31"].pct_change().dropna(); m = px["TLT"].loc["1986-06-05":"1991-12-31"].pct_change().dropna()
    ix = a.index.intersection(m.index); a, m = a.loc[ix], m.loc[ix]
    print("TLT model vs VUSTX 1986-91: CAGR %.1f%% vs %.1f%%, corr %.3f, vol %.1f%% vs %.1f%%" % ((np.prod(1 + m) ** (252 / len(m)) - 1) * 100, (np.prod(1 + a) ** (252 / len(a)) - 1) * 100,
          np.corrcoef(a, m)[0, 1], m.std() * 1587, a.std() * 1587))
    c = lambda s, a_, b_: (s.loc[b_] / s.loc[a_]) ** (1 / ((pd.Timestamp(b_) - pd.Timestamp(a_)).days / 365.25)) - 1
    for t in ["QQQ", "SPY", "TLT", "GLD", "BIL", "TQQQ", "UPRO", "TMF"]:
        s = px[t]; print(f"{t:5s} 1972-82 {c(s, s.index[s.index.searchsorted(pd.Timestamp('1972-01-03'))], s.index[s.index.searchsorted(pd.Timestamp('1982-08-12'))])*100:6.1f}%/yr")
