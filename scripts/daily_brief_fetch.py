#!/usr/bin/env python3
"""
Daily Market Brief Data Fetcher
Gathers all market data needed for the daily brief.
Uses the correct yfinance API (history() not fetch(), fast_info for metadata).
"""
import yfinance as yf
import json
import sys
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed

ERROR_LOG = "/home/user/.openclaw/workspace/tracking/state/cron-write-errors.json"

def log_error(stage, msg, details=""):
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "job": "daily_brief_fetch",
        "stage": stage,
        "message": msg,
        "details": details,
    }
    try:
        import os
        errors = []
        if os.path.exists(ERROR_LOG):
            try:
                with open(ERROR_LOG) as f:
                    errors = json.load(f)
            except (json.JSONDecodeError, IOError):
                errors = []
        errors.append(entry)
        with open(ERROR_LOG, "w") as f:
            json.dump(errors[-100:], f, indent=2)
    except Exception:
        pass


INSTRUMENTS = {
    'SPY':  {'name': 'S&P 500 ETF',         'type': 'equity'},
    'QQQ':  {'name': 'Nasdaq-100 ETF',        'type': 'equity'},
    'IWM':  {'name': 'Russell 2000 ETF',      'type': 'equity'},
    'VTI':  {'name': 'Total Stock Market ETF','type': 'equity'},
    'XLE':  {'name': 'Energy Select Sector',  'type': 'energy'},
    'XLF':  {'name': 'Financials Select',     'type': 'financial'},
    'XLK':  {'name': 'Tech Select',          'type': 'tech'},
    'GLD':  {'name': 'Gold ETF',              'type': 'metal'},
    'SLV':  {'name': 'Silver ETF',            'type': 'metal'},
    'TLT':  {'name': '20+ Year Treasury ETF', 'type': 'rates'},
    'UUP':  {'name': 'Dollar Bull',           'type': 'macro'},
    'XOM':  {'name': 'Exxon Mobil',           'type': 'energy'},
    'CVX':  {'name': 'Chevron',              'type': 'energy'},
    'NUE':  {'name': 'Nucor',                'type': 'materials'},
    # Futures / indices
    'CL=F': {'name': 'WTI Crude Oil',         'type': 'energy'},
    'GC=F': {'name': 'Gold Futures',          'type': 'metal'},
    '^TNX': {'name': '10Y Treasury Yield',    'type': 'rates'},
    '^VIX': {'name': 'CBOE VIX',             'type': 'volatility'},
}

SNAPSHOT_TICKERS = ['SPY', 'QQQ', 'IWM', 'VTI', 'XLE', 'XLF', 'XLK', 'GLD', 'SLV', 'TLT', 'UUP', 'XOM', 'CVX', 'NUE']
INFO_TICKERS     = ['SPY', 'QQQ', 'IWM', 'VTI']
METADATA_TICKERS = ['CL=F', 'GC=F', '^TNX', '^VIX']


def fetch_history(ticker, period='5d', interval='1d'):
    """Fetch price history. Returns (hist_df, error_or_None)."""
    try:
        obj = yf.Ticker(ticker)
        hist = obj.history(period=period, interval=interval)
        if hist.empty:
            return None, f"empty history for {ticker}"
        return hist, None
    except Exception as e:
        return None, str(e)


def fetch_fast_info(ticker):
    """Fetch fast metadata. Returns (dict, error_or_None)."""
    try:
        obj = yf.Ticker(ticker)
        fi = obj.fast_info
        return {
            'last_price': getattr(fi, 'last_price', None),
            'market_cap': getattr(fi, 'market_cap', None),
            'previous_close': getattr(fi, 'previous_close', None),
            'currency': getattr(fi, 'currency', None),
        }, None
    except Exception as e:
        return None, str(e)


def fetch_yield(ticker):
    """Fetch bond/futures yield via history + last close."""
    try:
        obj = yf.Ticker(ticker)
        hist = obj.history(period='5d', interval='1d')
        if hist.empty:
            return None, None, f"empty for {ticker}"
        last = hist['Close'].iloc[-1]
        prev = hist['Close'].iloc[-2] if len(hist) > 1 else last
        chg_pct = ((last - prev) / prev * 100) if prev else 0
        return last, chg_pct, None
    except Exception as e:
        return None, None, str(e)


def build_snapshot() -> list:
    """Build market snapshot rows with price, change_pct for each ticker."""
    snapshot = []
    failures = 0

    # Batch fetch equity histories in threads
    with ThreadPoolExecutor(max_workers=6) as ex:
        future_hist = {ex.submit(fetch_history, t): t for t in SNAPSHOT_TICKERS}
        future_info = {ex.submit(fetch_fast_info, t): t for t in INFO_TICKERS}

        hist_results = {}
        for fut in as_completed(future_hist):
            ticker = future_hist[fut]
            hist, err = fut.result()
            hist_results[ticker] = (hist, err)
            if err:
                print(f"WARN: {ticker} history failed: {err}", file=sys.stderr)
                failures += 1

        info_results = {}
        for fut in as_completed(future_info):
            ticker = future_info[fut]
            info, err = fut.result()
            info_results[ticker] = (info, err)

    # Build rows from history data
    for ticker in SNAPSHOT_TICKERS:
        hist, err = hist_results.get(ticker, (None, "not fetched"))
        if err or hist is None:
            snapshot.append({
                "ticker": ticker,
                "price": "—",
                "chg": "—",
                "signal": f"fetch error: {err}",
            })
            continue

        try:
            closes = hist['Close']
            last = closes.iloc[-1]
            prev = closes.iloc[-2] if len(closes) > 1 else last
            chg_pct = ((last - prev) / prev * 100) if prev else 0
            chg_str = f"{chg_pct:+.2f}%"
            price_str = f"${last:.2f}"

            info, _ = info_results.get(ticker, ({}, None))
            last_price = (info or {}).get('last_price')
            if last_price and last_price != last:
                price_str = f"${last_price:.2f}"

            snapshot.append({
                "ticker": ticker,
                "price": price_str,
                "chg": chg_str,
                "signal": "",
            })
        except Exception as e:
            snapshot.append({
                "ticker": ticker,
                "price": "—",
                "chg": "—",
                "signal": f"parse error: {e}",
            })

    # VIX separately
    vix_val, _, vix_err = fetch_yield('^VIX')
    if vix_err is None and vix_val is not None:
        # VIX is already a price-like value, not a yield
        pass

    # Bond/futures yields
    rate_tickers = [
        ('CL=F', 'WTI'),
        ('GC=F', 'Gold'),
        ('^TNX', '10Y'),
        ('UUP', 'DXY'),
    ]
    rate_data = {}
    for ticker, label in rate_tickers:
        val, chg, err = fetch_yield(ticker)
        if err is None and val is not None:
            chg_str = f"{chg:+.2f}%" if chg else "—"
            rate_data[ticker] = {'value': val, 'chg': chg_str}

    return snapshot, rate_data, vix_val


def get_market_summary() -> dict:
    """Gather all market data needed for the brief."""
    snapshot, rate_data, vix = build_snapshot()

    # SPY change for risk badge
    spy_hist, spy_err = fetch_history('SPY', period='5d')
    spy_chg_pct = 0.0
    if spy_err is None and spy_hist is not None and len(spy_hist) >= 2:
        closes = spy_hist['Close']
        last = closes.iloc[-1]
        prev = closes.iloc[-2]
        spy_chg_pct = ((last - prev) / prev * 100)

    return {
        'spy_chg_pct': round(spy_chg_pct, 2),
        'vix': f"{vix:.2f}" if vix else "—",
        'snapshot': snapshot,
        'rate_data': rate_data,
        'fetch_time_utc': datetime.now(timezone.utc).strftime("%H:%M"),
    }


if __name__ == "__main__":
    try:
        result = get_market_summary()
        # Also fetch individual rate data for the brief
        rate_data = result.pop('rate_data', {})

        print(json.dumps({**result, 'rates': rate_data}, default=str, indent=2))
        sys.exit(0)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        log_error("fetch", str(e))
        sys.exit(1)
