# YTGrab

A desktop download manager built on top of [yt-dlp](https://github.com/yt-dlp/yt-dlp),
with a queue-based Qt GUI.

## Features

- Paste a video or playlist URL and add it to a download queue; playlists
  expand into one queue item per video.
- Format presets: best quality, audio-only (MP3), capped resolution
  (1080p/720p/480p), or a custom yt-dlp format string.
- Queue table showing title, status, progress, speed, and ETA per item.
- Configurable number of parallel downloads.
- Cancel an individual download without affecting the rest of the queue.
- Choose the output folder.
- "Fetch available formats" to see the real formats yt-dlp reports for a URL.
- The queue is saved to disk and restored (including resuming unfinished
  items) the next time you launch YTGrab.

## Setup

Requires Python 3.9+.

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### ffmpeg

YTGrab shells out to `ffmpeg` (via yt-dlp) to merge separate video/audio
streams and to extract MP3 audio. It must be on your `PATH`; YTGrab detects
and warns in the UI if it isn't found, but it will still let you download
formats that don't need merging or conversion.

- **Windows**: `scoop install ffmpeg` or `choco install ffmpeg`, or download a
  build from [gyan.dev](https://www.gyan.dev/ffmpeg/builds/) and add it to `PATH`.
- **macOS**: `brew install ffmpeg`
- **Linux**: `sudo apt install ffmpeg` (Debian/Ubuntu) or the equivalent for
  your distribution.

## Running

```bash
python main.py
```

## Keeping yt-dlp up to date

Sites that yt-dlp supports change frequently, which can break extraction.
Update it regularly:

```bash
pip install -U yt-dlp
```

## Packaging with PyInstaller

To build a standalone executable:

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name YTGrab main.py
```

The built executable will be in `dist/`. Notes:

- PyInstaller does not bundle `ffmpeg` — ship it alongside the executable (or
  document that users must install it) if you plan to distribute the build.
- Test the packaged executable directly; if an extractor plugin fails to load,
  add it explicitly with `--hidden-import yt_dlp.extractor.<name>` or
  `--collect-submodules yt_dlp.extractor`.
- `build/`, `dist/`, and `*.spec` are gitignored — re-run PyInstaller to
  regenerate them rather than committing the output.

## Responsible use

YTGrab is a general-purpose tool for downloading media you have the rights to
download (your own content, content licensed for download, public domain
media, etc.). Respect copyright law and the terms of service of any site you
use it with.
