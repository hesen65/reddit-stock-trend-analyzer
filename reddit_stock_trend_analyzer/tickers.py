import re
from collections import Counter
from pathlib import Path


# Boundaries exclude embedded words, usernames, and ordinary lowercase tokens.
TOKEN = re.compile(
    r'(?<![\w/.-])(?:\$([A-Za-z]{1,5}(?:[.-][A-Za-z])?)|([A-Z]{1,5}(?:[.-][A-Z])?))'
    r'(?!\w|[.-][A-Za-z])'
)


def load_tickers(path: Path) -> set[str]:
    symbols = {line.strip().upper() for line in path.read_text(encoding='utf-8').splitlines()
               if line.strip() and not line.lstrip().startswith('#')}
    if not symbols or any(not re.fullmatch(r'[A-Z]{1,5}(?:[.-][A-Z])?', s) for s in symbols):
        raise ValueError('Ticker allowlist is empty or contains an invalid symbol.')
    return symbols


def extract_tickers(text: str, allowed: set[str]) -> Counter:
    return Counter(symbol for match in TOKEN.finditer(text)
                   if (symbol := (match.group(1) or match.group(2)).upper()) in allowed)
