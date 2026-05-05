#!/usr/bin/env python3
"""Upsert high-quality events from SQLite into weekend-planner.json.

Reads events from the events table (quality_score >= threshold, status = 'active')
and upserts them into the weekend-planner.json collection. Avoids duplicates
by checking existing titles and URLs.
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
        return '', ''
    date_part = m.group(1)
    time_part = (m.group(2) or '').strip()
    try:
        parsed = dt.datetime.strptime(date_part, '%m/%d/%Y').date().isoformat()
    except Exception:
        parsed = date_part
    return parsed, time_part


def classify(blob: str) -> tuple[str, list[str]]:
    blob_lower = blob.lower()
    if any(t in blob_lower for t in ('museum', 'exhibit', 'exhibition', 'gallery')):
        return 'museum', ['weekend', 'museum', 'cultural']
    if any(t in blob_lower for t in ('park', 'hike', 'trail', 'preserve', 'outdoors', 'nature', 'camp')):
        return 'parks', ['weekend', 'parks', 'outdoors']
    if any(t in blob_lower for t in ('library', 'lecture', 'history', 'science', 'education')):
        return 'education', ['weekend', 'education', 'interesting']
    if any(t in blob_lower for t in ('festival', 'market', 'tour', 'studio', 'maker', 'art', 'concert', 'music')):
        return 'event', ['weekend', 'event', 'interesting']
    return 'event', ['weekend', 'event']


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


def upsert(db_path: Path, planner_path: Path, min_quality: float) -> dict[str, int]:
    conn = connect(db_path)
    planner = load_planner(planner_path)
    now = utc_now()

    # Build existing dedup sets
    existing_titles = {item.get('title', '').strip().lower() for item in planner.get('items', [])}
    existing_urls = {item.get('source_url', '').strip().lower() for item in planner.get('items', [])}
    existing_keys = existing_titles | existing_urls

    rows = conn.execute(
        '''SELECT e.*, fs.source_name, fs.area, fs.source_type, fs.feed_url_or_page,
                  GROUP_CONCAT(et.tag) as tag_list
           FROM events e
           LEFT JOIN feed_sources fs ON fs.id = e.source_id
           LEFT JOIN event_tags et ON et.event_id = e.id
           WHERE e.quality_score >= ? AND e.status = 'active'
           GROUP BY e.id
           ORDER BY e.quality_score DESC, COALESCE(e.start_date, e.first_seen_at) DESC''',
        (min_quality,),
    ).fetchall()

    inserted = 0
    skipped = 0
    for row in rows:
        title = (row['title'] or '').strip()
        url = (row['url'] or '').strip()
        clean_title = strip_datetime_suffix(title)

        dedupe_keys = [title.lower(), clean_title.lower()]
        if url:
            dedupe_keys.append(url.lower())

        if any(k and k in existing_keys for k in dedupe_keys):
            skipped += 1
            continue

        parsed_date, parsed_time = extract_date_parts(title)
        blob = f"{title} {row['description'] or ''} {row['source_type'] or ''}"
        category, categories = classify(blob)

        slug = f"{(row['source_name'] or 'event').lower()[:40]}-{clean_title.lower()[:40]}"
        slug = re.sub(r'[^a-z0-9]+', '-', slug).strip('-')
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
                'reason': f"Quality score {round(row['quality_score'], 2)} from events pipeline",
                'source_feed': row['feed_url_or_page'] or '',
                'candidate_score': round((row['quality_score'] or 0.5) * 10, 1),
            },
            'history': [{'at': now, 'type': 'created', 'note': 'Imported from events table via upsert'}],
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
        inserted += 1

    planner['collection']['updated_at'] = now
    planner_path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_json_write(planner_path, planner)
    return {'inserted': inserted, 'skipped': skipped}


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


def main() -> int:
    parser = argparse.ArgumentParser(description='Upsert high-quality events into weekend-planner.json')
    parser.add_argument('--db', type=Path, default=DEFAULT_DB)
    parser.add_argument('--planner', type=Path, default=DEFAULT_PLANNER)
    parser.add_argument('--min-quality', type=float, default=0.7,
                        help='Minimum quality_score to import (0-1, default: 0.7)')
    args = parser.parse_args()

    result = upsert(args.db, args.planner, args.min_quality)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())