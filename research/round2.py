"""Round 2: combinations of round-1 near misses + new ideas. Same acceptance rules as round 1."""
import pandas as pd
from ideas import run_batch
M = dict(lds_freq="month"); D20 = dict(nine_dip=20); D10 = dict(nine_dip=10); S55 = dict(split_9sig=0.55)
G = dict(defensive=("GLD",)); OL = dict(overlay_long_only=True); X = dict(swap_asset=(("SOXL", 1.0),)); DD = dict(swap_dip=(5, 50))
def c(*ds):
    o = {}
    for d in ds: o.update(d)
    return o
IDEAS = [
    ("Combo", "Monthly LDS + dip boost 20", c(M, D20)), ("Combo", "Monthly LDS + dip boost 10", c(M, D10)),
    ("Combo", "Monthly LDS + 55/45", c(M, S55)), ("Combo", "Dip boost 20 + 55/45", c(D20, S55)),
    ("Combo", "Monthly LDS + dip boost 20 + 55/45", c(M, D20, S55)), ("Combo", "Monthly LDS + dip boost 20 + GLD defensive", c(M, D20, G)),
    ("Combo", "Monthly LDS + dip boost 20 + long-only overlay", c(M, D20, OL)), ("Combo", "Monthly + dip 20 + 55/45 + long-only", c(M, D20, S55, OL)),
    ("Combo", "SOXL Fed swap + dip boost 20", c(X, D20)), ("Combo", "SOXL Fed swap + monthly LDS", c(X, M)), ("Combo", "SOXL Fed swap + monthly + dip 20", c(X, M, D20)),
    ("Combo", "Monthly LDS + deep-dip LDS swap", c(M, DD)), ("Combo", "Dip boost 20 + deep-dip LDS swap", c(D20, DD)),
    ("Combo", "Monthly + dip 20 + deep-dip swap", c(M, D20, DD)),
    ("Combo", "Dip boost 20 + vol power 20", c(D20, dict(vol_power=20.0))), ("Combo", "Dip boost 20 + vol target 85%", c(D20, dict(vol_target=0.85))),
    ("Combo", "Dip boost 20 + trend avg 240d", c(D20, dict(sma_days=240))),
    ("9Sig", "Dip boost: RSI2 < 15", dict(nine_dip=15)), ("9Sig", "Dip boost: RSI2 < 25", dict(nine_dip=25)), ("9Sig", "Dip boost: RSI2 < 30", dict(nine_dip=30)),
    ("9Sig", "Dip boost RSI2 < 10, hold until > 50", dict(nine_dip=10, nine_dip_exit=50)), ("9Sig", "Dip boost RSI2 < 20, hold until > 50", dict(nine_dip=20, nine_dip_exit=50)),
    ("9Sig", "Dip boost RSI2 < 10, hold until > 70", dict(nine_dip=10, nine_dip_exit=70)),
    ("9Sig", "Vol switch on VIX x 3 (implied)", dict(vol_vix=True)), ("9Sig", "Vol switch on VIX x 3, target 90%", dict(vol_vix=True, vol_target=0.9)),
    ("9Sig", "Vol switch on VIX x 3, target 70%", dict(vol_vix=True, vol_target=0.7)),
    ("9Sig", "Vol switch EWMA (half-life 10d)", dict(vol_ewm_hl=10)), ("9Sig", "Vol switch EWMA (half-life 20d)", dict(vol_ewm_hl=20)),
    ("9Sig", "Seasonal: vol target 90% Nov-Apr", dict(vol_target_winter=0.90)), ("9Sig", "Seasonal: 90% Nov-Apr, 70% May-Oct", dict(vol_target_winter=0.90, vol_target=0.70)),
    ("9Sig", "TOM boost only in uptrend", dict(tom_trend=True)),
    ("Swap", "Fed swap only when QQQ > 200d", dict(swap_fomc_trend=True)), ("Swap", "Fed swap 50% of LDS", dict(swap_frac=0.5)),
    ("Swap", "Fed swap into SOXL, 50% of LDS", dict(swap_asset=(("SOXL", 1.0),), swap_frac=0.5)), ("Swap", "Fed swap into TQQQ + SOXL", dict(swap_asset=(("TQQQ", 0.5), ("SOXL", 0.5)))),
    ("LDS", "Core equal-weight (not inverse-vol)", dict(core_ew=True)), ("LDS", "Monthly review + threshold 2.5%", dict(lds_freq="month", lds_threshold=0.025)),
    ("LDS", "Monthly review + threshold 10%", dict(lds_freq="month", lds_threshold=0.10)), ("LDS", "Monthly review + long-only overlay", c(M, OL)),
    ("Split", "52.5 / 47.5", dict(split_9sig=0.525)), ("Split", "57.5 / 42.5", dict(split_9sig=0.575)),
]
if __name__ == "__main__":
    df = run_batch(IDEAS, "round2")
    pd.set_option("display.width", 250); pd.set_option("display.max_rows", 300)
    show = df.assign(**{k: (df[k] * 100).round(1) for k in ["cagr", "maxdd", "cagr07", "maxdd07", "h1", "h2", "d_cagr", "d_dd", "d_dd07"]})
    print(show.sort_values("d_cagr", ascending=False)[["group", "idea", "cagr", "maxdd", "cagr07", "maxdd07", "d_cagr", "d_dd", "d_dd07", "wins", "h1", "h2", "trade_days", "passed"]].to_string(index=False))
