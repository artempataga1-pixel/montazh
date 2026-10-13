"""Где лицо автора в кадре (для кадрирования карточки и крупного плана).

Восстановлено 2026-10-02 (оригинал застрял в iCloud). MediaPipe FaceLandmarker (модель assets/cv/face_landmarker.task,
официальная, storage.googleapis.com/mediapipe-models). Формат face.json прежний, доли кадра:
cx, cy — центр точек лица; h — высота лица (лоб–подбородок); top — верх головы ≈ лоб − h/3 (с волосами).
Сверено на IMG_9011: старое {cx .53, cy .535, top .422, h .131}, новое {.523, .534, .422, .134}.
"""
import statistics
from pathlib import Path

import cv2

MODEL = Path(__file__).resolve().parent / "assets" / "cv" / "face_landmarker.task"


def face_stats(video: str, samples: int = 30) -> dict:
    import mediapipe as mp
    from mediapipe.tasks.python import BaseOptions
    from mediapipe.tasks.python.vision import FaceLandmarker, FaceLandmarkerOptions, RunningMode
    fl = FaceLandmarker.create_from_options(FaceLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=str(MODEL), delegate=BaseOptions.Delegate.CPU),
        running_mode=RunningMode.IMAGE, num_faces=1))
    cap = cv2.VideoCapture(video)
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
    cx, cy, top, h = [], [], [], []
    for k in range(samples):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(n * (k + 0.5) / samples))
        ok, fr = cap.read()
        if not ok:
            continue
        res = fl.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(fr, cv2.COLOR_BGR2RGB)))
        if not res.face_landmarks:
            continue
        L = res.face_landmarks[0]
        xs, ys = [p.x for p in L], [p.y for p in L]
        hh = max(ys) - min(ys)
        cx.append(statistics.mean(xs)); cy.append(statistics.mean(ys)); h.append(hh); top.append(min(ys) - hh / 3)
    cap.release()
    if not cx:
        return {"cx": 0.5, "cy": 0.5, "top": 0.4, "h": 0.13}
    med = statistics.median
    return {"cx": round(med(cx), 3), "cy": round(med(cy), 3), "top": round(med(top), 3), "h": round(med(h), 3)}
