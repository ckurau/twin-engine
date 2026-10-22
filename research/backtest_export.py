"""Write backtest.json for the dashboard's Backtest tab: v1.6 (production engine) replayed 2000-2026 on the research panel.
Re-run after any rule change:  ..\\venv\\Scripts\\python research\\backtest_export.py   (writes ..\\backtest.json)"""
import os, sys, json, datetime as dt, multiprocessing as mp
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from insurance import SHOCK

SCEN = {"2000-2026": dict(), "2007-2026 (fresh start)": dict(start="2007-01-03"), "2010-2026 (real ETFs only)": dict(start="2010-03-12"),
        "2000-2026, double trading costs": dict(slippage_bps=10.0)}

def _run(a):
    """research copy with the current (v1.7) switches (matches the production engine within 0.1%) - it also records daily exposures"""
    import bt
    from round4 import V15
    n, kw = a; s = bt.run({**V15, "lds_assets": ("SPY", "TLT", "GLD"), "core_trend": "dual", "dual_fast": 30}, lab=True, **kw); return n, s

def cagr(e): return (e.iloc[-1] / e.iloc[0]) ** (365.25 / (e.index[-1] - e.index[0]).days) - 1
def mdd(e): return float((e / e.cummax() - 1).min())

if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(HERE)); import twin_engine as te
    with mp.Pool(4) as p: R = dict(p.map(_run, SCEN.items()))
    eq = R["2000-2026"]["equity"]; xp = R["2000-2026"]["expo"]
    spy = pd.read_pickle(os.path.join(HERE, "data", "panel.pkl"))["SPY"].reindex(eq.index)
    dd = eq / eq.cummax() - 1; ulcer = float(np.sqrt((dd ** 2).mean()))
    scen = [dict(name=n, cagr=round(s["cagr"] * 100, 1), maxdd=round(s["maxdd"] * 100, 1), final=round(s["final"]), trade_days=round(s["trade_days_yr"])) for n, s in R.items()]
    scen.append(dict(name="SPY, 2000-2026", cagr=round(cagr(spy) * 100, 1), maxdd=round(mdd(spy) * 100, 1), final=round(20000 * spy.iloc[-1] / spy.iloc[0]), trade_days=0))
    yr = lambda e: pd.concat([pd.Series({e.index[0]: e.iloc[0]}), e.resample("YE").last()]).pct_change().dropna()
    years = [dict(year=d.year, strat=round(a * 100, 1), spy=round(b * 100, 1)) for (d, a), b in zip(yr(eq).items(), yr(spy).values)]
    crashes = []
    for a, b, lab in [("2000-03-24", "2002-10-09", "Dot-com crash"), ("2007-10-09", "2009-03-09", "2008 financial crisis"), ("2018-09-20", "2018-12-24", "Q4 2018"),
                      ("2020-02-19", "2020-03-23", "Covid crash"), ("2021-11-19", "2022-12-28", "2022 bear market")]:
        e, s = eq.loc[a:b], spy.loc[a:b]
        crashes.append(dict(name=lab, start=a, end=b, strat_worst=round(mdd(e) * 100, 1), strat_total=round((e.iloc[-1] / e.iloc[0] - 1) * 100, 1), spy_total=round((s.iloc[-1] / s.iloc[0] - 1) * 100, 1)))
    eps, x = [], dd.copy()
    for _ in range(5):
        t = x.idxmin(); pk = eq.loc[:t].idxmax(); rec = eq.loc[t:][eq.loc[t:] >= eq.loc[pk]].index; end = rec[0] if len(rec) else None
        eps.append(dict(peak=str(pk.date()), trough=str(t.date()), depth=round(float(dd.loc[t]) * 100, 1), recovered=str(end.date()) if end is not None else None)); x.loc[pk:(end or x.index[-1])] = 0
    w10 = {y: cagr(eq.loc[f"{y}-01-01":f"{y + 9}-12-31"]) for y in range(2000, 2017)}
    xp = xp.reindex(columns=sorted(set(xp.columns) | set(SHOCK))).fillna(0); loss = sum(xp[a] * s for a, s in SHOCK.items()).clip(lower=-1)
    # 25-year projection: 12-month block bootstrap of monthly returns, $20k + $200/month
    m = eq.resample("ME").last(); r = m.pct_change().dropna().values; c0 = cagr(m)
    rng = np.random.default_rng(7); blocks = np.array([r[i:i + 12] for i in range(len(r) - 11)])
    paths = blocks[rng.integers(0, len(blocks), size=(20000, 25))].reshape(20000, 300)
    proj = {}
    for key, cut in [("realistic", 0.08), ("conservative", 0.15)]:
        Rm = (1 + paths) * ((1 + c0 - cut) / (1 + c0)) ** (1 / 12) - 1; v = np.full(20000, 20000.0); pk = v.copy(); worst = np.zeros(20000); rows = []
        for k in range(300):
            v = (v + 200) * (1 + Rm[:, k]); pk = np.maximum(pk, v); worst = np.minimum(worst, v / pk - 1)
            if (k + 1) % 12 == 0: rows.append((np.median(v), np.percentile(v, 10), np.percentile(v, 90)))
        proj[key] = dict(rows=rows, p50=float((worst < -0.5).mean()), worst=float(np.median(worst)))
    projection = [dict(year=i + 1, ending=f"Oct {2027 + i}", put_in=20000 + 2400 * (i + 1), median=round(a), p10=round(b), p90=round(c), conservative=round(proj["conservative"]["rows"][i][0]))
                  for i, (a, b, c) in enumerate(proj["realistic"]["rows"])]
    from metrics import compute
    rfd = pd.read_pickle(os.path.join(HERE, "data", "rf.pkl")); drag = (R["2000-2026"]["cagr"] - R["2000-2026, double trading costs"]["cagr"])
    e10 = R["2010-2026 (real ETFs only)"]["equity"]
    trading = {"2000-2026": compute(eq, spy, rfd, R["2000-2026"]["trades"], drag),
               "2010-2026 (real ETFs)": compute(e10, spy.reindex(e10.index) if False else pd.read_pickle(os.path.join(HERE, "data", "panel.pkl"))["SPY"], rfd, R["2010-2026 (real ETFs only)"]["trades"], drag)}
    eqm = eq.resample("ME").last(); spm = spy.resample("ME").last()
    out = dict(
        meta=dict(version=te.VERSION, generated=str(dt.date.today()), start_capital=20000,
                  notes=["Production engine replayed close by close, $20,000 start, no deposits, 0.05% cost per fill.",
                         "Before 2010 the leveraged ETFs are rebuilt from their indexes (calibrated to the real funds); from March 2010 every ETF is the real fund.",
                         "Backtests are not forecasts. The projection assumes returns 8 points a year below the backtest (realistic) or 15 points (conservative)."]),
        scenarios=scen, years=years, trading=trading, crashes=crashes, drawdowns=eps,
        metrics=dict(ulcer=round(ulcer * 100, 1), martin=round(cagr(eq) / ulcer, 2), worst10=round(min(w10.values()) * 100, 1), best10=round(max(w10.values()) * 100, 1),
                     median10=round(float(np.median(list(w10.values()))) * 100, 1), avg_nasdaq=round(float(xp["QQQ"].mean()), 2),
                     p5_12m=round(float((eq / eq.shift(252) - 1).dropna().quantile(0.05)) * 100, 1),
                     p5_36m_cagr=round(float(((eq / eq.shift(756)) ** (1 / 3) - 1).dropna().quantile(0.05)) * 100, 1)),
        stress=dict(median=round(float(loss.median()) * 100), p10=round(float(loss.quantile(0.10)) * 100), worst=round(float(loss.min()) * 100),
                    shock="S&P -20.5%, Nasdaq -20%, semiconductors -25%, Treasuries +2% in one day (like Oct 19, 1987)"),
        projection=dict(rows=projection, p_drop50=round(proj["realistic"]["p50"] * 100), median_worst=round(proj["realistic"]["worst"] * 100)),
        curve=[[d.strftime("%Y-%m"), round(float(a)), round(float(b) / float(spm.iloc[0]) * 20000)] for (d, a), b in zip(eqm.items(), spm.values)],
    )
    path = os.path.join(os.path.dirname(HERE), "backtest.json")
    json.dump(out, open(path, "w"), separators=(",", ":")); print("wrote", path, os.path.getsize(path) // 1024, "KB")
    print(json.dumps({k: out[k] for k in ("scenarios", "metrics", "stress")}, indent=1)); print(projection[19], projection[24], out["projection"]["p_drop50"])
