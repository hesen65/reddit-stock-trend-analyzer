import csv
import json
from collections import Counter
from datetime import date, timedelta, timezone
from pathlib import Path

from .tickers import extract_tickers


def summarize(items, allowed: set[str], target: date) -> dict:
    previous = target - timedelta(days=1)
    counts = {day: Counter() for day in (previous, target)}
    documents = {day: Counter() for day in counts}
    sampled = {day: Counter() for day in counts}
    seen = set()
    for item in items:
        if item.created_at.tzinfo is None:
            raise ValueError('Content timestamps must include a timezone.')
        day = item.created_at.astimezone(timezone.utc).date()
        if day not in counts or item.content_id in seen:
            continue
        seen.add(item.content_id)
        sampled[day][item.kind] += 1
        mentions = extract_tickers(item.text, allowed)
        counts[day].update(mentions)
        documents[day].update(mentions.keys())
    ranking = sorted((s for s in allowed if counts[target][s]), key=lambda s: (-counts[target][s], s))
    ranks = {symbol: rank for rank, symbol in enumerate(ranking, 1)}
    rows = []
    for symbol in sorted(allowed, key=lambda s: (-counts[target][s], s)):
        current, prior = counts[target][symbol], counts[previous][symbol]
        rows.append({
            'ticker': symbol, 'rank': ranks.get(symbol), 'mentions': current,
            'items_mentioning': documents[target][symbol], 'previous_mentions': prior,
            'mention_change': current - prior,
            'mention_change_percent': round(100 * (current - prior) / prior, 2) if prior else None,
        })
    daily_samples = {str(day): {'posts': sampled[day]['post'], 'comments': sampled[day]['comment'],
                              'total_items': sum(sampled[day].values())} for day in sampled}
    current_items, previous_items = sum(sampled[target].values()), sum(sampled[previous].values())
    return {
        'date': str(target), 'previous_date': str(previous), 'timezone': 'UTC',
        'coverage': 'bounded_recent_listing_sample', 'daily_samples': daily_samples,
        'sampled_item_change': current_items - previous_items,
        'sampled_item_change_percent': round(100 * (current_items - previous_items) / previous_items, 2) if previous_items else None,
        'tickers': rows,
    }


def write_reports(report: dict, directory: Path):
    directory.mkdir(parents=True, exist_ok=True)
    (directory / 'daily-summary.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    with (directory / 'ticker-ranking.csv').open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(report['tickers'][0]))
        writer.writeheader()
        writer.writerows(report['tickers'])
