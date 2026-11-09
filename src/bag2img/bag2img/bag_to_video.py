"""Convert a ROS 2 image topic into a constant-frame-rate video."""

from __future__ import annotations

import argparse
import math
from pathlib import Path
from typing import Optional, Sequence, Tuple

import cv2
import numpy as np
import rosbag2_py
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message

from .bag_exporter import _message_to_numpy, _select_topic, _topic_types


def _video_frame(image: np.ndarray) -> np.ndarray:
    if image.dtype == np.uint16:
        image = (image // 256).astype(np.uint8)
    if image.dtype != np.uint8:
        raise ValueError(f"Unsupported video image dtype: {image.dtype}")
    if image.ndim == 2:
        return cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    if image.ndim == 3 and image.shape[2] == 4:
        return cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)
    if image.ndim == 3 and image.shape[2] == 3:
        return image
    raise ValueError(f"Unsupported video image shape: {image.shape}")


def convert_bag_to_video(
    bag_path: Path,
    output_video: Path,
    topic: Optional[str] = None,
    fps: Optional[float] = None,
    codec: str = "mp4v",
    storage_id: str = "",
) -> Tuple[int, float, str]:
    """Return ``(frame_count, fps, selected_topic)`` after writing all frames.

    When FPS is omitted, use the average rate of bag record timestamps, or
    30 FPS for a single frame. Each message becomes exactly one video frame;
    irregular timestamp gaps are not reproduced individually.
    """
    if fps is not None and (not math.isfinite(fps) or fps <= 0):
        raise ValueError("fps must be finite and greater than zero.")
    if len(codec) != 4 or not codec.isascii():
        raise ValueError("codec must contain exactly four ASCII characters.")
    bag_path = bag_path.expanduser().resolve()
    output_video = output_video.expanduser().resolve()
    if not bag_path.exists():
        raise FileNotFoundError(f"Bag path does not exist: {bag_path}")
    if output_video.exists():
        raise FileExistsError(f"Output video already exists: {output_video}")

    reader = rosbag2_py.SequentialReader()
    reader.open(
        rosbag2_py.StorageOptions(uri=str(bag_path), storage_id=storage_id),
        rosbag2_py.ConverterOptions(
            input_serialization_format="cdr", output_serialization_format="cdr"
        ),
    )
    selected_topic, type_name = _select_topic(_topic_types(reader), topic)
    reader.set_filter(rosbag2_py.StorageFilter(topics=[selected_topic]))
    if fps is None:
        first_timestamp = last_timestamp = None
        count = 0
        while reader.has_next():
            _, _, timestamp = reader.read_next()
            if first_timestamp is None:
                first_timestamp = timestamp
            last_timestamp = timestamp
            count += 1
        if count == 0:
            raise ValueError(f"Topic '{selected_topic}' contains no image messages.")
        if count == 1:
            fps = 30.0
        elif last_timestamp <= first_timestamp:
            raise ValueError("Cannot infer FPS from timestamps. Specify --fps.")
        else:
            fps = (count - 1) * 1_000_000_000 / (last_timestamp - first_timestamp)
        reader.seek(first_timestamp)

    message_class = get_message(type_name)
    writer = None
    frame_size = None
    frame_count = 0
    try:
        while reader.has_next():
            _, serialized, _ = reader.read_next()
            image = _video_frame(
                _message_to_numpy(deserialize_message(serialized, message_class))
            )
            height, width = image.shape[:2]
            if writer is None:
                frame_size = (width, height)
                output_video.parent.mkdir(parents=True, exist_ok=True)
                writer = cv2.VideoWriter(
                    str(output_video), cv2.VideoWriter_fourcc(*codec), fps,
                    (width + width % 2, height + height % 2),
                )
                if not writer.isOpened():
                    raise ValueError(
                        f"OpenCV could not open video output: {output_video} "
                        f"(codec: {codec})"
                    )
            elif frame_size != (width, height):
                raise ValueError("Image dimensions changed within the selected topic.")
            # Many codecs truncate odd dimensions; pad the right/bottom instead.
            if width % 2 or height % 2:
                image = cv2.copyMakeBorder(
                    image, 0, height % 2, 0, width % 2, cv2.BORDER_CONSTANT
                )
            writer.write(image)
            frame_count += 1
        if frame_count == 0:
            raise ValueError(f"Topic '{selected_topic}' contains no image messages.")
    except BaseException:
        if writer is not None:
            writer.release()
            output_video.unlink(missing_ok=True)
        raise
    finally:
        if writer is not None:
            writer.release()

    return frame_count, fps, selected_topic


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Convert a ROS 2 image topic to video.")
    parser.add_argument("--bag", required=True, type=Path, help="Rosbag2 directory or file")
    parser.add_argument("--topic", help="Image topic; auto-selected when the bag has one")
    parser.add_argument(
        "--output-video", "--video", dest="output_video", type=Path,
        help="Output video path (default: <bag_name>.mp4 beside the bag)",
    )
    parser.add_argument("--fps", type=float, help="Output FPS (default: average bag rate)")
    parser.add_argument("--codec", default="mp4v", help="FourCC codec (default: mp4v)")
    parser.add_argument("--storage-id", default="", help="Storage plugin (default: auto)")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    bag_path = args.bag.expanduser().resolve()
    output_video = args.output_video or bag_path.parent / f"{bag_path.stem}.mp4"
    try:
        count, fps, selected_topic = convert_bag_to_video(
            bag_path, output_video, args.topic, args.fps, args.codec, args.storage_id
        )
    except (OSError, RuntimeError, TypeError, ValueError, cv2.error) as exc:
        parser.error(str(exc))
    print(
        f"Wrote {count} frames at {fps:g} FPS from {selected_topic} "
        f"to {output_video.expanduser().resolve()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
