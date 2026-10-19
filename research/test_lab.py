"""te_lab with default switches must reproduce the production engine."""
import time, bt
t = time.time(); a = bt.run(lab=False); b = bt.run(lab=True)
print("production:", bt.fmt(a)); print("lab       :", bt.fmt(b), f" [{time.time()-t:.0f}s]")
d = (b["equity"] / a["equity"] - 1).abs()
print("max daily equity difference:", f"{d.max()*100:.3f}%", "on", d.idxmax().date())
