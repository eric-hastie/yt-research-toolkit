#!/usr/bin/env python3
"""
Build a clean YouTube transcript corpus for researching a person or topic.

Searches YouTube, filters out clip-farm / AI-narrated reuploads, downloads the
auto-generated English transcripts for the top N genuine sources, cleans them
(reusing srt.py's logic), and drops them in a per-topic folder with a manifest.

Usage:
    yt_research.py "Lyn Alden"                 # person: most-recent appearances
    yt_research.py "fiscal dominance" --mode topic   # idea: relevance, many voices
    yt_research.py "Lyn Alden" --n 20 --dry-run      # plan only, no downloads

Output:
    ~/youtube_subtitles/research/<slug>/     (override: $YT_TRANSCRIPTS_DIR or --out)
        00_MANIFEST.json          machine-readable selection + stats
        00_MANIFEST.txt           human-readable list
        YYYY-MM-DD__<Channel>__<id>.txt   one cleaned transcript per source

The script handles ONLY the deterministic pipeline (search -> filter -> select ->
download -> clean -> organize). Analysis and Q&A happen on top of the corpus --
I feed it to an AI assistant (Claude) and ask questions grounded in the sources.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import unicodedata
from datetime import datetime, timedelta
from pathlib import Path

os.environ["PATH"] = "/opt/homebrew/bin:" + os.environ.get("PATH", "")

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
# Reuse the existing, battle-tested cleaning logic so output matches the rest
# of the youtube_subtitles library exactly.
from srt import parse_srt, clean_blocks, write_srt, fetch_caption_srt  # noqa: E402

# Corpora are built under <transcripts dir>/research/<slug>/, kept separate
# from the code so research data never lands in version control. Override the
# base with the YT_TRANSCRIPTS_DIR environment variable, or use --out per run.
TRANSCRIPTS_DIR = Path(os.environ.get("YT_TRANSCRIPTS_DIR", "~/youtube_subtitles")).expanduser()
RESEARCH_ROOT = TRANSCRIPTS_DIR / "research"
BLOCKLIST_FILE = HERE / "junk_channels.txt"

# Seed list of channels that re-upload AI-narrated clips of real interviews
# rather than producing genuine ones. Matched case-insensitively as substrings.
# Grows over time -- add a line to junk_channels.txt and it's picked up here.
SEED_BLOCKLIST = [
    "Savvy Minds Connect", "LifeWorthLiving", "Savvy Finance", "EVERYDAY FINANCE",
    "Library Of Wealth", "Crypto Nutshell", "Money Talks", "FINANCE INSIDER",
    "Rock Star Real Estate", "Understanding Lyn Alden",
]


def load_blocklist() -> list[str]:
    blocked = [b.lower() for b in SEED_BLOCKLIST]
    if BLOCKLIST_FILE.exists():
        for line in BLOCKLIST_FILE.read_text(encoding="utf-8").splitlines():
            line = line.split("#", 1)[0].strip()
            if line:
                blocked.append(line.lower())
    return sorted(set(blocked))


def parse_timeframe(s: str) -> int:
    """Convert a human timeframe to a max age in days. 0 == no limit.
    Accepts: '1 week', '3 months', '12 months', '2 years', '36 months',
    'no limit', 'none', '0', or a bare number of days."""
    s = (s or "").strip().lower()
    if not s or s in ("no limit", "none", "unlimited", "0", "all"):
        return 0
    m = re.match(r"(\d+)\s*(day|week|month|year)s?", s)
    if m:
        n, unit = int(m.group(1)), m.group(2)
        return n * {"day": 1, "week": 7, "month": 30, "year": 365}[unit]
    if s.isdigit():           # bare number = days
        return int(s)
    return 0                  # unrecognized -> no limit (safest: don't over-filter)


def detect_mode(query: str) -> str:
    """Guess person vs topic for --mode auto. A short, Title-Cased phrase with
    no digits reads as a name; anything else is treated as a topic."""
    words = query.split()
    if 1 <= len(words) <= 3 and all(
        w[:1].isupper() and w[1:].islower() and w.isalpha() for w in words
    ):
        return "person"
    return "topic"


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^\w\s-]", "", text).strip().lower()
    return re.sub(r"[\s_-]+", "_", text) or "topic"


def safe_name(text: str, maxlen: int = 24) -> str:
    """Filesystem-safe channel fragment for filenames."""
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^\w\s-]", "", text).strip()
    text = re.sub(r"\s+", "_", text)
    return text[:maxlen] or "Unknown"


def search_ids(query: str, mode: str, candidates: int) -> list[str]:
    """Return candidate video IDs from a YouTube search.

    person -> sort by upload date (most recent first).
    topic  -> default relevance sort (surfaces the best sources across voices).
    """
    from urllib.parse import quote_plus
    base = f"https://www.youtube.com/results?search_query={quote_plus(query)}"
    if mode == "person":
        base += "&sp=CAI%253D"  # sort by upload date
    proc = subprocess.run(
        ["yt-dlp", "--flat-playlist", "--print", "%(id)s",
         "--playlist-end", str(candidates), base],
        capture_output=True, text=True,
    )
    ids = [l.strip() for l in proc.stdout.splitlines() if l.strip()]
    # De-dupe while preserving order.
    seen, out = set(), []
    for i in ids:
        if i not in seen:
            seen.add(i)
            out.append(i)
    return out


def fetch_metadata(ids: list[str]) -> list[dict]:
    """Full metadata per video via --dump-json (JSON, so no delimiter parsing
    bug -- this is what broke the pipe-delimited version: channel names contain
    '|'). Each video extracted individually; --ignore-errors skips dead ones."""
    urls = [f"https://www.youtube.com/watch?v={i}" for i in ids]
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as bf:
        bf.write("\n".join(urls))
        batch = bf.name
    proc = subprocess.run(
        ["yt-dlp", "--no-download", "--ignore-errors", "--dump-json",
         "--batch-file", batch],
        capture_output=True, text=True,
    )
    os.unlink(batch)
    rows = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        rows.append({
            "id": d.get("id"),
            "title": (d.get("title") or "").strip(),
            "channel": (d.get("channel") or d.get("uploader") or "").strip(),
            "upload_date": d.get("upload_date") or "",
            "duration": int(d.get("duration") or 0),
            "url": d.get("webpage_url") or f"https://www.youtube.com/watch?v={d.get('id')}",
        })
    return rows


def select(rows: list[dict], mode: str, n: int, min_seconds: int,
           since_days: int) -> list[dict]:
    blocked = load_blocklist()
    cutoff = ""
    if since_days > 0:
        cutoff = (datetime.now() - timedelta(days=since_days)).strftime("%Y%m%d")
    kept, seen_titles, dropped = [], set(), []
    for r in rows:
        reason = None
        if cutoff and r["upload_date"] and r["upload_date"] < cutoff:
            reason = f"older than window ({r['upload_date']})"
        elif r["duration"] and r["duration"] < min_seconds:
            reason = f"too short ({r['duration']//60}m)"
        elif any(b in r["channel"].lower() for b in blocked):
            reason = "blocklisted channel"
        else:
            key = re.sub(r"[^\w]", "", r["title"].lower())[:60]
            if key in seen_titles:
                reason = "duplicate title"
            else:
                seen_titles.add(key)
        if reason:
            dropped.append({**r, "drop_reason": reason})
        else:
            kept.append(r)
    # person -> newest first; topic -> keep relevance order from search.
    if mode == "person":
        kept.sort(key=lambda r: r["upload_date"], reverse=True)
    return kept[:n], dropped


def download_clean(row: dict, out_dir: Path) -> dict | None:
    """Download + clean one transcript. Returns the row with file/words on
    success, or None on failure -- a single failure never aborts the batch
    (the old version's sys.exit killed every remaining download)."""
    raw, status, _ = fetch_caption_srt(row["url"])
    if raw is None:
        print(f"      no transcript for {row['id']}: {status}", flush=True)
        return None
    blocks = clean_blocks(parse_srt(raw))
    if not blocks:
        return None
    date = row["upload_date"] or "0000-00-00"
    if re.fullmatch(r"\d{8}", date):
        date = f"{date[:4]}-{date[4:6]}-{date[6:]}"
    fname = f"{date}__{safe_name(row['channel'])}__{row['id']}.txt"
    out = out_dir / fname
    out.write_text(write_srt(blocks), encoding="utf-8")
    words = len(re.sub(r"\d+|-->|\d{2}:\d{2}:\d{2},\d+", " ", out.read_text()).split())
    return {**row, "file": fname, "date": date, "words": words}


def main() -> None:
    ap = argparse.ArgumentParser(description="Build a YouTube transcript research corpus.")
    ap.add_argument("query", help="a person's name or a topic/idea")
    ap.add_argument("--mode", choices=["auto", "person", "topic"], default="auto",
                    help="person=recent appearances; topic=relevance across voices")
    ap.add_argument("--n", type=int, default=25, help="number of transcripts to keep")
    ap.add_argument("--timeframe", default="6 months",
                    help="max age: '1 week', '6 months', '2 years', 'no limit', or N days")
    ap.add_argument("--candidates", type=int, default=0,
                    help="search results to vet (default: 3x --n, min 45)")
    ap.add_argument("--min-minutes", type=int, default=8, help="drop videos shorter than this")
    ap.add_argument("--slug", default=None, help="corpus folder name (default: from query)")
    ap.add_argument("--out", default=None,
                    help="output root (default: $YT_TRANSCRIPTS_DIR/research "
                         "or ~/youtube_subtitles/research)")
    ap.add_argument("--dry-run", action="store_true", help="plan/select only, no downloads")
    args = ap.parse_args()

    mode = detect_mode(args.query) if args.mode == "auto" else args.mode
    since_days = parse_timeframe(args.timeframe)
    candidates = args.candidates or max(45, args.n * 3)
    slug = args.slug or slugify(args.query)
    root = Path(args.out).expanduser() if args.out else RESEARCH_ROOT
    out_dir = root / slug
    out_dir.mkdir(parents=True, exist_ok=True)

    window = args.timeframe if since_days else "no limit"
    print(f"[1/4] searching YouTube for {args.query!r} "
          f"(mode={mode}, window={window})...", flush=True)
    ids = search_ids(args.query, mode, candidates)
    print(f"      {len(ids)} candidates", flush=True)

    print("[2/4] fetching real upload dates + durations...", flush=True)
    rows = fetch_metadata(ids)
    print(f"      {len(rows)} resolved", flush=True)

    print("[3/4] filtering junk + selecting...", flush=True)
    selected, dropped = select(rows, mode, args.n, args.min_minutes * 60, since_days)
    print(f"      kept {len(selected)}, dropped {len(dropped)}", flush=True)
    for r in selected:
        print(f"        {r['upload_date']:>8}  {r['duration']//60:>3}m  "
              f"{r['channel'][:22]:22}  {r['title'][:50]}")

    if args.dry_run:
        print("\n[dry-run] no transcripts downloaded.")
        return

    print(f"[4/4] downloading + cleaning {len(selected)} transcripts...", flush=True)
    done = []
    for i, r in enumerate(selected, 1):
        res = download_clean(r, out_dir)
        status = f"{res['words']:>6}w" if res else "  FAILED (no subs)"
        print(f"      {i:>2}/{len(selected)}  {status}  {r['title'][:55]}", flush=True)
        if res:
            done.append(res)

    manifest = {
        "query": args.query, "mode": mode, "slug": slug,
        "timeframe": window, "count": len(done), "requested": args.n,
        "total_words": sum(d["words"] for d in done),
        "date_range": [min((d["date"] for d in done), default=""),
                       max((d["date"] for d in done), default="")],
        "transcripts": done,
        "dropped": [{"title": d["title"], "channel": d["channel"],
                     "reason": d["drop_reason"]} for d in dropped],
    }
    (out_dir / "00_MANIFEST.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    lines = [f"# {args.query}  ({mode})  -- {len(done)} transcripts, "
             f"{manifest['total_words']:,} words, "
             f"{manifest['date_range'][0]} -> {manifest['date_range'][1]}", ""]
    for d in sorted(done, key=lambda x: x["date"], reverse=True):
        lines.append(f"{d['date']}  {d['words']:>6}w  {d['channel'][:22]:22}  {d['title']}")
        lines.append(f"            {d['url']}  ->  {d['file']}")
    (out_dir / "00_MANIFEST.txt").write_text("\n".join(lines), encoding="utf-8")

    print(f"\nDone. {len(done)} transcripts in {out_dir}")
    print(f"Manifest: {out_dir / '00_MANIFEST.txt'}")


if __name__ == "__main__":
    main()
