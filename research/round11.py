"""Round 11 (vs v1.7): ~200 new ideas, same pass rules as rounds 9-10 (2000-26, 2010-26, out-of-sample 1988-99).
Signals: research/te_lab.py sig(). The "Account" family trades the account's own equity curve (computed from the v1.7
equity with T-bill yield on the cash part and 0.05% cost per unit of exposure change)."""
import os, sys, time, pickle, multiprocessing as mp
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); OUT = os.path.join(HERE, "out")
from round9 import V17, SC
from round6 import metrics
from round10 import work
I = []
def add(g, n, long=True, **ov): I.append((g, n, ov, long))
def three(g, label, spec, long=True):
    add(g, f"{label}: TQQQ max 50% when off", long, cap_sig=(spec, 0.5))
    add(g, f"{label}: full TQQQ when on", long, boost_sig=spec)
    add(g, f"{label}: split 60/40 on, 40/60 off", long, split_sig=(spec, 0.6, 0.4))
cap = lambda g, n, spec, c=0.5, long=True: add(g, n + f": TQQQ max {c:.0%} when off", long, cap_sig=(spec, c))
boost = lambda g, n, spec, long=True: add(g, n + ": full TQQQ", long, boost_sig=spec)

# --- price location / trend quality (George & Hwang 52-week high, overextension, Sharpe, acceleration)
for x in (0.02, 0.05): three("52-week high", f"QQQ within {x:.0%} of 52-week high", ("ath", x))
for x in (0.15, 0.25): three("52-week high", f"QQQ less than {x:.0%} below 52-week high", ("notdeep", x))
for x in (0.20, 0.30): three("Overextension", f"QQQ less than {x:.0%} above 200d", ("notover", x))
cap("Overextension", "QQQ less than 25% above 200d", ("notover", 0.25))
three("Trend quality", "QQQ 1-year Sharpe > 1", ("sharpe", 1.0)); boost("Trend quality", "QQQ 1-year Sharpe > 1.5", ("sharpe", 1.5))
three("Trend quality", "Momentum accelerating (3m > 12m/4)", ("accel",))
three("Trend quality", "Trending regime (variance ratio > 1)", ("vr",)); three("Trend quality", "Positive return autocorrelation (63d)", ("ac",))
three("Trend quality", "Volatility falling (20d < 60d)", ("vol_fall",))
# --- crash-risk statistics (Kritzman turbulence & absorption ratio, skew)
for q_ in (0.90, 0.95): three("Kritzman", f"Turbulence below {q_:.0%} percentile", ("turb", q_))
cap("Kritzman", "Turbulence below 90% percentile", ("turb", 0.90), 0.0); cap("Kritzman", "Turbulence below 90% percentile", ("turb", 0.90), 0.75)
three("Kritzman", "Absorption ratio shift < 1 sd", ("absorb", 1.0)); cap("Kritzman", "Absorption ratio shift < 1 sd", ("absorb", 1.0), 0.0); cap("Kritzman", "Absorption ratio shift < 1 sd", ("absorb", 1.0), 0.75)
three("Tail risk", "QQQ 60d skew > -0.5", ("skew", -0.5)); cap("Tail risk", "QQQ 60d skew > -1", ("skew", -1.0)); cap("Tail risk", "QQQ 60d skew > -0.5", ("skew", -0.5), 0.75)
# --- breadth
for x in (0.5, 0.7): three("Breadth", f"At least {x:.0%} of 12 ETFs above 200d", ("breadth", x))
cap("Breadth", "At least 50% of 12 ETFs above 200d", ("breadth", 0.5), 0.0); cap("Breadth", "At least 50% of 12 ETFs above 200d", ("breadth", 0.5), 0.75)
# --- macro / intermarket
three("Macro", "Commodities calm (DBC 6m < +30%)", ("dbc_calm", 0.30)); cap("Macro", "Commodities calm (DBC 6m < +40%)", ("dbc_calm", 0.40))
three("Macro", "Energy lagging (XLE/SPY below 200d)", ("lag", "XLE")); three("Gayed", "Utilities lagging (XLU/SPY below 200d)", ("lag", "XLU"))
cap("Macro", "Health care lagging (XLV/SPY below 200d)", ("lag", "XLV"))
three("Macro", "Gold beating Treasuries over 13 weeks", ("gold_tsy",)); three("Macro", "Copper above 200d", ("copper",), long=False)
three("Macro", "Emerging markets leading (EEM/SPY > 200d)", ("lead", "EEM")); three("Macro", "Financials leading (XLF/SPY > 200d)", ("lead", "XLF"))
cap("Macro", "Developed intl leading (EFA/SPY > 200d)", ("lead", "EFA")); three("Macro", "Tech leading (QQQ/SPY > 200d)", ("tech_lead",))
three("Rates", "10y yield below its 200d", ("yld_down",)); three("Rates", "TLT below 200d (no flight to safety)", ("tlt_down",))
three("Rates", "Stock/bond correlation negative (60d)", ("sb_corr",))
for x in (1.0, 0.5): three("Rates", f"No fast Fed hiking (3m bill up < {x} pt in 6m)", ("hiking", x))
three("Volatility", "VIX below 16", ("vix_low", 16)); boost("Volatility", "VIX below 13", ("vix_low", 13))
three("Shocks", "No bond spike (TLT 20d < +5%)", ("tlt_calm", 0.05)); cap("Shocks", "No bond spike (TLT 20d < +8%)", ("tlt_calm", 0.08))
three("Shocks", "No gold spike (GLD 20d < +8%)", ("gold_calm", 0.08)); three("Shocks", "No dollar spike (DXY 20d < +3%)", ("usd_calm", 0.03))
# --- classic technicians
three("Wilder", "ADX > 25 with +DI > -DI", ("adx", 25)); three("Wilder", "ADX > 20 with +DI > -DI", ("adx", 20))
three("Supertrend", "Supertrend(10, 3) up", ("supertrend", 10, 3)); three("Elder", "Weekly RSI(14) below 70", ("wrsi", 70))
boost("Crabel", "NR7 narrow range in uptrend", ("nr", 7)); boost("Crabel", "NR4 narrow range in uptrend", ("nr", 4))
boost("Connors", "3 down days in uptrend", ("dstreak", 3)); boost("Connors", "4 down days in uptrend", ("dstreak", 4)); cap("Connors", "Not 5 straight up days", ("nostreak", 5))
boost("Bollinger", "Close below lower band in uptrend", ("pctb",)); boost("Keltner", "Close above upper Keltner channel", ("keltner",))
boost("Chande", "Aroon up > 70, down < 30", ("aroon",)); add("Coppock", "Coppock curve turning up below zero: full TQQQ", boost_sig=("coppock",), win=700)
add("Mom crash", "LDS overlay off when S&P 2-year return < 0 (round 10 re-run, full data)", overlay_bear=True, win=700)
boost("Golden cross", "50d crossed above 200d in last 60 days", ("gcross",))
# --- bottoms (O'Neil follow-through, capitulation, recovery, crash buying)
boost("O'Neil", "Follow-through day +1.5% (20 days)", ("ftd", 1.5, 20)); boost("O'Neil", "Follow-through day +1.25% (20 days)", ("ftd", 1.25, 20))
boost("O'Neil", "Follow-through day +1.5% (40 days)", ("ftd", 1.5, 40))
boost("Capitulation", "Volume 2x avg on a down day below 200d (10 days)", ("capit", 2.0, 10)); boost("Capitulation", "Volume 1.5x avg down day below 200d (5 days)", ("capit", 1.5, 5))
boost("Recovery", "Half of a 20%+ bear recovered (63 days)", ("recov", 0.5)); boost("Recovery", "A third of a 20%+ bear recovered (63 days)", ("recov", 0.33))
boost("Buffett", "QQQ 30%+ below high and up on the week", ("crashbuy", 0.30)); boost("Buffett", "QQQ 40%+ below high and up on the week", ("crashbuy", 0.40))
# --- calendar not tested before
boost("Calendar", "Earnings season (weeks 2-5 of quarter)", ("earn",)); boost("Calendar", "Midterm-year Q4", ("midq4",)); cap("Calendar", "September", ("sept",))
# --- ensembles: k of n votes
RISK = (("turb", 0.90), ("breadth", 0.5), ("notdeep", 0.15), ("vol_fall",), ("skew", -0.5))
MACRO = (("lead", "EEM"), ("copper",), ("tech_lead",), ("yld_down",), ("usd_calm", 0.03))
for k in (3, 4, 5):
    add("Ensemble", f"Risk vote {k} of 5 (turbulence, breadth, drawdown, vol, skew): TQQQ max 50% when off", cap_sig=(("vote", k, RISK), 0.5))
    add("Ensemble", f"Risk vote {k} of 5: split 60/40", split_sig=(("vote", k, RISK), 0.6, 0.4))
three("Ensemble", "Macro vote 3 of 5 (EEM, copper, tech lead, yields, dollar)", ("vote", 3, MACRO))
TECH = (("adx", 25), ("supertrend", 10, 3), ("ath", 0.05), ("sharpe", 1.0), ("accel",))
add("Ensemble", "Technical vote 4 of 5 (ADX, supertrend, 52w high, Sharpe, acceleration): full TQQQ", boost_sig=("vote", 4, TECH))
add("Ensemble", "Technical vote 5 of 5: full TQQQ", boost_sig=("vote", 5, TECH))
# --- structural
for a_, f_ in (("SOXL", 1.0), ("SOXL", 0.5), ("TQQQ", 1.0), ("TQQQ", 0.5)): add("Fed swap", f"Fed day: also swap {f_:.0%} of 9Sig's bond/gold reserve into {a_}", res_swap=(a_, f_))
add("Fed swap", "Fed day swap into TECL", swap_asset=(("TECL", 1.0),)); add("Fed swap", "Fed day swap into UPRO", swap_asset=(("UPRO", 1.0),))
for lb, lo, hi in ((60, 0.4, 0.6), (120, 0.4, 0.6), (60, 0.3, 0.7)): add("Sleeve split", f"Sleeve risk parity ({lb}d vol, {lo:.0%}-{hi:.0%})", split_dyn=("rp", lb, lo, hi))
for lb in (63, 126, 252): add("Sleeve split", f"Tilt 10% toward the stronger sleeve ({lb}d)", split_dyn=("mom", lb, 0.10))
add("Sleeve split", "Tilt 10% toward the weaker sleeve (126d)", split_dyn=("mom", 126, -0.10))
for x in (0.40, 0.30, 0.60): add("Sleeve split", f"9Sig share {x:.0%} while its vol switch is de-risked", split_dyn=("state", x))
# --- combos fixed in advance
add("Combo", "Turbulence cap + follow-through boost", cap_sig=(("turb", 0.90), 0.5), boost_sig=("ftd", 1.5, 20))
add("Combo", "Breadth cap + Supertrend boost", cap_sig=(("breadth", 0.5), 0.5), boost_sig=("supertrend", 10, 3))
add("Combo", "Fed reserve swap (SOXL) + risk vote 4 of 5 cap", res_swap=("SOXL", 1.0), cap_sig=(("vote", 4, RISK), 0.5))
add("Combo", "Sleeve risk parity 60d + crash buy 30%", split_dyn=("rp", 60, 0.4, 0.6), boost_sig=("crashbuy", 0.30))
# --- account-level equity-curve rules (computed from v1.7's equity, see account())
ACC = [("Equity curve above 50d avg, else 50% cash", ("ma", 50, 0.5)), ("Equity curve above 100d avg, else 50% cash", ("ma", 100, 0.5)),
       ("Equity curve above 200d avg, else 50% cash", ("ma", 200, 0.5)), ("Equity curve above 100d avg, else all cash", ("ma", 100, 0.0)),
       ("Equity curve above 200d avg, else all cash", ("ma", 200, 0.0)), ("Account 6-month return > 0, else 50% cash", ("mom", 126, 0.5)),
       ("Account 12-month return > 0, else 50% cash", ("mom", 252, 0.5))] + \
      [(f"Account vol target {v:.0%} (20d)", ("vt", v)) for v in (0.30, 0.40, 0.50, 0.60)] + \
      [(f"Account drawdown > {x:.0%}: 50% cash until above 50d avg", ("dd", x)) for x in (0.20, 0.30)] + \
      [("Equity curve 20d avg above 100d avg, else 50% cash", ("x", 20, 100))]

def account(eq, rf, rule):
    r = eq.pct_change().fillna(0.0); rf = rf.reindex(eq.index).fillna(0.0); k = pd.Series(1.0, index=eq.index)
    if rule[0] == "ma": k[:] = np.where(eq > eq.rolling(rule[1]).mean(), 1.0, rule[2])
    elif rule[0] == "mom": k[:] = np.where(eq / eq.shift(rule[1]) - 1 > 0, 1.0, rule[2])
    elif rule[0] == "vt": k = (rule[1] / (r.rolling(20).std() * np.sqrt(252))).clip(upper=1.0)
    elif rule[0] == "x": k[:] = np.where(eq.rolling(rule[1]).mean() > eq.rolling(rule[2]).mean(), 1.0, 0.5)
    else:
        off = False; ma = eq.rolling(50).mean(); pk = eq.cummax(); kv = []
        for i in range(len(eq)):
            if not off and eq.iloc[i] / pk.iloc[i] - 1 < -rule[1]: off = True
            elif off and eq.iloc[i] > ma.iloc[i]: off = False
            kv.append(0.5 if off else 1.0)
        k[:] = kv
    k = k.fillna(1.0).shift(1).fillna(1.0)     # decided at today's close, applies from tomorrow
    rn = k * r + (1 - k) * rf - k.diff().abs().fillna(0.0) * 0.0005
    return eq.iloc[0] * (1 + rn).cumprod()

if __name__ == "__main__":
    jobs = []
    for sk, (kw, lg) in SC.items():
        jobs.append((("BASELINE", sk), V17, kw, lg))
        for g, n, ov, long_ok in I:
            if sk == "88" and not long_ok: continue
            jobs.append(((n, sk), {**V17, **ov}, kw, lg))
    if len(sys.argv) > 1:
        jobs = [((n, "10"), {**V17, **ov}, dict(start="2023-06-01"), False) for g, n, ov, _ in I] + [((n, "88"), {**V17, **ov}, dict(start="1994-06-01", end="1995-06-30"), True) for g, n, ov, lo in I if lo]
    print(len(I) + len(ACC), "ideas,", len(jobs), "runs", flush=True); res = {}; t = time.time()
    with mp.Pool(15) as pool:
        for i, (k, eq) in enumerate(pool.imap_unordered(work, jobs), 1):
            res[k] = eq
            if i % 50 == 0: print(f"[{i}/{len(jobs)} {time.time()-t:4.0f}s]", flush=True)
    if len(sys.argv) > 1: print("smoke ok"); sys.exit()
    import bt
    RF = {"00": bt.PANEL["RF"], "10": bt.PANEL["RF"], "88": pd.read_pickle(os.path.join(HERE, "data", "panel_long.pkl"))["RF"]}
    for n, rule in ACC:
        for sk in SC: res[(n, sk)] = account(res[("BASELINE", sk)], RF[sk], rule)
    I += [("Account", n, {}, True) for n, _ in ACC]
    pickle.dump(res, open(os.path.join(OUT, "round11.pkl"), "wb"))
    B = {sk: metrics(res[("BASELINE", sk)]) for sk in SC}
    rows = []
    for g, n, ov, long_ok in [("Base", "BASELINE", {}, True)] + I:
        m = {sk: metrics(res[(n, sk)]) if (n, sk) in res else None for sk in SC}
        d = {sk: (m[sk]["cagr"] - B[sk]["cagr"]) if m[sk] else None for sk in SC}
        dd = {sk: (m[sk]["maxdd"] - B[sk]["maxdd"]) if m[sk] else None for sk in SC}
        ret = d["00"] >= 0.005 and d["10"] >= 0.005 and (d["88"] is None or d["88"] >= -0.005) and all(x is None or x >= -0.03 for x in dd.values())
        risk = all(m[sk] is None or (m[sk]["martin"] > B[sk]["martin"] and d[sk] >= -1e-4) for sk in SC)
        rows.append(dict(group=g, idea=n, cagr00=m["00"]["cagr"], dd00=m["00"]["maxdd"], d00=d["00"], cagr10=m["10"]["cagr"], dd10=m["10"]["maxdd"], d10=d["10"],
                         cagr88=m["88"]["cagr"] if m["88"] else np.nan, dd88=m["88"]["maxdd"] if m["88"] else np.nan, d88=d["88"] if d["88"] is not None else np.nan,
                         martin00=m["00"]["martin"], verdict=("PASS return " if ret else "") + ("PASS risk" if risk else "") if n != "BASELINE" else ""))
    df = pd.DataFrame(rows); df.to_csv(os.path.join(OUT, "round11.csv"), index=False)
    show = df.copy()
    for c in ["cagr00", "dd00", "d00", "cagr10", "dd10", "d10", "cagr88", "dd88", "d88"]: show[c] = (show[c] * 100).round(1)
    show["martin00"] = show["martin00"].round(2)
    pd.set_option("display.width", 300); pd.set_option("display.max_rows", 300)
    print(show.sort_values("d00", ascending=False).to_string(index=False))
