#!/usr/bin/env python3
"""Prompt for a YouTube URL, download its auto-generated English transcript,
clean it, and save as <title>.clean.txt in your transcripts folder
(~/youtube_subtitles by default -- see OUT_DIR in srt.py).

Built to be triggered by a macOS keyboard shortcut (see SETUP.md). With no
argument it pops up a dialog, pre-filled from the clipboard when that looks
like a YouTube link, so you can usually just press Return. You can also pass
the URL as an argument:  python yt_to_txt.py <url>

Output format is identical to srt.py's .clean.srt, just saved as .txt.
"""

import os
import subprocess
import sys
from pathlib import Path

# When launched from a keyboard shortcut we don't inherit the Terminal's PATH,
# so make sure Homebrew's bin (yt-dlp, ffmpeg) is findable.
os.environ["PATH"] = "/opt/homebrew/bin:" + os.environ.get("PATH", "")

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

# Reuse the existing download + cleaning logic so formatting stays identical.
from srt import (  # noqa: E402
    download_subtitles,
    parse_srt,
    clean_blocks,
    write_srt,
    is_youtube_url,
)


def clipboard() -> str:
    return subprocess.run(["pbpaste"], capture_output=True, text=True).stdout.strip()


def notify(message: str) -> None:
    msg = message.replace('\\', '\\\\').replace('"', '\\"')
    subprocess.run(
        ["osascript", "-e",
         f'display notification "{msg}" with title "YouTube Transcript"'],
        capture_output=True,
    )


def error_dialog(message: str) -> None:
    msg = message.replace('\\', '\\\\').replace('"', '\\"')
    subprocess.run(
        ["osascript", "-e",
         f'display dialog "{msg}" with title "YouTube Transcript" '
         f'buttons {{"OK"}} default button "OK" with icon caution'],
        capture_output=True,
    )


def ask_for_url() -> str | None:
    """Show a paste box. Returns the entered text, or None if cancelled."""
    prefill = clipboard()
    if not is_youtube_url(prefill):
        prefill = ""
    prefill = prefill.replace('\\', '\\\\').replace('"', '\\"')
    script = (
        'display dialog "Paste a YouTube link to download its transcript:" '
        f'default answer "{prefill}" '
        'with title "YouTube Transcript" '
        'buttons {"Cancel", "Download"} default button "Download"\n'
        'return text returned of result'
    )
    proc = subprocess.run(["osascript", "-e", script],
                          capture_output=True, text=True)
    if proc.returncode != 0:          # Cancel pressed
        return None
    return proc.stdout.strip()


def main() -> None:
    url = sys.argv[1].strip() if len(sys.argv) > 1 else ask_for_url()
    if not url:
        return
    if not is_youtube_url(url):
        error_dialog("That doesn't look like a YouTube link:\n\n" + url)
        return

    notify("Downloading transcript…")
    try:
        raw = download_subtitles(url)     # writes <title>.en.srt into this folder
    except SystemExit as e:
        error_dialog(str(e) or "Download failed.")
        return
    except Exception as e:                # noqa: BLE001 - surface anything to the user
        error_dialog(f"Download failed:\n\n{e}")
        return

    text = raw.read_text(encoding="utf-8", errors="replace")
    cleaned = clean_blocks(parse_srt(text))
    out = raw.with_name(raw.stem.split(".en")[0] + ".clean.txt")
    out.write_text(write_srt(cleaned), encoding="utf-8")
    raw.unlink(missing_ok=True)

    notify("Saved: " + out.name)
    subprocess.run(["open", "-R", str(out)], capture_output=True)  # reveal in Finder


if __name__ == "__main__":
    main()
