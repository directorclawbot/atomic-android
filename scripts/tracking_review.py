#!/usr/bin/env python3
import argparse
import html
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

WORKSPACE = Path('/home/user/.openclaw/workspace')
TRACKING_DIR = WORKSPACE / 'tracking'
COLLECTIONS_DIR = TRACKING_DIR / 'collections'
INDEX_PATH = TRACKING_DIR / '_index.json'
REVIEW_DIR = TRACKING_DIR / 'review'

sys.path.insert(0, str(WORKSPACE / 'scripts'))
import cron_file


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text())


def esc(value: Any) -> str:
    return html.escape('' if value is None else str(value))


def collection_files() -> List[Path]:
    return sorted(COLLECTIONS_DIR.glob('*.json'))


def status_counts(items: List[Dict[str, Any]]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for item in items:
        status = item.get('status') or 'unknown'
        counts[status] = counts.get(status, 0) + 1
    return counts


def priority_queries(all_items: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    ordered = sorted(all_items, key=lambda x: (x.get('rating') is not None, x.get('rating') or -1, x.get('last_seen_at') or ''), reverse=True)
    return {
        'high_rating_unsent': [x for x in ordered if x.get('status') not in ('sent', 'archived') and (x.get('rating') or 0) >= 4.0][:25],
        'needs_follow_up': [x for x in ordered if (x.get('follow_up') or {}).get('status') not in ('none', 'done', '')][:25],
        'degraded_or_pricey': [x for x in ordered if x.get('thesis_status') in ('degraded', 'pricey', 'fading', 'needs-vin-check')][:25],
        'recently_sent': [x for x in sorted(all_items, key=lambda x: x.get('last_sent_at') or '', reverse=True) if x.get('last_sent_at')][:25],
    }


def item_card(item: Dict[str, Any]) -> str:
    attrs = item.get('attributes') or {}
    attr_bits = []
    for key in ('price', 'shipping', 'mileage', 'size', 'brand', 'trim', 'location', 'listing_platform', 'ticker', 'importance'):
        if key in attrs:
            attr_bits.append(f"<span class='pill'><strong>{esc(key)}</strong>: {esc(attrs.get(key))}</span>")
    notes = ''.join(f'<li>{esc(note)}</li>' for note in (item.get('notes') or [])[:4])
    return f"""
    <article class='card'>
      <div class='meta-row'>
        <span class='status status-{esc(item.get('status') or 'unknown')}'>{esc(item.get('status') or 'unknown')}</span>
        <span class='status thesis'>{esc(item.get('thesis_status') or 'untriaged')}</span>
        <span class='muted'>rating: {esc(item.get('rating'))}</span>
        <span class='muted'>seen: {esc(item.get('last_seen_at'))}</span>
      </div>
      <h3>{esc(item.get('title'))}</h3>
      <p>{esc(item.get('summary') or '')}</p>
      <div class='meta-row'>{''.join(attr_bits)}</div>
      <div class='meta-row'>
        <a href='{esc(item.get('source_url') or '#')}'>{esc(item.get('source_name') or item.get('source_domain') or 'source')}</a>
        <span class='muted'>{esc(item.get('record_id'))}</span>
      </div>
      <ul>{notes}</ul>
    </article>
    """


def render_index(collections: List[Dict[str, Any]], queries: Dict[str, List[Dict[str, Any]]]) -> str:
    collection_rows = ''.join(
        f"<tr><td><a href='./{esc(c['slug'])}.html'>{esc(c['title'])}</a></td><td>{c['item_count']}</td><td>{esc(c['updated_at'])}</td><td>{esc(c['statuses'])}</td></tr>"
        for c in collections
    )
    query_sections = []
    for name, items in queries.items():
        query_sections.append(f"<section><h2>{esc(name.replace('_', ' '))}</h2>{''.join(item_card(item) for item in items) or '<p class=\'muted\'>No items.</p>'}</section>")
    return page_template('Tracking Review', f"""
      <section>
        <h1>Tracking review</h1>
        <p class='muted'>Generated {esc(now_iso())}. Static local review surface over tracking collections.</p>
        <table>
          <thead><tr><th>Collection</th><th>Items</th><th>Updated</th><th>Status mix</th></tr></thead>
          <tbody>{collection_rows}</tbody>
        </table>
      </section>
      {''.join(query_sections)}
    """)


def render_collection_page(title: str, slug: str, items: List[Dict[str, Any]]) -> str:
    cards = ''.join(item_card(item) for item in sorted(items, key=lambda x: x.get('last_seen_at') or '', reverse=True))
    return page_template(title, f"""
      <section>
        <p><a href='./index.html'>← back to index</a></p>
        <h1>{esc(title)}</h1>
        <p class='muted'>{len(items)} items in {esc(slug)}</p>
        {cards or '<p>No items yet.</p>'}
      </section>
    """)


def page_template(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang='en'>
<head>
  <meta charset='utf-8' />
  <meta name='viewport' content='width=device-width, initial-scale=1' />
  <title>{esc(title)}</title>
  <style>
    body {{ font-family: Inter, system-ui, sans-serif; margin: 2rem auto; max-width: 1100px; padding: 0 1rem; background: #0f1115; color: #e8ecf1; }}
    a {{ color: #8bc3ff; }}
    table {{ width: 100%; border-collapse: collapse; margin: 1rem 0 2rem; }}
    th, td {{ border-bottom: 1px solid #26303b; padding: 0.65rem; text-align: left; vertical-align: top; }}
    .card {{ border: 1px solid #26303b; border-radius: 12px; padding: 1rem; margin: 0 0 1rem; background: #151922; }}
    .meta-row {{ display: flex; flex-wrap: wrap; gap: 0.5rem; align-items: center; margin-bottom: 0.6rem; }}
    .pill {{ display: inline-block; border-radius: 999px; padding: 0.2rem 0.6rem; background: #1f2631; font-size: 0.9rem; }}
    .status {{ display: inline-block; border-radius: 999px; padding: 0.2rem 0.6rem; font-size: 0.85rem; font-weight: 600; background: #243041; }}
    .status-new {{ background: #173b2d; }}
    .status-sent {{ background: #243a62; }}
    .status-archived {{ background: #46313d; }}
    .thesis {{ background: #40351c; }}
    .muted {{ color: #96a1ad; }}
    h1, h2, h3 {{ line-height: 1.2; }}
    ul {{ margin: 0.6rem 0 0 1.2rem; }}
  </style>
</head>
<body>
{body}
</body>
</html>
"""


def build_review() -> Dict[str, Any]:
    REVIEW_DIR.mkdir(parents=True, exist_ok=True)
    collections_meta = []
    all_items: List[Dict[str, Any]] = []
    for path in collection_files():
        data = load_json(path, {'collection': {}, 'items': []})
        meta = data.get('collection') or {}
        items = data.get('items') or []
        slug = path.stem
        for item in items:
            item['_collection_slug'] = slug
            item['_collection_title'] = meta.get('title') or slug
        all_items.extend(items)
        collections_meta.append({
            'slug': slug,
            'title': meta.get('title') or slug,
            'item_count': len(items),
            'updated_at': meta.get('updated_at') or '',
            'statuses': ', '.join(f"{k}:{v}" for k, v in sorted(status_counts(items).items())) or 'none',
        })
        try:
            (REVIEW_DIR / f'{slug}.html').write_text(render_collection_page(meta.get('title') or slug, slug, items))
        except Exception as exc:
            cron_file.log_error('tracking_review_html', str(REVIEW_DIR / f'{slug}.html'), str(exc))

    queries = priority_queries(all_items)
    try:
        (REVIEW_DIR / 'index.html').write_text(render_index(collections_meta, queries))
    except Exception as exc:
        cron_file.log_error('tracking_review_html', str(REVIEW_DIR / 'index.html'), str(exc))

    snapshot = {
        'generated_at': now_iso(),
        'collections': collections_meta,
        'queries': {name: [item.get('record_id') for item in items] for name, items in queries.items()},
    }
    if not cron_file.safe_write_json(REVIEW_DIR / 'summary.json', snapshot):
        cron_file.log_error('tracking_review_summary', str(REVIEW_DIR / 'summary.json'), 'safe_write_json returned False')
    return snapshot


def cmd_build(args: argparse.Namespace) -> None:
    print(json.dumps(build_review(), indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Build a static local review surface over tracking collections.')
    sub = parser.add_subparsers(dest='command', required=True)
    build_parser_ = sub.add_parser('build', help='Render static review files under tracking/review/')
    build_parser_.set_defaults(func=cmd_build)
    return parser


if __name__ == '__main__':
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)
