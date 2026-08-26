# 사용법
## bag2img
```bash
ros2 run bag2img bag2img \
  --bag testbag \
  --interval 0.5 \
  --topic /camera/raw/compressed \
  --output-dir ~/bag2img/bag_images
```

## video2img
```bash
ros2 run bag2img video2img \
  --video ~/Videos/input.mp4 \
  --interval 0.5 \
  --output-dir ~/bag2img/video_images
```

## video2bag

```bash
ros2 run bag2img video2bag \
  --video ~/Videos/input.mp4 \
  --output-bag ~/bags/input_bag \
  --topic /camera/image_raw \
  --compressed-topic /camera/image_raw/compressed \
  --frame-id camera
```

영상의 모든 프레임을 `/camera/image_raw`의 `sensor_msgs/msg/Image`와
`/camera/image_raw/compressed`의 `sensor_msgs/msg/CompressedImage`로 함께
기록합니다. 압축 토픽을 생략하면 `<--topic 값>/compressed`가 사용됩니다.
`--output-bag`을 생략하면 영상 옆에 `<영상이름>_bag`을 생성합니다.
