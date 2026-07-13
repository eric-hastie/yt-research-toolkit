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

def download_subtitles(url: str) -> Path:
    """Download auto-generated English subtitles via yt-dlp, return the .srt path."""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        result = subprocess.run(
            [
                'yt-dlp',
                '--write-auto-sub',
                '--sub-lang', 'en',
                '--sub-format', 'srt',
                '--convert-subs', 'srt',
                '--skip-download',
                '--no-playlist',
                '-o', str(tmp_path / '%(title)s.%(ext)s'),
                url,
            ],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            print(result.stderr)
            sys.exit(f"yt-dlp failed (exit {result.returncode})")

        srt_files = list(tmp_path.glob('*.srt'))
        if not srt_files:
            sys.exit("No subtitles found for this video.")

        src = srt_files[0]
        dest = OUT_DIR / src.name
        dest.write_bytes(src.read_bytes())
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
