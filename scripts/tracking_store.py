#!/usr/bin/env python3
import argparse
import errno
import fcntl
import hashlib
import json
import logging
import os
import sys
import time
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

WORKSPACE = Path('/home/user/.openclaw/workspace')
TRACKING_DIR = WORKSPACE / 'tracking'
COLLECTIONS_DIR = TRACKING_DIR / 'collections'
INDEX_PATH = TRACKING_DIR / '_index.json'

# Cron-safe file utilities (fcntl locking + read-back verification + error log)
sys.path.insert(0, str(WORKSPACE / 'scripts'))
import cron_file  # noqa: E402

_log = logging.getLogger('tracking_store')
_log.setLevel(logging.INFO)
if not _log.handlers:
    _log.addHandler(logging.StreamHandler(sys.stderr))


DEFAULT_COLLECTION_TEMPLATE = {
    'version': 1,
    'collection': {
        'name': '',
        'title': '',
        'description': '',
        'default_category': '',
        'created_at': '',
        'updated_at': '',
    },
    'items': [],
}


EXAMPLE_RECORD = {
    'record_id': 'market-fed-watch-2026-03-24',
    'source_key': 'https://www.federalreserve.gov/newsevents/pressreleases/monetary20260324a.htm',
    'external_id': 'fed-press-release-2026-03-24',
    'title': 'Fed holds rates steady and signals data dependence',
    'summary': 'Useful for a daily market brief because it reframes near-term rate expectations.',
    'collection': 'market',
    'category': 'macro',
    'categories': ['market', 'macro', 'rates'],
    'source_name': 'Federal Reserve',
    'source_url': 'https://www.federalreserve.gov/newsevents/pressreleases/monetary20260324a.htm',
    'source_published_at': '2026-03-24T14:00:00Z',
    'source_domain': 'federalreserve.gov',
    'first_seen_at': '2026-03-24T18:00:00Z',
    'last_seen_at': '2026-03-24T18:00:00Z',
    'last_sent_at': None,
    'sent_count': 0,
    'seen_count': 1,
    'status': 'new',
    'thesis_status': 'watch',
    'rating': 4.5,
    'notes': ['Mention source date in the digest so recency is obvious.'],
    'follow_up': {
        'status': 'pending',
        'owner': 'director',
        'due_at': '2026-03-25T15:00:00Z',
        'notes': 'Check futures reaction before tomorrow morning brief.',
    },
    'tags': ['daily-brief', 'high-signal'],
    'attributes': {
        'tickers': ['SPY', 'TLT'],
        'importance': 'high',
    },
    'history': [
        {
            'at': '2026-03-24T18:00:00Z',
            'type': 'created',
            'note': 'Initial capture from recurring market scan.',
        }
    ],
}


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


# ---------------------------------------------------------------------------
# File I/O — all routed through cron_file for locking + verification
# ---------------------------------------------------------------------------

def load_json(path: Path, default: Any) -> Any:
    """Load JSON, returning default on error (error is logged by cron_file)."""
    return cron_file.load_json_safe(path, default)


def save_json(path: Path, data: Any) -> bool:
    """Write JSON with fcntl locking + read-back verification. Returns True on success.

    On failure, logs to cron-write-errors.json and returns False.
    """
    ok = cron_file.safe_write_json(path, data)
    if not ok:
        cron_file.log_error('save_json', str(path), 'safe_write_json returned False')
    return ok


# ---------------------------------------------------------------------------
# Locked read-modify-write helpers
# ---------------------------------------------------------------------------

def locked_update(path: Path, update_fn, *, lock_dir: Optional[Path] = None) -> bool:
    """Read file, apply update_fn, write back — all under fcntl lock.

    update_fn: callable(current_data) -> new_data
    Returns True on success, False on any failure (logged to cron-write-errors.json).
    """
    lock_dir = lock_dir or (WORKSPACE / 'tracking' / '.locks')
    lock_dir.mkdir(parents=True, exist_ok=True)
    lock_path = lock_dir / f'{path.name}.lock'

    try:
        lock_fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR)
    except OSError as exc:
        cron_file.log_error('locked_update_open', str(lock_path), str(exc))
        return False

    acquired = False
    for _ in range(50):  # up to 5s
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            acquired = True
            break
        except OSError as exc:
            if exc.errno not in (errno.EWOULDBLOCK, errno.EAGAIN):
                try:
                    os.close(lock_fd)
                except Exception:
                    pass
                cron_file.log_error('locked_update_acquire', str(lock_path), str(exc))
                return False
        time.sleep(0.1)

    if not acquired:
        try:
            os.close(lock_fd)
        except Exception:
            pass
        cron_file.log_error('locked_update_timeout', str(lock_path), 'could not acquire lock within 5s')
        return False

    try:
        # Read current state
        data = cron_file.load_json_safe(path, None)
        if data is None:
            cron_file.log_error('locked_update_read', str(path), 'file does not exist')
            return False

        # Apply modification
        try:
            new_data = update_fn(data)
        except Exception as exc:
            cron_file.log_error('locked_update_fn', str(path), f'update_fn raised: {exc}')
            return False

        # Inline atomic write: temp file + rename (lock already held, no re-acquire needed)
        tmp = path.parent / f'.{path.name}.tmp'
        try:
            tmp.write_text(json.dumps(new_data, indent=2, sort_keys=False) + '\n')
        except Exception as exc:
            cron_file.log_error('locked_update_write', str(path), f'temp write failed: {exc}')
            try:
                tmp.unlink()
            except Exception:
                pass
            return False

        try:
            os.replace(str(tmp), str(path))
        except OSError as exc:
            cron_file.log_error('locked_update_write', str(path), f'rename failed: {exc}')
            try:
                tmp.unlink()
            except Exception:
                pass
            return False

        # Read back to verify
        try:
            verified = json.loads(path.read_text())
            if verified is None:
                raise ValueError('read back None')
        except Exception as exc:
            cron_file.log_error('locked_update_verify', str(path), f'read-back failed: {exc}')
            return False

        return True

    finally:
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            os.close(lock_fd)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------

def ensure_layout() -> None:
    TRACKING_DIR.mkdir(parents=True, exist_ok=True)
    COLLECTIONS_DIR.mkdir(parents=True, exist_ok=True)
    if not INDEX_PATH.exists():
        ok = cron_file.write_json_logged(INDEX_PATH, {'version': 1, 'collections': {}, 'updated_at': now_iso()})
        if not ok:
            _log.error('Failed to write initial index — tracking may not persist correctly')


def slug(text: str) -> str:
    cleaned = ''.join(ch.lower() if ch.isalnum() else '-' for ch in text.strip())
    while '--' in cleaned:
        cleaned = cleaned.replace('--', '-')
    return cleaned.strip('-') or 'untitled'


def collection_path(name: str) -> Path:
    return COLLECTIONS_DIR / f'{slug(name)}.json'


# ---------------------------------------------------------------------------
# Index operations
# ---------------------------------------------------------------------------

def load_index() -> Dict[str, Any]:
    ensure_layout()
    return load_json(INDEX_PATH, {'version': 1, 'collections': {}, 'updated_at': now_iso()})


def save_index(index: Dict[str, Any]) -> bool:
    index['updated_at'] = now_iso()
    return save_json(INDEX_PATH, index)


# ---------------------------------------------------------------------------
# Collection operations
# ---------------------------------------------------------------------------

def load_collection(name: str) -> Dict[str, Any]:
    path = collection_path(name)
    if not path.exists():
        raise SystemExit(f'Collection not found: {name}')
    return load_json(path, deepcopy(DEFAULT_COLLECTION_TEMPLATE))


def save_collection(name: str, data: Dict[str, Any]) -> bool:
    data['collection']['updated_at'] = now_iso()
    col_path = collection_path(name)
    if not save_json(col_path, data):
        cron_file.log_error('save_collection', str(col_path), 'save_json returned False')
        return False

    # Update index — best effort; non-fatal if this fails
    index = load_index()
    index['collections'][slug(name)] = {
        'path': str(col_path.relative_to(WORKSPACE)),
        'title': data['collection'].get('title') or name,
        'default_category': data['collection'].get('default_category', ''),
        'updated_at': data['collection']['updated_at'],
        'item_count': len(data.get('items', [])),
    }
    if not save_index(index):
        cron_file.log_error('save_collection', str(INDEX_PATH), 'index update failed (collection write succeeded)')

    return True


def create_collection(name: str, title: str, description: str, default_category: str) -> Dict[str, Any]:
    ensure_layout()
    path = collection_path(name)
    if path.exists():
        return load_collection(name)
    data = deepcopy(DEFAULT_COLLECTION_TEMPLATE)
    data['collection'].update({
        'name': slug(name),
        'title': title or name,
        'description': description,
        'default_category': default_category,
        'created_at': now_iso(),
        'updated_at': now_iso(),
    })
    save_collection(name, data)
    return data


# ---------------------------------------------------------------------------
# Record helpers
# ---------------------------------------------------------------------------

def infer_source_key(record: Dict[str, Any]) -> str:
    for key in ('source_key', 'external_id', 'source_url', 'title'):
        value = record.get(key)
        if value:
            return str(value)
    payload = json.dumps(record, sort_keys=True)
    return hashlib.sha1(payload.encode()).hexdigest()


def infer_record_id(collection_name: str, record: Dict[str, Any]) -> str:
    if record.get('record_id'):
        return str(record['record_id'])
    source_key = infer_source_key(record)
    digest = hashlib.sha1(source_key.encode()).hexdigest()[:12]
    return f'{slug(collection_name)}-{digest}'


def event(event_type: str, note: str = '', extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    payload = {'at': now_iso(), 'type': event_type}
    if note:
        payload['note'] = note
    if extra:
        payload.update(extra)
    return payload


REQUIRED_DEFAULTS = {
    'summary': '',
    'category': '',
    'categories': [],
    'source_name': '',
    'source_url': '',
    'source_published_at': None,
    'source_domain': '',
    'first_seen_at': None,
    'last_seen_at': None,
    'last_sent_at': None,
    'sent_count': 0,
    'seen_count': 0,
    'status': 'new',
    'thesis_status': 'untriaged',
    'rating': None,
    'notes': [],
    'follow_up': {'status': 'none', 'owner': '', 'due_at': None, 'notes': ''},
    'tags': [],
    'attributes': {},
    'history': [],
}


def normalize_record(collection_name: str, record: Dict[str, Any], previous: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    base = deepcopy(previous) if previous else {}
    for key, value in REQUIRED_DEFAULTS.items():
        if key not in base:
            base[key] = deepcopy(value)
    base.update(record)
    base['collection'] = slug(collection_name)
    base['source_key'] = infer_source_key(base)
    base['record_id'] = infer_record_id(collection_name, base)
    ts = now_iso()
    if not previous:
        base['first_seen_at'] = base.get('first_seen_at') or ts
        base['history'].append(event('created', 'Record created'))
        base['seen_count'] = int(base.get('seen_count') or 0) + 1
    else:
        base['seen_count'] = int(base.get('seen_count') or 0) + 1
        base['history'].append(event('updated', 'Record updated'))
    base['last_seen_at'] = ts
    return base


# ---------------------------------------------------------------------------
# CRUD — all use locked cycle to prevent concurrent clobbering
# ---------------------------------------------------------------------------

def upsert_record(collection_name: str, record: Dict[str, Any]) -> Dict[str, Any]:
    """Atomic upsert: find existing by source_key/record_id or create new."""
    col_path = collection_path(collection_name)

    def do_upsert(data: Dict[str, Any]) -> Dict[str, Any]:
        items: List[Dict[str, Any]] = data.setdefault('items', [])
        source_key = infer_source_key(record)
        record_id = record.get('record_id')
        for idx, existing in enumerate(items):
            if existing.get('source_key') == source_key or (record_id and existing.get('record_id') == record_id):
                updated = normalize_record(collection_name, record, previous=existing)
                items[idx] = updated
                return data
        created = normalize_record(collection_name, record)
        items.append(created)
        return data

    ok = locked_update(col_path, do_upsert)
    if not ok:
        cron_file.log_error('upsert_record', str(col_path), 'locked_update returned False — record may not be saved')
        raise SystemExit(f'Failed to save record to collection: {collection_name}')

    # Reload and return the full record so callers get the persisted state
    reloaded = load_collection(collection_name)
    rid = infer_record_id(collection_name, record)
    for item in reloaded.get('items', []):
        if item.get('record_id') == rid:
            return item
    # Fallback: return the record_id only if we could not find the saved item
    return {'record_id': rid, 'status': 'upserted'}


def get_record(collection_name: str, record_id: str) -> Dict[str, Any]:
    data = load_collection(collection_name)
    for item in data.get('items', []):
        if item.get('record_id') == record_id:
            return item
    raise SystemExit(f'Record not found: {record_id}')


def _atomic_field_update(collection_name: str, record_id: str, patch_fn) -> Dict[str, Any]:
    """Apply patch_fn(item) -> bool to matching item under lock."""
    col_path = collection_path(collection_name)

    def do_patch(data: Dict[str, Any]) -> Dict[str, Any]:
        for idx, item in enumerate(data.get('items', [])):
            if item.get('record_id') == record_id:
                if patch_fn(item):
                    return data
                else:
                    raise ValueError('patch_fn returned False')
        raise KeyError(record_id)

    ok = locked_update(col_path, do_patch)
    if not ok:
        cron_file.log_error('_atomic_field_update', str(col_path), 'locked_update returned False')
        raise SystemExit(f'Failed to update record: {collection_name}/{record_id}')
    return get_record(collection_name, record_id)


def mark_sent(collection_name: str, record_id: str, digest_id: str, note: str = '') -> Dict[str, Any]:
    def patch(item):
        item['status'] = 'sent'
        item['last_sent_at'] = now_iso()
        item['sent_count'] = int(item.get('sent_count') or 0) + 1
        item.setdefault('history', []).append(event('sent', note or 'Included in digest', {'digest_id': digest_id}))
        return True
    return _atomic_field_update(collection_name, record_id, patch)


def add_note(collection_name: str, record_id: str, note: str) -> Dict[str, Any]:
    def patch(item):
        item.setdefault('notes', []).append(note)
        item.setdefault('history', []).append(event('note_added', note))
        return True
    return _atomic_field_update(collection_name, record_id, patch)


def update_record(
    collection_name: str,
    record_id: str,
    *,
    status: Optional[str] = None,
    thesis_status: Optional[str] = None,
    rating: Optional[float] = None,
    summary: Optional[str] = None,
    source_url: Optional[str] = None,
    source_published_at: Optional[str] = None,
    add_tags: Optional[List[str]] = None,
    attributes: Optional[Dict[str, Any]] = None,
    follow_up_patch: Optional[Dict[str, Any]] = None,
    notes: Optional[List[str]] = None,
) -> Dict[str, Any]:
    def patch(item):
        changes: List[str] = []
        if status is not None:
            item['status'] = status
            changes.append(f'status={status}')
        if thesis_status is not None:
            item['thesis_status'] = thesis_status
            changes.append(f'thesis_status={thesis_status}')
        if rating is not None:
            item['rating'] = rating
            changes.append(f'rating={rating}')
        if summary is not None:
            item['summary'] = summary
            changes.append('summary')
        if source_url is not None:
            item['source_url'] = source_url
            changes.append('source_url')
        if source_published_at is not None:
            item['source_published_at'] = source_published_at
            changes.append('source_published_at')
        if add_tags:
            existing_tags = item.setdefault('tags', [])
            for tag in add_tags:
                if tag not in existing_tags:
                    existing_tags.append(tag)
            changes.append(f'tags+={len(add_tags)}')
        if attributes:
            item.setdefault('attributes', {}).update(attributes)
            changes.append(f'attributes+={len(attributes)}')
        if follow_up_patch:
            item.setdefault('follow_up', {}).update({k: v for k, v in follow_up_patch.items() if v is not None})
            changes.append('follow_up')
        if notes:
            item.setdefault('notes', []).extend(notes)
            changes.append(f'notes+={len(notes)}')
        item['last_seen_at'] = now_iso()
        if changes:
            item.setdefault('history', []).append(event('updated_fields', ', '.join(changes)))
        return True
    return _atomic_field_update(collection_name, record_id, patch)


def list_records(collection_name: str, status: str = '', follow_up_only: bool = False, limit: int = 20) -> List[Dict[str, Any]]:
    data = load_collection(collection_name)
    items = data.get('items', [])
    if status:
        items = [item for item in items if item.get('status') == status]
    if follow_up_only:
        items = [item for item in items if (item.get('follow_up') or {}).get('status') not in ('none', 'done', '')]
    items = sorted(items, key=lambda item: item.get('last_seen_at') or '', reverse=True)
    return items[:limit]


def queue_records(
    collection_name: str,
    *,
    min_rating: Optional[float] = None,
    include_sent: bool = False,
    include_archived: bool = False,
    follow_up_only: bool = False,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    data = load_collection(collection_name)
    items = data.get('items', [])
    if not include_sent:
        items = [item for item in items if item.get('status') != 'sent']
    if not include_archived:
        items = [item for item in items if item.get('status') != 'archived']
    if min_rating is not None:
        items = [item for item in items if item.get('rating') is not None and float(item.get('rating')) >= min_rating]
    if follow_up_only:
        items = [item for item in items if (item.get('follow_up') or {}).get('status') not in ('none', 'done', '')]
    items = sorted(
        items,
        key=lambda item: (
            item.get('status') == 'new',
            item.get('follow_up', {}).get('status') not in ('none', 'done', ''),
            item.get('rating') if item.get('rating') is not None else -1,
            item.get('last_seen_at') or '',
        ),
        reverse=True,
    )
    return items[:limit]


def stats() -> Dict[str, Any]:
    index = load_index()
    collections = []
    for name in sorted(index.get('collections', {})):
        data = load_collection(name)
        items = data.get('items', [])
        # Handle both standard 'collection' key and flat-schema files (decisions, reprice-watchdog, etc.)
        col = data.get('collection') or {}
        collections.append({
            'name': name,
            'title': col.get('title') or data.get('title') or name,
            'items': len(items),
            'sent': sum(1 for item in items if item.get('sent_count')),
            'pending_follow_up': sum(1 for item in items if isinstance(item.get('follow_up'), dict) and (item.get('follow_up') or {}).get('status') not in ('none', 'done', '')),
            'updated_at': col.get('updated_at') or data.get('updated_at') or '',
        })
    return {'collections': collections, 'updated_at': now_iso()}


def parse_record_json(value: str) -> Dict[str, Any]:
    try:
        payload = json.loads(value)
    except json.JSONDecodeError as exc:
        raise SystemExit(f'Invalid JSON: {exc}')
    if not isinstance(payload, dict):
        raise SystemExit('Record JSON must be an object')
    return payload


def parse_key_value_pairs(pairs: List[str]) -> Dict[str, Any]:
    payload: Dict[str, Any] = {}
    for pair in pairs:
        if '=' not in pair:
            raise SystemExit(f'Expected key=value, got: {pair}')
        key, raw_value = pair.split('=', 1)
        try:
            value = json.loads(raw_value)
        except json.JSONDecodeError:
            value = raw_value
        payload[key] = value
    return payload


def print_json(data: Any) -> None:
    json.dump(data, sys.stdout, indent=2)
    sys.stdout.write('\n')


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_init(args: argparse.Namespace) -> None:
    data = create_collection(args.name, args.title, args.description, args.default_category)
    print_json(data)


def cmd_upsert(args: argparse.Namespace) -> None:
    record = parse_record_json(args.json)
    updated_id = upsert_record(args.name, record)
    # Print the record_id as confirmation
    print_json({'record_id': updated_id, 'status': 'upserted'})


def cmd_mark_sent(args: argparse.Namespace) -> None:
    updated = mark_sent(args.name, args.record_id, args.digest_id, args.note)
    print_json(updated)


def cmd_add_note(args: argparse.Namespace) -> None:
    updated = add_note(args.name, args.record_id, args.note)
    print_json(updated)


def cmd_update(args: argparse.Namespace) -> None:
    follow_up_patch = {
        'status': args.follow_up_status,
        'owner': args.follow_up_owner,
        'due_at': args.follow_up_due_at,
        'notes': args.follow_up_notes,
    }
    if not any(value is not None for value in follow_up_patch.values()):
        follow_up_patch = None
    updated = update_record(
        args.name,
        args.record_id,
        status=args.status,
        thesis_status=args.thesis_status,
        rating=args.rating,
        summary=args.summary,
        source_url=args.source_url,
        source_published_at=args.source_published_at,
        add_tags=args.add_tag or [],
        attributes=parse_key_value_pairs(args.set_attribute or []),
        follow_up_patch=follow_up_patch,
        notes=args.note or [],
    )
    print_json(updated)


def cmd_list(args: argparse.Namespace) -> None:
    print_json(list_records(args.name, args.status, args.follow_up_only, args.limit))


def cmd_queue(args: argparse.Namespace) -> None:
    print_json(
        queue_records(
            args.name,
            min_rating=args.min_rating,
            include_sent=args.include_sent,
            include_archived=args.include_archived,
            follow_up_only=args.follow_up_only,
            limit=args.limit,
        )
    )


def cmd_stats(args: argparse.Namespace) -> None:
    print_json(stats())


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Persistent tracking store for recurring digests and research jobs.')
    sub = parser.add_subparsers(dest='command', required=True)

    init_parser = sub.add_parser('init-collection', help='Create a collection file if it does not exist')
    init_parser.add_argument('name')
    init_parser.add_argument('--title', default='')
    init_parser.add_argument('--description', default='')
    init_parser.add_argument('--default-category', default='')
    init_parser.set_defaults(func=cmd_init)

    upsert_parser = sub.add_parser('upsert', help='Create or update a record from a JSON payload')
    upsert_parser.add_argument('name')
    upsert_parser.add_argument('--json', required=True, help='Record JSON object')
    upsert_parser.set_defaults(func=cmd_upsert)

    sent_parser = sub.add_parser('mark-sent', help='Mark a record as included in a digest or outbound message')
    sent_parser.add_argument('name')
    sent_parser.add_argument('record_id')
    sent_parser.add_argument('--digest-id', required=True)
    sent_parser.add_argument('--note', default='')
    sent_parser.set_defaults(func=cmd_mark_sent)

    note_parser = sub.add_parser('add-note', help='Append a note to an existing record')
    note_parser.add_argument('name')
    note_parser.add_argument('record_id')
    note_parser.add_argument('note')
    note_parser.set_defaults(func=cmd_add_note)

    update_parser = sub.add_parser('update', help='Patch an existing record without re-sending the full JSON payload')
    update_parser.add_argument('name')
    update_parser.add_argument('record_id')
    update_parser.add_argument('--status')
    update_parser.add_argument('--thesis-status')
    update_parser.add_argument('--rating', type=float)
    update_parser.add_argument('--summary')
    update_parser.add_argument('--source-url')
    update_parser.add_argument('--source-published-at')
    update_parser.add_argument('--follow-up-status')
    update_parser.add_argument('--follow-up-owner')
    update_parser.add_argument('--follow-up-due-at')
    update_parser.add_argument('--follow-up-notes')
    update_parser.add_argument('--add-tag', action='append')
    update_parser.add_argument('--set-attribute', action='append', help='key=value; JSON values allowed')
    update_parser.add_argument('--note', action='append', help='Append a note while updating')
    update_parser.set_defaults(func=cmd_update)

    list_parser = sub.add_parser('list', help='List records in a collection')
    list_parser.add_argument('name')
    list_parser.add_argument('--status', default='')
    list_parser.add_argument('--follow-up-only', action='store_true')
    list_parser.add_argument('--limit', type=int, default=20)
    list_parser.set_defaults(func=cmd_list)

    queue_parser = sub.add_parser('queue', help='Show likely digest candidates: unsent, non-archived, and optionally filtered')
    queue_parser.add_argument('name')
    queue_parser.add_argument('--min-rating', type=float)
    queue_parser.add_argument('--include-sent', action='store_true')
    queue_parser.add_argument('--include-archived', action='store_true')
    queue_parser.add_argument('--follow-up-only', action='store_true')
    queue_parser.add_argument('--limit', type=int, default=20)
    queue_parser.set_defaults(func=cmd_queue)

    stats_parser = sub.add_parser('stats', help='Summarize collections')
    stats_parser.set_defaults(func=cmd_stats)

    return parser


if __name__ == '__main__':
    ensure_layout()
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)