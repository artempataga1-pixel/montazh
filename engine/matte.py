"""Маска человека для монтажа «с глубиной» (урок 08.10: текст и карточки уходят ЗА спикера, фон можно подменить).

MediaPipe selfie_multiclass_256x256 (официальная модель, assets/cv/) → вероятность «человек» = 1 − фон;
края уточняются guided filter по самому кадру (волосы, плечи), по времени — лёгкое сглаживание, чтобы край не дрожал.

    craft.render() сам вызывает mask_video() по проходу «только камера» (3 прохода, см. craft.render)

Сцены с z="behind" (Reel(..., depth=True)) попадают ЗА человека: render() берёт проход без них там, где маска белая.
build() (альфа-webm слоем в браузере) оставлен для коротких тестов — на всём ролике рендер на 8 ГБ виснет.
"""
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np

MODEL = Path(__file__).resolve().parent / "assets" / "cv" / "selfie_multiclass_256x256.tflite"
W, H = 1080, 1920


def masks(video: Path, out_w: int = 540):
    import mediapipe as mp
    from mediapipe.tasks.python import BaseOptions
    from mediapipe.tasks.python.vision import ImageSegmenter, ImageSegmenterOptions, RunningMode
    opts = ImageSegmenterOptions(base_options=BaseOptions(model_asset_path=str(MODEL), delegate=BaseOptions.Delegate.CPU),
                                 running_mode=RunningMode.VIDEO, output_confidence_masks=True, output_category_mask=False)
    cap = cv2.VideoCapture(str(video))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    prev = None
    with ImageSegmenter.create_from_options(opts) as seg:
        i = 0
        while True:
            ok, fr = cap.read()
            if not ok:
                break
            h, w = fr.shape[:2]
            small = cv2.resize(fr, (out_w, int(out_w * h / w)), interpolation=cv2.INTER_AREA)
            rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
            res = seg.segment_for_video(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb), int(i * 1000 / fps))
            bg = res.confidence_masks[0].numpy_view()
            p = 1.0 - cv2.resize(bg, (small.shape[1], small.shape[0]), interpolation=cv2.INTER_LINEAR)
            guide = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255
            p = cv2.ximgproc.guidedFilter(guide, p.astype(np.float32), 6, 1e-3)
            p = np.clip((p - 0.35) / 0.4, 0, 1)                       # контрастный край без ореола
            if prev is not None:
                p = 0.6 * p + 0.4 * prev                               # без дрожания края
            prev = p
            yield fr, p
            i += 1
    cap.release()


def build(wd: Path) -> Path:
    wd = Path(wd)
    src = wd / "master.mp4"
    out = wd / "craft" / "hf" / "person.webm"
    out.parent.mkdir(parents=True, exist_ok=True)
    fps = cv2.VideoCapture(str(src)).get(cv2.CAP_PROP_FPS) or 30
    ff = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgra", "-s", f"{W}x{H}", "-r", f"{fps}",
                           "-i", "-", "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-b:v", "0", "-crf", "34", "-row-mt", "1",
                           "-deadline", "realtime", "-cpu-used", "8", "-auto-alt-ref", "0", str(out)], stdin=subprocess.PIPE)
    n = 0
    for fr, p in masks(src):
        # кадр масштабируем так же, как #cam в Reel (object-fit: cover под 1080×1920; мастер уже 9:16)
        fr = cv2.resize(fr, (W, H), interpolation=cv2.INTER_AREA)
        a = cv2.resize(p, (W, H), interpolation=cv2.INTER_LINEAR)
        bgra = np.dstack([fr, (a * 255).astype(np.uint8)])
        ff.stdin.write(bgra.tobytes())
        n += 1
    ff.stdin.close()
    ff.wait()
    print(f"{out}: {n} кадров")
    return out


if __name__ == "__main__":
    build(Path(sys.argv[1]))


def mask_video(src: Path, out: Path) -> Path:
    """Маска человека по готовому проходу «только камера» (уже с движениями камеры) → серое mp4 1080×1920.
    Её использует craft.render(): где маска белая — берём проход без графики «за спикером»."""
    fps = cv2.VideoCapture(str(src)).get(cv2.CAP_PROP_FPS) or 30
    ff = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "gray", "-s", f"{W}x{H}", "-r", f"{fps}",
                           "-i", "-", "-c:v", "libx264", "-crf", "12", "-preset", "fast", "-pix_fmt", "yuv420p", str(out)],
                          stdin=subprocess.PIPE)
    n = 0
    for fr, p in masks(Path(src)):
        ff.stdin.write((cv2.resize(p, (W, H), interpolation=cv2.INTER_LINEAR) * 255).astype(np.uint8).tobytes())
        n += 1
    ff.stdin.close()
    ff.wait()
    print(f"{out}: маска, {n} кадров")
    return out
