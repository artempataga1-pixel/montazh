"""ARENA (IMG_9332, 12.10) — скилл Arena: 100 копий Claude, турнир на вылет. Было: IMG_9199 — CRM агентства недвижимости (сценарий C «Сдаю только полякам»): хук-возражение → ответ ИИ → «прописаны
заранее, всё видно в реальном времени, новые возражения заносит сам» → «не просто CRM — система» → «звонит ИИ на польском»
→ сценарии по дням, аналитика, KPI → CTA «СИСТЕМА». Вставки — запись экрана CRM (src/screen.mov).
Дубли: хук — 2-й полный; «тут реально…» — последний полный; «чтобы ты мог…» — 2-й заход."""
import sys, json, subprocess
sys.path.insert(0, "../../engine")
import cut
R = [[114.3, 120.1],                 # хук «Клод начал тупить и отвечать средне. Не переписывай промпт, устрой сотни его копий турнир на вылет»
     [128.78, 131.2],                # «Это скилл Арена для Claude Code.» (2-й заход; 1-й оборван на «ар-»)
     [139.1, 141.55],                # «Он бесплатный, код открытый.»
     [154.85, 164.3],                # «Ты просто пишешь „Арена“ и Claude Code запускает сотни субагентов… одну и ту же задачу» (1-й заход, без пауз)
     [229.15, 238.2],                # «у каждого есть своя стратегия… четвёртый — со сложного» (2-й заход, полный)
     [249.25, 251.65],               # «А дальше уже начинается турнир на вылет.»
     [255.15, 259.7],                # «Они разносят решения друг друга, защищаются, а судья ставит баллы.»
     [261.9, 264.7],                 # «И остаётся одно, самое сильное.»
     [280.2, 285.1],                 # (2-й заход внутри куска) «Конечно, 100 агентов дают самое сильное решение, но очень много лимитов съедает.»
     [300.5, 308.3],                 # «Но если задача сложная… это уже реально помогает.»
     [316.0, 319.5],                 # (2-й заход) «Я также собираю бизнесам агентов, которые работают вместо людей.»
     [350.9, 355.8]]                 # (2-й, полный заход) CTA «Если хочешь установить себе этот скилл, пиши слово „Арена“… скину полную инструкцию.»


def tighten(R, db=-28, d=0.3, pre=0.08, post=0.12):
    """Правка автора 04.10: «долгие паузы, слышно, как вздыхаю». Внутри и по краям каждого куска оставляем только речь
    (громче −28 дБ) с запасом до/после слова; паузы и вздохи от 0,3 с вырезаем."""
    import re
    out = []
    for a, b in R:
        r = subprocess.run(["ffmpeg", "-v", "info", "-ss", str(a), "-t", str(b - a), "-i", "audio.wav", "-af",
                            f"silencedetect=n={db}dB:d={d}", "-f", "null", "-"], capture_output=True, text=True).stderr
        st = [float(x) + a for x in re.findall(r"silence_start: ([\d.]+)", r)]
        en = [float(x) + a for x in re.findall(r"silence_end: ([\d.]+)", r)]
        en += [b] * (len(st) - len(en))
        segs, cur = [], a
        for s0, e0 in zip(st, en):
            # тихое слово (−28 дБ ловит и «в», «свяжусь») — паузу не режем, если внутри неё середина короткого слова
            # (тишину в начале куска режем всегда: Whisper сдвигает первое слово на тишину перед ним — «Люди» в 171,7 с)
            if s0 > a + 0.01 and any(s0 < (w["start"] + w["end"]) / 2 < e0 and w["end"] - w["start"] < 0.8 for w in WORDS):
                continue
            if s0 > cur:
                segs.append([cur, s0])
            cur = e0
        if cur < b:
            segs.append([cur, b])
        for x, y in segs:
            x, y = max(a, x - pre), min(b, y + post)
            if out and x <= out[-1][1] and out[-1][1] <= b and out[-1][0] >= a:
                out[-1][1] = max(out[-1][1], y)
            elif y - x > 0.12:
                out.append([round(x, 3), round(y, 3)])
    return out


WORDS = json.load(open("transcript.json"))["words"]
R = tighten(R[:3]) + [R[3]] + tighten(R[4:])  # кусок 4 не чистим: пауза −38 дБ внутри «Claude Code» съедала слово
# правило 07.10: конец куска — только в тишине (−40 дБ): дотягиваем до ближайшей тишины, если она в пределах 0,35 с
import re as _re
_r = subprocess.run(["ffmpeg", "-v", "info", "-i", "audio.wav", "-af", "silencedetect=n=-40dB:d=0.06", "-f", "null", "-"],
                    capture_output=True, text=True).stderr
_sil = list(zip([float(x) for x in _re.findall(r"silence_start: ([\d.]+)", _r)], [float(x) for x in _re.findall(r"silence_end: ([\d.]+)", _r)]))
for _k, (_a, _b) in enumerate(R):
    if not any(s - 0.03 <= _b <= e + 0.03 for s, e in _sil):
        _n = min([s for s, e in _sil if s > _b], default=_b)
        if _n - _b <= 0.35 and (_k + 1 == len(R) or _n < R[_k + 1][0]):
            R[_k][1] = round(_n + 0.02, 3)
R = [r for r in R if r[1] - r[0] >= 0.22]  # обрезки <0,22 с дёргают звук (правило 28.09)
R[-1][1] += 0.35  # последнее слово договариваем
json.dump(R, open("ranges.json", "w"))
cut.render_master("proxy.mp4", R, "master.mp4")
import transcribe as TR
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", "master.mp4", "-vn", "-ac", "1", "-ar", "16000", "m.wav"], check=True)
mw, _ = TR._words("m.wav", prompt="Claude, Claude Code, промпт, скилл Арена, субагентов, турнир на вылет, лимитов, баги, «Арена».")
dur = sum(b - a for a, b in R)
json.dump({"duration": dur, "ranges": R, "words": mw}, open("master_words.json", "w"), ensure_ascii=False, indent=1)
print("master", round(dur, 1)); print(" ".join(f"{w['w']}@{w['start']:.1f}" for w in mw))
