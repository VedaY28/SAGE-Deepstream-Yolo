# SAGE-Deepstream-Yolo

A Sage app that runs YOLO11-based fire and smoke detection on video with NVIDIA DeepStream, built for the Jetson AGX Thor.

The app takes a video file or a live RTSP camera stream, runs it through DeepStream with a TensorRT engine built from the model, counts fire and smoke detections, and publishes the results with pywaggle.

## Status

- Video file input
- RTSP (live camera) input

Tested on JetPack 7.0 (Jetson Linux R38.2.2) with DeepStream 8.0.

## How it works

1. `main.py` copies `deepstream_app_config.txt` and sets the input `uri` from `--source`. An `rtsp://` URL switches DeepStream to a live RTSP source.
2. It runs `deepstream-app` on that config and reads its output, printing it and picking out the FPS readings.
3. DeepStream writes the detections to KITTI-format text files, one per frame. `main.py` reads and deletes them every `--interval` seconds and counts them by class (`Fire`, `Smoke`).
4. The counts and FPS are published with `waggle.plugin`. Outside a Sage node, pywaggle runs in a local mode and nothing is uploaded.
5. A video file run ends when the video ends. A live stream runs until `--duration` elapses or the job is stopped.

## Usage

Build and run on the Thor:

```bash
git clone https://github.com/VedaY28/SAGE-Deepstream-Yolo
cd SAGE-Deepstream-Yolo
sudo docker build -t wildfire-app .
sudo docker run --rm --runtime nvidia wildfire-app
```

Run on a different video:

```bash
sudo docker run --rm --runtime nvidia \
  -v /path/to/videos:/videos \
  wildfire-app --source /videos/my_clip.mp4
```

Run on a live RTSP camera:

```bash
sudo docker run --rm --runtime nvidia \
  wildfire-app --source rtsp://<camera-address>/<path> --duration 600 --interval 30
```

The camera must be reachable from the host running the container. The RTSP URL is not printed in the logs.

### Arguments

| Argument | Default | Description |
|---|---|---|
| `--source` | `samples/sample1.mp4` | Path to a video file or an `rtsp://` URL |
| `--duration` | `0` | Stop after this many seconds of pipeline run time. `0` runs until the video ends or the job is stopped |
| `--interval` | `60` | Seconds between published detection counts |

### Example output

```
**PERF:  249.00 (258.04)
App run successful
Detections: {'smoke': 1552}
Frames with detections: {'smoke': 1552}
Average FPS: 249.0
```

## Published metrics

| Name | Description |
|---|---|
| `env.detection.fire.count` | Fire detections (boxes) since the previous publish |
| `env.detection.fire.frames` | Frames with at least one fire detection since the previous publish |
| `env.detection.smoke.count` | Smoke detections (boxes) since the previous publish |
| `env.detection.smoke.frames` | Frames with at least one smoke detection since the previous publish |
| `env.deepstream.fps` | Each FPS reading from DeepStream |
| `env.deepstream.fps.avg` | Mean of the FPS readings, published at the end of the run |


## Repository layout

```
Dockerfile                                 DeepStream 8.0 base image, pywaggle
sage.yaml                                  Sage app metadata
requirements.txt
main.py                                    Entry point
deepstream_app_config.txt                  DeepStream app config
config_infer_primary_yolo11_modified.txt   Inference (nvinfer) config
labels.txt                                 Class names: Fire, Smoke
firedetect-11s.onnx                        YOLO11s fire/smoke model
nvdsinfer_custom_impl_Yolo/                Compiled DeepStream-Yolo parser (.so)
samples/sample1.mp4                        Short demo clip
```

## Model

- YOLO11s trained for two classes: `0 = Fire`, `1 = Smoke`.
- The ONNX file is loaded by DeepStream, and the TensorRT engine is built from it at first run.
- The `labels.txt` order must match the class order above.