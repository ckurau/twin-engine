"""te_lab with the v1.5 switches (SOXL swap, monthly LDS, dip boost 20) must reproduce the production engine."""
import time, bt
A = dict(swap_asset=(("SOXL", 1.0),), lds_freq="month", nine_dip=20)
t = time.time(); a = bt.run(lab=False); b = bt.run(A, lab=True)
print("production:", bt.fmt(a)); print("lab       :", bt.fmt(b), f" [{time.time()-t:.0f}s]")
d = (b["equity"] / a["equity"] - 1).abs()
print("max daily equity difference:", f"{d.max()*100:.3f}%", "on", d.idxmax().date())
