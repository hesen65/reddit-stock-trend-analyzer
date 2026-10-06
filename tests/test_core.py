import json
import os
import tempfile
import unittest
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import patch

from reddit_stock_trend_analyzer.aggregate import summarize, write_reports
from reddit_stock_trend_analyzer.config import load_settings
from reddit_stock_trend_analyzer.models import ContentItem
from reddit_stock_trend_analyzer.tickers import extract_tickers, load_tickers


class TickerTests(unittest.TestCase):
    def test_punctuation_cashtags_and_share_classes(self):
        allowed = {'AAPL', 'NVDA', 'BRK.B', 'BRK-B'}
        self.assertEqual(
            extract_tickers('AAPL. ($nvda), BRK.B! $brk-b. AAPL...', allowed),
            Counter({'AAPL': 2, 'NVDA': 1, 'BRK.B': 1, 'BRK-B': 1}),
        )

    def test_reject_embedded_words_lowercase_and_partial_symbols(self):
        text = 'aapl XNAAPL AAPL2 u/AAPL r/NVDA BRK.B BRK.BLAH $NVDAx'
        self.assertEqual(extract_tickers(text, {'AAPL', 'NVDA', 'BRK', 'BLAH'}), Counter())

    def test_allowlist_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'tickers.txt'
            path.write_text('# example\naapl\nBRK.B\n', encoding='utf-8')
            self.assertEqual(load_tickers(path), {'AAPL', 'BRK.B'})
            path.write_text('AAPL\nINVALID_SYMBOL\n', encoding='utf-8')
            with self.assertRaises(ValueError):
                load_tickers(path)


class AggregateTests(unittest.TestCase):
    def test_utc_dates_deduplication_and_daily_changes(self):
        items = [
            ContentItem('t3_previous', 'post', 'stocks',
                        datetime.fromisoformat('2026-01-01T23:30:00+00:00'), 'AAPL'),
            ContentItem('t3_current', 'post', 'stocks',
                        datetime.fromisoformat('2026-01-03T00:30:00+02:00'), 'AAPL AAPL. NVDA'),
            ContentItem('t3_current', 'post', 'stocks',
                        datetime.fromisoformat('2026-01-03T00:30:00+02:00'), 'AAPL AAPL. NVDA'),
            ContentItem('t1_current', 'comment', 'stocks',
                        datetime.fromisoformat('2026-01-02T10:00:00+00:00'), 'NVDA'),
            ContentItem('t1_outside', 'comment', 'stocks',
                        datetime.fromisoformat('2026-01-03T10:00:00+00:00'), 'AAPL'),
        ]
        result = summarize(items, {'AAPL', 'NVDA', 'MSFT'}, date(2026, 1, 2))
        rows = {row['ticker']: row for row in result['tickers']}
        self.assertEqual(rows['AAPL']['mentions'], 2)
        self.assertEqual(rows['AAPL']['items_mentioning'], 1)
        self.assertEqual(rows['AAPL']['mention_change_percent'], 100.0)
        self.assertEqual(rows['NVDA']['rank'], 2)
        self.assertIsNone(rows['NVDA']['mention_change_percent'])
        self.assertIsNone(rows['MSFT']['rank'])
        self.assertEqual(result['daily_samples']['2026-01-02']['total_items'], 2)
        self.assertEqual(result['sampled_item_change'], 1)
        with tempfile.TemporaryDirectory() as directory:
            write_reports(result, Path(directory))
            saved = json.loads((Path(directory) / 'daily-summary.json').read_text(encoding='utf-8'))
            self.assertEqual(saved, result)
            raw = (Path(directory) / 'daily-summary.json').read_text(encoding='utf-8')
            self.assertNotIn('t3_current', raw)

    def test_naive_timestamps_are_rejected(self):
        item = ContentItem('t1_bad', 'comment', 'stocks', datetime(2026, 1, 2), 'AAPL')
        with self.assertRaises(ValueError):
            summarize([item], {'AAPL'}, date(2026, 1, 2))


class ConfigurationTests(unittest.TestCase):
    def test_live_access_requires_approval_and_credentials(self):
        with tempfile.TemporaryDirectory() as directory:
            no_env_file = Path(directory) / '.env'
            with patch.dict(os.environ, {}, clear=True):
                with self.assertRaisesRegex(ValueError, 'approval'):
                    load_settings(no_env_file)
            with patch.dict(os.environ, {'REDDIT_API_APPROVED': 'true'}, clear=True):
                with self.assertRaisesRegex(ValueError, 'Missing environment variables'):
                    load_settings(no_env_file)

    def test_invalid_limits_and_nonpublic_name_format_are_rejected(self):
        config = {
            'REDDIT_API_APPROVED': 'true', 'REDDIT_CLIENT_ID': 'test-id',
            'REDDIT_CLIENT_SECRET': 'test-secret', 'REDDIT_USER_AGENT': 'offline-unit-test',
        }
        with tempfile.TemporaryDirectory() as directory:
            no_env_file = Path(directory) / '.env'
            for invalid in ({'REDDIT_MIN_REQUEST_INTERVAL_SECONDS': '0'},
                            {'REDDIT_POST_LIMIT': '501'}, {'REDDIT_SUBREDDITS': 'r/stocks'}):
                with self.subTest(invalid=invalid), patch.dict(os.environ, {**config, **invalid}, clear=True):
                    with self.assertRaises(ValueError):
                        load_settings(no_env_file)


if __name__ == '__main__':
    unittest.main()
