#!/usr/bin/env python3
"""Sync events from SQLite to weekend-planner.json.

This reads all active/expired events from the events table and writes
a compatible JSON file that downstream consumers (weekend_candidate_report.py,
weekend_upsert_candidates.py) can use.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import sqlite3
from pathlib import Path

WORKSPACE = Path('/home/user/.openclaw/workspace')
DEFAULT_DB = WORKSPACE / 'tracking/state/weekend-research/weekend_sources.sqlite3'
DEFAULT_PLANNER = WORKSPACE / 'tracking/collections/weekend-planner.json'


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys=ON;')
    return conn


def strip_datetime_suffix(title: str) -> str:
    return re.sub(r'\s*\(\d{2}/\d{2}/\d{4}[^\)]*\)$', '', (title or '').strip()).strip()


def extract_date_parts(title: str) -> tuple[str, str]:
    title = (title or '').strip()
    m = re.search(r'\((\d{2}/\d{2}/\d{4})(?:\s+([^\)]+))?\)$', title)
    if not m:
        return '', 'Time not normalized yet'
    date_part = m.group(1)
    time_part = (m.group(2) or '').strip()
    try:
        parsed = dt.datetime.strptime(date_part, '%m/%d/%Y').date().isoformat()
    except Exception:
        parsed = date_part
    return parsed, time_part or 'Time not normalized yet'


def load_planner(planner_path: Path) -> dict:
    if planner_path.exists():
        return json.loads(planner_path.read_text(encoding='utf-8'))
    return {
        'version': 1,
        'collection': {
            'name': 'weekend-planner',
            'title': 'Weekend Planner',
            'description': 'Tracked weekend ideas, outings, pizza quest items, and repeat avoidance state',
            'default_category': 'weekend',
            'created_at': utc_now(),
            'updated_at': utc_now(),
        },
        'items': [],
    }


def classify(candidate: dict) -> tuple[str, list[str]]:
    blob = ' '.join([
        candidate.get('title', ''),
        candidate.get('description', ''),
        candidate.get('source_type', ''),
        candidate.get('tags', ''),
    ]).lower()
    if any(term in blob for term in ('museum', 'exhibit', 'exhibition', 'gallery')):
        return 'museum', ['weekend', 'museum', 'cultural']
    if any(term in blob for term in ('park', 'hike', 'trail', 'preserve', 'outdoors', 'nature', 'bike')):
        return 'parks', ['weekend', 'parks', 'outdoors']
    if any(term in blob for term in ('library', 'lecture', 'history', 'science', 'education', 'educational')):
        return 'education', ['weekend', 'education', 'interesting']
    if any(term in blob for term in ('festival', 'market', 'tour', 'studio', 'maker', 'art', 'arts', 'culture')):
        return 'event', ['weekend', 'event', 'interesting']
    return 'event', ['weekend', 'event']


def sync(args: argparse.Namespace) -> int:
    conn = connect(args.db)
    planner = load_planner(args.planner)
    now = utc_now()

    # Build existing key sets for dedup
    existing_titles = {item.get('title', '').strip().lower() for item in planner.get('items', [])}
    existing_urls = {item.get('source_url', '').strip().lower() for item in planner.get('items', [])}
    existing_keys = existing_titles | existing_urls

    # Query events
    rows = conn.execute(
        '''SELECT e.*, fs.source_name, fs.area, fs.source_type, fs.feed_url_or_page,
                  GROUP_CONCAT(et.tag) as tag_list
           FROM events e
           LEFT JOIN feed_sources fs ON fs.id = e.source_id
           LEFT JOIN event_tags et ON et.event_id = e.id
           WHERE e.status IN ('active', 'expired')
           GROUP BY e.id
           ORDER BY COALESCE(e.start_date, e.first_seen_at) DESC, e.id DESC'''
    ).fetchall()

    added = 0
    for row in rows:
        title = (row['title'] or '').strip()
        url = (row['url'] or '').strip()
        clean_title = strip_datetime_suffix(title)

        # Dedup against existing items
        dedupe_keys = [title.lower(), clean_title.lower()]
        if url:
            dedupe_keys.append(url.lower())
        if any(k and k in existing_keys for k in dedupe_keys):
            continue

        # Parse date/time from title suffix pattern
        parsed_date, parsed_time = extract_date_parts(title)

        category, categories = classify({
            'title': title,
            'description': row['description'] or '',
            'source_type': row['source_type'] or '',
            'tags': row['tag_list'] or '',
        })

        # Build record_id
        slug = re.sub(r'[^a-z0-9]+', '-', (row['source_name'] or 'event').lower())[:40] + '-' + re.sub(r'[^a-z0-9]+', '-', clean_title.lower() or title.lower())[:40]
        record_id = f"weekend-planner-{hashlib.sha1(slug.encode('utf-8')).hexdigest()[:12]}"

        item = {
            'summary': (row['description'] or '')[:400],
            'category': category,
            'categories': categories,
            'source_name': row['source_name'] or row['location_name'] or '',
            'source_url': url,
            'source_published_at': row['first_seen_at'] or now,
            'source_domain': '',
            'first_seen_at': row['first_seen_at'] or now,
            'last_seen_at': row['last_seen_at'] or now,
            'last_sent_at': None,
            'sent_count': 0,
            'seen_count': 1,
            'status': 'new',
            'thesis_status': 'watch',
            'rating': round(min(5.0, 2.5 + (row['quality_score'] or 0.5) * 3), 1),
            'notes': [],
            'follow_up': {'status': 'none', 'owner': '', 'due_at': None, 'notes': ''},
            'tags': [t for t in (row['tag_list'] or '').split(',') if t] if row['tag_list'] else [],
            'attributes': {
                'date': row['start_date'] or parsed_date or '',
                'time': row['start_time'] or parsed_time or '',
                'venue': row['location_name'] or '',
                'location': row['area'] or '',
                'cost': row['cost'] or 'Price not confirmed',
                'parking': 'Price not confirmed',
                'reason': 'Synced from events table',
                'source_feed': row['feed_url_or_page'] or '',
            },
            'history': [{'at': now, 'type': 'created', 'note': 'Imported from events table (sync)'}],
            'external_id': f"evt-{row['record_id']}",
            'title': clean_title or title,
            'collection': 'weekend-planner',
            'source_key': f"evt-{row['record_id']}",
            'record_id': record_id,
        }
        planner.setdefault('items', []).append(item)
        for k in dedupe_keys:
            if k:
                existing_keys.add(k)
        added += 1

    planner['collection']['updated_at'] = now
    args.planner.parent.mkdir(parents=True, exist_ok=True)
    _atomic_json_write(args.planner, planner)
    print(json.dumps({
        'added': added,
        'total_items': len(planner.get('items', [])),
        'planner': str(args.planner),
    }, indent=2))
    return 0


def _atomic_json_write(path: Path, data: Any) -> None:
    """Atomic write + read-back verification for weekend planner JSON files."""
    import os
    temp = str(path) + '.tmp'
    try:
        with open(temp, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write('\n')
        with open(temp, encoding='utf-8') as f:
            verify = json.load(f)
        if verify != data:
            raise RuntimeError(f'Write verification failed for {path}')
        os.replace(temp, path)
    except Exception as exc:
        import datetime as dt
        ERROR_LOG = Path('/home/user/.openclaw/workspace/tracking/state/cron-write-errors.json')
        errors = []
        try:
            ERROR_LOG.parent.mkdir(parents=True, exist_ok=True)
            if ERROR_LOG.exists():
                try:
                    errors = json.loads(ERROR_LOG.read_text()).get('errors', [])
                except Exception:
                    pass
        except Exception:
            pass
        errors.append({
            'ts': dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
            'file': str(path),
            'operation': 'write',
            'error': str(exc)[:500],
        })
        errors = errors[-100:]
        try:
            ERROR_LOG.write_text(json.dumps({'errors': errors}, indent=2) + '\n')
        except Exception:
            pass
        raise


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Sync events table to weekend-planner.json')
    parser.add_argument('--db', type=Path, default=DEFAULT_DB)
    parser.add_argument('--planner', type=Path, default=DEFAULT_PLANNER)
    parser.set_defaults(func=sync)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == '__main__':
    raise SystemExit(main())