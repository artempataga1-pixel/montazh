"""Монтажёр целиком: закинул видео → готовый рилс.

    python engine/montage.py путь/к/видео.mov [--script сценарий.txt] [--notes "пожелания"] [--music трек.mp3]

Шаги (результат каждого сохраняется в work/<имя>/ и не пересчитывается повторно):
рабочая копия → расшифровка → AI-режиссёр → чистка и мастер-версия → композиция → рендер → звуки и музыка → проверка.
Готовые ролики не перезаписываются: final_v1.mp4, final_v2.mp4, …
"""
import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

ENGINE = Path(__file__).resolve().parent
ROOT = ENGINE.parent
sys.path.insert(0, str(ENGINE))

import compose  # noqa: E402
import cut  # noqa: E402
import mix  # noqa: E402
import timeline  # noqa: E402

HF = "hyperframes@0.8.79"


_progress = None  # студия подписывается на шаги, чтобы показывать их на странице


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)
    if _progress:
        _progress(msg)


def run(cmd: list[str], **kw) -> None:
    subprocess.run(cmd, check=True, **kw)


def proxy(src: Path, dst: Path) -> None:
    """Рабочая копия 1440×2560 30 fps: из 4K можно приближать лицо без потери качества."""
    run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-vf", "scale=1440:2560:flags=lanczos,fps=30,format=yuv420p",
         "-c:v", "h264_videotoolbox", "-b:v", "14M", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(dst)])


def qa(path: Path, expect: float) -> list[str]:
    """Финальная приёмка: читается целиком, длительность, звук, громкость."""
    problems = []
    info = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height:format=duration",
                                      "-of", "json", str(path)], capture_output=True, text=True).stdout)
    kinds = {s["codec_type"] for s in info["streams"]}
    if kinds != {"video", "audio"}:
        problems.append(f"дорожки: {kinds}")
    v = next(s for s in info["streams"] if s["codec_type"] == "video")
    if (v["width"], v["height"]) != (1080, 1920):
        problems.append(f"размер {v['width']}×{v['height']}")
    d = float(info["format"]["duration"])
    if abs(d - expect) > 0.5:
        problems.append(f"длительность {d:.1f} с вместо {expect:.1f}")
    if subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "null", "-"], capture_output=True, text=True).stderr.strip():
        problems.append("ошибки при полном чтении файла")
    return problems


def timed_words(wd: Path) -> str:
    """Карта «секунда готового ролика: слово» прошлой версии — для правок вида «на 12 секунде»."""
    f = wd / "master_words.json"
    if not f.exists():
        return ""
    return " ".join(f"{w['start']:.1f}:{w['w']}" for w in json.load(open(f, encoding="utf-8"))["words"])


def theme_hint(text: str) -> str | None:
    t = (text or "").lower()
    if any(w in t for w in ("тёмн", "темн", "чёрн", "черн", "dark")):
        return "dark"
    if any(w in t for w in ("светл", "белый фон", "белом фоне", "light")):
        return "light"
    return None


def next_theme() -> str:
    """A/B-тест тем монтажа: берём ту, которой пока меньше среди смонтированных роликов."""
    count = {"light": 0, "dark": 0}
    for p in (ROOT / "work").glob("*/plan.json"):
        t = json.load(open(p, encoding="utf-8")).get("theme")
        if t in count:
            count[t] += 1
    return "dark" if count["dark"] < count["light"] else "light"


def montage(video: str, script: str = "", notes: str = "", music: str | None = None, redirect: bool = False,
            feedback: str = "", name: str | None = None, theme: str | None = None) -> Path:
    src = Path(video).expanduser().resolve()
    name = name or re.sub(r"[^\w-]+", "_", src.stem)[:40]
    wd = ROOT / "work" / name
    wd.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    if not (wd / "proxy.mp4").exists():
        log("рабочая копия 1440×2560")
        proxy(src, wd / "proxy.mp4")
    if not (wd / "audio.wav").exists():
        run(["ffmpeg", "-v", "error", "-y", "-i", str(wd / "proxy.mp4"), "-vn", "-ac", "1", "-ar", "16000", str(wd / "audio.wav")])
    if not (wd / "transcript.json").exists():
        log("расшифровка речи (слова и таймкоды)")
        from transcribe import transcribe
        transcribe(str(wd / "audio.wav"), str(wd / "transcript.json"))
    transcript = json.load(open(wd / "transcript.json", encoding="utf-8"))
    if not transcript.get("refined"):  # старые расшифровки — дочитываем спрятанные куски речи
        from transcribe import refine
        transcript["words"], transcript["refined"] = refine(str(wd / "audio.wav"), transcript["words"]), True
        json.dump(transcript, open(wd / "transcript.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        (wd / "director.json").unlink(missing_ok=True)  # номера слов поменялись — план заново
    if not transcript.get("gaps_filled"):  # речь без распознанных слов (пропущенный дубль) — дочитываем
        from transcribe import fill_gaps
        n = len(transcript["words"])
        transcript["words"], transcript["gaps_filled"] = fill_gaps(str(wd / "audio.wav"), transcript["words"]), True
        json.dump(transcript, open(wd / "transcript.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        if len(transcript["words"]) != n:
            (wd / "director.json").unlink(missing_ok=True)

    if (feedback and (wd / "director.json").exists()) or redirect or not (wd / "director.json").exists():
        import takes
        from director import clean, direct
        prev = json.load(open(wd / "director.json", encoding="utf-8")) if feedback and (wd / "director.json").exists() else None
        fb = f"{feedback}\n\n# Карта прошлой версии (секунда готового ролика: слово)\n{timed_words(wd)}" if prev else ""
        log("AI-монтажёр: выбираю удачные дубли" + (" по твоему тексту" if script else ""))
        c = clean(transcript["words"], script, notes, previous=(prev or {}).get("text", ""), feedback=fb)
        keep, report = takes.align(transcript["words"], c["text"], c.get("fixes"))
        lost = [r["text"] for r in report if r["from"] is None]
        if lost:
            log(f"⚠️ не нашёл в записи: {' | '.join(lost)[:200]}")
        if not keep:
            raise RuntimeError("не удалось сопоставить текст с записью — проверь, что текст рилса от этого видео")
        log("AI-режиссёр: " + ("вношу правку" if prev else "сцены и графика"))
        plan = direct(transcript["words"], transcript["duration"], script, notes, previous=prev, feedback=fb, keep=keep)
        plan.update(text=c["text"], fixes=c.get("fixes", []), drop=takes.drops(keep, len(transcript["words"])), takes=report)
        if prev:
            n_prev = len(list(wd.glob("director_v*.json"))) + 1
            (wd / f"director_v{n_prev}.json").write_text(json.dumps(prev, ensure_ascii=False, indent=1), encoding="utf-8")
        json.dump(plan, open(wd / "director.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    plan = json.load(open(wd / "director.json", encoding="utf-8"))
    if plan.get("text"):  # дубли пересчитываем каждый раз: это код, быстро и без модели
        import takes
        keep, plan["takes"] = takes.align(transcript["words"], plan["text"], plan.get("fixes"))
        plan["drop"] = takes.drops(keep, len(transcript["words"]))
    log(f"план: сцен {len(plan['scenes'])}, вырезать {len(plan['drop'])}, исправлений {len(plan['fixes'])}")

    tl = timeline.build(transcript, plan, str(wd / "audio.wav"))
    log(f"мастер-версия: {transcript['duration']:.1f} с → {tl['duration']:.1f} с")
    cut.render_master(str(wd / "proxy.mp4"), tl["ranges"], str(wd / "master.mp4"))
    log("контроль звука: слушаю нарезку на оговорки и мат")
    import verify
    bad = verify.extras(str(wd / "master.mp4"), [w["w"] for w in tl["words"]], tl["ranges"])
    if bad:
        log("вырезаю найденное: " + ", ".join(b[2] for b in bad)[:200])
        tl = timeline.build(transcript, plan, str(wd / "audio.wav"), extra_cuts=bad)
        cut.render_master(str(wd / "proxy.mp4"), tl["ranges"], str(wd / "master.mp4"))
    prev_theme = json.load(open(wd / "plan.json", encoding="utf-8")).get("theme") if (wd / "plan.json").exists() else None
    tl["plan"]["theme"] = (theme or theme_hint(f"{notes} {feedback}") or prev_theme or next_theme())
    log(f"тема оформления: {'тёмная' if tl['plan']['theme'] == 'dark' else 'светлая'}")
    face_file = wd / "face.json"
    if not face_file.exists():
        from freeze import face_stats  # где и насколько крупно лицо — кадрирование подстраивается под съёмку
        face_file.write_text(json.dumps(face_stats(str(wd / "proxy.mp4"))), encoding="utf-8")
    tl["plan"]["face"] = json.loads(face_file.read_text(encoding="utf-8"))
    photos = [sc for sc in tl["plan"]["scenes"] if (sc.get("graphic") or {}).get("type") == "photo"]
    if photos:
        log(f"ищу реальные фото для вставок: {len(photos)}")
        import broll
        for sc in photos:
            g = sc["graphic"]
            try:
                img = broll.resolve(g.get("query") or g.get("caption", ""), g.get("caption", ""), wd / "broll")
            except Exception as e:
                log(f"⚠️ фото «{g.get('caption', '')}» не нашлось: {str(e)[:120]}")
                img = None
            if img:
                g["src"] = str(img)
            else:  # не нашли подходящее фото — вместо него крупная подпись, сцена не пропадает
                sc["graphic"] = {"type": "title", "text": g.get("caption") or ""} if sc["layout"] == "graphic" and g.get("caption") else None
                if not sc["graphic"]:
                    sc["layout"] = "full"
    json.dump({"duration": tl["duration"], "ranges": tl["ranges"], "words": tl["words"]},
              open(wd / "master_words.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(tl["plan"], open(wd / "plan.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    log("сборка композиции")
    compose.build(tl["plan"], str(wd / "master_words.json"), str(wd / "master.mp4"), str(wd / "hf"))
    log("рендер (2 браузера)")
    env = {**__import__("os").environ, "PRODUCER_BROWSER_GPU_MODE": "hardware"}
    r = subprocess.run(["npx", "-y", HF, "render", "--no-low-memory-mode", "--workers", "2", "-o", str(wd / "render.mp4")],
                       cwd=wd / "hf", env=env, capture_output=True, text=True)
    (wd / "render.log").write_text(r.stdout + r.stderr, encoding="utf-8")
    if r.returncode or not (wd / "render.mp4").exists():
        raise RuntimeError("рендер не удался:\n" + "\n".join((r.stdout + r.stderr).strip().splitlines()[-8:]))

    n = 1 + max([int(m.group(1)) for p in wd.glob("final_v*.mp4") if (m := re.search(r"_v(\d+)", p.name))] or [0])
    final = wd / f"final_v{n}.mp4"
    log("звуки и музыка")
    mix.mix(str(wd / "render.mp4"), str(final), music=music,
            sfx=json.load(open(wd / "hf" / "sfx.json", encoding="utf-8")))
    problems = qa(final, tl["duration"])
    log(("⚠️ " + "; ".join(problems)) if problems else f"готово за {time.time() - t0:.0f} с → {final}")
    return final


VIDEO_EXT = {".mov", ".mp4", ".m4v"}
INBOX = Path.home() / "Library" / "Mobile Documents" / "com~apple~CloudDocs" / "Монтаж"  # iCloud Drive → видно на iPhone


def notify(title: str, text: str) -> None:
    subprocess.run(["osascript", "-e", f'display notification "{text}" with title "{title}" sound name "Glass"'],
                   capture_output=True)


def watch(folder: Path = INBOX) -> None:
    """Режим «закинул — получил»: видео в «Монтаж/Входящие» → готовый ролик в «Монтаж/Готово».

    Рядом с видео можно положить .txt с тем же именем — сценарий Альфреда или пожелания к монтажу."""
    import os
    from director import load_env
    load_env()
    if not os.environ.get("LLM_API_KEY"):
        log("⚠️ Нет ключа для AI-режиссёра. Создай файл montazh/.env со строками:\n"
            "LLM_API_KEY=<ключ>\nLLM_BASE_URL=<адрес Anthropic-совместимого API>\nDIRECTOR_MODEL=<модель>")
        notify("Монтажёр", "Нет ключа LLM_API_KEY в montazh/.env")
        return
    inbox, done, used = folder / "Входящие", folder / "Готово", folder / "Входящие" / "обработано"
    for d in (inbox, done, used):
        d.mkdir(parents=True, exist_ok=True)
    log(f"слежу за папкой {inbox} (Ctrl+C — выход)")
    sizes: dict[Path, int] = {}
    while True:
        for stub in inbox.glob(".*.icloud"):  # файл ещё в облаке — просим iCloud докачать его на Мак
            subprocess.run(["brctl", "download", str(stub)], capture_output=True)
        for f in sorted(inbox.iterdir()):
            if f.name.startswith(".") or f.suffix.lower() not in VIDEO_EXT:
                continue
            size = f.stat().st_size
            if sizes.get(f) != size:  # файл ещё копируется — ждём, пока размер перестанет меняться
                sizes[f] = size
                continue
            sizes.pop(f, None)
            note = f.with_suffix(".txt")
            text = note.read_text(encoding="utf-8") if note.exists() else ""
            notify("Монтажёр", f"Взял в работу: {f.name}")
            try:
                final = montage(str(f), script=text)
                out = done / f"{f.stem}_{final.stem}.mp4"
                out.write_bytes(final.read_bytes())
                f.rename(used / f.name)
                if note.exists():
                    note.rename(used / note.name)
                notify("Монтажёр", f"Готово: {out.name}")
                log(f"→ {out}")
            except Exception as e:  # ролик не сломал монтажёр: сообщаем и идём дальше
                log(f"⚠️ {f.name}: {e}")
                notify("Монтажёр", f"Не получилось: {f.name}")
                f.rename(used / f"ОШИБКА_{f.name}")
        time.sleep(10)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "watch":
        watch(Path(sys.argv[2]).expanduser() if len(sys.argv) > 2 else INBOX)
        sys.exit()
    ap = argparse.ArgumentParser(description="Монтажёр: сырое видео → готовый рилс")
    ap.add_argument("video")
    ap.add_argument("--script", help="файл со сценарием Альфреда (txt/md)")
    ap.add_argument("--notes", default="", help="пожелания к монтажу")
    ap.add_argument("--music", help="музыкальный трек")
    ap.add_argument("--redirect", action="store_true", help="заново позвать режиссёра")
    a = ap.parse_args()
    montage(a.video, open(a.script, encoding="utf-8").read() if a.script else "", a.notes, a.music, a.redirect)
