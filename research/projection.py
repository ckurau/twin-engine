"""25-year Monte Carlo for v1.5: 12-month block bootstrap of the engine's monthly returns (2000-2026, 0.05%/fill),
$20,000 start + $200 at the start of each month. Haircut = backtest CAGR minus N points (applied evenly per month)."""
import os, pickle, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__))
res = pickle.load(open(os.path.join(HERE, "out", "round3.pkl"), "rb"))
eq = res[("A: SOXL swap + monthly + dip 20", "2000-26")][1]
m = eq.resample("ME").last(); r = m.pct_change().dropna().values
yrs = (m.index[-1] - m.index[0]).days / 365.25; cagr = (m.iloc[-1] / m.iloc[0]) ** (1 / yrs) - 1
YEARS, N, START, CONTRIB = 25, 20000, 20000.0, 200.0
rng = np.random.default_rng(7)
blocks = np.array([r[i:i + 12] for i in range(len(r) - 11)])
idx = rng.integers(0, len(blocks), size=(N, YEARS))
paths = blocks[idx].reshape(N, YEARS * 12)

def simulate(cut):
    f = ((1 + cagr - cut) / (1 + cagr)) ** (1 / 12)
    R = (1 + paths) * f - 1
    v = np.full(N, START); out = []; peak = v.copy(); worst = np.zeros(N)
    for k in range(YEARS * 12):
        v = (v + CONTRIB) * (1 + R[:, k])
        peak = np.maximum(peak, v); worst = np.minimum(worst, v / peak - 1)
        if (k + 1) % 12 == 0: out.append(v.copy())
    return np.array(out), worst

real, worst = simulate(0.08); cons, _ = simulate(0.15); raw, _ = simulate(0.0)
rows = []
for y in range(YEARS):
    put_in = START + CONTRIB * 12 * (y + 1)
    v = real[y]
    rows.append(dict(year=y + 1, ending=f"Oct {2027 + y}", contributed=put_in, median=np.median(v), profit=np.median(v) - put_in,
                     p10=np.percentile(v, 10), p90=np.percentile(v, 90), conservative=np.median(cons[y]), no_haircut=np.median(raw[y])))
df = pd.DataFrame(rows)
pd.set_option("display.width", 200)
print(f"v1.5 backtest CAGR {cagr*100:.1f}% (monthly returns {m.index[0]:%Y-%m}..{m.index[-1]:%Y-%m}); realistic = minus 8 pts, conservative = minus 15 pts")
print(df.to_string(index=False, formatters={c: (lambda x: f"${x:,.0f}") for c in ["contributed", "median", "profit", "p10", "p90", "conservative", "no_haircut"]}))
fv = real[-1]
print(f"\nrealistic: median CAGR on money-weighted basis ~; paths with a drop worse than -50% at some point: {(worst < -0.5).mean():.0%}; median worst drop {np.median(worst)*100:.0f}%")
print(f"paths ending below money put in (${START + CONTRIB*12*YEARS:,.0f}): {(fv < START + CONTRIB*12*YEARS).mean():.1%}")
print(f"median with no contributions after start: compare -> run separately")
df.to_csv(os.path.join(HERE, "out", "projection_v15.csv"), index=False)
