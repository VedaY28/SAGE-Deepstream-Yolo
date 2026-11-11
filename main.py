import argparse
import os
import shutil
import subprocess
from collections import Counter

from waggle.plugin import Plugin

APP_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(APP_DIR, "deepstream_app_config.txt")
RUN_CONFIG = os.path.join(APP_DIR, "run_config.txt")
KITTI_DIR = os.path.join(APP_DIR, "results", "kitti")


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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default="samples/sample1.mp4")
    args = parser.parse_args()

    shutil.rmtree(KITTI_DIR, ignore_errors=True)
    os.makedirs(KITTI_DIR, exist_ok=True)
    make_config(args.source)

    result = subprocess.run(["deepstream-app", "-c", RUN_CONFIG], cwd=APP_DIR)
    if result.returncode != 0:
        raise SystemExit(f"deepstream-app failed (exit {result.returncode})")

    totals, frames = count_detections()
    print("Detections:", dict(totals))
    print("Frames with detections:", dict(frames))

    with Plugin() as plugin:
        for cls in ("fire", "smoke"):
            plugin.publish(f"env.detection.{cls}.count", totals.get(cls, 0))
            plugin.publish(f"env.detection.{cls}.frames", frames.get(cls, 0))


if __name__ == "__main__":
    main()