"""Convert a video file into a ROS 2 bag containing image messages."""

from __future__ import annotations

import argparse
import time
from pathlib import Path
from typing import Optional, Sequence, Tuple

import cv2
import rosbag2_py
from rclpy.serialization import serialize_message
from sensor_msgs.msg import CompressedImage, Image


IMAGE_TYPE = "sensor_msgs/msg/Image"
COMPRESSED_IMAGE_TYPE = "sensor_msgs/msg/CompressedImage"
NANOSECONDS_PER_SECOND = 1_000_000_000


def _image_message(frame: object, timestamp_ns: int, frame_id: str) -> Image:
    """Build a ``bgr8`` Image message from an OpenCV frame."""
    if frame.ndim != 3 or frame.shape[2] != 3:
        raise ValueError("Decoded video frame is not a three-channel BGR image.")

    contiguous_frame = frame if frame.flags.c_contiguous else frame.copy()
    height, width = contiguous_frame.shape[:2]
    message = Image()
    message.header.stamp.sec = timestamp_ns // NANOSECONDS_PER_SECOND
    message.header.stamp.nanosec = timestamp_ns % NANOSECONDS_PER_SECOND
    message.header.frame_id = frame_id
    message.height = height
    message.width = width
    message.encoding = "bgr8"
    message.is_bigendian = False
    message.step = width * 3
    message.data = contiguous_frame.tobytes()
    return message


def _compressed_image_message(
    frame: object,
    timestamp_ns: int,
    frame_id: str,
    jpeg_quality: int,
) -> CompressedImage:
    """Build a JPEG-compressed image message from an OpenCV frame."""
    success, encoded = cv2.imencode(
        ".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality]
    )
    if not success:
        raise ValueError("OpenCV could not encode a video frame as JPEG.")

    message = CompressedImage()
    message.header.stamp.sec = timestamp_ns // NANOSECONDS_PER_SECOND
    message.header.stamp.nanosec = timestamp_ns % NANOSECONDS_PER_SECOND
    message.header.frame_id = frame_id
    message.format = "jpeg"
    message.data = encoded.tobytes()
    return message


def convert_video_to_bag(
    video_path: Path,
    output_bag: Path,
    topic: str = "/camera/image_raw",
    compressed_topic: Optional[str] = None,
    frame_id: str = "camera",
    jpeg_quality: int = 95,
    start_time_ns: Optional[int] = None,
    storage_id: str = "sqlite3",
) -> Tuple[int, float]:
    """Write all video frames and return ``(frame_count, fps)``.

    Bag and header timestamps start at ``start_time_ns`` and advance according
    to the video's frame rate. When it is omitted, the conversion start time is
    used.
    """
    video_path = video_path.expanduser().resolve()
    if not video_path.is_file():
        raise FileNotFoundError(f"Video file does not exist: {video_path}")
    if not topic.strip():
        raise ValueError("topic must not be empty.")
    compressed_topic = compressed_topic or f"{topic.rstrip('/')}/compressed"
    if not compressed_topic.strip():
        raise ValueError("compressed_topic must not be empty.")
    if topic == compressed_topic:
        raise ValueError("topic and compressed_topic must be different.")
    if not 0 <= jpeg_quality <= 100:
        raise ValueError("jpeg_quality must be between 0 and 100.")
    if start_time_ns is not None and start_time_ns < 0:
        raise ValueError("start_time_ns must be zero or greater.")

    output_bag = output_bag.expanduser().resolve()
    if output_bag.exists():
        raise FileExistsError(
            f"Output bag path already exists: {output_bag}. "
            "Choose a new path or remove it first."
        )
    output_bag.parent.mkdir(parents=True, exist_ok=True)

    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise ValueError(f"OpenCV could not open the video: {video_path}")

    fps = capture.get(cv2.CAP_PROP_FPS)
    if fps <= 0:
        capture.release()
        raise ValueError("The video does not contain a valid frame rate.")

    first_timestamp_ns = time.time_ns() if start_time_ns is None else start_time_ns
    writer = rosbag2_py.SequentialWriter()
    try:
        writer.open(
            rosbag2_py.StorageOptions(uri=str(output_bag), storage_id=storage_id),
            rosbag2_py.ConverterOptions(
                input_serialization_format="cdr",
                output_serialization_format="cdr",
            ),
        )
        writer.create_topic(
            rosbag2_py.TopicMetadata(
                name=topic,
                type=IMAGE_TYPE,
                serialization_format="cdr",
            )
        )
        writer.create_topic(
            rosbag2_py.TopicMetadata(
                name=compressed_topic,
                type=COMPRESSED_IMAGE_TYPE,
                serialization_format="cdr",
            )
        )

        frame_index = 0
        while True:
            success, frame = capture.read()
            if not success:
                break

            timestamp_ns = first_timestamp_ns + round(
                frame_index * NANOSECONDS_PER_SECOND / fps
            )
            message = _image_message(frame, timestamp_ns, frame_id)
            writer.write(topic, serialize_message(message), timestamp_ns)
            compressed_message = _compressed_image_message(
                frame, timestamp_ns, frame_id, jpeg_quality
            )
            writer.write(
                compressed_topic,
                serialize_message(compressed_message),
                timestamp_ns,
            )
            frame_index += 1
    finally:
        capture.release()

    if frame_index == 0:
        raise ValueError("The video contains no decodable frames.")
    return frame_index, fps


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Convert every video frame into raw and JPEG-compressed ROS 2 images."
        )
    )
    parser.add_argument("--video", required=True, type=Path, help="Input video path")
    parser.add_argument(
        "--output-bag",
        "--bag",
        dest="output_bag",
        type=Path,
        help="Output rosbag2 directory (default: <video_name>_bag)",
    )
    parser.add_argument("--topic", default="/camera/image_raw")
    parser.add_argument(
        "--compressed-topic",
        help="CompressedImage topic (default: <topic>/compressed)",
    )
    parser.add_argument("--frame-id", default="camera")
    parser.add_argument("--jpeg-quality", type=int, default=95)
    parser.add_argument(
        "--start-time-ns",
        type=int,
        help="First frame timestamp in nanoseconds (default: current system time)",
    )
    parser.add_argument("--storage-id", default="sqlite3")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    output_bag = args.output_bag or args.video.parent / f"{args.video.stem}_bag"
    compressed_topic = (
        args.compressed_topic or f"{args.topic.rstrip('/')}/compressed"
    )
    try:
        frame_count, fps = convert_video_to_bag(
            video_path=args.video,
            output_bag=output_bag,
            topic=args.topic,
            compressed_topic=compressed_topic,
            frame_id=args.frame_id,
            jpeg_quality=args.jpeg_quality,
            start_time_ns=args.start_time_ns,
            storage_id=args.storage_id,
        )
    except (FileExistsError, FileNotFoundError, OSError, RuntimeError, ValueError) as exc:
        parser.error(str(exc))

    duration = (frame_count - 1) / fps
    print(
        f"Wrote {frame_count} frames ({duration:.3f} s at {fps:g} FPS) "
        f"to {output_bag.expanduser().resolve()} on {args.topic} and "
        f"{compressed_topic}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
