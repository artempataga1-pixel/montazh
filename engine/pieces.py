"""Проверка нарезки: каждый кусок мастера режем ещё и по внутренним паузам (≥0.3 с) и распознаём по частям отдельно.
Whisper склеивает оборванный дубль с полным и в целом мастере, и в целом куске (IMG_9010 «в Финляндии» дважды,
IMG_9012 «Пока dots» дважды), а по частям между паузами повтор видно: две части подряд начинаются одинаково."""
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path


def silences(wav: str, db: int = -40, d: float = 0.3) -> list[tuple[float, float]]:
    r = subprocess.run(["ffmpeg", "-v", "info", "-i", wav, "-af", f"silencedetect=n={db}dB:d={d}", "-f", "null", "-"],
                       capture_output=True, text=True).stderr
    st = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", r)]
    en = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", r)]
    return list(zip(st, en))


def check(wd: str = ".") -> list[tuple[float, str, bool]]:
    from faster_whisper import WhisperModel
    wd = Path(wd)
    m = WhisperModel("large-v3-turbo", device="cpu", compute_type="int8")
    R = json.load(open(wd / "master_words.json"))["ranges"]
    tmp = Path(tempfile.mkdtemp())
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", wd / "master.mp4", "-vn", "-ac", "1", "-ar", "16000", tmp / "m.wav"], check=True)
    sil = silences(str(tmp / "m.wav"))
    off, out, prev = 0.0, [], ""
    for a, b in R:
        end = off + (b - a)
        cuts = [off] + [(s + e) / 2 for s, e in sil if off + 0.2 < (s + e) / 2 < end - 0.2] + [end]
        for x, y in zip(cuts, cuts[1:]):
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{x}", "-t", f"{y - x}", "-i", tmp / "m.wav", tmp / "p.wav"], check=True)
            segs, _ = m.transcribe(str(tmp / "p.wav"), language="ru", condition_on_previous_text=False,
                                   initial_prompt="Ээ, бля, ну, эм, короче.")
            txt = " ".join(s.text.strip() for s in segs)
            head = lambda t: " ".join(re.sub(r"[^\w\s]", "", t.lower()).split()[:2])
            rep = bool(prev) and head(txt) != "" and head(txt) == head(prev)
            out.append((round(x, 2), txt, rep))
            prev = txt
        off = end
    return out


if __name__ == "__main__":
    for off, txt, rep in check(sys.argv[1] if len(sys.argv) > 1 else "."):
        print(f"{'⚠️ ПОВТОР ' if rep else ''}{off:6.1f} | {txt}")
