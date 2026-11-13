# Wildfire Detection (DeepStream + YOLO)

## Science

This app detects fire and smoke in video using a YOLO11s object detection model running in NVIDIA DeepStream on a Jetson AGX Thor. Each frame is analyzed individually, and the app reports how many fire and smoke detections it finds. Because it processes video at frame rate, it is suited to continuous monitoring of a camera view and complements approaches that analyze one image at a time.

The model is a two-class YOLO11s network (`Fire`, `Smoke`). DeepStream converts it to a TensorRT engine for the GPU it runs on.

## Usage

The app reads either a video file or a live RTSP camera stream and runs it through the DeepStream detection pipeline. Detections are counted by class and published at a user-defined interval, along with the pipeline's processing speed in frames per second.

A video file run ends when the video ends. A live stream runs until the optional duration is reached or the job is stopped.

## Using the code

Sensor needed: Camera with an RTSP stream (or a video file)

Output: Fire and smoke detection counts, frames with detections, processing speed (FPS)

Input: Video file or RTSP stream

Image resolution: Frames are scaled to 1920x1080 before inference

Model loading time: The TensorRT engine is built from the ONNX model when the app first starts

### Arguments

- `--source`: Path to a video file or an `rtsp://` URL (default: bundled sample clip)
- `--duration`: Stop after this many seconds of pipeline run time (default: 0, runs until the video ends or the job is stopped)
- `--interval`: Seconds between published detection counts (default: 60)

## Ontology

The app publishes the following data:

- Fire detections: `env.detection.fire.count`
- Frames with fire: `env.detection.fire.frames`
- Smoke detections: `env.detection.smoke.count`
- Frames with smoke: `env.detection.smoke.frames`
- Processing speed: `env.deepstream.fps`
- Mean processing speed: `env.deepstream.fps.avg`

Detection counts cover the period since the previous publish.

## Inference from Sage codes

To query the output from the app, use the Python library `sage_data_client`:

```python
import sage_data_client

df = sage_data_client.query(
    start="-1h",
    filter={
        "name": "env.detection.smoke.count",
    }
)

print(df)
```