"""Мастер-версия: вырезать паузы (по громкости звука), пересчитать таймкоды слов.

Whisper растягивает слова на тишину, поэтому паузы ищем по уровню сигнала (ffmpeg silencedetect)."""
import json
import re
import subprocess
import sys

NOISE_DB = -35   # тише — пауза
MIN_SIL = 0.2    # паузы короче не трогаем, с
PAD = 0.08       # оставляем воздуха у края речи, с


def silences(audio: str, noise: float = NOISE_DB, d: float = MIN_SIL) -> list[tuple[float, float]]:
    log = subprocess.run(["ffmpeg", "-hide_banner", "-i", audio, "-af", f"silencedetect=noise={noise}dB:d={d}",
                          "-f", "null", "-"], capture_output=True, text=True).stderr
    starts = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", log)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", log)]
    return list(zip(starts, ends + [None] * (len(starts) - len(ends))))


def keep_ranges(sil: list[tuple[float, float | None]], duration: float) -> list[tuple[float, float]]:
    ranges, cur = [], 0.0
    for a, b in sil:
        b = duration if b is None else b
        cut_a = a + PAD if a > 0.05 else a      # в начале ролика тишину режем целиком
        cut_b = b - PAD if b < duration - 0.05 else b
        if cut_b - cut_a < 0.06:
            continue
        if cut_a > cur:
            ranges.append((round(cur, 3), round(cut_a, 3)))
        cur = cut_b
    if duration - cur > 0.06:
        ranges.append((round(cur, 3), round(duration, 3)))
    return ranges


def remap(words: list[dict], ranges: list[tuple[float, float]]) -> list[dict]:
    out, offset = [], 0.0
    bounds = []
    for a, b in ranges:
        bounds.append((a, b, offset))
        offset += b - a
    def at(t: float) -> float:  # время в мастере; попавшее в вырезанную паузу — к ближайшей склейке
        for a, b, off in bounds:
            if t < a:
                return off
            if t <= b:
                return t - a + off
        return offset
    for w in words:
        s, e = at(w["start"]), at(w["end"])
        out.append({**w, "start": round(s, 3), "end": round(max(e, s + 0.05), 3)})
    return out


def render_master(src: str, ranges, dst: str) -> None:
    parts, labels = [], []
    for i, (a, b) in enumerate(ranges):
        parts.append(f"[0:v]trim={a}:{b},setpts=PTS-STARTPTS[v{i}];"
                     f"[0:a]atrim={a}:{b},asetpts=PTS-STARTPTS,afade=t=in:d=0.01,afade=t=out:st={b - a - 0.01:.3f}:d=0.01[a{i}];")
        labels.append(f"[v{i}][a{i}]")
    graph = "".join(parts) + "".join(labels) + f"concat=n={len(ranges)}:v=1:a=1[v][a]"
    base = ["ffmpeg", "-v", "error", "-y", "-i", src, "-filter_complex", graph, "-map", "[v]", "-map", "[a]"]
    tail = ["-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", dst]
    r = subprocess.run(base + ["-c:v", "h264_videotoolbox", "-b:v", "14M"] + tail, capture_output=True, text=True)
    if r.returncode:  # аппаратный кодек Мака иногда отваливается по таймауту — тогда обычный, чуть медленнее
        subprocess.run(base + ["-c:v", "libx264", "-preset", "veryfast", "-crf", "18"] + tail, check=True)


if __name__ == "__main__":
    src, transcript, dst, words_out, audio = sys.argv[1:6]
    t = json.load(open(transcript, encoding="utf-8"))
    ranges = keep_ranges(silences(audio), t["duration"])
    kept = sum(b - a for a, b in ranges)
    render_master(src, ranges, dst)
    json.dump({"duration": round(kept, 3), "ranges": ranges, "words": remap(t["words"], ranges)},
              open(words_out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{t['duration']:.1f} с → {kept:.1f} с, кусков: {len(ranges)}")
