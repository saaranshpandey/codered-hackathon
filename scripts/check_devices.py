"""Phase 0 hardware check: cameras, microphones, and both at once.

Usage:
  python scripts/check_devices.py                 # list devices + 3 s simultaneous test
  python scripts/check_devices.py --camera 1 --mic Logitech --preview
"""
import argparse
import threading
import time

import cv2
import numpy as np
import sounddevice as sd

PERMISSION_HINT = ("macOS is probably blocking access. Open System Settings > Privacy & Security > "
                   "{what}, enable the app running Python (Terminal, iTerm or VS Code), then restart that app.")


def list_cameras(max_index=5):
    found = []
    for i in range(max_index):
        cap = cv2.VideoCapture(i, cv2.CAP_AVFOUNDATION)
        if cap.isOpened():
            ok, frame = cap.read()
            if ok:
                found.append((i, frame.shape[1], frame.shape[0]))
        cap.release()
    return found


def find_mic(name):
    for i, d in enumerate(sd.query_devices()):
        if d["max_input_channels"] > 0 and (name is None or name.lower() in d["name"].lower()):
            return i, d["name"]
    return None, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--camera", type=int, default=None)
    ap.add_argument("--mic", default=None, help="substring of the input device name")
    ap.add_argument("--seconds", type=float, default=3.0)
    ap.add_argument("--preview", action="store_true")
    args = ap.parse_args()

    print("Input devices:")
    for i, d in enumerate(sd.query_devices()):
        if d["max_input_channels"] > 0:
            print(f"  [{i}] {d['name']}  ({int(d['default_samplerate'])} Hz)")
    cams = list_cameras()
    print("Cameras (AVFoundation index, width x height):", cams or "none")
    if not cams:
        print(PERMISSION_HINT.format(what="Camera"))
        return

    cam_index = args.camera if args.camera is not None else cams[-1][0]
    mic_index, mic_name = find_mic(args.mic)
    print(f"Testing camera {cam_index} + mic [{mic_index}] {mic_name} together for {args.seconds}s ...")

    levels = []

    def record():
        audio = sd.rec(int(args.seconds * 16000), samplerate=16000, channels=1, device=mic_index, dtype="float32")
        sd.wait()
        levels.append(float(np.sqrt(np.mean(audio ** 2))))

    t = threading.Thread(target=record)
    t.start()
    cap = cv2.VideoCapture(cam_index, cv2.CAP_AVFOUNDATION)
    n, brightness, t0 = 0, [], time.time()
    while time.time() - t0 < args.seconds:
        ok, frame = cap.read()
        if not ok:
            break
        n += 1
        brightness.append(frame.mean())
        if args.preview:
            cv2.imshow("camera check (q to quit)", cv2.flip(frame, 1))
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    cap.release()
    cv2.destroyAllWindows()
    t.join()

    fps = n / (time.time() - t0)
    print(f"Camera: {n} frames, {fps:.1f} fps, mean brightness {np.mean(brightness) if brightness else 0:.0f}/255")
    if not brightness or np.mean(brightness) < 3:
        print("  Frames are black. " + PERMISSION_HINT.format(what="Camera"))
    rms = levels[0] if levels else 0.0
    print(f"Mic RMS: {rms:.5f}  (speak during the test; silence is ~0.001)")
    if rms == 0.0:
        print("  Mic returned pure zeros. " + PERMISSION_HINT.format(what="Microphone"))


if __name__ == "__main__":
    main()
