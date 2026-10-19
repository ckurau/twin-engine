"""Round 1: one change at a time vs the v1.3 baseline (80% vol target), 2000-2026, 0.05% per fill.

Acceptance (fixed before looking at results):
  CAGR >= baseline + 0.5 pt (2000-26), max DD no more than 3 pt worse (2000-26 and 2007-26),
  higher CAGR than baseline in >= 12 of 17 ten-year windows (starts Jan 2000..2016), and in both halves (2000-12, 2013-26).
"""
import os, sys, json, time, pickle, multiprocessing as mp
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, "out"); os.makedirs(OUT, exist_ok=True)

BASE_ASSETS = ("SPY", "QQQ", "TLT", "GLD")
IDEAS = [
    # --- Engine 1: Modified 9Sig
    ("9Sig", "Vol target 70%", dict(vol_target=0.70)), ("9Sig", "Vol target 75%", dict(vol_target=0.75)),
    ("9Sig", "Vol target 85%", dict(vol_target=0.85)), ("9Sig", "Vol target 90%", dict(vol_target=0.90)), ("9Sig", "Vol target 100%", dict(vol_target=1.00)),
    ("9Sig", "Vol power 5", dict(vol_power=5.0)), ("9Sig", "Vol power 7", dict(vol_power=7.0)), ("9Sig", "Vol power 15", dict(vol_power=15.0)), ("9Sig", "Vol power 20", dict(vol_power=20.0)),
    ("9Sig", "Vol lookback 10d", dict(vol_lookback=10)), ("9Sig", "Vol lookback 15d", dict(vol_lookback=15)), ("9Sig", "Vol lookback 30d", dict(vol_lookback=30)), ("9Sig", "Vol lookback 40d", dict(vol_lookback=40)),
    ("9Sig", "Vol band 0 (trade every change)", dict(vol_band=0.0)), ("9Sig", "Vol band 10 pts", dict(vol_band=0.10)),
    ("9Sig", "TOM: first 1 day after", dict(tom_after=1)), ("9Sig", "TOM: first 2 days after", dict(tom_after=2)), ("9Sig", "TOM: first 4 days after", dict(tom_after=4)), ("9Sig", "TOM: first 5 days after", dict(tom_after=5)),
    ("9Sig", "TOM: last 2 days before", dict(tom_before=2)), ("9Sig", "TOM: last 3 days before", dict(tom_before=3)),
    ("9Sig", "30-down rule off", dict(skip_after_crash=0)), ("9Sig", "30-down: skip 2 sells", dict(skip_after_crash=2)), ("9Sig", "30-down: skip 6 sells", dict(skip_after_crash=6)),
    ("9Sig", "Crash trigger -20%", dict(crash_qtr=-0.20)), ("9Sig", "Crash trigger -40%", dict(crash_qtr=-0.40)),
    ("9Sig", "Quarterly growth 8%", dict(sig_rate=0.08)), ("9Sig", "Quarterly growth 10%", dict(sig_rate=0.10)), ("9Sig", "Quarterly growth 11%", dict(sig_rate=0.11)),
    ("9Sig", "Defensive: TLT only", dict(defensive=("TLT",))), ("9Sig", "Defensive: GLD only", dict(defensive=("GLD",))),
    ("9Sig", "Defensive: IEF + GLD", dict(defensive=("IEF", "GLD"))), ("9Sig", "Defensive: TLT + GLD + IEF", dict(defensive=("TLT", "GLD", "IEF"))),
    ("9Sig", "Defensive: TLT + GLD + T-bills", dict(defensive=("TLT", "GLD", "BIL"))), ("9Sig", "Defensive: UBT (2x) + GLD", dict(defensive=("UBT", "GLD"))),
    ("9Sig", "Defensive: TLT + UGL (2x gold)", dict(defensive=("TLT", "UGL"))), ("9Sig", "Defensive: TMF (3x) + GLD", dict(defensive=("TMF", "GLD"))),
    ("9Sig", "Defensive trend filter (200d, else T-bills)", dict(def_trend=True)), ("9Sig", "Defensive trend filter (100d)", dict(def_trend=True, def_sma=100)),
    ("9Sig", "Vol switch parks in QQQ (1x)", dict(derisk_asset="QQQ")), ("9Sig", "Vol switch parks in QLD (2x)", dict(derisk_asset="QLD")),
    ("9Sig", "Vol switch parks in SPY", dict(derisk_asset="SPY")),
    ("9Sig", "Growth: TQQQ + UPRO", dict(growth=("TQQQ", "UPRO"))), ("9Sig", "Growth: UPRO only", dict(growth=("UPRO",))), ("9Sig", "Growth: TQQQ + TECL", dict(growth=("TQQQ", "TECL"))),
    ("9Sig", "Growth: TQQQ + SOXL", dict(growth=("TQQQ", "SOXL"))),
    ("9Sig", "TQQQ to 0 when QQQ < 200d", dict(growth_trend_cap=0.0)), ("9Sig", "TQQQ capped 50% when QQQ < 200d", dict(growth_trend_cap=0.5)),
    ("9Sig", "Dip boost: full TQQQ when RSI2 < 10 (uptrend)", dict(nine_dip=10)), ("9Sig", "Dip boost: RSI2 < 20", dict(nine_dip=20)),
    # --- Engine 2: LDS
    ("LDS", "Trend average 150d", dict(sma_days=150)), ("LDS", "Trend average 180d", dict(sma_days=180)), ("LDS", "Trend average 240d", dict(sma_days=240)), ("LDS", "Trend average 270d", dict(sma_days=270)),
    ("LDS", "Risk window 21d", dict(cov_days=21)), ("LDS", "Risk window 42d", dict(cov_days=42)), ("LDS", "Risk window 126d", dict(cov_days=126)),
    ("LDS", "Momentum 3/6/12 mo", dict(mom_months=(3, 6, 12))), ("LDS", "Momentum 1/3/6 mo", dict(mom_months=(1, 3, 6))),
    ("LDS", "Momentum 12 mo only", dict(mom_months=(12,))), ("LDS", "Momentum 6/12 mo", dict(mom_months=(6, 12))),
    ("LDS", "Core 100% / no overlay", dict(lds_core=1.0, lds_overlay=0.0)), ("LDS", "Core 90 / overlay 10", dict(lds_core=0.9, lds_overlay=0.1)), ("LDS", "Core 70 / overlay 30", dict(lds_core=0.7, lds_overlay=0.3)),
    ("LDS", "Overlay long-only (no inverse ETFs)", dict(overlay_long_only=True)), ("LDS", "Overlay vol 10%", dict(lds_overlay_vol=0.10)), ("LDS", "Overlay vol 25%", dict(lds_overlay_vol=0.25)),
    ("LDS", "Core vol target 80%", dict(lds_vol_target=0.8)), ("LDS", "Core vol target 120%", dict(lds_vol_target=1.2)), ("LDS", "Core vol target 150%", dict(lds_vol_target=1.5)),
    ("LDS", "Trade threshold 0%", dict(lds_threshold=0.0)), ("LDS", "Trade threshold 2.5%", dict(lds_threshold=0.025)), ("LDS", "Trade threshold 10%", dict(lds_threshold=0.10)),
    ("LDS", "Review daily", dict(lds_freq="day")), ("LDS", "Review every 2 weeks", dict(lds_freq="2week")), ("LDS", "Review monthly", dict(lds_freq="month")),
    ("LDS", "Core: top 2 by momentum", dict(core_topk=2)), ("LDS", "Core: top 3 by momentum", dict(core_topk=3)),
    ("LDS", "Add 7-10yr Treasuries (IEF/TYD)", dict(lds_assets=BASE_ASSETS + ("IEF",))), ("LDS", "Add emerging markets (EEM/EDC)", dict(lds_assets=BASE_ASSETS + ("EEM",))),
    ("LDS", "Add small caps (IWM/TNA)", dict(lds_assets=BASE_ASSETS + ("IWM",))), ("LDS", "Add semis (SOXX/SOXL)", dict(lds_assets=BASE_ASSETS + ("SOXX",))),
    ("LDS", "Add tech (XLK/TECL)", dict(lds_assets=BASE_ASSETS + ("XLK",))), ("LDS", "Add utilities (XLU/UTSL)", dict(lds_assets=BASE_ASSETS + ("XLU",))),
    ("LDS", "Add IEF + EEM", dict(lds_assets=BASE_ASSETS + ("IEF", "EEM"))),
    # --- Calendar / event swaps (LDS sleeve -> TQQQ for the session)
    ("Swap", "No Fed-day swap (v1.2 rules)", dict(fomc_swap=False)), ("Swap", "Fed swap: 2 days before", dict(fomc_pre=2)), ("Swap", "Fed swap: 3 days before", dict(fomc_pre=3)),
    ("Swap", "Fed swap: + day after", dict(fomc_lag=1)), ("Swap", "Fed swap into UPRO", dict(swap_asset=(("UPRO", 1.0),))),
    ("Swap", "Fed swap into TQQQ + UPRO", dict(swap_asset=(("TQQQ", 0.5), ("UPRO", 0.5)))), ("Swap", "Fed swap into TECL", dict(swap_asset=(("TECL", 1.0),))),
    ("Swap", "Fed swap into SOXL", dict(swap_asset=(("SOXL", 1.0),))), ("Swap", "Fed swap also sets 9Sig TQQQ to full", dict(swap_9sig=True)),
    ("Swap", "LDS -> TQQQ on turn-of-month days", dict(swap_tom=True)), ("Swap", "LDS -> TQQQ day before holidays", dict(swap_preholiday=True)),
    ("Swap", "LDS -> TQQQ on TOM + pre-holiday", dict(swap_tom=True, swap_preholiday=True)),
    ("Swap", "LDS -> TQQQ on dips (RSI2 < 10 until > 70)", dict(swap_dip=(10, 70))), ("Swap", "LDS -> TQQQ on deep dips (RSI2 < 5 until > 50)", dict(swap_dip=(5, 50))),
    ("Swap", "LDS -> TQQQ on dips (RSI2 < 20 until > 70)", dict(swap_dip=(20, 70))),
    # --- Split between engines
    ("Split", "40% 9Sig / 60% LDS", dict(split_9sig=0.40)), ("Split", "45 / 55", dict(split_9sig=0.45)), ("Split", "55 / 45", dict(split_9sig=0.55)), ("Split", "60 / 40", dict(split_9sig=0.60)),
    ("Split", "Reset twice a year", dict(rebalance_months=(6, 12))), ("Split", "Reset every quarter (v1.2)", dict(rebalance_months=(3, 6, 9, 12))), ("Split", "Never reset", dict(rebalance_months=())),
    ("Split", "Reset only on 10-pt drift", dict(rebalance_months=(), rebal_band=0.10)), ("Split", "Reset only on 15-pt drift", dict(rebalance_months=(), rebal_band=0.15)),
    ("Split", "Reset only on 20-pt drift", dict(rebalance_months=(), rebal_band=0.20)), ("Split", "Year end + 15-pt drift", dict(rebal_band=0.15)),
    ("Split", "Tilt 10 pts to last year's laggard", dict(tilt=0.10)), ("Split", "Tilt 20 pts to last year's laggard", dict(tilt=0.20)),
]

def _one(args):
    name, ov, kw = args
    import bt
    s = bt.run(ov, **kw)
    return name, {k: v for k, v in s.items() if k not in ("equity", "expo")}, s["equity"]

def windows(eq):
    out = {}
    for y in range(2000, 2017):
        e = eq.loc[f"{y}-01-01":f"{y + 9}-12-31"]
        if len(e) < 2000: continue
        yrs = (e.index[-1] - e.index[0]).days / 365.25
        out[y] = (e.iloc[-1] / e.iloc[0]) ** (1 / yrs) - 1
    return out

def sub(eq, a, b):
    e = eq.loc[a:b]; yrs = (e.index[-1] - e.index[0]).days / 365.25
    return dict(cagr=(e.iloc[-1] / e.iloc[0]) ** (1 / yrs) - 1, maxdd=float((e / e.cummax() - 1).min()))

def evaluate(results, base_name="BASELINE"):
    beq = results[base_name][1]; bs = results[base_name][0]
    bw = windows(beq); bh1, bh2, b07 = sub(beq, "2000", "2012"), sub(beq, "2013", "2026"), sub(beq, "2007", "2026")
    rows = []
    for name, (s, eq, grp) in results.items():
        w = windows(eq); h1, h2, s07 = sub(eq, "2000", "2012"), sub(eq, "2013", "2026"), sub(eq, "2007", "2026")
        wins = sum(w[y] > bw[y] for y in bw)
        d_cagr = s["cagr"] - bs["cagr"]; d_dd = s["maxdd"] - bs["maxdd"]; d_dd07 = s07["maxdd"] - b07["maxdd"]
        ok = (d_cagr >= 0.005 and d_dd >= -0.03 and d_dd07 >= -0.03 and wins >= 12 and h1["cagr"] > bh1["cagr"] and h2["cagr"] > bh2["cagr"])
        rows.append(dict(group=grp, idea=name, cagr=s["cagr"], maxdd=s["maxdd"], cagr07=s07["cagr"], maxdd07=s07["maxdd"],
                         h1=h1["cagr"], h2=h2["cagr"], wins=wins, nwin=len(bw), d_cagr=d_cagr, d_dd=d_dd, d_dd07=d_dd07,
                         trade_days=s.get("trade_days_yr"), final=s["final"], sharpe=s["sharpe"], passed=bool(ok) and name != base_name))
    return pd.DataFrame(rows)

def run_batch(ideas, tag, kw=None, procs=15):
    kw = kw or {}
    jobs = [("BASELINE", {}, kw)] + [(n, ov, kw) for _, n, ov in ideas]
    grp = {"BASELINE": "Base"}; grp.update({n: g for g, n, _ in ideas})
    t = time.time()
    with mp.Pool(procs) as pool:
        res = {}
        for i, (name, s, eq) in enumerate(pool.imap_unordered(_one, jobs), 1):
            res[name] = (s, eq, grp[name])
            print(f"[{i}/{len(jobs)} {time.time()-t:4.0f}s] {name:48s} CAGR {s['cagr']*100:5.1f}%  DD {s['maxdd']*100:6.1f}%", flush=True)
    pickle.dump(res, open(os.path.join(OUT, f"{tag}.pkl"), "wb"))
    df = evaluate(res); df.to_csv(os.path.join(OUT, f"{tag}.csv"), index=False)
    return df

if __name__ == "__main__":
    df = run_batch(IDEAS, "round1")
    pd.set_option("display.width", 250); pd.set_option("display.max_rows", 300)
    show = df.assign(**{c: (df[c] * 100).round(1) for c in ["cagr", "maxdd", "cagr07", "maxdd07", "h1", "h2", "d_cagr", "d_dd", "d_dd07"]})
    print(show.sort_values("d_cagr", ascending=False)[["group", "idea", "cagr", "maxdd", "cagr07", "maxdd07", "d_cagr", "d_dd", "d_dd07", "wins", "h1", "h2", "trade_days", "passed"]].to_string(index=False))
