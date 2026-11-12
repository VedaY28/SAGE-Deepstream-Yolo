import argparse
import os
import re
import shutil
import subprocess
import time
from collections import Counter
from statistics import mean

from waggle.plugin import Plugin

APP_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(APP_DIR, "deepstream_app_config.txt")
RUN_CONFIG = os.path.join(APP_DIR, "run_config.txt")
KITTI_DIR = os.path.join(APP_DIR, "results", "kitti")

PERF_RE = re.compile(r"\*\*PERF:\s+([\d.]+)\s+\(([\d.]+)\)")


def make_config(source):
    uri = source if "://" in source else "file://" + os.path.abspath(source)
    lines, in_src = [], False
    with open(TEMPLATE) as f:
        for line in f:
            s = line.strip()
            if s.startswith("["):
                in_src = (s == "[source0]")
            if in_src and s.startswith("uri="):
                line = f"uri={uri}\n"
            lines.append(line)
    with open(RUN_CONFIG, "w") as f:
        f.writelines(lines)


def count_detections():
    totals, frames = Counter(), Counter()
    if not os.path.isdir(KITTI_DIR):
        return totals, frames
    for name in os.listdir(KITTI_DIR):
        seen = set()
        with open(os.path.join(KITTI_DIR, name)) as f:
            for line in f:
                parts = line.split()
                if parts:
                    cls = parts[0].lower()
                    totals[cls] += 1
                    seen.add(cls)
        for c in seen:
            frames[c] += 1
    return totals, frames


def run_deepstream(plugin):
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

    fps_readings = []
    running_since = None
    for line in proc.stdout:
        line = line.rstrip()
        if not line.strip():
            continue
        print(line, flush=True)
        if running_since is None and "Pipeline running" in line:
            running_since = time.time()
        m = PERF_RE.search(line)
        if m:
            current = float(m.group(1))
            if current > 0:
                fps_readings.append(current)
                plugin.publish("env.deepstream.fps", current)
    proc.wait()
    run_time = time.time() - running_since if running_since else None
    return proc.returncode, fps_readings, run_time


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default="samples/sample1.mp4")
    args = parser.parse_args()

    shutil.rmtree(KITTI_DIR, ignore_errors=True)
    os.makedirs(KITTI_DIR, exist_ok=True)
    make_config(args.source)

    with Plugin() as plugin:
        returncode, fps_readings, run_time = run_deepstream(plugin)

        if returncode != 0:
            raise SystemExit(f"deepstream-app failed (exit {returncode})")

        totals, frames = count_detections()
        print("Detections:", dict(totals))
        print("Frames with detections:", dict(frames))
        if fps_readings:
            print(f"Average FPS: {mean(fps_readings):.1f}")
        if run_time is not None:
            print(f"Run time (excluding engine build): {run_time:.1f}s")

        for cls in ("fire", "smoke"):
            plugin.publish(f"env.detection.{cls}.count", totals.get(cls, 0))
            plugin.publish(f"env.detection.{cls}.frames", frames.get(cls, 0))
        if fps_readings:
            plugin.publish("env.deepstream.fps.avg", mean(fps_readings))
        if run_time is not None:
            plugin.publish("env.deepstream.runtime_sec", run_time)


if __name__ == "__main__":
    main()