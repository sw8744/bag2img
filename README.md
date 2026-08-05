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
