#!/usr/bin/env python3
"""Travel deals RSS fetcher.

Fetches RSS feeds from travel deal sources, filters to actual deals,
and updates the travel-deals.json collection.

Stdlib-only. No external dependencies.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

WORKSPACE = Path('/home/user/.openclaw/workspace')
COLLECTION_PATH = WORKSPACE / 'tracking/collections/travel-deals.json'
DEFAULT_TIMEOUT = 25
USER_AGENT = 'Director-TravelDeals/1.0 (+local stdlib fetcher)'

# RSS feed sources
SOURCES = [
    {'name': 'The Points Guy', 'url': 'https://www.thepointsguy.com/feed/'},
    {'name': 'Thrifty Traveler', 'url': 'https://thriftytraveler.com/feed/'},
    {'name': 'The Flight Deal', 'url': 'https://theflightdeal.com/feed/'},
]

# Email search sources (Gmail senders/keywords)
EMAIL_SENDERS = [
    'thepointsguy.com',
    'thriftytraveler.com',
    'scottscheapflights.com',
    'going.com',
    'airfarewatchdog.com',
    'flyertalk.com',
    'frequentmiler.com',
]

EMAIL_KEYWORDS = [
    'deal',
    'sale',
    'fare',
    'error fare',
    'mistake fare',
    'flash sale',
    'price drop',
    '$',
    'miles',
    'points',
    'award',
]

# Patterns that indicate a deal (not a guide/article)
DEAL_PATTERNS = [
    r'\bdeal\b',
    r'\bsale\b',
    r'\$\d+',
    r'\b\d+K\b',
    r'\bmiles\b',
    r'\bpoints\b',
    r'\bskymiles\b',
    r'\baward\b',
    r'\bflash\b',
    r'\berror fare\b',
    r'\bmistake fare\b',
    r'\bdiscount\b',
    r'\boff\b',
    r'\broundtrip\b',
    r'\bone-way\b',
    r'\b→\b',
    r'\bto\b.*\bfrom\b',
    r'\bunder\b.*\b\d+',
]

# Patterns that indicate a guide/article (should skip)
SKIP_PATTERNS = [
    r'\bhow to\b',
    r'\bguide\b',
    r'\btips\b',
    r'\bbest.*ways\b',
    r'\breview\b',
    r'\bexplained\b',
    r'\bwhat you need to know\b',
    r'\bbeginner\b',
    r'\bultimate guide\b',
    r'\bcomplete guide\b',
    r'\bwhy you should\b',
    r'\bshould you\b',
    r'\bis it worth\b',
]


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def strip_html(text: str) -> str:
    if not text:
        return ''
    clean = re.sub(r'<[^>]+>', '', text)
    clean = clean.replace('&nbsp;', ' ').replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>').replace('&quot;', '"').replace('&#39;', "'")
    clean = ' '.join(clean.split())
    return clean


def is_deal_title(title: str) -> bool:
    title_lower = title.lower()
    for pattern in SKIP_PATTERNS:
        if re.search(pattern, title_lower):
            return False
    for pattern in DEAL_PATTERNS:
        if re.search(pattern, title_lower):
            return True
    return False


def extract_price(text: str) -> str | None:
    matches = re.findall(r'\$[\d,]+(?:\.\d{2})?', text)
    return matches[0] if matches else None


def extract_route(title: str) -> str | None:
    # Non-greedy: capture everything up to the arrow/en-dash, then stop at . or $
    m = re.search(r'([A-Za-z].*?)\s*[-–—→]\s+(.*?)(?=\s*[.$])', title)
    if m:
        origin = m.group(1).strip().rstrip(',')
        dest = m.group(2).strip().rstrip(',')
        if len(origin) > 2 and len(dest) > 2 and origin != dest:
            return f'{origin} → {dest}'
    return None
    return None


def extract_destination(title: str, description: str) -> str | None:
    dest_keywords = ['Europe', 'Tokyo', 'Japan', 'Hawaii', 'Caribbean', 'Mexico', 'Asia', 'South America', 'Africa', 'Australia', 'New York', 'London', 'Paris', 'Los Angeles', 'San Francisco', 'Miami', 'Las Vegas']
    text = f"{title} {description}".lower()
    for keyword in dest_keywords:
        if keyword.lower() in text:
            return keyword
    return None


def calculate_rating(title: str, description: str, attributes: dict) -> float:
    rating = 4.0
    if attributes.get('price'):
        rating = max(rating, 4.5)
    if attributes.get('award_possible') and attributes.get('cash_vs_points') == 'points-focused':
        text = f"{title} {description}".lower()
        if 'under' in text and ('k' in text or '000' in text):
            rating = max(rating, 5.0)
        elif 'cheap' in text or 'steal' in text or 'incredible' in text:
            rating = max(rating, 4.8)
    return rating


def determine_deal_type(title: str, description: str, attributes: dict) -> str:
    text = f"{title} {description}".lower()
    if attributes.get('award_possible'):
        if 'cruise' in text:
            return 'award-cruise'
        if 'hotel' in text:
            return 'award-hotel'
        return 'award-travel'
    if 'cruise' in text:
        return 'cruise-deal'
    if 'hotel' in text:
        return 'hotel-deal'
    return 'flight-deal'


def determine_categories(deal_type: str, destination: str | None) -> list[str]:
    categories = ['travel']
    if 'award' in deal_type:
        categories.append('award-travel')
    if 'flight' in deal_type:
        categories.append('flights')
    if 'hotel' in deal_type:
        categories.append('hotels')
    if 'cruise' in deal_type:
        categories.append('cruise')
    if destination:
        dest_lower = destination.lower()
        if 'europe' in dest_lower:
            categories.append('europe')
        elif 'asia' in dest_lower or 'tokyo' in dest_lower or 'japan' in dest_lower:
            categories.append('asia')
        elif 'caribbean' in dest_lower:
            categories.append('caribbean')
        elif 'mexico' in dest_lower:
            categories.append('mexico')
        elif 'hawaii' in dest_lower:
            categories.append('hawaii')
    return categories


def parse_feed(xml_bytes: bytes, source_name: str) -> list[dict[str, Any]]:
    root = ET.fromstring(xml_bytes)
    tag = root.tag.lower()
    items: list[dict[str, Any]] = []

    if tag.endswith('rss') or tag.endswith('rdf'):
        channel = root.find('channel')
        nodes = channel.findall('item') if channel is not None else root.findall('.//item')
        for item in nodes:
            title = link = description = pub_date = ''
            for child in item:
                if child.tag == 'title' and child.text:
                    title = child.text.strip()
                elif child.tag == 'link' and child.text:
                    link = child.text.strip()
                elif child.tag in ('description', 'summary') and child.text:
                    description = child.text.strip()
                elif child.tag == 'pubDate' and child.text:
                    pub_date = child.text.strip()
            if title and link:
                items.append({'title': title, 'link': link, 'description': description, 'pub_date': pub_date})

    elif tag.endswith('feed'):
        nodes = root.findall('{*}entry') or root.findall('entry')
        for entry in nodes:
            title = link = description = pub_date = ''
            for child in entry:
                if child.tag.endswith('title') and child.text:
                    title = child.text.strip()
                elif child.tag.endswith('link'):
                    href = child.attrib.get('href')
                    if href:
                        link = href.strip()
                    elif child.text:
                        link = child.text.strip()
                elif child.tag.endswith('summary') or child.tag.endswith('content'):
                    if child.text:
                        description = child.text.strip()
                elif child.tag.endswith('updated') or child.tag.endswith('published'):
                    if child.text:
                        pub_date = child.text.strip()
            if title and link:
                items.append({'title': title, 'link': link, 'description': description, 'pub_date': pub_date})

    return items


def parse_date(pub_date: str) -> str:
    if not pub_date:
        return utc_now()
    try:
        parsed = parsedate_to_datetime(pub_date)
        return parsed.astimezone(dt.timezone.utc).replace(microsecond=0).isoformat()
    except Exception:
        pass
    try:
        parsed = dt.datetime.fromisoformat(pub_date.replace('Z', '+00:00'))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=dt.timezone.utc)
        return parsed.astimezone(dt.timezone.utc).replace(microsecond=0).isoformat()
    except Exception:
        pass
    return utc_now()


def fetch_url(url: str, timeout: int = DEFAULT_TIMEOUT) -> bytes:
    headers = {'User-Agent': USER_AGENT, 'Accept': 'application/rss+xml, application/atom+xml, application/xml, text/xml, */*'}
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def fetch_email_deals(args: argparse.Namespace) -> list[dict[str, Any]]:
    deals = []
    now = utc_now()
    sender_parts = [f'from:{sender}' for sender in EMAIL_SENDERS]
    search_query = f"({' OR '.join(sender_parts)})"

    if args.verbose:
        print(f"Searching Gmail: {search_query}")

    try:
        cmd = ['gog', 'gmail', 'messages', 'search', search_query, '--max', '50', '--json']
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

        if result.returncode != 0:
            if args.verbose:
                print(f"gog CLI error: {result.stderr}", file=sys.stderr)
            return deals

        messages = json.loads(result.stdout) if result.stdout.strip() else []
        if isinstance(messages, dict):
            messages = messages.get('messages', [])

        for msg in messages:
            if not isinstance(msg, dict):
                continue
            subject = msg.get('subject', '') or msg.get('title', '')
            snippet = msg.get('snippet', '') or msg.get('body', '')
            msg_id = msg.get('id', '') or msg.get('messageId', '')
            date = msg.get('date', '') or msg.get('internalDate', '')
            sender = msg.get('from', '')

            if not subject:
                continue

            text = f"{subject} {snippet}".lower()
            is_deal = any(kw.lower() in text for kw in EMAIL_KEYWORDS)
            if is_deal and any(skip.lower() in text for skip in SKIP_PATTERNS):
                is_deal = False

            if not is_deal:
                continue

            price = extract_price(f"{subject} {snippet}")
            route = extract_route(subject)
            destination = extract_destination(subject, snippet)
            award_possible = bool(re.search(r'\b(miles|points|skymiles|award|redeem)\b', text))

            source_name = 'Gmail'
            for sender_domain in EMAIL_SENDERS:
                if sender_domain in sender.lower():
                    source_name = sender_domain.split('.')[0].title()
                    break

            deal_item = {
                'title': subject,
                'summary': snippet[:120] if snippet else '',
                'category': 'email-deal',
                'categories': ['travel', 'email-sourced'],
                'source_name': source_name,
                'source_url': f"gmail://{msg_id}",
                'source_published_at': parse_date(date),
                'first_seen_at': now,
                'last_seen_at': now,
                'status': 'active',
                'rating': 4.0,
                'attributes': {
                    'deal_type': 'email-deal',
                    'destination': destination or 'varies',
                    'cash_vs_points': 'points-focused' if award_possible else 'cash-deal',
                    'award_possible': award_possible,
                    'source': 'gmail',
                },
            }

            if price:
                deal_item['attributes']['price'] = price
                deal_item['rating'] = max(deal_item['rating'], 4.5)
            if route:
                deal_item['attributes']['route'] = route

            deals.append(deal_item)

        if args.verbose:
            print(f"Found {len(deals)} deal emails")

    except subprocess.TimeoutExpired:
        print("Gmail search timed out", file=sys.stderr)
    except FileNotFoundError:
        print("gog CLI not found - skipping email search", file=sys.stderr)
    except json.JSONDecodeError as exc:
        if args.verbose:
            print(f"JSON parse error: {exc}", file=sys.stderr)
    except Exception as exc:
        if args.verbose:
            print(f"Email fetch error: {exc}", file=sys.stderr)

    return deals


def process_item(item: dict, source_name: str) -> dict[str, Any] | None:
    title = item.get('title', '')
    link = item.get('link', '')
    description = strip_html(item.get('description', ''))
    pub_date = item.get('pub_date', '')

    if not is_deal_title(title):
        return None

    price = extract_price(f"{title} {description}")
    route = extract_route(title)
    destination = extract_destination(title, description)

    text_lower = f"{title} {description}".lower()
    award_possible = bool(re.search(r'\b(miles|points|skymiles|award|redeem)\b', text_lower))

    if award_possible:
        cash_vs_points = 'points-focused'
    elif price:
        cash_vs_points = 'cash-deal'
    else:
        cash_vs_points = 'mixed'

    attributes: dict[str, Any] = {
        'deal_type': '',
        'destination': destination or 'varies',
        'cash_vs_points': cash_vs_points,
        'award_possible': award_possible,
    }

    if price:
        attributes['price'] = price
    if route:
        attributes['route'] = route

    deal_type = determine_deal_type(title, description, attributes)
    attributes['deal_type'] = deal_type

    now = utc_now()
    source_published = parse_date(pub_date)

    return {
        'title': title,
        'summary': description[:120] if description else '',
        'category': deal_type,
        'categories': determine_categories(deal_type, destination),
        'source_name': source_name,
        'source_url': link,
        'source_published_at': source_published,
        'first_seen_at': now,
        'last_seen_at': now,
        'status': 'active',
        'rating': calculate_rating(title, description, attributes),
        'attributes': attributes,
    }


def load_collection(path: Path) -> dict[str, Any]:
    if path.exists():
        with path.open('r', encoding='utf-8') as f:
            return json.load(f)
    now = utc_now()
    return {
        'version': 1,
        'collection': {
            'name': 'travel-deals',
            'title': 'Travel Deals',
            'description': 'Tracked travel deals from RSS feeds',
            'default_category': 'travel',
            'created_at': now,
            'updated_at': now,
        },
        'items': [],
    }


def save_collection(path: Path, collection: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = str(path) + '.tmp'
    try:
        with open(temp, 'w', encoding='utf-8') as f:
            json.dump(collection, f, indent=2, ensure_ascii=False)
            f.write('\n')
        # Verify read-back
        with open(temp, encoding='utf-8') as f:
            verify = json.load(f)
        if verify != collection:
            raise RuntimeError(f'Write verification failed for {path}: data mismatch after write')
        os.replace(temp, path)
    except Exception as exc:
        import datetime as dt
        ERROR_LOG = Path('/home/user/.openclaw/workspace/tracking/state/cron-write-errors.json')
        ERROR_LOG.parent.mkdir(parents=True, exist_ok=True)
        errors = []
        if ERROR_LOG.exists():
            try:
                errors = json.loads(ERROR_LOG.read_text()).get('errors', [])
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
        raise RuntimeError(f'Failed to save {path}: {exc}') from exc


def dedupe_items(new_items: list[dict], existing_items: list[dict]) -> list[dict]:
    existing_urls = {item.get('source_url') for item in existing_items if item.get('source_url')}
    return [item for item in new_items if item.get('source_url') not in existing_urls]


def cmd_fetch(args: argparse.Namespace) -> int:
    collection = load_collection(COLLECTION_PATH)
    existing_items = collection.get('items', [])

    all_new_items: list[dict] = []
    sources_checked = 0
    total_items_found = 0

    for source in SOURCES:
        source_name = source['name']
        source_url = source['url']

        try:
            xml_bytes = fetch_url(source_url, timeout=args.timeout)
            items = parse_feed(xml_bytes, source_name)
            total_items_found += len(items)

            for item in items:
                deal = process_item(item, source_name)
                if deal:
                    all_new_items.append(deal)

            sources_checked += 1
            if args.verbose:
                print(f"Checked {source_name}: {len(items)} items, {sum(1 for d in all_new_items if d['source_name'] == source_name)} deals")

        except urllib.error.HTTPError as exc:
            print(f"HTTP error fetching {source_name}: {exc.code}", file=sys.stderr)
        except Exception as exc:
            print(f"Error fetching {source_name}: {exc}", file=sys.stderr)

    if args.include_email:
        if args.verbose:
            print("\nFetching email deals...")
        email_deals = fetch_email_deals(args)
        all_new_items.extend(email_deals)

    new_items = dedupe_items(all_new_items, existing_items)
    collection['items'].extend(new_items)
    collection['collection']['updated_at'] = utc_now()
    save_collection(COLLECTION_PATH, collection)

    result = {
        'sources_checked': sources_checked,
        'total_items_parsed': total_items_found,
        'deals_found': len(all_new_items),
        'new_items_added': len(new_items),
        'existing_items': len(existing_items),
        'total_items': len(collection['items']),
    }

    print(json.dumps(result, indent=2))

    if args.verbose and new_items:
        print(f"\nNew deals added:")
        for item in new_items:
            print(f"  - {item['title']} ({item['source_name']})")

    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Travel deals RSS fetcher')
    parser.add_argument('--timeout', type=int, default=DEFAULT_TIMEOUT, help='HTTP timeout in seconds')
    parser.add_argument('--verbose', '-v', action='store_true', help='Print detailed output')
    parser.add_argument('--include-email', action='store_true', help='Also fetch deals from Gmail')

    subparsers = parser.add_subparsers(dest='command')
    fetch_parser = subparsers.add_parser('fetch', help='Fetch RSS feeds and update collection')
    fetch_parser.set_defaults(func=cmd_fetch)
    parser.add_argument('--fetch', action='store_true', help='Fetch RSS feeds (shorthand for fetch command)')

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.fetch and not hasattr(args, 'func'):
        args.func = cmd_fetch

    if hasattr(args, 'func'):
        return args.func(args)

    parser.print_help()
    return 1


if __name__ == '__main__':
    sys.exit(main())
