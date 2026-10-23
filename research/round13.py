"""Round 13 (vs v1.7): ~200 ideas aimed at named drawbacks. Same pass rules as rounds 9-12 (2000-26, 2010-26, 1988-99),
plus each idea's result in the historical episode tied to each drawback. Stress panels for the best: round13b.py."""
import os, sys, time, pickle, multiprocessing as mp
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); OUT = os.path.join(HERE, "out")
from round9 import V17, SC
from round6 import metrics
from round10 import work
I = []   # (drawback, group, name, overrides, long_ok)
def add(dbk, g, n, long=True, **ov): I.append((dbk, g, n, ov, long))
def safe_work(a):
    try: return work(a)
    except Exception as e: print("FAILED", a[0], str(e)[:150], flush=True); return a[0], None

# D1 deep drawdowns / D6 crash-day (gap) risk / D12 both sleeves long stocks at once
for w in (0.6, 0.7, 0.8, 0.9, 0.95): add("D1 drawdown", "TQQQ ceiling", f"9Sig TQQQ never above {w:.0%} of the sleeve", nine_wmax=w)
for c in (1.25, 1.5, 1.75, 2.0, 2.25, 2.5): add("D12 sleeves overlap", "Account beta cap", f"Total stock exposure (both sleeves) capped at {c}x", beta_cap=c)
for c in (0.3, 0.4, 0.5): add("D6 gap risk", "TQQQ share cap", f"TQQQ at most {c:.0%} of the whole account", tqqq_cap=c)
for w in (0.6, 0.75, 0.9): add("D1 drawdown", "Softer boosts", f"Dip boost lifts TQQQ to {w:.0%} (not 100%)", dip_w=w)
for w in (0.75, 0.9): add("D1 drawdown", "Softer boosts", f"TOM boost lifts TQQQ to {w:.0%} (not 100%)", tom_w=w)
add("D1 drawdown", "Softer boosts", "Dip and TOM boosts both to 75%", dip_w=0.75, tom_w=0.75)
for x in (0.15, 0.20, 0.30): add("D1 drawdown", "No boosts in deep drawdown", f"No full-TQQQ boosts while account is >{x:.0%} below peak", boosts_off_dd=x)
for th, n in ((0.04, 5), (0.05, 5), (0.07, 5), (0.05, 10)): add("D6 gap risk", "Crash-day brake", f"After a {th:.0%}+ QQQ down day: TQQQ max 50% for {n} days", daycrash=(th, n, "cap"))
for th in (0.04, 0.05): add("D6 gap risk", "Crash-day buy", f"After a {th:.0%}+ QQQ down day in an uptrend: full TQQQ 5 days", daycrash=(th, 5, "buy"))
add("D6 gap risk", "LDS leverage", "LDS never above 2x", lds_kmax=2); add("D6 gap risk", "LDS leverage", "LDS never leveraged (1x only)", lds_kmax=1)
add("D6 gap risk", "LDS leverage", "LDS keeps 10% in T-bills", lds_invest=0.9); add("D6 gap risk", "LDS leverage", "LDS keeps 20% in T-bills", lds_invest=0.8)
# D9 Fed-day concentration (whole LDS in 3x semis)
add("D9 Fed swap tail", "Fed swap", "Fed swap 75% of LDS", swap_frac=0.75)
for v in (25, 30, 35): add("D9 Fed swap tail", "Fed swap", f"Skip Fed swap when VIX > {v}", swap_sig=("vix_low", v))
add("D9 Fed swap tail", "Fed swap", "Fed swap into TQQQ when VIX > 25, else SOXL", swap_asset_sig=(("vix_low", 25), (("SOXL", 1.0),), (("TQQQ", 1.0),)))
add("D9 Fed swap tail", "Fed swap", "Fed swap into QLD (2x)", swap_asset=(("QLD", 1.0),)); add("D9 Fed swap tail", "Fed swap", "Fed swap into SSO (2x S&P)", swap_asset=(("SSO", 1.0),))
add("D9 Fed swap tail", "Fed swap", "Fed swap held through the day after", fomc_lag=1)
# D2 tech concentration / lost tech decade
for m in (12, 24, 36): add("D2 tech concentration", "Growth rotation", f"9Sig holds UPRO instead of TQQQ when S&P beat Nasdaq over {m} months", win=800, growth_rot=(("TQQQ", "UPRO"), m, "mom"))
for n, th in ((756, 0.3), (756, 0.5), (756, 0.7), (504, 0.4)):
    add("D2 tech concentration", "Tech froth", f"Nasdaq beat S&P by >{th:.0%} over {n // 252}y: split 40/60", win=800, split_sig=(("froth", n, th), 0.5, 0.4))
add("D2 tech concentration", "Tech froth", "Nasdaq beat S&P by >50% over 3y: TQQQ max 75%", win=800, cap_sig=(("froth", 756, 0.5), 0.75))
add("D2 tech concentration", "Tech froth", "Nasdaq beat S&P by >50% over 3y: TQQQ max 0% (all reserve)", win=800, cap_sig=(("froth", 756, 0.5), 0.0))
BA = ("SPY", "TLT", "GLD")
add("D2 tech concentration", "LDS diversifiers", "LDS adds real estate (VNQ, 1x)", long=False, lds_assets=BA + ("VNQ",))
add("D2 tech concentration", "LDS diversifiers", "LDS adds health care (XLV, 1x)", long=False, lds_assets=BA + ("XLV",))
add("D2 tech concentration", "LDS diversifiers", "LDS adds energy (XLE, 1x)", long=False, lds_assets=BA + ("XLE",))
add("D2 tech concentration", "LDS diversifiers", "LDS core: S&P at most 60%", lds_cap={"SPY": 0.6}); add("D2 tech concentration", "LDS diversifiers", "LDS core: S&P at most 45%", lds_cap={"SPY": 0.45})
# D3 stocks and bonds falling together / D14 rising rates hurt the TLT reserve
for nm, d in (("IEF", ("IEF",)), ("IEF + gold", ("IEF", "GLD")), ("TLT + IEF + gold", ("TLT", "IEF", "GLD")), ("gold + T-bills", ("GLD", "BIL")),
              ("2 TLT : 1 gold", ("TLT", "TLT", "GLD")), ("1 TLT : 2 gold", ("TLT", "GLD", "GLD")), ("IEF + gold + T-bills", ("IEF", "GLD", "BIL"))):
    add("D3 stock+bond crash", "Reserve mix", f"9Sig reserve = {nm}", long="IEF" not in d, defensive=d)
add("D14 rising rates", "Reserve by rates", "10y yield above its 200d: reserve gold + T-bills", res_sig=(("yld_down",), ("GLD", "BIL")))
add("D14 rising rates", "Reserve by rates", "Fed hiking fast: reserve gold + T-bills", res_sig=(("hiking", 1.0), ("GLD", "BIL")))
add("D14 rising rates", "Reserve by rates", "Fed hiking at all (3m bill up in 6m): reserve gold + T-bills", res_sig=(("hiking", 0.0), ("GLD", "BIL")))
add("D14 rising rates", "Reserve by rates", "Stock/bond corr > 0 (20d): reserve gold + T-bills", res_sig=(("sbc", 20, 0.0), ("GLD", "BIL")))
add("D3 stock+bond crash", "LDS bonds", "LDS uses IEF (7-10y) instead of TLT", long=False, lds_assets=("SPY", "IEF", "GLD"))
for c in (0.3, 0.5): add("D3 stock+bond crash", "LDS bonds", f"LDS core: Treasuries at most {c:.0%}", lds_cap={"TLT": c})
# D4 choppy / sideways markets (whipsaw)
for n in (2, 3, 5): add("D4 whipsaw", "Vol switch smoothing", f"Vol switch acts only after {n} days in a row", vol_persist=n)
add("D4 whipsaw", "Vol switch smoothing", "Vol switch checked only on Fridays", vol_weekly=True)
for s_ in (0.1, 0.25, 0.5): add("D4 whipsaw", "Vol switch smoothing", f"Vol switch in {s_:.0%} steps", vol_step=s_)
for r_, b_ in ((0.1, False), (0.2, False), (0.2, True), (0.34, False)): add("D4 whipsaw", "Vol switch smoothing", f"Re-entry ramps {r_:.0%}/day" + (" (exits too)" if b_ else ""), vol_ramp=(r_, b_))
for m_ in (1, 2, 6): add("D4 whipsaw", "9Sig frequency", f"9Sig rebalance every {m_} month(s) (target scaled)", nine_months=m_, sig_rate=(1.09 ** (m_ / 3) - 1))
# D5 leverage decay & financing cost
for th in (2.0, 3.0, 4.0, 5.0): add("D5 decay/financing", "Rate-aware leverage", f"9Sig uses QLD (2x) when 3m T-bill > {th:.0f}%", growth_rot=(("TQQQ", "QLD"), th, "rate"))
for th in (0.25, 0.30, 0.35): add("D5 decay/financing", "Vol-aware leverage", f"9Sig uses QLD when QQQ 60d vol > {th:.0%}", growth_rot=(("TQQQ", "QLD"), th, "volreg"))
add("D5 decay/financing", "Lower leverage", "9Sig uses QLD always", growth=("QLD",)); add("D5 decay/financing", "Lower leverage", "9Sig uses QLD, vol target 100%", growth=("QLD",), vol_target=1.0)
add("D5 decay/financing", "Lower leverage", "9Sig growth = half TQQQ, half QLD", growth=("TQQQ", "QLD"), growth_vol_blend=True)
add("D5 decay/financing", "De-risk asset", "Vol switch parks in QQQ (1x) in uptrends, else reserve", derisk_cond="QQQ")
add("D5 decay/financing", "De-risk asset", "Vol switch parks in SPY (1x) in uptrends, else reserve", derisk_cond="SPY")
add("D5 decay/financing", "De-risk asset", "Vol switch parks in QLD (2x) in uptrends, else reserve", derisk_cond="QLD")
# D8 rebalance timing luck
for o in (1, 2): add("D8 timing luck", "9Sig calendar", f"9Sig quarters offset by {o} month", q_offset=o)
for k in (1, 3): add("D8 timing luck", "9Sig calendar", f"9Sig rebalance {k} session(s) before quarter end", q_shift=k)
add("D8 timing luck", "LDS calendar", "LDS review mid-month (timing check)", lds_freq="midmonth")
# Other places: 9Sig crash rule, LDS vol window, start mix, Fed swap exit, TOM window
for cq, sk in ((-0.25, 2), (-0.35, 2), (-0.30, 1), (-0.30, 3)): add("D7 rule fragility", "30-down rule", f"Crash quarter {cq:.0%}, skip {sk} sell(s)", crash_qtr=cq, skip_after_crash=sk)
for cd in (21, 126): add("D7 rule fragility", "LDS vol window", f"LDS volatility from {cd} days", cov_days=cd)
add("D7 rule fragility", "TOM window", "TOM boost on last 2 days of month", tom_before=2)
# second batch
add("D1 drawdown", "TQQQ ceiling", "TQQQ ceiling 90% + vol target 90%", nine_wmax=0.9, vol_target=0.90); add("D1 drawdown", "TQQQ ceiling", "TQQQ ceiling 70% + vol target 100%", nine_wmax=0.7, vol_target=1.0)
add("D12 sleeves overlap", "Account beta cap", "Beta cap 2x + vol target 90%", beta_cap=2.0, vol_target=0.90); add("D12 sleeves overlap", "Account beta cap", "Beta cap 2.5x + vol target 90%", beta_cap=2.5, vol_target=0.90)
add("D6 gap risk", "TQQQ share cap", "TQQQ at most 60% of the whole account", tqqq_cap=0.6)
add("D1 drawdown", "Softer boosts", "Dip boost to 75% + vol target 85%", dip_w=0.75, vol_target=0.85)
for x in (0.20, 0.30): add("D1 drawdown", "Drawdown brake", f"Account >{x:.0%} below peak: LDS unleveraged", dd_lds=x)
add("D6 gap risk", "Crash-day brake", "After a 3%+ QQQ down day: TQQQ max 50% for 5 days", daycrash=(0.03, 5, "cap"))
add("D6 gap risk", "Permanent hedge", "9Sig growth = 90% TQQQ + 10% TMF", growth=("TQQQ",) * 9 + ("TMF",)); add("D6 gap risk", "Permanent hedge", "9Sig growth = 90% TQQQ + 10% UGL", growth=("TQQQ",) * 9 + ("UGL",))
add("D9 Fed swap tail", "Fed swap", "Fed swap 75% and skipped when VIX > 30", swap_frac=0.75, swap_sig=("vix_low", 30)); add("D9 Fed swap tail", "Fed swap", "Fed swap only when VIX < 20", swap_sig=("vix_low", 20))
add("D9 Fed swap tail", "Fed swap", "Fed swap only when QQQ within 8% of its 52-week high", swap_sig=("notdeep", 0.08))
add("D2 tech concentration", "Tech froth", "Nasdaq beat S&P by >50% over 3y: TQQQ max 50%", win=800, cap_sig=(("froth", 756, 0.5), 0.5))
add("D2 tech concentration", "LDS diversifiers", "LDS core: S&P at most 30%", lds_cap={"SPY": 0.3}); add("D2 tech concentration", "LDS diversifiers", "LDS adds VNQ and XLV", long=False, lds_assets=BA + ("VNQ", "XLV"))
add("D3 stock+bond crash", "Reserve mix", "9Sig reserve = TLT + IEF + gold + T-bills", long=False, defensive=("TLT", "IEF", "GLD", "BIL"))
add("D3 stock+bond crash", "Reserve mix", "9Sig reserve = 2 gold : 1 IEF", long=False, defensive=("GLD", "GLD", "IEF"))
add("D14 rising rates", "Reserve by rates", "10y yield above its 200d: reserve IEF + gold", long=False, res_sig=(("yld_down",), ("IEF", "GLD")))
add("D14 rising rates", "Reserve by rates", "Fed hiking fast: reserve gold only", res_sig=(("hiking", 1.0), ("GLD",)))
add("D14 rising rates", "LDS bonds by rates", "LDS holds TLT only when 10y yield below its 200d", lds_gate={"TLT": ("yld_down",)})
add("D14 rising rates", "LDS bonds by rates", "LDS holds TLT only when Fed not hiking fast", lds_gate={"TLT": ("hiking", 1.0)})
add("D14 rising rates", "LDS bonds by rates", "LDS holds TLT only when stock/bond corr < 0", lds_gate={"TLT": ("sbc", 60, 0.0)})
add("D4 whipsaw", "Vol switch smoothing", "Vol switch in 20% steps", vol_step=0.2); add("D4 whipsaw", "Vol switch smoothing", "Vol switch Fridays only, 25% steps", vol_weekly=True, vol_step=0.25)
add("D4 whipsaw", "Vol switch smoothing", "Re-entry ramps 50%/day", vol_ramp=(0.5, False))
add("D5 decay/financing", "Rate-aware leverage", "9Sig uses QLD when 3m T-bill > 1%", growth_rot=(("TQQQ", "QLD"), 1.0, "rate"))
add("D5 decay/financing", "Rate-aware leverage", "QLD when T-bill > 4% + vol target 90%", growth_rot=(("TQQQ", "QLD"), 4.0, "rate"), vol_target=0.90)
add("D5 decay/financing", "Vol-aware leverage", "9Sig uses QLD when QQQ 60d vol > 20%", growth_rot=(("TQQQ", "QLD"), 0.20, "volreg"))
add("D5 decay/financing", "Lower leverage", "Half TQQQ / half QLD + vol target 90%", growth=("TQQQ", "QLD"), growth_vol_blend=True, vol_target=0.90)
for k in (2, 5): add("D8 timing luck", "9Sig calendar", f"9Sig rebalance {k} sessions before quarter end", q_shift=k)
for cd in (42, 252): add("D7 rule fragility", "LDS vol window", f"LDS volatility from {cd} days", cov_days=cd)
for w0 in (0.5, 0.7): add("D7 rule fragility", "Start mix", f"9Sig starts {w0:.0%} TQQQ", w0_growth=w0)
for f in (0.5, 0.25): add("D19 forced selling", "Partial reset", f"Year-end reset moves only {f:.0%} of the way to 50/50", reset_frac=f)
add("D19 forced selling", "Partial reset", "No year-end reset (sleeves drift)", rebalance_months=())
add("D19 forced selling", "Partial reset", "50/50 reset every quarter", rebalance_months=(3, 6, 9, 12))
# combos fixed in advance (one per drawback pair)
add("Combo", "Combo", "Beta cap 2x + reserve IEF + gold", long=False, beta_cap=2.0, defensive=("IEF", "GLD"))
add("Combo", "Combo", "TQQQ ceiling 90% + vol steps 25%", nine_wmax=0.9, vol_step=0.25)
add("Combo", "Combo", "Rate-aware QLD 4% + reserve gold + T-bills when yields rise", growth_rot=(("TQQQ", "QLD"), 4.0, "rate"), res_sig=(("yld_down",), ("GLD", "BIL")))
add("Combo", "Combo", "Crash-day brake 5% + no boosts in 20% drawdown", daycrash=(0.05, 5, "cap"), boosts_off_dd=0.20)
add("Combo", "Combo", "Skip Fed swap VIX>30 + LDS max 2x", swap_sig=("vix_low", 30), lds_kmax=2)
add("Combo", "Combo", "Beta cap 2x + stock/bond-corr vol target", beta_cap=2.0, vt_sig=(("sbc", 60, 0.0), 0.85, 0.75))
add("Combo", "Combo", "Stock/bond-corr vol target + reserve gold + T-bills when corr > 0", vt_sig=(("sbc", 60, 0.0), 0.85, 0.75), res_sig=(("sbc", 60, 0.0), ("GLD", "BIL")))
add("Combo", "Combo", "Vol persist 3 days + re-entry ramp 20%", vol_persist=3, vol_ramp=(0.2, False))
add("Combo", "Combo", "Tech froth split + UPRO rotation 36m", win=800, split_sig=(("froth", 756, 0.5), 0.5, 0.4), growth_rot=(("TQQQ", "UPRO"), 36, "mom"))
add("Combo", "Combo", "Softer dip 75% + beta cap 2.5x + vol target 85%", dip_w=0.75, beta_cap=2.5, vol_target=0.85)
add("Combo", "Combo", "TQQQ ceiling 80% + vol target 90%", nine_wmax=0.8, vol_target=0.90)
add("Combo", "Combo", "Beta cap 1.75x + vol target 90%", beta_cap=1.75, vol_target=0.90)
add("Combo", "Combo", "LDS max 2x + split 55/45", lds_kmax=2, split_9sig=0.55)
add("Combo", "Combo", "Reserve gold + T-bills + vol target 85%", defensive=("GLD", "BIL"), vol_target=0.85)
add("Combo", "Combo", "Partial reset 50% + beta cap 2.5x", reset_frac=0.5, beta_cap=2.5)
add("Combo", "Combo", "LDS TLT gated by yields + reserve gold/T-bills when yields rise", lds_gate={"TLT": ("yld_down",)}, res_sig=(("yld_down",), ("GLD", "BIL")))
add("Combo", "Combo", "10% TMF hedge + vol target 90%", growth=("TQQQ",) * 9 + ("TMF",), vol_target=0.90)
add("Combo", "Combo", "Drawdown brake 20% + vol target 90%", dd_lds=0.20, vol_target=0.90)
add("Combo", "Combo", "Vol steps 25% + Fed swap skipped VIX>30 + crash-day brake 5%", vol_step=0.25, swap_sig=("vix_low", 30), daycrash=(0.05, 5, "cap"))

# ---- post-hoc account-level ideas (exactly implementable: separate sub-accounts / blends rebalanced monthly)
ENS = [("D8 timing luck", "3 staggered copies of the strategy (9Sig quarters offset 0/1/2 months)", ["BASELINE", "9Sig quarters offset by 1 month", "9Sig quarters offset by 2 month"]),
       ("D8 timing luck", "2 copies: LDS reviewed month-end and mid-month", ["BASELINE", "LDS review mid-month (timing check)"])]
BLEND = [(f"{int(w*100)}% Twin Engine + {int((1-w)*100)}% {nm}", w, nm) for nm in ("S&P 500 (VOO)", "Gold", "Leverage rotation (UPRO above 200d, else T-bills)", "HFEA (55% UPRO / 45% TMF)", "60/40 S&P / 7-10y Treasuries", "T-bills")
         for w in ((0.9, 0.8, 0.6, 0.5) if nm == "S&P 500 (VOO)" else (0.8, 0.6) if nm == "Leverage rotation (UPRO above 200d, else T-bills)" else (0.9, 0.8) if nm == "Gold" else (0.8,))] + \
        [("80% Twin Engine + 20% QQQ", 0.8, "QQQ")]

def others(px, rf):
    r = px.pct_change().fillna(0.0); o = {}
    o["S&P 500 (VOO)"] = r["SPY"]; o["Gold"] = r["GLD"]; o["T-bills"] = rf.reindex(r.index).fillna(0.0)
    up = (px["SPY"] > px["SPY"].rolling(200).mean()).shift(1).fillna(False)
    o["Leverage rotation (UPRO above 200d, else T-bills)"] = np.where(up, r["UPRO"], o["T-bills"]) - up.astype(float).diff().abs().fillna(0) * 0.0005
    o["HFEA (55% UPRO / 45% TMF)"] = 0.55 * r["UPRO"] + 0.45 * r["TMF"]; o["60/40 S&P / 7-10y Treasuries"] = 0.6 * r["SPY"] + 0.4 * r["IEF"].fillna(r["TLT"])
    o["QQQ"] = r["QQQ"]; o["TQQQ buy & hold"] = r["TQQQ"]
    return {k: pd.Series(v, index=r.index) for k, v in o.items()}

def blend(eq, other_r, w):
    """two sub-accounts, reset to w / 1-w at each month end"""
    r1 = eq.pct_change().fillna(0.0); r2 = other_r.reindex(eq.index).fillna(0.0); a, b, out = w, 1 - w, []
    me = eq.index.to_series().dt.month != eq.index.to_series().shift(-1).dt.month
    for i in range(len(eq)):
        a *= 1 + r1.iloc[i]; b *= 1 + r2.iloc[i]; out.append(a + b)
        if me.iloc[i]: t = a + b; a, b = w * t, (1 - w) * t
    return pd.Series(out, index=eq.index) * eq.iloc[0]

EPIS = {"Dot-com crash": ("00", "2000-03-24", "2002-10-09"), "Lost tech decade 2000-12": ("00", "2000-01-03", "2012-12-31"),
        "GFC 2007-09": ("00", "2007-10-09", "2009-03-09"), "2011 debt scare": ("00", "2011-04-29", "2011-10-03"), "Chop 2015-16": ("00", "2015-05-01", "2016-06-30"),
        "Q4 2018": ("00", "2018-09-20", "2018-12-24"), "COVID crash": ("00", "2020-02-19", "2020-03-23"), "2022 stocks+bonds": ("00", "2022-01-03", "2022-10-14"),
        "1990 bear": ("88", "1990-07-16", "1990-10-11"), "1994 bond crash": ("88", "1994-01-03", "1994-12-30"), "1998 LTCM": ("88", "1998-07-17", "1998-10-08")}
def episodes(res, n):
    out = {}
    for e, (sk, a, b) in EPIS.items():
        s = res.get((n, sk))
        if s is None: out[e] = np.nan; continue
        x = s.loc[a:b]; out[e] = float(x.iloc[-1] / x.iloc[0] - 1) if len(x) > 1 else np.nan
    return out

if __name__ == "__main__":
    jobs = []
    for sk, (kw, lg) in SC.items():
        jobs.append((("BASELINE", sk), V17, kw, lg))
        for dbk, g, n, ov, long_ok in I:
            if sk == "88" and not long_ok: continue
            jobs.append(((n, sk), {**V17, **ov}, kw, lg))
    if len(sys.argv) > 1:
        jobs = [((n, "10"), {**V17, **ov}, dict(start="2023-06-01"), False) for _, g, n, ov, _ in I] + [((n, "88"), {**V17, **ov}, dict(start="1994-06-01", end="1995-06-30"), True) for _, g, n, ov, lo in I if lo]
    print(len(I) + len(ENS) + len(BLEND), "ideas,", len(jobs), "runs", flush=True); res = {}; t = time.time()
    with mp.Pool(15) as pool:
        for i, (k, eq) in enumerate(pool.imap_unordered(safe_work, jobs), 1):
            if eq is not None: res[k] = eq
            if i % 50 == 0: print(f"[{i}/{len(jobs)} {time.time()-t:4.0f}s]", flush=True); pickle.dump(res, open(os.path.join(OUT, "round13_partial.pkl"), "wb"))
    if len(sys.argv) > 1: print("smoke ok"); sys.exit()
    import bt
    LONG = bt.add_signal_cols(pd.read_pickle(os.path.join(HERE, "data", "panel_long.pkl")))
    OTH = {"00": others(bt.PANEL, bt.PANEL["RF"]), "10": others(bt.PANEL, bt.PANEL["RF"]), "88": others(LONG, LONG["RF"])}
    names = [(dbk, g, n, long_ok) for dbk, g, n, ov, long_ok in I]
    for dbk, n, parts in ENS:
        for sk in SC:
            if all((p_, sk) in res for p_ in parts): res[(n, sk)] = sum(res[(p_, sk)] / res[(p_, sk)].iloc[0] for p_ in parts) / len(parts) * res[("BASELINE", sk)].iloc[0]
        names.append((dbk, "Copies", n, True))
    for n, w, nm in BLEND:
        for sk in SC: res[(n, sk)] = blend(res[("BASELINE", sk)], OTH[sk][nm], w)
        names.append(("D11 money elsewhere", "Blend", n, True))
    pickle.dump(res, open(os.path.join(OUT, "round13.pkl"), "wb"))
    B = {sk: metrics(res[("BASELINE", sk)]) for sk in SC}; EB = episodes(res, "BASELINE")
    rows = []
    for dbk, g, n, long_ok in [("Base", "Base", "BASELINE", True)] + names:
        m = {sk: metrics(res[(n, sk)]) if (n, sk) in res else None for sk in SC}
        if m["00"] is None or m["10"] is None: print("missing", n); continue
        d = {sk: (m[sk]["cagr"] - B[sk]["cagr"]) if m[sk] else None for sk in SC}
        dd = {sk: (m[sk]["maxdd"] - B[sk]["maxdd"]) if m[sk] else None for sk in SC}
        ret = d["00"] >= 0.005 and d["10"] >= 0.005 and (d["88"] is None or d["88"] >= -0.005) and all(x is None or x >= -0.03 for x in dd.values())
        risk = all(m[sk] is None or (m[sk]["martin"] > B[sk]["martin"] and d[sk] >= -1e-4) for sk in SC)
        row = dict(drawback=dbk, group=g, idea=n, cagr00=m["00"]["cagr"], dd00=m["00"]["maxdd"], d00=d["00"], cagr10=m["10"]["cagr"], dd10=m["10"]["maxdd"], d10=d["10"],
                   cagr88=m["88"]["cagr"] if m["88"] else np.nan, dd88=m["88"]["maxdd"] if m["88"] else np.nan, d88=d["88"] if d["88"] is not None else np.nan,
                   martin00=m["00"]["martin"], verdict=("PASS return " if ret else "") + ("PASS risk" if risk else "") if n != "BASELINE" else "")
        ep = episodes(res, n); row.update({f"ep:{e}": (ep[e] - EB[e]) if n != "BASELINE" else ep[e] for e in EPIS})
        rows.append(row)
    df = pd.DataFrame(rows); df.to_csv(os.path.join(OUT, "round13.csv"), index=False)
    show = df[["drawback", "idea", "cagr00", "dd00", "d00", "cagr10", "dd10", "d10", "cagr88", "dd88", "d88", "martin00", "verdict"]].copy()
    for c in ["cagr00", "dd00", "d00", "cagr10", "dd10", "d10", "cagr88", "dd88", "d88"]: show[c] = (show[c] * 100).round(1)
    show["martin00"] = show["martin00"].round(2)
    pd.set_option("display.width", 320); pd.set_option("display.max_rows", 400); pd.set_option("display.max_colwidth", 70)
    print(show.sort_values("d00", ascending=False).to_string(index=False))
