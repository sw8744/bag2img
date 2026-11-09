# bag2img

다음 네 개의 ROS 2 실행 파일을 제공합니다.

- `bag2img`: ROS 2 bag의 `sensor_msgs/msg/Image` 또는
  `sensor_msgs/msg/CompressedImage` 토픽을 일정 주기로 저장
- `bag2video`: ROS 2 bag의 이미지 토픽을 동영상으로 저장
- `video2img`: MP4, AVI 등 OpenCV가 읽을 수 있는 동영상을 일정 주기로 저장
- `video2bag`: 동영상의 모든 프레임을 ROS 2 bag의
  원본 및 JPEG 압축 이미지 토픽으로 저장

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

## ROS 2 bag을 동영상으로 변환

```bash
ros2 run bag2img bag2video \
  --bag ~/bags/input_bag \
  --topic /camera/image_raw/compressed \
  --output-video ~/Videos/output.mp4
```

원본 `Image`와 `CompressedImage`를 모두 지원합니다. 이미지 토픽이 하나면
`--topic`을 생략할 수 있습니다. `--output-video`(별칭 `--video`)를 생략하면
bag 옆에 `<bag이름>.mp4`를 생성하며 기존 파일은 덮어쓰지 않습니다.

모든 메시지를 한 프레임씩 기록합니다. 기본 FPS는 bag 기록 타임스탬프의
평균 주기로 계산하며, 프레임이 하나면 30 FPS를 사용합니다. `--fps 30`으로
직접 지정할 수 있습니다. 출력은 고정 FPS이므로 불규칙한 프레임 간격은
평균 간격으로 바뀝니다. `--codec`으로 FourCC를 지정할 수 있으며 기본값은
MP4용 `mp4v`입니다. `--storage-id`는 기본적으로 자동 감지합니다.

흑백 이미지는 BGR로 변환하고 알파 채널은 제거합니다. 16비트 이미지는
256으로 나눠 8비트로 변환합니다. 홀수 크기 영상은 오른쪽/아래쪽에 검은
픽셀을 추가해 짝수 크기로 저장하며, 도중에 이미지 크기가 바뀌면 오류를
반환합니다.

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

## 동영상을 ROS 2 bag으로 변환

```bash
ros2 run bag2img video2bag \
  --video ~/Videos/input.mp4 \
  --output-bag ~/bags/input_bag \
  --topic /camera/image_raw \
  --compressed-topic /camera/image_raw/compressed \
  --frame-id camera
```

각 영상 프레임은 다음 두 토픽에 같은 타임스탬프로 기록됩니다.

- `/camera/image_raw`: `bgr8` 인코딩의 `sensor_msgs/msg/Image`
- `/camera/image_raw/compressed`: JPEG 형식의
  `sensor_msgs/msg/CompressedImage`

`--compressed-topic`을 생략하면 `<--topic 값>/compressed`를 사용합니다.
JPEG 품질은 `--jpeg-quality`로 지정할 수 있으며 기본값은 95입니다.
bag과 메시지 헤더의 타임스탬프는 변환 시작 시각부터 영상 FPS에 맞춰
증가합니다. `--output-bag`을 생략하면 입력 영상 옆에 `<영상이름>_bag`
디렉터리를 만듭니다. 기존 경로를 덮어쓰지 않으므로 출력 경로는 존재하지
않아야 합니다.

재현 가능한 타임스탬프가 필요하면 첫 프레임의 시각을 직접 지정할 수 있습니다.

```bash
ros2 run bag2img video2bag \
  --video ~/Videos/input.mp4 \
  --start-time-ns 0
```

생성 결과 확인:

```bash
ros2 bag info ~/bags/input_bag
ros2 bag play ~/bags/input_bag
```
