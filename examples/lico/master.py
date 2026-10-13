"""LICO (IMG_9333, 12.10) — «Не кидай своё фото в ChatGPT, если не готов узнать правду»: селфи + промпт → отчёт о внешности
с оценками → сильные/слабые стороны → оценка из 10 → разбор популярных личностей → CTA «ЛИЦО».
Дубли: хук — последний (65,7); «Смотри, делаю селфи…» — 3-й заход (90,2, во 2-м «клод»); конец с матом выкинут."""
import sys, json, subprocess
sys.path.insert(0, "../../engine")
import cut
R = [[65.85, 69.68],                 # хук «Не кидай своё фото в ChatGPT, если не готов узнать правду.»
     [90.3, 94.9],                   # «Смотри, делаю селфи, кидаю в ChatGPT и вставляю вот этот промпт.»
     [97.7, 104.95],                 # «ChatGPT разбирает симметрию, пропорцию, кожу, линию челюсти и собирает вот такой отчёт.»
     [104.95, 114.93],               # «Можно прям посмотреть, изучить по баллам… насколько лицо вообще симметрично и тому подобное.»
     [117.38, 122.83],               # «То есть, грубо говоря, разбирать сильные и слабые стороны, чтобы подтянуть, ну, например, стрижку»
     [130.19, 133.09],               # «или уход, или даже какие очки тебе подойдут.»
     [135.55, 136.7],                # «И в конце»
     [143.68, 147.77],               # «можно посмотреть по каждому пункту оценку по десятибалльной шкале.»
     [152.75, 155.55],               # «А также полную оценку по 10-балльной шкале.» (2-й заход; 1-й «а также… также по 10» — повтор)
     [158.0, 162.79],                # «И это не приговор, это ориентир для стиля, который можно использовать в дальнейшем.»
     [165.4, 170.31],                # (2-й заход) «Я также на примере разобрал популярных личностей, чтобы можно было оценить, как это может работать.»
     [179.8, 184.15]]                # (3-й, полный заход) CTA «Если хочешь получить полный промпт, пиши слово ЛИЦО в комментариях, я скину инструкцию.»


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
R = tighten(R)
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
mw, _ = TR._words("m.wav", prompt="ChatGPT, селфи, промпт, симметрию, пропорцию, линию челюсти, десятибалльной, ЛИЦО.")
dur = sum(b - a for a, b in R)
json.dump({"duration": dur, "ranges": R, "words": mw}, open("master_words.json", "w"), ensure_ascii=False, indent=1)
print("master", round(dur, 1)); print(" ".join(f"{w['w']}@{w['start']:.1f}" for w in mw))
