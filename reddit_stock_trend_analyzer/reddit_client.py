"""Application-only OAuth and bounded public listing reads; never writes to Reddit."""
import base64
import json
import math
import time
from datetime import date, datetime, time as day_time, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .config import Settings
from .models import ContentItem


class CollectionError(RuntimeError):
    pass


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Never forward credentials or bearer tokens to a redirected host.
        return None


class RedditClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.opener = build_opener(NoRedirects())
        self.token = None
        self.token_expires = 0.0
        self.next_request = 0.0
        self.attempts = 0

    def _json(self, url, data=None, authorization=None):
        headers = {'User-Agent': self.settings.user_agent, 'Accept': 'application/json'}
        if authorization:
            headers['Authorization'] = authorization
        if data is not None:
            headers['Content-Type'] = 'application/x-www-form-urlencoded'
        for retry in range(3):
            if self.attempts >= self.settings.max_http_attempts:
                raise CollectionError('HTTP budget exhausted; lower collection limits or adjust the approved budget.')
            time.sleep(max(0.0, self.next_request - time.monotonic()))
            self.attempts += 1
            self.next_request = time.monotonic() + self.settings.min_interval
            try:
                with self.opener.open(Request(url, data=data, headers=headers), timeout=30) as response:
                    remaining = float(response.headers.get('X-Ratelimit-Remaining', 'inf'))
                    reset = float(response.headers.get('X-Ratelimit-Reset', '0'))
                    if math.isfinite(reset) and reset > 0 and math.isfinite(remaining):
                        delay = reset + 1 if remaining < 1 else reset / remaining
                        self.next_request = max(self.next_request, time.monotonic() + delay)
                    return json.load(response)
            except HTTPError as exc:
                if exc.code == 429 and retry < 2:
                    try:
                        delay = float(exc.headers.get('Retry-After', '60'))
                    except (TypeError, ValueError):
                        delay = 60.0
                    if not math.isfinite(delay) or delay < 0:
                        delay = 60.0
                    self.next_request = max(self.next_request, time.monotonic() + max(60.0, delay) + 1)
                    continue
                # Do not include response bodies, request headers, or tokens in errors.
                raise CollectionError(f'Reddit returned HTTP {exc.code}; check approval and configuration.') from None
            except (URLError, TimeoutError):
                raise CollectionError('Reddit connection failed; no complete report was written.') from None

    def _get(self, path, **params):
        if not self.token or time.monotonic() >= self.token_expires:
            basic = base64.b64encode(
                f'{self.settings.client_id}:{self.settings.client_secret}'.encode()
            ).decode('ascii')
            payload = self._json(
                'https://www.reddit.com/api/v1/access_token',
                urlencode({'grant_type': 'client_credentials'}).encode(),
                'Basic ' + basic,
            )
            if not payload.get('access_token'):
                raise CollectionError('Reddit did not issue an application-only OAuth token.')
            self.token = payload['access_token']
            self.token_expires = time.monotonic() + max(1, int(payload.get('expires_in', 3600)) - 60)
        return self._json(
            'https://oauth.reddit.com' + path + '?' + urlencode({'raw_json': 1, **params}),
            authorization='Bearer ' + self.token,
        )

    def _listing(self, subreddit, listing, limit, start, end):
        after = None
        remaining = limit
        kind = 'post' if listing == 'new' else 'comment'
        while remaining > 0:
            params = {'limit': min(100, remaining)}
            if after:
                params['after'] = after
            page = self._get(f'/r/{subreddit}/{listing}', **params)['data']
            children = page['children']
            if not children:
                break
            reached_start = False
            for child in children[:remaining]:
                item = child['data']
                created = datetime.fromtimestamp(item['created_utc'], timezone.utc)
                if created < start:
                    reached_start = True
                text = '\n'.join((item.get('title', ''), item.get('selftext', ''))) if kind == 'post' else item.get('body', '')
                if start <= created < end and text.strip() not in ('', '[deleted]', '[removed]'):
                    yield ContentItem(item['name'], kind, subreddit, created, text)
            remaining -= len(children)
            next_after = page.get('after')
            if reached_start or not next_after or next_after == after:
                break
            after = next_after

    def collect(self, target: date):
        start = datetime.combine(target - timedelta(days=1), day_time.min, timezone.utc)
        end = datetime.combine(target + timedelta(days=1), day_time.min, timezone.utc)
        for name in self.settings.subreddits:
            metadata = self._get(f'/r/{name}/about')['data']
            if metadata.get('subreddit_type') != 'public':
                raise CollectionError('A configured subreddit is not public; collection stopped.')
            yield from self._listing(name, 'new', self.settings.post_limit, start, end)
            yield from self._listing(name, 'comments', self.settings.comment_limit, start, end)
