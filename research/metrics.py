"""Trading metrics for an equity curve (+ its trade list) vs SPY. Used by backtest_export.py for the dashboard."""
import math, numpy as np, pandas as pd

def _cagr(e): return (e.iloc[-1] / e.iloc[0]) ** (365.25 / (e.index[-1] - e.index[0]).days) - 1

def compute(eq, spy, rf_daily, trades, cost_drag_per_5bp=None):
    eq = eq.dropna(); spy = spy.reindex(eq.index).ffill(); rf = rf_daily.reindex(eq.index).fillna(0.0)
    r = eq.pct_change().dropna(); rs = spy.pct_change().reindex(r.index).fillna(0); rfx = rf.reindex(r.index)
    ex = r - rfx; yrs = (eq.index[-1] - eq.index[0]).days / 365.25
    c = _cagr(eq); vol = r.std() * math.sqrt(252); down = r[r < 0].std() * math.sqrt(252)
    dd = eq / eq.cummax() - 1; mdd = float(dd.min()); ulcer = float(np.sqrt((dd ** 2).mean()))
    under = (dd < 0).astype(int); runs = under.groupby((under != under.shift()).cumsum()).sum()
    longest = int(runs.max()); avg_dd = float(dd[dd < 0].mean())
    m = eq.resample("ME").last().pct_change().dropna(); ms = spy.resample("ME").last().pct_change().reindex(m.index)
    y = pd.concat([pd.Series({eq.index[0]: eq.iloc[0]}), eq.resample("YE").last()]).pct_change().dropna()
    beta = float(np.cov(r, rs)[0, 1] / rs.var()); corr = float(np.corrcoef(r, rs)[0, 1])
    alpha = (r.mean() - rfx.mean() - beta * (rs.mean() - rfx.mean())) * 252
    up, dn = ms > 0, ms < 0
    upcap = (1 + m[up]).prod() ** (12 / up.sum()) / (1 + ms[up]).prod() ** (12 / up.sum())
    up_capture = float(((1 + m[up]).prod() ** (1 / up.sum()) - 1) / ((1 + ms[up]).prod() ** (1 / up.sum()) - 1))
    dn_capture = float(((1 + m[dn]).prod() ** (1 / dn.sum()) - 1) / ((1 + ms[dn]).prod() ** (1 / dn.sum()) - 1))
    var95, cvar95 = float(r.quantile(0.05)), float(r[r <= r.quantile(0.05)].mean())
    mvar95 = float(m.quantile(0.05))
    omega = float(ex[ex > 0].sum() / -ex[ex < 0].sum())
    gtp = float(m.sum() / -m[m < 0].sum())
    mu = r.mean() * 252; kelly = (mu - rfx.mean() * 252) / (r.var() * 252)
    t = pd.DataFrame(trades); t = t[(t.date >= str(eq.index[0].date())) & (t.date <= str(eq.index[-1].date()))]
    sells = t[t.side == "SELL"]; wins = sells[sells.realized_pl > 0]; losses = sells[sells.realized_pl < 0]
    daily = t.groupby('date').value.sum(); daily.index = pd.to_datetime(daily.index)
    turnover = float((daily / eq.reindex(daily.index).ffill()).sum() / yrs)   # value traded each day / account that day
    pct = lambda v, d=1: f"{v*100:+.{d}f}%" if v < 0 else f"{v*100:.{d}f}%"
    S = []
    S += [("Returns", "CAGR", pct(c), "compound annual growth"),
          ("Returns", "Total return", f"{(eq.iloc[-1]/eq.iloc[0]-1)*100:,.0f}%", f"$20k became ${eq.iloc[-1]:,.0f}"),
          ("Returns", "Best / worst year", f"{pct(y.max())} / {pct(y.min())}", f"{y.idxmax().year} / {y.idxmin().year}"),
          ("Returns", "Positive years", f"{(y > 0).sum()} of {len(y)}", f"beat SPY in {(y.values > pd.concat([pd.Series({spy.index[0]: spy.iloc[0]}), spy.resample('YE').last()]).pct_change().dropna().values).sum()}"),
          ("Returns", "Positive months", f"{(m > 0).mean()*100:.0f}%", f"average month {pct(m.mean())}, median {pct(m.median())}"),
          ("Returns", "Best / worst month", f"{pct(m.max())} / {pct(m.min())}", f"{m.idxmax():%b %Y} / {m.idxmin():%b %Y}"),
          ("Returns", "Best / worst day", f"{pct(r.max())} / {pct(r.min())}", f"{r.idxmax():%b %d %Y} / {r.idxmin():%b %d %Y}")]
    S += [("Risk", "Volatility (annual)", pct(vol), f"SPY {pct(rs.std()*math.sqrt(252))}"),
          ("Risk", "Downside volatility", pct(down), "volatility of losing days only"),
          ("Risk", "Max drawdown", pct(mdd), "deepest fall from a high"),
          ("Risk", "Average drawdown", pct(avg_dd), "typical distance below the last high when under water"),
          ("Risk", "Ulcer index", f"{ulcer*100:.1f}", "depth and length of drawdowns combined"),
          ("Risk", "Longest time under water", f"{longest} trading days", f"about {longest/252*12:.0f} months to a new high"),
          ("Risk", "Daily VaR / CVaR (95%)", f"{pct(var95)} / {pct(cvar95)}", "1 day in 20 is worse than VaR; CVaR = average of those days"),
          ("Risk", "Monthly VaR (95%)", pct(mvar95), "1 month in 20 is worse than this"),
          ("Risk", "Skew / excess kurtosis", f"{r.skew():.2f} / {r.kurt():.1f}", "fat tails: big days happen far more than a bell curve says")]
    S += [("Risk-adjusted", "Sharpe ratio", f"{ex.mean()/ex.std()*math.sqrt(252):.2f}", f"SPY {(rs-rfx).mean()/(rs-rfx).std()*math.sqrt(252):.2f}"),
          ("Risk-adjusted", "Sortino ratio", f"{ex.mean()*252/down:.2f}", "like Sharpe, but only penalises downside"),
          ("Risk-adjusted", "Calmar ratio (CAGR / max DD)", f"{c/-mdd:.2f}", "above 1 is excellent"),
          ("Risk-adjusted", "Martin ratio (CAGR / Ulcer)", f"{c/ulcer:.2f}", "return per unit of pain"),
          ("Risk-adjusted", "Omega ratio", f"{omega:.2f}", "sum of gains / sum of losses above the T-bill rate"),
          ("Risk-adjusted", "Gain-to-pain (monthly)", f"{gtp:.2f}", "sum of monthly returns / sum of losing months")]
    S += [("Vs the market", "Beta to SPY", f"{beta:.2f}", "moves about this many times SPY on an average day"),
          ("Vs the market", "Correlation to SPY", f"{corr:.2f}", ""),
          ("Vs the market", "Alpha (annual)", pct(alpha), "return not explained by SPY exposure"),
          ("Vs the market", "Up / down capture (monthly)", f"{up_capture*100:.0f}% / {dn_capture*100:.0f}%", "share of SPY's up months / down months it captured")]
    S += [("Trading", "Trade days per year", f"{t.date.nunique()/yrs:.0f}", f"{len(t)/yrs:.0f} orders a year"),
          ("Trading", "Turnover", f"{turnover*100:.0f}% a year", "value traded each year / account size (buys + sells)"),
          ("Trading", "Win rate (closed sales)", f"{len(wins)/max(len(sells),1)*100:.0f}%", f"{len(sells)} sells with realized P&L"),
          ("Trading", "Profit factor", f"{wins.realized_pl.sum()/-losses.realized_pl.sum():.2f}", "realized gains / realized losses"),
          ("Trading", "Average win / average loss", f"{wins.realized_pct.mean():.1f}% / {losses.realized_pct.mean():.1f}%", "per closed sale, % of cost"),
          ("Trading", "Average holding period", f"{sells.hold_days.mean():.0f} days", f"median {sells.hold_days.median():.0f}")]
    if cost_drag_per_5bp is not None:
        S.append(("Trading", "Cost of trading", f"{cost_drag_per_5bp*100:.1f} pts a year", "per 0.05% of cost per fill (spread + slippage)"))
    S.append(("Trading", "Kelly-optimal leverage", f"{kelly:.2f}x", "above 1x means more leverage would have raised growth in this history; full Kelly is far too aggressive in practice"))
    return [dict(section=a, name=b, value=v, note=n) for a, b, v, n in S]
