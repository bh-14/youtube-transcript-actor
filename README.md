## What does YouTube Transcript Scraper do?

YouTube Transcript Scraper gets the **transcript (captions) of YouTube videos** and returns it as clean plain text and as timestamped segments. Paste video URLs or IDs, pick the languages you want, and get one row per video, ready for AI summaries, RAG pipelines, SEO content, subtitles, research or search.

- **Bulk:** hundreds of videos in one run, watch links, `youtu.be` links, Shorts, embeds, live replays or bare video IDs.
- **Language control:** choose languages in order of preference; captions written by a person win over auto-generated ones. If the video has none of them, you get the language it does have, and every available caption track is listed.
- **Reliable from the cloud:** YouTube blocks cloud servers, so the Actor routes every request through Apify Proxy and switches to residential IPs automatically when a request is blocked. You don't configure any proxy.
- **Fair pricing:** you pay only for transcripts delivered. Videos without captions, private videos and invalid links are reported in the dataset for free.

## Why scrape YouTube transcripts?

- **AI and LLM apps:** feed video content to ChatGPT, Claude or your own model for summaries, Q&A and RAG knowledge bases.
- **Content repurposing:** turn videos into blog posts, newsletters, social posts and show notes.
- **SEO and research:** analyze what competitors and creators say, find keywords and quotes, study a topic across many videos.
- **Accessibility and subtitles:** reuse timestamped captions in your own player or editor.

## How to use YouTube Transcript Scraper

1. Click **Try for free**.
2. Paste one or more YouTube video URLs or IDs in **YouTube videos**.
3. Optional: set **Preferred languages** (for example `en`, `pt`, `es`).
4. Click **Start** and download the results as JSON, CSV, Excel or HTML, or get them through the API.

## Input

| Field | What it does | Default |
|---|---|---|
| `videos` | Video URLs or 11-character IDs | required |
| `languages` | Language codes in order of preference | `["en"]` |
| `fallbackToAnyLanguage` | If none of the preferred languages exists, return the language the video has | `true` |
| `includeSegments` | Also return timestamped segments | `true` |
| `maxConcurrency` | Videos fetched at the same time | `5` |

```json
{
    "videos": ["https://www.youtube.com/watch?v=aircAruvnKk", "dQw4w9WgXcQ"],
    "languages": ["en", "es"],
    "includeSegments": true
}
```

## Output

One item per video:

```json
{
    "videoId": "aircAruvnKk",
    "videoUrl": "https://www.youtube.com/watch?v=aircAruvnKk",
    "languageCode": "en",
    "language": "English",
    "isGenerated": false,
    "text": "This is a 3. It's sloppily written and rendered at an extremely low resolution of 28x28 pixels, but your brain has no trouble...",
    "wordCount": 3357,
    "segmentCount": 286,
    "durationSecs": 1105.6,
    "segments": [
        { "start": 4.22, "duration": 1.18, "text": "This is a 3." },
        { "start": 6.06, "duration": 4.653, "text": "It's sloppily written and rendered at an extremely low resolution of 28x28 pixels," }
    ],
    "availableLanguages": [
        { "languageCode": "ar", "language": "Arabic", "isGenerated": false },
        { "languageCode": "en", "language": "English", "isGenerated": false }
    ],
    "fetchedAt": "2026-10-10T20:51:59.030248+00:00",
    "error": null,
    "errorType": null
}
```

When a transcript can't be fetched, the item has `text: null` and explains why in `error` and `errorType` (for example `TranscriptsDisabled`, `NoTranscriptFound`, `VideoUnavailable`, `AgeRestricted`, `IpBlocked`). These items are free.

## How much does it cost?

The Actor uses pay-per-event pricing: you pay a small fee per **transcript delivered**, and nothing for failed videos. The current price is shown on the **Pricing** tab. Set a maximum cost per run in the run options and the Actor stops before going over it.

## Tips

- Auto-generated captions (`isGenerated: true`) are produced by YouTube's speech recognition and may contain mistakes.
- Videos with captions turned off by the creator have no transcript; the Actor can't create one.
- For very large batches, split them across several runs or raise **Max concurrency**.

## Is it legal to scrape YouTube transcripts?

The Actor reads only public captions that YouTube shows to any viewer, and stores no personal data. You are responsible for how you use the content: respect copyright and YouTube's terms, and check with a lawyer if you're unsure about your use case.

## Feedback

Found a video that fails, or need another field? Open an issue on the **Issues** tab and it will be looked at.
