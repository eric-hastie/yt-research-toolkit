# YouTube Research Toolkit

**One command turns "what is this person, company, or market actually saying?" into a clean, dated, citable library of transcripts - pulled straight from the primary sources.**

I'm a sales professional, not an engineer. I built this because the way most of
us research a prospect, an executive, or a market is backwards: we read
summaries of summaries - news articles, LinkedIn hot takes, analyst recaps -
and hope nothing important got lost in translation. Meanwhile, the executives
and experts we're trying to understand are on YouTube every week saying exactly
what they think, in their own words, on podcasts and conference stages and
earnings interviews.

The problem was never access. It was volume and noise. Nobody has time to watch
25 hour-long interviews before a discovery call (I've tried; it doesn't scale),
and YouTube search results are increasingly polluted with clip farms and
AI-narrated re-uploads that *look* like primary sources but aren't.

So I built a pipeline that does the grunt work: search, filter out the fakes,
grab the transcripts, clean them, and file them with receipts. Then I read - or
have an AI assistant read with me - and walk into the call knowing what the
person actually said, not what someone said they said.

## Account intelligence: the sales use case

This started as a research tool, but the highest-value use I've found is
generating **account intelligence that isn't published anywhere else** - and
putting it to work in deals, whether that's prospecting and outbound or
meeting prep.

Founders and executives have a habit of discussing the topics that matter
most - the future of the company, where priorities are shifting - on podcasts
and conference stages that end up on YouTube. Often that's detail you won't
find in a press release, an earnings deck, or a LinkedIn post. It gets said
once, on camera, and then buried under an hour of small talk and a thousand
other videos.

That kind of intelligence is extremely useful in a deal: it tells you what an
account's leadership actually cares about *right now*, in their own words. The
problem has always been scale - nobody can spend hours sifting through YouTube
videos hunting for the golden nuggets before every call. This tool collects
that intelligence at scale: one command pulls an executive's recent appearances
into a clean, dated corpus I can read (or interrogate with an AI assistant) in
minutes. The sifting becomes the machine's job; the selling stays mine.

## How it works (and why each step exists)

Run one command:

```
python3 yt_research.py "Lyn Alden"
```

Five things happen:

**1. Search - tuned to what you're researching.**
A person and a topic need different searches. For a *person* ("Lyn Alden"),
you want their most recent appearances - what they're saying *now*. For a
*topic* ("fiscal dominance"), you want the most relevant sources across many
voices. The script detects which kind of query you gave it (or you tell it with
`--mode`) and sorts accordingly. It deliberately over-collects - roughly 3x the
number of transcripts you asked for - because the next step throws a lot away.

**2. Filter out the junk - the step that makes the rest worth doing.**
This is the part I care about most. YouTube is full of channels that take a
real interview, run it through an AI voice, slap a thumbnail on it, and
re-upload it. If those land in your research pile, you're quoting a robot's
paraphrase back to a prospect (not a great look). The script keeps a
**blocklist of known junk channels** (`junk_channels.txt`) that grows with use:
every research run surfaces a new offender or two, I add a line, and every
future run is cleaner. It also drops videos that are too short to be
substantive (clips, shorts) and near-duplicate titles (the same interview
re-uploaded five times).

**3. Verify the metadata.** "3 days ago" on a search page isn't a date you can
cite. The script pulls each video's real upload date, channel, and duration, so
selection decisions are made on facts.

**4. Download and clean the transcripts.** YouTube's auto-captions arrive as
subtitle files full of duplicated, overlapping lines. A shared cleaning engine
(`srt.py`) collapses them into readable text with timestamps preserved - so you
can jump to the moment in the video where a quote came from. One failed
download never kills the batch; it's logged and the run continues.

**5. Write a manifest - because research you can't cite is just vibes.**
Every corpus gets a manifest listing each source: date, channel, title, URL,
word count - plus every video that was *rejected* and why ("blocklisted
channel", "too short", "duplicate title"). If I quote something in a follow-up
email or an interview, I can point to exactly where it came from. The rejected
list also keeps the filter honest: I can audit what got dropped.

The output is a tidy folder per research target:

```
research/lyn_alden/
    00_MANIFEST.txt      human-readable source list
    00_MANIFEST.json     the same, machine-readable
    2026-06-28__Forward_Guidance__abc123.txt
    2026-06-21__Blockworks_Macro__def456.txt
    ...
```

## A realistic workflow: account intelligence before a call

Say I have a discovery call next week with a company whose CEO does the podcast
circuit:

1. `python3 yt_research.py "Jane Doe Acme CEO" --timeframe "12 months"` -
   pull her last year of interviews.
2. `python3 yt_research.py "supply chain visibility software" --mode topic` -
   pull the market conversation her company lives in.
3. Skim the manifests, then feed the corpus to an AI assistant and interrogate
   it: *What does she keep repeating? What changed between the January and June
   interviews? What priorities does she describe that never made it into a
   press release? What does she say about the problem my product solves? What
   questions do interviewers ask that she deflects?*
4. Walk into the call with her own words - dated and linked - instead of a
   rehashed news summary.

The same intelligence works upstream of the call, too: a cold email that opens
with something an executive said on a podcast last month - something you can't
find on the company's About page - earns a reply that a generic one doesn't.

And the same loop covers interview prep (research the hiring company's
leadership), competitive intel, and market research. The tool doesn't care what
you're researching; it just guarantees the inputs are genuine and organized.

## Bonus: the one-video hotkey

Sometimes you don't need a corpus - someone sends you *one* video worth reading
instead of watching. `yt_to_txt.py` wires a macOS keyboard shortcut (⌘⇧Y) to a
paste box: copy a YouTube link anywhere, hit the hotkey, press Return, and a
cleaned transcript lands in your transcripts folder. Setup instructions are in
[SETUP.md](SETUP.md).

## What's in this repo

| File | What it does |
|---|---|
| `yt_research.py` | The pipeline: search → filter → select → download → clean → manifest |
| `srt.py` | Shared transcript-cleaning engine; also works standalone on one URL or file |
| `yt_to_txt.py` | One-shot transcript grab, built for a macOS Shortcuts hotkey |
| `junk_channels.txt` | The growing blocklist of clip-farm / AI-reupload channels |
| `SETUP.md` | 2-minute setup for the ⌘⇧Y hotkey |

## Setup

- Python 3.10+ and [`yt-dlp`](https://github.com/yt-dlp/yt-dlp) + `ffmpeg` on
  your PATH (`brew install yt-dlp ffmpeg` on macOS). No Python packages to
  install - standard library only.
- Transcripts are written to `~/youtube_subtitles` by default, kept outside the
  repo on purpose (research data doesn't belong in version control). Point them
  elsewhere with the `YT_TRANSCRIPTS_DIR` environment variable or the `--out`
  flag on `yt_research.py`.

```
python3 yt_research.py "Lyn Alden"                    # a person: recent appearances
python3 yt_research.py "fiscal dominance" --mode topic # an idea: many voices
python3 yt_research.py "Lyn Alden" --n 20 --dry-run    # see the plan, download nothing
```

`--dry-run` is worth calling out: it runs the whole search-and-filter pass and
shows you exactly what it *would* download and what it rejected, before you
spend any bandwidth. I use it to sanity-check a new query in ten seconds.

## Honest scope notes

- **English auto-captions only.** Auto-generated captions are imperfect - good
  enough to know what was said, not good enough to quote verbatim without
  checking the timestamped moment in the video (which the manifest links make
  a 10-second job).
- **The junk filter is a blocklist, not an oracle.** New clip farms appear
  faster than any list grows. The design accepts that: the manifest's rejected
  list makes misses visible, and fixing one is a one-line edit.
- **The hotkey tool is macOS-only** (it uses Shortcuts and AppleScript
  dialogs). The main pipeline is plain Python and should run anywhere `yt-dlp`
  does.
- **It respects the boundary between pipeline and judgment.** The script does
  the deterministic work; the analysis - what the sources *mean* - is done by a
  human, with an AI assistant as a reading partner. I think that division of
  labor is the right one, so it's a design decision, not a limitation.

## How this was built

Built with Python and AI pair-programming tools. I described the problems as I
hit them ("search results are full of AI re-uploads", "a channel name with a
`|` in it just broke the parser", "one dead video killed the whole batch") and
we iterated on the design together. The judgment calls (what counts as junk,
why manifests matter, where the pipeline should stop and the human should
start) are mine; a lot of the actual Python isn't - and I'm completely at peace
with that 🙂
