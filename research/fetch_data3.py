"""Round 10 signals: Dow transports, copper, dollar index, 10-year yield, QQQ volume and high/low/close (already in extra.pkl)."""
import os, time, pandas as pd, yfinance as yf
OUT = os.path.join(os.path.dirname(__file__), "data"); S = {}
for t in ["^DJT", "^DJI", "HG=F", "GC=F", "DX-Y.NYB", "^TNX", "^IRX", "QQQ", "^NDX"]:
    for i in range(3):
        d = yf.download(t, period="max", auto_adjust=False, progress=False)
        if len(d): break
        time.sleep(3)
    if not len(d): print("FAILED", t); continue
    d.columns = [c[0] if isinstance(c, tuple) else c for c in d.columns]
    if t in ("QQQ", "^NDX"):
        S[t + "_V"] = d["Volume"]; S[t + "_H"] = d["High"]; S[t + "_L"] = d["Low"]; S[t + "_C"] = d["Close"]
    else: S[t] = d["Close"]
    print(f"{t:9s} {d.index[0].date()} .. {d.index[-1].date()}")
df = pd.DataFrame(S); df.index = pd.DatetimeIndex(df.index).tz_localize(None).normalize(); df.to_pickle(os.path.join(OUT, "extra3.pkl")); print(df.shape)
