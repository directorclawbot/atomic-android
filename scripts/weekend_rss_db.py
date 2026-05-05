#!/usr/bin/env python3
"""Weekend research RSS/Page source importer and fetcher.

Creates and updates a small SQLite database that stores:
- source metadata imported from a CSV
- optional evergreen map/list sources (parks, museums, etc.)
- fetched RSS/Atom entries with lightweight dedupe
- normalized events with venues, tags, and quality scores

This is intentionally stdlib-only so it can run anywhere Python 3 is available.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import os
import re
import sqlite3
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from pathlib import Path

WORKSPACE_PATH = Path('/home/user/.openclaw/workspace')
sys.path.insert(0, str(WORKSPACE_PATH / 'scripts'))
import cron_file
from typing import Iterable

WORKSPACE = Path('/home/user/.openclaw/workspace')
DEFAULT_DB = WORKSPACE / 'tracking/state/weekend-research/weekend_sources.sqlite3'
DEFAULT_CSV = WORKSPACE / 'tmp/weekend_rss_build/rss_sources.csv'
DEFAULT_PLANNER = WORKSPACE / 'tracking/collections/weekend-planner.json'
DEFAULT_TIMEOUT = 25
USER_AGENT = 'Director-WeekendResearch/1.0 (+local stdlib fetcher)'

# Keywords for auto-tagging and quality scoring
EVENT_KEYWORDS = {
    'museum', 'museums', 'park', 'parks', 'monument', 'history', 'science', 'library', 'lecture', 'lectures',
    'festival', 'fest', 'art', 'arts', 'culture', 'cultural', 'garden', 'botanical', 'zoo', 'wildlife', 'hike',
    'maker', 'makerspace', 'technology', 'workshop', 'astronomy', 'planetarium', 'education', 'educational',
    'exhibit', 'exhibition', 'historic', 'heritage', 'outdoors', 'nature', 'community', 'tour', 'market',
    'preserve', 'trail', 'bike', 'global', 'studio', 'brew', 'beer', 'wine', 'class', 'kids', 'family',
    'concert', 'music', 'dance', 'theater', 'performance', 'film', 'screening', 'reading', 'book',
}
NEGATIVE_KEYWORDS = {
    'meeting', 'board', 'commission', 'committee', 'budget', 'advisory', 'hearing', 'agenda', 'minutes',
    'lighting', 'awareness', 'cancelled', 'canceled', 'forum', 'recruitment', 'regulatory', 'town hall',
    'candidates', 'election', 'vote', 'primary', 'campaign',
}
CATEGORY_MAP = {
    'museum': ['museum', 'exhibit', 'exhibition', 'gallery'],
    'parks': ['park', 'hike', 'trail', 'preserve', 'outdoors', 'nature', 'bike', 'camp'],
    'education': ['library', 'lecture', 'history', 'science', 'education', 'educational', 'astronomy'],
    'arts': ['art', 'arts', 'gallery', 'theater', 'dance', 'music', 'concert', 'performance', 'film'],
    'community': ['community', 'festival', 'market', 'fair', 'celebration'],
    'maker': ['maker', 'makerspace', 'workshop', 'class', 'technology', 'build'],
    'food': ['brew', 'beer', 'wine', 'food', 'tasting', 'restaurant'],
}


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def connect(db_path: Path) -> sqlite3.Connection:
    ensure_parent(db_path)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL;')
    conn.execute('PRAGMA foreign_keys=ON;')
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        '''
        CREATE TABLE IF NOT EXISTS source_lists (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            kind TEXT NOT NULL,
            url TEXT NOT NULL,
            notes TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS feed_sources (
            id INTEGER PRIMARY KEY,
            source_name TEXT NOT NULL,
            area TEXT,
            source_type TEXT,
            tags TEXT,
            access_type TEXT,
            feed_url_or_page TEXT NOT NULL,
            source_page_url TEXT,
            notes TEXT,
            status TEXT NOT NULL DEFAULT 'active',
            last_imported_at TEXT,
            last_checked_at TEXT,
            last_success_at TEXT,
            last_error_at TEXT,
            last_error TEXT,
            etag TEXT,
            last_modified TEXT,
            fetch_count INTEGER NOT NULL DEFAULT 0,
            item_count INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(source_name, feed_url_or_page)
        );

        CREATE TABLE IF NOT EXISTS feed_items (
            id INTEGER PRIMARY KEY,
            source_id INTEGER NOT NULL REFERENCES feed_sources(id) ON DELETE CASCADE,
            guid TEXT,
            title TEXT,
            url TEXT,
            summary TEXT,
            author TEXT,
            category TEXT,
            published_at TEXT,
            raw_date TEXT,
            hash TEXT NOT NULL,
            raw_json TEXT,
            first_seen_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL,
            UNIQUE(source_id, hash)
        );

        CREATE INDEX IF NOT EXISTS idx_feed_items_source_published ON feed_items(source_id, published_at);
        CREATE INDEX IF NOT EXISTS idx_feed_items_url ON feed_items(url);
        CREATE INDEX IF NOT EXISTS idx_feed_sources_status ON feed_sources(status);

        -- Events schema
        CREATE TABLE IF NOT EXISTS venues (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            normalized_name TEXT UNIQUE,
            address TEXT,
            city TEXT DEFAULT 'Gilbert',
            state TEXT DEFAULT 'AZ',
            lat REAL,
            lng REAL,
            source_url TEXT,
            created_at TEXT DEFAULT (CURRENT_TIMESTAMP),
            updated_at TEXT DEFAULT (CURRENT_TIMESTAMP)
        );

        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            record_id TEXT UNIQUE NOT NULL,
            source_id INTEGER,
            venue_id INTEGER,
            title TEXT NOT NULL,
            description TEXT,
            url TEXT UNIQUE,
            start_date DATE,
            end_date DATE,
            start_time TEXT,
            end_time TEXT,
            all_day INTEGER DEFAULT 0,
            timezone TEXT DEFAULT 'America/Phoenix',
            location_name TEXT,
            location_address TEXT,
            cost TEXT,
            cost_amount REAL,
            currency TEXT DEFAULT 'USD',
            age_range TEXT,
            category TEXT,
            registration_url TEXT,
            organizer TEXT,
            status TEXT DEFAULT 'active',
            quality_score REAL DEFAULT 0.5,
            view_count INTEGER DEFAULT 0,
            last_seen_at TEXT,
            first_seen_at TEXT DEFAULT (CURRENT_TIMESTAMP),
            updated_at TEXT DEFAULT (CURRENT_TIMESTAMP),
            FOREIGN KEY (source_id) REFERENCES feed_sources(id) ON DELETE SET NULL,
            FOREIGN KEY (venue_id) REFERENCES venues(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS event_tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL,
            tag TEXT NOT NULL,
            source TEXT DEFAULT 'auto',
            created_at TEXT DEFAULT (CURRENT_TIMESTAMP),
            FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE,
            UNIQUE(event_id, tag)
        );

        CREATE TABLE IF NOT EXISTS event_venues (
            event_id INTEGER,
            venue_id INTEGER,
            PRIMARY KEY(event_id, venue_id)
        );

        CREATE INDEX IF NOT EXISTS idx_events_status ON events(status);
        CREATE INDEX IF NOT EXISTS idx_events_start_date ON events(start_date);
        CREATE INDEX IF NOT EXISTS idx_events_category ON events(category);
        CREATE INDEX IF NOT EXISTS idx_event_tags_event ON event_tags(event_id);
        CREATE INDEX IF NOT EXISTS idx_event_tags_tag ON event_tags(tag);
        CREATE INDEX IF NOT EXISTS idx_venues_normalized ON venues(normalized_name);
        '''
    )
    conn.commit()

    # ---- Additive migration: dedupe_key columns and indexes ----
    # Runs after schema so existing tables exist. Uses PRAGMA to check columns.
    conn.execute('PRAGMA user_version = 1;')
    feed_cols = {r['name'] for r in conn.execute('PRAGMA table_info(feed_items)').fetchall()}
    event_cols = {r['name'] for r in conn.execute('PRAGMA table_info(events)').fetchall()}

    if 'dedupe_key' not in feed_cols:
        conn.execute('ALTER TABLE feed_items ADD COLUMN dedupe_key TEXT;')
    if 'dedupe_key' not in event_cols:
        conn.execute('ALTER TABLE events ADD COLUMN dedupe_key TEXT;')

    # Backfill dedupe_key for any rows that don't have it yet
    for row in conn.execute(
            'SELECT id, url, title, raw_date FROM feed_items WHERE dedupe_key IS NULL OR dedupe_key = ""'
    ).fetchall():
        key = make_dedupe_key({'url': row['url'], 'title': row['title'], 'raw_date': row['raw_date']})
        conn.execute('UPDATE feed_items SET dedupe_key = ? WHERE id = ?', (key, row['id']))
    for row in conn.execute(
            'SELECT id, url, title, start_date FROM events WHERE dedupe_key IS NULL OR dedupe_key = ""'
    ).fetchall():
        key = compute_dedupe_key_for_event(row['url'], row['title'], row['start_date'])
        conn.execute('UPDATE events SET dedupe_key = ? WHERE id = ?', (key, row['id']))

    # Create partial indexes for fast cross-source dedup lookups
    conn.execute('CREATE INDEX IF NOT EXISTS idx_feed_items_dedupe_key ON feed_items(dedupe_key) WHERE dedupe_key != "";')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_events_dedupe_key ON events(dedupe_key) WHERE dedupe_key != "";')
    conn.commit()


def normalize_text(value: str | None) -> str:
    return (value or '').strip()


def normalize_url_for_dedup(url: str | None) -> str:
    """Normalize a URL for cross-source deduplication.
    Strips fragments, trailing slashes, and common tracking params."""
    url = (url or '').strip().lower()
    if not url:
        return ''
    # Strip fragment
    url = url.split('#')[0]
    # Strip trailing slash
    url = url.rstrip('/')
    # Basic cleanup of whitespace
    url = re.sub(r'\s+', '', url)
    return url


def normalize_title_for_dedup(title: str | None) -> str:
    """Normalize a title for cross-source deduplication.
    Lowercase, collapse whitespace, remove special chars."""
    title = (title or '').strip().lower()
    title = re.sub(r'[^a-z0-9\s]+', ' ', title)
    title = re.sub(r'\s+', ' ', title).strip()
    return title


def make_dedupe_key(item: dict[str, str]) -> str:
    """Build a cross-source dedupe key for a feed item.
    Prefers normalized URL; falls back to normalized title+date."""
    norm_url = normalize_url_for_dedup(item.get('url'))
    if norm_url:
        return f'url:{norm_url}'
    norm_title = normalize_title_for_dedup(item.get('title'))
    raw_date = (item.get('raw_date') or '').strip()
    if norm_title and raw_date:
        return f'title:{norm_title}|date:{raw_date}'
    elif norm_title:
        return f'title:{norm_title}'
    return ''


def normalize_location_name(name: str) -> str:
    """Create a normalized venue name for dedup."""
    name = (name or '').strip().lower()
    name = re.sub(r'[^a-z0-9]+', ' ', name)
    return re.sub(r'\s+', ' ', name).strip()


def parse_csv(conn: sqlite3.Connection, csv_path: Path) -> dict[str, int]:
    now = utc_now()
    inserted = 0
    updated = 0
    with csv_path.open('r', encoding='utf-8', newline='') as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            source_name = normalize_text(row.get('source_name'))
            url = normalize_text(row.get('feed_url_or_page'))
            if not source_name or not url:
                continue
            existing = conn.execute(
                'SELECT id FROM feed_sources WHERE source_name = ? AND feed_url_or_page = ?',
                (source_name, url),
            ).fetchone()
            payload = (
                source_name,
                normalize_text(row.get('area')),
                normalize_text(row.get('source_type')),
                normalize_text(row.get('tags')),
                normalize_text(row.get('access_type')),
                url,
                normalize_text(row.get('source_page_url')),
                normalize_text(row.get('notes')),
            )
            if existing:
                conn.execute(
                    '''
                    UPDATE feed_sources
                    SET area=?, source_type=?, tags=?, access_type=?, source_page_url=?,
                        notes=?, last_imported_at=?, updated_at=?
                    WHERE id=?
                    ''',
                    payload[1:4] + (payload[4], payload[6], payload[7], now, now, existing['id']),
                )
                updated += 1
            else:
                conn.execute(
                    '''
                    INSERT INTO feed_sources (
                        source_name, area, source_type, tags, access_type, feed_url_or_page,
                        source_page_url, notes, last_imported_at, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''',
                    payload + (now, now, now),
                )
                inserted += 1
    conn.commit()
    return {'inserted': inserted, 'updated': updated}


def upsert_source_list(conn: sqlite3.Connection, name: str, kind: str, url: str, notes: str = '') -> None:
    now = utc_now()
    conn.execute(
        '''
        INSERT INTO source_lists (name, kind, url, notes, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(name) DO UPDATE SET
            kind=excluded.kind,
            url=excluded.url,
            notes=excluded.notes,
            updated_at=excluded.updated_at
        ''',
        (name, kind, url, notes, now, now),
    )
    conn.commit()


def add_default_lists(conn: sqlite3.Connection) -> None:
    upsert_source_list(
        conn,
        'parks-map',
        'google-maps-list',
        'https://maps.app.goo.gl/CzZv7b3PSgmHvYZG7?g_st=ac',
        'Rob-provided park map/list source for weekend research.',
    )
    upsert_source_list(
        conn,
        'museums-map',
        'google-maps-list',
        'https://maps.app.goo.gl/Rpb7M68teXpGrrZM8?g_st=ac',
        'Rob-provided museum map/list source for weekend research.',
    )


def fetch_url(url: str, etag: str | None = None, last_modified: str | None = None, timeout: int = DEFAULT_TIMEOUT):
    headers = {'User-Agent': USER_AGENT, 'Accept': 'application/rss+xml, application/atom+xml, application/xml, text/xml, */*'}
    if etag:
        headers['If-None-Match'] = etag
    if last_modified:
        headers['If-Modified-Since'] = last_modified
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read()
        return {
            'status': getattr(resp, 'status', 200),
            'body': body,
            'etag': resp.headers.get('ETag'),
            'last_modified': resp.headers.get('Last-Modified'),
            'content_type': resp.headers.get('Content-Type', ''),
            'final_url': resp.geturl(),
        }


def child_text(node: ET.Element, *names: str) -> str:
    for name in names:
        found = node.find(name)
        if found is not None and found.text:
            return found.text.strip()
    return ''


def first_link(entry: ET.Element) -> str:
    for link in entry.findall('{*}link') + entry.findall('link'):
        href = link.attrib.get('href')
        if href:
            return href.strip()
        if link.text:
            return link.text.strip()
    return ''


def parse_date(raw: str) -> str:
    raw = normalize_text(raw)
    if not raw:
        return ''
    try:
        return parsedate_to_datetime(raw).astimezone(dt.timezone.utc).isoformat()
    except Exception:
        pass
    try:
        parsed = dt.datetime.fromisoformat(raw.replace('Z', '+00:00'))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=dt.timezone.utc)
        return parsed.astimezone(dt.timezone.utc).isoformat()
    except Exception:
        return ''


def parse_feed(xml_bytes: bytes) -> list[dict[str, str]]:
    root = ET.fromstring(xml_bytes)
    tag = root.tag.lower()
    items: list[dict[str, str]] = []

    if tag.endswith('rss') or tag.endswith('rdf'):
        channel = root.find('channel')
        nodes = channel.findall('item') if channel is not None else root.findall('.//item')
        for item in nodes:
            title = child_text(item, 'title')
            link = child_text(item, 'link')
            guid = child_text(item, 'guid') or link or title
            summary = child_text(item, 'description', 'summary')
            author = child_text(item, 'author', '{http://purl.org/dc/elements/1.1/}creator')
            category = child_text(item, 'category')
            raw_date = child_text(item, 'pubDate', '{http://purl.org/dc/elements/1.1/}date')
            items.append({
                'guid': guid,
                'title': title,
                'url': link,
                'summary': summary,
                'author': author,
                'category': category,
                'raw_date': raw_date,
                'published_at': parse_date(raw_date),
            })
        return items

    if tag.endswith('feed'):
        nodes = root.findall('{*}entry') or root.findall('entry')
        for entry in nodes:
            title = child_text(entry, '{*}title', 'title')
            link = first_link(entry)
            guid = child_text(entry, '{*}id', 'id') or link or title
            summary = child_text(entry, '{*}summary', '{*}content', 'summary', 'content')
            author_node = entry.find('{*}author') or entry.find('author')
            author = ''
            if author_node is not None:
                author = child_text(author_node, '{*}name', 'name')
            category = ''
            category_node = entry.find('{*}category') or entry.find('category')
            if category_node is not None:
                category = normalize_text(category_node.attrib.get('term') or category_node.text)
            raw_date = child_text(entry, '{*}updated', '{*}published', 'updated', 'published')
            items.append({
                'guid': guid,
                'title': title,
                'url': link,
                'summary': summary,
                'author': author,
                'category': category,
                'raw_date': raw_date,
                'published_at': parse_date(raw_date),
            })
        return items

    raise ValueError(f'Unsupported feed root tag: {root.tag}')


def item_hash(item: dict[str, str]) -> str:
    base = '||'.join([
        normalize_text(item.get('guid')),
        normalize_text(item.get('title')),
        normalize_text(item.get('url')),
        normalize_text(item.get('raw_date')),
    ])
    return hashlib.sha256(base.encode('utf-8')).hexdigest()


def store_items(conn: sqlite3.Connection, source_id: int, items: Iterable[dict[str, str]]) -> tuple[int, int, int]:
    """Store feed items with cross-source deduplication.

    Returns (inserted, updated, skipped_cross_source) counts.
    Cross-source dedup uses:
    - Normalized URL match (preferred): if the same URL exists from any source, skip
    - Normalized title+date match (fallback): if same title+date exists from any source, skip

    The existing hash-based same-source dedup is preserved for that layer.
    """
    inserted = 0
    updated = 0
    skipped = 0
    now = utc_now()
    for item in items:
        h = item_hash(item)

        # First: same-source dedup via hash (existing behavior, preserves same-source updates)
        existing_same = conn.execute(
            'SELECT id, dedupe_key FROM feed_items WHERE source_id = ? AND hash = ?',
            (source_id, h),
        ).fetchone()

        # Compute cross-source dedupe_key for this item
        dedupe_key = make_dedupe_key(item)

        if existing_same:
            # Same source, same item — update as before
            conn.execute(
                '''
                UPDATE feed_items
                SET title=?, url=?, summary=?, author=?, category=?, published_at=?, raw_date=?,
                    raw_json=?, last_seen_at=?, dedupe_key=?
                WHERE id=?
                ''',
                (
                    item.get('title', ''), item.get('url', ''), item.get('summary', ''), item.get('author', ''),
                    item.get('category', ''), item.get('published_at', ''), item.get('raw_date', ''),
                    json.dumps(item, ensure_ascii=False), now, dedupe_key,
                    existing_same['id'],
                ),
            )
            updated += 1
        elif dedupe_key:
            # Cross-source dedup check: does this dedupe_key exist from any source?
            existing_cross = conn.execute(
                'SELECT id FROM feed_items WHERE dedupe_key = ?',
                (dedupe_key,),
            ).fetchone()
            if existing_cross:
                # Skip — same item (URL or title+date) already exists from another source
                skipped += 1
                continue

            # No cross-source duplicate — insert
            conn.execute(
                '''
                INSERT INTO feed_items (
                    source_id, guid, title, url, summary, author, category, published_at,
                    raw_date, hash, raw_json, dedupe_key, first_seen_at, last_seen_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                (
                    source_id, item.get('guid', ''), item.get('title', ''), item.get('url', ''),
                    item.get('summary', ''), item.get('author', ''), item.get('category', ''),
                    item.get('published_at', ''), item.get('raw_date', ''),
                    h, json.dumps(item, ensure_ascii=False), dedupe_key, now, now,
                ),
            )
            inserted += 1
        else:
            # No dedupe_key possible (no URL, no title) — insert with empty dedupe_key
            conn.execute(
                '''
                INSERT INTO feed_items (
                    source_id, guid, title, url, summary, author, category, published_at,
                    raw_date, hash, raw_json, dedupe_key, first_seen_at, last_seen_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                (
                    source_id, item.get('guid', ''), item.get('title', ''), item.get('url', ''),
                    item.get('summary', ''), item.get('author', ''), item.get('category', ''),
                    item.get('published_at', ''), item.get('raw_date', ''),
                    h, json.dumps(item, ensure_ascii=False), dedupe_key, now, now,
                ),
            )
            inserted += 1

    return inserted, updated, skipped


# ---- Events helpers ----

def compute_quality_score(title: str, description: str, cost: str, venue_name: str, source_type: str) -> float:
    """Compute a 0-1 quality score for an event."""
    score = 0.5
    blob = ' '.join([title or '', description or '', source_type or '']).lower()

    # Has meaningful description
    if len(description or '') > 50:
        score += 0.1
    # Has substantial content
    if len(description or '') > 200:
        score += 0.05

    # Has cost info (anything except "not confirmed")
    if cost and cost not in ('', 'Price not confirmed'):
        score += 0.1
        # Free events get a small boost
        if 'free' in cost.lower() or cost.strip() == '0':
            score += 0.05

    # Has a venue (normalized location)
    if venue_name and len(venue_name) > 2:
        score += 0.1

    # Good keywords in title/description
    hit_count = sum(1 for kw in EVENT_KEYWORDS if kw in blob)
    score += min(0.15, hit_count * 0.02)

    # Negative keywords penalize
    neg_hits = sum(1 for kw in NEGATIVE_KEYWORDS if kw in blob)
    score -= min(0.2, neg_hits * 0.05)

    # Source type reliability bonus
    if any(t in (source_type or '').lower() for t in ['library', 'college', 'museum', 'community']):
        score += 0.1

    # Title length reasonable (not too short, not bloated)
    title_len = len(title or '')
    if 10 <= title_len <= 100:
        score += 0.05

    return max(0.0, min(1.0, score))


def auto_tag(title: str, description: str, location_name: str, category: str) -> list[str]:
    """Auto-generate tags from event content."""
    tags: set[str] = set()
    blob = ' '.join([title or '', description or '', location_name or '']).lower()

    # Location-based tags
    location_lower = (location_name or '').lower()
    for city in ['mesa', 'phoenix', 'chandler', 'gilbert', 'tempe', 'scottsdale', 'apache junction']:
        if city in location_lower:
            tags.add(city)

    # Keyword-based tags
    for kw in EVENT_KEYWORDS:
        if kw in blob:
            tags.add(kw)

    # Category tag
    if category:
        tags.add(category.lower())

    # Quality indicators
    if 'free' in blob:
        tags.add('free')
    if any(t in blob for t in ['kids', 'family', 'all ages']):
        tags.add('family')
    if any(t in blob for t in ['21+', 'adult', 'mature']):
        tags.add('21+')

    return sorted(tags)[:15]


def classify_event(title: str, description: str, source_type: str) -> str:
    """Classify event into a primary category."""
    blob = ' '.join([title or '', description or '', source_type or '']).lower()
    for cat, keywords in CATEGORY_MAP.items():
        if any(kw in blob for kw in keywords):
            return cat
    return 'event'


def make_record_id(title: str, url: str) -> str:
    """Create a stable record ID for an event."""
    base = f"{title or ''}|{url or ''}"
    h = hashlib.sha1(base.encode('utf-8')).hexdigest()[:12]
    return f"evt-{h}"


def extract_date_from_text(text: str) -> tuple[str | None, str | None, bool]:
    """Try to extract a date, time, and all_day from text. Tries multiple formats."""
    if not text:
        return None, None, False

    # MM/DD/YYYY or MM/DD/YYYY H:MM AM/PM (e.g. "04/11/2026 9:00 AM - 2:00 PM")
    m = re.search(r'(\d{1,2})/(\d{1,2})/(\d{4})', text)
    if m:
        try:
            parsed = dt.datetime(int(m.group(3)), int(m.group(1)), int(m.group(2)))
            date_str = parsed.date().isoformat()
            # Look for time range in the same text
            time_m = re.search(r'(\d{1,2}:\d{2}\s*(?:AM|PM)?)\s*-\s*(\d{1,2}:\d{2}\s*(?:AM|PM)?)', text, re.I)
            if time_m:
                time_str = time_m.group(1)
            return date_str, time_str, False
        except Exception:
            pass

    # Try ISO date
    iso_m = re.search(r'\d{4}-\d{2}-\d{2}', text)
    if iso_m:
        date_str = iso_m.group()
        time_m = re.search(r'\d{1,2}:\d{2}', text)
        time_str = time_m.group() if time_m else None
        return date_str, time_str, False

    # Try written month
    m = re.search(r'\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4}', text, re.I)
    if not m:
        m = re.search(r'\b\d{1,2}\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4}', text, re.I)
    if m:
        try:
            parsed = dt.datetime.strptime(m.group(), '%b %d %Y')
            return parsed.date().isoformat(), None, False
        except Exception:
            pass

    # Check for all-day indicators
    all_day = any(t in text.lower() for t in ['all day', 'all-day', 'entire day', 'continuous'])
    return None, None, all_day


def compute_dedupe_key_for_event(url: str | None, title: str | None, start_date: str | None) -> str:
    """Build a dedupe key for an event (mirrors make_dedupe_key logic for events table)."""
    norm_url = normalize_url_for_dedup(url)
    if norm_url:
        return f'url:{norm_url}'
    norm_title = normalize_title_for_dedup(title)
    if norm_title and start_date:
        return f'title:{norm_title}|date:{start_date}'
    elif norm_title:
        return f'title:{norm_title}'
    return ''


def upsert_event_from_feed_item(conn: sqlite3.Connection, feed_row: sqlite3.Row) -> str:
    """Upsert a single feed_item into the events table. Returns record_id.

    Cross-source deduplication:
    - URL match (any source): skip if active event with same normalized URL exists
    - Title+date match (any source): skip if active event with same title+date exists

    Same-source duplicates are handled by the caller (store_items already deduped
    feed_items by this point), so here we focus on cross-source event dedup.
    """
    title = normalize_text(feed_row['title'])
    url = normalize_text(feed_row['url'])
    if not title:
        return ''

    record_id = make_record_id(title, url)
    now = utc_now()

    # Extract date/time from raw_date or published_at
    date_str = None
    time_str = None
    all_day = False
    raw_date = feed_row['raw_date'] or feed_row['published_at'] or ''
    # Prefer date from title since feed publish dates are often wrong
    title_for_date = feed_row['title'] or ''
    # Try title first (it contains the actual event date)
    date_str, time_str, all_day = None, None, False
    if title_for_date:
        date_str, time_str, all_day = extract_date_from_text(title_for_date)
    # Fall back to feed publish date only if title gave nothing
    if not date_str and raw_date:
        date_str, time_str, all_day = extract_date_from_text(raw_date)

    # Compute dedupe_key for cross-source dedup in events table
    dedupe_key = compute_dedupe_key_for_event(url, title, date_str)

    # Try to get venue from source_name (area field)
    source_name = normalize_text(feed_row['source_name'] or '')
    area = normalize_text(feed_row['area'] or '')
    venue_name = source_name or area or ''
    venue_id = None

    if venue_name:
        norm_venue = normalize_location_name(venue_name)
        existing = conn.execute('SELECT id FROM venues WHERE normalized_name = ?', (norm_venue,)).fetchone()
        if existing:
            venue_id = existing['id']
        else:
            cursor = conn.execute(
                'INSERT INTO venues (name, normalized_name, city, source_url) VALUES (?, ?, ?, ?)',
                (venue_name, norm_venue, 'Gilbert', feed_row['feed_url_or_page'] or ''),
            )
            venue_id = cursor.lastrowid

    # Determine source_id
    source_id = feed_row['source_id']

    # Compute quality
    source_type = normalize_text(feed_row['source_type'] or '')
    quality = compute_quality_score(title, feed_row['summary'] or '', '', venue_name, source_type)

    # Classify
    category = classify_event(title, feed_row['summary'] or '', source_type)

    # Cross-source dedup check: look for existing active event with same dedupe_key from ANY source
    existing_by_dedupe_key = None
    if dedupe_key:
        existing_by_dedupe_key = conn.execute(
            'SELECT id, record_id, url FROM events WHERE dedupe_key = ? AND status = "active"',
            (dedupe_key,),
        ).fetchone()

    if existing_by_dedupe_key:
        # Cross-source duplicate — skip silently (don't create another event)
        return existing_by_dedupe_key['record_id']

    # No cross-source duplicate found via dedupe_key — proceed with insert
    # (URL-based check as fallback for events that predate the dedupe_key column)
    existing_by_url = conn.execute('SELECT id, record_id FROM events WHERE url = ?', (url,)).fetchone() if url else None
    existing_by_title = None
    if date_str:
        existing_by_title = conn.execute(
            'SELECT id, record_id FROM events WHERE title = ? AND start_date = ? AND status = "active"',
            (title, date_str),
        ).fetchone()

    if existing_by_url:
        # Update existing record (URL match, possibly from pre-dedupe-key data)
        conn.execute(
            '''UPDATE events SET title=?, description=?, source_id=?, venue_id=?, start_date=?,
               start_time=?, all_day=?, location_name=?, category=?, quality_score=?,
               last_seen_at=?, updated_at=?, dedupe_key=COALESCE(dedupe_key, dedupe_key)
            WHERE url=?''',
            (title, feed_row['summary'], source_id, venue_id, date_str, time_str, all_day,
             venue_name, category, quality, now, now, url),
        )
        event_id = existing_by_url['id']
        if existing_by_url['record_id'] != record_id:
            conn.execute('UPDATE events SET record_id=? WHERE id=?', (record_id, event_id))
        if dedupe_key:
            conn.execute('UPDATE events SET dedupe_key=? WHERE id=?', (dedupe_key, event_id))
    elif existing_by_title:
        # Fuzzy duplicate — mark as duplicate
        conn.execute(
            '''UPDATE events SET status="duplicate", last_seen_at=?, updated_at=?
            WHERE id=?''',
            (now, now, existing_by_title['id']),
        )
        # Still insert the new one but mark it
        conn.execute(
            '''INSERT INTO events (record_id, source_id, venue_id, title, description, url,
               start_date, start_time, all_day, location_name, category, status, quality_score,
               last_seen_at, first_seen_at, updated_at, dedupe_key)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, "duplicate", ?, ?, ?, ?, ?)''',
            (record_id, source_id, venue_id, title, feed_row['summary'], url,
             date_str, time_str, all_day, venue_name, category, quality, now, now, now, dedupe_key),
        )
        event_id = conn.execute('SELECT last_insert_rowid()').fetchone()[0]
    else:
        # Fresh insert
        conn.execute(
            '''INSERT INTO events (record_id, source_id, venue_id, title, description, url,
               start_date, start_time, all_day, location_name, category, status, quality_score,
               last_seen_at, first_seen_at, updated_at, dedupe_key)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, "active", ?, ?, ?, ?, ?)''',
            (record_id, source_id, venue_id, title, feed_row['summary'], url,
             date_str, time_str, all_day, venue_name, category, quality, now, now, now, dedupe_key),
        )
        event_id = conn.execute('SELECT last_insert_rowid()').fetchone()[0]

    # Auto-generate and insert tags
    tags = auto_tag(title, feed_row['summary'] or '', venue_name, category)
    for tag in tags:
        conn.execute(
            'INSERT OR IGNORE INTO event_tags (event_id, tag, source) VALUES (?, ?, "auto")',
            (event_id, tag),
        )

    return record_id


def sync_feed_items_to_events(conn: sqlite3.Connection) -> dict[str, int]:
    """Sync all feed_items into events table. Idempotent."""
    now = utc_now()
    rows = conn.execute(
        '''SELECT fi.*, fs.source_name, fs.area, fs.source_type, fs.feed_url_or_page
           FROM feed_items fi
           JOIN feed_sources fs ON fs.id = fi.source_id
           ORDER BY COALESCE(fi.published_at, fi.first_seen_at) DESC'''
    ).fetchall()

    inserted = 0
    updated = 0
    for row in rows:
        try:
            rid = upsert_event_from_feed_item(conn, row)
            if rid:
                inserted += 1
        except Exception as exc:
            print(f"  Warning: failed to upsert event for feed_item {row['id']}: {exc}", file=sys.stderr)
    conn.commit()
    return {'events_synced': inserted}


def fetch_sources(conn: sqlite3.Connection, limit: int | None = None, source_id: int | None = None, active_only: bool = True) -> list[dict[str, object]]:
    sql = 'SELECT * FROM feed_sources'
    clauses = []
    params: list[object] = []
    if active_only:
        clauses.append("status = 'active'")
    if source_id is not None:
        clauses.append('id = ?')
        params.append(source_id)
    if clauses:
        sql += ' WHERE ' + ' AND '.join(clauses)
    sql += ' ORDER BY id'
    if limit is not None:
        sql += ' LIMIT ?'
        params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    results = []
    for row in rows:
        results.append(dict(row))
    return results


def update_source_status(conn: sqlite3.Connection, source_id: int, **fields) -> None:
    if not fields:
        return
    fields['updated_at'] = utc_now()
    cols = ', '.join(f'{k} = ?' for k in fields)
    vals = list(fields.values()) + [source_id]
    conn.execute(f'UPDATE feed_sources SET {cols} WHERE id = ?', vals)
    conn.commit()


def cmd_init(args: argparse.Namespace) -> int:
    conn = connect(args.db)
    init_db(conn)
    add_default_lists(conn)
    print(f'initialized {args.db}')
    return 0


def cmd_import_csv(args: argparse.Namespace) -> int:
    conn = connect(args.db)
    init_db(conn)
    add_default_lists(conn)
    result = parse_csv(conn, args.csv)
    print(json.dumps({'db': str(args.db), 'csv': str(args.csv), **result}, indent=2))
    return 0


def cmd_fetch(args: argparse.Namespace) -> int:
    conn = connect(args.db)
    init_db(conn)
    sources = fetch_sources(conn, limit=args.limit, source_id=args.source_id, active_only=not args.include_inactive)
    summary = {'checked': 0, 'inserted': 0, 'updated': 0, 'failed': 0, 'not_modified': 0}
    for source in sources:
        sid = int(source['id'])
        url = str(source['feed_url_or_page'])
        summary['checked'] += 1
        try:
            result = fetch_url(url, etag=source.get('etag'), last_modified=source.get('last_modified'), timeout=args.timeout)
            xml_bytes = result['body']
            items = parse_feed(xml_bytes)
            inserted, updated, skipped = store_items(conn, sid, items)
            total_items = conn.execute('SELECT COUNT(*) AS c FROM feed_items WHERE source_id = ?', (sid,)).fetchone()[0]
            update_source_status(
                conn,
                sid,
                last_checked_at=utc_now(),
                last_success_at=utc_now(),
                last_error=None,
                last_error_at=None,
                etag=result.get('etag'),
                last_modified=result.get('last_modified'),
                fetch_count=int(source.get('fetch_count', 0)) + 1,
                item_count=total_items,
            )
            summary['inserted'] += inserted
            summary['updated'] += updated
            if args.verbose:
                print(f"[{sid}] ok {source['source_name']} -> +{inserted} new / {updated} updated / {skipped} cross-source skipped")
        except urllib.error.HTTPError as exc:
            if exc.code == 304:
                summary['not_modified'] += 1
                update_source_status(conn, sid, last_checked_at=utc_now())
                if args.verbose:
                    print(f'[{sid}] 304 not modified {source["source_name"]}')
            else:
                summary['failed'] += 1
                update_source_status(conn, sid, last_checked_at=utc_now(), last_error_at=utc_now(), last_error=f'HTTP {exc.code}: {exc.reason}')
                if args.verbose:
                    print(f'[{sid}] failed HTTP {exc.code} {source["source_name"]}')
        except Exception as exc:
            summary['failed'] += 1
            update_source_status(conn, sid, last_checked_at=utc_now(), last_error_at=utc_now(), last_error=str(exc))
            if args.verbose:
                print(f'[{sid}] failed {source["source_name"]}: {exc}')

    # After fetch, sync feed_items → events
    if summary['inserted'] > 0 or summary['updated'] > 0:
        sync_result = sync_feed_items_to_events(conn)
        if args.verbose:
            print(f"  events sync: {sync_result}")

    print(json.dumps(summary, indent=2))
    return 0 if summary['failed'] == 0 else 1


def cmd_sync_to_json(args: argparse.Namespace) -> int:
    """Sync events table to weekend-planner.json."""
    conn = connect(args.db)
    init_db(conn)
    now = utc_now()

    rows = conn.execute(
        '''SELECT e.*, fs.source_name, GROUP_CONCAT(et.tag) as tag_list
           FROM events e
           LEFT JOIN feed_sources fs ON fs.id = e.source_id
           LEFT JOIN event_tags et ON et.event_id = e.id
           WHERE e.status IN ("active", "expired")
           GROUP BY e.id
           ORDER BY COALESCE(e.start_date, e.first_seen_at) DESC'''
    ).fetchall()

    planner_path = args.planner or DEFAULT_PLANNER
    planner_path = Path(planner_path)
    if planner_path.exists():
        planner = json.loads(planner_path.read_text(encoding='utf-8'))
    else:
        planner = {
            'version': 1,
            'collection': {
                'name': 'weekend-planner',
                'title': 'Weekend Planner',
                'description': 'Tracked weekend ideas, outings, pizza quest items, and repeat avoidance state',
                'default_category': 'weekend',
                'created_at': now,
                'updated_at': now,
            },
            'items': [],
        }

    existing_titles = {item.get('title', '').lower() for item in planner.get('items', [])}
    existing_urls = {item.get('source_url', '').lower() for item in planner.get('items', [])}
    existing_keys = existing_titles | existing_urls

    added = 0
    for row in rows:
        title = (row['title'] or '').strip()
        url = (row['url'] or '').strip()
        if title.lower() in existing_titles or (url and url.lower() in existing_urls):
            continue

        # Build item compatible with existing weekend_candidate_report.py consumers
        category = row['category'] or 'event'
        item = {
            'title': title,
            'summary': (row['description'] or '')[:400],
            'category': category,
            'categories': ['weekend', category],
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
            'rating': round(min(5.0, 0.5 + row['quality_score'] * 4.5), 1),
            'notes': [],
            'follow_up': {'status': 'none', 'owner': '', 'due_at': None, 'notes': ''},
            'tags': [t for t in (row['tag_list'] or '').split(',') if t] if row['tag_list'] else [],
            'attributes': {
                'date': row['start_date'] or '',
                'time': row['start_time'] or '',
                'venue': row['location_name'] or '',
                'location': '',
                'cost': row['cost'] or 'Price not confirmed',
                'age_range': row['age_range'] or '',
            },
            'history': [{'at': now, 'type': 'created', 'note': 'Imported from events table'}],
            'external_id': f"evt-{row['record_id']}",
            'collection': 'weekend-planner',
            'source_key': f"evt-{row['record_id']}",
            'record_id': f"weekend-planner-{row['record_id']}",
        }
        planner.setdefault('items', []).append(item)
        existing_titles.add(title.lower())
        if url:
            existing_urls.add(url.lower())
        added += 1

    planner['collection']['updated_at'] = now
    planner_path.parent.mkdir(parents=True, exist_ok=True)
    ok = cron_file.safe_write_json(planner_path, planner)
    if not ok:
        print(json.dumps({'error': 'failed to write planner file', 'path': str(planner_path)}))
        return 1
    print(json.dumps({'planner': str(planner_path), 'added': added, 'total_items': len(planner.get('items', []))}, indent=2))
    return 0


def cmd_list_sources(args: argparse.Namespace) -> int:
    conn = connect(args.db)
    init_db(conn)
    rows = conn.execute(
        'SELECT id, source_name, area, source_type, access_type, feed_url_or_page, item_count, last_success_at, last_error FROM feed_sources ORDER BY id'
    ).fetchall()
    for row in rows:
        print(json.dumps(dict(row), ensure_ascii=False))
    return 0


def cmd_recent(args: argparse.Namespace) -> int:
    conn = connect(args.db)
    init_db(conn)
    rows = conn.execute(
        '''
        SELECT fi.id, fs.source_name, fi.title, fi.url, fi.published_at, fi.first_seen_at
        FROM feed_items fi
        JOIN feed_sources fs ON fs.id = fi.source_id
        ORDER BY COALESCE(fi.published_at, fi.first_seen_at) DESC, fi.id DESC
        LIMIT ?
        ''',
        (args.limit,),
    ).fetchall()
    for row in rows:
        print(json.dumps(dict(row), ensure_ascii=False))
    return 0


def cmd_purge(args: argparse.Namespace) -> int:
    """Delete events older than --days threshold (default 30 days)."""
    conn = connect(args.db)
    init_db(conn)
    cutoff = dt.date.today() - dt.timedelta(days=args.days)
    cur = conn.cursor()
    cur.execute('DELETE FROM event_tags WHERE event_id IN (SELECT id FROM events WHERE start_date < ?)', (str(cutoff),))
    cur.execute('DELETE FROM events WHERE start_date < ?', (str(cutoff),))
    deleted = cur.rowcount
    conn.commit()
    print(f'Deleted {deleted} events with start_date before {cutoff}')
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Weekend research RSS/page source database utility')
    parser.add_argument('--db', type=Path, default=DEFAULT_DB, help=f'SQLite DB path (default: {DEFAULT_DB})')
    sub = parser.add_subparsers(dest='command', required=True)

    p_init = sub.add_parser('init', help='Initialize the SQLite database')
    p_init.set_defaults(func=cmd_init)

    p_import = sub.add_parser('import-csv', help='Import source rows from CSV')
    p_import.add_argument('--csv', type=Path, default=DEFAULT_CSV, help=f'CSV path (default: {DEFAULT_CSV})')
    p_import.set_defaults(func=cmd_import_csv)

    p_fetch = sub.add_parser('fetch', help='Fetch RSS/Atom items for imported sources')
    p_fetch.add_argument('--limit', type=int, default=None, help='Only fetch the first N sources')
    p_fetch.add_argument('--source-id', type=int, default=None, help='Fetch a single source by id')
    p_fetch.add_argument('--timeout', type=int, default=DEFAULT_TIMEOUT, help='HTTP timeout in seconds')
    p_fetch.add_argument('--include-inactive', action='store_true', help='Also include inactive sources')
    p_fetch.add_argument('--verbose', action='store_true', help='Print per-source progress')
    p_fetch.set_defaults(func=cmd_fetch)

    p_sync = sub.add_parser('sync-to-json', help='Sync events table to weekend-planner.json')
    p_sync.add_argument('--planner', type=Path, default=None, help=f'Output planner path (default: {DEFAULT_PLANNER})')
    p_sync.set_defaults(func=cmd_sync_to_json)

    p_list = sub.add_parser('list-sources', help='List imported sources')
    p_list.set_defaults(func=cmd_list_sources)

    p_recent = sub.add_parser('recent', help='Show most recent stored items')
    p_recent.add_argument('--limit', type=int, default=20)
    p_recent.set_defaults(func=cmd_recent)

    p_purge = sub.add_parser('purge', help='Delete events older than --days threshold (default 30)')
    p_purge.add_argument('--days', type=int, default=30, help='Delete events older than this many days (default 30)')
    p_purge.set_defaults(func=cmd_purge)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == '__main__':
    sys.exit(main())