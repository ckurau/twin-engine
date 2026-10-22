"""Round 8, batch 2: neighbours and stacks of the batch-1 near misses (Santa window, dual trend average, fear premium),
plus the stacks with a 55/45 or 60/40 split (the only direct lever toward 40% CAGR). Same scoring as round 8."""
from round8 import runjobs
I = []
def add(g, n, **ov): I.append((g, n, ov))
S = dict(santa=True); DU = dict(core_trend="dual"); VR = dict(vrp=(1.5, 1.0))
for d0, nj in ((15, 2), (18, 2), (20, 2), (22, 1), (22, 3), (24, 2), (20, 3)): add("Santa", f"Santa window Dec {d0} - January session {nj}", santa=(d0, nj))
for f in (20, 30, 75, 100, 150): add("Dual trend", f"LDS trend needs {f}d > 210d too", core_trend="dual", dual_fast=f)
for r_, hi in ((1.4, 1.0), (1.6, 1.0), (1.8, 1.0), (1.5, 0.95), (2.0, 1.0)): add("Fear premium", f"VIX > {r_}x realized vol -> target {hi:.0%}", vrp=(r_, hi))
add("Stack", "Santa + dual trend", **S, **DU)
add("Stack", "Santa + fear premium 1.5x", **S, **VR)
add("Stack", "Dual trend + fear premium 1.5x", **DU, **VR)
add("Stack", "Santa + dual trend + fear premium 1.5x", **S, **DU, **VR)
add("Stack", "Santa + dual + growth target 10%/6%", **S, **DU, sig_rate_trend=(0.10, 0.06))
add("Stack", "Santa + dual + reserve by inverse vol", **S, **DU, def_invvol=True)
add("Stack", "Santa + dual + drop correlated Treasuries", **S, **DU, lds_corr_cut=True)
add("Stack", "Santa + dual + vol target 85%", **S, **DU, vol_target=0.85)
for sp in (0.55, 0.60, 0.65):
    add("Stack + split", f"Santa + dual, {sp:.0%}/{1-sp:.0%} split", **S, **DU, split_9sig=sp)
    add("Stack + split", f"Santa + dual + fear premium, {sp:.0%}/{1-sp:.0%} split", **S, **DU, **VR, split_9sig=sp)
    add("Stack + split", f"Santa, {sp:.0%}/{1-sp:.0%} split", **S, split_9sig=sp)
add("Stack + split", "Santa + dual, 60/40, vol target 85%", **S, **DU, split_9sig=0.60, vol_target=0.85)
add("Stack + split", "Santa + dual, 70/30", **S, **DU, split_9sig=0.70)
add("Stack + split", "Santa + dual + fear premium, 70/30", **S, **DU, **VR, split_9sig=0.70)
if __name__ == "__main__":
    runjobs(I, "round8b")
