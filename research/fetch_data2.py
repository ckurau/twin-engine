"""Extra series for round 4: VIX term structure, VVIX, credit and bond proxies, long-vol ETFs, QQQ high/low."""
import os, time, pandas as pd, yfinance as yf
OUT = os.path.join(os.path.dirname(__file__), "data")
S = {}
for t in ["^VIX3M", "^VVIX", "VWEHX", "VBMFX", "VIXY", "TAIL", "VXX", "AGG"]:
    for i in range(3):
        d = yf.download(t, period="max", auto_adjust=False, progress=False)
        if len(d): break
        time.sleep(3)
    if not len(d): print("FAILED", t); continue
    d.columns = [c[0] if isinstance(c, tuple) else c for c in d.columns]
    S[t] = d["Adj Close"]; print(f"{t:7s} {d.index[0].date()} .. {d.index[-1].date()}")
q = yf.download("QQQ", period="max", auto_adjust=False, progress=False); q.columns = [c[0] if isinstance(c, tuple) else c for c in q.columns]
S["QQQ_H"], S["QQQ_L"], S["QQQ_C"] = q["High"], q["Low"], q["Close"]
df = pd.DataFrame(S); df.index = pd.DatetimeIndex(df.index).tz_localize(None).normalize()
df.to_pickle(os.path.join(OUT, "extra.pkl")); print(df.shape)
