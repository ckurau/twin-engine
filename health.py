"""
Twin Engine health check -> health.json (dashboard Health tab). Opens a GitHub issue (phone notification) when a check fails
and closes it when everything passes again.

Runs every 30 minutes on weekdays (cron-job.org, New York time), right after every preview / daily run, and hourly as a backup.
  python health.py            # needs GITHUB_TOKEN / GITHUB_REPOSITORY for the GitHub checks (set automatically in Actions)
Status per check: ok | warn | fail | pending (not due yet) | info.
"""
import os, sys, json, glob, datetime as dt, urllib.request, urllib.error
from zoneinfo import ZoneInfo
import numpy as np, pandas as pd
import twin_engine as te

HERE = te.HERE
REPO = os.environ.get("GITHUB_REPOSITORY", "ckurau/twin-engine")
TOKEN = os.environ.get("GITHUB_TOKEN")
OWNER, NAME = REPO.split("/")
PAGES = f"https://{OWNER}.github.io/{NAME}/"
HEALTH_PATH = os.path.join(HERE, "health.json")
ISSUE_TITLE = "Twin Engine health: problem found"
ET = ZoneInfo("America/New_York")
checks = []

def add(group, name, status, detail, fix=""):
    checks.append(dict(group=group, name=name, status=status, detail=detail, fix=fix))

DRY = bool(os.environ.get("HEALTH_DRY"))     # test mode: log fixes and issues instead of sending them

def api(path, method="GET", body=None):
    if DRY and method != "GET":
        print(f"[dry run] would {method} {path} {json.dumps(body) if body else ''}"); return {}
    data = json.dumps(body).encode() if body is not None else (b"" if method in ("POST", "PUT") else None)
    req = urllib.request.Request(f"https://api.github.com/repos/{REPO}/{path}", method=method, data=data,
                                 headers={"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28",
                                          **({"Authorization": f"Bearer {TOKEN}"} if TOKEN else {})})
    with urllib.request.urlopen(req, timeout=20) as r:
        txt = r.read(); return json.loads(txt) if txt else {}

def load(path, default=None):
    try:
        with open(path) as f: return json.load(f)
    except Exception: return default

def safe(fn):
    """run a check function; an unexpected error becomes a failed check instead of stopping the health run"""
    try: fn()
    except Exception as e: add("Health check", f"{fn.__doc__ or fn.__name__}".split("\n")[0], "fail", f"The check itself crashed: {type(e).__name__}: {e}", "Ask Claude to look at health.py.")

# ---------------------------------------------------------------------------- market clock
import exchange_calendars as xcals
CAL = xcals.get_calendar("XNYS")
NOW = dt.datetime.fromisoformat(os.environ["HEALTH_NOW"]).astimezone(ET) if os.environ.get("HEALTH_NOW") else dt.datetime.now(ET)   # HEALTH_NOW: tests only
TODAY = pd.Timestamp(NOW.date())
IS_SESSION = CAL.is_session(TODAY)
CLOSE = CAL.session_close(TODAY).tz_convert(ET).to_pydatetime() if IS_SESSION else None
CUTOFF = CLOSE - dt.timedelta(minutes=te.MOC_CUTOFF_MIN) if IS_SESSION else None   # Schwab's MOC cutoff (3:45 PM ET)
def prev_session(d): return pd.Timestamp(CAL.previous_session(d)).tz_localize(None) if CAL.is_session(d) else pd.Timestamp(CAL.date_to_session(d, direction="previous")).tz_localize(None)
# the close the daily run should have booked by now (daily run starts 4:20 PM ET; allow until close + 50 min)
if IS_SESSION and NOW >= CLOSE + dt.timedelta(minutes=50): EXPECTED_CLOSE = TODAY
else: EXPECTED_CLOSE = prev_session(TODAY)
fmt_t = lambda d: d.strftime("%a %b %d, %I:%M %p ET").replace(" 0", " ")

summary = load(te.SUMMARY_PATH, {}); state = load(te.STATE_PATH, {}); preview = load(te.PREVIEW_PATH, {})

# ---------------------------------------------------------------------------- 1. schedule & runs
def c_daily():
    """Daily run booked the last close"""
    asof = summary.get("meta", {}).get("as_of")
    if not asof: return add("Schedule", "Daily run booked the last close", "fail", "summary.json has no data.", "Run 'Daily run' in GitHub Actions.")
    if pd.Timestamp(asof) >= EXPECTED_CLOSE:
        add("Schedule", "Daily run booked the last close", "ok", f"Account is as of the {pd.Timestamp(asof):%a %b %d} close.")
    else:
        add("Schedule", "Daily run booked the last close", "fail", f"Account is as of {asof}, but the {EXPECTED_CLOSE:%a %b %d} close should be booked by now.",
            "Open GitHub > Actions > 'Daily run (after the close)' > Run workflow. It catches up any missed days.")
    if IS_SESSION and CLOSE <= NOW < CLOSE + dt.timedelta(minutes=50):
        add("Schedule", "Today's close", "pending", f"The daily run books today's close at about {fmt_t(CLOSE + dt.timedelta(minutes=20))}.")

def c_preview():
    """Today's preview arrived"""
    if not IS_SESSION:
        return add("Schedule", "Today's order preview", "info", "Market closed today, no preview needed.")
    due = CLOSE - dt.timedelta(minutes=35)
    if NOW < CLOSE - dt.timedelta(minutes=46):
        return add("Schedule", "Today's order preview", "pending", f"Due at about {fmt_t(CLOSE - dt.timedelta(minutes=45))}.")
    ok = preview.get("date") == str(TODAY.date()) and preview.get("status") in ("orders", "no_orders")
    if ok:
        n = len(preview.get("orders", []))
        add("Schedule", "Today's order preview", "ok", f"Arrived {preview.get('prices_as_of', '')}: " + (f"{n} MOC order(s) to place." if n else "no orders today."))
    elif NOW < due:
        add("Schedule", "Today's order preview", "pending", "Expected any minute now.")
    elif NOW < CUTOFF:
        add("Schedule", "Today's order preview", "fail", f"No preview yet; Schwab's MOC cutoff is {fmt_t(CUTOFF)}.",
            "GitHub app > twin-engine > Actions > 'Preview orders' > Run workflow (runs immediately). Place the orders as MOC before Schwab's cutoff.")
    else:
        add("Schedule", "Today's order preview", "warn", "No preview before Schwab's MOC cutoff today. The daily run still books the paper close; when live, compare Schwab with the dashboard tomorrow.", "Check the 'Preview orders' runs in GitHub Actions.")

RUNS = []
def c_runs():
    """Recent workflow runs succeeded"""
    global RUNS
    if not TOKEN: return add("Schedule", "Recent workflow runs", "info", "Not checked (runs only inside GitHub Actions).")
    RUNS = api("actions/runs?per_page=60").get("workflow_runs", [])
    latest = {}
    for r in RUNS:
        if r["status"] != "completed" or r["name"] in latest: continue
        latest[r["name"]] = r
    # the health check's own hiccups show up as a stale timestamp instead; a failed preview/daily run is already judged by its result
    # (preview arrived, close booked) and restarted automatically, so a failed run alone is a warning, not a page
    bad = [r for r in latest.values() if r["conclusion"] not in ("success", "skipped", "neutral", "cancelled") and not r["name"].startswith(("pages", "Health"))]
    if bad:
        add("Schedule", "Recent workflow runs", "warn", "Last run failed: " + "; ".join(f"{r['name']} ({r['conclusion']}, {pd.Timestamp(r['created_at']).tz_convert(ET):%b %d %I:%M %p})" for r in bad),
            "Open the failed run in GitHub Actions to see the error, then re-run it. Ask Claude if it fails again.")
    else:
        add("Schedule", "Recent workflow runs", "ok", f"Latest run of each workflow succeeded ({len(latest)} workflows).")

def c_trigger():
    """cron-job.org is starting the jobs on time"""
    if not TOKEN: return
    if not RUNS: return add("Schedule", "On-time trigger (cron-job.org)", "warn", "Could not read workflow runs.")
    def dispatched(name_start, day, start, end):
        """a run started by cron-job.org (workflow_dispatch) on `day` between start and end (ET datetimes)"""
        for r in RUNS:
            if r["event"] != "workflow_dispatch" or not r["name"].startswith(name_start): continue
            t = pd.Timestamp(r["created_at"]).tz_convert(ET)
            if t.date() == day.date() and start <= t.to_pydatetime() <= end: return t
        return None
    msgs, status = [], "ok"
    if IS_SESSION and NOW >= CLOSE - dt.timedelta(minutes=40):
        t = dispatched("Preview", TODAY, CLOSE - dt.timedelta(minutes=50), CLOSE - dt.timedelta(minutes=10))
        if t: msgs.append(f"preview started {t:%-I:%M %p} ET today" if os.name != "nt" else f"preview started {t:%I:%M %p} ET today")
        else: status = "warn"; msgs.append("no cron-job.org preview start seen today")
    prev = prev_session(TODAY) if not (IS_SESSION and NOW >= CLOSE + dt.timedelta(minutes=30)) else TODAY
    pc = CAL.session_close(prev).tz_convert(ET).to_pydatetime()
    t = dispatched("Daily", prev, pc + dt.timedelta(minutes=10), pc + dt.timedelta(hours=2, minutes=30))
    if t: msgs.append(f"daily run started {t:%a %I:%M %p} ET")
    else: status = "warn"; msgs.append(f"no cron-job.org daily start seen for {prev:%a %b %d}")
    txt = "; ".join(msgs); txt = txt[:1].upper() + txt[1:]
    add("Schedule", "On-time trigger (cron-job.org)", status, txt + ".",
        "" if status == "ok" else "Open cron-job.org > Cronjobs > History. A 401/403 means the GitHub token expired or was pasted wrong; 404 means the URL is wrong.")

def c_workflows():
    """Workflows are enabled"""
    if not TOKEN: return
    wf = api("actions/workflows").get("workflows", [])
    off = [w["name"] for w in wf if w["state"] != "active"]
    add("Schedule", "Workflows enabled", "fail" if off else "ok", ("Disabled: " + ", ".join(off)) if off else f"All {len(wf)} workflows are active.",
        "GitHub > Actions > select the workflow > 'Enable workflow'." if off else "")

def c_pages():
    """Dashboard is published and current"""
    try:
        with urllib.request.urlopen(PAGES + "summary.json?t=" + str(NOW.timestamp()), timeout=20) as r: live = json.load(r)
        a, b = live.get("meta", {}).get("as_of"), summary.get("meta", {}).get("as_of")
        if a == b: add("Dashboard", "Dashboard is published and current", "ok", f"Live page shows the {pd.Timestamp(a):%a %b %d} close.")
        else: add("Dashboard", "Dashboard is published and current", "warn", f"Live page shows {a}, the repo has {b}. Usually a publish still in progress.", "If this lasts over an hour: GitHub > Actions > 'pages build and deployment'.")
    except Exception as e:
        add("Dashboard", "Dashboard is published and current", "fail", f"Could not load the live dashboard data: {e}", "GitHub > Settings > Pages must deploy from main / root.")

# ---------------------------------------------------------------------------- 2. data
PX = {}
def c_data():
    """Price data downloads"""
    adj, close, divs, spl = te.fetch_yf(years=1, tries=2)
    PX.update(adj=adj, close=close)
    last = close.index[-1]
    # today's row may be an intraday price; the engine ignores it until 4:15 PM ET
    want = EXPECTED_CLOSE
    row = close.loc[want] if want in close.index else None
    missing = [t for t in te.ALL_TICKERS if row is None or t not in row or not (row[t] > 0)]
    close_t = CAL.session_close(want).tz_convert(ET).to_pydatetime(); late_h = (NOW - close_t).total_seconds() / 3600
    sev = "fail" if late_h > 20 else "warn"     # Yahoo is sometimes hours late; it only matters if it lasts into the next session
    if row is None: add("Data", "Price data (Yahoo Finance)", sev, f"Yahoo doesn't have the {want:%b %d} close yet (latest {last:%b %d}, {late_h:.0f} h after that close).",
                        "Usually Yahoo catches up within hours. If this is still failing by the next morning, ask Claude.")
    elif missing: add("Data", "Price data (Yahoo Finance)", sev, f"No {want:%b %d} close yet for: {', '.join(missing)}.", "Usually fixes itself within hours; if it persists into the next session, ask Claude.")
    else: add("Data", "Price data (Yahoo Finance)", "ok", f"All {len(te.ALL_TICKERS)} tickers have the {want:%b %d} close.")
    r = close.pct_change().iloc[-5:]
    big = [(t, d, v) for d, row_ in r.iterrows() for t, v in row_.items() if v == v and abs(v) > 0.35]
    add("Data", "Price sanity", "warn" if big else "ok",
        ("Unusual moves: " + ", ".join(f"{t} {v:+.0%} on {d:%b %d}" for t, d, v in big)) if big else "No price jumps above 35% in the last week (no unhandled splits).",
        "Probably a stock split or bad tick. Ask Claude to check before the next run." if big else "")

# ---------------------------------------------------------------------------- 3. account
def c_state():
    """Paper account integrity"""
    if not state: return add("Account", "Paper account file", "fail", "state.json is missing.", "Run 'Start account (once)'.")
    probs = []
    for sl, h in state["sleeves"].items():
        if h["cash"] < -1: probs.append(f"{sl} cash is negative (${h['cash']:,.2f})")
        for t, sh in h["holdings"].items():
            if sh < -1e-6: probs.append(f"{sl} holds negative shares of {t}")
    held = {t for h in state["sleeves"].values() for t in h["holdings"]}
    pc = state.get("prev_close", {}); unpriced = sorted(t for t in held if not (pc.get(t, 0) > 0))
    if unpriced: probs.append("no price for " + ", ".join(unpriced))
    add("Account", "Cash, shares and prices", "fail" if probs else "ok", "; ".join(probs) if probs else f"No negative cash or shares; all {len(held)} holdings priced.", "Ask Claude: the ledger may need repair." if probs else "")
    # 9Sig bookkeeping matches the sleeve
    v9 = state["sleeves"]["9SIG"]["cash"] + sum(sh * pc.get(t, 0) for t, sh in state["sleeves"]["9SIG"]["holdings"].items())
    sb = state["nine"]["S"] + state["nine"]["B"]
    gap = abs(sb / v9 - 1) if v9 else 1
    add("Account", "9Sig bookkeeping", "ok" if gap < 0.03 else "warn", f"Growth + reserve = ${sb:,.0f} vs sleeve ${v9:,.0f} ({gap:.1%} apart).",
        "" if gap < 0.03 else "Ask Claude: 9Sig targets may be off.")
    vl = state["sleeves"]["LDS"]["cash"] + sum(sh * pc.get(t, 0) for t, sh in state["sleeves"]["LDS"]["holdings"].items())
    share = v9 / (v9 + vl) if v9 + vl else 0.5
    add("Account", "Engine split", "ok" if abs(share - 0.5) < 0.25 else "warn", f"9Sig {share:.0%} / LDS {1 - share:.0%} (reset to 50/50 each Dec 31).")
    fs = state["lds"].get("fomc_swap") or {}
    if fs.get("active"):
        dec = pd.Timestamp(fs.get("decision")); stuck = pd.Timestamp(state["last_date"]) > dec
        add("Account", "Fed-day swap", "fail" if stuck else "ok", f"Swap into {te.P['fomc_asset']} is {'STILL ' if stuck else ''}active for the {dec:%b %d} decision.",
            "Ask Claude: the swap should have ended at that close." if stuck else "")
    else:
        add("Account", "Fed-day swap", "ok", "No swap open.")
    if state["lds"].get("assets") and state["lds"]["assets"] != list(te.P["lds_assets"]):
        add("Account", "LDS rules applied", "warn", f"LDS still holds the old asset list {state['lds']['assets']}; it switches at the next close.")
    eq = pd.to_datetime([e["date"] for e in state["equity"]])
    sess = pd.DatetimeIndex(CAL.sessions_in_range(eq[0], pd.Timestamp(state["last_date"]))).tz_localize(None)
    gaps = sess.difference(eq)
    add("Account", "No missed days", "fail" if len(gaps) else "ok", (f"Missing closes: {', '.join(str(d.date()) for d in gaps[:5])}") if len(gaps) else f"Every close since {eq[0]:%b %d, %Y} is booked ({len(eq)} days).",
        "Ask Claude: these days were skipped." if len(gaps) else "")

def c_preview_vs_booked():
    """Last preview matched the booked close"""
    files = sorted(glob.glob(os.path.join(HERE, "previews", "*.json")))
    files = [f for f in files if os.path.basename(f)[:10] <= str(pd.Timestamp(state.get("last_date", "1900-01-01")).date())]
    if not files: return add("Account", "Preview matched the booked close", "info", "No preview to compare yet.")
    pv = load(files[-1]); day = pv["date"]
    booked = {}
    for t in state["trades"]:
        if t["date"] == day: booked[t["ticker"]] = booked.get(t["ticker"], 0) + (t["shares"] if t["side"] == "BUY" else -t["shares"])
    booked = {k: v for k, v in booked.items() if abs(v) > 1e-6}
    plan = {o["ticker"]: (o["shares"] if o["side"] == "BUY" else -o["shares"]) for o in pv.get("orders", [])}
    diffs = [(t, plan.get(t, 0), booked.get(t, 0)) for t in sorted(set(plan) | set(booked)) if abs(plan.get(t, 0) - booked.get(t, 0)) > max(2, 0.05 * abs(booked.get(t, 0)))]
    if not diffs: add("Account", "Preview matched the booked close", "ok", f"{day}: preview orders matched the booked trades ({len(plan)} tickers).")
    else: add("Account", "Preview matched the booked close", "warn", f"{day}: " + "; ".join(f"{t} preview {a:+g}, booked {b:+g}" for t, a, b in diffs),
              "Prices moved after the preview. When live, compare your fills with the dashboard and adjust at the next order day.")

# ---------------------------------------------------------------------------- 4. configuration
def c_config():
    """Versions, calendars, token"""
    v = summary.get("meta", {}).get("version"); bt = load(os.path.join(HERE, "backtest.json"), {}).get("meta", {}).get("version")
    add("Configuration", "Versions match", "ok" if v == te.VERSION else "warn", f"Engine {te.VERSION}, dashboard data {v}, backtest {bt}." + ("" if bt == te.VERSION else " Backtest tab is from an older version."),
        "" if v == te.VERSION else "The next daily run rewrites the dashboard data.")
    fut = sorted(d for d in te.FOMC_DATES if d > TODAY)
    st_ = "ok" if len(fut) >= 5 else ("warn" if len(fut) >= 3 else "fail")
    add("Configuration", "Fed meeting dates", st_, f"{len(fut)} scheduled decisions left in the list (last {fut[-1]:%b %d, %Y})." if fut else "No future Fed dates.",
        "" if st_ == "ok" else "Ask Claude to add next year's FOMC dates (federalreserve.gov publishes them each summer).")
    last = pd.Timestamp(CAL.last_session).tz_localize(None); days = (last - TODAY).days
    add("Configuration", "Market holiday calendar", "ok" if days > 90 else "warn", f"Covers trading days through {last:%b %d, %Y}.",
        "" if days > 90 else "Update the exchange_calendars package (requirements.txt).")
    exp = pd.Timestamp(te.CRON_TOKEN_EXPIRES); left = (exp - TODAY).days
    add("Configuration", "cron-job.org GitHub token", "ok" if left > 30 else ("warn" if left > 7 else "fail"), f"Expires {exp:%b %d, %Y} ({left} days).",
        "" if left > 30 else "Create a new fine-grained token (this repo, Actions read/write) and paste it into both cron-job.org jobs. Then ask Claude to update the expiry date.")
    soon = [r for r in te.reminders(TODAY) if (pd.Timestamp(r["date"]) - TODAY).days <= 7]
    for r in soon: add("Reminders", r["what"], "info", f"{pd.Timestamp(r['date']):%a %b %d}. {r['note']}")
    add("Live trading", "Real account matches the paper account", "info", "Not checked automatically: there is no connection to Schwab yet. Compare your Schwab positions with the Positions tab after each order day.")

# ---------------------------------------------------------------------------- automatic fixes
MAX_TRIES = 3          # per problem per day; after that the problem is reported (GitHub issue -> phone)
prev_health = load(HEALTH_PATH, {}) or {}
rem = prev_health.get("remediation", {})
if rem.get("date") != str(TODAY.date()): rem = dict(date=str(TODAY.date()), counts={}, log=rem.get("log", [])[:30])

def running(name_start):
    return any(r["name"].startswith(name_start) and r["status"] in ("queued", "in_progress", "waiting", "pending") for r in RUNS)

SPACING = {"preview": 8, "daily": 25, "pages": 30, "enable": 30}   # minutes between tries (the health check also runs right after each run)

def fix(key, check_name, action, label):
    """try an automatic fix; the failed check becomes 'fixing' (no notification) unless today's tries are used up"""
    c = next((c for c in checks if c["name"] == check_name and c["status"] == "fail"), None)
    if c is None: return
    tries = rem["counts"].get(key, 0)
    last = rem.setdefault("last", {}).get(key)
    if last and tries < MAX_TRIES and (NOW - dt.datetime.fromisoformat(last)).total_seconds() < SPACING[key] * 60:
        c["status"] = "fixing"; c["detail"] += f" Automatic fix tried {tries} time(s); next try after {SPACING[key]} minutes."; return
    if tries >= MAX_TRIES:
        c["detail"] += f" Automatic fix tried {tries} times today without success."; return
    try:
        action(); rem["counts"][key] = tries + 1; rem["last"][key] = NOW.isoformat(timespec="seconds")
        rem["log"].insert(0, dict(t=NOW.isoformat(timespec="seconds"), what=label, result="started"))
        c["status"] = "fixing"; c["detail"] += f" Automatic fix: {label} (try {tries + 1} of {MAX_TRIES}). The health check runs again when it finishes."
        if key == "preview" and NOW >= CUTOFF - dt.timedelta(minutes=15): c["status"] = "fail"   # within 15 min of Schwab's MOC cutoff: tell the owner too
    except Exception as e:
        rem["log"].insert(0, dict(t=NOW.isoformat(timespec="seconds"), what=label, result=f"could not start: {e}"))
        c["detail"] += f" Automatic fix could not start: {e}"

def remediate():
    if not TOKEN: return
    # preview missing close to the cutoff: start it now (the engine's window check stops it if it's too late)
    if IS_SESSION and NOW < CUTOFF - dt.timedelta(minutes=3) and not running("Preview"):
        fix("preview", "Today's order preview", lambda: api("actions/workflows/preview.yml/dispatches", "POST", {"ref": "main", "inputs": {"window": "true"}}),
            "started 'Preview orders'")
    # close not booked (late, failed or crashed run): start the daily run again - it only books closes that are final
    if not running("Daily"):
        fix("daily", "Daily run booked the last close", lambda: api("actions/workflows/daily.yml/dispatches", "POST", {"ref": "main"}), "started 'Daily run'")
    # a disabled workflow: switch it back on
    c = next((c for c in checks if c["name"] == "Workflows enabled" and c["status"] == "fail"), None)
    if c:
        def enable():
            for w in api("actions/workflows").get("workflows", []):
                if w["state"] != "active": api(f"actions/workflows/{w['id']}/enable", "PUT")
        fix("enable", "Workflows enabled", enable, "re-enabled the disabled workflows")
    # live dashboard behind the repo for a while: ask GitHub Pages to publish again
    c = next((c for c in checks if c["name"] == "Dashboard is published and current" and c["status"] in ("warn", "fail")), None)
    lag_min = (NOW - dt.datetime.fromisoformat(prev_health["pages_lag_since"])).total_seconds() / 60 if prev_health.get("pages_lag_since") else 0
    if c and (c["status"] == "fail" or lag_min >= 45):
        c["status"] = "fail"; fix("pages", "Dashboard is published and current", lambda: api("pages/builds", "POST"), "asked GitHub Pages to republish")
    # a failed preview/daily run whose problem is already gone needs nothing; other failed workflows are reported as they are
    # within 15 minutes of Schwab's MOC cutoff a missing preview is always reported, even while a retry is pending
    c = next((c for c in checks if c["name"] == "Today's order preview" and c["status"] == "fixing"), None)
    if c and IS_SESSION and NOW >= CUTOFF - dt.timedelta(minutes=15): c["status"] = "fail"

# ---------------------------------------------------------------------------- run
for fn in (c_daily, c_preview, c_runs, c_trigger, c_workflows, c_pages, c_data, c_state, c_preview_vs_booked, c_config): safe(fn)
try: remediate()
except Exception as e: add("Health check", "Automatic fixes", "warn", f"Automatic fixes crashed: {e}")
order = {"fail": 0, "fixing": 1, "warn": 2, "pending": 3, "ok": 4, "info": 5}
n = {k: sum(c["status"] == k for c in checks) for k in order}
overall = "fail" if n["fail"] else ("warn" if n["warn"] or n["fixing"] else "ok")
prev = load(HEALTH_PATH, {})
hist = ([dict(t=NOW.isoformat(timespec="seconds"), overall=overall, fails=n["fail"], warns=n["warn"])] + prev.get("history", []))[:60]
out = dict(generated=NOW.isoformat(timespec="seconds"), generated_et=fmt_t(NOW), overall=overall, counts=n, version=te.VERSION,
           schedule="Every 30 minutes on weekdays 9:25 AM - 5:55 PM ET (cron-job.org), right after each preview and daily run, and hourly as a backup.",
           checks=checks, history=hist, remediation=rem,
           pages_lag_since=(prev_health.get("pages_lag_since") or NOW.isoformat(timespec="seconds")) if any(c["name"].startswith("Dashboard is published") and c["status"] != "ok" for c in checks) else None)
with open(HEALTH_PATH, "w") as f: json.dump(out, f, indent=1)
print(f"{overall.upper()}  fail {n['fail']} warn {n['warn']} ok {n['ok']}  ({fmt_t(NOW)})")
for c in checks: print(f"  [{c['status']:7s}] {c['group']}: {c['name']} - {c['detail']}")

# GitHub issue = phone notification when something fails; closed automatically when all pass again
if TOKEN:
    try:
        issues = api(f"issues?state=open&per_page=50"); mine = [i for i in issues if i.get("title") == ISSUE_TITLE and "pull_request" not in i]
        fails = [c for c in checks if c["status"] == "fail"]
        sig = "|".join(sorted(c["name"] + c["detail"][:40] for c in fails))
        if fails and (not mine or prev.get("fail_sig") != sig):
            body = f"@{OWNER} Health check at {fmt_t(NOW)} found {len(fails)} problem(s):\n\n" + "\n".join(f"- **{c['name']}**: {c['detail']}\n  - Fix: {c['fix']}" for c in fails) + f"\n\nDashboard: {PAGES}#health"
            if mine: api(f"issues/{mine[0]['number']}/comments", "POST", {"body": body})
            else: api("issues", "POST", {"title": ISSUE_TITLE, "body": body})
        if not fails and mine:
            for i in mine:
                api(f"issues/{i['number']}/comments", "POST", {"body": f"All checks pass again ({fmt_t(NOW)}). Closing."})
                api(f"issues/{i['number']}", "PATCH", {"state": "closed"})
        out["fail_sig"] = sig
        with open(HEALTH_PATH, "w") as f: json.dump(out, f, indent=1)
    except Exception as e:
        print("could not update the health issue:", e)
