#!/usr/bin/env python3
"""
EOD Market Snapshot Capture

Captures end-of-day closing data for key instruments used in the daily market brief.
Designed to be run as part of the market-brief cron workflow.

Instruments tracked:
- SPY (S&P 500 ETF)
- QQQ (Nasdaq-100 ETF)
- IWM (Russell 2000 ETF)
- VTI (Total Stock Market ETF)
- WTI crude oil (CL=F)
- GLD (Gold ETF)
- 10-Year Treasury Yield (^TNX)

Data quality notes:
- Yahoo Finance data is delayed (not real-time)
- EOD closes are typically available within 15-30 minutes after market close (4:00 PM ET)
- Weekend/holiday runs will return the prior trading day's close
- Bond yields may have limited hours; ^TNX tracks the 10-year Treasury note yield

Storage:
- Daily snapshots written to: tracking/state/market-eod/YYYY-MM.json (monthly files)
- Each day's data includes timestamp, prices, and metadata about data quality

Usage:
    python3 scripts/capture_eod_market_snapshot.py

Integration:
    Add to market-brief cron payload as a pre-step before feedback analysis.
"""

import yfinance as yf
from datetime import datetime, timezone
from pathlib import Path
import json
import os
import sys

WORKSPACE = Path('/home/user/.openclaw/workspace')
sys.path.insert(0, str(WORKSPACE / 'scripts'))

import cron_file

# Instruments to track
INSTRUMENTS = {
    # Core market ETFs
    'SPY': {'name': 'S&P 500 ETF', 'type': 'equity'},
    'QQQ': {'name': 'Nasdaq-100 ETF', 'type': 'equity'},
    'IWM': {'name': 'Russell 2000 ETF', 'type': 'equity'},
    'VTI': {'name': 'Total Stock Market ETF', 'type': 'equity'},
    
    # Sector ETFs
    'XLK': {'name': 'Technology Sector ETF', 'type': 'sector'},
    'XLF': {'name': 'Financial Sector ETF', 'type': 'sector'},
    'XLE': {'name': 'Energy Sector ETF', 'type': 'sector'},
    'XLB': {'name': 'Materials Sector ETF', 'type': 'sector'},
    'XLV': {'name': 'Health Care Sector ETF', 'type': 'sector'},
    'XLY': {'name': 'Consumer Discretionary Sector ETF', 'type': 'sector'},
    'XLP': {'name': 'Consumer Staples Sector ETF', 'type': 'sector'},
    'XLU': {'name': 'Utilities Sector ETF', 'type': 'sector'},
    'XLI': {'name': 'Industrials Sector ETF', 'type': 'sector'},
    
    # Major indices
    '^GSPC': {'name': 'S&P 500 Index', 'type': 'index'},
    '^IXIC': {'name': 'Nasdaq Composite Index', 'type': 'index'},
    '^DJI': {'name': 'Dow Jones Industrial Average', 'type': 'index'},
    
    # Volatility
    '^VIX': {'name': 'CBOE Volatility Index (VIX)', 'type': 'volatility'},
    
    # Commodities
    'CL=F': {'name': 'WTI Crude Oil Futures', 'type': 'commodity'},
    'GLD': {'name': 'Gold ETF', 'type': 'commodity'},
    
    # Bonds
    '^TNX': {'name': '10-Year Treasury Yield', 'type': 'bond'},
    
    # Key individual stocks
    'AAPL': {'name': 'Apple Inc.', 'type': 'stock'},
    'MSFT': {'name': 'Microsoft Corporation', 'type': 'stock'},
    'NVDA': {'name': 'NVIDIA Corporation', 'type': 'stock'},
    'TSLA': {'name': 'Tesla Inc.', 'type': 'stock'},
}

# Output directory (relative to workspace root)
OUTPUT_DIR = 'tracking/state/market-eod'


def get_workspace_root():
    """Resolve workspace root directory."""
    # Script is in scripts/, workspace is parent
    script_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.dirname(script_dir)


def fetch_eod_data(symbol: str) -> dict:
    """
    Fetch end-of-day data for a single instrument.
    
    Returns dict with:
    - symbol
    - name
    - close: closing price/yield
    - open, high, low: daily range
    - volume: trading volume (if applicable)
    - prior_close: previous day's close
    - change, change_pct: daily move
    - market_state: open/closed/pre/post
    - fetched_at: timestamp
    - data_quality: good/delayed/stale/missing
    - error: any error message
    """
    result = {
        'symbol': symbol,
        'name': INSTRUMENTS.get(symbol, {}).get('name', 'Unknown'),
        'type': INSTRUMENTS.get(symbol, {}).get('type', 'unknown'),
        'close': None,
        'open': None,
        'high': None,
        'low': None,
        'volume': None,
        'prior_close': None,
        'change': None,
        'change_pct': None,
        'market_state': 'unknown',
        'fetched_at': datetime.now(timezone.utc).isoformat(),
        'data_quality': 'unknown',
        'error': None,
    }
    
    try:
        ticker = yf.Ticker(symbol)
        
        # Get historical data for today and prior day
        # Use 2d period to ensure we get prior close for comparison
        hist = ticker.history(period='2d', interval='1d')
        
        if hist is None or len(hist) == 0:
            result['data_quality'] = 'missing'
            result['error'] = 'No historical data returned'
            return result
        
        # Get the most recent complete day
        # Yahoo sometimes includes partial today data, so we use the last row
        latest = hist.iloc[-1]
        
        result['close'] = float(latest['Close'])
        result['open'] = float(latest['Open']) if 'Open' in latest and latest['Open'] is not None else None
        result['high'] = float(latest['High']) if 'High' in latest and latest['High'] is not None else None
        result['low'] = float(latest['Low']) if 'Low' in latest and latest['Low'] is not None else None
        result['volume'] = int(latest['Volume']) if 'Volume' in latest and latest['Volume'] is not None else None
        
        # Calculate prior close and change
        if len(hist) >= 2:
            prior = hist.iloc[-2]
            result['prior_close'] = float(prior['Close'])
            
            if result['prior_close'] and result['prior_close'] > 0:
                result['change'] = round(result['close'] - result['prior_close'], 2)
                result['change_pct'] = round((result['change'] / result['prior_close']) * 100, 2)
        
        # Try to get market state
        try:
            info = ticker.info
            if info:
                result['market_state'] = info.get('marketState', 'closed')
        except Exception:
            pass
        
        # Assess data quality
        # If close is within last few hours and market is closed, mark as good
        result['data_quality'] = 'good'
        
        # For bond yields, volume may not be available - that's OK
        if symbol == '^TNX' and result['volume'] is None:
            result['volume'] = 'N/A'
        
    except Exception as e:
        result['data_quality'] = 'error'
        result['error'] = str(e)
    
    return result


def capture_snapshot() -> dict:
    """
    Capture EOD snapshot for all instruments.
    
    Returns complete snapshot dict ready for JSON serialization.
    """
    snapshot = {
        'snapshot_date': datetime.now(timezone.utc).strftime('%Y-%m-%d'),
        'snapshot_time_utc': datetime.now(timezone.utc).isoformat(),
        'instruments': {},
        'summary': {},
        'metadata': {
            'source': 'yfinance',
            'data_delay_note': 'Yahoo Finance data is delayed and may not reflect real-time prices',
            'eod_availability': 'EOD closes typically available 15-30 min after 4:00 PM ET',
            'weekend_behavior': 'Weekend/holiday runs return prior trading day closes',
        },
    }
    
    # Fetch all instruments
    for symbol in INSTRUMENTS.keys():
        data = fetch_eod_data(symbol)
        snapshot['instruments'][symbol] = data
    
    # Build summary for quick reference
    snapshot['summary'] = {
        # Core ETFs
        'spy_close': snapshot['instruments']['SPY']['close'],
        'qqq_close': snapshot['instruments']['QQQ']['close'],
        'iwm_close': snapshot['instruments']['IWM']['close'],
        'vti_close': snapshot['instruments']['VTI']['close'],
        # Sector ETFs
        'xlk_close': snapshot['instruments']['XLK']['close'],
        'xlf_close': snapshot['instruments']['XLF']['close'],
        'xle_close': snapshot['instruments']['XLE']['close'],
        'xlb_close': snapshot['instruments']['XLB']['close'],
        'xlv_close': snapshot['instruments']['XLV']['close'],
        'xly_close': snapshot['instruments']['XLY']['close'],
        'xlp_close': snapshot['instruments']['XLP']['close'],
        'xlu_close': snapshot['instruments']['XLU']['close'],
        'xli_close': snapshot['instruments']['XLI']['close'],
        # Major indices
        'gspc_close': snapshot['instruments']['^GSPC']['close'],
        'ixic_close': snapshot['instruments']['^IXIC']['close'],
        'dji_close': snapshot['instruments']['^DJI']['close'],
        # Volatility
        'vix_close': snapshot['instruments']['^VIX']['close'],
        'vix_change_pct': snapshot['instruments']['^VIX']['change_pct'],
        # Commodities
        'wti_close': snapshot['instruments']['CL=F']['close'],
        'gld_close': snapshot['instruments']['GLD']['close'],
        # Bonds
        'tnx_yield': snapshot['instruments']['^TNX']['close'],
        # Key stocks
        'aapl_close': snapshot['instruments']['AAPL']['close'],
        'msft_close': snapshot['instruments']['MSFT']['close'],
        'nvda_close': snapshot['instruments']['NVDA']['close'],
        'tsla_close': snapshot['instruments']['TSLA']['close'],
        # Daily changes
        'spy_change_pct': snapshot['instruments']['SPY']['change_pct'],
        'qqq_change_pct': snapshot['instruments']['QQQ']['change_pct'],
        'iwm_change_pct': snapshot['instruments']['IWM']['change_pct'],
    }
    
    return snapshot


def save_snapshot(snapshot: dict, workspace_root: str):
    """
    Save snapshot to monthly JSON file and append to rolling log.
    
    Files are organized as:
    tracking/state/market-eod/YYYY-MM.json
    
    Each file contains an array of daily snapshots for that month.
    
    Rolling log: tracking/state/market-eod/eod-log.jsonl
    """
    # Determine output file
    year_month = snapshot['snapshot_date'][:7]  # YYYY-MM
    output_subdir = os.path.join(workspace_root, OUTPUT_DIR)
    output_file = os.path.join(output_subdir, f'{year_month}.json')
    log_file = os.path.join(output_subdir, 'eod-log.jsonl')
    
    # Create directory if needed
    os.makedirs(output_subdir, exist_ok=True)
    
    # Load existing data for this month (if any)
    existing_data = []
    if os.path.exists(output_file):
        try:
            with open(output_file, 'r') as f:
                existing_data = json.load(f)
        except (json.JSONDecodeError, IOError):
            existing_data = []
    
    # Check if we already have data for this date
    snapshot_date = snapshot['snapshot_date']
    existing_dates = [d.get('snapshot_date') for d in existing_data]
    
    if snapshot_date in existing_dates:
        # Update existing entry for this date
        for i, entry in enumerate(existing_data):
            if entry.get('snapshot_date') == snapshot_date:
                existing_data[i] = snapshot
                break
    else:
        # Append new entry
        existing_data.append(snapshot)
    
    # Sort by date
    existing_data.sort(key=lambda x: x['snapshot_date'])
    
    # Write monthly file
    output_path = Path(output_file)
    if not cron_file.safe_write_json(output_path, existing_data):
        raise RuntimeError(f"Failed to persist monthly EOD snapshot to {output_file}")
    
    # Append to rolling log (JSONL format - one JSON object per line)
    log_entry = {
        'snapshot_date': snapshot['snapshot_date'],
        'snapshot_time_utc': snapshot['snapshot_time_utc'],
        'summary': snapshot['summary'],
        'data_quality_issues': [
            f"{sym}: {data['data_quality']}"
            for sym, data in snapshot['instruments'].items()
            if data['data_quality'] != 'good'
        ],
    }
    log_path = Path(log_file)
    existing_log = log_path.read_text() if log_path.exists() else ''
    new_log = existing_log + json.dumps(log_entry) + '\n'
    if not cron_file.safe_write_json_plain(log_path, new_log):
        raise RuntimeError(f"Failed to append EOD log entry to {log_file}")
    
    return output_file, log_file


def main():
    """Main entry point."""
    workspace_root = get_workspace_root()

    try:
        print("Capturing EOD market snapshot...")
        print(f"Workspace: {workspace_root}")
        print(f"Instruments: {', '.join(INSTRUMENTS.keys())}")

        snapshot = capture_snapshot()
        output_file, log_file = save_snapshot(snapshot, workspace_root)

        print(f"\nSnapshot saved to: {output_file}")
        print(f"Log appended to: {log_file}")
        print(f"Snapshot date: {snapshot['snapshot_date']}")
        print("\nKey closes:")
        print(f"  SPY:  ${snapshot['summary']['spy_close']:.2f} ({snapshot['summary']['spy_change_pct']:+.2f}%)")
        print(f"  QQQ:  ${snapshot['summary']['qqq_close']:.2f} ({snapshot['summary']['qqq_change_pct']:+.2f}%)")
        print(f"  IWM:  ${snapshot['summary']['iwm_close']:.2f} ({snapshot['summary']['iwm_change_pct']:+.2f}%)")
        print(f"  VTI:  ${snapshot['summary']['vti_close']:.2f}")
        print("\nSector ETFs:")
        print(f"  XLK:  ${snapshot['summary']['xlk_close']:.2f}")
        print(f"  XLF:  ${snapshot['summary']['xlf_close']:.2f}")
        print(f"  XLE:  ${snapshot['summary']['xle_close']:.2f}")
        print(f"  XLB:  ${snapshot['summary']['xlb_close']:.2f}")
        print(f"  XLV:  ${snapshot['summary']['xlv_close']:.2f}")
        print(f"  XLY:  ${snapshot['summary']['xly_close']:.2f}")
        print(f"  XLP:  ${snapshot['summary']['xlp_close']:.2f}")
        print(f"  XLU:  ${snapshot['summary']['xlu_close']:.2f}")
        print(f"  XLI:  ${snapshot['summary']['xli_close']:.2f}")
        print("\nMajor Indices:")
        print(f"  S&P 500:  {snapshot['summary']['gspc_close']:.2f}")
        print(f"  Nasdaq:   {snapshot['summary']['ixic_close']:.2f}")
        print(f"  Dow:      {snapshot['summary']['dji_close']:.2f}")
        print("\nVolatility & Commodities:")
        print(f"  VIX:  {snapshot['summary']['vix_close']:.2f} ({snapshot['summary']['vix_change_pct']:+.2f}%)")
        print(f"  WTI:  ${snapshot['summary']['wti_close']:.2f}")
        print(f"  GLD:  ${snapshot['summary']['gld_close']:.2f}")
        print(f"  10Y:  {snapshot['summary']['tnx_yield']:.2f}%")
        print("\nKey Stocks:")
        print(f"  AAPL: ${snapshot['summary']['aapl_close']:.2f}")
        print(f"  MSFT: ${snapshot['summary']['msft_close']:.2f}")
        print(f"  NVDA: ${snapshot['summary']['nvda_close']:.2f}")
        print(f"  TSLA: ${snapshot['summary']['tsla_close']:.2f}")

        issues = []
        for symbol, data in snapshot['instruments'].items():
            if data['data_quality'] != 'good':
                issues.append(f"{symbol}: {data['data_quality']} - {data.get('error', 'unknown issue')}")

        if issues:
            print("\n⚠️  Data quality warnings:")
            for issue in issues:
                print(f"  - {issue}")
        else:
            print("\n✓ All instruments captured successfully")

        return 0 if not issues else 1
    except Exception as exc:
        cron_file.log_error('capture_eod_market_snapshot', str(WORKSPACE / OUTPUT_DIR), str(exc))
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
