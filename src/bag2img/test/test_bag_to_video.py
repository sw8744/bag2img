"""Integration tests using real rosbag2 storage and OpenCV video encoding."""

import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np
import rosbag2_py
from rclpy.serialization import serialize_message

from bag2img.bag_to_video import convert_bag_to_video
from bag2img.video_to_bag import _compressed_image_message, _image_message


class BagToVideoTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bag = self.root / "input"
        self.output = self.root / "output.mp4"

    def make_bag(self, sizes=((48, 64),) * 5, timestamps=None, compressed=True):
        writer = rosbag2_py.SequentialWriter()
        writer.open(
            rosbag2_py.StorageOptions(uri=str(self.bag), storage_id="sqlite3"),
            rosbag2_py.ConverterOptions("cdr", "cdr"),
        )
        topics = [("/raw", "sensor_msgs/msg/Image")]
        if compressed:
            topics.append(("/compressed", "sensor_msgs/msg/CompressedImage"))
        for name, type_name in topics:
            metadata = dict(name=name, type=type_name, serialization_format="cdr")
            try:
                topic_metadata = rosbag2_py.TopicMetadata(**metadata)
            except TypeError:  # Jazzy also requires an ID; Humble does not.
                topic_metadata = rosbag2_py.TopicMetadata(id=0, **metadata)
            writer.create_topic(topic_metadata)
        if timestamps is None:
            timestamps = [1_000_000_000 + i * 100_000_000 for i in range(len(sizes))]
        for (height, width), timestamp in zip(sizes, timestamps):
            frame = np.full((height, width, 3), (20, 90, 180), dtype=np.uint8)
            writer.write("/raw", serialize_message(
                _image_message(frame, timestamp, "camera")
            ), timestamp)
            if compressed:
                writer.write("/compressed", serialize_message(
                    _compressed_image_message(frame, timestamp, "camera", 95)
                ), timestamp)
        del writer  # Flush metadata before opening the reader.

    def assert_video(self, count, fps, size=(64, 48)):
        capture = cv2.VideoCapture(str(self.output))
        try:
            self.assertTrue(capture.isOpened())
            self.assertAlmostEqual(capture.get(cv2.CAP_PROP_FPS), fps, places=2)
            frames = []
            while True:
                success, frame = capture.read()
                if not success:
                    break
                frames.append(frame)
            self.assertEqual(len(frames), count)
            self.assertEqual(frames[0].shape[:2], (size[1], size[0]))
            np.testing.assert_allclose(
                frames[0][10, 10], (20, 90, 180), atol=10
            )
        finally:
            capture.release()

    def test_raw_and_compressed_auto_fps(self):
        self.make_bag()
        for topic in ("/raw", "/compressed"):
            with self.subTest(topic=topic):
                self.assertEqual(convert_bag_to_video(
                    self.bag, self.output, topic=topic
                ), (5, 10.0, topic))
                self.assert_video(5, 10)
                self.output.unlink()

    def test_explicit_fps_and_odd_dimensions(self):
        self.make_bag(sizes=((49, 65),) * 3, compressed=False)
        self.assertEqual(convert_bag_to_video(
            self.bag, self.output, fps=24
        ), (3, 24, "/raw"))
        self.assert_video(3, 24, (66, 50))

    def test_single_frame(self):
        self.make_bag(sizes=((48, 64),), compressed=False)
        self.assertEqual(convert_bag_to_video(
            self.bag, self.output
        ), (1, 30.0, "/raw"))
        self.assert_video(1, 30)

    def test_requires_topic_when_ambiguous(self):
        self.make_bag()
        with self.assertRaisesRegex(ValueError, "multiple image topics"):
            convert_bag_to_video(self.bag, self.output)
        self.assertFalse(self.output.exists())

    def test_existing_output_is_preserved(self):
        self.make_bag()
        self.output.write_bytes(b"existing file")
        with self.assertRaises(FileExistsError):
            convert_bag_to_video(self.bag, self.output, topic="/raw")
        self.assertEqual(self.output.read_bytes(), b"existing file")

    def test_changed_dimensions_removes_partial_video(self):
        self.make_bag(sizes=((48, 64), (60, 80)), compressed=False)
        with self.assertRaisesRegex(ValueError, "dimensions changed"):
            convert_bag_to_video(self.bag, self.output)
        self.assertFalse(self.output.exists())

    def test_invalid_fps(self):
        for fps in (0, -1, float("nan"), float("inf")):
            with self.subTest(fps=fps), self.assertRaisesRegex(ValueError, "fps"):
                convert_bag_to_video(self.bag, self.output, fps=fps)

    def test_equal_timestamps_require_explicit_fps(self):
        self.make_bag(sizes=((48, 64),) * 2, timestamps=[0, 0], compressed=False)
        with self.assertRaisesRegex(ValueError, "Specify --fps"):
            convert_bag_to_video(self.bag, self.output)
        self.assertEqual(convert_bag_to_video(
            self.bag, self.output, fps=15
        ), (2, 15, "/raw"))
        self.assert_video(2, 15)


if __name__ == "__main__":
    unittest.main()
