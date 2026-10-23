"""Round 14: stagflation / slow-bear defences. Scored on 1972-91 and 1972-82 (panel_70s.pkl), the synthetic stagflation
panel (stress.py, 2000-26) and the usual 2000-26 / 2010-26 / 1988-99."""
import os, sys, time, pickle, multiprocessing as mp
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); OUT = os.path.join(HERE, "out")
from round9 import V17
from round6 import metrics
I = []
def add(g, n, **ov): I.append((g, n, ov))
UP = ("yld_down",)   # True = 10y yield below its 200d (rates not rising)
# A. slow-bear protection for 9Sig (the 1973-74 failure: low volatility, steady decline)
for c in (0.5, 0.25, 0.0): add("Slow bear", f"TQQQ max {c:.0%} when QQQ dual trend is down", nine_dual_cap=c)
for c in (0.5, 0.0): add("Slow bear", f"TQQQ max {c:.0%} when QQQ below 200d", growth_trend_cap=c)
add("Slow bear", "Quarterly TQQQ buys skipped when QQQ dual trend is down", q_gate="skip_buys")
add("Slow bear", "Quarterly TQQQ buys halved when QQQ dual trend is down", q_gate="half_buys")
add("Slow bear", "TQQQ max 50% when QQQ >20% below its high", cap_sig=(("notdeep", 0.20), 0.5))
add("Slow bear", "TQQQ max 50% when QQQ below 200d and >15% below high", cap_sig=(("vote", 2, (("notdeep", 0.15), ("stage2",))), 0.5))
add("Slow bear", "Split 40/60 when QQQ below 200d", regime_split=(0.5, 0.4))
add("Slow bear", "Year-end reset only half way", reset_frac=0.5)
# B. inflation regime (rising yields / stocks and bonds together)
add("Inflation", "Rising 10y yield: reserve gold + T-bills", res_sig=(UP, ("GLD", "BIL")))
add("Inflation", "Rising 10y yield: reserve T-bills", res_sig=(UP, ("BIL",)))
add("Inflation", "Stock/bond corr > 0: reserve gold + T-bills", res_sig=(("sbc", 60, 0.0), ("GLD", "BIL")))
add("Inflation", "Fed hiking fast: reserve gold + T-bills", res_sig=(("hiking", 1.0), ("GLD", "BIL")))
add("Inflation", "Rising 10y yield: LDS drops TLT", lds_gate={"TLT": UP})
add("Inflation", "Rising 10y yield: vol target 60%", vt_sig=(UP, 0.80, 0.60))
add("Inflation", "Rising 10y yield: TQQQ max 50%", cap_sig=(UP, 0.5))
add("Inflation", "Rising 10y yield: split 40/60", split_sig=(UP, 0.5, 0.4))
add("Inflation", "Stock/bond corr vol target 85/75", vt_sig=(("sbc", 60, 0.0), 0.85, 0.75))
add("Inflation", "Reserve gold + T-bills always", defensive=("GLD", "BIL"))
add("Inflation", "Reserve TLT + gold + T-bills always", defensive=("TLT", "GLD", "BIL"))
add("Inflation", "Idle cash earns T-bill interest", cash_yield=True)
# C. combos fixed in advance
add("Combo", "Quarterly buys skipped in downtrend + rising yield reserve gold/T-bills", q_gate="skip_buys", res_sig=(UP, ("GLD", "BIL")))
add("Combo", "TQQQ max 50% in QQQ downtrend + rising-yield reserve gold/T-bills", nine_dual_cap=0.5, res_sig=(UP, ("GLD", "BIL")))
add("Combo", "TQQQ max 50% in downtrend + LDS drops TLT when yields rise", nine_dual_cap=0.5, lds_gate={"TLT": UP})
add("Combo", "Skip buys in downtrend + TQQQ max 50% >20% below high", q_gate="skip_buys", cap_sig=(("notdeep", 0.20), 0.5))
add("Combo", "Skip buys + rising yield: TQQQ max 50% + reserve gold/T-bills", q_gate="skip_buys", cap_sig=(UP, 0.5), res_sig=(UP, ("GLD", "BIL")))

SC = {"00": ("std", dict(start="2000-01-03")), "10": ("std", dict(start="2010-03-12")), "88": ("long", dict(start="1988-01-04", end="1999-12-31")),
      "70s": ("p70", dict(start="1972-01-03")), "stag": ("stag", dict(start="2000-01-03"))}
PN = {}
def work(a):
    import bt, stress
    key, ov, kind, kw = a
    try:
        if kind not in PN:
            PN[kind] = (bt.PANEL if kind == "std" else bt.add_signal_cols(pd.read_pickle(os.path.join(HERE, "data", "panel_long.pkl"))) if kind == "long"
                        else pd.read_pickle(os.path.join(HERE, "data", "panel_70s.pkl")) if kind == "p70" else stress.make("stagflation", bt.PANEL))
        return key, bt.run(ov, panel=PN[kind], **kw)["equity"]
    except Exception as e:
        print("FAILED", key, str(e)[:150], flush=True); return key, None

if __name__ == "__main__":
    jobs = [((n, sk), {**V17, **ov}, kind, kw) for g, n, ov in [("Base", "BASELINE", {})] + I for sk, (kind, kw) in SC.items()]
    print(len(I), "ideas,", len(jobs), "runs", flush=True); res = {}; t = time.time()
    with mp.Pool(15) as pool:
        for i, (k, eq) in enumerate(pool.imap_unordered(work, jobs), 1):
            if eq is not None: res[k] = eq
            if i % 25 == 0: print(f"[{i}/{len(jobs)} {time.time()-t:4.0f}s]", flush=True)
    pickle.dump(res, open(os.path.join(OUT, "round14.pkl"), "wb"))
    def seg(e, a, b): x = e.loc[a:b]; return metrics(x)
    rows = []
    for g, n, ov in [("Base", "BASELINE", {})] + I:
        if any((n, sk) not in res for sk in SC): print("missing", n); continue
        m = {sk: metrics(res[(n, sk)]) for sk in SC}; s72 = seg(res[(n, "70s")], "1972-01-03", "1982-08-12"); c74 = seg(res[(n, "70s")], "1973-01-11", "1974-12-06")
        rows.append(dict(group=g, idea=n, **{f"{sk}": f"{m[sk]['cagr']*100:.1f}/{m[sk]['maxdd']*100:.0f}" for sk in SC},
                         **{"72-82": f"{s72['cagr']*100:.1f}/{s72['maxdd']*100:.0f}", "73-74 loss": f"{(res[(n, '70s')].loc['1974-12-06'] / res[(n, '70s')].loc['1973-01-11'] - 1)*100:.0f}%"},
                         d00=m["00"]["cagr"], d10=m["10"]["cagr"], d88=m["88"]["cagr"], dd70=m["70s"]["maxdd"], c70=m["70s"]["cagr"]))
    df = pd.DataFrame(rows); b = df.iloc[0]
    for c in ("d00", "d10", "d88"): df[c] = ((df[c] - b[c]) * 100).round(1)
    df["dd70"] = (df["dd70"] * 100).round(0); df["c70"] = (df["c70"] * 100).round(1)
    df.to_csv(os.path.join(OUT, "round14.csv"), index=False)
    pd.set_option("display.width", 320); pd.set_option("display.max_colwidth", 70); pd.set_option("display.max_rows", 100)
    print(df.drop(columns=["group"]).sort_values("dd70", ascending=False).to_string(index=False))
