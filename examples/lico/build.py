"""LICO (12.10) — «Не кидай своё фото в ChatGPT, если не готов узнать правду».
Правки автора к этому ролику: в начале НЕ моушн-дизайн, а красивые субтитры + 3D-элементы, потом переход в «сочный» монтаж;
отчёты (картинки) показывать как видео — наезды, приближения на нужные строки; вставки из фильмов без подписей; 3D везде.
Тёмная тема. 3D — engine/assets/vendor/lico3d.js (хук «?/10» + «ПРАВДУ», скан лица MediaPipe, очки, итог «8,4», галерея).
Звук — finish.py (голос из оригинала без обработки, эффекты тише голоса)."""
import json
import shutil
import subprocess
import sys
from pathlib import Path

WD = Path(__file__).resolve().parents[1]
ENG = WD.parents[1] / "engine"
sys.path.insert(0, str(ENG))
from craft import Reel, render  # noqa: E402
from textpath import text_path  # noqa: E402

r = Reel(WD, theme="dark")
for x in r.words:
    w = x["w"]
    if w.startswith("промп") and not w.startswith("промпт"):
        x["w"] = "промпт" + w[5:]
    if w.startswith("симметр,"):
        x["w"] = "симметрию,"
    if w.startswith("пропор,"):
        x["w"] = "пропорции,"
    if w.startswith("-бальной"):
        x["w"] = "-балльной" + w[8:]
    if w.lower().startswith("лицо") and x["start"] > 55:
        x["w"] = "«ЛИЦО»"
    if w == "разбирает" and x["start"] > 20:
        x["w"] = "разбирать"
T, pop, js, sound, P = r.T, r.pop, r.js, r.sound, r.P
HF = WD / "craft" / "hf"
HF.mkdir(parents=True, exist_ok=True)
GOLD, CYAN, RED = "#F0C46A", "#47E5FF", P["red"]
for n in (21, 22, 23):
    shutil.copyfile(WD / "src" / f"card{n}.png", HF / f"card{n}.png")
shutil.copyfile(ENG / "assets" / "avatar.jpg", HF / "avatar.jpg")


def G(gid, a, b, *k, **kw):
    r.G(gid, a + 0.2 if a > 0.5 else a, b, *k, **kw)


def clip(vid, src, ss, se, t_in, t_out, crop=None, w=1000, h=563, top=285, left=None, speed=None, radius=30):
    """Видео-вставка: окно (или весь кадр). Скорость подгоняется под фразу, звук не берём."""
    need = t_out - t_in + 0.35
    sp = speed or max(0.5, min(4.0, (se - ss) / need))
    vf = (f"crop={crop}," if crop else "") + f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setpts=PTS/{sp:.4f},fps=30,format=yuv420p"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{ss:.3f}", "-t", f"{se - ss:.3f}", "-i", str(src), "-vf", vf, "-an",
                    "-c:v", "libx264", "-crf", "17", "-preset", "fast", "-movflags", "+faststart", str(HF / f"{vid}.mp4")], check=True)
    left = (1080 - w) // 2 if left is None else left
    r.parts.append(f'<video id="{vid}" class="clip vin" style="left:{left}px;top:{top}px;width:{w}px;height:{h}px;border-radius:{radius}px" '
                   f'src="{vid}.mp4" muted playsinline data-start="{t_in:.3f}" data-duration="{need:.3f}" data-track-index="4"></video>')
    js.append(f'tl.fromTo("#{vid}", {{opacity: 0, y: 50, scale: .94, rotationX: 12}}, {{opacity: 1, y: 0, scale: 1, rotationX: 0, '
              f'duration: 0.4, ease: "power3.out"}}, {t_in:.3f});')
    if t_out < r.dur - 0.3:
        js.append(f'tl.to("#{vid}", {{opacity: 0, y: -30, filter: "blur(12px)", duration: 0.3, ease: "power1.in"}}, {t_out:.3f});')


def canvas3d(cid, a, b):
    r.parts.append(f'<canvas id="{cid}" class="clip c3f" width="1080" height="1920" data-start="{a:.3f}" data-duration="{b - a + 0.5:.3f}" data-track-index="6"></canvas>')
    js.append(f'tl.fromTo("#{cid}", {{opacity: 0}}, {{opacity: 1, duration: 0.25}}, {a:.3f});')
    js.append(f'tl.to("#{cid}", {{opacity: 0, duration: 0.3}}, {b:.3f});')


# ---------- «отчёт как видео»: картинка в окне, камера наезжает на нужные строки ----------
CW, CH = 1055, 1491
ROWS = [355, 462, 557, 652, 747, 845, 943, 1043, 1150, 1262]  # центры строк «Оценки» на отчёте автора


def viewer(vid, img, box, radius=0, badges=False):
    x, y, w, h = box
    bd = "".join(f'<i class="bdg" style="left:466px;top:{c - 40}px"></i>' for c in ROWS) if badges else ""
    js.append(f'tl.set("#{vid} .vi", {{x: {(w - CW * 0.87) / 2:.1f}, y: {(h - CH * 0.87) / 2:.1f}, scale: 0.87}}, 0);')
    return (f'<div class="vw" id="{vid}" style="left:{x}px;top:{y}px;width:{w}px;height:{h}px;border-radius:{radius}px">'
            f'<div class="vt"><div class="vi"><img src="{img}">{bd}<div class="hl"></div></div></div></div>')


def focus(vid, box, reg, t, dur=0.7, smax=2.2, fill=0.92, cy=None, hl=True, sway=True, snd=True):
    """Наезд «камеры» на область отчёта reg=(x0, y0, x1, y1) в пикселях картинки; cy — где по высоте окна её поставить."""
    _, _, w, h = box
    x0, y0, x1, y1 = reg
    s = min(w * fill / (x1 - x0), h * fill / (y1 - y0), smax)
    tx, ty = w / 2 - s * (x0 + x1) / 2, (h / 2 if cy is None else cy) - s * (y0 + y1) / 2
    js.append(f'tl.to("#{vid} .vi", {{x: {tx:.1f}, y: {ty:.1f}, scale: {s:.3f}, duration: {dur}, ease: "power3.inOut"}}, {t:.3f});')
    if sway:  # объём: окно слегка «качается» в перспективе во время наезда
        js.append(f'tl.to("#{vid} .vt", {{rotationX: 7, rotationY: -8, duration: {dur / 2:.2f}, yoyo: true, repeat: 1, ease: "sine.inOut"}}, {t:.3f});')
    js.append(f'tl.to("#{vid} .hl", {{opacity: 0, duration: 0.15}}, {t:.3f});')
    if hl:
        js.append(f'tl.set("#{vid} .hl", {{left: {x0 - 6}, top: {y0 - 6}, width: {x1 - x0 + 12}, height: {y1 - y0 + 12}}}, {t + 0.16:.3f});')
        js.append(f'tl.fromTo("#{vid} .hl", {{opacity: 0, scale: 1.08}}, {{opacity: 1, scale: 1, duration: 0.3, ease: "power2.out"}}, {t + dur * 0.75:.3f});')
    if snd:
        sound("whoosh-short", t, 0.05)


# ---------- опорные моменты ----------
t_look = T("Смотри") - 0.1
t_scan = T("ChatGPT", T("промпт")) - 0.15
t_rep = T("Можно") - 0.1
t_toest = T("То", T("подобное")) - 0.1
t_end = T("И", T("подойдут")) - 0.1
t_tot = T("А", T("шкале")) - 0.1
t_not = T("И", T("шкале", t_tot)) - 0.1
t_pop = T("Я", T("дальнейшем")) - 0.1
t_cta = T("Если", T("работать")) - 0.1

r.states([(0, "full"), (t_look, "hide"), (t_scan, "card"), (t_rep, "hide"), (t_toest, "card"), (t_end, "hide"), (t_not, "full"),
          (t_pop, "hide"), (t_cta, "card")])
SCENES = []

# 0. ХУК — без моушн-дизайна: лицо на весь кадр, красивые субтитры по словам + 3D «?/10» над головой и золотое «ПРАВДУ»
HOOK = [("Не", "s", 1150), ("кидай", "s", 1150), ("своё|свое", "s", 1150), ("фото", "s", 1150),
        ("в", "b", 1222), ("ChatGPT,", "b", 1222), ("если", "s", 1352), ("не", "s", 1352), ("готов", "s", 1352), ("узнать", "s", 1352)]
lines = {}
for k, (wd, cls, y) in enumerate(HOOK):
    lines.setdefault((cls, y), []).append(f'<span class="hw" id="hw{k}">{wd.split("|")[0]}</span>')
G("g0", 0, t_look, "full0", "".join(f'<div class="hl_{c}" style="top:{y}px">{" ".join(s)}</div>' for (c, y), s in lines.items()), enter=False)
after = 0.0
for k, (wd, _, _) in enumerate(HOOK):
    t = T(wd.split("|")[-1].strip(","), after) if k else 0.0
    after = t + 0.01
    js.append(f'tl.fromTo("#hw{k}", {{opacity: 0, y: 28, filter: "blur(14px)"}}, {{opacity: 1, y: 0, filter: "blur(0px)", duration: 0.32, ease: "power3.out"}}, {max(0, t - 0.06):.3f});')
t_prav = T("правду") - 0.08
SCENES.append({"canvas": "c3h", "t0": 0, "t1": round(t_look + 0.1, 3), "mode": "hook", "pravT": round(t_prav, 3), "topY": 330, "pravY": 1520, "pravW": 860})
canvas3d("c3h", 0, t_look + 0.1)
js.append('tl.set("#c3h", {opacity: 1}, 0);')
sound("whoosh", 0.05, 0.05)
sound("whoosh-cinematic", t_prav - 0.2, 0.09)
sound("impact-bass-1", t_prav + 0.22, 0.12)

# 1. «Смотри, делаю селфи, кидаю в ChatGPT и вставляю вот этот промпт» — запись экрана 9:16 на весь кадр
clip("v1", WD / "src" / "screen.mp4", 0.1, 4.75, t_look, t_scan, w=1080, h=1920, top=0, radius=0)
G("g1", t_look, t_scan, "full0", '<div class="row r1"><span class="ch k0">📸 селфи</span><span class="ch k1">📝 промпт</span></div>'
  '', enter=False)
pop("#g1 .k0", T("селфи") - 0.1, "pop", 0.08)
pop("#g1 .k1", T("промпт") - 0.15, "pop", 0.08)

# 2. «ChatGPT разбирает симметрию, пропорцию, кожу, линию челюсти и собирает вот такой отчёт» — 3D-скан лица над карточкой
marks = [T("симметрию"), T("пропорции"), T("кожу"), T("линию")]
SCENES.append({"canvas": "c3s", "t0": round(t_scan, 3), "t1": round(t_rep, 3), "mode": "scan", "img": "face.png", "cx": 540, "cy": 552,
               "w": 424 * 1.02, "h": 520 * 1.02, "marks": [round(m - 0.1, 3) for m in marks]})
canvas3d("c3s", t_scan, t_rep)
CH_S = [("⚖️ симметрия", "l", 330), ("📐 пропорции", "r", 430), ("✨ кожа", "l", 580), ("🦴 челюсть", "r", 690)]
G("g2", t_scan, t_rep, "full0", "".join(f'<span class="ch sc{k} {s}" style="top:{y}px">{n}</span>' for k, (n, s, y) in enumerate(CH_S))
  + '<span class="ch rep">📄 готовый отчёт</span>', enter=False)
sound("glitch-2", t_scan + 0.3, 0.025)
for k, m in enumerate(marks):
    pop(f"#g2 .sc{k}", m - 0.12, "ping" if k % 2 == 0 else "click", 0.05)
pop("#g2 .rep", T("отчет") - 0.1, "pop", 0.08)

# 3. «Можно прям посмотреть, изучить по баллам… по привлекательности… насколько лицо симметрично» — отчёт как видео
BOXF = (0, 110, 1080, 1500)
G("g3", t_rep, t_toest, "full0", viewer("v3", "card21.png", BOXF, badges=True), enter=False)
js.append(f'tl.fromTo("#v3 .vt", {{opacity: 0, rotationX: 38, y: 260, scale: .8}}, {{opacity: 1, rotationX: 0, y: 0, scale: 1, duration: 0.7, ease: "power3.out"}}, {t_rep:.3f});')
sound("whoosh-cinematic", t_rep, 0.07)
focus("v3", BOXF, (20, 290, 600, 1320), T("баллам") - 0.35, hl=False)
js.append(f'tl.fromTo("#v3 .bdg", {{opacity: 0}}, {{opacity: 1, duration: 0.12, stagger: 0.09, yoyo: true, repeat: 1, repeatDelay: 0.05}}, {T("баллам"):.3f});')
# «Образцовый самец»: «Магнум» на «привлекательности» (без подписи — правило автора 10.10)
t_z0, t_z1 = T("привлекательности") - 0.25, T("Насколько") - 0.12
clip("f1", WD / "src" / "mag.mkv", 63.7, 66.2, t_z0, t_z1, crop="1280:530:0:110", w=1000, h=1180, top=260)
sound("sparkle", t_z0 + 0.1, 0.035)
focus("v3", BOXF, (20, 300, 600, 410), T("симметрично") - 0.55, smax=1.8)
focus("v3", BOXF, (20, 290, 600, 700), T("подобное") - 0.1, hl=False, snd=False)

# 4. «То есть разбирать сильные и слабые стороны, чтобы подтянуть стрижку или уход, или даже какие очки тебе подойдут»
BOXC = (40, 255, 1000, 590)
G("g4", t_toest, t_end, "full0", viewer("v4", "card21.png", BOXC, radius=34) + '<span class="ch tag4">💪 сильные · 🛠 слабые</span>', enter=False)
focus("v4", BOXC, (605, 548, 1045, 830), t_toest + 0.1, smax=2.0)
pop("#g4 .tag4", T("сильные") - 0.1, None)
focus("v4", BOXC, (605, 838, 1045, 1000), T("слабые") - 0.1, smax=2.0)
focus("v4", BOXC, (605, 888, 1045, 990), T("стрижку") - 0.3, smax=2.1)
# «Американский психопат»: маска на лицо — «уход»
t_a0, t_a1 = T("уход") - 0.12, T("очки") - 0.22
clip("f2", WD / "src" / "RjKNbfA64EE.mkv", 124.6, 126.4, t_a0, t_a1, crop="1280:560:0:88", w=1000, h=590, top=255, radius=34)
focus("v4", BOXC, (605, 1145, 1045, 1258), t_a1 - 0.05, smax=2.0, cy=470, snd=False)
SCENES.append({"canvas": "c3g", "t0": round(t_a1, 3), "t1": round(t_end, 3), "mode": "glasses", "cx": 540, "cy": 420, "width": 520})
canvas3d("c3g", t_a1, t_end)
sound("whoosh", t_a1, 0.06)
sound("ping", T("подойдут") - 0.1, 0.05)

# 5. «И в конце можно посмотреть по каждому пункту оценку по 10-балльной шкале» — проходим по баллам сверху вниз
G("g5", t_end, t_not, "full0", viewer("v5", "card21.png", BOXF, badges=True), enter=False)
js.append(f'tl.fromTo("#v5 .vt", {{opacity: 0, rotationY: -30, x: 300}}, {{opacity: 1, rotationY: 0, x: 0, duration: 0.6, ease: "power3.out"}}, {t_end:.3f});')
focus("v5", BOXF, (20, 290, 600, 1320), t_end, hl=False, snd=False)
t_b = T("каждому", t_end) - 0.1
step = max(0.18, (T("шкале", t_end) - t_b) / len(ROWS))
for k in range(len(ROWS)):
    js.append(f'tl.fromTo("#v5 .bdg:nth-of-type({k + 1})", {{opacity: 0, scale: 1.2}}, {{opacity: 1, scale: 1, duration: 0.18}}, {t_b + k * step:.3f});')
    sound("click-soft", t_b + k * step, 0.03)
# «А также полную оценку по 10-балльной шкале» — наезд на «Итог» + золотые 3D-цифры 0 → 8,4
focus("v5", BOXF, (20, 1330, 1040, 1488), t_tot, smax=1.05, cy=1150)
js.append(f'tl.to("#v5 .bdg", {{opacity: 0, duration: 0.2}}, {t_tot:.3f});')
SCENES.append({"canvas": "c3n", "t0": round(t_tot + 0.1, 3), "t1": round(t_not, 3), "mode": "score", "cx": 540, "cy": 560, "value": 8.4,
               "countT": round(T("полную") - 0.05, 3), "countD": 1.6})
canvas3d("c3n", t_tot + 0.1, t_not)
sound("riser", T("полную") - 0.4, 0.06)
sound("impact-bass-2", T("полную") + 1.55, 0.05)
sound("sparkle", T("полную") + 1.6, 0.035)

# 6. «И это не приговор, это ориентир для стиля» — лицо на весь кадр
G("g6", t_not, t_pop, "full0", '<span class="ch big vd"><s>⚖️ приговор</s></span><span class="ch big ok">🧭 ориентир для стиля</span>', enter=False)
pop("#g6 .vd", T("приговор") - 0.2, "error", 0.04)
js.append(f'tl.fromTo("#g6 .vd s", {{"--x": "0%"}}, {{"--x": "100%", duration: 0.25}}, {T("приговор") + 0.25:.3f});')
js.append(f'tl.to("#g6 .vd", {{opacity: .45, duration: 0.2}}, {T("ориентир") - 0.1:.3f});')
pop("#g6 .ok", T("ориентир") - 0.1, "chime", 0.05)

# 7. «Я также на примере разобрал популярных личностей, чтобы можно было оценить, как это может работать» — три отчёта в 3D;
# правка автора 12.10: «детальнее, под каждое слово что-то показывается» — камера по планам: Юра Борисов → его итог 7,9 →
# Брэд Питт → его оценки (глаза 9,4, челюсть 9,5) → итог 9,1
t_p1, t_p2, t_p3, t_p4 = T("популярных") - 0.15, T("личностей") - 0.2, T("оценить") - 0.3, T("работать") - 0.45
SCENES.append({"canvas": "c3p", "t0": round(t_pop, 3), "t1": round(t_cta, 3), "mode": "gallery", "imgs": ["card22.png", "card21.png", "card23.png"],
               "cardH": 860, "aspect": CW / CH, "cy": 930,
               "focus": [[round(t_pop, 3), 1], [round(T("разобрал") - 0.25, 3), 0], [round(t_p2, 3), 2]],
               "shots": [[round(t_pop, 3), 0, 0, 35.8], [round(t_p1, 3), 0.07, -0.43, 11], [round(t_p2, 3), 0, 0, 30],
                         [round(t_p3, 3), -0.22, 0.12, 15], [round(t_p4, 3), -0.33, -0.48, 10]]})
canvas3d("c3p", t_pop, t_cta)
G("g7", t_pop, t_cta, "full0", '<div class="pph">популярные <b>личности</b></div>'
  '<span class="ch big nm n1">🎬 Юра Борисов · <b>7,9</b></span><span class="ch big nm n2">🌟 Брэд Питт · <b>9,1</b></span>'
  '<span class="ch nm n3">👁 глаза 9,4 · 🗿 челюсть 9,5</span>', enter=False)
pop("#g7 .pph", t_pop + 0.1, None)
pop("#g7 .n1", t_p1 + 0.1, "pop", 0.06)
js.append(f'tl.to("#g7 .n1", {{opacity: 0, y: -20, duration: 0.2}}, {t_p2:.3f});')
pop("#g7 .n2", t_p2 + 0.15, "pop", 0.06)
pop("#g7 .n3", t_p3 + 0.2, "click", 0.05)
js.append(f'tl.to("#g7 .n3", {{opacity: 0, duration: 0.2}}, {t_p4:.3f});')
sound("whoosh-cinematic", t_pop, 0.08)
for t in (t_p1, t_p2, t_p3, t_p4):
    sound("whoosh-short", t, 0.05)
sound("sparkle", t_p4 + 0.4, 0.035)

# 8. CTA «Если хочешь получить полный промпт — пиши „ЛИЦО“ в комментариях, я скину инструкцию»
G("g8", t_cta, r.dur, "top", '<div class="hook2">полный <b>промпт</b></div>'
  '<div class="igc"><img class="iga" src="avatar.jpg"><div class="igf"><span class="igp">Добавьте комментарий…</span>'
  '<span class="igt" id="g8t">' + r.typed("ЛИЦО") + '</span><span class="igi">'
  '<svg viewBox="0 0 24 24"><rect x="3" y="3" width="18" height="18" rx="4"/><circle cx="9" cy="9" r="1.6"/><path d="M4 18l5-5 4 4 3-3 4 4"/></svg>'
  '<svg viewBox="0 0 24 24"><rect x="3" y="3" width="18" height="18" rx="4"/><text x="12" y="15.5" text-anchor="middle">GIF</text></svg></span>'
  '<span class="igs">Опубликовать</span></div></div>'
  '<div class="gift">📩 скину инструкцию</div>')
t_w = T("«ЛИЦО»", t_cta)
js.append(f'tl.to("#g8 .igp", {{opacity: 0, duration: 0.1}}, {t_w - 0.12:.3f});')
r.typing("#g8t", "ЛИЦО", t_w - 0.1, t_w + 0.45)
js.append(f'tl.to("#g8 .igi", {{opacity: 0, duration: 0.15}}, {t_w + 0.1:.3f});')
js.append(f'tl.fromTo("#g8 .igs", {{opacity: 0, x: 20}}, {{opacity: 1, x: 0, duration: 0.25}}, {t_w + 0.15:.3f});')
js.append(f'tl.fromTo("#g8 .igs", {{scale: 1}}, {{scale: 1.15, duration: 0.15, yoyo: true, repeat: 1}}, {T("комментариях") + 0.1:.3f});')
sound("notification", T("комментариях") + 0.1, 0.1)
pop("#g8 .gift", T("скину") - 0.1, "pop", 0.08)

# 3D-конфиг: контуры надписей из Inter 900 (y вверх — для Three.js)
GL = {"q": "?", "s10": "/10", "pravdu": "ПРАВДУ", "dc": ",", "tag0": "7,9", "tag1": "8,4", "tag2": "9,1", **{f"d{i}": str(i) for i in range(10)}}
glyphs = {k: dict(zip(("d", "w"), text_path(v, y_up=True))) for k, v in GL.items()}
mesh = json.load(open(WD / "craft" / "facemesh.json"))
LICO = {"glyphs": glyphs, "mesh": {"pts": mesh["pts"], "tess": mesh["tess"], "oval": mesh["oval"]}, "scenes": SCENES}
(HF / "lico.js").write_text("window.LICO = " + json.dumps(LICO, ensure_ascii=False) + ";", encoding="utf-8")
r.parts.insert(0, '<script src="lico.js"></script><script type="importmap">{"imports": {"three": "./assets/vendor/three.module.min.js"}}</script>'
               '<script type="module" src="assets/vendor/lico3d.js"></script>')
js.append(f'tl.to({{}}, {{duration: {r.dur:.2f}, onUpdate: () => {{ if (window.__arenaRender) window.__arenaRender(tl.time()); }}}}, 0);')

r.captions(keys=["ChatGPT,", "ChatGPT", "селфи,", "промпт.", "симметрию,", "пропорции,", "кожу,", "челюсти", "отчет.", "баллам,",
                 "привлекательности", "симметрично", "сильные", "слабые", "стрижку", "уход,", "очки", "оценку", "шкале.", "приговор,",
                 "ориентир", "личностей,", "промпт,", "«ЛИЦО»"], hide=[(0, t_look + 0.3)])

CSS = f"""
      .scene {{ z-index: 5; }}
      #cam, #cam video {{ filter: saturate(.95) contrast(1.06) brightness(1.02); }}
      .scene.full0 {{ top: 0; height: 1920px; align-items: stretch; justify-content: stretch; }}
      .scene.full0 .gw {{ position: relative; width: 1080px; height: 1920px; }}
      .scene.top {{ top: 270px; height: 570px; }}
      .scene.top .gw {{ display: flex; flex-direction: column; align-items: center; gap: 16px; }}
      .cap-card {{ top: 1650px; }} .cap-hide {{ top: 1650px; }}
      .cap .s, .cap .b {{ text-shadow: 0 4px 24px rgba(0,0,0,.85); }}
      .cap .k, .cap-card .k, .cap-hide .k {{ color: {GOLD}; }}
      video.vin {{ position: absolute; object-fit: cover; z-index: 6; opacity: 0; box-shadow: 0 30px 90px rgba(0,0,0,.6), 0 0 0 2px rgba(240,196,106,.35); }}
      .c3f {{ position: absolute; left: 0; top: 0; width: 1080px; height: 1920px; z-index: 5; pointer-events: none; opacity: 0; }}
      /* хук: субтитры-«титры» */
      .hl_s, .hl_b {{ position: absolute; left: 0; right: 0; text-align: center; color: #fff; text-shadow: 0 6px 30px rgba(0,0,0,.7), 0 1px 3px rgba(0,0,0,.6); }}
      .hl_s {{ font-family: "Playfair"; font-style: italic; font-weight: 700; font-size: 66px; }}
      .hl_b {{ font-weight: 900; font-size: 112px; letter-spacing: -2px; }}
      .hl_b .hw:last-child {{ color: {GOLD}; }}
      .cap {{ z-index: 8; }}
      .hw {{ display: inline-block; opacity: 0; }}
      /* чипы */
      .ch {{ position: absolute; font-weight: 800; font-size: 40px; color: #fff; background: rgba(3,6,12,.88); border: 2px solid rgba(240,196,106,.55);
             padding: 10px 26px; border-radius: 99px; opacity: 0; box-shadow: 0 20px 60px rgba(0,0,0,.5); white-space: nowrap; }}
      .row {{ position: absolute; left: 0; right: 0; display: flex; gap: 16px; justify-content: center; }}
      .row .ch {{ position: static; }}
      .r1 {{ top: 110px; }} #g1, #g4 {{ z-index: 7; }}
      .gptb {{ position: absolute; left: 50%; top: 300px; margin-left: -150px; width: 300px; text-align: center; font-weight: 900; font-size: 46px;
               color: #fff; background: #10A37F; border-radius: 22px; padding: 8px 0; opacity: 0; box-shadow: 0 20px 60px rgba(16,163,127,.45); }}
      .sc0, .sc2 {{ left: 50px; }} .sc1, .sc3 {{ right: 50px; }}
      #g2 .ch {{ font-size: 34px; padding: 8px 20px; border-color: rgba(71,229,255,.6); }}
      #g2 .rep {{ left: 50%; top: 770px; transform: translateX(-50%); border-color: {GOLD}; }}
      /* отчёт как видео */
      .vw {{ position: absolute; overflow: hidden; perspective: 1600px; }}
      .vt {{ position: absolute; inset: 0; transform-style: preserve-3d; }}
      .vi {{ position: absolute; left: 0; top: 0; width: {CW}px; height: {CH}px; transform-origin: 0 0; }}
      .vi img {{ width: {CW}px; height: {CH}px; display: block; border-radius: 22px; box-shadow: 0 40px 120px rgba(0,0,0,.7); }}
      #v4 {{ box-shadow: 0 0 0 2px rgba(240,196,106,.45), 0 30px 90px rgba(0,0,0,.6); background: #F4F1EA; }}
      .hl {{ position: absolute; left: 0; top: 0; border: 5px solid {GOLD}; border-radius: 20px; opacity: 0;
             box-shadow: 0 0 40px rgba(240,196,106,.8), inset 0 0 30px rgba(240,196,106,.25); }}
      .bdg {{ position: absolute; width: 126px; height: 80px; border-radius: 18px; border: 4px solid {GOLD}; opacity: 0;
              box-shadow: 0 0 30px rgba(240,196,106,.9); }}
      .tag4 {{ left: 50%; top: 770px; transform: translateX(-50%); }}
      .big {{ font-size: 50px; padding: 12px 34px; }}
      .vd {{ left: 50%; top: 170px; transform: translateX(-50%); border-color: {RED}; }}
      .vd s {{ --x: 0%; text-decoration: none; background-image: linear-gradient({RED}, {RED}); background-repeat: no-repeat;
               background-position: 0 55%; background-size: var(--x) 7px; }}
      .ok {{ left: 50%; top: 290px; transform: translateX(-50%); border-color: {GOLD}; }}
      .pph {{ position: absolute; left: 0; right: 0; top: 190px; text-align: center; font-family: "Playfair"; font-style: italic; font-weight: 700;
              font-size: 64px; color: #fff; opacity: 0; text-shadow: 0 6px 30px rgba(0,0,0,.7); background: rgba(3,6,12,.82); width: fit-content; margin: 0 auto; padding: 4px 34px; border-radius: 24px; }}
      .nm {{ left: 50%; top: 300px; transform: translateX(-50%); }} .nm b {{ color: {GOLD}; }} .n3 {{ top: 400px; }}
      .pph b {{ font-family: "Inter"; font-style: normal; font-weight: 900; color: {GOLD}; }}
      /* CTA */
      .hook2 {{ font-weight: 900; font-size: 52px; color: #fff; background: rgba(3,6,12,.88); padding: 10px 30px; border-radius: 24px;
                border: 2px solid rgba(240,196,106,.4); }}
      .hook2 b {{ color: {GOLD}; }}
      .igc {{ width: 980px; display: flex; align-items: center; gap: 22px; background: #fff; border-radius: 26px; padding: 18px 22px;
              box-shadow: 0 24px 80px rgba(0,0,0,.45); }}
      .iga {{ width: 96px; height: 96px; border-radius: 50%; object-fit: cover; flex: none; }}
      .igf {{ position: relative; flex: 1; height: 96px; border: 2px solid #DBDBDB; border-radius: 99px; display: flex; align-items: center; padding: 0 26px; }}
      .igp {{ position: absolute; left: 30px; font-family: Inter, sans-serif; font-weight: 500; font-size: 40px; color: #737373; }}
      .igt {{ font-family: Inter, sans-serif; font-weight: 600; font-size: 44px; color: #000; letter-spacing: 1px; }}
      .igi {{ position: absolute; right: 22px; display: flex; gap: 22px; }}
      .igi svg {{ width: 58px; height: 58px; fill: none; stroke: #000; stroke-width: 2.2; }}
      .igi svg circle {{ fill: #000; stroke: none; }} .igi svg text {{ font: 900 6.5px Inter, sans-serif; fill: #000; stroke: none; }}
      .igs {{ position: absolute; right: 26px; font-family: Inter, sans-serif; font-weight: 700; font-size: 40px; color: #0095F6; opacity: 0; }}
      .gift {{ position: static; font-weight: 800; font-size: 42px; color: #fff; background: rgba(3,6,12,.88); padding: 12px 30px; border-radius: 99px; opacity: 0; }}
"""

if __name__ == "__main__":
    r.write(CSS)
    # длинные хвосты звуков (riser 10 с, удар 2,6 с) режем — иначе на паузах голоса эффекты громче (замер 12.10)
    sf = json.load(open(HF / "sfx.json", encoding="utf-8"))
    for e in sf:
        if e["file"].endswith("riser.mp3"):
            e["dur"] = 2.0
        if e["file"].endswith("impact-bass-2.mp3"):
            e["dur"] = 1.2
    (HF / "sfx.json").write_text(json.dumps(sf, ensure_ascii=False, indent=1), encoding="utf-8")
    if "--render" in sys.argv:
        print(render(WD, int(sys.argv[sys.argv.index("--render") + 1])))
