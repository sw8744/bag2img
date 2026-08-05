"""Export image messages from a ROS 2 bag at a fixed time interval."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict, Optional, Sequence, Tuple

import cv2
import numpy as np
import rosbag2_py
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message
from sensor_msgs.msg import CompressedImage, Image


SUPPORTED_TYPES = {
    "sensor_msgs/msg/Image",
    "sensor_msgs/msg/CompressedImage",
}


def _topic_types(reader: rosbag2_py.SequentialReader) -> Dict[str, str]:
    return {item.name: item.type for item in reader.get_all_topics_and_types()}


def _select_topic(topic_types: Dict[str, str], requested: Optional[str]) -> Tuple[str, str]:
    image_topics = {
        name: type_name
        for name, type_name in topic_types.items()
        if type_name in SUPPORTED_TYPES
    }

    if requested:
        if requested not in topic_types:
            available = ", ".join(sorted(topic_types)) or "(none)"
            raise ValueError(
                f"Topic '{requested}' is not in the bag. Available topics: {available}"
            )
        type_name = topic_types[requested]
        if type_name not in SUPPORTED_TYPES:
            raise ValueError(
                f"Topic '{requested}' has unsupported type '{type_name}'. "
                f"Supported types: {', '.join(sorted(SUPPORTED_TYPES))}"
            )
        return requested, type_name

    if not image_topics:
        raise ValueError("The bag contains no sensor_msgs Image or CompressedImage topic.")
    if len(image_topics) > 1:
        choices = ", ".join(
            f"{name} ({type_name})" for name, type_name in sorted(image_topics.items())
        )
        raise ValueError(
            "The bag contains multiple image topics. Select one with --topic: " + choices
        )
    return next(iter(image_topics.items()))


def _raw_image_to_numpy(message: Image) -> np.ndarray:
    encodings = {
        "bgr8": (np.uint8, 3),
        "rgb8": (np.uint8, 3),
        "bgra8": (np.uint8, 4),
        "rgba8": (np.uint8, 4),
        "mono8": (np.uint8, 1),
        "mono16": (np.uint16, 1),
        "16UC1": (np.uint16, 1),
    }
    if message.encoding not in encodings:
        raise ValueError(
            f"Unsupported raw image encoding '{message.encoding}'. "
            f"Supported encodings: {', '.join(encodings)}"
        )

    dtype, channels = encodings[message.encoding]
    item_size = np.dtype(dtype).itemsize
    row_elements = message.step // item_size
    expected_elements = row_elements * message.height
    data = np.frombuffer(message.data, dtype=dtype, count=expected_elements)
    if data.size != expected_elements:
        raise ValueError("Raw image data is shorter than height * step.")

    rows = data.reshape(message.height, row_elements)
    used_elements = message.width * channels
    if used_elements > row_elements:
        raise ValueError("Raw image step is smaller than width * channel size.")
    image = rows[:, :used_elements]
    if channels > 1:
        image = image.reshape(message.height, message.width, channels)
    else:
        image = image.reshape(message.height, message.width)

    if item_size > 1 and bool(message.is_bigendian) != (np.little_endian is False):
        image = image.byteswap().newbyteorder()

    conversions = {
        "rgb8": cv2.COLOR_RGB2BGR,
        "rgba8": cv2.COLOR_RGBA2BGRA,
    }
    if message.encoding in conversions:
        image = cv2.cvtColor(image, conversions[message.encoding])
    return image


def _message_to_numpy(message: object) -> np.ndarray:
    if isinstance(message, CompressedImage):
        encoded = np.frombuffer(message.data, dtype=np.uint8)
        image = cv2.imdecode(encoded, cv2.IMREAD_UNCHANGED)
        if image is None:
            raise ValueError("OpenCV could not decode the compressed image message.")
        return image
    if isinstance(message, Image):
        return _raw_image_to_numpy(message)
    raise TypeError(f"Unsupported message class: {type(message).__name__}")


def export_images(
    bag_path: Path,
    output_dir: Path,
    interval_seconds: float,
    topic: Optional[str] = None,
    image_format: str = "jpg",
    jpeg_quality: int = 95,
    prefix: str = "frame",
) -> Tuple[int, str]:
    """Export frames and return ``(saved_count, selected_topic)``."""
    if interval_seconds <= 0:
        raise ValueError("interval_seconds must be greater than zero.")
    if image_format not in {"jpg", "png"}:
        raise ValueError("image_format must be 'jpg' or 'png'.")
    if not 0 <= jpeg_quality <= 100:
        raise ValueError("jpeg_quality must be between 0 and 100.")

    bag_path = bag_path.expanduser().resolve()
    if not bag_path.exists():
        raise FileNotFoundError(f"Bag path does not exist: {bag_path}")

    reader = rosbag2_py.SequentialReader()
    reader.open(
        rosbag2_py.StorageOptions(uri=str(bag_path), storage_id="sqlite3"),
        rosbag2_py.ConverterOptions(
            input_serialization_format="cdr", output_serialization_format="cdr"
        ),
    )
    selected_topic, type_name = _select_topic(_topic_types(reader), topic)
    reader.set_filter(rosbag2_py.StorageFilter(topics=[selected_topic]))

    output_dir = output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    message_class = get_message(type_name)
    interval_ns = round(interval_seconds * 1_000_000_000)
    next_timestamp: Optional[int] = None
    saved_count = 0

    while reader.has_next():
        _, serialized, timestamp = reader.read_next()
        if next_timestamp is not None and timestamp < next_timestamp:
            continue

        message = deserialize_message(serialized, message_class)
        image = _message_to_numpy(message)
        filename = output_dir / f"{prefix}_{saved_count:06d}_{timestamp}.{image_format}"
        params = (
            [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality]
            if image_format == "jpg"
            else []
        )
        if not cv2.imwrite(str(filename), image, params):
            raise OSError(f"Failed to write image: {filename}")

        saved_count += 1
        if next_timestamp is None:
            next_timestamp = timestamp + interval_ns
        else:
            missed_intervals = max(1, (timestamp - next_timestamp) // interval_ns + 1)
            next_timestamp += missed_intervals * interval_ns

    return saved_count, selected_topic


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Export camera frames from a ROS 2 bag at a fixed interval."
    )
    parser.add_argument(
        "--bag", required=True, type=Path, help="Rosbag2 directory or .db3 file path"
    )
    parser.add_argument(
        "--interval",
        required=True,
        type=float,
        help="Time between exported frames in seconds (for example: 0.5)",
    )
    parser.add_argument("--topic", help="Image topic; auto-selected when the bag has one")
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Output directory (default: <bag>/images_<interval>s)",
    )
    parser.add_argument("--format", choices=("jpg", "png"), default="jpg")
    parser.add_argument("--jpeg-quality", type=int, default=95)
    parser.add_argument("--prefix", default="frame")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    default_parent = args.bag.parent if args.bag.suffix == ".db3" else args.bag
    output_dir = args.output_dir or default_parent / f"images_{args.interval:g}s"
    try:
        count, selected_topic = export_images(
            bag_path=args.bag,
            output_dir=output_dir,
            interval_seconds=args.interval,
            topic=args.topic,
            image_format=args.format,
            jpeg_quality=args.jpeg_quality,
            prefix=args.prefix,
        )
    except (FileNotFoundError, OSError, RuntimeError, TypeError, ValueError) as exc:
        parser.error(str(exc))

    print(f"Saved {count} images from {selected_topic} to {output_dir.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
