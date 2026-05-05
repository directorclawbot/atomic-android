#!/usr/bin/env python3
"""
Daily Learning Digest — weekday learning resource recommendations
Tracks suggested resources, evaluates effectiveness, continuously improves suggestions.
"""

import json
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

WORKSPACE = Path("/home/user/.openclaw/workspace")
TRACKING_DIR = WORKSPACE / "tracking"
STATE_DIR = TRACKING_DIR / "state" / "learning-digest"
COLLECTION_FILE = TRACKING_DIR / "collections" / "learning-digest.json"

# Learning resource categories
CATEGORIES = [
    "book",
    "course",
    "youtube",
    "podcast",
    "article",
    "masterclass",
    "great-courses",
    "workshop",
]

# Topics aligned with Rob's goals
TOPICS = [
    "product-management",
    "ai-agents",
    "investing",
    "real-estate",
    "data-governance",
    "copywriting",
    "marketing",
    "fire-movement",
    "heathenry-spirituality",
    "negotiation",
    "public-speaking",
    "finance",
    "entrepreneurship",
    "leadership",
    "system-thinking",
]

# Curated learning resources with metadata
# Format: (title, source, url, category, topic_tags, description, quality_score)
RESOURCE_POOL = [
    # Books
    ("Inspired", "Marty Cagan", "https://www.amazon.com/Inspired-Create-Products-Customers-Love/dp/1491970167",
     "book", ["product-management", "ai-agents"], 9.0,
     "The bible for modern product management. Essential if you're building products others will use."),
    ("Continuous Discovery Habits", "Teresa Torres", "https://www.amazon.com/Continuous-Discovery-Habits-Discover-Customers/dp/1950405252",
     "book", ["product-management"], 9.2,
     "Action-oriented product discovery. Great for AI-age product thinking."),
    ("The Lean Startup", "Eric Ries", "https://www.amazon.com/Lean-Startup-Now-New-Markets/dp/0596517977",
     "book", ["entrepreneurship", "finance"], 8.5,
     "Foundational for evidence-based product thinking. Still relevant."),
    ("Escaping the Build Trap", "Melissa Perri", "https://www.amazon.com/Escaping-Build-Trap-Effective-Product/dp/1942788332",
     "book", ["product-management"], 8.8,
     "Why product teams get stuck building the wrong things."),
    ("Building a Second Brain", "David Whyte", "https://www.amazon.com/Building-Second-Brain-Organize-Confidence/dp/1982167386",
     "book", ["system-thinking"], 8.5,
     "Personal knowledge management. Useful when you're running many systems."),
    ("Never Split the Difference", "Chris Voss", "https://www.amazon.com/Never-Split-Difference-Negotiate-Departments/dp/0062407805",
     "book", ["negotiation", "finance"], 9.0,
     "FBI hostage negotiator's tactics. Practical for any deal."),
    ("The Psychology of Money", "Morgan Housel", "https://www.amazon.com/Psychology-Money-Timeless-lessons-happiness/dp/0857197689",
     "book", ["finance", "fire-movement", "investing"], 9.0,
     "Behavioral finance done right. Accessible and durable."),
    ("The Simple Path to Wealth", "JL Collins", "https://www.amazon.com/Simple-Path-Wealth-Financial-Independence/dp/0991587010",
     "book", ["finance", "fire-movement", "investing"], 8.8,
     "The canonical FIRE book. Simple, direct, no-nonsense."),
    ("Range", "David Epstein", "https://www.amazon.com/Range-Generalists-Rules-Better-World/dp/0735214484",
     "book", ["entrepreneurship", "system-thinking"], 8.5,
     "Why generalists win in a specialized world. Relevant when everything is changing."),
    ("How to Win Friends and Influence People", "Dale Carnegie", "https://www.amazon.com/How-Win-Friends-Influence-People/dp/1982137274",
     "book", ["leadership", "negotiation"], 8.5,
     "Classic for a reason. Practical social skills."),
    ("The Almanack of Naval Ravikant", "Eric Jorgenson", "https://www.amazon.com/Almanack-Naval-Ravikant/dp/0578442960",
     "book", ["finance", "entrepreneurship", "ai-agents"], 9.0,
     "Wealth and wisdom from Naval. Concise and high-signal."),
    ("The Psychology of Persuasion", "Robert Cialdini", "https://www.amazon.com/Psychology-Persuasion-Business-Classics/dp/1589252363",
     "book", ["marketing", "copywriting", "negotiation"], 9.0,
     "The foundational authority on influence and persuasion."),
    ("Influence", "Robert Cialdini", "https://www.amazon.com/Influence-Psychology-Persuasion-Business-Classics/dp/1982137274",
     "book", ["marketing", "copywriting", "negotiation"], 9.0,
     "The classic on persuasion. More academic than Cialdini's summary version."),

    # Courses / Great Courses
    ("Product Management 101", "LinkedIn Learning", "https://www.linkedin.com/learning/product-management-foundations",
     "course", ["product-management"], 8.0,
     "Foundational PM skills. Good if you're new to product thinking."),
    ("Business Writing", "LinkedIn Learning", "https://www.linkedin.com/learning/writing-a-professional-report",
     "course", ["copywriting", "marketing"], 7.5,
     "Clear, concise business writing. Useful for the marketing content work."),
    ("Strategic Negotiation", "LinkedIn Learning", "https://www.linkedin.com/learning/strategic-negotiation",
     "course", ["negotiation"], 8.0,
     "Practical negotiation frameworks."),
    ("Data-Driven Marketing", "LinkedIn Learning", "https://www.linkedin.com/learning/data-driven-marketing",
     "course", ["marketing", "product-management"], 8.0,
     "Marketing decisions backed by data."),
    ("Financial Markets", "Yale Online / Coursera", "https://www.coursera.org/learn/financial-markets",
     "course", ["finance", "investing"], 9.2,
     "Taught by Yale's Robert Shiller. Free to audit. Excellent quality."),
    ("Machine Learning", "Stanford Online", "https://www.coursera.org/learn/machine-learning",
     "course", ["ai-agents"], 9.0,
     "Andrew Ng's classic. Free to audit. The definitive intro."),
    ("AI for Everyone", "DeepLearning.AI / Coursera", "https://www.coursera.org/learn/ai-for-everyone",
     "course", ["ai-agents"], 7.5,
     "Non-technical AI literacy. Fast and useful for product thinking."),

    # Great Courses Plus
    ("Brain Energy", "The Great Courses Plus", "https://www.thegreatcoursesplus.com",
     "great-courses", ["health", "system-thinking"], 7.5,
     "How to optimize brain function. Useful for sustained deep work."),
    ("Philosophy of Mind", "The Great Courses Plus", "https://www.thegreatcoursesplus.com",
     "great-courses", ["heathenry-spirituality", "system-thinking"], 7.5,
     "Explores consciousness, mind, and the nature of thought."),
    ("The Great Tours", "The Great Courses Plus", "https://www.thegreatcoursesplus.com",
     "great-courses", ["entrepreneurship"], 7.0,
     "Virtual travel + cultural education. Broadens context."),

    # YouTube channels
    ("Patrick Bet-David", "YouTube", "https://www.youtube.com/@PatrickBetDavid",
     "youtube", ["finance", "entrepreneurship", "negotiation"], 8.5,
     "Entrepreneurial mindset. What to watch before your next deal."),
    ("Andrei Jikh", "YouTube", "https://www.youtube.com/@AndreiJikh",
     "youtube", ["finance", "investing"], 7.5,
     "Personal finance and investing. Entertaining, practical."),
    ("Ali Abdaal", "YouTube", "https://www.youtube.com/@AliAbdaal",
     "youtube", ["product-management", "system-thinking"], 8.0,
     "Product doctor. Good at explaining systems and habits."),
    ("Magnify Money", "YouTube", "https://www.youtube.com/@MagnifyMoney",
     "youtube", ["finance", "fire-movement"], 7.5,
     "Banking, credit, personal finance. Practical and current."),
    ("Pursuit of Wealth", "YouTube", "https://www.youtube.com/@PursuitofWealth",
     "youtube", ["fire-movement", "investing", "finance"], 7.5,
     "FIRE-focused. Personal finance discipline."),
    ("Two Cents", "YouTube", "https://www.youtube.com/@TwoCentsPBS",
     "youtube", ["finance", "fire-movement"], 7.5,
     "PBS's personal finance channel. Accessible and well-researched."),
    ("Chris Invests", "YouTube", "https://www.youtube.com/@ChrisInvests",
     "youtube", ["investing", "real-estate"], 7.5,
     "Real estate investing education. Clear and practical."),
    ("George Kamel", "YouTube", "https://www.youtube.com/@GeorgeKamel",
     "youtube", ["finance", "fire-movement", "investing"], 7.5,
     "Dave Ramsey style with a modern edge. Strong following."),

    # Masterclass
    ("Chris Anderson on Public Speaking", "Masterclass", "https://www.masterclass.com/classes/chris-anderson-teaches-public-speaking",
     "masterclass", ["public-speaking"], 8.5,
     "TED founder on speaking clearly. Great for presentations and pitches."),
    ("Ruth Bader Ginsburg on Law", "Masterclass", "https://www.masterclass.com/classes/ruth-bader-ginsburg-teaches-law",
     "masterclass", ["negotiation", "leadership"], 8.0,
     "Legal mind and strategic thinking. Unexpectedly broadly applicable."),
    ("Bob Iger on Leadership", "Masterclass", "https://www.masterclass.com/classes/bob-iger-teaches-business-strategy",
     "masterclass", ["leadership", "entrepreneurship"], 8.5,
     "Disney CEO on building things that matter."),
    ("Daniel Pink on Sales", "Masterclass", "https://www.masterclass.com/classes/daniel-pink-teaches-sales",
     "masterclass", ["negotiation", "marketing"], 8.5,
     "When and how to persuade. From the author of To Sell Is Human."),

    # Podcasts (also great for commute/exercise)
    ("ChooseFI", "Podcast", "https://www.choiceinvestor.com/podcast",
     "podcast", ["fire-movement", "investing", "finance"], 9.0,
     "The FIRE community's flagship podcast. Rob already likes this one."),
    ("Invest Like a Pro", "Apple Podcasts", "https://podcasts.apple.com/podcast/id1434060466",
     "podcast", ["investing", "finance"], 8.0,
     "Real estate and investing education."),
    ("Pomp Podcast", "Podcast", "https://pomp.libsyn.com",
     "podcast", ["finance", "investing", "entrepreneurship"], 8.5,
     "Anthony Pompiano. Macro, BTC, contrarian investing."),
    ("The Knowledge Project", "Podcast", "https://fs.blog/knowledge-project/",
     "podcast", ["system-thinking", "decision-making", "finance"], 9.2,
     "Shane Parrish's podcast on decision-making and mental models. High-signal."),

    # Websites / newsletters
    ("Farnam Street (The Signal)", "Newsletter", "https://fs.blog/",
     "article", ["system-thinking", "decision-making"], 9.0,
     "Mental models, better thinking. The blog behind The Knowledge Project."),
    ("Not Boring", "Newsletter", "https://www.notboring.co",
     "article", ["product-management", "entrepreneurship", "ai-agents"], 8.5,
     "Product and business strategy. Consistently interesting."),
    ("Stratechery", "Newsletter", "https://stratechery.com",
     "article", ["product-management", "ai-agents", "finance"], 9.0,
     "Ben Thompson's analysis of tech strategy. Excellent for understanding platforms."),
    ("The Diff", "Newsletter", "https://diff.substack.com",
     "article", ["finance", "ai-agents", "product-management"], 8.5,
     "Capital as a competitive advantage. Finance meets tech thinking."),
]


def load_state() -> dict:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    state_file = STATE_DIR / "state.json"
    if state_file.exists():
        return json.loads(state_file.read_text())
    return {
        "sent": [],
        "feedback": {},
        "category_weights": {c: 1.0 for c in CATEGORIES},
        "topic_weights": {t: 1.0 for t in TOPICS},
        "quality_scores": {},
        "click_counts": {},
    }


def _atomic_save(path: Path, data: Any) -> None:
    """Atomic write + read-back verification for learning digest state/collection files."""
    path.parent.mkdir(parents=True, exist_ok=True)
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
        raise


def save_state(state: dict):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    state_file = STATE_DIR / "state.json"
    _atomic_save(state_file, state)


def save_collection(items: list):
    COLLECTION_FILE.parent.mkdir(parents=True, exist_ok=True)
    _atomic_save(COLLECTION_FILE, items)


def compute_resource_score(resource: dict, state: dict) -> float:
    """Score a resource based on quality, novelty, and learning state."""
    base = resource.get("quality_score", 7.0)
    title = resource.get("title", "")

    # Boost resources not yet sent
    novelty = 1.5 if title not in state.get("sent", []) else 1.0

    # Boost resources that showed good engagement
    clicks = state.get("click_counts", {}).get(title, 0)
    click_boost = 1.0 + (clicks * 0.1)

    # Boost categories Rob has been engaging with
    cat = resource.get("category", "article")
    cat_weight = state.get("category_weights", {}).get(cat, 1.0)

    return base * novelty * click_boost * cat_weight


def pick_resources(state: dict, count: int = 3) -> list:
    """Pick the best resources considering quality, novelty, and engagement."""
    scored = []
    for r in RESOURCE_POOL:
        title, source, url, category, topic_tags, quality_score, description = r
        resource = {
            "title": title,
            "source": source,
            "url": url,
            "category": category,
            "topic_tags": topic_tags,
            "quality_score": quality_score,
            "description": description,
        }
        score = compute_resource_score(resource, state)
        scored.append((score, resource))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [r for _, r in scored[:count]]


def build_markdown(resources: list, date_str: str) -> str:
    """Build Discord markdown digest."""
    day = datetime.now(timezone.utc).strftime("%A, %B %d, %Y")
    lines = [
        f"📚 **Learning Digest — {day}**\n",
        "*What to learn today. Sources ranked by quality, relevance, and your engagement history.*\n",
    ]

    category_emoji = {
        "book": "📖",
        "course": "🎓",
        "youtube": "▶️",
        "podcast": "🎙️",
        "article": "📝",
        "masterclass": "🎬",
        "great-courses": "🏛️",
        "workshop": "🛠️",
    }

    for i, r in enumerate(resources, 1):
        emoji = category_emoji.get(r["category"], "📌")
        topics = ", ".join(f"`{t}`" for t in r["topic_tags"])
        lines.extend([
            f"**{i}. {r['title']}** {emoji}",
            f"   {r['description']}",
            f"   Source: *{r['source']}* | Topics: {topics}",
            f"   🔗 {r['url']}\n",
        ])

    lines.extend([
        "---",
        "*Learning digest improves with use. Resources you've engaged with score higher over time.*",
    ])
    return "\n".join(lines)


def build_html(resources: list, date_str: str) -> str:
    """Build polished HTML email digest."""
    day = datetime.now(timezone.utc).strftime("%A, %B %d, %Y")

    cards_html = []
    category_emoji = {
        "book": "📖",
        "course": "🎓",
        "youtube": "▶️",
        "podcast": "🎙️",
        "article": "📝",
        "masterclass": "🎬",
        "great-courses": "🏛️",
        "workshop": "🛠️",
    }

    category_labels = {
        "book": "Book",
        "course": "Online Course",
        "youtube": "YouTube Channel",
        "podcast": "Podcast",
        "article": "Newsletter / Article",
        "masterclass": "Masterclass",
        "great-courses": "Great Courses",
        "workshop": "Workshop",
    }

    for i, r in enumerate(resources, 1):
        emoji = category_emoji.get(r["category"], "📌")
        cat_label = category_labels.get(r["category"], r["category"])
        topics = " ".join(f"<span class='tag'>{t}</span>" for t in r["topic_tags"])
        cards_html.append(f"""
        <div class="resource-card">
          <div class="card-header">
            <span class="card-number">{emoji}</span>
            <div class="card-title-block">
              <div class="card-title">{r['title']}</div>
              <div class="card-source">{r['source']} &bull; <span class="cat-label">{cat_label}</span></div>
            </div>
            <div class="card-score">{r['quality_score']:.1f}</div>
          </div>
          <div class="card-desc">{r['description']}</div>
          <div class="card-topics">{topics}</div>
          <div class="card-link"><a href="{r['url']}">View Resource →</a></div>
        </div>
        """)

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #f5f0e6; font-family: Georgia, serif; }}
  .wrapper {{ max-width: 600px; margin: 0 auto; padding: 24px 16px; }}
  .header {{ background: #1a2a3a; color: #f5f0e6; padding: 28px 24px; border-radius: 16px 16px 0 0; }}
  .header h1 {{ font-size: 1.4rem; margin-bottom: 4px; }}
  .header p {{ color: #aabbcc; font-size: 0.85rem; }}
  .content {{ background: #fff; padding: 24px; border-radius: 0 0 16px 16px; }}
  .resource-card {{ border: 1px solid #e8e0d0; border-radius: 12px; padding: 18px; margin-bottom: 14px; background: #fafaf5; }}
  .card-header {{ display: flex; align-items: flex-start; gap: 12px; margin-bottom: 10px; }}
  .card-number {{ font-size: 1.4rem; line-height: 1.2; }}
  .card-title-block {{ flex: 1; }}
  .card-title {{ font-size: 1.05rem; font-weight: bold; color: #1a2a3a; }}
  .card-source {{ font-size: 0.8rem; color: #666; margin-top: 2px; }}
  .cat-label {{ color: #8b6c3a; }}
  .card-score {{ background: #1a2a3a; color: #f5f0e6; border-radius: 8px; padding: 4px 8px; font-size: 0.8rem; font-weight: bold; min-width: 32px; text-align: center; }}
  .card-desc {{ font-size: 0.9rem; color: #444; line-height: 1.5; margin-bottom: 10px; }}
  .card-topics {{ margin-bottom: 10px; }}
  .tag {{ background: #e8e0d0; color: #5a4a2a; font-size: 0.72rem; padding: 2px 8px; border-radius: 20px; margin-right: 4px; display: inline-block; }}
  .card-link a {{ color: #8b6c3a; text-decoration: none; font-size: 0.85rem; font-weight: bold; }}
  .card-link a:hover {{ text-decoration: underline; }}
  .footer {{ text-align: center; padding: 16px; font-size: 0.75rem; color: #999; }}
  .footer a {{ color: #8b6c3a; }}
</style>
</head>
<body>
<div class="wrapper">
  <div class="header">
    <h1>📚 Today's Learning Digest</h1>
    <p>{day} &bull; 3 handpicked resources</p>
  </div>
  <div class="content">
    {"".join(cards_html)}
  </div>
  <div class="footer">
    Learning digest improves with use. Resources you've engaged with score higher over time.<br>
    <a href="#">Manage preferences</a>
  </div>
</div>
</body>
</html>"""
    return html


def send_email(html: str, subject: str) -> bool:
    """Send HTML email via gog CLI."""
    import subprocess
    SMTP_USER = "directorclawbot@gmail.com"
    FROM_NAME = "Director"  # Note: gog requires the from address to be the configured account

    try:
        result = subprocess.run(
            ["gog", "send",
             "--to", "robnield@gmail.com",
             "--from", SMTP_USER,
             "--subject", subject,
             "--body-html", html,
             "--no-input"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.returncode == 0
    except Exception as e:
        print(f"Email send failed: {e}")
        return False


def main():
    # Only send on weekdays (Mon-Fri)
    today = datetime.now(timezone.utc).weekday()
    if today >= 5:
        print("Weekend — skipping learning digest.")
        return

    state = load_state()
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Pick 3 top resources
    resources = pick_resources(state, count=3)

    # Mark as sent
    for r in resources:
        title = r["title"]
        if title not in state["sent"]:
            state["sent"].append(title)

    save_state(state)

    # Save to collection
    collection = load_collection()
    for r in resources:
        r["date_suggested"] = date_str
        # Avoid duplicates
        if not any(x.get("title") == r["title"] for x in collection):
            collection.insert(0, r)
    save_collection(collection)

    # Build outputs
    markdown = build_markdown(resources, date_str)
    html = build_html(resources, date_str)

    # Send email
    subject = f"📚 Learning Digest — {datetime.now(timezone.utc).strftime('%B %d')}"
    email_ok = send_email(html, subject)

    # Print Discord version
    print(markdown)
    print(f"\n--- Email {'✅ sent' if email_ok else '❌ failed'} ---")


if __name__ == "__main__":
    main()
