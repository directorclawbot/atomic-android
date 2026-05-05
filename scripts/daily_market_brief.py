#!/usr/bin/env python3
"""
Daily Market Brief HTML Generator
Produces a clean light-theme financial-newsletter style email.
"""
import subprocess
import sys
from pathlib import Path
from datetime import datetime, timezone

WORKSPACE = Path('/home/user/.openclaw/workspace')
sys.path.insert(0, str(WORKSPACE / 'scripts'))

import cron_file
from daily_brief_fetch import get_market_summary

# ─── HTML TEMPLATE ────────────────────────────────────────────────────────────
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
  .footer {{ text-align: center; font-size: 11px; color: #9ca3af; padding: 16px 0; }}
  .watchlist-tag {{ background: #fef3c7; color: #92400e; }}
</style>
</head>
<body>
<div class="wrapper">
<div class="header">
  <h1>Market Insights</h1>
  <div class="meta">{date} · {risk_badge} · Sources: Yahoo Finance / VIX / DXY ({fetch_time} UTC)</div>
  <div>{risk_label}</div>
</div>
<div class="card">
  <h2>🌐 Market Tone & Macro Context</h2>
  <p style="margin:0 0 12px 0; font-size:14px; line-height:1.7;">{macro_tone}</p>
  <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap:10px; margin-top:12px;">
{vibe_cards}
  </div>
</div>
<div class="card">
  <h2>📊 Market Snapshot</h2>
  <table><thead><tr><th>Ticker</th><th>Price</th><th>% Change</th><th>Signal</th></tr></thead><tbody>
{snapshot_rows}
    </tbody></table>
</div>
<div class="card">
  <h2>🎯 Market Direction Probabilities</h2>
  <div class="prob-grid">
    <div class="prob-box prob-bull"><div class="pct">{bull_pct}%</div><div class="label">🐂 Bull</div></div>
    <div class="prob-box prob-neut"><div class="pct">{neut_pct}%</div><div class="label">⚖️ Neutral</div></div>
    <div class="prob-box prob-bear"><div class="pct">{bear_pct}%</div><div class="label">🐻 Bear</div></div>
  </div>
  <p style="font-size:12px; color:#6b7280; margin-top:12px; margin-bottom:0;">VIX: {vix} | DXY: {dxy} ({dxy_chg}) | 10Y: {ten_yr} | 5D Range: {five_day_range}</p>
</div>
<div class="card"><h2>👀 Things to Watch Today</h2><ul>
{watch_items}
</ul></div>
<div class="card"><h2>📈 Top 5 Traders to Watch</h2><ul>
{top_traders}
</ul></div>
<div class="card"><h2>💬 WallStreetBets / Reddit Pulse</h2><ul>
{reddit_items}
</ul></div>
<div class="card" style="background:#fafafa;"><h2>⚡ Blunt Take</h2><div class="blunt">{blunt_take}</div></div>
<div class="card"><h2>🎯 Testable Calls for Today</h2>
{testable_calls}
</div>
<div class="card"><h2>❌ What Would Prove This Wrong</h2>
{invalidations}
</div>
<div class="footer">Market Insights · {date} · Not financial advice · For informational purposes only</div>
</div>
</body>
</html>\
"""

ERROR_LOG = "/home/user/.openclaw/workspace/tracking/state/cron-write-errors.json"
OUTPUT_FILE = Path("/tmp/market_brief.html")
MIN_OUTPUT_SIZE = 5000


def format_row(ticker, price, pct_chg, signal="", highlight=False):
    cls = "up" if pct_chg.startswith("+") else "down" if pct_chg.startswith("-") else "neutral"
    arrow = "▲" if pct_chg.startswith("+") else "▼" if pct_chg.startswith("-") else ""
    return f"      <tr>\n        <td class=\"ticker\">{ticker}</td>\n        <td>{price}</td>\n        <td class=\"{cls}\">{arrow} {pct_chg}</td>\n        <td style=\"font-size:12px; color:#6b7280;\">{signal}</td>\n      </tr>"


def build_snapshot_rows(markets):
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
    if date is None:
        date = datetime.now(timezone.utc).strftime("%B %d, %Y")
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
        macro_tone=market_data.get("macro_tone", "Live market snapshot generated from current Yahoo Finance data."),
        vibe_cards=build_vibe_cards(market_data.get("vibes", [])),
        blunt_take=market_data.get("blunt_take", "Live market snapshot generated successfully."),
        testable_calls=build_testable_calls(market_data.get("calls", [])),
        invalidations=build_invalidations(market_data.get("invalids", [])),
    )


def log_error(job_name: str, stage: str, message: str, details: str = ""):
    cron_file.log_error(f"{job_name}:{stage}", ERROR_LOG, f"{message} | {details}" if details else message)


def build_live_market_data() -> dict:
    market_data = get_market_summary()
    rate_data = market_data.pop('rate_data', {}) or market_data.pop('rates', {}) or {}
    market_data.setdefault('dxy', '—')
    market_data.setdefault('dxy_chg', '—')
    market_data.setdefault('ten_yr', rate_data.get('^TNX', {}).get('value', '—'))
    market_data.setdefault('five_day_range', '—')
    market_data.setdefault('watch', [])
    market_data.setdefault('traders', [])
    market_data.setdefault('reddit', [])
    market_data.setdefault('vibes', [])
    market_data.setdefault('calls', [])
    market_data.setdefault('invalids', [])
    market_data.setdefault('macro_tone', 'Live market snapshot generated from current Yahoo Finance data.')
    market_data.setdefault('blunt_take', 'Live market snapshot generated successfully.')
    return market_data


if __name__ == "__main__":
    job_name = "daily_market_brief"
    try:
        market_data = build_live_market_data()
        html = generate(market_data)

        if not cron_file.safe_write_json_plain(OUTPUT_FILE, html):
            msg = f"Failed to write {OUTPUT_FILE}"
            print(f"ERROR: {msg}", file=sys.stderr)
            log_error(job_name, "output_write", msg)
            sys.exit(1)

        if not OUTPUT_FILE.exists():
            msg = f"Output file {OUTPUT_FILE} was not created"
            print(f"ERROR: {msg}", file=sys.stderr)
            log_error(job_name, "output_verification", msg)
            sys.exit(1)

        file_size = OUTPUT_FILE.stat().st_size
        print(f"Written {file_size} chars to {OUTPUT_FILE}", file=sys.stderr)
        if file_size < MIN_OUTPUT_SIZE:
            msg = f"Output file {OUTPUT_FILE} is only {file_size} bytes (expected >{MIN_OUTPUT_SIZE})"
            print(f"ERROR: {msg}", file=sys.stderr)
            log_error(job_name, "output_verification", msg, f"size={file_size}")
            sys.exit(1)

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
            log_error(job_name, "gog_send", msg, f"stdout={result.stdout[:200]} stderr={result.stderr[:200]}")
            sys.exit(1)

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
