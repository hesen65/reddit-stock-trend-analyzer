from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ContentItem:
    """Transient record; no username, author profile, or permalink."""

    content_id: str
    kind: str
    subreddit: str
    created_at: datetime
    text: str
