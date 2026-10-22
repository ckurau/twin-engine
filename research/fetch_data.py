"""Download daily history for the research backtests (adjusted + raw closes) into research/data/."""
import os, sys, time, pandas as pd, yfinance as yf
OUT = os.path.join(os.path.dirname(__file__), "data")
T = """^XAU QQQ ^NDX SPY ^GSPC TLT VUSTX GLD GC=F IEF VFITX ^IRX ^VIX BIL SHY VFISX EFA EEM VEIEX XLK ^SOX SOXX XLU VWO DBC
UUP VNQ IWM ^RUT XLE XLV XLF ^DJI DIA VGSIX FSPTX FSELX VGPMX
TQQQ QLD SQQQ PSQ QID UPRO SSO SPXU SH SDS TMF UBT TMV TBF TBT UGL GLL TECL SOXL TYD EDC EURL UTSL TNA FAS ERX CURE UDOW""".split()
frames = {}
for t in T:
    for i in range(3):
        try:
            d = yf.download(t, period="max", auto_adjust=False, progress=False)
            if len(d): break
        except Exception as e: print(t, e)
        time.sleep(3)
    if not len(d): print("FAILED", t); continue
    d.columns = [c[0] if isinstance(c, tuple) else c for c in d.columns]
    frames[t] = d[["Adj Close", "Close"]]
    print(f"{t:6s} {d.index[0].date()} .. {d.index[-1].date()}  {len(d)} rows")
adj = pd.DataFrame({t: f["Adj Close"] for t, f in frames.items()}); close = pd.DataFrame({t: f["Close"] for t, f in frames.items()})
adj.index = pd.DatetimeIndex(adj.index).tz_localize(None).normalize(); close.index = adj.index
adj.to_pickle(os.path.join(OUT, "adj.pkl")); close.to_pickle(os.path.join(OUT, "close.pkl"))
print("saved", adj.shape)
