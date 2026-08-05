"""Export frames from a video file at a fixed time interval."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional, Sequence

import cv2


def export_video_images(
    video_path: Path,
    output_dir: Path,
    interval_seconds: float,
    image_format: str = "jpg",
    jpeg_quality: int = 95,
    prefix: str = "frame",
) -> int:
    """Export video frames and return the number of saved images."""
    if interval_seconds <= 0:
        raise ValueError("interval_seconds must be greater than zero.")
    if image_format not in {"jpg", "png"}:
        raise ValueError("image_format must be 'jpg' or 'png'.")
    if not 0 <= jpeg_quality <= 100:
        raise ValueError("jpeg_quality must be between 0 and 100.")

    video_path = video_path.expanduser().resolve()
    if not video_path.is_file():
        raise FileNotFoundError(f"Video file does not exist: {video_path}")

    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise ValueError(f"OpenCV could not open the video: {video_path}")

    fps = capture.get(cv2.CAP_PROP_FPS)
    if fps <= 0:
        capture.release()
        raise ValueError("The video does not contain a valid frame rate.")

    output_dir = output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    interval_ns = round(interval_seconds * 1_000_000_000)
    next_timestamp_ns = 0
    frame_index = 0
    saved_count = 0
    params = (
        [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality]
        if image_format == "jpg"
        else []
    )

    try:
        while True:
            success, frame = capture.read()
            if not success:
                break

            timestamp_ns = round(frame_index / fps * 1_000_000_000)
            frame_index += 1
            if timestamp_ns < next_timestamp_ns:
                continue

            filename = output_dir / (
                f"{prefix}_{saved_count:06d}_{timestamp_ns}.{image_format}"
            )
            if not cv2.imwrite(str(filename), frame, params):
                raise OSError(f"Failed to write image: {filename}")

            saved_count += 1
            missed_intervals = max(
                1, (timestamp_ns - next_timestamp_ns) // interval_ns + 1
            )
            next_timestamp_ns += missed_intervals * interval_ns
    finally:
        capture.release()

    return saved_count


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Export video frames at a fixed time interval."
    )
    parser.add_argument("--video", required=True, type=Path, help="Input video path")
    parser.add_argument(
        "--interval",
        required=True,
        type=float,
        help="Time between exported frames in seconds (for example: 0.5)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Output directory (default: <video_name>_images_<interval>s)",
    )
    parser.add_argument("--format", choices=("jpg", "png"), default="jpg")
    parser.add_argument("--jpeg-quality", type=int, default=95)
    parser.add_argument("--prefix", default="frame")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    output_dir = args.output_dir or args.video.parent / (
        f"{args.video.stem}_images_{args.interval:g}s"
    )
    try:
        count = export_video_images(
            video_path=args.video,
            output_dir=output_dir,
            interval_seconds=args.interval,
            image_format=args.format,
            jpeg_quality=args.jpeg_quality,
            prefix=args.prefix,
        )
    except (FileNotFoundError, OSError, ValueError) as exc:
        parser.error(str(exc))

    print(f"Saved {count} images from {args.video.resolve()} to {output_dir.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
