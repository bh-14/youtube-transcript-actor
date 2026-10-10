"""YouTube Transcript actor.

Fetches the transcript (captions) of a list of YouTube videos and pushes one dataset item per video. YouTube blocks
cloud IPs, so every request goes through Apify Proxy: datacenter first, residential only when datacenter is blocked.
Users pay only for transcripts delivered (the `transcript` pay-per-event event); failed videos are reported for free.
"""

from __future__ import annotations

import asyncio
import re
from datetime import datetime, timezone
from typing import Any

import requests
from apify import Actor, Event, ProxyConfiguration
from youtube_transcript_api import (
    AgeRestricted,
    InvalidVideoId,
    NoTranscriptFound,
    RequestBlocked,
    TranscriptsDisabled,
    VideoUnavailable,
    YouTubeTranscriptApi,
)
from youtube_transcript_api.proxies import GenericProxyConfig

CHARGED_EVENT = 'transcript'

# Failures that another IP cannot fix: retrying them only costs proxy traffic.
DEFINITIVE_ERRORS = (
    AgeRestricted,
    InvalidVideoId,
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
)

VIDEO_ID_RE = re.compile(r'^[A-Za-z0-9_-]{11}$')
URL_PATTERNS = [
    re.compile(r'[?&]v=([A-Za-z0-9_-]{11})'),
    re.compile(r'youtu\.be/([A-Za-z0-9_-]{11})'),
    re.compile(r'/(?:shorts|embed|live|v)/([A-Za-z0-9_-]{11})'),
]


def parse_video_id(value: str) -> str | None:
    """Return the 11-character video ID from a URL or a bare ID, or None if there is none."""
    value = value.strip()
    if VIDEO_ID_RE.match(value):
        return value
    for pattern in URL_PATTERNS:
        match = pattern.search(value)
        if match:
            return match.group(1)
    return None


def fetch_transcript(video_id: str, proxy_url: str | None, opts: dict[str, Any]) -> dict[str, Any]:
    """Fetch one transcript through one proxy URL and return the dataset item. Raises on failure."""
    proxy = GenericProxyConfig(http_url=proxy_url, https_url=proxy_url) if proxy_url else None
    api = YouTubeTranscriptApi(proxy_config=proxy, http_client=requests.Session())
    transcript_list = api.list(video_id)
    available = [
        {'languageCode': t.language_code, 'language': t.language, 'isGenerated': t.is_generated}
        for t in transcript_list
    ]

    try:
        transcript = transcript_list.find_transcript(opts['languages'])
    except NoTranscriptFound:
        if not opts['fallback_to_any_language']:
            raise
        # Prefer captions written by a person over auto-generated ones.
        transcripts = sorted(transcript_list, key=lambda t: t.is_generated)
        if not transcripts:
            raise
        transcript = transcripts[0]

    fetched = transcript.fetch()
    snippets = [{'start': round(s.start, 3), 'duration': round(s.duration, 3), 'text': s.text} for s in fetched]
    text = ' '.join(s['text'].replace('\n', ' ') for s in snippets).strip()
    end = snippets[-1]['start'] + snippets[-1]['duration'] if snippets else 0

    item: dict[str, Any] = {
        'videoId': video_id,
        'videoUrl': f'https://www.youtube.com/watch?v={video_id}',
        'languageCode': fetched.language_code,
        'language': fetched.language,
        'isGenerated': fetched.is_generated,
        'text': text,
        'wordCount': len(text.split()),
        'segmentCount': len(snippets),
        'durationSecs': round(end, 1),
        'availableLanguages': available,
        'fetchedAt': datetime.now(timezone.utc).isoformat(),
        'error': None,
        'errorType': None,
    }
    if opts['include_segments']:
        item['segments'] = snippets
    return item


async def get_transcript(
    video_id: str, routes: list[tuple[str, ProxyConfiguration | None]], opts: dict[str, Any]
) -> dict:
    """Try each proxy route in order until one delivers the transcript. Raises the last error."""
    last_error: Exception | None = None
    for name, config in routes:
        proxy_url = await config.new_url() if config else None
        try:
            return await asyncio.to_thread(fetch_transcript, video_id, proxy_url, opts)
        except DEFINITIVE_ERRORS:
            raise
        except Exception as exc:  # noqa: BLE001 - blocked or flaky request, try the next route
            Actor.log.debug(f'{video_id} failed via {name}: {type(exc).__name__}')
            last_error = exc
    raise last_error or RuntimeError('No proxy route available')


def error_message(exc: Exception) -> str:
    """Return the first meaningful line of a library error, without its long boilerplate."""
    if isinstance(exc, RequestBlocked):
        return 'YouTube blocked every attempt for this video, including through residential proxies. Try again later.'
    lines = [line.strip() for line in str(exc).splitlines() if line.strip()]
    for line in lines:
        if not line.startswith('Could not retrieve a transcript for the video'):
            return line[:300]
    return type(exc).__name__


async def main() -> None:
    """Read the input, fetch the transcripts concurrently and push one dataset item per video."""
    async with Actor:

        async def on_aborting(_: Any) -> None:
            await Actor.exit()

        Actor.on(Event.ABORTING, on_aborting)

        actor_input = await Actor.get_input() or {}
        languages = [c.strip() for c in actor_input.get('languages', ['en']) if isinstance(c, str) and c.strip()]
        opts = {
            'languages': languages or ['en'],
            'fallback_to_any_language': bool(actor_input.get('fallbackToAnyLanguage', True)),
            'include_segments': bool(actor_input.get('includeSegments', True)),
        }
        max_concurrency = max(1, min(int(actor_input.get('maxConcurrency', 5)), 20))

        # Accept URLs, bare IDs and the requestListSources format ({"url": ...}); drop duplicates.
        video_ids: list[str] = []
        for source in actor_input.get('videos', []):
            raw = (source.get('url') if isinstance(source, dict) else source) or ''
            video_id = parse_video_id(str(raw))
            if not video_id:
                Actor.log.warning(f'Skipping input that is not a YouTube video: {raw!r}')
                await Actor.push_data({'videoId': None, 'videoUrl': str(raw)[:500], 'text': None,
                                       'error': 'Not a YouTube video URL or ID', 'errorType': 'InvalidInput'})
            elif video_id not in video_ids:
                video_ids.append(video_id)

        if not video_ids:
            Actor.log.info('No valid videos in the input, exiting.')
            return

        # Never deliver more transcripts than the user's maximum cost per run allows.
        allowed = Actor.get_charging_manager().calculate_max_event_charge_count_within_limit(CHARGED_EVENT)
        if allowed is not None and allowed < len(video_ids):
            Actor.log.warning(f'The run cost limit allows only {allowed} of {len(video_ids)} transcripts.')
            video_ids = video_ids[:allowed]
            if not video_ids:
                return

        routes: list[tuple[str, ProxyConfiguration | None]] = []
        for name, groups in (('datacenter', None), ('residential', ['RESIDENTIAL'])):
            try:
                config = await Actor.create_proxy_configuration(groups=groups)
            except ConnectionError as exc:
                Actor.log.warning(f'Apify Proxy ({name}) is not available: {exc}')
                config = None
            if config:
                routes += [(name, config), (name, config)]
        if not routes:
            if Actor.is_at_home():
                raise RuntimeError('Apify Proxy is not available, and YouTube blocks cloud IPs without it.')
            # Local development: a home connection is not blocked, so go direct.
            routes = [('direct', None)]

        Actor.log.info(f'Fetching {len(video_ids)} transcript(s) with concurrency {max_concurrency}.')
        semaphore = asyncio.Semaphore(max_concurrency)
        delivered = 0

        async def handle(video_id: str) -> None:
            nonlocal delivered
            async with semaphore:
                try:
                    item = await get_transcript(video_id, routes, opts)
                    await Actor.push_data(item, charged_event_name=CHARGED_EVENT)
                    delivered += 1
                    Actor.log.info(f'OK {video_id} ({item["languageCode"]}, {item["wordCount"]} words)')
                except Exception as exc:  # noqa: BLE001 - every failure becomes a free dataset item
                    Actor.log.warning(f'Failed {video_id}: {type(exc).__name__}')
                    await Actor.push_data({
                        'videoId': video_id,
                        'videoUrl': f'https://www.youtube.com/watch?v={video_id}',
                        'text': None,
                        'error': error_message(exc),
                        'errorType': type(exc).__name__,
                    })

        await asyncio.gather(*(handle(v) for v in video_ids))
        Actor.log.info(f'Delivered {delivered} of {len(video_ids)} transcript(s).')
