# ⌘⇧Y → paste a YouTube link → get a .txt transcript

`yt_to_txt.py` downloads a video's auto-generated English transcript, cleans it
(same engine as `srt.py`), and saves it as `<title>.clean.txt` in your
transcripts folder - `~/youtube_subtitles` by default, or wherever the
`YT_TRANSCRIPTS_DIR` environment variable points (see `OUT_DIR` in `srt.py`).

This sets up the **⌘⇧Y** hotkey using macOS's built-in **Shortcuts** app - no
extra software to install.

## Prerequisites

- Python 3.10+
- [`yt-dlp`](https://github.com/yt-dlp/yt-dlp) and `ffmpeg` on your PATH
  (`brew install yt-dlp ffmpeg` on macOS)

## One-time setup (2 minutes)

1. Open the **Shortcuts** app (⌘-Space, type "Shortcuts").
2. Click **+** (top toolbar) to create a new shortcut. Name it
   **YouTube Transcript** (double-click the name at the top).
3. In the right-hand search box, find **Ask for Input** and double-click it to
   add it. Set:
   - Input type: **Text**
   - Prompt: `Paste a YouTube link`
4. Search for **Run Shell Script** and double-click to add it (it goes below
   "Ask for Input"). Set:
   - Shell: **zsh**
   - Pass Input: **to stdin**
   - In the script box, paste (adjust the path to wherever you cloned this repo):
     ```
     /opt/homebrew/bin/python3 /path/to/yt-research-toolkit/yt_to_txt.py "$(cat)"
     ```
5. Open the shortcut's **Details** panel (the ⓘ / sidebar toggle, top-right) →
   click **Add Keyboard Shortcut** → press **⌘⇧Y**.
6. First run only: macOS will ask permission for the shortcut to run a shell
   script / send notifications - click **Allow**.

## Use it

Press **⌘⇧Y** anywhere → a box appears → paste the link → press Return.
A notification shows "Downloading…" then "Saved: …", and Finder reveals the
finished `.txt` in your transcripts folder.

## Notes

- Running the script directly also works and shows its own paste box:
  `python3 yt_to_txt.py`  - or pass a URL:  `python3 yt_to_txt.py <url>`
- Output is byte-for-byte the same format as `srt.py`'s `.clean.srt`, just `.txt`.
- To stop Finder popping up each time, delete the `open -R` line near the
  bottom of `yt_to_txt.py`.
