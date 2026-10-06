import os
import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    client_id: str = field(repr=False)
    client_secret: str = field(repr=False)
    user_agent: str
    subreddits: tuple[str, ...]
    post_limit: int = 25
    comment_limit: int = 100
    min_interval: float = 2.0
    max_http_attempts: int = 20


def load_settings(env_file: Path = Path('.env')) -> Settings:
    if env_file.exists():
        try:
            from dotenv import load_dotenv
        except ImportError as exc:
            raise ValueError('Install requirements.txt to load a local .env file.') from exc
        load_dotenv(env_file, override=False)
    if os.getenv('REDDIT_API_APPROVED', '').lower() != 'true':
        raise ValueError('Live access requires explicit Reddit approval. Use --demo until approved.')
    required = ('REDDIT_CLIENT_ID', 'REDDIT_CLIENT_SECRET', 'REDDIT_USER_AGENT')
    missing = [name for name in required if not os.getenv(name, '').strip()]
    if missing:
        raise ValueError('Missing environment variables: ' + ', '.join(missing))
    names = tuple(dict.fromkeys(
        name.strip() for name in os.getenv(
            'REDDIT_SUBREDDITS', 'wallstreetbets,stocks,investing'
        ).split(',') if name.strip()
    ))
    if not names or len(names) > 10 or any(not re.fullmatch(r'[A-Za-z0-9_]{2,21}', n) for n in names):
        raise ValueError('Configure 1-10 valid public subreddit names without r/ prefixes.')
    settings = Settings(
        os.environ[required[0]].strip(), os.environ[required[1]].strip(),
        os.environ[required[2]].strip(), names,
        int(os.getenv('REDDIT_POST_LIMIT', '25')),
        int(os.getenv('REDDIT_COMMENT_LIMIT', '100')),
        float(os.getenv('REDDIT_MIN_REQUEST_INTERVAL_SECONDS', '2')),
        int(os.getenv('REDDIT_MAX_HTTP_ATTEMPTS', '20')),
    )
    if not 1 <= settings.post_limit <= 500 or not 1 <= settings.comment_limit <= 500:
        raise ValueError('Each listing limit must be between 1 and 500.')
    if not 2 <= settings.min_interval <= 3600 or not 1 <= settings.max_http_attempts <= 100:
        raise ValueError('Use an interval of 2-3600 seconds and a budget of 1-100 HTTP attempts.')
    return settings
