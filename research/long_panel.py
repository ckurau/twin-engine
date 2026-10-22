"""Panel back to 1986 for out-of-sample tests (1988-1999 was never used to design the strategy).
Gold before Aug 2000 is the gold-miners index scaled to gold's volatility (rough), Treasuries = Vanguard long Treasury fund."""
import os, pandas as pd, synth
synth.START = "1986-06-01"
px, rf = synth.build(verbose=False)
HERE = os.path.dirname(os.path.abspath(__file__))
X = pd.read_pickle(os.path.join(HERE, "data", "extra.pkl")).reindex(px.index); A = pd.read_pickle(os.path.join(HERE, "data", "adj.pkl")).reindex(px.index)
px["VIXLVL"] = A["^VIX"].ffill()
for c, src in [("VIX3M", X["^VIX3M"]), ("VVIX", X["^VVIX"]), ("VWEHX", X["VWEHX"]), ("VBMFX", X["VBMFX"]), ("VFITX", A["VFITX"])]: px[c] = src.ffill()
for c in ("QQQ_H", "QQQ_L", "QQQ_C"): px[c] = X[c]
px["RF"] = rf.reindex(px.index).fillna(0.0)
px.to_pickle(os.path.join(HERE, "data", "panel_long.pkl")); print(px.shape, px.index[0].date(), px[["SPY", "QQQ", "TLT", "GLD", "TQQQ", "UPRO", "TMF", "UGL"]].apply(lambda s: s.first_valid_index().date()).to_dict())
