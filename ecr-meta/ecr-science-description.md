# High-Performance Wildfire Detection

## Science
Wildfires can grow quickly, so early warning matters. This app watches a camera feed and detects fire and smoke in real time. It runs a YOLO11s object detection model inside NVIDIA DeepStream on a Jetson AGX Thor.

The app checks every frame of the video, not just a snapshot now and then. On 1080p video it can process up to 300 frames per second (FPS). That is about 10 times faster than a typical 30 FPS camera. So one device can keep up with a live stream and still have plenty of room to spare. This makes the app a good fit for continuous monitoring. It also complements apps that look at one image at a time.

The model has two classes: `Fire` and `Smoke`. When the app first starts, DeepStream converts the model into a TensorRT engine. TensorRT is NVIDIA's tool for making models run fast on a specific GPU.

## Usage
The app takes a video file or a live RTSP camera stream (RTSP is the standard protocol most IP cameras use to stream video). It runs the video through the DeepStream detection pipeline. At a set interval, it publishes:
- how many fire and smoke detections it found, and
- how fast the pipeline is running, in FPS.

With a video file, the app stops when the video ends. With a live stream, it runs until the set duration is reached or the job is stopped.

## Using the code
- **Input:** Video file or RTSP stream
- **Output:** Fire and smoke detection counts, number of frames with detections, and processing speed (FPS)
- **Sensor needed:** A camera with an RTSP stream (or a video file)
- **Hardware:** NVIDIA Jetson AGX Thor
- **Image resolution:** Frames are scaled to 1920x1080 before inference
- **Performance:** Up to 300 FPS on 1080p video
- **Model loading time:** The first run builds the TensorRT engine from the ONNX model, which can take a few minutes.

### Arguments
- `--source`: Path to a video file or an `rtsp://` URL (default: a bundled sample clip)
- `--duration`: Stop after this many seconds (default: `0`, which means run until the video ends or the job is stopped)
- `--interval`: Seconds between published results (default: `60`)

### Example
    python3 main.py --source rtsp://<camera-ip>/stream --interval 30

## Ontology
The app publishes these values. Each count covers the time since the last publish.

| Name | Description |
|---|---|
| `env.detection.fire.count` | Number of fire detections |
| `env.detection.fire.frames` | Number of frames with fire |
| `env.detection.smoke.count` | Number of smoke detections |
| `env.detection.smoke.frames` | Number of frames with smoke |
| `env.deepstream.fps` | Current processing speed (FPS) |
| `env.deepstream.fps.avg` | Average processing speed (FPS) |

## Querying the data
Use the Python library `sage_data_client` to get the app's output:

    import sage_data_client

    df = sage_data_client.query(
        start="-1h",
        filter={
            "name": "env.detection.smoke.count",
        }
    )

    print(df)