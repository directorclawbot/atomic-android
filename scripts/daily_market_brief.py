#!/usr/bin/env python3
"""
Daily Market Brief HTML Generator
Produces a clean light-theme financial-newsletter style email.
"""
import subprocess
import os
import sys
import json
from datetime import datetime, timezone

# ─── HTML TEMPLATE ────────────────────────────────────────────────────────────
# Light theme: white/light-grey background, dark text, colored header accent
TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Market Insights — {date}</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f4f5f7; color: #1a1a2e; margin: 0; padding: 20px; font-size: 14px; line-height: 1.6; }}
  .wrapper {{ max-width: 700px; margin: 0 auto; }}
  .header {{ background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); color: #fff; padding: 24px 28px; border-radius: 12px 12px 0 0; }}
  .header h1 {{ margin: 0 0 6px 0; font-size: 22px; font-weight: 700; color: #fff; }}
  .header .meta {{ font-size: 12px; color: #a0a8c0; margin-bottom: 12px; }}
  .badge {{ display: inline-block; padding: 4px 12px; border-radius: 20px; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; }}
  .badge-green {{ background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }}
  .badge-red {{ background: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }}
  .badge-amber {{ background: #fff3cd; color: #856404; border: 1px solid #ffeeba; }}
  .card {{ background: #fff; border-radius: 0 0 12px 12px; padding: 20px 28px; margin-bottom: 16px; box-shadow: 0 1px 4px rgba(0,0,0,0.06); }}
  .card h2 {{ font-size: 14px; font-weight: 700; color: #1a1a2e; text-transform: uppercase; letter-spacing: 0.06em; margin: 0 0 14px 0; border-bottom: 1px solid #eef0f4; padding-bottom: 8px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  th {{ text-align: left; color: #6b7280; font-weight: 600; font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em; padding: 6px 8px; border-bottom: 2px solid #eef0f4; }}
  td {{ padding: 8px 8px; border-bottom: 1px solid #f4f5f7; }}
  tr:last-child td {{ border-bottom: none; }}
  .up {{ color: #15803d; font-weight: 600; }}
  .down {{ color: #b91c1c; font-weight: 600; }}
  .neutral {{ color: #6b7280; }}
  .ticker {{ font-weight: 700; color: #1a1a2e; }}
  .prob-grid {{ display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 12px; margin-top: 12px; }}
  .prob-box {{ border-radius: 8px; padding: 12px; text-align: center; }}
  .prob-bull {{ background: #d4edda; }}
  .prob-neut {{ background: #f3f4f6; }}
  .prob-bear {{ background: #f8d7da; }}
  .prob-box .pct {{ font-size: 24px; font-weight: 700; }}
  .prob-bull .pct {{ color: #15803d; }}
  .prob-neut .pct {{ color: #6b7280; }}
  .prob-bear .pct {{ color: #b91c1c; }}
  .prob-box .label {{ font-size: 11px; text-transform: uppercase; font-weight: 600; letter-spacing: 0.05em; margin-top: 2px; }}
  ul {{ margin: 0 0 12px 0; padding-left: 20px; }}
  li {{ margin-bottom: 6px; }}
  .tag {{ display: inline-block; background: #eef2f7; color: #3d5a80; font-size: 10px; padding: 2px 8px; border-radius: 20px; font-weight: 600; text-transform: uppercase; margin-right: 4px; }}
  .blunt {{ background: #1a1a2e; color: #fff; border-radius: 8px; padding: 16px 20px; margin-top: 12px; }}
  .blunt strong {{ color: #f0c040; }}
  .call-item {{ background: #f9fafb; border-left: 3px solid #15803d; padding: 10px 14px; border-radius: 0 6px 6px 0; margin-bottom: 10px; }}
  .call-item .conf {{ font-size: 11px; font-weight: 700; text-transform: uppercase; }}
  .call-item .conf.High {{ color: #15803d; }}
  .call-item .conf.Medium {{ color: #b45309; }}
  .call-item .conf.Low {{ color: #6b7280; }}
  .invalidation {{ background: #fff; border-left: 3px solid #b91c1c; padding: 10px 14px; border-radius: 0 6px 6px 0; margin-bottom: 6px; }}
  .section-divider {{ height: 1px; background: #eef0f4; margin: 16px 0; }}
  .footer {{ text-align: center; font-size: 11px; color: #9ca3af; padding: 16px 0; }}
  .watchlist-tag {{ background: #fef3c7; color: #92400e; }}
</style>
</head>
<body>
<div class="wrapper">

<!-- HEADER -->
<div class="header">
  <h1>Market Insights</h1>
  <div class="meta">{date} · {risk_badge} · Sources: Yahoo Finance / VIX / DXY ({fetch_time} UTC)</div>
  <div>{risk_label}</div>
</div>

<!-- MACRO CONTEXT -->
<div class="card">
  <h2>🌐 Market Tone & Macro Context</h2>
  <p style="margin:0 0 12px 0; font-size:14px; line-height:1.7;">{macro_tone}</p>
  <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap:10px; margin-top:12px;">
{vibe_cards}
  </div>
</div>

<!-- MARKET SNAPSHOT -->
<div class="card">
  <h2>📊 Market Snapshot</h2>
  <table>
    <thead>
      <tr>
        <th>Ticker</th>
        <th>Price</th>
        <th>% Change</th>
        <th>Signal</th>
      </tr>
    </thead>
    <tbody>
{snapshot_rows}
    </tbody>
  </table>
</div>

<!-- PROBABILITIES -->
<div class="card">
  <h2>🎯 Market Direction Probabilities</h2>
  <div class="prob-grid">
    <div class="prob-box prob-bull">
      <div class="pct">{bull_pct}%</div>
      <div class="label">🐂 Bull</div>
    </div>
    <div class="prob-box prob-neut">
      <div class="pct">{neut_pct}%</div>
      <div class="label">⚖️ Neutral</div>
    </div>
    <div class="prob-box prob-bear">
      <div class="pct">{bear_pct}%</div>
      <div class="label">🐻 Bear</div>
    </div>
  </div>
  <p style="font-size:12px; color:#6b7280; margin-top:12px; margin-bottom:0;">VIX: {vix} | DXY: {dxy} ({dxy_chg}) | 10Y: {ten_yr} | 5D Range: {five_day_range}</p>
</div>

<!-- THINGS TO WATCH -->
<div class="card">
  <h2>👀 Things to Watch Today</h2>
  <ul>
{watch_items}
  </ul>
</div>

<!-- TOP TRADERS -->
<div class="card">
  <h2>📈 Top 5 Traders to Watch</h2>
  <ul>
{top_traders}
  </ul>
</div>

<!-- REDDIT PULSE -->
<div class="card">
  <h2>💬 WallStreetBets / Reddit Pulse</h2>
  <ul>
{reddit_items}
  </ul>
</div>

<!-- BLUNT TAKE -->
<div class="card" style="background:#fafafa;">
  <h2>⚡ Blunt Take</h2>
  <div class="blunt">{blunt_take}</div>
</div>

<!-- TESTABLE CALLS -->
<div class="card">
  <h2>🎯 Testable Calls for Today</h2>
{testable_calls}
</div>

<!-- INVALIDATIONS -->
<div class="card">
  <h2>❌ What Would Prove This Wrong</h2>
{invalidations}
</div>

<div class="footer">
  Market Insights · {date} · Not financial advice · For informational purposes only
</div>

</div>
</body>
</html>\
"""


def format_row(ticker, price, pct_chg, signal="", highlight=False):
    """Format a single market snapshot table row."""
    cls = "up" if pct_chg.startswith("+") else "down" if pct_chg.startswith("-") else "neutral"
    arrow = "▲" if pct_chg.startswith("+") else "▼" if pct_chg.startswith("-") else ""
    return f"      <tr>\n        <td class=\"ticker\">{ticker}</td>\n        <td>{price}</td>\n        <td class=\"{cls}\">{arrow} {pct_chg}</td>\n        <td style=\"font-size:12px; color:#6b7280;\">{signal}</td>\n      </tr>"


def build_snapshot_rows(markets):
    """Build table rows from market dict."""
    rows = []
    for m in markets:
        cls = "up" if m["chg"].startswith("+") else "down" if m["chg"].startswith("-") else "neutral"
        arrow = "▲" if m["chg"].startswith("+") else "▼" if m["chg"].startswith("-") else ""
        highlight_flag = "🏆" if m.get("highlight") else ""
        rows.append(
            f'      <tr>\n'
            f'        <td class="ticker">{m["ticker"]}</td>\n'
            f'        <td>{m["price"]}</td>\n'
            f'        <td class="{cls}">{arrow} {m["chg"]}</td>\n'
            f'        <td style="font-size:12px; color:#6b7280;">{highlight_flag} {m.get("signal","")}</td>\n'
            f'      </tr>'
        )
    return "\n".join(rows)


def build_watch_items(items):
    return "\n".join(f"      <li>{i}</li>" for i in items)


def build_top_traders(traders):
    rows = []
    for t in traders:
        badge = f'<span class="tag watchlist-tag">{t["tag"]}</span>'
        rows.append(f"      <li>{badge} <strong>{t['name']}</strong> — {t['desc']}</li>")
    return "\n".join(rows)


def build_reddit_items(items):
    return "\n".join(f"      <li>{i}</li>" for i in items)


def build_vibe_cards(vibes):
    """Build macro context vibe cards."""
    rows = []
    for v in vibes:
        color = v.get("color", "#3d5a80")
        rows.append(
            f'      <div style="background:#f9fafb;border-left:3px solid {color};padding:10px 12px;border-radius:0 6px 6px 0;">'
            f'<div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:0.05em;color:{color};margin-bottom:4px;">{v["label"]}</div>'
            f'<div style="font-size:13px;line-height:1.5;">{v["value"]}</div></div>'
        )
    return "\n".join(rows)


def build_testable_calls(calls):
    rows = []
    for c in calls:
        rows.append(
            f'    <div class="call-item">\n'
            f'      <div class="conf {c["conf"]}">[{c["conf"]}]</div>\n'
            f'      <div><strong>{c["prediction"]}</strong></div>\n'
            f'      <div style="font-size:12px; color:#6b7280;">Driver: {c["driver"]}</div>\n'
            f'    </div>'
        )
    return "\n".join(rows)


def build_invalidations(items):
    return "\n".join(f'    <div class="invalidation">{i}</div>' for i in items)


def generate(market_data: dict, date: str = None) -> str:
    """Build the final HTML from market data dict."""
    if date is None:
        date = datetime.now(timezone.utc).strftime("%B %d, %Y")

    # Compute risk badge
    spy_chg = market_data.get("spy_chg_pct", 0)
    if spy_chg > 0.5:
        risk_badge = "🟢 Risk-On"
        risk_label = f'<span class="badge badge-green">Risk-On</span> SPY {spy_chg:+.2f}%'
    elif spy_chg < -0.5:
        risk_badge = "🔴 Risk-Off"
        risk_label = f'<span class="badge badge-red">Risk-Off</span> SPY {spy_chg:+.2f}%'
    else:
        risk_badge = "🟡 Cautious"
        risk_label = f'<span class="badge badge-amber">Cautious</span> SPY {spy_chg:+.2f}%'

    return TEMPLATE.format(
        date=date,
        risk_badge=risk_badge,
        risk_label=risk_label,
        fetch_time=market_data.get("fetch_time_utc", "00:00"),
        snapshot_rows=build_snapshot_rows(market_data.get("snapshot", [])),
        bull_pct=market_data.get("bull_pct", 40),
        neut_pct=market_data.get("neut_pct", 35),
        bear_pct=market_data.get("bear_pct", 25),
        vix=market_data.get("vix", "—"),
        dxy=market_data.get("dxy", "—"),
        dxy_chg=market_data.get("dxy_chg", "—"),
        ten_yr=market_data.get("ten_yr", "—"),
        five_day_range=market_data.get("five_day_range", "—"),
        watch_items=build_watch_items(market_data.get("watch", [])),
        top_traders=build_top_traders(market_data.get("traders", [])),
        reddit_items=build_reddit_items(market_data.get("reddit", [])),
        macro_tone=market_data.get("macro_tone", "The market is showing mixed signals. Awaiting further clarity."),
        vibe_cards=build_vibe_cards(market_data.get("vibes", [])),
        blunt_take=market_data.get("blunt_take", "Market is mixed. Awaiting further clarity."),
        testable_calls=build_testable_calls(market_data.get("calls", [])),
        invalidations=build_invalidations(market_data.get("invalids", [])),
    )


# ─── ERROR LOGGING ────────────────────────────────────────────────────────────
ERROR_LOG = "/home/user/.openclaw/workspace/tracking/state/cron-write-errors.json"
OUTPUT_FILE = "/tmp/market_brief.html"
MIN_OUTPUT_SIZE = 5000


def log_error(job_name: str, stage: str, message: str, details: str = ""):
    """Append an error entry to the cron-write-errors.json log."""
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "job": job_name,
        "stage": stage,
        "message": message,
        "details": details,
    }
    try:
        errors = []
        if os.path.exists(ERROR_LOG):
            try:
                with open(ERROR_LOG) as f:
                    errors = json.load(f)
            except (json.JSONDecodeError, IOError):
                errors = []
        errors.append(entry)
        # Keep last 100 entries to prevent unbounded growth
        with open(ERROR_LOG, "w") as f:
            json.dump(errors[-100:], f, indent=2)
    except Exception as e:
        print(f"WARNING: Could not write error log: {e}", file=sys.stderr)


# ─── STANDALONE RUN ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    job_name = "daily_market_brief"

    try:
        sample = {
            "spy_chg_pct": 0.99,
            "fetch_time_utc": "13:23",
            "vix": "16.81",
            "dxy": "97.92",
            "dxy_chg": "−0.91%",
            "ten_yr": "4.39%",
            "five_day_range": "$708–$720",
            "snapshot": [
                {"ticker": "SPY", "price": "$718.66", "chg": "+0.99%", "signal": "SPX +0.99%"},
                {"ticker": "QQQ", "price": "$667.74", "chg": "+0.93%", "signal": "Nasdaq +0.93%"},
                {"ticker": "IWM", "price": "$277.97", "chg": "+2.16%", "highlight": True, "signal": "Small caps leading"},
                {"ticker": "VTI", "price": "$354.18", "chg": "+1.13%", "signal": "Broad US rally"},
                {"ticker": "XLE", "price": "$59.65", "chg": "+1.05%", "signal": "Energy +1.05%"},
                {"ticker": "XLF", "price": "$52.13", "chg": "+0.40%", "signal": "Financials lagging"},
                {"ticker": "XLK", "price": "$159.50", "chg": "+0.25%", "signal": "Tech marginal"},
                {"ticker": "GLD", "price": "$423.66", "chg": "+1.50%", "highlight": True, "signal": "Gold strong"},
                {"ticker": "SLV", "price": "$66.66", "chg": "+2.81%", "highlight": True, "signal": "Metals outperforming"},
                {"ticker": "TLT", "price": "$85.62", "chg": "−0.09%", "signal": "Bonds flat"},
                {"ticker": "UUP", "price": "$27.36", "chg": "−0.91%", "highlight": True, "signal": "Dollar weak"},
                {"ticker": "XOM", "price": "$154.33", "chg": "−0.22%", "signal": "Oil drag"},
                {"ticker": "CVX", "price": "$193.31", "chg": "+0.57%", "signal": "Chevron soft"},
                {"ticker": "NUE", "price": "$225.29", "chg": "+1.30%", "signal": "Steel +1.30%"},
            ],
            "bull_pct": 50,
            "neut_pct": 30,
            "bear_pct": 20,
            "watch": [
                "<strong>Small-cap breakout endurance</strong> — IWM +2.16% is the standout. If it holds +1.5% through close, that's a real signal.",
                "<strong>SLV / GLD ratio</strong> — Silver outpacing gold often precedes reflation. Watch if it persists.",
                "<strong>Dollar breakdown</strong> — DXY at 97.92, down ~1%. Sustained break below 97.5 changes macro.",
                "<strong>XFL / XLK lag</strong> — Financials +0.40%, Tech +0.25% — unusual on broad risk-on day.",
                "<strong>AMD earnings May 5</strong> — First major tech report after tariff shock. NVDA May 20.",
            ],
            "traders": [
                {"name": "Silver/Gold ratio players", "tag": "Explicit", "desc": "SLV +2.81% vs GLD +1.50%"},
                {"name": "Small-cap rotation funds", "tag": "Inferred", "desc": "IWM leading"},
                {"name": "Dollar sellers", "tag": "Price Action", "desc": "DXY −0.91% on no clear news"},
                {"name": "Commodity desk rotation", "tag": "Inferred", "desc": "Sector swap within commodities"},
                {"name": "Fed rate path watchers", "tag": "Explicit", "desc": "FOMC May 7–8, ~2 cuts priced for 2026"},
            ],
            "macro_tone": "Today is a <strong>legitimate risk-on day</strong>, not a head-fake. Small caps are leading for once (IWM +2.16%), metals are screaming (SLV +2.81%), and the dollar is getting punched down (DXY −0.91%). That's a coherent macro picture — not random noise. The VIX at 16.8 means nobody's panicking, which leaves room for the rally to breathe. Energy is the only soft spot and it's marginal. The real test comes with AMD earnings on May 5 and the Fed meeting May 7–8.",
            "vibes": [
                {"label": "Breadth", "value": "Broad rally — all major ETFs positive", "color": "#15803d"},
                {"label": "Leadership", "value": "Small caps (IWM) + metals (SLV/GLD) leading megacap tech", "color": "#15803d"},
                {"label": "Macro Theme", "value": "Dollar weakness + supply disruption (oil/metals)", "color": "#1d4ed8"},
                {"label": "Hidden Risk", "value": "Fed May 7–8 + AMD May 5 could shift narrative fast", "color": "#b45309"},
            ],
            "reddit": [
                "<strong>VOW3 (Volkswagen)</strong> — Hot DD: Q1 net cash flow swung −€0.8B → +€2.0B. SEAT/CUPRA +760% yoy. Bull case on German autos / EV transition. <em>Source: r/wallstreetbets DD</em>",
                "<strong>AMC, GME</strong> — Low-level chatter, no fresh catalyst. <em>Low signal.</em>",
                "<strong>Nuclear/SMR chatter</strong> — Emerging Reddit buzz. No actionable position yet.",
            ],
            "blunt_take": "Today looks like a <strong>legitimate risk-on day</strong>, not a head-fake. Small caps leading (IWM +2.16%), metals screaming (SLV +2.81%), dollar getting punched down. That's a <strong>coherent macro picture</strong>. VIX at 16.8 means nobody's panicking, which leaves room for the rally to breathe. Energy is the lone soft spot. <strong>AMD on May 5 is the real test.</strong>",
            "calls": [
                {"conf": "High", "prediction": "IWM holds +1.0% or better through market close", "driver": "Broad risk-on + dollar weakness = small-cap fuel"},
                {"conf": "Medium", "prediction": "DXY closes below 97.50 for second consecutive day", "driver": "Already at 97.92; sustained break signals further weakness"},
                {"conf": "Medium", "prediction": "XLF or XLK catches up — closes positive > SPY (+0.99%) by end of session", "driver": "Laggard rotation = breadth confirmation"},
            ],
            "invalids": [
                "<strong>XLF or XLK flips red</strong> — Laggard rotation fails; breadth narrows. Classic fake-out.",
                "<strong>VIX reclaims 18.5</strong> — Complacency breaks. Could happen fast on hawkish Fed comment.",
                "<strong>Oil crashes further</strong> — XOM/CVX breakdown accelerates. Demand fears.",
                "<strong>DXY reverses to 98.5+</strong> — Dollar short squeeze reverses macro setup.",
                "<strong>IWM fades below +0.5% by noon</strong> — Early strength that can't be maintained = intraday reversal.",
            ],
        }

        html = generate(sample)

        # ── Deliverable existence + size check BEFORE proceeding ──
        with open(OUTPUT_FILE, "w") as f:
            f.write(html)

        file_size = os.path.getsize(OUTPUT_FILE)
        print(f"Written {file_size} chars to {OUTPUT_FILE}", file=sys.stderr)

        if file_size < MIN_OUTPUT_SIZE:
            msg = f"Output file {OUTPUT_FILE} is only {file_size} bytes (expected >{MIN_OUTPUT_SIZE})"
            print(f"ERROR: {msg}", file=sys.stderr)
            log_error(job_name, "output_verification", msg, f"size={file_size}")
            sys.exit(1)

        # ── Send email via gog ──
        result = subprocess.run(
            ["gog", "send",
             "--account", "directorclawbot@gmail.com",
             "--to", "robnield@gmail.com",
             "--subject", f"Market Insights — {datetime.now(timezone.utc).strftime('%B %d, %Y')}",
             "--body-html", html],
            capture_output=True, text=True, timeout=30,
        )

        if result.returncode != 0:
            msg = f"gog send failed with exit code {result.returncode}"
            print(f"ERROR: {msg}", file=sys.stderr)
            print(f"  STDOUT: {result.stdout[:300]}", file=sys.stderr)
            print(f"  STDERR: {result.stderr[:300]}", file=sys.stderr)
            log_error(job_name, "gog_send", msg,
                      f"stdout={result.stdout[:200]} stderr={result.stderr[:200]}")
            sys.exit(1)

        # Verify message_id in output — the definitive proof of send
        stdout = result.stdout.strip()
        if "message_id" not in stdout:
            msg = "gog send succeeded but no message_id in output — email may NOT have been sent"
            print(f"ERROR: {msg}", file=sys.stderr)
            print(f"  STDOUT: {stdout[:300]}", file=sys.stderr)
            log_error(job_name, "gog_send", msg, f"no_message_id stdout={stdout[:200]}")
            sys.exit(1)

        print(f"SUCCESS: Email sent. {stdout}", file=sys.stderr)
        sys.exit(0)

    except subprocess.TimeoutExpired:
        msg = "gog send timed out after 30 seconds"
        print(f"ERROR: {msg}", file=sys.stderr)
        log_error(job_name, "gog_send", msg, "timeout")
        sys.exit(1)
    except Exception as e:
        msg = f"Unexpected error: {e}"
        print(f"ERROR: {msg}", file=sys.stderr)
        log_error(job_name, "unexpected", msg, str(e))
        sys.exit(1)