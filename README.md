# Reddit Stock Trend Analyzer

A small, non-commercial personal research project proposed for a Reddit API
Data Access Request. It analyzes public posts and comments in finance communities
such as **r/wallstreetbets, r/stocks, and r/investing** to identify publicly traded
stock ticker mentions and produce daily discussion statistics.

**Status:** runnable development scaffold; Reddit API approval is required before
live collection. This repository does not claim that access has been approved.
The offline demo uses invented examples and makes no network requests.

## Purpose and scope

The planned outputs are daily ticker mention counts, changes in discussion
volume compared with the preceding UTC day, and rankings of the most discussed
tickers in the collected sample. The results are informational research, not
investment advice or trade signals.

- Read only public posts (title and self-text) and public comments in explicitly
  configured, approved subreddits, using Reddit's authenticated Data API.
- Do not access private communities, private messages, account profiles, or other
  private information. Do not profile or identify users or infer personal traits.
- Do not automatically post, comment, vote, send private messages, or moderate.
- Do not execute automated trading or connect to a brokerage account.
- Do not sell Reddit data, train AI models, or use unapproved commercial services.

The API necessarily returns additional metadata. The collector selects only the
content text, content ID, creation timestamp, content kind, and subreddit needed
for this analysis. It never selects usernames or author profiles. Text and IDs
are used transiently in memory and are not written to report files or logs.
Only aggregate statistics are exported; this repository contains no real Reddit
content and no credentials.

## How the scaffold works

1. `config.py` reads credentials and bounded collection settings from environment
   variables; a local `.env` can be loaded for convenience.
2. `reddit_client.py` obtains an application-only OAuth token and uses only GET
   requests to public subreddit metadata, new posts, and recent comments. The
   OAuth token endpoint is the only POST request. It checks that a subreddit is
   public, limits requests and pagination, honors rate-limit headers, and waits
   on HTTP 429 with bounded retries.
3. `tickers.py` matches uppercase symbols and dollar-prefixed symbols against
   `data/tickers.txt`, a deliberately small example allowlist. Repeated matches
   count as separate mentions. Lowercase plain words do not count; `$aapl` does.
4. `aggregate.py` deduplicates content IDs within a run, groups by creation date
   in UTC, counts mentions and distinct items mentioning each ticker, and compares
   the selected day with the preceding day in the same collected sample.
5. `__main__.py` writes an aggregate JSON report and an aggregate ticker CSV.

This is a **bounded snapshot**, not an exhaustive historical archive or a complete
count of Reddit activity. Recent listing endpoints may not reach the requested
day, and active communities can exceed the configured limits. A zero means no
matching item was observed in this sample, not that no discussion occurred.
The JSON labels coverage as `bounded_recent_listing_sample`; day-to-day changes
are sample changes, affected by collection coverage. Percent changes are `null`
when the previous count is zero. Each day's counts include all configured
tickers, including zero-count tickers; daily ranks include only mentioned tickers.

Ticker detection is a heuristic: common uppercase words can overlap with symbols,
and context is not disambiguated. Expand and maintain the allowlist using a
legitimately obtained, current stock reference list. The example list is neither
complete nor a guarantee of current listing status. Company-name recognition,
sentiment analysis, durable cross-run deduplication, scheduling, and exhaustive
historical collection are not implemented.

## Run the offline demo

Requires Python 3.10 or newer. Run from the repository root:

```sh
python -m reddit_stock_trend_analyzer --demo --output-dir reports/demo
```

No credentials or third-party packages are needed for the demo. It uses synthetic
records dated January 1-2, 2026, and writes `daily-summary.json` and
`ticker-ranking.csv`. These invented records are never represented as actual
Reddit discussions. Inspect the JSON for both days' sampling counts and changes.

## Configure live collection after approval

First request and receive explicit Reddit approval for this use case and these
communities. Do not set the approval acknowledgement until approval is obtained.
No network requests are made by the CLI without that acknowledgement and valid
environment settings. This local acknowledgement does not grant API access.

```sh
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements.txt
# Copy .env.example to .env and edit it locally.
# Windows PowerShell: Copy-Item .env.example .env
# macOS/Linux: cp .env.example .env
python -m reddit_stock_trend_analyzer --date 2026-10-05 --output-dir reports/live
```

Use the actual UTC day you want to examine in place of the example date; the
default is yesterday in UTC. A single run examines that day and its preceding
day from recent listings. It may return partial or empty samples for older dates.
Environment variables take precedence over `.env` values. The only dependency is
`python-dotenv`, used when loading a local `.env`; direct environment-variable
configuration and the demo work with Python's standard library alone.

Set `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, and a truthful, descriptive
`REDDIT_USER_AGENT` issued/configured for your approved application. This scaffold
uses the confidential-client application-only flow; it does not ask for your
Reddit password, user refresh token, or account permissions. Credentials must
remain local. `.env.example` intentionally leaves credential fields blank.

Defaults are 25 posts and 100 comments per subreddit, at least two seconds
between HTTP attempts, and at most 20 HTTP attempts per run, including OAuth and
retries. Lower the volume or increase the interval to match your approved access.
Do not run overlapping collectors; they would share the same client quota.
An external scheduler could invoke the CLI after approval, but is not included.

## Data handling and responsible use

The project will comply with the [Responsible Builder Policy](https://support.reddithelp.com/hc/en-us/articles/42728983564564-Responsible-Builder-Policy),
[Reddit Data API Terms](https://redditinc.com/policies/data-api-terms), and applicable
Reddit terms. Use must remain within the scope Reddit explicitly approves.
No scraping fallback, alternate accounts, or quota circumvention is implemented.
The project respects Reddit API rate limits and response headers; consult the
[Data API Wiki](https://support.reddithelp.com/hc/en-us/articles/16160319875092-Reddit-Data-API-Wiki)
for current requirements instead of treating a quota as a permanent entitlement.

No raw-content database is implemented. Live text, IDs, and OAuth tokens exist
only in process memory during a run; reports contain daily counts and ticker
rankings without authors, content IDs, quotations, or permalinks. Reports remain
local and are ignored by Git. Retain only the aggregate reports needed for the
approved purpose, delete reports when no longer needed, and comply with Reddit
requests to delete or correct derived outputs. A snapshot cannot observe later
edits or deletions. Any future persistent collector needs deletion/refresh and
retention controls before deployment; this scaffold does not implement them.

## Repository layout

```text
reddit_stock_trend_analyzer/
  config.py          # Environment settings and approval acknowledgement
  reddit_client.py   # Bounded OAuth public-content collector
  tickers.py         # Allowlist-based ticker extraction
  aggregate.py       # Daily counts, changes, rankings, aggregate export
  models.py          # Minimal transient content record
  __main__.py        # Demo and live command-line entry point
data/tickers.txt     # Small example ticker allowlist
tests/              # Offline checks; no real API calls
requirements.txt
.env.example
.gitignore
```

Run the offline checks with `python -m unittest discover -s tests -v`.

## Reddit Data Access Request

Provide this repository's public GitHub URL in the form field requesting a link
to the source code or platform that will access the API. This repository documents
the intended implementation and its limitations; publication is not API approval.
