#!/usr/bin/env python3
"""
Download and clean subtitles in one step.

Usage:
    python srt.py <youtube-url>        # download subtitles then clean
    python srt.py <file.srt|file.txt>  # clean a local subtitle file

Output: <title>.clean.srt (for URLs) or <filename>.clean.srt (for local files)
"""

import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path


# ── SRT parsing & cleaning ────────────────────────────────────────────────────

def parse_srt(text: str) -> list[dict]:
    blocks = []
    for block in re.split(r'\n{2,}', text.strip()):
        lines = block.strip().splitlines()
        if len(lines) < 2 or '-->' not in lines[1]:
            continue
        try:
            int(lines[0])
        except ValueError:
            continue
        start, end = lines[1].split('-->')
        blocks.append({
            'start': start.strip(),
            'end': end.strip(),
            'text': '\n'.join(lines[2:]),
        })
    return blocks


def clean_blocks(blocks: list[dict]) -> list[dict]:
    result = []
    prev_text = None

    for block in blocks:
        lines = [l.strip() for l in block['text'].splitlines() if l.strip()]
        if not lines:
            continue
        new_text = lines[-1]
        if new_text != prev_text:
            result.append({'start': block['start'], 'end': block['end'], 'text': new_text})
            prev_text = new_text
        elif result:
            result[-1]['end'] = block['end']

    for i in range(len(result) - 1):
        result[i]['end'] = result[i + 1]['start']

    return result


def write_srt(blocks: list[dict]) -> str:
    return '\n'.join(
        f"{i}\n{b['start']} --> {b['end']}\n{b['text']}\n"
        for i, b in enumerate(blocks, 1)
    )


def clean_file(src: Path, out: Path) -> None:
    text = src.read_text(encoding='utf-8', errors='replace')
    blocks = parse_srt(text)
    cleaned = clean_blocks(blocks)
    out.write_text(write_srt(cleaned), encoding='utf-8')
    print(f"Cleaned: {len(blocks)} blocks -> {len(cleaned)} blocks")
    print(f"Output:  {out}")


# ── YouTube download ──────────────────────────────────────────────────────────

def is_youtube_url(s: str) -> bool:
    return 'youtube.com' in s or 'youtu.be' in s


# Cleaned transcripts are saved here, separate from the code, so the growing
# transcript library never ends up in version control. Override by setting the
# YT_TRANSCRIPTS_DIR environment variable, or change the default below.
OUT_DIR = Path(os.environ.get("YT_TRANSCRIPTS_DIR", "~/youtube_subtitles")).expanduser()

# ── Fetching the right caption track ─────────────────────────────────────────
# YouTube labels an English video's own automatic captions "en-orig". Plain "en"
# (and "en.*") automatic captions are machine translations, and YouTube rate-limits
# only those: HTTP 429 (yt-dlp issue #13831, pinned maintainer comment, 2026-01-06).
# So: "en-orig" automatic first, then human-made "en" subtitles only.

RATE_LIMITED = "rate_limited"
NO_SUBS = "no_subs"
BOT_CHECK = "bot_check"  # "Sign in to confirm you're not a bot": wait, don't retry hard
TRACKS = (("en-orig", True), ("en", False))  # (track, include automatic captions)


def fetch_caption_srt(url: str, retries: int = 2, backoff: tuple = (30, 90),
                      extra_args: list | None = None, tracks: tuple = TRACKS):
    """Return (raw_srt_text, status, track). status is "ok", RATE_LIMITED,
    BOT_CHECK, NO_SUBS or "error: <tail of stderr>"."""
    import time
    last_err = ""
    for track, auto in tracks:
        for attempt in range(retries + 1):
            with tempfile.TemporaryDirectory() as tmp:
                tp = Path(tmp)
                proc = subprocess.run(
                    ['yt-dlp', *(['--write-auto-sub'] if auto else []), '--write-sub',
                     '--sub-lang', track, '--sub-format', 'srt', '--convert-subs', 'srt',
                     '--skip-download', '--no-playlist', *(extra_args or []),
                     '-o', str(tp / 'v.%(ext)s'), url],
                    capture_output=True, text=True)
                srts = list(tp.glob('*.srt'))
                if srts:
                    return srts[0].read_text(encoding='utf-8', errors='replace'), "ok", track
            err = proc.stderr or ""
            if "confirm you" in err:
                return None, BOT_CHECK, None
            if "429" in err or "Too Many Requests" in err:
                last_err = RATE_LIMITED
                if attempt < retries:
                    time.sleep(backoff[min(attempt, len(backoff) - 1)])
                    continue
                return None, RATE_LIMITED, None
            if proc.returncode != 0 and "no subtitles" not in err.lower():
                last_err = "error: " + err.strip()[-200:]
            break  # this track does not exist; try the next one
    return None, (last_err or NO_SUBS), None


def download_subtitles(url: str) -> Path:
    """Download English subtitles via yt-dlp, return the .srt path."""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    raw, status, _ = fetch_caption_srt(url)
    if raw is None:
        sys.exit(f"Could not get subtitles: {status}")
    title = subprocess.run(['yt-dlp', '--no-playlist', '--print', '%(title)s', url],
                           capture_output=True, text=True).stdout.strip() or 'video'
    dest = OUT_DIR / (re.sub(r'[/\\:]', '_', title) + '.en.srt')
    dest.write_text(raw, encoding='utf-8')
    return dest


# ── Entry point ───────────────────────────────────────────────────────────────

def process_url(url: str) -> None:
    print(f"\nDownloading: {url}")
    raw = download_subtitles(url)
    print(f"Downloaded: {raw.name}")
    out = raw.with_name(raw.stem.split('.en')[0] + '.clean.srt')
    clean_file(raw, out)
    raw.unlink()


def main() -> None:
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)

    arg = sys.argv[1]

    if is_youtube_url(arg):
        process_url(arg)
    else:
        src = Path(arg)
        if not src.exists():
            sys.exit(f"File not found: {src}")

        # Check if the file is a list of YouTube URLs
        lines = [l.strip() for l in src.read_text().splitlines() if l.strip()]
        urls = [l for l in lines if is_youtube_url(l)]

        if urls:
            print(f"Found {len(urls)} YouTube URL(s) in {src.name}")
            for url in urls:
                process_url(url)
        else:
            OUT_DIR.mkdir(parents=True, exist_ok=True)
            out = OUT_DIR / (src.stem + '.clean.srt')
            clean_file(src, out)


if __name__ == '__main__':
    main()
