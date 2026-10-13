"""ARENA (12.10) — скилл Arena: «устрой сотне копий Claude турнир на вылет».
Тёмная тема. Состояния: card (лицо в карточке снизу, графика 260–840 px) и hide (полноэкранная 3D-арена).
Герой ролика — 3D-арена: 100 логотипов Claude спавнятся волной (×100), делятся на 4 стратегии, дерутся, вылетают по раундам
100→50→25→12→6→3→1, победитель — в короне. Вставки: запись экрана установки (src/IMG_9354/9355), «Гладиатор» (без подписи,
правило автора 10.10). Звук — finish.py (голос из оригинала без обработки)."""
import random
import re
import subprocess
import sys
from pathlib import Path

WD = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WD.parents[1] / "engine"))
from craft import Reel, render  # noqa: E402

FIX = {"бизнесом": "бизнесам", "Арена": "Арена", "арена": "Арена", "промп,": "промпт,", "средне,": "средне,"}
r = Reel(WD, theme="dark")
for x in r.words:
    k = x["w"].strip("«».,")
    if k in ("бизнесом",):
        x["w"] = "бизнесам"
    if x["w"].startswith("промп") and not x["w"].startswith("промпт"):
        x["w"] = "промпт" + x["w"][5:]
    if k.lower() == "арена" and x["start"] > 50:
        x["w"] = "«АРЕНА»"
T, pop, js, sound, P = r.T, r.pop, r.js, r.sound, r.P
HF = WD / "craft" / "hf"
HF.mkdir(parents=True, exist_ok=True)
GREEN, RED, ORANGE = P["green"], P["red"], "#D97757"
PATH = re.search(r'd="([^"]+)"', (WD.parents[1] / "engine" / "assets" / "logos" / "claude.svg").read_text()).group(1)
random.seed(12)


def G(gid, a, b, *k, **kw):
    """Сцена входит через 0,2 с после ухода предыдущей — надписи не наезжают."""
    r.G(gid, a + 0.2 if a > 0.5 else a, b, *k, **kw)


def stamp(sel, t, snd="impact-bass-1", vol=0.08, rot=-3):
    js.append(f'tl.fromTo("{sel}", {{opacity: 0, scale: 1.8, rotation: {rot - 3}}}, {{opacity: 1, scale: 1, rotation: {rot}, '
              f'duration: 0.3, ease: "back.out(2)"}}, {t:.3f});')
    if snd:
        sound(snd, t, vol)


def clip(vid, src, ss, se, t_in, t_out, crop=None, w=1000, h=563, top=285, speed=None):
    """Видео-вставка в окне над карточкой (или на весь кадр при top=None). Скорость подгоняется под фразу."""
    need = t_out - t_in + 0.35
    sp = speed or max(0.5, min(4.0, (se - ss) / need))
    vf = (f"crop={crop}," if crop else "") + f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setpts=PTS/{sp:.4f},fps=30,format=yuv420p"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{ss:.3f}", "-t", f"{se - ss:.3f}", "-i", str(src), "-vf", vf, "-an",
                    "-c:v", "libx264", "-crf", "17", "-preset", "fast", "-movflags", "+faststart", str(HF / f"{vid}.mp4")], check=True)
    style = f"left:{(1080 - w) // 2}px;top:{top}px;width:{w}px;height:{h}px"
    r.parts.append(f'<video id="{vid}" class="clip vin" style="{style}" src="{vid}.mp4" muted playsinline '
                   f'data-start="{t_in:.3f}" data-duration="{need:.3f}" data-track-index="4"></video>')
    js.append(f'tl.fromTo("#{vid}", {{opacity: 0, y: 50, scale: .94, rotationX: 12}}, {{opacity: 1, y: 0, scale: 1, rotationX: 0, '
              f'duration: 0.45, ease: "power3.out"}}, {t_in:.3f});')
    if t_out < r.dur - 0.3:
        js.append(f'tl.to("#{vid}", {{opacity: 0, y: -30, filter: "blur(12px)", duration: 0.3, ease: "power1.in"}}, {t_out:.3f});')
    sound("whoosh-short", t_in, 0.08)


POS = {}


def arena(aid, n=100, groups=False):
    """3D-арена: пол-амфитеатр под наклоном + n логотипов Claude, стоящих на полу (контр-поворот). Координаты — детерминированные."""
    logos = []
    cols = 10
    for i in range(n):
        gx, gy = i % cols, i // cols
        x = 90 + gx * 82 + random.uniform(-14, 14)
        y = 90 + gy * 82 + random.uniform(-14, 14)
        g = (gx // 3 + (gy // 5) * 2) % 4 if groups else 0
        POS[(aid, i)] = (x, y)
        logos.append(f'<div class="lg g{g}" style="left:{x:.0f}px;top:{y:.0f}px"><div class="st"><svg viewBox="0 0 24 24"><use href="#cl"/></svg></div></div>')
    return (f'<div class="ar" id="{aid}"><div class="stage"><div class="floor"><div class="ring r1"></div><div class="ring r2"></div>'
            f'<div class="ring r3"></div><div class="sand"></div>{"".join(logos)}</div></div>'
            f'<div class="crowd"></div><div class="beam b1"></div><div class="beam b2"></div></div>')


# ---------- опорные моменты ----------
t_skill = T("Это") - 0.1
t_type = T("Ты") - 0.1
t_strat = T("У", T("задачу")) - 0.1
t_tour = T("А", T("сложного")) - 0.1
t_fight = T("Они") - 0.1
t_win = T("И", T("баллы")) - 0.1
t_lim = T("Конечно") - 0.1
t_meter = T("но", t_lim) - 0.1
t_bug = T("Но", T("съедает")) - 0.1
t_biz = T("Я", T("помогает")) - 0.1
t_cta = T("Если", T("людей")) - 0.1
t_cta2 = T("пиши", t_cta) - 0.1

r.states([(0, "card"), (t_skill, "hide"), (t_strat, "card"), (t_fight, "hide"), (t_lim, "card"), (t_cta, "hide"), (t_cta2, "card")])
r.parts.append(f'<svg width="0" height="0" style="position:absolute"><symbol id="cl" viewBox="0 0 24 24"><path d="{PATH}"/></symbol></svg>')

# 1. ХУК: Claude отвечает «средне» → не переписывай промпт → сотня копий, турнир на вылет
G("g1", 0, t_skill, "top",
  '<div class="h3"><span class="meh">😐 отвечает средне</span><span class="nop"><span class="pr">✏️ переписать промпт</span></span></div>'
  '<b class="t100">×100</b><div class="tv">ТУРНИР <em>НА ВЫЛЕТ</em></div>', enter=False)
pop("#g1 .meh", T("средне") - 0.1, "error", 0.06)
pop("#g1 .nop", T("не", T("средне")) - 0.1, None)
js.append(f'tl.to("#g1 .pr", {{"--x": "100%", opacity: .5, duration: 0.25}}, {T("переписывая") + 0.1:.3f});')
js.append(f'tl.to("#g1 .h3", {{opacity: 0, y: -30, filter: "blur(10px)", duration: 0.25}}, {T("устрой") - 0.1:.3f});')
sound("whoosh-cinematic", T("устрой") - 0.05, 0.12)
sound("impact-bass-2", T("устрой"), 0.08)
stamp("#g1 .t100", T("сотни") - 0.05, "impact-bass-1", 0.09, -2)
stamp("#g1 .tv", T("турнир") - 0.05, "impact-bass-2", 0.09, 2)

# 2. «Это скилл Арена для Claude Code. Бесплатный, код открытый» — запись экрана 9:16 на весь кадр (правка автора 12.10)
clip("v1", WD / "src" / "IMG_9354.mp4", 0.5, 16.5, t_skill, t_type, w=1080, h=1920, top=0)
G("g2", t_skill, t_type, "tags", '<div class="row"><span class="ch k0">⚔️ скилл <b>Arena</b></span><span class="ch k1">🆓 бесплатно</span>'
  '<span class="ch k2">🔓 код открыт</span></div>', enter=False)
pop("#g2 .k0", T("Арена") - 0.15, "pop", 0.08)
pop("#g2 .k1", T("бесплатный") - 0.1, "click", 0.08)
pop("#g2 .k2", T("код", T("бесплатный")) - 0.1, "click", 0.08)

# 3. ПОЛНОЭКРАННАЯ 3D-АРЕНА: «пишешь „арена“ → Claude Code запускает сотни субагентов… одну и ту же задачу»
G("g3", t_type, t_strat, "center", '<canvas id="c3d1" class="c3d" width="1080" height="1920"></canvas><div class="term"><span class="pp">›</span><span id="g3t">' + r.typed("arena") + '</span><span class="cur"></span></div>'
  + '<div class="hud"><b id="cnt">0</b><span>копий Claude</span></div><div class="task">🎯 одна задача</div>', enter=False)
js.append(f'tl.fromTo("#g3 .term", {{opacity: 0, y: -30}}, {{opacity: 1, y: 0, duration: 0.35}}, {t_type + 0.25:.3f});')
r.typing("#g3t", "arena", T("пишешь") - 0.05, T("Арена", t_type) + 0.4)
sound("riser", T("запускает") - 0.3, 0.08)
for k in range(10):
    sound("pop", T("запускает") + k * 0.28, 0.035)
js.append(f'countUp("#cnt", 0, 100, {T("запускает") - 0.05:.3f}, 3.0);')
js.append(f'tl.fromTo("#g3 .hud", {{opacity: 0, scale: .6}}, {{opacity: 1, scale: 1, duration: 0.4, ease: "back.out(2)"}}, {T("запускает") - 0.1:.3f});')
pop("#g3 .task", T("одну", T("копий")) - 0.1, "ping", 0.09)

# 4. «У каждого своя стратегия: с начала, с конца, с простого, со сложного» — 4 отряда (лицо в карточке)
STR = [("⏮️", "с начала", "#3AA8FF"), ("⏭️", "с конца", "#A78BFA"), ("🟢", "с простого", "#22C55E"), ("🔥", "со сложного", "#F97316")]
G("g4", t_strat, t_tour, "top", '<div class="hd">у каждой копии — <b>своя стратегия</b></div><div class="sq">'
  + "".join(f'<div class="sg s{k}" style="--c:{c}"><span>{e} {n}</span></div>' for k, (e, n, c) in enumerate(STR)) + '</div>')
for k, w in enumerate(["начала", "конца", "простого", "сложного"]):
    js.append(f'tl.fromTo("#g4 .s{k}", {{opacity: 0, y: 40, rotationY: 40}}, {{opacity: 1, y: 0, rotationY: 0, duration: 0.4, ease: "back.out(1.8)"}}, {T(w, t_strat) - 0.15:.3f});')
    sound("click", T(w, t_strat) - 0.15, 0.08)

# 5. «А дальше начинается турнир на вылет» — «Гладиатор», бой на арене
clip("f1", WD / "src" / "glad.mkv", 40.0, 43.0, t_tour, t_fight)
G("g5", t_tour, t_fight, "tags", '<div class="row"><span class="tt">ТУРНИР <em>НА ВЫЛЕТ</em></span></div>', enter=False)
stamp("#g5 .tt", T("турнир", t_tour) - 0.05, "impact-bass-2", 0.09, -2)

# 6. ПОЛНОЭКРАННЫЙ БОЙ: «разносят решения друг друга, защищаются, судья ставит баллы» → 100→1
ROUNDS = [100, 50, 25, 12, 6, 3, 1]
G("g6", t_fight, t_lim, "center", '<canvas id="c3d2" class="c3d" width="1080" height="1920"></canvas>' + '<div class="hud"><span>осталось</span><b id="cnt2">100</b></div>'
  '<div class="judge">⚖️ судья: <b id="sc">0</b> баллов</div>', enter=False)
order = list(range(100))
random.shuffle(order)
win = order[-1]
t0, span = t_fight + 0.5, (T("одно") - 0.1) - (t_fight + 0.5)
for k in range(1, len(ROUNDS)):
    out = order[100 - ROUNDS[k - 1]:100 - ROUNDS[k]]
    tk = t0 + span * (k - 1) / (len(ROUNDS) - 1)
    js.append(f'countUp("#cnt2", {ROUNDS[k - 1]}, {ROUNDS[k]}, {tk:.3f}, 0.35);')
    sound("glitch-1", tk, 0.05)
js.append(f'countUp("#sc", 0, 97, {T("судья") - 0.1:.3f}, 0.8);')
pop("#g6 .judge", T("судья") - 0.15, "ping", 0.08)
import json as _json
R3 = [{"t": round(t0 + span * (k - 1) / (len(ROUNDS) - 1), 3), "ids": order[100 - ROUNDS[k - 1]:100 - ROUNDS[k]]} for k in range(1, len(ROUNDS))]
ARENA = {"path": PATH, "scenes": [
    {"canvas": "c3h", "t0": 0, "t1": round(t_skill + 0.3, 3), "mode": "hook", "dullT": round(T("тупить") - 0.1, 3),
     "burstT": round(T("устрой") - 0.05, 3), "fightT": round(T("турнир") - 0.05, 3)},
    {"canvas": "c3s", "t0": round(t_strat, 3), "t1": round(t_tour + 0.3, 3), "mode": "squads",
     "appear": [round(T(w, t_strat) - 0.15, 3) for w in ["начала", "конца", "простого", "сложного"]]},
    {"canvas": "c3d1", "t0": round(t_type, 3), "t1": round(t_strat + 0.5, 3), "mode": "spawn", "spawn": round(T("запускает") - 0.05, 3)},
    {"canvas": "c3d2", "t0": round(t_fight, 3), "t1": round(t_lim + 0.5, 3), "mode": "fight", "groups": True, "rounds": R3, "win": win,
     "winT": round(T("одно") - 0.1, 3), "crownT": round(T("самое", T("одно")) - 0.1, 3)}]}
for cid, a0, a1 in [("c3h", 0, t_skill + 0.3), ("c3s", t_strat, t_tour + 0.3)]:
    r.parts.append(f'<canvas id="{cid}" class="clip c3f" width="1080" height="1920" data-start="{a0:.3f}" data-duration="{a1 - a0:.3f}" data-track-index="6"></canvas>')
r.parts.insert(0, '<script>window.ARENA = ' + _json.dumps(ARENA) + ';</script>'
               '<script type="importmap">{"imports": {"three": "./assets/vendor/three.module.min.js"}}</script>'
               '<script type="module" src="assets/vendor/arena3d.js"></script>')
# дублёр hf-seek: таймлайн GSAP тоже перерисовывает 3D (рендер HyperFrames сикает таймлайн с событиями — проверено countUp)
js.append(f'tl.to({{}}, {{duration: {r.dur:.2f}, onUpdate: () => {{ if (window.__arenaRender) window.__arenaRender(tl.time()); }}}}, 0);')
sound("impact-bass-1", T("одно") - 0.1, 0.1)
sound("sparkle", T("самое", T("одно")) - 0.1, 0.1)

# 7. «Конечно, 100 агентов дают самое сильное решение» — «Гладиатор»: Максимус раскидывает руки перед толпой
clip("f2", WD / "src" / "glad.mkv", 74.6, 77.6, t_lim, t_meter)
G("g7", t_lim, t_meter, "tags", '<div class="row"><span class="tt">САМОЕ <em>СИЛЬНОЕ</em> 👑</span></div>', enter=False)
stamp("#g7 .tt", T("сильное", t_lim) - 0.1, None)

# 8. «100 агентов — самое сильное решение, но очень много лимитов съедает» — шкала лимита пустеет
G("g8", t_meter, t_bug, "top", '<div class="lim"><div class="lh"><span>⚡ лимит Claude</span><b id="lp">100%</b></div><div class="bar"><i></i></div>'
  '<div class="lrow"><span class="ch q1 warn">🔥 100 агентов съедают много лимита</span></div></div>')
js.append(f'tl.fromTo("#g8 .bar i", {{width: "100%"}}, {{width: "8%", duration: 1.4, ease: "power2.in"}}, {T("лимитов") - 0.3:.3f});')
js.append(f'countUp("#lp", 100, 8, {T("лимитов") - 0.3:.3f}, 1.4, "%");')
pop("#g8 .q1", T("съедает") - 0.15, "error", 0.06)

# 9. «Но если задача сложная и нужно найти баги — реально помогает»
G("g9", t_bug, t_biz, "top", '<div class="hd">сложная задача → <b>Арена</b></div><div class="bugs">'
  + "".join(f'<span class="bg b{k}">🐞</span>' for k in range(6)) + '</div><div class="row"><span class="ch ok">✅ реально помогает</span></div>')
js.append(f'tl.fromTo("#g9 .bg", {{opacity: 0, scale: 0}}, {{opacity: 1, scale: 1, duration: 0.3, stagger: 0.08, ease: "back.out(2)"}}, {T("баги") - 0.6:.3f});')
js.append(f'tl.to("#g9 .bg", {{opacity: 0.15, scale: 0.6, rotation: 90, filter: "grayscale(1)", duration: 0.2, stagger: 0.12}}, {T("баги") + 0.4:.3f});')
for k in range(6):
    sound("click", T("баги") + 0.4 + k * 0.12, 0.06)
pop("#g9 .ok", T("помогает") - 0.2, "ping", 0.09)

# 10. «Я собираю бизнесам агентов, которые работают вместо людей»
G("g10", t_biz, t_cta, "top", '<div class="hook2">собираю бизнесам <b>ИИ-агентов</b></div>'
  '<div class="row"><span class="ch w0">🤖 работают вместо людей</span><span class="ch w1">24/7</span></div>')
pop("#g10 .w0", T("работают") - 0.15, "pop", 0.08)
pop("#g10 .w1", T("людей") - 0.1, "click", 0.08)

# 10б. «ТРИ РАЗРЕЗА» (правка автора 12.10): «Если хочешь установить себе этот скилл…» — три экрана в 3D-перспективе:
# установка (запись экрана) / автор / готово (запись экрана)
def panel(vid, src, ss, se, t_in, t_out, top, rot, crop, delay):
    need = t_out - t_in + 0.35
    sp = max(0.5, min(5.0, (se - ss) / need))
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{ss:.3f}", "-t", f"{se - ss:.3f}", "-i", str(src), "-vf",
                    f"crop={crop},scale=960:540,setpts=PTS/{sp:.4f},fps=30,format=yuv420p", "-an", "-c:v", "libx264", "-crf", "17",
                    "-preset", "fast", "-movflags", "+faststart", str(HF / f"{vid}.mp4")], check=True)
    r.parts.append(f'<video id="{vid}" class="clip tri" style="top:{top}px;--r:{rot}deg" src="{vid}.mp4" muted playsinline '
                   f'data-start="{t_in:.3f}" data-duration="{need:.3f}" data-track-index="4"></video>')
    js.append(f'tl.fromTo("#{vid}", {{opacity: 0, x: {-700 if rot > 0 else 700}, rotationY: {rot * 3}}}, {{opacity: 1, x: 0, rotationY: {rot}, '
              f'duration: 0.45, ease: "power3.out"}}, {t_in + delay:.3f});')
    js.append(f'tl.to("#{vid}", {{opacity: 0, scale: .9, filter: "blur(10px)", duration: 0.3}}, {t_out:.3f});')
    sound("whoosh-short", t_in + delay, 0.07)


G("g10b", t_cta, t_cta2, "center", '<div class="tribg"></div>', enter=False)
panel("p1", WD / "src" / "IMG_9354.mp4", 6.0, 12.0, t_cta, t_cta2, 190, 12, "1080:608:0:110", 0.0)
panel("p2", WD / "master.mp4", t_cta, t_cta2 + 0.4, t_cta, t_cta2, 715, -12, "1440:810:0:830", 0.12)
panel("p3", WD / "src" / "IMG_9355.mp4", 0.2, 4.5, t_cta, t_cta2, 1240, 12, "1080:608:0:150", 0.24)

# 11. CTA «Если хочешь установить себе этот скилл — пиши „Арена“, скину полную инструкцию»
import shutil
shutil.copyfile(WD.parents[1] / "engine" / "assets" / "avatar.jpg", HF / "avatar.jpg")
G("g11", t_cta2, r.dur, "top", '<div class="hook2">установить себе <b>Арену</b></div>'
  '<div class="igc"><img class="iga" src="avatar.jpg"><div class="igf"><span class="igp">Добавьте комментарий…</span>'
  '<span class="igt" id="g11t">' + r.typed("АРЕНА") + '</span><span class="igi">'
  '<svg viewBox="0 0 24 24"><rect x="3" y="3" width="18" height="18" rx="4"/><circle cx="9" cy="9" r="1.6"/><path d="M4 18l5-5 4 4 3-3 4 4"/></svg>'
  '<svg viewBox="0 0 24 24"><rect x="3" y="3" width="18" height="18" rx="4"/><text x="12" y="15.5" text-anchor="middle">GIF</text></svg></span>'
  '<span class="igs">Опубликовать</span></div></div>'
  '<div class="gift">📩 скину полную инструкцию</div>')
t_w = T("АРЕНА", t_cta)
js.append(f'tl.to("#g11 .igp", {{opacity: 0, duration: 0.1}}, {t_w - 0.12:.3f});')
r.typing("#g11t", "АРЕНА", t_w - 0.1, t_w + 0.5)
js.append(f'tl.to("#g11 .igi", {{opacity: 0, duration: 0.15}}, {t_w + 0.1:.3f});')
js.append(f'tl.fromTo("#g11 .igs", {{opacity: 0, x: 20}}, {{opacity: 1, x: 0, duration: 0.25}}, {t_w + 0.15:.3f});')
js.append(f'tl.fromTo("#g11 .igs", {{scale: 1}}, {{scale: 1.15, duration: 0.15, yoyo: true, repeat: 1}}, {T("комментариях") + 0.1:.3f});')
sound("notification", T("комментариях") + 0.1, 0.1)
pop("#g11 .gift", T("скину") - 0.1, "pop", 0.1)

r.captions(keys=["средне,", "промпт,", "сотни", "турнир", "Арена", "бесплатный,", "открытый.", "«Арена»", "субагентов,", "копий,", "стратегия,",
                 "вылет.", "баллы.", "сильное.", "лимитов", "баги,", "агентов,", "людей.", "«АРЕНА»"], hide=[])

CSS = f"""
      .scene {{ z-index: 5; }}
      #cam, #cam video {{ filter: saturate(.92) contrast(1.06) brightness(1.03); }}
      .scene.top {{ top: 270px; height: 570px; }}
      .scene.top .gw {{ display: flex; flex-direction: column; align-items: center; gap: 16px; }}
      .scene.tags {{ top: 770px; height: 80px; z-index: 6; }}
      .scene.center {{ top: 0; height: 1920px; padding: 0; background: radial-gradient(ellipse at 50% 55%, #1a1206 0%, #07080d 60%, #03060C 100%); }}
      .scene.center .gw {{ width: 1080px; height: 1920px; position: relative; }}
      .cap-card {{ top: 1650px; }} .cap-hide {{ top: 1640px; }}
      .cap .s, .cap .b {{ text-shadow: 0 4px 24px rgba(0,0,0,.8); }}
      video.vin {{ position: absolute; object-fit: cover; z-index: 4; opacity: 0; border-radius: 30px;
                   box-shadow: 0 30px 90px rgba(217,119,87,.35), 0 0 0 2px rgba(255,180,140,.25); }}
      svg {{ fill: {ORANGE}; }}
      .ch {{ font-weight: 800; font-size: 40px; color: #fff; background: rgba(3,6,12,.9); border: 2px solid rgba(217,119,87,.55);
             padding: 10px 26px; border-radius: 99px; opacity: 0; box-shadow: 0 20px 60px rgba(0,0,0,.5); }}
      .ch b {{ color: #FFB38A; }} .ch.warn {{ border-color: {RED}; }} .ch.ok {{ border-color: {GREEN}; }}
      .row {{ display: flex; gap: 14px; justify-content: center; align-items: center; }}
      .hd, .hook2 {{ font-weight: 900; font-size: 52px; color: #fff; background: rgba(3,6,12,.88); padding: 10px 30px; border-radius: 24px;
                     border: 2px solid rgba(217,119,87,.35); }}
      .hd b, .hook2 b {{ color: #FFB38A; }}
      .tt, .tv {{ font-weight: 900; font-size: 64px; color: #fff; background: rgba(3,6,12,.9); padding: 6px 30px; border-radius: 20px;
                  letter-spacing: 1px; opacity: 0; border: 3px solid {ORANGE}; }}
      .tt em, .tv em {{ font-style: normal; color: {ORANGE}; }}
      /* хук */
      .chat {{ width: 940px; background: rgba(12,19,33,.96); border: 2px solid {P['line']}; border-radius: 32px; padding: 22px 26px;
               display: flex; flex-direction: column; gap: 16px; opacity: 0; }}
      .chat .me {{ align-self: flex-end; background: #1C2840; color: #fff; font-weight: 700; font-size: 34px; padding: 14px 22px; border-radius: 24px 24px 6px 24px; }}
      .chat .ai {{ display: flex; align-items: center; gap: 18px; }}
      .ava svg {{ width: 64px; height: 64px; }}
      .lines {{ flex: 1; display: flex; flex-direction: column; gap: 10px; }}
      .lines i {{ display: block; height: 16px; border-radius: 9px; background: #2A3550; width: 0; }} .lines i.s {{ max-width: 60%; }}
      .meh {{ font-weight: 900; font-size: 36px; color: #FDE68A; background: rgba(245,158,11,.15); padding: 8px 18px; border-radius: 16px; opacity: 0; }}
      .nop {{ opacity: 0; }}
      .pr {{ --x: 0%; font-weight: 900; font-size: 46px; color: #fff; background: rgba(3,6,12,.88); padding: 8px 26px; border-radius: 20px;
             background-image: linear-gradient({RED}, {RED}); background-repeat: no-repeat; background-position: 0 55%; background-size: var(--x) 7px; }}
      .burst {{ position: absolute; left: 540px; top: 230px; width: 0; height: 0; }}
      .burst svg {{ position: absolute; width: 58px; height: 58px; margin: -29px; opacity: 0; filter: drop-shadow(0 0 14px rgba(217,119,87,.7)); }}
      .t100 {{ position: absolute; left: 0; right: 0; top: 30px; z-index: 6; text-align: center; font-weight: 900; font-size: 140px; color: #fff;
               text-shadow: 0 0 40px rgba(217,119,87,.9); opacity: 0; }}
      .tv {{ position: absolute; top: 150px; z-index: 6; white-space: nowrap; }}
      /* 3D-арена */
      .ar {{ position: absolute; inset: 0; perspective: 1500px; perspective-origin: 50% 30%; }}
      .stage {{ position: absolute; left: 50%; top: 52%; width: 1000px; height: 1000px; margin: -500px 0 0 -500px; transform-style: preserve-3d;
                transform: rotateX(58deg); }}
      .floor {{ position: absolute; inset: 0; transform-style: preserve-3d; border-radius: 50%; }}
      .sand {{ position: absolute; inset: 60px; border-radius: 50%; background: radial-gradient(circle, #d9a065 0%, #a8693a 55%, #5b3418 100%);
               box-shadow: inset 0 0 120px rgba(0,0,0,.6); }}
      .ring {{ position: absolute; border-radius: 50%; border: 18px solid #3a2414; }}
      .r1 {{ inset: 30px; border-color: #5a3a22; }} .r2 {{ inset: -40px; border-color: #3a2414; border-width: 40px; }}
      .r3 {{ inset: -120px; border-color: #24160c; border-width: 60px; box-shadow: 0 0 80px rgba(217,119,87,.25); }}
      .lg {{ position: absolute; width: 70px; height: 70px; margin: -35px; transform-style: preserve-3d; }}
      .lg .st {{ width: 70px; height: 70px; transform: rotateX(-58deg) translateZ(35px); transform-origin: 50% 100%; }}
      .lg svg {{ width: 70px; height: 70px; filter: drop-shadow(0 6px 10px rgba(0,0,0,.6)) drop-shadow(0 0 8px rgba(217,119,87,.6)); }}
      .lg.g1 svg {{ fill: #A78BFA; }} .lg.g2 svg {{ fill: #22C55E; }} .lg.g3 svg {{ fill: #F97316; }} .lg.g0 svg {{ fill: #3AA8FF; }}
      #a1 .lg svg {{ fill: {ORANGE}; }}
      .crowd {{ position: absolute; left: 0; right: 0; top: 0; height: 520px; background:
                radial-gradient(ellipse at 50% 120%, rgba(217,119,87,.25), rgba(0,0,0,0) 60%),
                repeating-linear-gradient(90deg, rgba(255,255,255,.04) 0 6px, rgba(0,0,0,0) 6px 18px); opacity: .8; }}
      .beam {{ position: absolute; top: -200px; width: 260px; height: 1500px; background: linear-gradient(rgba(255,210,150,.22), rgba(255,210,150,0));
               filter: blur(18px); }}
      .b1 {{ left: 120px; transform: rotate(18deg); }} .b2 {{ right: 120px; transform: rotate(-18deg); }}
      .term {{ position: absolute; left: 90px; top: 300px; width: 900px; display: flex; align-items: center; gap: 16px; background: rgba(12,14,20,.95);
               border: 2px solid rgba(217,119,87,.5); border-radius: 24px; padding: 18px 26px; font-family: "JetBrains Mono", monospace;
               font-size: 52px; color: #fff; opacity: 0; z-index: 3; }}
      .term .pp {{ color: {ORANGE}; font-weight: 900; }} .cur {{ width: 4px; height: 52px; background: #fff; }}
      .hud {{ position: absolute; right: 80px; top: 430px; text-align: right; z-index: 3; opacity: 0; }}
      #g6 .hud {{ opacity: 1; }}
      .hud b {{ display: block; font-weight: 900; font-size: 150px; line-height: 1; color: #fff; text-shadow: 0 0 40px rgba(217,119,87,.9); }}
      .hud span {{ font-weight: 800; font-size: 40px; color: #FFB38A; }}
      .task {{ position: absolute; left: 90px; top: 450px; font-weight: 900; font-size: 46px; color: #fff; background: rgba(3,6,12,.85);
               border: 2px solid {GREEN}; padding: 10px 26px; border-radius: 99px; opacity: 0; z-index: 3; }}
      .judge {{ position: absolute; left: 80px; top: 470px; font-weight: 900; font-size: 44px; color: #fff; background: rgba(3,6,12,.88);
                border: 2px solid #FDE68A; padding: 10px 26px; border-radius: 99px; opacity: 0; z-index: 3; }}
      .judge b {{ color: #FDE68A; }}
      video.tri {{ position: absolute; left: 60px; width: 960px; height: 490px; object-fit: cover; z-index: 6; opacity: 0; border-radius: 28px;
                   transform: perspective(1400px) rotateY(var(--r)); box-shadow: 0 30px 90px rgba(0,0,0,.6), 0 0 0 3px rgba(217,119,87,.6); }}
      .tribg {{ position: absolute; inset: 0; background: radial-gradient(ellipse at 50% 50%, #2a1408 0%, #07060a 70%); }}
      .c3f {{ position: absolute; left: 0; top: 0; width: 1080px; height: 1920px; z-index: 4; pointer-events: none; }}
      .h3 {{ position: absolute; top: 140px; white-space: nowrap; display: flex; flex-direction: column; align-items: center; gap: 12px; }}
      .h3 .meh {{ font-size: 44px; }}
      .sq {{ height: 480px; grid-template-rows: 1fr 1fr; align-items: end; }}
      .sg {{ background: none; border: none; box-shadow: none; padding: 0; }}
      .sg span {{ background: rgba(3,6,12,.85); border: 2px solid var(--c); padding: 4px 18px; border-radius: 99px; font-size: 34px; }}
      .c3d {{ position: absolute; left: 0; top: 0; width: 1080px; height: 1920px; z-index: 1; }}
      .crown {{ position: absolute; left: 470px; top: 830px; font-size: 140px; opacity: 0; z-index: 3; filter: drop-shadow(0 0 30px rgba(253,230,138,.9)); }}
      /* стратегии */
      .sq {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; width: 960px; perspective: 900px; }}
      .sg {{ background: rgba(12,19,33,.96); border: 2px solid var(--c); border-radius: 26px; padding: 14px; display: flex; flex-direction: column;
             align-items: center; gap: 8px; opacity: 0; box-shadow: 0 0 40px color-mix(in srgb, var(--c) 30%, transparent); }}
      .sg .mini {{ display: grid; grid-template-columns: repeat(9, 1fr); gap: 4px; width: 100%; }}
      .sg .mini svg {{ width: 100%; height: 40px; fill: var(--c); }}
      .sg span {{ font-weight: 900; font-size: 40px; color: #fff; }}
      /* лимит */
      .lim {{ width: 960px; background: rgba(12,19,33,.96); border: 2px solid {P['line']}; border-radius: 30px; padding: 24px 28px;
              display: flex; flex-direction: column; gap: 18px; }}
      .lh {{ display: flex; justify-content: space-between; font-weight: 900; font-size: 44px; color: #fff; }} .lh b {{ color: #FDE68A; }}
      .bar {{ height: 46px; background: #111A2C; border-radius: 14px; overflow: hidden; }}
      .bar i {{ display: block; height: 100%; width: 100%; background: linear-gradient(90deg, {RED}, #F59E0B, {GREEN}); border-radius: 14px; }}
      .lrow {{ display: flex; flex-direction: column; gap: 12px; align-items: flex-start; }}
      /* баги */
      .bugs {{ display: flex; gap: 22px; }} .bg {{ font-size: 90px; opacity: 0; }}
      /* CTA */
      .cbox {{ width: 920px; display: flex; align-items: center; gap: 20px; background: {P['card']}; border: 2px solid rgba(217,119,87,.6);
               border-radius: 99px; padding: 16px 16px 16px 24px; box-shadow: 0 20px 80px rgba(217,119,87,.35); }}
      .cbox .av2 {{ font-size: 56px; }} .cbox .cin {{ flex: 1; font-weight: 900; font-size: 64px; color: #FFB38A; letter-spacing: 4px; }}
      .cbox .send {{ display: inline-flex; width: 76px; height: 76px; border-radius: 50%; background: {ORANGE}; color: #fff;
                     align-items: center; justify-content: center; font-size: 40px; font-weight: 900; }}
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
      .gift {{ font-weight: 800; font-size: 42px; color: #fff; background: rgba(3,6,12,.88); padding: 12px 30px; border-radius: 99px; opacity: 0; }}
"""

if __name__ == "__main__":
    r.write(CSS)
    if "--render" in sys.argv:
        print(render(WD, int(sys.argv[sys.argv.index("--render") + 1])))
