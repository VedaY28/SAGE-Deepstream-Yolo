import argparse
import os
import queue
import re
import shutil
import signal
import subprocess
import threading
import time
from collections import Counter
from statistics import mean

from waggle.plugin import Plugin

APP_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(APP_DIR, "deepstream_app_config.txt")
RUN_CONFIG = os.path.join(APP_DIR, "run_config.txt")
KITTI_DIR = os.path.join(APP_DIR, "results", "kitti")

PERF_RE = re.compile(r"\*\*PERF:\s+([\d.]+)\s+\(([\d.]+)\)")
NOISE_RE = re.compile(
    r"GStreamer-WARNING.*Failed to load plugin"
    r"|lsmod: not found"
    r"|\(Argus\) Error"
    r"|deserialize (engine|backend context)",
    re.IGNORECASE,
)
VERBOSE = os.environ.get("DEEPSTREAM_VERBOSE") == "1"
CLASSES = ("fire", "smoke")

stop_requested = False


def handle_stop(signum, frame):
    global stop_requested
    stop_requested = True


def is_live(source):
    return source.startswith("rtsp://")


def make_config(source):
    live = is_live(source)
    uri = source if "://" in source else "file://" + os.path.abspath(source)
    lines, section = [], ""
    with open(TEMPLATE) as f:
        for line in f:
            s = line.strip()
            if s.startswith("["):
                section = s
            if section == "[source0]":
                if s.startswith("uri="):
                    line = f"uri={uri}\n"
                elif live and s.startswith("type="):
                    line = "type=4\n"
            elif section == "[streammux]" and live and s.startswith("live-source="):
                line = "live-source=1\n"
            lines.append(line)
    with open(RUN_CONFIG, "w") as f:
        f.writelines(lines)


def drain_kitti(min_age):
    dets, frames = Counter(), Counter()
    if not os.path.isdir(KITTI_DIR):
        return dets, frames
    now = time.time()
    for name in os.listdir(KITTI_DIR):
        path = os.path.join(KITTI_DIR, name)
        try:
            if now - os.path.getmtime(path) < min_age:
                continue
            seen = set()
            with open(path) as f:
                for line in f:
                    parts = line.split()
                    if parts:
                        cls = parts[0].lower()
                        dets[cls] += 1
                        seen.add(cls)
            for c in seen:
                frames[c] += 1
            os.remove(path)
        except OSError:
            continue
    return dets, frames


def read_output(proc, fps_q, running_evt):
    for line in proc.stdout:
        line = line.rstrip()
        if not line.strip():
            continue
        if not VERBOSE and NOISE_RE.search(line):
            continue
        print(line, flush=True)
        if "Pipeline running" in line:
            running_evt.set()
        m = PERF_RE.search(line)
        if m and float(m.group(1)) > 0:
            fps_q.put(float(m.group(1)))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default="samples/sample1.mp4")
    parser.add_argument("--duration", type=int, default=0)
    parser.add_argument("--interval", type=int, default=60)
    args = parser.parse_args()

    signal.signal(signal.SIGTERM, handle_stop)
    signal.signal(signal.SIGINT, handle_stop)

    shutil.rmtree(KITTI_DIR, ignore_errors=True)
    os.makedirs(KITTI_DIR, exist_ok=True)
    make_config(args.source)

    print("Source:", "rtsp://<hidden>" if is_live(args.source) else args.source, flush=True)

    cmd = ["deepstream-app", "-c", RUN_CONFIG]
    if shutil.which("stdbuf"):
        cmd = ["stdbuf", "-oL", "-eL"] + cmd
    proc = subprocess.Popen(
        cmd,
        cwd=APP_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        errors="replace",
        bufsize=1,
    )

    fps_q, running_evt = queue.Queue(), threading.Event()
    reader = threading.Thread(target=read_output, args=(proc, fps_q, running_evt), daemon=True)
    reader.start()

    totals, frame_totals, fps_all = Counter(), Counter(), []
    running_since, last_publish = None, None
    stopped_by_us = False

    with Plugin() as plugin:

        def publish_fps():
            while not fps_q.empty():
                fps = fps_q.get()
                fps_all.append(fps)
                plugin.publish("env.deepstream.fps", fps)

        def publish_counts(min_age):
            dets, frames = drain_kitti(min_age)
            totals.update(dets)
            frame_totals.update(frames)
            for c in CLASSES:
                plugin.publish(f"env.detection.{c}.count", dets.get(c, 0))
                plugin.publish(f"env.detection.{c}.frames", frames.get(c, 0))

        while proc.poll() is None:
            time.sleep(1)
            publish_fps()

            if running_evt.is_set() and running_since is None:
                running_since = time.time()
                last_publish = running_since

            if last_publish is not None and time.time() - last_publish >= args.interval:
                publish_counts(min_age=1.0)
                last_publish = time.time()

            timed_out = (
                args.duration
                and running_since
                and time.time() - running_since >= args.duration
            )
            if stop_requested or timed_out:
                stopped_by_us = True
                proc.terminate()
                break

        try:
            proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        reader.join(timeout=5)

        publish_fps()
        if running_since is not None:
            publish_counts(min_age=0)

        print("Detections:", dict(totals))
        print("Frames with detections:", dict(frame_totals))
        if fps_all:
            avg = mean(fps_all)
            print(f"Average FPS: {avg:.1f}")
            plugin.publish("env.deepstream.fps.avg", avg)

    if proc.returncode != 0 and not stopped_by_us:
        raise SystemExit(f"deepstream-app failed (exit {proc.returncode})")


if __name__ == "__main__":
    main()