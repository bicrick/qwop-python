#!/usr/bin/env python3
"""Extract Q/W/O/P press timeline from the kurodo QWOP WR video.

Pressed vs unpressed is a scale change on the on-screen buttons:
  unpressed ~98-101 px, origin near the rest position
  pressed   ~88-90 px, origin shifted +4 px right and +4 px down
Detection uses the tight bounding box of the beige button face inside a
fixed search window for each letter.
"""
import csv
import json
import subprocess
from pathlib import Path

import numpy as np

VIDEO = Path("/workspace/qwop-wr-extract/kurodo.mp4")
OUT_DIR = Path("/workspace/qwop-wr-extract")
FPS = 60.0

# Absolute search windows (x0, x1, y0, y1), exclusive ends. Measured on 1920x1080.
# P window stops before the speaker icon at ~(1366, 58-79).
ROIS = {
    "Q": (50, 165, 80, 210),
    "W": (168, 295, 80, 210),
    "O": (1120, 1252, 80, 210),
    "P": (1248, 1362, 88, 210),
}

# Decoded crop of the button band so we don't pipe full 1080p.
CROP_X, CROP_Y = 40, 75
CROP_W, CROP_H = 1400, 140

# min(w, h) of unpressed is >= 96; pressed is <= 90. Gap is unambiguous.
PRESSED_MAX_MIN_DIM = 93


def beige_mask(arr):
    r = arr[:, :, 0].astype(np.int16)
    g = arr[:, :, 1].astype(np.int16)
    b = arr[:, :, 2].astype(np.int16)
    return (
        (r >= 175)
        & (g >= 155)
        & (b >= 135)
        & (r <= 235)
        & (g <= 220)
        & (b <= 200)
        & ((r - b) >= 8)
        & (r >= g - 8)
    )


def measure_button(mask, roi):
    x0, x1, y0, y1 = roi
    # ROIs are in full-frame coords; mask is the crop.
    lx0, lx1 = x0 - CROP_X, x1 - CROP_X
    ly0, ly1 = y0 - CROP_Y, y1 - CROP_Y
    sub = mask[ly0:ly1, lx0:lx1]
    ys, xs = np.where(sub)
    if ys.size < 200:
        return None
    w = int(xs.max() - xs.min() + 1)
    h = int(ys.max() - ys.min() + 1)
    area = int(sub.sum())
    abs_x = int(x0 + xs.min())
    abs_y = int(y0 + ys.min())
    return {"w": w, "h": h, "area": area, "x": abs_x, "y": abs_y}


def pressed_from_meas(meas):
    if meas is None:
        return None
    return int(min(meas["w"], meas["h"]) <= PRESSED_MAX_MIN_DIM)


def rising_edges(states):
    n = 0
    prev = 0
    for s in states:
        if s == 1 and prev != 1:
            n += 1
        prev = s if s is not None else 0
    return n


def main():
    cmd = [
        "ffmpeg",
        "-v",
        "error",
        "-i",
        str(VIDEO),
        "-vf",
        f"crop={CROP_W}:{CROP_H}:{CROP_X}:{CROP_Y}",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "pipe:1",
    ]
    frame_bytes = CROP_W * CROP_H * 3
    rows = []
    size_rows = []
    missing = {k: 0 for k in ROIS}

    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, bufsize=frame_bytes * 4)
    i = 0
    while True:
        buf = proc.stdout.read(frame_bytes)
        if len(buf) < frame_bytes:
            break
        arr = np.frombuffer(buf, dtype=np.uint8).reshape(CROP_H, CROP_W, 3)
        mask = beige_mask(arr)
        rec = {"t_sec": round(i / FPS, 5)}
        sizes = {"t_sec": rec["t_sec"]}
        for name, roi in ROIS.items():
            meas = measure_button(mask, roi)
            state = pressed_from_meas(meas)
            if state is None:
                missing[name] += 1
                rec[name.lower()] = ""
                sizes[name] = None
            else:
                rec[name.lower()] = state
                sizes[name] = meas
        rows.append(rec)
        size_rows.append(sizes)
        i += 1
        if i % 600 == 0:
            print(f"decoded {i} frames", flush=True)
    proc.stdout.close()
    rc = proc.wait()
    if rc != 0:
        raise SystemExit(f"ffmpeg exited {rc}")

    csv_path = OUT_DIR / "timeline.csv"
    with csv_path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["t_sec", "q", "w", "o", "p"])
        for rec in rows:
            w.writerow([f"{rec['t_sec']:.5f}", rec["q"], rec["w"], rec["o"], rec["p"]])

    def col(name):
        return [r[name] for r in rows]

    duration = (len(rows) / FPS) if rows else 0.0
    # last frame timestamp + 1/fps is the span covered
    summary = {
        "video": str(VIDEO),
        "video_stream_duration_sec": 55.9,
        "n_frames": len(rows),
        "sample_fps": FPS,
        "timeline_span_sec": duration,
        "last_sample_t_sec": rows[-1]["t_sec"] if rows else None,
        "button_search_windows_xyxy": {
            k: {"x0": v[0], "x1": v[1], "y0": v[2], "y1": v[3]} for k, v in ROIS.items()
        },
        "pressed_detection_rule": (
            "Inside each fixed search window, take the tight bounding box of "
            "beige button-face pixels (R 175-235, G 155-220, B 135-200, R-B>=8). "
            "Pressed if min(width, height) <= 93. Unpressed buttons measure "
            "about 98-101 px; pressed buttons measure about 88-90 px and sit "
            "~4 px down-right. Threshold sits in the empty gap."
        ),
        "press_sample_counts": {k: int(sum(1 for v in col(k) if v == 1)) for k in "qwop"},
        "release_sample_counts": {k: int(sum(1 for v in col(k) if v == 0)) for k in "qwop"},
        "press_event_counts_rising_edges": {
            k: rising_edges(col(k)) for k in "qwop"
        },
        "undetected_frames": missing,
        "notes": (
            "Buttons are the HTML5 QWOP Q/W (thighs, top-left of the game) and "
            "O/P (calves, top-right). Right side of the recording is LiveSplit "
            "and a keyboard cam; those keys were not used. Native 60 fps."
        ),
    }

    # size histogram for QA
    dims = {k: [] for k in "qwop"}
    for s in size_rows:
        for name in "QWOP":
            m = s[name]
            if m:
                dims[name.lower()].append(min(m["w"], m["h"]))
    summary["min_dim_stats"] = {}
    for k, vals in dims.items():
        if not vals:
            continue
        arr = np.array(vals)
        summary["min_dim_stats"][k] = {
            "min": int(arr.min()),
            "max": int(arr.max()),
            "median": float(np.median(arr)),
            "n_le_93": int((arr <= 93).sum()),
            "n_between_94_and_95": int(((arr >= 94) & (arr <= 95)).sum()),
            "n_ge_96": int((arr >= 96).sum()),
        }

    json_path = OUT_DIR / "timeline.json"
    json_path.write_text(json.dumps(summary, indent=2) + "\n")

    # Persist per-frame measurements for spot-check selection
    dbg = OUT_DIR / "timeline_sizes.jsonl"
    with dbg.open("w") as f:
        for s in size_rows:
            f.write(json.dumps(s) + "\n")

    print(f"frames {len(rows)}")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
