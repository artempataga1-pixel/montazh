"""План режиссёра (номера слов) → таймлайн мастер-версии (секунды).

1. исправления слов; 2. вырезаем дубли (drop) + паузы; 3. сцены по номерам слов → секунды мастера;
4. проверка правил (стоп-кадр ≤ 1.8 с и после него — спикер).
"""
import re

from cut import PAD, keep_ranges, remap, silences

PHONE_MAX = 1.8
MIN_SCENE = 0.6
GRAPHIC_MAX = 3.5
TAIL = 0.5  # хвост после последнего слова ролика, с
MERGE_GAP = 0.45  # паузы внутри дубля короче — оставляем как есть


def drop_ranges(words: list[dict], drop: list[dict]) -> list[tuple[float, float]]:
    out = []
    for d in drop:
        a, b = max(0, int(d["from"])), min(len(words) - 1, int(d["to"]))
        if a <= b:
            out.append((max(0.0, words[a]["start"] - 0.03), words[b]["end"] + 0.03))
    return sorted(out)


def subtract(ranges: list[tuple[float, float]], cuts: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Из оставляемых кусков вычесть вырезанные дубли."""
    for ca, cb in cuts:
        nxt = []
        for a, b in ranges:
            if cb <= a or ca >= b:
                nxt.append((a, b))
                continue
            if ca - a > 0.06:
                nxt.append((a, ca))
            if b - cb > 0.06:
                nxt.append((cb, b))
        ranges = nxt
    return [(round(a, 3), round(b, 3)) for a, b in ranges]


def stretched(w: dict, speech: list[tuple[float, float]]) -> bool:
    """Короткое слово («а», «и», «ну»), которое реально звучит дольше 0.45 с, — распознавание спрятало в нём оговорку."""
    if re.search(r"\d", w["w"]):  # цифры («5», «.7») — содержание, а не «а-а»; распознавание тянет их до паузы
        return False
    letters = len(re.sub(r"[^\wё]", "", w["w"])) or 1
    voiced = sum(max(0.0, min(w["end"], y) - max(w["start"], x)) for x, y in speech)
    return letters <= 2 and voiced > 0.45


def detached(w: dict, all_words: list[dict], kept_i: set[int]) -> bool:
    """Крайнее слово дубля, приклеенное вплотную к брошенному дублю и оторванное паузой от своей фразы, —
    почти всегда оговорка («э, бля», распознанное как «например»)."""
    i = w["i"]
    prv = all_words[i - 1] if i > 0 else None
    nxt = all_words[i + 1] if i + 1 < len(all_words) else None
    glued_prev = prv is not None and prv["i"] not in kept_i and w["start"] - prv["end"] < 0.15
    glued_next = nxt is not None and nxt["i"] not in kept_i and nxt["start"] - w["end"] < 0.15
    far_next = nxt is not None and nxt["i"] in kept_i and nxt["start"] - w["end"] > 0.8
    far_prev = prv is not None and prv["i"] in kept_i and w["start"] - prv["end"] > 0.8
    return (glued_prev and far_next) or (glued_next and far_prev)


def coverage(kept: list[dict], speech: list[tuple[float, float]], all_words: list[dict] | None = None,
             pad_a: float = 0.06, pad_b: float = 0.15, join: float = 0.25, join_take: float = 1.0) -> list[tuple[float, float]]:
    """Звучит только то, что покрыто оставленными словами. Внутри одного дубля (слова подряд) держим зазоры до 1 с —
    распознавание иногда теряет слово («абсолютно»); на стыке разных дублей — склейка уже после 0.25 с.
    Растянутое слово («а» длиной в секунду — внутри спрятано «бля») обрезаем до нормальной длины от начала звука.
    Отступ «для воздуха» не заходит на соседнее вырезанное слово — иначе цепляется хвост («…ство» перед «где»).
    Так в ролик не пролезают нераспознанные куски — бормотание, мат, спрятанные дубли."""
    all_words = all_words or kept
    kept_i = {w["i"] for w in kept}
    out, prev = [], None
    for w in kept:
        onset = next((max(w["start"], a) for a, b in speech if b > w["start"]), w["start"])  # где слово реально зазвучало
        letters = len(re.sub(r"[^\wё]", "", w["w"])) or 1
        if stretched(w, speech) or detached(w, all_words, kept_i):
            continue
        i = w["i"]
        lo = all_words[i - 1]["end"] if i > 0 and all_words[i - 1]["i"] not in kept_i else 0.0
        hi = all_words[i + 1]["start"] if i + 1 < len(all_words) and all_words[i + 1]["i"] not in kept_i else 1e9
        a = max(0.0, lo, w["start"] - pad_a)
        b = min(hi, min(w["end"], onset + 0.2 + 0.09 * letters) + pad_b)
        gap = join_take if prev is not None and w["i"] == prev + 1 else join
        prev = w["i"]
        if out and a - out[-1][1] <= gap:
            out[-1] = (out[-1][0], max(out[-1][1], b))
        else:
            out.append((a, b))
    return out


def intersect(xs: list[tuple[float, float]], ys: list[tuple[float, float]]) -> list[tuple[float, float]]:
    out, i, j = [], 0, 0
    while i < len(xs) and j < len(ys):
        a, b = max(xs[i][0], ys[j][0]), min(xs[i][1], ys[j][1])
        if b - a > 0.06:
            out.append((round(a, 3), round(b, 3)))
        if xs[i][1] < ys[j][1]:
            i += 1
        else:
            j += 1
    return out


_PCM: dict = {}


def loudness(audio: str):
    """Громкость по 10-мс окнам (дБ) — для точной подрезки тишины на стыках."""
    if audio not in _PCM:
        import subprocess
        import numpy as np
        raw = subprocess.run(["ffmpeg", "-v", "error", "-i", audio, "-f", "s16le", "-ac", "1", "-ar", "16000", "-"],
                             capture_output=True, check=True).stdout
        x = np.frombuffer(raw, np.int16).astype(np.float32) / 32768
        n = len(x) // 160
        _PCM[audio] = 20 * np.log10(np.sqrt((x[:n * 160].reshape(n, 160) ** 2).mean(axis=1)) + 1e-9)
    return _PCM[audio]


def tighten(ranges: list[tuple[float, float]], audio: str, kept: list[dict], thr: float = -40, head: float = 0.02,
            tail: float = 0.04, take_gap: float = 1.0) -> list[tuple[float, float]]:
    """На стыке РАЗНЫХ дублей режем точно по звуку слова: «…за наставничество, где…» идёт сразу, без провала,
    и не цепляет ни хвост соседнего слова, ни начало следующей оговорки (звук после провала громкости).
    Паузы внутри одного дубля не трогаем — там это живая речь."""
    db = loudness(audio)
    loud = lambda t, th=thr: db[min(len(db) - 1, max(0, int(t * 100)))] > th
    out = []
    for k, (a, b) in enumerate(ranges):
        inside = [w for w in kept if a - 0.5 <= w["start"] and w["end"] <= b + 0.2]
        if k and a - ranges[k - 1][1] > take_gap and inside:  # начало куска — от первого звука первого слова
            lo = max(ranges[k - 1][1], a - 0.4)  # тихие «с», «ш» порог пауз (−35 дБ) считает тишиной — начало можно раньше
            t = max(lo, inside[0]["start"])
            q, run = t, 0  # хвост соседнего слова (< 0.15 с), потом тишина — настоящее начало после тишины
            while q < min(b - 0.1, t + 0.6):
                run = run + 1 if not loud(q, -55) else 0
                if run >= 8 and q - 0.08 - t < 0.15:
                    while q < b - 0.1 and not loud(q, -55):
                        q += 0.01
                    t = q
                    break
                if run == 0 and q - t >= 0.15:
                    break
                q += 0.01
            while t - 0.01 > lo and loud(t - 0.01, -55):  # тихие «с», «н» перед распознанным началом — тоже слово
                t -= 0.01
            a = round(max(lo, t - head), 3)
        if k + 1 < len(ranges) and ranges[k + 1][0] - b > take_gap and inside:  # конец — по затуханию последнего слова
            t = min(b, inside[-1]["end"])
            while t + 0.01 < b and loud(t):
                t += 0.01
            b = round(min(b, t + tail), 3)
        out.append((a, b))
    return out


SOUND_DB, SOUND_GAP = -45, 0.15  # звук речи: всё громче −45 дБ; тишина — от 0.15 с (тихие окончания и «с» — это ещё звук)


def by_speech(words: list[dict], good_i: set[int], audio: str, duration: float) -> list[tuple[float, float]]:
    """Куски, которые звучат в ролике, — по НАСТОЯЩИМ границам звука, а не по таймкодам распознавания.

    Звук режется на куски по тишине. Кусок берём, если все слова в нём оставлены; если в одном непрерывном куске встык
    идут нужный дубль и выброшенная оговорка — режем в самом тихом месте между их словами. Кусок без слов не берём."""
    db = loudness(audio)
    lvl = lambda t: db[min(len(db) - 1, max(0, int(t * 100)))]

    def valley(t0: float, t1: float) -> float:  # самое тихое место между словами — там склейка не слышна
        if t1 <= t0:
            return round((t0 + t1) / 2, 3)
        ts = [t0 + k * 0.01 for k in range(int((t1 - t0) / 0.01) + 1)]
        return round(min(ts, key=lvl), 3)

    out = []
    for a, b in keep_ranges(silences(audio, SOUND_DB, SOUND_GAP), duration):
        seg = [w for w in words if a <= (w["start"] + w["end"]) / 2 <= b]
        if not seg:
            continue
        good = [w["i"] in good_i for w in seg]
        k = 0
        while k < len(seg):
            if not good[k]:
                k += 1
                continue
            j = k
            while j + 1 < len(seg) and good[j + 1]:
                j += 1
            s0 = a if k == 0 else max(a, valley(seg[k - 1]["end"] - 0.12, seg[k]["start"] + 0.08))
            e0 = b if j == len(seg) - 1 else min(b, valley(seg[j]["end"] - 0.08, seg[j + 1]["start"] + 0.12))
            if e0 - s0 > 0.06:
                out.append((round(s0, 3), round(e0, 3)))
            k = j + 1
    return out


def build(transcript: dict, plan: dict, audio: str, extra_cuts: list | None = None) -> dict:
    """extra_cuts — куски записи, которые контроль готового звука (verify.py) велел вырезать."""
    words = [dict(w, i=i) for i, w in enumerate(transcript["words"])]
    for f in plan.get("fixes", []):
        if 0 <= f["i"] < len(words) and f.get("text"):
            words[f["i"]]["w"] = f["text"]
    dropped = set()
    for d in plan.get("drop", []):
        dropped.update(range(int(d["from"]), int(d["to"]) + 1))
    kept = [w for w in words if w["i"] not in dropped]
    speech = keep_ranges(silences(audio), transcript["duration"])
    kept_i = {w["i"] for w in kept}
    cut_words = [w for w in words if w["i"] in dropped or stretched(w, speech) or (w["i"] in kept_i and detached(w, words, kept_i))]
    cut_i = {w["i"] for w in cut_words}
    ranges = by_speech(words, kept_i - cut_i, audio, transcript["duration"])
    merged = ranges[:1]
    for x, y in ranges[1:]:  # короткую паузу внутри дубля не режем — микросклейки дёргают звук и картинку
        px, py = merged[-1]
        if x - py < MERGE_GAP and not any(w["start"] < x and w["end"] > py for w in cut_words):
            merged[-1] = (px, y)
        else:
            merged.append((x, y))
    ranges = [r for k, r in enumerate(merged) if r[1] - r[0] >= 0.22 or k == len(merged) - 1]  # обрывки — мигание кадра
    if ranges and kept:  # последнее слово договариваем до конца: тихие окончания тише порога пауз
        ranges[-1] = (ranges[-1][0], round(min(transcript["duration"], max(ranges[-1][1], kept[-1]["end"] + TAIL)), 3))
    if extra_cuts:
        from verify import subtract
        ranges = subtract(ranges, extra_cuts)
    silent = {w["i"] for w in cut_words} | {w["i"] for w in words for a, b, _ in extra_cuts or []
                                            if a <= (w["start"] + w["end"]) / 2 <= b}
    master = [w for w in remap([w for w in words if w["i"] not in dropped and w["i"] not in silent], ranges)]
    dur = round(sum(b - a for a, b in ranges), 3)
    by_idx = {w["i"]: w for w in master}

    def t_of(i: int) -> float:  # начало сцены — чуть раньше её первого слова
        for k in range(i, len(words)):
            if k in by_idx:
                return max(0.0, by_idx[k]["start"] - 0.08)
        return dur

    raw = sorted(plan["scenes"], key=lambda s: s["from"])
    scenes = []
    for k, s in enumerate(raw):
        st = 0.0 if k == 0 else t_of(int(s["from"]))
        if scenes and st - scenes[-1]["start"] < MIN_SCENE:  # слишком короткая — сливаем: графика важнее пустой сцены
            if s.get("graphic") and not scenes[-1].get("graphic"):
                scenes[-1].update({x: s[x] for x in ("layout", "zoom", "graphic") if x in s})
            continue
        if scenes:
            scenes[-1]["end"] = round(st, 3)
        scenes.append({**{x: s[x] for x in ("layout", "zoom", "graphic") if x in s}, "start": round(st, 3)})
    scenes[-1]["end"] = dur
    items = [s for s in scenes if (s.get("graphic") or {}).get("type") == "item"]
    for s in scenes:  # страховка от ошибок режиссёра: только известные раскладки
        g = s.get("graphic") or {}
        if s.get("layout") not in ("full", "split", "graphic"):
            s["layout"] = "split" if g and g.get("type") != "dm" else "full"
        if g.get("type") == "dm":
            s["layout"] = "full"
        if g.get("type") == "item":  # номер и общее число пунктов — по факту, а не как угадал режиссёр
            g["n"] = items.index(s) + 1
            g["total"] = max(int(g.get("total") or 0), len(items))
    for s in scenes:  # долгая графика без лица утомляет — дольше 3.5 с держим автора в карточке снизу
        if s["layout"] == "graphic" and s["end"] - s["start"] > GRAPHIC_MAX and (s.get("graphic") or {}).get("type") != "phone":
            s["layout"] = "split"
    first = scenes[0]  # первый кадр — всегда лицо автора: графика хука появляется через ~1 с
    if first["layout"] == "full" and first["end"] < 1.0 and len(scenes) > 1:
        nxt = scenes[1]
        cut_at = next((w["start"] - 0.08 for w in master if w["start"] >= 1.0), None)
        if cut_at and nxt["end"] - cut_at >= MIN_SCENE + 0.4:
            first["end"] = nxt["start"] = round(cut_at, 3)
    elif first["layout"] != "full":
        cut_at = next((w["start"] - 0.08 for w in master if w["start"] >= 1.0), None)
        if cut_at and first["end"] - cut_at >= MIN_SCENE + 0.4:
            scenes.insert(0, {"layout": "full", "zoom": 1.0, "start": 0.0, "end": round(cut_at, 3)})
            first["start"] = round(cut_at, 3)
        else:
            first["layout"] = "full"
            first.pop("graphic", None)
    fixed = []
    for s in scenes:  # правила стоп-кадра: коротко, потом спикер
        fixed.append(s)
        if (s.get("graphic") or {}).get("type") == "phone":
            s["layout"] = "graphic"
            hold = min(PHONE_MAX, max(0.9, float(s["graphic"].get("hold") or 1.6)))
            if s["end"] - s["start"] > hold + 0.05:
                fixed.append({"layout": "full", "zoom": 1.0, "start": round(s["start"] + hold, 3), "end": s["end"]})
                s["end"] = round(s["start"] + hold, 3)
    return {"duration": dur, "ranges": ranges, "words": master,
            "plan": {"keywords": plan.get("keywords", []), "fixes": [], "scenes": fixed,
                     "title": plan.get("title", ""), "music_mood": plan.get("music_mood", "")}}
