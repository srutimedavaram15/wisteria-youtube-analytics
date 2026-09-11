"""
Utilities for working with local video files before upload.
"""

import json
import math
import subprocess
import sys
from pathlib import Path


def get_video_duration_seconds(file_path: str) -> int:
    """
    Returns the duration of a video file in whole seconds using ffprobe.

    Raises FileNotFoundError if the file does not exist.
    Raises ValueError if ffprobe cannot read the file or duration is missing.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Video file not found: {file_path}")

    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                str(path),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        raise ValueError(
            f"ffprobe could not read '{file_path}' — is it a valid video file?\n"
            f"ffprobe stderr: {e.stderr.strip()}"
        ) from e
    except FileNotFoundError:
        raise ValueError(
            "ffprobe not found. Install it via: brew install ffmpeg  (macOS) "
            "or apt install ffmpeg  (Linux)"
        )

    try:
        data = json.loads(result.stdout)
        duration_str = data["format"]["duration"]
    except (json.JSONDecodeError, KeyError) as e:
        raise ValueError(
            f"ffprobe output did not contain a duration for '{file_path}'"
        ) from e

    return math.floor(float(duration_str))


def main() -> None:
    if len(sys.argv) != 2:
        print(f"Usage: python {sys.argv[0]} <video_file>", file=sys.stderr)
        sys.exit(1)

    file_path = sys.argv[1]
    try:
        duration = get_video_duration_seconds(file_path)
        print(f"{duration} seconds")
    except (FileNotFoundError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
