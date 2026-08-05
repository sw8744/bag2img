# bag2img

다음 두 개의 ROS 2 실행 파일을 제공합니다.

- `bag2img`: ROS 2 bag의 `sensor_msgs/msg/Image` 또는
  `sensor_msgs/msg/CompressedImage` 토픽을 일정 주기로 저장
- `video2img`: MP4, AVI 등 OpenCV가 읽을 수 있는 동영상을 일정 주기로 저장

## 빌드

```bash
cd ~/bag2img
source /opt/ros/humble/setup.bash
colcon build --packages-select bag2img --symlink-install
source install/setup.bash
```

## ROS 2 bag 변환

이미지 토픽이 하나뿐이면 `--topic`은 생략할 수 있습니다.

```bash
ros2 run bag2img bag2img \
  --bag ~/dolbatS/bag/0801_full_track_camera \
  --interval 0.5 \
  --topic /camera/lane/raw/compressed \
  --output-dir ~/bag2img/bag_images
```

`--bag`에는 rosbag2 디렉터리 또는 그 안의 `.db3` 파일을 지정할 수 있습니다.

## 동영상 변환

```bash
ros2 run bag2img video2img \
  --video ~/Videos/input.mp4 \
  --interval 0.5 \
  --output-dir ~/bag2img/video_images
```

`--output-dir`을 생략하면 입력 파일 근처에 자동으로 출력 디렉터리를 만듭니다.

공통 옵션:

```text
--format {jpg,png}       출력 형식 (기본값: jpg)
--jpeg-quality 0..100    JPG 품질 (기본값: 95)
--prefix TEXT            파일명 접두사 (기본값: frame)
```

저장 파일명에는 순번과 입력 데이터 기준 timestamp(ns)가 포함됩니다.
