# Twin Engine — Paper Trading Guide

**Strategy:** 50% Modified 9Sig (+ Turn-of-Month) / 50% Leveraged Diversification Strategy (LDS)
**Account plan:** $20,000 start, optional $200/month, Roth IRA (taxes make it unsuitable for a taxable account — see §8)
**Status:** paper trading (no broker orders are sent)

> Not financial advice. Backtests overstate live results. Leveraged ETFs can lose most of their value quickly.

---

## 1. What you're running, in one paragraph

Two independent "engines" share one account and are reset to 50/50 at each year end.
**Engine 1 – Modified 9Sig** holds TQQQ in a *growth* sub-sleeve and TLT + GLD in a *defensive* reserve. Every quarter the growth sub-sleeve must grow 9%: excess is sold into the reserve, shortfalls are bought from it. Inside the growth sub-sleeve a **volatility switch** shrinks TQQQ when Nasdaq volatility spikes, and a **turn-of-month (TOM)** rule holds full TQQQ around month-end.
**Engine 2 – LDS** checks S&P 500, Nasdaq-100, long Treasuries and gold every Friday; it holds the ones above their 210-day average, sized by inverse volatility and levered up with 3x/2x ETFs (UPRO, TQQQ, TMF, UGL), plus a small long/short momentum overlay (can use SPXU, SQQQ, TMV, GLL). On each scheduled **Fed decision day** (8 a year) the whole LDS sleeve is held in TQQQ for that one day.

### Expected behaviour (backtest, $20k start)

| | Final equity | CAGR | Max drawdown |
|---|---|---|---|
| Paper engine replay v1.3, 2000 → Sep 2026 | $38.2M | 32.7% | −43% |
| Paper engine replay v1.3, 2007 → Sep 2026 | $13.5M | 39.2% | −38% |
| (v1.2 without the Fed-day swap / yearly reset, 2000 → 2026) | $28.7M | 31.3% | −51% |
| SPY, 2000 → Sep 2026 | $165k | 8.2% | −55% |

**Realistic live expectation:** ~20–25%/yr with a 45–60% drawdown at some point.

### 20-year projection (v1.3, $20,000 start on Oct 16, 2026)

Monte Carlo: 20,000 paths that resample real 12-month blocks of the v1.3 engine's monthly returns (2000–2026, 0.05% slippage). **Realistic** = backtest returns minus 8 points a year (future edge decay, real-world fills). **Conservative** = minus 15 points. Values are account balances at each anniversary.

| Year | Ending | Realistic median | Profit (median) | 10th – 90th percentile | Median with +$200/mo | Conservative median |
|---|---|---|---|---|---|---|
| 1 | Oct 2027 | $24,363 | $4,363 | $16,962 – $35,030 | $27,036 | $22,509 |
| 2 | Oct 2028 | $29,758 | $9,758 | $17,694 – $50,668 | $35,789 | $25,402 |
| 3 | Oct 2029 | $36,514 | $16,514 | $19,305 – $70,242 | $46,698 | $28,797 |
| 4 | Oct 2030 | $44,876 | $24,876 | $21,512 – $95,290 | $59,974 | $32,700 |
| 5 | Oct 2031 | $55,190 | $35,190 | $24,181 – $129,076 | $76,856 | $37,155 |
| 6 | Oct 2032 | $67,200 | $47,200 | $27,135 – $170,244 | $95,984 | $41,798 |
| 7 | Oct 2033 | $82,152 | $62,152 | $31,428 – $224,987 | $120,759 | $47,210 |
| 8 | Oct 2034 | $100,184 | $80,184 | $35,604 – $294,563 | $150,265 | $53,192 |
| 9 | Oct 2035 | $122,995 | $102,995 | $40,667 – $390,629 | $187,478 | $60,335 |
| 10 | Oct 2036 | $150,874 | $130,874 | $47,203 – $507,450 | $232,560 | $68,379 |
| 11 | Oct 2037 | $185,328 | $165,328 | $54,253 – $653,815 | $290,961 | $77,604 |
| 12 | Oct 2038 | $228,268 | $208,268 | $62,282 – $852,076 | $359,434 | $88,312 |
| 13 | Oct 2039 | $279,363 | $259,363 | $73,116 – $1,083,516 | $443,398 | $99,856 |
| 14 | Oct 2040 | $344,216 | $324,216 | $84,848 – $1,402,808 | $549,973 | $113,675 |
| 15 | Oct 2041 | $422,944 | $402,944 | $100,375 – $1,808,453 | $680,819 | $129,047 |
| 16 | Oct 2042 | $522,119 | $502,119 | $114,709 – $2,345,605 | $845,944 | $147,186 |
| 17 | Oct 2043 | $642,697 | $622,697 | $136,239 – $3,044,229 | $1,040,472 | $167,392 |
| 18 | Oct 2044 | $783,299 | $763,299 | $159,481 – $3,871,205 | $1,275,169 | $188,490 |
| 19 | Oct 2045 | $963,206 | $943,206 | $186,732 – $4,909,391 | $1,572,807 | $214,146 |
| 20 | Oct 2046 | $1,178,578 | $1,158,578 | $218,996 – $6,291,138 | $1,930,859 | $242,092 |

In the realistic case, 41% of paths have a drop worse than −50% at some point (median worst drop −48%), and 0.1% end below $20,000. Without any haircut (the backtest as-is), the median 20-year result is $6.2M. This is a range, not a promise.

Replays use 0.05% slippage per fill (stricter than the engine's default 0.02%). Typical year: ~55–60 trade days, ~235 orders. 2000–2026: beat SPY in 20 of 27 calendar years, worst year −36% (2022).

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

### 2.3 Engine 2 — LDS (checked at the close of the last trading day of each week)
1. **Trend:** for SPY, QQQ, TLT, GLD — is today's close ≥ its 210-day simple average?
2. **Core (85%)**: uptrend assets get weight ∝ 1 / (63-day volatility). Scale the mix so its expected volatility = 100%/yr; the scale is capped by the leverage that exists (see step 4), so in practice it means "as much leverage as the ETFs allow."
3. **Overlay (15%)**: each asset long if the average of its 1-, 3-, 6- and 12-month returns > 0, short if < 0; weight ∝ 1/vol, scaled to 15% vol.
4. **Implement** combined exposures with the lowest common leverage tier that fits in 100% of the sleeve: 1x (SPY, QQQ, TLT, GLD) → 2x (SSO, QLD, UBT, UGL) → 3x (UPRO, TQQQ, TMF; gold max 2x UGL). Shorts use inverse ETFs (SH/SDS/SPXU, PSQ/QID/SQQQ, TBF/TBT/TMV, GLL). If even max leverage doesn't fit, everything is scaled down.
5. **Trade only if** the total change across positions is > 5% of the sleeve.
6. **Fed-day swap (v1.3):** at the close of the trading day **before** each scheduled FOMC decision, sell the whole LDS sleeve and buy TQQQ. At the close of **decision day**, sell the TQQQ and buy the normal LDS positions (fresh weekly signal). The weekly check is skipped that day because the sleeve was just rebuilt. Engine 1 is not affected. The dates are listed in `FOMC_DATES` in `twin_engine.py` (through Dec 2027). The Fed publishes next year's schedule each summer: add it once a year. The dashboard shows an "Action needed" banner when fewer than 3 dates are left.

   Why: Nasdaq rose on Fed decision days far more often than on normal days (TQQQ +0.97% average vs +0.12%, 60% up days, 1999–2026; first documented by Lucca & Moench, 2015). With costs it added +1.4 points of CAGR from 2000 and cut the max drawdown by ~7 points. It helped in both halves of history and in every 10-year window's drawdown. Most of the gain came in 2007–12 and 2020–26. If your fills cost more than ~0.10% per side, the CAGR gain disappears but the drawdown benefit remains.

### 2.4 What does NOT exist (on purpose)
No stop-losses, no profit targets, no discretionary overrides. Every exit comes from the rules above. About 100 other ideas tested (crash pauses, VIX sizing, put hedges, trend filters, Turtle/PTJ/Livermore rules, overnight trading, sell-in-May, extra assets, Bitcoin, more leverage, etc.) either failed walk-forward validation or only added return by adding leverage. The futures-based ones (LDS up to 5x, volatility-managed leverage) need $25k+ and a futures-approved IRA, and carry 1987-crash risk. They are parked for now.

---

## 3. Files

```
twin-engine/
  twin_engine.py       paper-trading engine (signals, paper fills, FIFO tax lots, ledger, order preview)
  index.html           dashboard (GitHub Pages; open on phone)
  state.json           engine state — created by "Start account", DO NOT edit by hand
  summary.json         dashboard data — rewritten by every daily run
  preview.json         today's orders, written ~45 min before the close
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

GitHub cron runs in UTC, so each job is scheduled at both daylight-saving offsets; the engine checks the NYSE calendar (holidays, early closes) and the extra runs do nothing. GitHub can start scheduled jobs 10–30 minutes late. If the preview hasn't arrived by 12:30 PM PT, open the repo in the GitHub app → Actions → **Preview orders** → **Run workflow**; it runs immediately.

---

## 4. Setup (≈20 minutes, once, from any computer)

1. **GitHub account and repo.** Create a repo named `twin-engine` and upload these files (or push them with git). *Free GitHub Pages requires a public repo*: anyone with the link can see the paper account. Fine for paper trading; before real money, either upgrade to GitHub Pro (~$4/mo, private repo with Pages) or accept that the page shows your balance.
2. **Pages:** Settings → Pages → *Deploy from a branch* → `main` / `(root)`. The dashboard lives at `https://<user>.github.io/twin-engine/`.
3. **Actions permissions:** Settings → Actions → General → *Workflow permissions* → **Read and write**. (The jobs commit `summary.json` / `preview.json` back to the repo.)
4. **Validate:** Actions → **Validate engine** → Run workflow. It must end in PASS; the report is on the run page.
5. **Open the account:** Actions → **Start account (once)** → Run workflow (defaults: start 2026-10-16, $20,000, $200/month, whole shares). The account opens at the real close of the start date.
6. **Phone:** open the dashboard → Share → **Add to Home Screen**. Install the GitHub app and allow notifications (order days open an issue that mentions you).

### Daily routine (2 minutes)
- ~12:20 PM PT on order days: notification / **Place before the close** card on the dashboard → enter each order in thinkorswim as **MOC** (market-on-close).
- After the close: glance at **Today's moves** and **Next actions**.
- Once a week (after Friday's run): Signals tab — which LDS assets are in trend.
- Fed days: the LDS sleeve shows as one TQQQ position for one day. That is the Fed-day swap, not an error.
- If a job fails, GitHub emails you. Re-run it from the Actions tab; nothing is saved on a failed run.

The preview is an estimate from prices ~45 minutes before the close. If prices move a lot in the last minutes, the paper ledger (booked at the real close) can differ from your orders by a share or two, or — rarely — a borderline rule (the 5% LDS threshold, the volatility band) can flip. The ledger is the reference; small differences are expected.

---

## 4a. Go-live timeline (from Oct 17, 2026)

| When | What |
|---|---|
| **Sat–Sun Oct 17–18** | Set up the repo, Pages and permissions (§4 steps 1–3). Run **Validate engine** (must PASS) and **Start account (once)**. Decide how to fund the Roth (the 2026 contribution limit is about $7,500, so $20k needs an existing Roth balance or a rollover) and start the transfer. In thinkorswim: confirm MOC orders and their cutoff, and accept the leveraged/inverse ETF disclosure if asked. Read §2 and §7 |
| **Mon–Fri Oct 19–23** | Dry run: on order days the preview arrives ~12:15–12:30 PM PT. Enter the orders in thinkorswim without sending them (or in paperMoney). After the close, compare with the daily run. Friday Oct 23 = first weekly LDS rebalance |
| **Mon Oct 26** | Go live: place the starting allocation as MOC orders |
| **Tue Oct 27** | First live Fed-day swap: LDS sleeve into TQQQ at the close |
| **Wed Oct 28** | Fed decision: swap back at the close |
| **Fri Oct 30 – Wed Nov 4** | First turn-of-month window plus the Friday LDS review. Check every fill against the dashboard |
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

**Timing matters:** backtests show that placing orders one day late costs about 2.4 percentage points of CAGR and deepens the max drawdown by ~5 points. Orders must go in the **same day, before the close** (market-on-close, by 3:50 PM ET / 12:50 PM PT). That requires automation running on a computer or server, not manual orders from a phone the next morning.

### Production path
1. Run **Validate engine** (Actions tab) with real data. Pass = all checks PASS and results in line with the backtest.
2. Add the Schwab execution step (Schwab Trader API via the `schwab-py` library: computes targets ~12:40 PM PT from live prices, submits market-on-close orders, reconciles fills) and run it in dry-run mode for ~2–3 weeks.
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

## 8. Taxes (why Roth)

Simulated FIFO tax lots (2000–2026): dollar-weighted holding period of sold shares ≈ **64 days**; ~1% of sale proceeds came from lots held > 1 year; **~85–90% of realized gains are short-term**. In a taxable account that means ordinary-income rates plus frequent wash sales. In a Roth/IRA none of this matters. The dashboard still tags each sale LONG/SHORT so you can see it.

Futures would get 60/40 tax treatment, but at $20k contracts are far too large to follow the weights (one micro Nasdaq contract ≈ $60k notional). Revisit at ~$250k.

---

## 9. Dashboard guide

| Tab | What it shows |
|---|---|
| **Overview** | Portfolio value, today's P&L, total return vs SPY, drawdown, sleeve split, next actions, today's moves |
| **Positions** | Every position: ticker, sleeve, shares, first/last entry date, average entry price, current price, $ / % P&L, weight, **why it's held and exactly what makes it exit / next review date**, tax lots |
| **Trades** | Full ledger: date, side, shares, price, $ value, reason, realized P&L, holding days, LONG/SHORT term |
| **Signals** | 9Sig volatility switch gauge, TOM calendar, quarterly target progress, Fed-day swap status (next decision, buy/sell closes), LDS trend status per asset (price vs 210-day average), momentum overlay |
| **Strategy** | The rules above, parameters, backtest stats |

The dashboard reads `summary.json` from the same folder and shows only your paper account, from its start date onward. Before the first run it shows a "Not started" screen with the setup steps. No simulated or historical data is ever shown.

On order days a **Place before the close** card appears at the top of Overview (from `preview.json`) and disappears once the daily run books that close.

Note: opening `index.html` directly from a file explorer can't read `summary.json` (browsers block that). View it through GitHub Pages, or locally with `python -m http.server` in the folder and then http://localhost:8000.

---

## 10. summary.json fields (for future automation)

`meta` (as_of, start_capital, demo) • `portfolio` (value, day_pl, total_pl, twr_pct, cagr, max_dd, current_dd, spy_value, realized/unrealized P&L, gross_exposure) • `sleeves.nine` (tqqq_weight, vol20, tom window, quarter target/gap, skips_left) • `sleeves.lds` (effective exposures, per-asset trend/momentum) • `positions[]` (incl. lots, exit_rule, next_review) • `trades[]` • `equity[]` (daily value vs SPY with same contributions) • `events[]` • `next_actions[]` • `params`.

---

## 11. Commands

```bat
python twin_engine.py run [--capital 20000] [--contrib 200] [--whole-shares]
python twin_engine.py preview [--window]     # orders from live prices; --window = only 5-65 min before the close
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
| 1.4.0 | Oct 2026 | Runs in the cloud. New `preview` command: ~45 min before the close it runs today's close through the exact rules on a copy of the account using live prices and lists the market-on-close orders (net per ticker, whole shares); never changes the ledger. Checked against real closes: identical orders on a new account, a normal day, a Fed-day swap in/out and a 1:00 PM early close. GitHub Actions workflows replace Task Scheduler / `run_daily.bat` (preview, daily run, start account, validate; DST and early closes handled via the NYSE calendar). Dashboard: **Place before the close** card. Price download retries when Yahoo throttles |
| 1.3.0 | Oct 2026 | Two rules added after testing ~100 ideas: (1) **Fed-day swap**: the LDS sleeve holds TQQQ from the close before each scheduled FOMC decision to the close of decision day; (2) **50/50 reset once a year** (December) instead of quarterly. Engine replay at 0.05% slippage: 2000–26 31.3% → 32.7% CAGR, max DD −50.9% → −43.4%; 2007–26 35.7% → 39.2%, −45.2% → −38.1%. ~12 more trade days a year. Also fixed: future calendar now covers ~14 months without losing market holidays |
| 1.2.0 | Oct 2026 | Full code review, 7 fixes: (1) volatility uses the same estimator as the validated backtest (sample std); replay 2007–26 now 36.1% CAGR, −44.8% max DD, matching the backtest (36.1% / −44.7%) instead of slightly beating it; (2) ETF splits: Yahoo's split-adjusted prices are converted back to real per-share prices, and the split day no longer shows a fake ±50% return (which could falsely trigger the 30-down rule); (3) a missing price now stops the run with a clear error instead of valuing that ETF at $0; short gaps (≤5 days) carry the last price; (4) a monthly contribution is invested once on its day instead of re-trading 9Sig every day until quarter end; (5) leftover positions under $25 are fully closed when an ETF leaves the target; (6) `--whole-shares` is remembered by the account; the SPY benchmark now includes dividends; (7) warning when the market-holiday calendar library is missing. 30 regression tests pass (splits, gaps, dividends, contributions, whole shares, catch-up runs, holidays) |
| 1.1.2 | Oct 2026 | Whole-share mode fixed (sells round up so cash never goes negative); README switched from IBKR to Schwab/thinkorswim |
| 1.1.1 | Oct 2026 | Added `validate` command. Fixed: quarterly rebalance could leave the LDS sleeve with slightly negative cash (−$30 to −$45) after slippage. Replay unchanged (36.5% CAGR, −44.1% max DD) |
