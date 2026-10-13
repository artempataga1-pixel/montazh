"""Контроль готовой нарезки: распознаём смонтированный звук и вырезаем то, чего нет в тексте ролика.

Первичное распознавание прячет оговорки внутри соседних слов («Людмила» = «люди, бля»), поэтому после склейки
слушаем результат ещё раз — с подсказкой модели записывать «ээ», «бля» — и сверяем с тем, что должно звучать.
Лишнее (мат, «ээ», неуверенно распознанные обрывки) переводим во время записи и вырезаем.
"""
import re
import subprocess
import tempfile
from difflib import SequenceMatcher
from pathlib import Path

from takes import key

BANNED = re.compile(r"^(бля|блят|блядь|сука|нахуй|нахер|хуй|пизд|ёб|еб|эээ?|эм+|мм+)", re.I)
PROMPT = "Ээ, бля, ну, эм, короче."
LOW_P = 0.5


def master_to_source(t: float, ranges: list[tuple[float, float]]) -> float:
    off = 0.0
    for a, b in ranges:
        if t <= off + (b - a):
            return a + (t - off)
        off += b - a
    return ranges[-1][1]


def extras(master: str, expected: list[str], ranges: list[tuple[float, float]], model=None) -> list[tuple[float, float, str]]:
    """Куски записи (секунды исходника), которые звучат в нарезке, но не входят в текст ролика."""
    from faster_whisper import WhisperModel
    m = model or WhisperModel("large-v3-turbo", device="cpu", compute_type="int8")
    wav = Path(tempfile.mkdtemp()) / "m.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", master, "-vn", "-ac", "1", "-ar", "16000", str(wav)], check=True)
    segs, _ = m.transcribe(str(wav), language="ru", word_timestamps=True, condition_on_previous_text=False,
                           initial_prompt=PROMPT)
    heard = [w for s in segs for w in (s.words or []) if w.word.strip()]
    hk = [key(w.word) for w in heard]
    sm = SequenceMatcher(None, [key(x) for x in expected], hk, autojunk=False)
    bad = []
    for op, a1, a2, b1, b2 in sm.get_opcodes():
        for w in heard[b1:b2]:
            word = re.sub(r"[^\wё]", "", w.word.lower())
            name = re.search(r"[a-z0-9]", word)  # латиница/цифры — названия моделей (Astra, GPT-6), их распознавание пишет как угодно
            if BANNED.match(word) or (op in ("insert", "replace") and w.probability < LOW_P and not name):
                bad.append((master_to_source(w.start, ranges), master_to_source(w.end, ranges), w.word.strip()))
    for w in heard:  # мат режем всегда, даже если он «совпал» с текстом
        word = re.sub(r"[^\wё]", "", w.word.lower())
        if BANNED.match(word) and not any(abs(master_to_source(w.start, ranges) - b[0]) < 0.01 for b in bad):
            bad.append((master_to_source(w.start, ranges), master_to_source(w.end, ranges), w.word.strip()))
    return sorted(bad)


def subtract(ranges: list[tuple[float, float]], cuts: list[tuple[float, float, str]], pad: float = 0.04) -> list[tuple[float, float]]:
    out = list(ranges)
    for ca, cb, _ in cuts:
        ca, cb, nxt = ca - pad, cb + pad, []
        for a, b in out:
            if cb <= a or ca >= b:
                nxt.append((a, b))
                continue
            if ca - a > 0.22:
                nxt.append((a, round(ca, 3)))
            if b - cb > 0.22:
                nxt.append((round(cb, 3), b))
        out = nxt
    return out
