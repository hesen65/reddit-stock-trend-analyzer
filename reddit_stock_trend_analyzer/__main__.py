import argparse
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from .aggregate import summarize, write_reports
from .config import load_settings
from .models import ContentItem
from .reddit_client import CollectionError, RedditClient
from .tickers import load_tickers


def demo_items():
    """Invented records for an offline demonstration; not actual Reddit content."""
    examples = [
        ('demo-1', 'post', '2026-01-01T10:00:00+00:00', 'AAPL and $NVDA research'),
        ('demo-2', 'comment', '2026-01-01T12:00:00+00:00', 'AAPL'),
        ('demo-3', 'post', '2026-01-02T10:00:00+00:00', '$NVDA NVDA and MSFT'),
        ('demo-4', 'comment', '2026-01-02T11:00:00+00:00', '$aapl and TSLA'),
        ('demo-5', 'comment', '2026-01-02T12:00:00+00:00', 'NVDA'),
    ]
    return [ContentItem(i, k, 'synthetic_demo', datetime.fromisoformat(t), text)
            for i, k, t, text in examples]


def main():
    parser = argparse.ArgumentParser(description='Aggregate a bounded sample of public Reddit ticker mentions.')
    parser.add_argument('--demo', action='store_true', help='Synthetic offline demo; no network or credentials.')
    parser.add_argument('--date', type=date.fromisoformat, help='Target UTC date (YYYY-MM-DD); default: yesterday.')
    parser.add_argument('--tickers-file', type=Path, default=Path(__file__).resolve().parents[1] / 'data' / 'tickers.txt')
    parser.add_argument('--output-dir', type=Path, default=Path('reports'))
    args = parser.parse_args()
    try:
        allowed = load_tickers(args.tickers_file)
        if args.demo:
            target = args.date or date(2026, 1, 2)
            items = demo_items()
            metadata = {'source': 'synthetic_offline_demo', 'subreddits': ['synthetic_demo']}
        else:
            target = args.date or (datetime.now(timezone.utc).date() - timedelta(days=1))
            settings = load_settings()
            client = RedditClient(settings)
            items = client.collect(target)
            metadata = {'source': 'reddit_oauth_public_api', 'subreddits': list(settings.subreddits),
                        'post_limit_per_subreddit': settings.post_limit,
                        'comment_limit_per_subreddit': settings.comment_limit}
        report = summarize(items, allowed, target)
        report.update(metadata)
        report['generated_at'] = datetime.now(timezone.utc).isoformat()
        write_reports(report, args.output_dir)
        print(f'Aggregate report written to {args.output_dir.resolve()}')
        return 0
    except (ValueError, OSError, CollectionError):
        # Avoid echoing configuration values, paths containing secrets, or raw content.
        print('Unable to complete collection. Check approval, environment settings, API access, and output permissions. Use --demo for offline validation.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
