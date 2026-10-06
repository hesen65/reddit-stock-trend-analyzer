import io
import json
import unittest
from datetime import date
from urllib.error import HTTPError
from unittest.mock import Mock, patch

from reddit_stock_trend_analyzer.config import Settings
from reddit_stock_trend_analyzer.reddit_client import CollectionError, RedditClient


def settings(**overrides):
    values = dict(client_id='test-id', client_secret='test-secret',
                  user_agent='offline-unit-test', subreddits=('stocks',))
    return Settings(**{**values, **overrides})


def response(payload, headers=None):
    stream = io.BytesIO(json.dumps(payload).encode())
    stream.headers = headers or {}
    return stream


class CollectionTests(unittest.TestCase):
    def test_only_public_content_is_selected_and_not_author_metadata(self):
        client = RedditClient(settings())
        client._get = Mock(side_effect=[
            {'data': {'subreddit_type': 'public'}},
            {'data': {'children': [{'data': {
                'name': 't3_example', 'created_utc': 1767355200,
                'title': 'AAPL', 'selftext': 'NVDA', 'author': 'not-selected',
            }}], 'after': None}},
            {'data': {'children': [
                {'data': {'name': 't1_removed', 'created_utc': 1767355200, 'body': '[removed]'}},
                {'data': {'name': 't1_example', 'created_utc': 1767355200, 'body': 'TSLA'}},
            ], 'after': None}},
        ])
        items = list(client.collect(date(2026, 1, 2)))
        self.assertEqual([item.kind for item in items], ['post', 'comment'])
        self.assertEqual(items[0].text, 'AAPL\nNVDA')
        self.assertFalse(hasattr(items[0], 'author'))
        self.assertEqual([call.args[0] for call in client._get.call_args_list],
                         ['/r/stocks/about', '/r/stocks/new', '/r/stocks/comments'])

    def test_nonpublic_community_stops_before_content_requests(self):
        client = RedditClient(settings())
        client._get = Mock(return_value={'data': {'subreddit_type': 'private'}})
        with self.assertRaises(CollectionError):
            list(client.collect(date(2026, 1, 2)))
        client._get.assert_called_once_with('/r/stocks/about')

    def test_http_attempt_budget_is_enforced_before_another_request(self):
        client = RedditClient(settings(max_http_attempts=1))
        client.opener = Mock()
        client.opener.open.return_value = response({'ok': True})
        with patch('reddit_stock_trend_analyzer.reddit_client.time.sleep'):
            self.assertEqual(client._json('https://oauth.reddit.com/test'), {'ok': True})
            with self.assertRaisesRegex(CollectionError, 'budget'):
                client._json('https://oauth.reddit.com/test')
        self.assertEqual(client.opener.open.call_count, 1)

    def test_rate_limit_exhaustion_delays_next_attempt(self):
        client = RedditClient(settings())
        client.opener = Mock()
        client.opener.open.side_effect = [
            response({'ok': True}, {'X-Ratelimit-Remaining': '0', 'X-Ratelimit-Reset': '30'}),
            response({'ok': True}),
        ]
        with patch('reddit_stock_trend_analyzer.reddit_client.time.monotonic', return_value=100), \
             patch('reddit_stock_trend_analyzer.reddit_client.time.sleep') as sleep:
            client._json('https://oauth.reddit.com/test')
            client._json('https://oauth.reddit.com/test')
        self.assertEqual(sleep.call_args_list[1].args[0], 31)

    def test_429_backoff_retries_then_succeeds(self):
        client = RedditClient(settings())
        client.opener = Mock()
        client.opener.open.side_effect = [
            HTTPError('https://oauth.reddit.com/test', 429, 'limited', {'Retry-After': '90'}, None),
            response({'ok': True}),
        ]
        with patch('reddit_stock_trend_analyzer.reddit_client.time.monotonic', return_value=100), \
             patch('reddit_stock_trend_analyzer.reddit_client.time.sleep') as sleep:
            self.assertEqual(client._json('https://oauth.reddit.com/test'), {'ok': True})
        self.assertEqual(sleep.call_args_list[1].args[0], 91)
        self.assertEqual(client.attempts, 2)


if __name__ == '__main__':
    unittest.main()
