# Twin Engine — Paper Trading Guide

**Strategy:** 50% Modified 9Sig (+ Turn-of-Month) / 50% Leveraged Diversification Strategy (LDS)
**Account plan:** $20,000 start, optional $200/month, Roth IRA (taxes make it unsuitable for a taxable account — see §8)
**Status:** paper trading (no broker orders are sent)

> Not financial advice. Backtests overstate live results. Leveraged ETFs can lose most of their value quickly.

---

## 1. What you're running, in one paragraph

Two independent "engines" share one account and are reset to 50/50 at each year end.
**Engine 1 – Modified 9Sig** holds TQQQ in a *growth* sub-sleeve and TLT + GLD in a *defensive* reserve. Every quarter the growth sub-sleeve must grow 9%: excess is sold into the reserve, shortfalls are bought from it. Inside the growth sub-sleeve a **volatility switch** shrinks TQQQ when Nasdaq volatility spikes, a **turn-of-month (TOM)** rule holds full TQQQ around month-end, and a **dip boost** holds full TQQQ for a session after a sharp short-term drop in an uptrend.
**Engine 2 – LDS** checks the S&P 500, long Treasuries and gold at each month-end close (v1.6: no Nasdaq-100, which Engine 1 already holds); it holds the ones above their 210-day average whose 30-day average is also above it (v1.7), sized by inverse volatility and levered up with 3x/2x ETFs (UPRO, TMF, UGL), plus a small long/short momentum overlay (can use SPXU, TMV, GLL). On each scheduled **Fed decision day** (8 a year) the whole LDS sleeve is held in SOXL (3x semiconductors) for that one day.

### Expected behaviour (backtest of v1.7.0, $20k start, no deposits)

The same numbers, plus a growth chart, trading metrics and calendar years, are on the dashboard's **Research** tab (from `backtest.json`; regenerate with `research\backtest_export.py` after any rule change).

| Scenario | $20k became | CAGR | Max drawdown |
|---|---|---|---|
| 2000-2026 | $114.5M | 38.1% | −36.4% |
| 2007-2026 (fresh start) | $25.6M | 43.5% | −32.8% |
| 2010-2026 (real ETFs only) | $4.8M | 39.1% | −32.8% |
| 2000-2026, double trading costs | $83.8M | 36.5% | −37.6% |
| SPY, 2000-2026 | $170k | 8.3% | −55.2% |

Before 2010 the leveraged ETFs are rebuilt from their indexes (calibrated to the real funds); from March 2010 every ETF is the real fund, so **2010–2026 is the most honest row**. Ten-year windows (starts 2000–2016): worst 31.3%, median 37.8%, best 45.9% CAGR. Ulcer index 11.6, Martin ratio 3.29. Worst 5% of 12-month periods: -8.9%.

**Through the crashes** (worst drop inside the period / start to end, vs SPY start to end):

| Period | Worst drop | Start → end | SPY |
|---|---|---|---|
| Dot-com crash | −36.4% | +4.0% | −47.5% |
| 2008 financial crisis | −25.9% | +50.0% | −55.2% |
| Q4 2018 | −27.7% | −27.7% | −19.3% |
| Covid crash | −24.3% | −12.5% | −33.7% |
| 2022 bear market | −31.3% | −23.6% | −18.1% |

How a leveraged strategy fell less than SPY in 2000–02 and 2008: the volatility switch shrinks TQQQ as markets get choppy, and LDS only holds assets in a confirmed uptrend, so in long bear markets the account drifts into Treasuries and gold. **2022 and Q4 2018 were worse than SPY**: stocks and bonds fell together. A one-day crash like Oct 19, 1987 (S&P -20.5%, Nasdaq -20%, semiconductors -25%, Treasuries +2% in one day (like Oct 19, 1987)) applied to every day's holdings: typical loss -35%, 1 day in 10 -52%, worst -71%.

**Realistic live expectation:** ~20–30%/yr, and a 40–50% drop at some point is likely. The backtest's drawdown is one historical path, not a floor.

### 25-year projection (v1.7.0, $20,000 start + $200/month)

Monte Carlo: 20,000 paths that resample real 12-month blocks of the v1.7.0 backtest's monthly returns (2000–2026, 0.05% per fill). **Realistic** = backtest returns minus 8 points a year (edge decay, real-world fills). **Conservative** = minus 15 points. Balances at each anniversary, before inflation.

| Year | Ending | Put in | Realistic median | 10th – 90th percentile | Conservative median |
|---|---|---|---|---|---|
| 1 | Oct 2027 | $22,400 | $29k | $21k – $40k | $27k |
| 2 | Oct 2028 | $24,800 | $40k | $26k – $64k | $36k |
| 3 | Oct 2029 | $27,200 | $54k | $32k – $96k | $47k |
| 4 | Oct 2030 | $29,600 | $73k | $41k – $142k | $60k |
| 5 | Oct 2031 | $32,000 | $98k | $51k – $205k | $77k |
| 6 | Oct 2032 | $34,400 | $131k | $63k – $292k | $98k |
| 7 | Oct 2033 | $36,800 | $174k | $79k – $413k | $123k |
| 8 | Oct 2034 | $39,200 | $229k | $98k – $578k | $154k |
| 9 | Oct 2035 | $41,600 | $298k | $122k – $808k | $191k |
| 10 | Oct 2036 | $44,000 | $392k | $153k – $1.1M | $239k |
| 11 | Oct 2037 | $46,400 | $514k | $189k – $1.5M | $298k |
| 12 | Oct 2038 | $48,800 | $667k | $236k – $2.1M | $367k |
| 13 | Oct 2039 | $51,200 | $875k | $293k – $2.9M | $458k |
| 14 | Oct 2040 | $53,600 | $1.1M | $362k – $3.9M | $567k |
| 15 | Oct 2041 | $56,000 | $1.5M | $454k – $5.4M | $700k |
| 16 | Oct 2042 | $58,400 | $1.9M | $568k – $7.4M | $863k |
| 17 | Oct 2043 | $60,800 | $2.5M | $710k – $10.0M | $1.1M |
| 18 | Oct 2044 | $63,200 | $3.3M | $867k – $13.5M | $1.3M |
| 19 | Oct 2045 | $65,600 | $4.3M | $1.1M – $18.4M | $1.6M |
| 20 | Oct 2046 | $68,000 | $5.6M | $1.4M – $24.8M | $2.0M |
| 21 | Oct 2047 | $70,400 | $7.3M | $1.7M – $33.3M | $2.5M |
| 22 | Oct 2048 | $72,800 | $9.6M | $2.1M – $45.7M | $3.1M |
| 23 | Oct 2049 | $75,200 | $12.3M | $2.7M – $62.6M | $3.8M |
| 24 | Oct 2050 | $77,600 | $15.9M | $3.4M – $83.9M | $4.6M |
| 25 | Oct 2051 | $80,000 | $20.7M | $4.2M – $112.2M | $5.7M |

In the realistic case 5% of paths fall more than 50% at some point (typical worst drop -37%). This is a range, not a promise.

**Round 8 (Oct 21, 2026), 93 ideas aimed at 40% CAGR:** only the LDS "dual trend" passed every stress test (better CAGR and drawdown from 2000, 2003, 2007, 2010 and at double costs; >50%-drop odds in the 20-year simulation 9% → 4%); adopted as v1.7. Its gain comes after 2013 (2000–12: −0.7 pt). Rejected: Santa Claus rally (depends on the exact start date), fear premium (fragile), high-low / downside volatility, regime splits, mid-quarter 9Sig trades, weekly reversals, switch floors; 60/40 on top of v1.7 adds ~2% more money for double the >50%-drop odds.

**Tech-reliance check (Oct 21, 2026):** mixing non-tech 3x ETFs into 9Sig's growth engine (UPRO, UDOW, TNA, CURE, FAS, ERX) was worse when the volatility switch read the mix (2000–02 crash −28% to −63% vs −4.8%: TQQQ's volatility is the early warning). Keeping the switch on TQQQ while holding a mix costs 1.5–3 pts a year (TQQQ 75/UPRO 25: 34.8%; 50/50: 33.3%) for a similar drawdown, but halves Nasdaq concentration; its payoff would come only in a slow, crash-free tech slump the history doesn't contain. **Decision: keep v1.6 (TQQQ only).**

**Split check (Oct 19, 2026):** 60/40 and 70/30 were tested as ways to trade drawdown for return. After 20 years (realistic median, same deposits): 50/50 $4.08M, 60/40 $4.43M (+8%), 70/30 $4.57M (+12%); chance of a drop worse than 50%: 9%, 13%, 26%. **Decision: stay at 50/50.**

Replays use 0.05% slippage per fill (stricter than the engine's default 0.02%). Typical year: ~40 trade days.

---

## 2. Exact rules

All signals use **closing prices**. In paper trading all orders fill at that day's close (+2 bp slippage).

### 2.1 Sleeve split
- Start 50% / 50%. On the **last trading day of each year**, move cash so both sleeves are 50/50 again. (v1.3: was every quarter end. Yearly was better in 19 of 22 ten-year windows and gave smaller drawdowns in all 22.)
- Monthly contributions (if any) are split 50/50 on the first trading day of the month.

### 2.2 Engine 1 — Modified 9Sig + TOM
| Item | Rule |
|---|---|
| Structure | 9Sig sleeve = **growth sub-sleeve** (S) + **defensive reserve** (B). Start S = 60%, B = 40% |
| Defensive assets | B, plus any unused part of S, held **50% TLT / 50% GLD** |
| Quarterly signal (last trading day of quarter) | Target S = (S after last quarter's trade) × 1.09 + ½ × new contributions. If S > target → sell excess into B. If S < target → buy the shortfall from B (as far as B allows) |
| 30-down rule | If the growth sub-sleeve fell ≥ 30% during the quarter, ignore the next **4** sell signals |
| Volatility switch (daily) | vol20 = annualized std-dev of TQQQ's last 20 daily returns. TQQQ share of S = min(1, (0.80 / vol20)^10). Only change it if the new value differs by > 5 points. Remainder of S → TLT/GLD |
| Rough switch levels | vol20 ≤ 80% → 100% • 86% → ~50% • 90% → ~31% • ≥ 100% → ~10% |
| Turn-of-month | Hold TQQQ at 100% of S on the **last trading day of the month and the first 3 trading days** of the next (buy at the close the day before; return to switch size at the close of the 3rd day). Only matters when the switch is below 100% |
| Dip boost (v1.5) | If QQQ's **2-day RSI closes below 20** while QQQ is **above its 200-day average**, hold TQQQ at 100% of S for the next session (re-checked every close). Only matters when the switch is below 100% |

### 2.3 Engine 2 — LDS (checked at the close of the last trading day of each month; v1.3: each week)
1. **Trend:** for SPY, TLT, GLD (v1.6; v1.5 also QQQ) — is today's close ≥ its 210-day simple average **and** its 30-day average above the 210-day average (v1.7 dual trend)?
2. **Core (85%)**: uptrend assets get weight ∝ 1 / (63-day volatility). Scale the mix so its expected volatility = 100%/yr; the scale is capped by the leverage that exists (see step 4), so in practice it means "as much leverage as the ETFs allow."
3. **Overlay (15%)**: each asset long if the average of its 1-, 3-, 6- and 12-month returns > 0, short if < 0; weight ∝ 1/vol, scaled to 15% vol.
4. **Implement** combined exposures with the lowest common leverage tier that fits in 100% of the sleeve: 1x (SPY, QQQ, TLT, GLD) → 2x (SSO, QLD, UBT, UGL) → 3x (UPRO, TQQQ, TMF; gold max 2x UGL). Shorts use inverse ETFs (SH/SDS/SPXU, PSQ/QID/SQQQ, TBF/TBT/TMV, GLL). If even max leverage doesn't fit, everything is scaled down.
5. **Trade only if** the total change across positions is > 5% of the sleeve.
6. **Fed-day swap (v1.3; SOXL since v1.5):** at the close of the trading day **before** each scheduled FOMC decision, sell the whole LDS sleeve and buy **SOXL** (3x semiconductors; v1.3 used TQQQ). At the close of **decision day**, sell the SOXL and buy the normal LDS positions (fresh signal). A month-end review falling on that day is skipped because the sleeve was just rebuilt. Engine 1 is not affected. The dates are listed in `FOMC_DATES` in `twin_engine.py` (through Dec 2027). The Fed publishes next year's schedule each summer: add it once a year. The dashboard shows an "Action needed" banner when fewer than 3 dates are left.

   Why SOXL (v1.5): semiconductors have a higher beta, so they capture more of the Fed-day drift. Real SOXL averaged +1.11% on decision days since 2010 vs +0.65% for TQQQ; its worst decision day was −16% (TQQQ −10.8%). Because the LDS sleeve is half the account, the account's worst day in the replay did not get worse (−12.2% vs −12.3%).

   Why: Nasdaq rose on Fed decision days far more often than on normal days (TQQQ +0.97% average vs +0.12%, 60% up days, 1999–2026; first documented by Lucca & Moench, 2015). With costs it added +1.4 points of CAGR from 2000 and cut the max drawdown by ~7 points. It helped in both halves of history and in every 10-year window's drawdown. Most of the gain came in 2007–12 and 2020–26. If your fills cost more than ~0.10% per side, the CAGR gain disappears but the drawdown benefit remains.

### 2.4 What does NOT exist (on purpose)
No stop-losses, no profit targets, no discretionary overrides. Every exit comes from the rules above. About 330 other ideas tested (Idea Labs I–III: ~100 for v1.3, 155 for v1.5, ~80 more on Nasdaq concentration, crash signals, insurance and risk budget for v1.6). Crash-warning signals (VIX term structure, VVIX, credit spreads, Keller canary) all cost far more return than they saved; VIX/tail-risk ETFs cost 2.5–9 pts a year; QQQ puts are the cheapest insurance (~0.4 pt a year) but one contract (~$60k of QQQ) is too big for a $20k account — revisit around $100k (crash pauses, VIX sizing, put hedges, trend filters, Turtle/PTJ/Livermore rules, overnight trading, sell-in-May, extra assets, Bitcoin, more leverage, etc.) either failed walk-forward validation or only added return by adding leverage. The futures-based ones (LDS up to 5x, volatility-managed leverage) need $25k+ and a futures-approved IRA, and carry 1987-crash risk. They are parked for now.

---

## 3. Files

```
twin-engine/
  twin_engine.py       paper-trading engine (signals, paper fills, FIFO tax lots, ledger, order preview)
  index.html           dashboard (GitHub Pages; open on phone)
  state.json           engine state — created by "Start account", DO NOT edit by hand
  summary.json         dashboard data — rewritten by every daily run
  preview.json         today's orders, written ~45 min before the close
  backtest.json        backtest results for the dashboard's Backtest tab (research/backtest_export.py)
  research/            Idea Lab test harness: synthetic 1998-2026 history, idea switches, all rounds (data not in git)
  .github/workflows/   the four cloud jobs (below)
  requirements.txt
  README-twin-engine.md
```

Everything runs on GitHub's servers. No PC has to be on.

| Workflow | When | What it does |
|---|---|---|
| **Preview orders** | Weekdays ~3:15 PM ET / 12:15 PM PT (12:15 PM ET on 1:00 PM early-close days) | Takes live prices, runs today's close through the exact rules on a copy of the account, and lists the market-on-close orders. Shows them on the dashboard and opens a GitHub issue (→ phone notification) when there is something to place. Never changes the ledger |
| **Daily run** | Weekdays after the close (~1:20 PM PT) | Books the paper fills at the real closing prices and updates the dashboard. Catches up automatically if a day was missed |
| **Start account (once)** | Manual | Opens the paper account at the close of the start date |
| **Validate engine** | Manual | Replays the last 3 years of real prices in a scratch folder and runs the checks (§5a) |

**Timing:** GitHub's own scheduler turned out to be unreliable (on Oct 19, 2026 it started the previews ~2 hours late and skipped other runs), so the jobs are started on time by **cron-job.org**, a free external timer that calls GitHub's "run workflow" API in New York time (DST handled). GitHub's own UTC schedule stays on as a backup: the engine checks the NYSE calendar (holidays, early closes), a second preview on the same day is skipped, and a second daily run changes nothing. If the preview hasn't arrived by 12:30 PM PT, open the repo in the GitHub app → Actions → **Preview orders** → **Run workflow**; it runs immediately.

---

## 4. Setup (≈20 minutes, once, from any computer)

1. **GitHub account and repo.** Create a repo named `twin-engine` and upload these files (or push them with git). *Free GitHub Pages requires a public repo*: anyone with the link can see the paper account. Fine for paper trading; before real money, either upgrade to GitHub Pro (~$4/mo, private repo with Pages) or accept that the page shows your balance.
2. **Pages:** Settings → Pages → *Deploy from a branch* → `main` / `(root)`. The dashboard lives at `https://<user>.github.io/twin-engine/`.
3. **Actions permissions:** Settings → Actions → General → *Workflow permissions* → **Read and write**. (The jobs commit `summary.json` / `preview.json` back to the repo.)
3b. **On-time trigger (cron-job.org):** create a fine-grained GitHub token (Settings → Developer settings → Fine-grained tokens) with access to **only this repo** and **Actions: Read and write**. At cron-job.org create two jobs, time zone **America/New_York**, Monday–Friday, method **POST**, headers `Accept: application/vnd.github+json`, `Authorization: Bearer <token>`, `X-GitHub-Api-Version: 2022-11-28`:
   - Preview — 12:15 and 15:15 → `https://api.github.com/repos/<user>/twin-engine/actions/workflows/preview.yml/dispatches`, body `{"ref":"main","inputs":{"window":"true"}}`
   - Daily run — 16:20 → `.../workflows/daily.yml/dispatches`, body `{"ref":"main"}`
   - Health check — every 30 min, hours 9–17, minutes 25 and 55 → `.../workflows/health.yml/dispatches`, body `{"ref":"main"}`
   A successful call returns HTTP 204. The token expires (max 1 year): renew it and paste the new one into both jobs.
4. **Validate:** Actions → **Validate engine** → Run workflow. It must end in PASS; the report is on the run page.
5. **Open the account:** Actions → **Start account (once)** → Run workflow (defaults: start 2026-10-16, $20,000, $200/month, whole shares). The account opens at the real close of the start date.
6. **Phone:** open the dashboard → Share → **Add to Home Screen**. Install the GitHub app and allow notifications (order days open an issue that mentions you).

### Daily routine (2 minutes)
- ~12:20 PM PT on order days: notification / **Place before the close** card on the dashboard → enter each order in thinkorswim as **MOC** (market-on-close).
- After the close: glance at **Today's moves** and **Next actions**.
- Once a month (after the month-end run): Signals tab — which LDS assets are in trend.
- Fed days: the LDS sleeve shows as one TQQQ position for one day. That is the Fed-day swap, not an error.
- If a job fails, GitHub emails you. Re-run it from the Actions tab; nothing is saved on a failed run.

The preview is an estimate from prices ~45 minutes before the close. If prices move a lot in the last minutes, the paper ledger (booked at the real close) can differ from your orders by a share or two, or — rarely — a borderline rule (the 5% LDS threshold, the volatility band) can flip. The ledger is the reference; small differences are expected.

---

## 4a. Go-live timeline (from Oct 17, 2026)

| When | What |
|---|---|
| **Sat–Sun Oct 17–18** | Set up the repo, Pages and permissions (§4 steps 1–3). Run **Validate engine** (must PASS) and **Start account (once)**. Decide how to fund the Roth (the 2026 contribution limit is about $7,500, so $20k needs an existing Roth balance or a rollover) and start the transfer. In thinkorswim: confirm MOC orders and their cutoff, and accept the leveraged/inverse ETF disclosure if asked. Read §2 and §7 |
| **Mon–Fri Oct 19–23** | Dry run: on order days the preview arrives ~12:15–12:30 PM PT. Enter the orders in thinkorswim without sending them (or in paperMoney). After the close, compare with the daily run. v1.5: no weekly LDS rebalance any more; dip-boost days can bring TQQQ orders |
| **Mon Oct 26** | Go live: place the starting allocation as MOC orders |
| **Tue Oct 27** | First live Fed-day swap: LDS sleeve into SOXL at the close |
| **Wed Oct 28** | Fed decision: swap back at the close |
| **Fri Oct 30 – Wed Nov 4** | First turn-of-month window plus the first monthly LDS review (Fri Oct 30). Check every fill against the dashboard |
| **Fri Nov 27** | Early close (1:00 PM ET / 10:00 AM PT): the preview comes ~9:15 AM PT |
| **Dec 31** | First year-end 50/50 reset |
| **Each summer** | Add the Fed's next-year meeting dates to `FOMC_DATES` (edit `twin_engine.py` in the GitHub web editor) |

## 5. Paper trading plan — pass criteria before using real money

Run for **at least 3 months** (ideally through one quarter end, one Fed-day swap and one TOM window).

| Check | Pass |
|---|---|
| Engine ran every trading day | 100% (catch-up runs count) |
| Re-run the same period with `replay` | Equity within ±1% of the live paper ledger (confirms no state bugs) |
| Trade days per month | ~3–6 |
| Each trade explainable from the rules | Yes — every trade has a "reason" in the ledger |
| You executed / would have executed each order in time | Yes — practice placing the orders as market-on-close (MOC) by 3:45 PM ET in thinkorswim paperMoney |
| Emotional check | You held through at least one −10% week without wanting to override |

---

## 5a. Fast validation (instead of months of paper trading)

Two different things need testing, and only one of them needs live time:

| What | How | Time |
|---|---|---|
| **Strategy logic** (right trades, right sizes, no accounting errors) | `python twin_engine.py validate --years 3` replays the exact production code over the last 3 years of **real** prices and runs automatic checks (cash never negative, no negative shares, every held ETF priced, 50/50 at every year end, every Fed-day swap opens and closes, every trade has a reason). Writes `validation\validation_report.txt` and `validation\trades.csv`. Does not touch your paper account. | ~1 minute |
| **Order execution** (orders reach Schwab, fill near the close, permissions) | Schwab's API has no paper-trading mode, so: run the order step in **dry-run** (prints the exact orders it would send) for ~2–3 weeks while checking them against thinkorswim, then go live with a small amount first | ~2–3 weeks |

**Timing matters:** backtests show that placing orders one day late costs about 2.4 percentage points of CAGR and deepens the max drawdown by ~5 points. Orders must go in the **same day, before the close** (market-on-close, by Schwab's cutoff, 3:45 PM ET / 12:45 PM PT). That requires automation running on a computer or server, not manual orders from a phone the next morning.

### Production path
1. Run **Validate engine** (Actions tab) with real data. Pass = all checks PASS and results in line with the backtest.
2. Add the Schwab execution step (Schwab Trader API via the `schwab-py` library: computes targets ~12:15 PM PT from live prices, submits market-on-close orders, reconciles fills) and run it in dry-run mode for ~2–3 weeks.
3. Go live in the Roth IRA. Optionally start with part of the $20k and add the rest after the first quarter end.

Where it runs: the order preview already runs on GitHub Actions (§3). Automatic order submission would need somewhere that can hold the Schwab login: GitHub Actions with the token stored as a secret, a small Linux VPS (~$10–20/mo), or QuantConnect cloud (supports Schwab live trading with market-on-close orders; ~$120/mo; IRA support not listed — confirm). Schwab's API needs a one-click browser re-login every 7 days (the refresh token expires). The dashboard stays on GitHub Pages for your phone.

Broker setup at Schwab: register an app at developer.schwab.com ("Accounts and Trading Production"), link your Roth IRA, and confirm leveraged/inverse ETFs are enabled for the IRA (Schwab may ask you to acknowledge a disclosure).

---

## 6. Is $20,000 enough?

**Yes — $20k works.** It is the comfortable minimum. Specifics:

| Potential limitation | At $20k? | Notes |
|---|---|---|
| Pattern-day-trader rule (< $25k) | ✅ Not an issue | The strategy never buys and sells the same ETF on the same day. PDT also doesn't apply to IRA cash/limited-margin accounts the same way |
| Margin | ✅ Not needed | Leverage comes from the ETFs; the account is never margined |
| Trade size | ✅ OK | Smallest positions ≈ $200–500 (overlay legs). Orders < $25 are skipped |
| Fractional shares | ✅ Not needed | Tested with whole shares only (`--whole-shares`): costs ~0.1 pt/yr at $10k–$50k. Schwab offers fractional ETF shares on its site, but API support is unclear, so plan on whole shares |
| Commissions | ✅ $0 | Schwab charges $0 for online US ETF trades (confirm this applies to API orders). ~235 orders/yr |
| Settlement (T+1) in an IRA | ✅ OK | IRAs are cash accounts. Buying with same-day sale proceeds is allowed; a good-faith violation only happens if a position bought with unsettled money is sold before that money settles. With T+1 settlement and no same-day round trips in the rules, this shouldn't occur |
| Leveraged/inverse ETF permissions | ⚠️ Check | Some brokers require an acknowledgment form for leveraged/inverse ETFs in IRAs |
| Below ~$5k | ❌ | Rounding and minimums start distorting the weights |

---

## 7. Before committing real money — checklist

1. **Account type:** Roth IRA (or traditional IRA). Not a taxable account (see §8).
2. **Broker setup:** confirm leveraged + inverse ETFs allowed in the IRA, fractional shares on, $0-commission plan, MOC orders available.
3. **Size it so you'll stay in:** the backtest had −53% and −48% drawdowns, 2022 was −36% for Twin Engine, and in 2026 YTD the LDS half was −11% while SPY was +11%. Decide now that you won't stop after a bad year.
4. **Keep a core elsewhere:** SPY/VTI in a 401(k) or taxable account. Twin Engine is the growth engine, not your whole net worth.
5. **Single-day crash risk:** a ~33% one-day Nasdaq drop would nearly wipe out TQQQ. Never happened, but possible.
6. **Leveraged ETF reverse splits** happen often (SQQQ, TMV, GLL…). The engine applies splits from yfinance; verify after any split.
7. **Live execution plan:** in live trading you'll compute signals ~3:30 PM ET and submit MOC orders by 3:45 PM ET. Expect small slippage vs the paper fills at the exact close.
8. **Maintenance:** every 2 years, re-run the walk-forward to refresh parameters (vol target, power, band). Don't tune after bad months.
9. **Contributions:** $200/month lifts the 20-year realistic median from $1.18M to $1.93M. Consistency beats tweaking.

---

### 7a. Pre-set rules (decided now, checked automatically on the Health tab > Guardrails)

| Situation | Pre-set response |
|---|---|
| Down up to 40% from the high | Normal for this strategy. Keep following the orders. |
| Down 40–55% | Painful but inside the expected range. Keep following the orders. |
| Down 55–65% (deeper than the backtest ever went) | Review with Claude: is a data feed, ETF or rule broken? Keep following the orders meanwhile. |
| Down more than 65% | Pause new contributions and decide calmly whether to continue. Positions keep following the rules until you decide. |
| Last 12 months below −8.9% (the backtest's worst 5%) | Review; a bad year alone is not a reason to quit. |
| After 3+ years: CAGR more than 10 pts below SPY, or under 5% a year | The edge may be gone: consider moving to a plain index fund. |
| An ETF stops trading (closure) | The Health tab names the replacement (`SUBSTITUTES` in `twin_engine.py`); ask Claude to switch. Nothing switches automatically. |
| Real account differs from the paper account | Automatic: from go-live (`GO_LIVE_DATE`), any preview-vs-close difference is added to the next preview as a correction order. |

Never change these rules during a drawdown. They live in `GUARDRAILS` in `twin_engine.py`.

**Borderline days:** when a decision is close to its trigger at 3:15 PM ET (dip-boost RSI near 20, volatility switch near its band, LDS change near 5%), the order card says so. The close may decide differently; the next preview corrects it.

## 8. Taxes (why Roth)

Simulated FIFO tax lots (2000–2026): dollar-weighted holding period of sold shares ≈ **64 days**; ~1% of sale proceeds came from lots held > 1 year; **~85–90% of realized gains are short-term**. In a taxable account that means ordinary-income rates plus frequent wash sales. In a Roth/IRA none of this matters. The dashboard still tags each sale LONG/SHORT so you can see it.

Futures would get 60/40 tax treatment, but at $20k contracts are far too large to follow the weights (one micro Nasdaq contract ≈ $60k notional). Revisit at ~$250k.

---

## 8a. Health checks

`health.py` checks everything the system depends on and writes `health.json` for the dashboard's **Health** tab:
schedule (daily run booked the last close, today's preview arrived, latest run of every workflow succeeded, cron-job.org started the jobs on time, workflows enabled),
dashboard (live page published and current), data (Yahoo has every ticker's last close, no unexplained price jumps),
account (no negative cash or shares, every holding priced, 9Sig bookkeeping matches the sleeve, engine split, Fed swap not stuck, every close booked, last preview matched the booked trades),
configuration (versions, Fed dates left, market calendar coverage, cron-job.org token expiry) and upcoming reminders.

It runs every 30 minutes on weekdays from 9:25 AM to 5:55 PM ET (cron-job.org), right after every preview and daily run, and hourly as a backup.
The run about 10 minutes after the 3:15 PM ET preview leaves time to fix a missing preview before Schwab's MOC cutoff.

**Schwab's MOC cutoff: 3:45 PM ET (12:45 PM PT)**, 12:45 PM ET on 1:00 PM early-close days. thinkorswim removes MOC from the order-type menu after that (the exchanges accept MOC until 3:50 PM NYSE / 3:55 PM Nasdaq, but Schwab's deadline is the one that counts). The preview arrives ~12:15 PM PT, leaving 30 minutes; automatic re-tries stop at the cutoff, and you're notified if the preview is still missing at 12:30 PM PT.
**Automatic fixes** (before anyone is notified): a missing preview is started again (8 minutes apart), a close that wasn't booked starts the daily run again (25 minutes apart), disabled workflows are re-enabled, and the page is republished if it lags for 45+ minutes. Each fix runs at most 3 times a day; the check shows **Fixing** meanwhile and re-runs as soon as the fixed job finishes.
A GitHub issue (phone notification through the GitHub app) is opened only when a fix doesn't work, when a problem needs a person (the account ledger is never changed automatically), or when a preview is still missing 15 minutes before the close. It closes itself when everything passes again. Warnings show only on the dashboard.
**Watching the watcher:** turn on "notify on failure" for the three cron-job.org jobs, so cron-job.org emails you if GitHub stops accepting its calls (for example an expired token).

### 8b. What can fail, and what happens automatically

| Failure | Automatic response |
|---|---|
| cron-job.org doesn't start a job | GitHub's own schedule (hourly backup) and the health check start it; cron-job.org emails you |
| Preview missing near the close | Health check restarts it (8 min apart, until 3:42 PM ET); you're notified at 3:30 PM ET if it's still missing |
| Daily run failed / close not booked | Restarted every 25 min (3 a day); it catches up missed days |
| A ticker missing from Yahoo's batch download | Re-downloaded on its own |
| Yahoo missing a recent close or a whole day | Filled from Nasdaq's daily closes |
| Yahoo completely down | All prices from Nasdaq (closes not dividend-adjusted; fine for a day or two) |
| Yahoo intraday prices missing or stale in the preview | Replaced with CNBC live quotes (any gap, or >3% off) |
| Yahoo publishes a bad price (>45% move without a split) | Checked against Nasdaq: confirmed, replaced, or not booked until it can be confirmed |
| Unscheduled market closure | No orders, once Yahoo and CNBC both show no trades after 10:00 AM ET |
| Yahoo changes its site and breaks yfinance | Library versions are locked; a failed run retries once with the newest yfinance |
| A library update breaks the code | Can't happen silently: versions are locked in requirements.txt |
| Two jobs save at once | Save retried 4 times, then fails visibly |
| Workflow disabled / page not republished | Re-enabled / republished by the health check |
| Account ledger problem (negative cash, stuck swap, missed days) | Never changed automatically: you're notified |

## 9. Dashboard guide

| Tab | What it shows |
|---|---|
| **Overview** | Portfolio value, today's P&L, total return vs SPY, drawdown, sleeve split, next actions, today's moves |
| **Positions** | Every position: ticker, sleeve, shares, first/last entry date, average entry price, current price, $ / % P&L, weight, **why it's held and exactly what makes it exit / next review date**, tax lots |
| **Trades** | Full ledger: date, side, shares, price, $ value, reason, realized P&L, holding days, LONG/SHORT term |
| **Signals** | 9Sig volatility switch gauge, TOM calendar, quarterly target progress, Fed-day swap status (next decision, buy/sell closes), LDS trend status per asset (price vs 210-day average), momentum overlay |
| **Strategy** | The rules above and the parameters |
| **Health** | Every automatic check with its status, details and how to fix it, and when it last ran (from `health.json`). The dot next to PAPER in the header is the same status on every tab: green OK, amber warning, red problem |
| **Research** | v1.6 backtest from `backtest.json` (trading metrics too), plus the Idea Lab summary and a link to the full Idea Lab (`idealab.html`): scenarios (2000, 2007, 2010 real ETFs, double costs, SPY), growth chart vs SPY, crash periods, five worst drawdowns, calendar years, 1987-style stress test, 25-year projection |

The dashboard reads `summary.json` from the same folder and shows only your paper account, from its start date onward. Before the first run it shows a "Not started" screen with the setup steps. No simulated or historical data is mixed into the account; backtest results live only on the Backtest tab.

On order days a **Place before the close** card appears at the top of Overview (from `preview.json`) and disappears once the daily run books that close.

Note: opening `index.html` directly from a file explorer can't read `summary.json` (browsers block that). View it through GitHub Pages, or locally with `python -m http.server` in the folder and then http://localhost:8000.

---

## 10. summary.json fields (for future automation)

`meta` (as_of, start_capital, demo) • `portfolio` (value, day_pl, total_pl, twr_pct, cagr, max_dd, current_dd, spy_value, realized/unrealized P&L, gross_exposure) • `sleeves.nine` (tqqq_weight, vol20, tom window, quarter target/gap, skips_left) • `sleeves.lds` (effective exposures, per-asset trend/momentum) • `positions[]` (incl. lots, exit_rule, next_review) • `trades[]` • `equity[]` (daily value vs SPY with same contributions) • `events[]` • `next_actions[]` • `params`.

---

## 11. Commands

```bat
python twin_engine.py run [--capital 20000] [--contrib 200] [--whole-shares]
python twin_engine.py preview [--window]     # orders from live prices; --window = only from 65 min before the close until the MOC cutoff
python twin_engine.py status
python twin_engine.py reset
python twin_engine.py replay --csv prices.csv --start 2025-10-01 [--contrib 200] [--demo]
python twin_engine.py validate [--years 3]
```

---

## 12. Version history

| Version | Date | Change |
|---|---|---|
| 1.0 | Oct 2026 | Initial paper-trading release: 50/50 Twin Engine + TOM. Engine replay matches backtest (33.9% vs 35.0% CAGR, −48.4% vs −48.4% max DD, 2007–2026) |
| 1.1 | Oct 2026 | Volatility switch target raised 70% → 80% (larger TQQQ position in the 9Sig sleeve). Walk-forward out of sample: 35.1% vs 34.7% CAGR, −51.5% vs −53.3% max DD. Across 18 start years (2000–2017, 10-year windows): higher CAGR in 16, shallower drawdown in 13. Weaker for starts from 2013 on (drawdowns ~2–3 points deeper in 2022). Replay 2007–26: 36.4% CAGR, −44.1% max DD |
| 1.7.0 | Oct 21, 2026 | LDS **dual trend**: a core asset also needs its 30-day average above its 210-day average, so LDS skips assets that are still above the long average but already rolling over. 2000–26 38.1% / −36.4% (v1.6 36.2% / −37.4%); 2010–26 39.1% / −32.8% (36.2% / −35.2%); double costs 36.5%; worst 10-year CAGR 31.3% (27.8%); >50%-drop odds 9% → 4%. Round 8 tested 93 ideas; one-time LDS rebalance at the next close |
| 1.6.0 | Oct 19, 2026 | LDS drops QQQ (assets SPY, TLT, GLD): Engine 1 already holds the Nasdaq, so both engines no longer stack TQQQ. Same or higher CAGR with a 1.7–4.8 pt smaller max drawdown in every scenario tested (2000–26 36.2% / −37.4%; 2010–26 real ETFs 36.1% / −35.2% vs 36.0% / −40.0%). Nasdaq share of stock exposure 78% → 68%; days with Nasdaq exposure above 2x the account 12% → 2%. Idea Lab IV |
| 1.5.0 | Oct 19, 2026 | Idea Lab III (155 ideas, production engine over 1998–2026): three changes adopted together: (1) Fed-day swap into **SOXL** instead of TQQQ, (2) LDS review **monthly** instead of weekly (~15 fewer trade days a year), (3) 9Sig **dip boost** (QQQ 2-day RSI < 20 in an uptrend → full TQQQ next session). 35.2% / −40% vs 30.6% / −52% for v1.3 on the same data (2000–26); 2010–26 with real ETFs 36.0% / −40% vs 34.0% / −39%. Passed: double costs, fresh starts 2003/2007/2010, 15 of 17 ten-year windows, both halves, and a 2000–12 walk-forward pick. On-time job triggers via cron-job.org |
| 1.4.0 | Oct 2026 | Runs in the cloud. New `preview` command: ~45 min before the close it runs today's close through the exact rules on a copy of the account using live prices and lists the market-on-close orders (net per ticker, whole shares); never changes the ledger. Checked against real closes: identical orders on a new account, a normal day, a Fed-day swap in/out and a 1:00 PM early close. GitHub Actions workflows replace Task Scheduler / `run_daily.bat` (preview, daily run, start account, validate; DST and early closes handled via the NYSE calendar). Dashboard: **Place before the close** card. Price download retries when Yahoo throttles |
| 1.3.0 | Oct 2026 | Two rules added after testing ~100 ideas: (1) **Fed-day swap**: the LDS sleeve holds TQQQ from the close before each scheduled FOMC decision to the close of decision day; (2) **50/50 reset once a year** (December) instead of quarterly. Engine replay at 0.05% slippage: 2000–26 31.3% → 32.7% CAGR, max DD −50.9% → −43.4%; 2007–26 35.7% → 39.2%, −45.2% → −38.1%. ~12 more trade days a year. Also fixed: future calendar now covers ~14 months without losing market holidays |
| 1.2.0 | Oct 2026 | Full code review, 7 fixes: (1) volatility uses the same estimator as the validated backtest (sample std); replay 2007–26 now 36.1% CAGR, −44.8% max DD, matching the backtest (36.1% / −44.7%) instead of slightly beating it; (2) ETF splits: Yahoo's split-adjusted prices are converted back to real per-share prices, and the split day no longer shows a fake ±50% return (which could falsely trigger the 30-down rule); (3) a missing price now stops the run with a clear error instead of valuing that ETF at $0; short gaps (≤5 days) carry the last price; (4) a monthly contribution is invested once on its day instead of re-trading 9Sig every day until quarter end; (5) leftover positions under $25 are fully closed when an ETF leaves the target; (6) `--whole-shares` is remembered by the account; the SPY benchmark now includes dividends; (7) warning when the market-holiday calendar library is missing. 30 regression tests pass (splits, gaps, dividends, contributions, whole shares, catch-up runs, holidays) |
| 1.1.2 | Oct 2026 | Whole-share mode fixed (sells round up so cash never goes negative); README switched from IBKR to Schwab/thinkorswim |
| 1.1.1 | Oct 2026 | Added `validate` command. Fixed: quarterly rebalance could leave the LDS sleeve with slightly negative cash (−$30 to −$45) after slippage. Replay unchanged (36.5% CAGR, −44.1% max DD) |
