from __future__ import annotations

from dataclasses import dataclass, field

PRESET_BEST = "best"
PRESET_AUDIO_MP3 = "audio_mp3"
PRESET_1080P = "1080p"
PRESET_720P = "720p"
PRESET_480P = "480p"
PRESET_CUSTOM = "custom"

# Order here is the order presets appear in the UI combo box.
PRESET_LABELS = [
    (PRESET_BEST, "Best quality"),
    (PRESET_AUDIO_MP3, "Audio only (MP3)"),
    (PRESET_1080P, "1080p max"),
    (PRESET_720P, "720p max"),
    (PRESET_480P, "480p max"),
    (PRESET_CUSTOM, "Custom format string…"),
]

_RESOLUTION_PRESETS = {
    PRESET_1080P: 1080,
    PRESET_720P: 720,
    PRESET_480P: 480,
}


@dataclass
class FormatSpec:
    format_selector: str
    postprocessors: list[dict] = field(default_factory=list)
    merge_output_format: str | None = None


def resolve_format(preset: str, custom_format: str = "") -> FormatSpec:
    if preset == PRESET_BEST:
        return FormatSpec("bv*+ba/b", merge_output_format="mp4")

    if preset == PRESET_AUDIO_MP3:
        return FormatSpec(
            "bestaudio/best",
            postprocessors=[
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }
            ],
        )

    if preset in _RESOLUTION_PRESETS:
        height = _RESOLUTION_PRESETS[preset]
        return FormatSpec(
            f"bv*[height<={height}]+ba/b[height<={height}]",
            merge_output_format="mp4",
        )

    if preset == PRESET_CUSTOM:
        return FormatSpec(custom_format.strip() or "best")

    raise ValueError(f"Unknown format preset: {preset}")
