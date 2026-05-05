#!/usr/bin/env python3
import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

WORKSPACE = Path('/home/user/.openclaw/workspace')
TRACKING_INDEX = WORKSPACE / 'tracking' / '_index.json'
CRON_SNAPSHOT = WORKSPACE / 'mission-control' / 'cron-snapshot.json'

import sys
sys.path.insert(0, str(WORKSPACE / 'scripts'))
import cron_file
DASHBOARD = WORKSPACE / 'mission-control' / 'dashboard.md'
RUNWAY = WORKSPACE / 'mission-control' / 'daily-runway.md'
OPERATOR_CONSOLE = WORKSPACE / 'mission-control' / 'today-operator-console.md'
EXPERIMENT_REGISTER = WORKSPACE / 'mission-control' / 'experiment-register.md'
REVISIT_QUEUE = WORKSPACE / 'mission-control' / 'revisit-queue.md'
DECISIONS = WORKSPACE / 'tracking' / 'collections' / 'decisions.json'
OPENCLAW_BIN = Path('/home/user/.npm-global/bin/openclaw')


def load_json(path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text())


def _atomic_json_write(path: Path, data: Any) -> None:
    """Atomic write + read-back verification for mission control JSON files."""
    import os
    temp = str(path) + '.tmp'
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
        ERROR_LOG = WORKSPACE / 'tracking' / 'state' / 'cron-write-errors.json'
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


def refresh_cron_snapshot():
    if not OPENCLAW_BIN.exists():
        return load_json(CRON_SNAPSHOT, {'jobs': []})

    try:
        result = subprocess.run(
            [str(OPENCLAW_BIN), 'cron', 'list', '--json'],
            cwd=str(WORKSPACE),
            capture_output=True,
            text=True,
            timeout=45,
            check=True,
        )
        data = json.loads(result.stdout)
        if not cron_file.safe_write_json(CRON_SNAPSHOT, data):
            cron_file.log_error('refresh_cron_snapshot', str(CRON_SNAPSHOT), 'safe_write_json returned False')
        return data
    except subprocess.TimeoutExpired:
        # Fall back to cached snapshot on timeout
        return load_json(CRON_SNAPSHOT, {'jobs': []})
    except Exception as exc:
        cron_file.log_error('refresh_cron_snapshot', str(CRON_SNAPSHOT), str(exc))
        return load_json(CRON_SNAPSHOT, {'jobs': []})


def fmt_local_schedule(job):
    sched = job.get('schedule', {})
    kind = sched.get('kind')
    if kind == 'every':
        ms = sched.get('everyMs', 0)
        mins = int(ms / 60000)
        return f"Every {mins} min"
    if kind == 'at':
        return f"One-time at {sched.get('at', 'unknown')}"
    if kind == 'cron':
        return sched.get('expr', 'unknown cron')
    return 'unknown'


def classify_job(name):
    low = name.lower()
    if 'travel' in low:
        return 'travel'
    if 'calendar' in low:
        return 'calendar'
    if 'job' in low:
        return 'jobs'
    if 'comic' in low:
        return 'comics'
    if 'saas' in low:
        return 'saas'
    if 'tool' in low:
        return 'tool-needs'
    if 'weekend' in low or 'pizza' in low:
        return 'weekend'
    if 'clothing' in low:
        return 'clothing'
    if 'ioniq' in low or 'ev' in low:
        return 'evs'
    if 'market' in low or 'moat' in low:
        return 'market'
    return 'other'


def load_decision_items():
    data = load_json(DECISIONS, {'items': []})
    return data.get('items', [])


def extract_revisit_triggers(decisions):
    """Extract decisions with revisit_when conditions and their trigger details."""
    revisit_items = []
    for d in decisions:
        if d.get('status') != 'active':
            continue
        decision_state = d.get('decision_state', {})
        revisit_when = decision_state.get('revisit_when', [])
        if revisit_when:
            revisit_items.append({
                'id': d.get('id', ''),
                'title': d.get('title', '(untitled)'),
                'summary': d.get('summary', ''),
                'triggers': revisit_when,
                'kind': decision_state.get('kind', 'decision'),
                'updated_at': d.get('updated_at', '')
            })
    return revisit_items


def build_dashboard(tracking, cron_jobs, decisions):
    date_label = datetime.now().strftime('%Y-%m-%d %H:%M')
    by_group = {}
    for job in cron_jobs:
        by_group.setdefault(classify_job(job.get('name', '')), []).append(job)

    failing_jobs = []
    for job in cron_jobs:
        state = job.get('state', {})
        if state.get('lastStatus') == 'error' or state.get('consecutiveErrors', 0) > 0:
            failing_jobs.append(job)

    active_decisions = [d for d in decisions if d.get('status') == 'active']
    revisit_queue = extract_revisit_triggers(decisions)

    lines = [
        '# Mission Control Dashboard',
        '',
        f'Last updated: {date_label}',
        '',
        '## Current Operating Picture',
        '',
        f'You currently have **{len(cron_jobs)} scheduled jobs** active or queued.',
        '',
        f'Current failing jobs: **{len(failing_jobs)}**.',
        '',
        f'Active decision records: **{len(active_decisions)}**.',
        '',
        f'Decisions with revisit triggers: **{len(revisit_queue)}**.',
        ''
    ]

    lines += [
        '## Operator layer',
        '',
        '- Front door: `mission-control/today-operator-console.md`',
        '- Experiments: `mission-control/experiment-register.md`',
        '- Revisit triggers: `mission-control/revisit-queue.md`',
        '- **Accuracy trending**: `mission-control/accuracy-dashboard.md`',
        ''
    ]

    if failing_jobs:
        lines += [
            '## Cron failures needing attention',
            ''
        ]
        for job in sorted(failing_jobs, key=lambda j: j.get('state', {}).get('consecutiveErrors', 0), reverse=True):
            state = job.get('state', {})
            reason = state.get('lastErrorReason', 'unknown')
            message = state.get('lastError', 'No error text available')
            last_run = state.get('lastRunAtMs')
            last_run_label = datetime.fromtimestamp(last_run / 1000).strftime('%Y-%m-%d %H:%M') if last_run else 'unknown'
            lines.append(f"- **{job.get('name','(unnamed)')}** — {state.get('consecutiveErrors', 0)} consecutive errors · last run {last_run_label} · reason: `{reason}`")
            lines.append(f"  - Last error: {message}")
        lines.append('')

    lines += [
        '## Jobs by area',
        ''
    ]
    for group in sorted(by_group):
        lines.append(f'### {group}')
        lines.append('')
        for job in by_group[group]:
            state = job.get('state', {})
            suffix = ''
            if state.get('lastStatus') == 'error' or state.get('consecutiveErrors', 0) > 0:
                suffix = f" ⚠️ error x{state.get('consecutiveErrors', 0)}"
            lines.append(f"- **{job.get('name','(unnamed)')}** — `{fmt_local_schedule(job)}`{suffix}")
        lines.append('')

    if active_decisions:
        lines += [
            '## Current durable decisions',
            ''
        ]
        for item in active_decisions[:8]:
            summary = item.get('summary', '').strip()
            title = item.get('title', '(untitled)')
            lines.append(f"- **{title}** — {summary}")
        lines.append('')

    # Revisit Queue section - live actionable layer
    if revisit_queue:
        lines += [
            '## Revisit Queue — Decisions to Reconsider',
            '',
            'These decisions have explicit revisit triggers. Review when conditions match current evidence.',
            '',
            '*Honesty note: Triggers are qualitative, not automatically evaluated. Operator must assess whether conditions are met.*',
            ''
        ]
        for item in revisit_queue:
            lines.append(f"### {item['title']}")
            lines.append(f"- **Type:** {item['kind']}")
            lines.append(f"- **Summary:** {item['summary']}")
            lines.append(f"- **Revisit when:**")
            for trigger in item['triggers']:
                lines.append(f"  - {trigger}")
            lines.append(f"- **Last updated:** {item['updated_at'][:10] if item['updated_at'] else 'unknown'}")
            lines.append('')

    # Needs attention today section
    attention_items = []
    
    # Check for failing jobs
    if failing_jobs:
        attention_items.append(("Jobs needing attention", [f"{job.get('name')} ({job.get('state', {}).get('consecutiveErrors', 0)} errors)" for job in failing_jobs[:3]]))
    
    # Surface revisit queue items that should be evaluated now
    # Since triggers are qualitative (not date-based), we surface all for manual evaluation
    # In practice, operator reviews these against current evidence
    if revisit_queue:
        attention_items.append(("Decisions due for revisit evaluation", [item['title'] for item in revisit_queue[:5]]))
    
    if attention_items:
        lines += [
            '## Needs attention today',
            ''
        ]
        for section_title, items in attention_items:
            lines.append(f"### {section_title}")
            for item in items:
                lines.append(f"- {item}")
            lines.append('')
    else:
        lines += [
            '## Needs attention today',
            '',
            'No items requiring immediate attention.',
            ''
        ]

    lines += [
        '## Tracking collections',
        ''
    ]
    for name, meta in tracking.get('collections', {}).items():
        lines.append(f"- **{meta.get('title', name)}** (`{name}`) — {meta.get('item_count', 0)} items")
    lines += [
        '',
        '## Efficiency / continuity notes',
        '',
        '- Shared tracking now exists for market, moat companies, clothing, EVs, jobs, travel deals, comics, SaaS ideas, tool-needs, weekend planning, and stay-at-home recommendations.',
        '- Calendar now has a snapshot/history file under `tracking/state/calendar-claw.json`.',
        '- Mission Control is now generated from snapshots instead of being purely hand-maintained.',
        '- The operator layer now sits on top of Mission Control so decisions, experiments, and revisit conditions are easier to act on.',
    ]
    return '\n'.join(lines) + '\n'


def build_runway(cron_jobs, decisions):
    date_label = datetime.now().strftime('%Y-%m-%d')
    sorted_jobs = sorted(cron_jobs, key=lambda job: (job.get('schedule', {}).get('kind', ''), fmt_local_schedule(job), job.get('name', '')))
    active_decisions = [d for d in decisions if d.get('status') == 'active']
    lines = [
        '# Daily Runway',
        '',
        f'Last updated: {date_label}',
        '',
        'Generated from the latest cron snapshot and decision registry.',
        '',
        '## Today\'s focus anchors',
        ''
    ]
    for item in active_decisions[:5]:
        lines.append(f"- **{item.get('title','(untitled)')}**")
    lines += [
        '',
        '## Current jobs',
        ''
    ]
    for job in sorted_jobs:
        lines.append(f"- **{job.get('name','(unnamed)')}** — `{fmt_local_schedule(job)}`")
    lines += [
        '',
        '## Immediate observation',
        '',
        'The next real efficiency gains now come more from better shared state and dedupe than from more schedule shuffling.'
    ]
    return '\n'.join(lines) + '\n'


def main():
    tracking = load_json(TRACKING_INDEX, {'collections': {}})
    decisions = load_decision_items()
    cron_data = refresh_cron_snapshot()
    jobs = cron_data.get('jobs', [])
    DASHBOARD.write_text(build_dashboard(tracking, jobs, decisions))
    RUNWAY.write_text(build_runway(jobs, decisions))
    print(json.dumps({'dashboard': str(DASHBOARD), 'runway': str(RUNWAY), 'jobs': len(jobs), 'decisions': len(decisions)}))


if __name__ == '__main__':
    main()
