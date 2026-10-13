"""Расшифровка со словами и таймкодами (faster-whisper large-v3-turbo, локально).

Восстановлено 2026-10-02 (оригинал застрял в iCloud). Формат transcript.json прежний:
{"duration", "segments", "words": [{"w", "start", "end", "p"}], "secs"}.
Границы кусков потом всё равно режутся по звуку (timeline.by_speech), поэтому refine слова не подрезает.
"""
import json
import re
import subprocess
import tempfile
import time
from pathlib import Path

PROMPT = "Привет. Это ролик про ИИ, нейросети, ChatGPT, OpenAI, Claude."
_M = None


def model():
    global _M
    if _M is None:
        from faster_whisper import WhisperModel
        _M = WhisperModel("large-v3-turbo", device="cpu", compute_type="int8")
    return _M


def _words(path: str, offset: float = 0.0, prompt: str = PROMPT) -> tuple[list[dict], int]:
    segs, _ = model().transcribe(path, language="ru", word_timestamps=True, condition_on_previous_text=False,
                                 initial_prompt=prompt)
    out, n = [], 0
    for s in segs:
        n += 1
        for w in s.words or []:
            t = w.word.strip()
            if t:
                out.append({"w": t, "start": round(offset + w.start, 2), "end": round(offset + w.end, 2),
                            "p": round(w.probability, 2)})
    return out, n


def duration(path: str) -> float:
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                                capture_output=True, text=True).stdout)


def transcribe(audio: str, out: str) -> dict:
    t0 = time.time()
    words, n = _words(audio)
    d = {"duration": duration(audio), "segments": n, "words": words, "secs": round(time.time() - t0, 1)}
    Path(out).write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    return d


def refine(audio: str, words: list[dict]) -> list[dict]:
    """Слова не подрезаем: подрезка по таймкодам Whisper обрезала голос (правка автора 2026-09-29)."""
    return words


def speech(audio: str, db: int = -40, min_sil: float = 0.35) -> list[tuple[float, float]]:
    """Куски речи по громкости (silencedetect)."""
    r = subprocess.run(["ffmpeg", "-v", "info", "-i", audio, "-af", f"silencedetect=n={db}dB:d={min_sil}", "-f", "null", "-"],
                       capture_output=True, text=True).stderr
    st = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", r)]
    en = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", r)]
    total, out, cur = duration(audio), [], 0.0
    for a, b in zip(st, en + [None] * (len(st) - len(en))):
        if a > cur + 0.15:
            out.append((cur, a))
        cur = b if b is not None else total
    if total > cur + 0.15:
        out.append((cur, total))
    return out


def fill_gaps(audio: str, words: list[dict]) -> list[dict]:
    """Whisper иногда пропускает целый дубль: речь есть, слов нет. Такие куски распознаём отдельно и вставляем."""
    tmp = Path(tempfile.mkdtemp())
    add = []
    for a, b in speech(audio):
        if b - a < 0.8:
            continue
        covered = sum(max(0.0, min(b, w["end"]) - max(a, w["start"])) for w in words)
        if covered / (b - a) > 0.35:
            continue
        piece = tmp / "gap.wav"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{a}", "-t", f"{b - a}", "-i", audio, str(piece)], check=True)
        ws, _ = _words(str(piece), offset=a)
        add += [w for w in ws if not any(abs(w["start"] - x["start"]) < 0.15 for x in words)]
    return sorted(words + add, key=lambda w: w["start"])
