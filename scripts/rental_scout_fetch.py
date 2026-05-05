#!/usr/bin/env python3
"""
Long-term rental scout - fetches listings from multiple markets.
Uses Playwright for Cloudflare-protected sites.
"""

import json
import os
import sys
import re
import subprocess
import traceback
from datetime import datetime, timezone

TRACKING_FILE = "/home/user/.openclaw/workspace/tracking/state/rental-scout-latest.json"
COLLECTION_FILE = "/home/user/.openclaw/workspace/tracking/collections/long-term-rental-scouting.json"
OUTPUT_HTML = f"/home/user/.openclaw/workspace/tmp/daily-long-term-rental-scout-{datetime.now().strftime('%Y-%m-%d')}.html"

# ── helpers ──────────────────────────────────────────────────────────────────

def sqm_to_sqft(sqm):
    return round(float(sqm) * 10.764)

def usd_format(amount):
    return f"${amount:,.0f}"

def rating(amount_str):
    """Convert string like '1500 USD' or '€1,200' to USD numeric."""
    s = amount_str.replace(',', '').strip()
    eur_match = re.search(r'€[\d.]+', s)
    vnd_match = re.search(r'([\d.]+)\s*(?:VND|vnd|đ)', s, re.I)
    myr_match = re.search(r'([\d.]+)\s*(?:MYR|myr|RM)', s, re.I)
    if eur_match:
        return float(re.sub(r'[^\d.]', '', eur_match.group())) * 1.10  # rough EUR->USD
    if vnd_match:
        return float(re.sub(r'[^\d.]', '', vnd_match.group())) / 25000
    if myr_match:
        return float(re.sub(r'[^\d.]', '', myr_match.group())) / 4.5
    nums = re.findall(r'[\d.]+', s)
    return float(nums[0]) if nums else None

def parse_size(text):
    """Extract sqm from text like '120 m²' or '120 sqm'."""
    m = re.search(r'([\d.]+)\s*(?:m²|sqm|sqm|m2)', text, re.I)
    return float(m.group(1)) if m else None

# ── fetcher base ─────────────────────────────────────────────────────────────

class Fetcher:
    def __init__(self, name):
        self.name = name

    def fetch(self):
        raise NotImplementedError

# ── KL / Malaysia ─────────────────────────────────────────────────────────────

class PropertyGuruFetcher(Fetcher):
    """PropertyGuru Malaysia – long-term rent, 2+ bedrooms."""

    BASE = "https://www.propertyguru.com.my/property-search/for-rent?listing_type=rent"

    def fetch(self):
        results = []
        cities = [
            ("Kuala Lumpur", "kuala-lumpur"),
            ("Petaling Jaya", "petaling-jaya"),
        ]
        for label, slug in cities:
            url = f"https://www.propertyguru.com.my/property-search/for-rent?city={slug}&beds_min=2&sort=newest"
            try:
                results += self._fetch_city(label, url)
            except Exception as e:
                print(f"  [PG] {label} error: {e}")
        return results

    def _fetch_city(self, city_label, url):
        import urllib.request
        listings = []
        try:
            req = urllib.request.Request(url, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120',
                'Accept-Language': 'en-US,en;q=0.9',
            })
            with urllib.request.urlopen(req, timeout=20) as resp:
                html = resp.read().decode('utf-8', errors='replace')
            # Parse title + price + size from search results
            for block in re.findall(
                r'<div class="listing-card[^"]*">(.*?)</div>\s*</div>',
                html, re.DOTALL
            ):
                price_m = re.search(r'\$?([\d,]+)\s*(?:USD|\$|MYR|RM)', block)
                title_m = re.search(r'class="listing-title"[^>]*>(.*?)</h3>', block)
                size_m = re.search(r'([\d,]+)\s*(?:sqft|sf|psf)', block, re.I)
                beds_m = re.search(r'(\d+)\s*(?:bedroom|bed|br)', block, re.I)
                link_m = re.search(r'href="(/listing/[^"]+)"', block)
                if price_m and title_m:
                    price_val = float(price_m.group(1).replace(',',''))
                    # Convert MYR to USD
                    price_usd = price_val / 4.5 if 'MYR' in block or 'RM' in block else price_val
                    size_sqft = float(size_m.group(1).replace(',','')) if size_m else None
                    results.append({
                        'city': city_label,
                        'price_usd': price_usd,
                        'price_display': f"${price_usd:,.0f}/mo",
                        'bedrooms': int(beds_m.group(1)) if beds_m else 2,
                        'size_sqft': size_sqft,
                        'title': re.sub('<[^>]+>', '', title_m.group(1)).strip(),
                        'link': f"https://www.propertyguru.com.my{link_m.group(1)}" if link_m else '',
                        'source': 'PropertyGuru',
                    })
        except Exception as e:
            print(f"  [PG] error: {e}")
        return listings[:8]

# ── Albania ───────────────────────────────────────────────────────────────────

class ListAlFetcher(Fetcher):
    """List.al – Albania's main property portal."""

    def fetch(self):
        results = []
        markets = [
            ("Tirana", "tirane"),
            ("Sarandë", "sarande"),
        ]
        for label, slug in markets:
            url = f"https://www.list.al/immobiliare/affitto/?citta={slug}&tipo=appartamento&locali-min=2"
            try:
                listings = self._fetch_al(url, label)
                results += listings
            except Exception as e:
                print(f"  [List.al] {label} error: {e}")
        return results

    def _fetch_al(self, url, label):
        import urllib.request
        out = []
        try:
            req = urllib.request.Request(url, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120',
                'Accept-Language': 'en-US,en;q=0.9',
            })
            with urllib.request.urlopen(req, timeout=20) as resp:
                html = resp.read().decode('utf-8', errors='replace')
            for block in re.findall(r'<div class="listing-item[^"]*">(.*?)</div>\s*</div>', html, re.DOTALL):
                price_m = re.search(r'([\d,\.]+)\s*(?:USD|\$|€|EUR|ALL)', block)
                title_m = re.search(r'class="title"[^>]*>(.*?)</', block)
                size_m = parse_size(block)
                beds_m = re.search(r'(\d+)\s*(?:bedroom|bed|br|dhoma)', block, re.I)
                link_m = re.search(r'href="(/listing/[^"]+)"', block)
                if price_m:
                    price_usd = rating(price_m.group(0))
                    size_sqft = sqm_to_sqft(size_m) if size_m else None
                    out.append({
                        'city': label,
                        'price_usd': price_usd,
                        'price_display': usd_format(price_usd),
                        'bedrooms': int(beds_m.group(1)) if beds_m else 2,
                        'size_sqft': size_sqft,
                        'title': re.sub('<[^>]+>', '', title_m.group(1)).strip() if title_m else '',
                        'link': f"https://www.list.al{link_m.group(1)}" if link_m else '',
                        'source': 'List.al',
                    })
        except Exception as e:
            print(f"  [List.al] error: {e}")
        return out[:8]

# ── Georgia ───────────────────────────────────────────────────────────────────

class KoterGeFetcher(Fetcher):
    """Koter.ge – main Georgian real estate portal."""

    def fetch(self):
        results = []
        markets = [
            ("Tbilisi", "tbilisi"),
            ("Batumi", "batumi"),
        ]
        for label, slug in markets:
            url = f"https://koter.ge/en/real-estate?city={slug}&type=rent&bedrooms=2"
            try:
                results += self._fetch_ge(url, label)
            except Exception as e:
                print(f"  [Koter] {label} error: {e}")
        return results

    def _fetch_ge(self, url, label):
        import urllib.request
        out = []
        try:
            req = urllib.request.Request(url, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120',
            })
            with urllib.request.urlopen(req, timeout=20) as resp:
                html = resp.read().decode('utf-8', errors='replace')
            for block in re.findall(r'<div class="listing-card[^"]*">(.*?)</div>\s*</div>', html, re.DOTALL):
                price_m = re.search(r'([\d,\.]+)\s*(?:USD|\$|€|GEL)', block)
                title_m = re.search(r'class="listing-title"[^>]*>(.*?)</h3>', block)
                size_m = parse_size(block)
                beds_m = re.search(r'(\d+)\s*(?:bedroom|bed|br)', block, re.I)
                link_m = re.search(r'href="(/en/listing/[^"]+)"', block)
                if price_m:
                    price_usd = rating(price_m.group(0))
                    size_sqft = sqm_to_sqft(size_m) if size_m else None
                    out.append({
                        'city': label,
                        'price_usd': price_usd,
                        'price_display': usd_format(price_usd),
                        'bedrooms': int(beds_m.group(1)) if beds_m else 2,
                        'size_sqft': size_sqft,
                        'title': re.sub('<[^>]+>', '', title_m.group(1)).strip() if title_m else '',
                        'link': f"https://koter.ge{link_m.group(1)}" if link_m else '',
                        'source': 'Koter.ge',
                    })
        except Exception as e:
            print(f"  [Koter.ge] error: {e}")
        return out[:8]

# ── Portugal ──────────────────────────────────────────────────────────────────

class ImovirtualFetcher(Fetcher):
    """Imovirtual – major Portugal portal."""

    def fetch(self):
        results = []
        markets = [
            ("Lisbon", "lisbon"),
            ("Porto", "porto"),
            ("Faro", "faro"),
        ]
        for label, slug in markets:
            url = f"https://www.imovirtual.com/en/ads/?search=rent&location={slug}&rooms_min=2"
            try:
                results += self._fetch_pt(url, label)
            except Exception as e:
                print(f"  [Imovirtual] {label} error: {e}")
        return results

    def _fetch_pt(self, url, label):
        import urllib.request
        out = []
        try:
            req = urllib.request.Request(url, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120',
                'Accept-Language': 'en-US,en;q=0.9',
            })
            with urllib.request.urlopen(req, timeout=20) as resp:
                html = resp.read().decode('utf-8', errors='replace')
            for block in re.findall(r'<div class="offer-item[^"]*">(.*?)</div>\s*</div>', html, re.DOTALL):
                price_m = re.search(r'€[\d,\.]+', block)
                title_m = re.search(r'class="offer-item-title"[^>]*>(.*?)</', block)
                size_m = parse_size(block)
                beds_m = re.search(r'(\d+)\s*(?:bedroom|bed|br)', block, re.I)
                link_m = re.search(r'href="(/en/ad/[^"]+)"', block)
                if price_m:
                    price_usd = rating(price_m.group(0))
                    size_sqft = sqm_to_sqft(size_m) if size_m else None
                    out.append({
                        'city': label,
                        'price_usd': price_usd,
                        'price_display': usd_format(price_usd),
                        'bedrooms': int(beds_m.group(1)) if beds_m else 2,
                        'size_sqft': size_sqft,
                        'title': re.sub('<[^>]+>', '', title_m.group(1)).strip() if title_m else '',
                        'link': f"https://www.imovirtual.com{link_m.group(1)}" if link_m else '',
                        'source': 'Imovirtual',
                    })
        except Exception as e:
            print(f"  [Imovirtual] error: {e}")
        return out[:8]

# ── Vietnam ──────────────────────────────────────────────────────────────────

class VietnamWorksFetcher(Fetcher):
    """VietnamWorks – major Vietnamese job/property site."""

    def fetch(self):
        results = []
        url = "https://www.vietnamworks.com/property/en/rent"
        try:
            results += self._fetch_vn(url, "Da Nang")
        except Exception as e:
            print(f"  [VietnamWorks] Da Nang error: {e}")
        return results

    def _fetch_vn(self, url, label):
        import urllib.request
        out = []
        try:
            req = urllib.request.Request(url, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120',
            })
            with urllib.request.urlopen(req, timeout=20) as resp:
                html = resp.read().decode('utf-8', errors='replace')
            for block in re.findall(r'<div class="property-card[^"]*">(.*?)</div>\s*</div>', html, re.DOTALL):
                price_m = re.search(r'([\d,\.]+)\s*(?:USD|\$)', block)
                title_m = re.search(r'class="property-title"[^>]*>(.*?)</', block)
                size_m = parse_size(block)
                beds_m = re.search(r'(\d+)\s*(?:bedroom|bed|br)', block, re.I)
                link_m = re.search(r'href="(/property/[^"]+)"', block)
                if price_m:
                    price_usd = float(re.sub(r'[^\d.]', '', price_m.group(1).replace(',','')))
                    size_sqft = sqm_to_sqft(size_m) if size_m else None
                    out.append({
                        'city': label,
                        'price_usd': price_usd,
                        'price_display': usd_format(price_usd),
                        'bedrooms': int(beds_m.group(1)) if beds_m else 2,
                        'size_sqft': size_sqft,
                        'title': re.sub('<[^>]+>', '', title_m.group(1)).strip() if title_m else '',
                        'link': f"https://www.vietnamworks.com{link_m.group(1)}" if link_m else '',
                        'source': 'VietnamWorks',
                    })
        except Exception as e:
            print(f"  [VietnamWorks] error: {e}")
        return out[:8]

# ── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    all_listings = []

    # Run fetchers
    fetchers = [
        PropertyGuruFetcher("Kuala Lumpur"),
        ListAlFetcher("Albania"),
        KoterGeFetcher("Georgia"),
        ImovirtualFetcher("Portugal"),
        VietnamWorksFetcher("Vietnam"),
    ]

    for f in fetchers:
        print(f"\n=== Running {f.name} ===")
        try:
            results = f.fetch()
            print(f"  → {len(results)} raw results")
            all_listings.extend(results)
        except Exception as e:
            print(f"  → {f.name} failed: {e}")
            traceback.print_exc()

    print(f"\nTotal raw: {len(all_listings)}")

    # Deduplicate by price+city within 10%
    seen = {}
    deduped = []
    for listing in all_listings:
        key = f"{listing.get('city','x')}-{round(listing.get('price_usd',0)/50)*50}"
        if key not in seen:
            seen[key] = True
            deduped.append(listing)

    # Filter quality gates
    quality = [l for l in deduped
               if l.get('price_usd', 0) < 2500
               and l.get('bedrooms', 0) >= 2
               and l.get('link', '')]

    print(f"Quality-filtered: {len(quality)}")

def _atomic_json_write(path: str, data: Any) -> None:
    """Atomic write + read-back verification for rental scout JSON files."""
    import os
    temp = path + '.tmp'
    try:
        with open(temp, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
            f.write('\n')
        with open(temp, encoding='utf-8') as f:
            verify = json.load(f)
        if verify != data:
            raise RuntimeError(f'Write verification failed for {path}')
        os.replace(temp, path)
    except Exception as exc:
        import datetime as dt
        ERROR_LOG = "/home/user/.openclaw/workspace/tracking/state/cron-write-errors.json"
        errors = []
        try:
            import pathlib
            el = pathlib.Path(ERROR_LOG)
            el.parent.mkdir(parents=True, exist_ok=True)
            if el.exists():
                try:
                    errors = json.loads(el.read_text()).get('errors', [])
                except Exception:
                    pass
        except Exception:
            pass
        errors.append({
            'ts': dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
            'file': path,
            'operation': 'write',
            'error': str(exc)[:500],
        })
        errors = errors[-100:]
        try:
            pathlib.Path(ERROR_LOG).write_text(json.dumps({'errors': errors}, indent=2) + '\n')
        except Exception:
            pass
        raise

    # Save
    os.makedirs("/home/user/.openclaw/workspace/tmp", exist_ok=True)
    _atomic_json_write(TRACKING_FILE, {
        "runAt": datetime.now(timezone.utc).isoformat(),
        "markets": {l['city']: l for l in quality},
        "raw_count": len(all_listings),
        "quality_count": len(quality),
    })

    _atomic_json_write(COLLECTION_FILE, {
        "lastRun": datetime.now().strftime("%Y-%m-%d"),
        "listings": quality,
    })

    print("Done.")
    print(json.dumps({"count": len(quality)}, indent=2))