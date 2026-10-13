"""Ручной монтаж «как у топовых AI-блогеров» — общий набор (камера, переходы, окна, пункты, субтитры, темы).

Эталон — IMG_8876 (одобрен автором 2026-09-29). Режиссура ролика пишется отдельно, под его слова:

    from craft import Reel
    r = Reel(work_dir, theme="light")
    r.states([(0, "full"), (1.4, "card"), ...])         # камера: full ↔ card ↔ hide, перетекание 0.6 с
    r.G("g1", t_in, t_out, "top", html)                  # графика: входит/уходит через размытие
    r.captions(keys=[...], hide=[(a, b), ...])
    r.write()                                            # → work/<имя>/craft/hf/index.html + sfx.json

Принципы: единый фон на весь ролик; камера перетекает, а не переключается; графика входит из размытия и уходит
в размытие, перекрываясь со следующей; всё печатаемое печатается в момент, когда автор это говорит; первый кадр —
лицо автора; крупность меняется только на стыках разных дублей на полном экране.
"""
import json
import re
import shutil
from pathlib import Path

import compose as C

ENGINE = Path(__file__).resolve().parent
W, H = 1080, 1920
SRC_W, SRC_H = 1440, 2560
MORPH = 0.6
PUSH = 330  # сдвиг кадра в состоянии left/right
CARD = dict(t=860, l=40, b=40, r=40, R=56)
CARD_FACE_Y = 1245
CARD_S = 300 / 420

THEMES = {
    "dark": dict(bg="#03060C", ink="#FFFFFF", muted="#8A96AD", accent="#3AA8FF", card="#0C1321", line="#1C2840",
                 soft="#131D31", red="#FF4458", green="#57E39A", bubble="#16213A", me="#1F3B66", me_ink="#FFFFFF",
                 ans="#C3CCDD", cap_s="#C8D2E6", cap_b="#FFFFFF", cap_k="#6CC4FF", hd="#DCE4F5",
                 glow="34,120,255", glow_a=".42", glow2="0,190,255", glow2_a=".16", grid="120,160,255", grid_a=".05",
                 shadow="0 40px 100px rgba(10,80,220,.28)", ring="rgba(80,150,255,.35)",
                 card_shadow="0 30px 90px rgba(20,110,255,.35)", sum_grad="#FFFFFF 0%, #7CC6FF 100%",
                 neon=".45", tg_bg="rgba(18,24,38,.94)", tg_ink="#FFFFFF", tg_sub="#D5DDEC", tg_app="#AAB6CA"),
    "light": dict(bg="#F2F5FA", ink="#0B1220", muted="#6B7A90", accent="#1E8CFF", card="#FFFFFF", line="#E2E8F1",
                  soft="#EEF3FA", red="#F0364A", green="#12B76A", bubble="#EEF3FA", me="#1E8CFF", me_ink="#FFFFFF",
                  ans="#3A475C", cap_s="#55647A", cap_b="#0B1220", cap_k="#1E8CFF", hd="#1D2A3F",
                  glow="30,140,255", glow_a=".20", glow2="120,200,255", glow2_a=".22", grid="11,18,32", grid_a=".045",
                  shadow="0 30px 80px rgba(20,60,140,.14), 0 2px 8px rgba(11,18,32,.05)", ring="rgba(30,140,255,.28)",
                  card_shadow="0 30px 80px rgba(20,60,140,.20)", sum_grad="#0B1220 0%, #1E8CFF 100%",
                  neon=".22", tg_bg="rgba(255,255,255,.97)", tg_ink="#0B1220", tg_sub="#3A475C", tg_app="#6B7A90"),
}


class Reel:
    def __init__(self, wd: str | Path, theme: str = "light", fixes: dict | None = None, depth: bool = False):
        self.wd = Path(wd)
        self.depth = depth  # урок 08.10: маска человека → графика может стоять ЗА спикером (G(..., z="behind"))
        self.theme = theme
        self.P = THEMES[theme]
        C._THEME_NAME = theme
        mw = json.load(open(self.wd / "master_words.json", encoding="utf-8"))
        self.mw, self.dur = mw, mw["duration"]
        self.words = C.merge_tokens(mw["words"])
        for w in self.words:
            if fixes and w["w"] in fixes:
                w["w"] = fixes[w["w"]]
        self.js, self.parts, self.sfx = [], [], []
        self.cap_cls = None
        self.STATES: list[tuple[float, str]] = [(0, "full")]
        face = json.load(open(self.wd / "face.json"))
        vh = max(420 / face["h"], 1.05 * W * SRC_H / SRC_W)
        vw = vh * SRC_W / SRC_H
        top = 760 - face["cy"] * vh
        top = max(top, 150 - face["top"] * vh) if top + face["top"] * vh < 150 else top
        self.top = min(0.0, max(H - vh, top))
        self.left = min(0.0, max(W - vw, 540 - face["cx"] * vw))
        self.vw, self.vh = vw, vh
        self.px, self.py = 540 - self.left, 760 - self.top

    # ---------- время ----------
    def T(self, word: str, after: float = 0.0) -> float:
        """Когда звучит слово (первое вхождение после after)."""
        q = re.sub(r"[^\wё-]", "", word.lower())  # запрос чистим так же, как слова: «2,5» → «25», «Grok,» → «grok»
        for w in self.words:
            if w["start"] >= after - 1e-6 and re.sub(r"[^\wё-]", "", w["w"].lower()).startswith(q):
                return w["start"]
        raise KeyError(word)

    def E(self, word: str, after: float = 0.0) -> float:
        """Когда слово заканчивается."""
        t = self.T(word, after)
        return next(w["end"] for w in self.words if w["start"] == t)

    def sound(self, name: str, t: float, vol: float = 0.3) -> None:
        f = ENGINE / "assets" / "sfx" / f"{name}.mp3"
        if f.exists() and 0 <= t < self.dur - 0.1:
            self.sfx.append({"file": str(f), "at": round(t, 3), "volume": vol})

    # ---------- камера ----------
    def cam(self, state: str, z: float = 1.0) -> dict:
        if state == "full":
            v = dict(x=(1 - z) * self.px, y=(1 - z) * self.py, scale=z)
            clip = "inset(0px 0px 0px 0px round 0px)"
        elif state in ("left", "right"):  # «смести меня вправо»: кадр уезжает, свободная половина — под список/панель
            v = dict(x=(-1 if state == "left" else 1) * PUSH, y=0, scale=1)
            clip = "inset(0px 0px 0px 0px round 0px)"
        else:
            s = CARD_S * z
            v = dict(x=540 - self.left - s * self.px, y=CARD_FACE_Y - self.top - s * self.py, scale=s)
            clip = f"inset({CARD['t']}px {CARD['r']}px {CARD['b']}px {CARD['l']}px round {CARD['R']}px)"
        return {"v": {k: round(x, 2) for k, x in v.items()}, "clip": clip}

    def state_at(self, t: float) -> str:
        s = self.STATES[0][1]
        for a, st in self.STATES:
            if t >= a + MORPH / 2:
                s = st
        return s

    def states(self, states: list[tuple[float, str]]) -> None:
        """Сценарий камеры: (время начала перехода, full|card|hide). Первый кадр — всегда лицо: full или card
        (card — лицо в карточке и графика над ним уже с 0 с, motion-дизайн цепляет с первого кадра)."""
        assert states[0][1] in ("full", "card", "left", "right"), "первый кадр — лицо автора"
        self.STATES = states
        js, jsn = self.js, lambda d: json.dumps(d, ensure_ascii=False)
        R = self.mw["ranges"]
        cuts, off = [], 0.0
        for k, (a, b) in enumerate(R[:-1]):  # стыки РАЗНЫХ дублей — только на них меняем крупность
            off += b - a
            if R[k + 1][0] - b > 1.0:
                cuts.append(round(off, 3))
        zoom = {"full": 1.0, "card": 1.0}
        first = self.cam(states[0][1])
        js.append(f'tl.set("#cam", {jsn(first["v"])}, 0);')
        js.append(f'tl.set("#camwrap", {{clipPath: "{first["clip"]}", opacity: 1, y: 0, scale: 1}}, 0);')
        js.append(f'tl.set("#cardglow", {{opacity: {1 if states[0][1] == "card" else 0}}}, 0);')
        prev = None
        for k, (t0, st) in enumerate(states):
            t1 = states[k + 1][0] if k + 1 < len(states) else self.dur
            if prev is not None:
                a = self.cam(prev if prev != "hide" else "card", zoom.get(prev, 1.0))
                b = self.cam(st if st != "hide" else "card", 1.0)
                zoom[st] = 1.0
                if st == "hide":  # автор уходит вниз и растворяется — графика занимает экран
                    js.append(f'tl.fromTo("#camwrap", {{opacity: 1, y: 0, scale: 1}}, {{opacity: 0, y: 140, scale: 1, duration: 0.5, ease: "power2.in"}}, {t0});')
                    js.append(f'tl.to("#cardglow", {{opacity: 0, duration: 0.4}}, {t0});')
                    if prev == "full":
                        js.append(f'tl.fromTo("#cam", {jsn(a["v"])}, {{...{jsn(b["v"])}, duration: 0.5, ease: "power3.inOut"}}, {t0});')
                        js.append(f'tl.fromTo("#camwrap", {{clipPath: "{a["clip"]}"}}, {{clipPath: "{b["clip"]}", duration: 0.5, ease: "power3.inOut"}}, {t0});')
                elif prev == "hide":  # возвращается: карточка всплывает снизу, весь экран — проявляется с лёгким наездом
                    js.append(f'tl.set("#cam", {jsn(b["v"])}, {t0});')
                    js.append(f'tl.set("#camwrap", {{clipPath: "{b["clip"]}"}}, {t0});')
                    if st == "card":
                        js.append(f'tl.fromTo("#camwrap", {{opacity: 0, y: 160, scale: 1}}, {{opacity: 1, y: 0, scale: 1, duration: {MORPH}, ease: "power3.out"}}, {t0});')
                        js.append(f'tl.to("#cardglow", {{opacity: 1, duration: {MORPH}}}, {t0});')
                    else:
                        js.append(f'tl.fromTo("#camwrap", {{opacity: 0, y: 0, scale: 1.08}}, {{opacity: 1, y: 0, scale: 1, duration: {MORPH}, ease: "power3.out"}}, {t0});')
                else:  # весь экран ↔ карточка: кадр перетекает
                    js.append(f'tl.fromTo("#cam", {jsn(a["v"])}, {{...{jsn(b["v"])}, duration: {MORPH}, ease: "power3.inOut"}}, {t0});')
                    js.append(f'tl.fromTo("#camwrap", {{clipPath: "{a["clip"]}"}}, {{clipPath: "{b["clip"]}", duration: {MORPH}, ease: "power3.inOut"}}, {t0});')
                    js.append(f'tl.to("#cardglow", {{opacity: {1 if st == "card" else 0}, duration: {MORPH}}}, {t0});')
                self.sound("whoosh-short", t0, 0.16)
            if st == "full":  # стык дублей на крупном плане — смена крупности, чтобы стык читался как приём
                for c in cuts:
                    if t0 + MORPH + 0.1 < c < t1 - 0.35:
                        zoom["full"] = 1.1 if zoom["full"] == 1.0 else 1.0
                        js.append(f'tl.set("#cam", {jsn(self.cam("full", zoom["full"])["v"])}, {c});')
            prev = st

    # ---------- графика ----------
    def G(self, gid: str, t_in: float, t_out: float, area: str, html: str, enter: bool = True, z: str = "front") -> None:
        """Сцена графики (area: top — над карточкой, center — весь экран, banner — поверх автора сверху)."""
        # T() ищет первое вхождение слова: «Только» может найтись раньше нужного («не только») — сцена «навсегда»
        assert t_out > t_in, f"{gid}: конец {t_out:.2f} раньше начала {t_in:.2f} — проверь опорное слово (after=)"
        end = min(self.dur, t_out + 0.45)
        self.parts.append(f'<div id="{gid}" class="clip scene {area}{" behind" if z == "behind" else ""}" data-start="{t_in:.3f}" data-duration="{end - t_in:.3f}" '
                          f'data-track-index="3"><div class="gw">{html}</div></div>')
        if enter:
            self.js.append(f'tl.fromTo("#{gid} .gw", {{opacity: 0, y: 46, scale: 0.94, filter: "blur(18px)"}}, '
                           f'{{opacity: 1, y: 0, scale: 1, filter: "blur(0px)", duration: 0.55, ease: "power3.out"}}, {t_in:.3f});')
        if t_out < self.dur - 0.2:
            self.js.append(f'tl.to("#{gid} .gw", {{opacity: 0, y: -36, scale: 1.04, filter: "blur(16px)", duration: 0.42, '
                           f'ease: "power2.in"}}, {t_out:.3f});')

    def pop(self, sel: str, t: float, snd: str | None = "pop", vol: float = 0.22, y: int = 26) -> None:
        self.js.append(f'tl.fromTo("{sel}", {{opacity: 0, y: {y}, scale: 0.9}}, {{opacity: 1, y: 0, scale: 1, duration: 0.38, '
                       f'ease: "back.out(1.8)"}}, {t:.3f});')
        if snd:
            self.sound(snd, t, vol)

    def typing(self, sel: str, text: str, st: float, en: float, after: float = 0.0) -> list[float]:
        """Печать синхронно с голосом: каждое слово появляется, когда автор его произносит."""
        tt = C.type_times(text, self.words, st, en, after=after)
        self.js.extend(C.type_js(sel, tt, st))
        if tt:
            self.sound("typing", tt[0], 0.16)
        return tt

    @staticmethod
    def typed(text: str) -> str:
        return C.typed_html(text)

    @staticmethod
    def logo(slug: str) -> str:
        return C.logo_html(slug)

    @staticmethod
    def esc(x) -> str:
        return C.esc(x)

    def item(self, gid: str, n: int, total: int, label: str, code: str, t_in: float, t_out: float) -> None:
        """Пункт списка «01 / 03»: контурная цифра, подпись, код расшифровывается из символов."""
        segs = "".join(f'<i class="{"on" if k < n else ""}"></i>' for k in range(total))
        self.G(gid, t_in, t_out, "center",
               f'<div class="item"><div class="prog">{segs}</div><div class="cnt">{n:02d} / {total:02d}</div>'
               f'<div class="num">{n:02d}</div><div class="lbl">{label}</div><div class="code"><span class="sl">/</span>'
               f'<span class="cd" data-code="{C.esc(code)}">{C.esc(code)}</span></div></div>')
        self.js.append(f'tl.fromTo("#{gid} .num", {{scale: 1.35, opacity: 0}}, {{scale: 1, opacity: 1, duration: 0.6, ease: "power3.out"}}, {t_in:.3f});')
        self.js.append(f'tl.fromTo("#{gid} .prog i.on", {{scaleX: 0}}, {{scaleX: 1, transformOrigin: "left center", duration: 0.3, stagger: 0.05}}, {t_in:.3f});')
        self.js.append(f'tl.fromTo("#{gid} .code", {{opacity: 0, y: 24}}, {{opacity: 1, y: 0, duration: 0.35, ease: "power3.out"}}, {t_in + 0.35:.3f});')
        self.js.append(f'scramble("#{gid} .cd", {t_in + 0.4:.3f}, 0.7);')
        self.sound("glitch-1", t_in + 0.4, 0.03)  # автор просил максимально тихо

    # ---------- субтитры ----------
    def captions(self, keys: list[str], hide: list[tuple[float, float]]) -> None:
        """Субтитры 1–3 слова: курсив + крупный гротеск, ключевые слова акцентом. hide — где крупная графика сама говорит."""
        j = 0
        K = set(keys)
        for c in C.caption_groups(self.words):
            ws = c["words"]
            small, big = (ws[:-1], ws[-1:]) if len(ws) > 1 else ([], ws)
            if any(C.is_key(w, K) for w in small):
                small, big = [], ws
            big_html = " ".join(f'<span class="{"k" if C.is_key(w, K) else ""}">{C.esc(w.rstrip(".,!?:"))}</span>' for w in big)
            small_html = " ".join(C.esc(w.rstrip(".,!?:")) for w in small)
            inner = (f'<div class="s">{small_html}</div>' if small_html else "") + f'<div class="b">{big_html}</div>'
            cs, ce = c["start"], min(c["end"], self.dur)
            marks = sorted({cs, ce, *[a + MORPH / 2 for a, _ in self.STATES if cs < a + MORPH / 2 < ce],
                            *[x for h in hide for x in h if cs < x < ce]})
            for a, b in zip(marks, marks[1:]):
                if b - a < 0.08 or any(h0 <= a < h1 for h0, h1 in hide):
                    continue
                pos = self.cap_cls or {"card": "cap-card", "hide": "cap-hide"}.get(self.state_at(a), "cap-full")
                self.parts.append(f'<div id="c{j}" class="clip cap {pos}" data-start="{a:.3f}" data-duration="{b - a:.3f}" '
                                  f'data-track-index="5">{inner}</div>')
                if a == cs:
                    self.js.append(f'tl.fromTo("#c{j}", {{opacity: 0, y: 16, scale: 0.96}}, {{opacity: 1, y: 0, scale: 1, '
                                   f'duration: 0.16, ease: "power2.out"}}, {a:.3f});')
                j += 1


    # ---------- стиль «урок 08.10»: спикер на весь кадр, графика вокруг и ЗА ним ----------
    def stack(self, gid: str, t_in: float, t_out: float, lines: list[tuple[str, str, str]], x: int = 70, y: int = 300,
              align: str = "left", z: str = "front", width: int = 940) -> None:
        """Стопка строк: (слово-триггер, текст, класс) — класс s (мелкая белая), b (крупная акцентная), c (хром), x (зачёркнутая).
        Каждая строка проявляется из размытия на своём слове. Ставить в пустое место рядом с головой или ЗА головой (z="behind")."""
        assert t_out > t_in, f"{gid}: конец {t_out:.2f} раньше начала {t_in:.2f} — проверь опорное слово (after=)"
        html = "".join(f'<div class="ln {c} l{k}">' + (f'<span class="xw">{t}<i class="strk"></i></span>' if c == "x" else t) + '</div>'
                       for k, (_, t, c) in enumerate(lines))
        self.parts.append(f'<div id="{gid}" class="clip stk{" behind" if z == "behind" else ""}" style="left:{x}px;top:{y}px;width:{width}px;'
                          f'text-align:{align}" data-start="{t_in:.3f}" data-duration="{min(self.dur, t_out + 0.45) - t_in:.3f}" '
                          f'data-track-index="3">{html}</div>')
        for k, (w, _, c) in enumerate(lines):
            at = max(t_in, self.T(w, t_in) - 0.12) if w else t_in + 0.12 * k
            self.js.append(f'tl.fromTo("#{gid} .l{k}", {{opacity: 0, y: 30, filter: "blur(14px)", scale: {1.25 if c in ("b", "c", "c2") else 1}}}, '
                           f'{{opacity: 1, y: 0, filter: "blur(0px)", scale: 1, duration: 0.42, ease: "power3.out"}}, {at:.3f});')
            if c in ("b", "c", "c2"):
                self.sound("pop", at, 0.12)
            if c == "x":  # зачёркивание через 0.4 с
                self.js.append(f'tl.fromTo("#{gid} .l{k} .strk", {{width: "0%"}}, {{width: "104%", duration: 0.3, ease: "power2.out"}}, {at + 0.4:.3f});')
                self.sound("error", at + 0.4, 0.06)
        if t_out < self.dur - 0.2:
            self.js.append(f'tl.to("#{gid} .ln", {{opacity: 0, y: -24, filter: "blur(14px)", duration: 0.38, stagger: 0.04, ease: "power2.in"}}, {t_out:.3f});')

    def vtext(self, gid: str, t_in: float, t_out: float, text: str, side: str = "left", y: int = 1150, z: str = "front") -> None:
        """Вертикальная надпись вдоль края (как «я просто покажу») — печатается по словам синхронно с речью."""
        assert t_out > t_in, f"{gid}: конец {t_out:.2f} раньше начала {t_in:.2f} — проверь опорное слово (after=)"
        rot = -90 if side == "left" else 90
        pos = f"left:60px" if side == "left" else "right:60px"
        self.parts.append(f'<div id="{gid}" class="clip vt{" behind" if z == "behind" else ""}" style="{pos};top:{y}px;transform:rotate({rot}deg)" '
                          f'data-start="{t_in:.3f}" data-duration="{min(self.dur, t_out + 0.45) - t_in:.3f}" data-track-index="3">'
                          f'<span id="{gid}t">{self.typed(text)}</span></div>')
        self.typing(f"#{gid}t", text, t_in, t_out)
        if t_out < self.dur - 0.2:
            self.js.append(f'tl.to("#{gid}", {{opacity: 0, filter: "blur(10px)", duration: 0.35}}, {t_out:.3f});')


    def head(self) -> tuple[float, float, float]:
        """Центр головы и её радиус в кадре (состояние full) — для текста по окружности."""
        face = json.load(open(self.wd / "face.json"))
        cx = self.left + face["cx"] * self.vw
        cy = self.top + face["cy"] * self.vh
        r = face["h"] * self.vh / 2
        return cx, cy - r * 0.35, r

    def arc(self, gid: str, t_in: float, t_out: float, text: str, r: float | None = None, size: int = 56, spin: float = 8,
            side: str = "top", z: str = "front", color: str = "#fff", key: str | None = None) -> None:
        """Текст по окружности вокруг головы (правка автора 08.10: «надпись заводить по окружности», вместо вертикальной).
        side="top" — дуга над головой (радиус ограничен безопасной зоной 290 px), "bottom" — «улыбка» под лицом по груди
        (длинные фразы, лучший контраст). Строка заводится по окружности от левого края к центру дуги (startOffset 0→25 %,
        text-anchor middle) и чуть докручивается поворотом; слова проявляются, когда автор их говорит. key — слово акцентом."""
        assert t_out > t_in, f"{gid}: конец {t_out:.2f} раньше начала {t_in:.2f} — проверь опорное слово (after=)"
        cx, cy, hr = self.head()
        r = r or (min(hr * 1.85, cy - 290) if side == "top" else hr * 2.0)
        words = text.split()
        acc = 'fill="#6CC4FF"'
        spans = "".join(f'<tspan class="aw{k}" {acc if key and w.strip(",.!?«»").lower() == key.lower() else ""}>{self.esc(w)} </tspan>'
                        for k, w in enumerate(words))
        sgn = -1 if side == "top" else 1
        sw = 1 if side == "top" else 0  # по часовой — через верх, против — через низ (буквы стоят прямо в обоих случаях)
        d = f"M {cx - r:.1f},{cy:.1f} a {r:.1f},{r:.1f} 0 1,{sw} {2 * r:.1f},0 a {r:.1f},{r:.1f} 0 1,{sw} {-2 * r:.1f},0"
        self.parts.append(
            f'<div id="{gid}" class="clip arcw{" behind" if z == "behind" else ""}" data-start="{t_in:.3f}" '
            f'data-duration="{min(self.dur, t_out + 0.45) - t_in:.3f}" data-track-index="3">'
            f'<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}"><defs><path id="{gid}p" d="{d}"/></defs>'
            f'<g class="ag" style="transform-origin:{cx:.1f}px {cy:.1f}px"><text class="at" style="font-size:{size}px" fill="{color}">'
            f'<textPath href="#{gid}p" startOffset="25%" text-anchor="middle">{spans}</textPath></text></g></svg></div>')
        self.js.append(f'tl.fromTo("#{gid} textPath", {{attr: {{startOffset: "0%"}}}}, {{attr: {{startOffset: "25%"}}, duration: 1.0, ease: "power3.out"}}, {t_in:.3f});')
        self.js.append(f'tl.fromTo("#{gid} .ag", {{rotation: {sgn * spin}}}, {{rotation: 0, duration: {max(1.0, t_out - t_in):.2f}, ease: "sine.out"}}, {t_in:.3f});')
        # слова — по речи (если слово найдено в расшифровке после t_in), иначе равномерно
        ts, last = [], t_in
        for k, w in enumerate(words):
            try:
                t = self.T(w, last)
                t = t if t < t_out else None
            except KeyError:
                t = None
            ts.append(t)
            if t:
                last = t
        for k, t in enumerate(ts):
            t = t if t is not None else t_in + 0.08 * k
            self.js.append(f'tl.fromTo("#{gid} .aw{k}", {{fillOpacity: 0, strokeOpacity: 0}}, {{fillOpacity: 1, strokeOpacity: 1, duration: 0.18}}, {max(t_in, t - 0.08):.3f});')
        self.sound("whoosh-short", t_in, 0.1)
        if t_out < self.dur - 0.2:
            self.js.append(f'tl.to("#{gid} .ag", {{opacity: 0, rotation: "+={spin}", duration: 0.4, ease: "power2.in"}}, {t_out:.3f});')

    def section(self, gid: str, t_in: float, t_out: float, label: str) -> None:
        """Плашка раздела сверху слева («ШАГ 02 · …») — в безопасной зоне, ниже интерфейса Reels."""
        assert t_out > t_in, f"{gid}: конец {t_out:.2f} раньше начала {t_in:.2f} — проверь опорное слово (after=)"
        self.parts.append(f'<div id="{gid}" class="clip sec" data-start="{t_in:.3f}" data-duration="{min(self.dur, t_out + 0.4) - t_in:.3f}" '
                          f'data-track-index="3"><i></i>{label}</div>')
        self.js.append(f'tl.fromTo("#{gid}", {{opacity: 0, x: -30}}, {{opacity: 1, x: 0, duration: 0.35, ease: "power2.out"}}, {t_in:.3f});')
        if t_out < self.dur - 0.2:
            self.js.append(f'tl.to("#{gid}", {{opacity: 0, duration: 0.3}}, {t_out:.3f});')

    def glass(self, gid: str, t_in: float, t_out: float, html: str, x: int, y: int, w: int = 520, ry: int = -18, z: str = "front",
              snd: str | None = "whoosh-short") -> None:
        """Стеклянная панель в перспективе (поворот ry°), влетает из глубины и чуть «дышит»; z="behind" — за спикером."""
        assert t_out > t_in, f"{gid}: конец {t_out:.2f} раньше начала {t_in:.2f} — проверь опорное слово (after=)"
        self.parts.append(f'<div id="{gid}" class="clip gl3{" behind" if z == "behind" else ""}" style="left:{x}px;top:{y}px;width:{w}px" '
                          f'data-start="{t_in:.3f}" data-duration="{min(self.dur, t_out + 0.45) - t_in:.3f}" data-track-index="3">'
                          f'<div class="glass" style="transform:rotateY({ry}deg)">{html}</div></div>')
        self.js.append(f'tl.fromTo("#{gid} .glass", {{opacity: 0, z: -400, rotationY: {ry * 2.5}, filter: "blur(16px)"}}, {{opacity: 1, z: 0, '
                       f'rotationY: {ry}, filter: "blur(0px)", duration: 0.6, ease: "power3.out"}}, {t_in:.3f});')
        self.js.append(f'tl.fromTo("#{gid} .glass", {{y: 0}}, {{y: -14, duration: {max(0.5, t_out - t_in - 0.6):.2f}, ease: "sine.inOut"}}, {t_in + 0.6:.3f});')
        if snd:
            self.sound(snd, t_in, 0.1)
        if t_out < self.dur - 0.2:
            self.js.append(f'tl.to("#{gid} .glass", {{opacity: 0, z: -300, filter: "blur(14px)", duration: 0.4, ease: "power2.in"}}, {t_out:.3f});')

    def comment_cta(self, gid: str, t_in: float, word: str, t_word: float, lines: list[tuple[str, str, str]] | None = None) -> None:
        """Финал как в уроке: поле комментария внизу печатает кодовое слово + справа стопка «пиши … слово X»."""
        self.parts.append(f'<div id="{gid}" class="clip cbar" data-start="{t_in:.3f}" data-duration="{self.dur - t_in:.3f}" data-track-index="5">'
                          f'<span class="av"></span><span class="ci" id="{gid}t">{self.typed(word)}</span><span class="sd">↑</span></div>')
        self.js.append(f'tl.fromTo("#{gid}", {{opacity: 0, y: 80}}, {{opacity: 1, y: 0, duration: 0.45, ease: "back.out(1.6)"}}, {t_in:.3f});')
        self.typing(f"#{gid}t", word, t_word - 0.05, t_word + 0.5)
        self.js.append(f'tl.fromTo("#{gid} .sd", {{scale: 1}}, {{scale: 1.3, duration: 0.15, yoyo: true, repeat: 1}}, {t_word + 0.7:.3f});')
        self.sound("notification", t_word + 0.7, 0.1)
        if lines:
            self.stack(gid + "s", t_in, self.dur, lines, x=380, y=1060, align="right", width=640)

    # ---------- сборка ----------
    def css(self) -> str:
        P, L = self.P, self
        return f"""
      #root {{ position: relative; width: {W}px; height: {H}px; overflow: hidden; background: {P['bg']}; }}
      #glow {{ position: absolute; left: 90px; top: -260px; width: 900px; height: 900px; border-radius: 50%;
               background: radial-gradient(circle, rgba({P['glow']},{P['glow_a']}) 0%, rgba({P['glow']},.1) 45%, rgba({P['glow']},0) 70%); }}
      #glow2 {{ position: absolute; left: 380px; top: 700px; width: 800px; height: 800px; border-radius: 50%;
                background: radial-gradient(circle, rgba({P['glow2']},{P['glow2_a']}) 0%, rgba({P['glow2']},0) 70%); }}
      #grid {{ position: absolute; inset: 0; opacity: .5;
               background-image: linear-gradient(rgba({P['grid']},{P['grid_a']}) 1px, rgba(0,0,0,0) 1px), linear-gradient(90deg, rgba({P['grid']},{P['grid_a']}) 1px, rgba(0,0,0,0) 1px);
               background-size: 90px 90px; -webkit-mask-image: radial-gradient(ellipse at 50% 30%, #000 20%, rgba(0,0,0,0) 70%); }}
      #cardglow {{ position: absolute; left: {CARD['l']}px; top: {CARD['t']}px; width: {W - CARD['l'] - CARD['r']}px;
                   height: {H - CARD['t'] - CARD['b']}px; border-radius: {CARD['R']}px; z-index: 1;
                   box-shadow: 0 0 0 2px {P['ring']}, {P['card_shadow']}; }}
      #camwrap {{ position: absolute; left: 0; top: 0; width: {W}px; height: {H}px; overflow: hidden; z-index: 2; }}
      #cam {{ position: absolute; left: {L.left:.1f}px; top: {L.top:.1f}px; width: {L.vw:.1f}px; height: {L.vh:.1f}px; object-fit: cover;
              transform-origin: 0 0; }}
      .scene {{ position: absolute; left: 0; width: {W}px; display: flex; align-items: center; justify-content: center; z-index: 3; }}
      .scene.top {{ top: 50px; height: 640px; }}
      .scene.center {{ top: 0; height: {H}px; padding-bottom: 120px; }}
      .scene.banner {{ top: 80px; height: 380px; align-items: flex-start; }}
      .gw {{ will-change: transform, filter, opacity; }}
      /* субтитры */
      .cap {{ position: absolute; left: 60px; right: 60px; text-align: center; z-index: 6; line-height: 1.02; color: #fff; }}
      .cap .s {{ font-family: "Playfair"; font-style: italic; font-weight: 700; font-size: 48px; margin-bottom: 4px; }}
      .cap .b {{ font-weight: 800; font-size: 74px; letter-spacing: -1.5px; }}
      .cap .k {{ color: #6CC4FF; }}
      .cap-full {{ top: 1290px; text-shadow: 0 4px 28px rgba(0,0,0,.6), 0 1px 3px rgba(0,0,0,.6); }}
      .cap-card {{ top: 712px; color: {P['cap_b']}; }} .cap-card .s {{ font-size: 40px; color: {P['cap_s']}; }}
      .cap-card .b {{ font-size: 60px; }} .cap-card .k {{ color: {P['cap_k']}; }}
      .cap-hide {{ top: 1500px; color: {P['cap_b']}; }} .cap-hide .k {{ color: {P['cap_k']}; }}
      /* окна */
      .win {{ width: 960px; background: {P['card']}; border: 1.5px solid {P['line']}; border-radius: 40px; padding: 28px 32px 30px;
              box-shadow: {P['shadow']}; text-align: left; color: {P['ink']}; }}
      .hd2 {{ display: flex; align-items: center; gap: 14px; font-weight: 600; font-size: 30px; color: {P['hd']}; margin-bottom: 20px; }}
      .hd2 .logo {{ width: 38px; height: 38px; }}
      .hd2 em {{ margin-left: auto; font-style: normal; font-size: 24px; color: {P['muted']}; background: {P['soft']};
                 padding: 8px 18px; border-radius: 99px; }}
      .hd2 em.ok {{ color: {P['green']}; background: rgba(87,227,154,.12); }}
      .win i, .ty i {{ font-style: normal; }}
      .caret {{ display: inline-block; width: 4px; height: 1em; margin-left: 3px; vertical-align: -0.12em; background: {P['accent']}; }}
      .compose .big {{ font-size: 46px; line-height: 1.3; font-weight: 500; min-height: 240px; }}
      .compose .old {{ font-size: 28px; line-height: 1.35; color: {P['muted']}; margin-bottom: 16px; padding-bottom: 16px;
                       border-bottom: 1px dashed {P['line']}; }}
      .compose .bar {{ display: flex; justify-content: space-between; align-items: center; margin-top: 18px; color: {P['muted']}; font-size: 40px; }}
      .send {{ width: 64px; height: 64px; border-radius: 50%; background: {P['accent']}; color: #fff; font-weight: 800; font-size: 34px;
               display: flex; align-items: center; justify-content: center; }}
      .gpt .body {{ position: relative; min-height: 250px; }}
      .gpt .me, .me {{ margin-left: auto; width: fit-content; max-width: 700px; background: {P['me']}; color: {P['me_ink']}; font-size: 36px;
                  font-weight: 600; padding: 14px 26px; border-radius: 26px 26px 8px 26px; margin-bottom: 14px; opacity: 0; }}
      .gpt .ans p {{ font-size: 32px; line-height: 1.4; color: {P['ans']}; opacity: 0; }}
      .gpt .inp {{ display: flex; align-items: center; justify-content: space-between; border: 2px solid {P['line']}; border-radius: 28px;
                   padding: 16px 18px 16px 26px; margin-top: 18px; font-size: 40px; min-height: 96px; }}
      .bub {{ width: fit-content; max-width: 760px; font-size: 36px; padding: 16px 24px; border-radius: 26px 26px 26px 8px;
              background: {P['bubble']}; margin-top: 12px; opacity: 0; }}
      .stamp2 {{ position: absolute; left: 50%; top: 52%; border: 8px solid {P['red']}; color: {P['red']}; font-weight: 800;
                 font-size: 96px; letter-spacing: 8px; padding: 4px 40px; border-radius: 18px; text-transform: uppercase;
                 background: rgba(255,68,88,.1); opacity: 0; }}
      .qs .q {{ display: flex; align-items: center; gap: 18px; font-size: 38px; font-weight: 600; background: {P['bubble']};
                padding: 18px 24px; border-radius: 8px 26px 26px 26px; margin-bottom: 14px; width: fit-content; opacity: 0; }}
      .qs .q b {{ width: 48px; height: 48px; border-radius: 50%; background: {P['accent']}; color: #fff; font-size: 26px;
                  display: flex; align-items: center; justify-content: center; flex: none; }}
      .dots {{ display: flex; gap: 10px; padding: 18px 24px; background: {P['bubble']}; border-radius: 26px; width: fit-content; opacity: 0; }}
      .dots i {{ width: 16px; height: 16px; border-radius: 50%; background: {P['muted']}; }}
      .rows .row {{ display: flex; align-items: center; gap: 20px; padding: 16px 0; border-top: 1px solid {P['line']}; font-size: 34px; font-weight: 600; }}
      .rows .ck {{ width: 46px; height: 46px; border-radius: 50%; background: {P['line']}; color: #fff; font-size: 26px; flex: none;
                   display: flex; align-items: center; justify-content: center; }}
      .rows .sk {{ display: block; height: 16px; border-radius: 8px; background: {P['line']}; flex: 1; margin-left: 10px; }}
      /* крупное: цифра / слово */
      .pre-i {{ font-family: "Playfair"; font-style: italic; font-size: 52px; color: {P['muted']}; text-align: center; }}
      .huge {{ font-weight: 800; font-size: 170px; letter-spacing: -6px; line-height: 1.05; text-align: center;
               background: linear-gradient(180deg, {P['sum_grad']}); -webkit-background-clip: text; color: rgba(0,0,0,0);
               filter: drop-shadow(0 0 40px rgba(58,168,255,{P['neon']})); }}
      .outline {{ font-weight: 800; font-size: 400px; line-height: .92; letter-spacing: -14px; color: rgba(0,0,0,0); text-align: center;
                  -webkit-text-stroke: 6px {P['accent']}; text-shadow: 0 0 60px rgba(58,168,255,{P['neon']}); }}
      .title-i {{ font-family: "Playfair"; font-style: italic; font-weight: 700; font-size: 110px; text-transform: uppercase;
                  letter-spacing: -1px; text-align: center; line-height: 1; color: {P['ink']}; }}
      .pill {{ display: inline-flex; align-items: center; gap: 14px; padding: 14px 32px; border-radius: 99px; border: 2px solid {P['line']};
               background: {P['card']}; font-weight: 600; font-size: 38px; color: {P['ink']}; box-shadow: {P['shadow']}; }}
      .pill .logo {{ width: 44px; height: 44px; }}
      /* пункт «01 / 03» */
      .item {{ text-align: center; }}
      .item .prog {{ display: flex; gap: 12px; justify-content: center; margin-bottom: 16px; }}
      .item .prog i {{ display: block; width: 70px; height: 9px; border-radius: 9px; background: {P['line']}; }}
      .item .prog i.on {{ background: {P['accent']}; box-shadow: 0 0 16px rgba(58,168,255,{P['neon']}); }}
      .item .cnt {{ font-weight: 600; font-size: 30px; color: {P['muted']}; letter-spacing: 3px; }}
      .item .num {{ font-weight: 800; font-size: 400px; line-height: .92; letter-spacing: -14px; color: rgba(0,0,0,0);
                    -webkit-text-stroke: 6px {P['accent']}; text-shadow: 0 0 60px rgba(58,168,255,{P['neon']}); }}
      .item .lbl {{ font-family: "Playfair"; font-style: italic; font-weight: 700; font-size: 110px; text-transform: uppercase;
                    letter-spacing: -1px; margin-top: -20px; color: {P['ink']}; }}
      .item .code {{ display: inline-block; margin-top: 28px; padding: 16px 50px; border-radius: 99px; border: 3px solid {P['accent']};
                     font-family: "JetBrains Mono", monospace; font-weight: 700; font-size: 70px; background: {P['card']}; color: {P['ink']};
                     box-shadow: 0 0 40px rgba(58,168,255,{P['neon']}); }}
      .item .sl {{ color: {P['accent']}; }}
      /* уведомление поверх автора */
      .tgn {{ width: 960px; background: {P['tg_bg']}; border: 1.5px solid rgba(127,127,127,.12); border-radius: 40px;
              padding: 28px 32px; text-align: left; box-shadow: 0 30px 80px rgba(0,0,0,.35); color: {P['tg_ink']}; }}
      .tgn .app {{ display: flex; align-items: center; gap: 12px; font-size: 26px; color: {P['tg_app']}; margin-bottom: 12px; }}
      .tgn .app .logo {{ width: 36px; height: 36px; }}
      .tgn b {{ font-size: 40px; }} .tgn p {{ font-size: 34px; margin-top: 8px; color: {P['tg_sub']}; }}
      .tgn .btn {{ display: inline-block; margin-top: 18px; background: #2AABEE; color: #fff; font-weight: 700; font-size: 32px;
                   padding: 14px 34px; border-radius: 99px; }}
      .logo {{ width: 96px; height: 96px; object-fit: contain; }}

      /* ---- стиль «урок 08.10» ---- */
      .scene.behind, .stk.behind, .vt.behind, .gl3.behind {{ z-index: 3 !important; }}
      #personwrap {{ position: absolute; left: 0; top: 0; width: {W}px; height: {H}px; overflow: hidden; z-index: 4; pointer-events: none; }}
      #person {{ position: absolute; left: {L.left:.1f}px; top: {L.top:.1f}px; width: {L.vw:.1f}px; height: {L.vh:.1f}px; object-fit: cover;
                 transform-origin: 0 0; }}
      .stk, .vt, .gl3, .sec, .cbar {{ position: absolute; z-index: 5; }}
      .stk .ln {{ opacity: 0; line-height: 1.02; color: #fff; text-shadow: 0 6px 30px rgba(0,0,0,.45); }}
      .stk .s {{ font-weight: 800; font-size: 56px; letter-spacing: -1px; }}
      .stk .b {{ font-weight: 900; font-size: 120px; letter-spacing: -4px; line-height: .98;
                 background: linear-gradient(180deg, #9AD8FF 0%, #3AA8FF 45%, #1E5BFF 100%); -webkit-background-clip: text; color: rgba(0,0,0,0);
                 text-shadow: none; filter: drop-shadow(0 8px 30px rgba(30,120,255,.55)); }}
      .stk .c {{ font-weight: 900; font-size: 150px; letter-spacing: -5px; line-height: .95; text-shadow: none;
                 background: linear-gradient(180deg, #FFFFFF 0%, #DDE3EC 28%, #7D8796 50%, #F4F7FB 54%, #AEB7C4 78%, #5B6573 100%);
                 -webkit-background-clip: text; color: rgba(0,0,0,0);
                 filter: drop-shadow(0 2px 0 #9AA3B0) drop-shadow(0 4px 0 #6F7886) drop-shadow(0 7px 0 #4A525E) drop-shadow(0 18px 30px rgba(0,0,0,.6)); }}
      .stk .c2 {{ font-weight: 900; font-size: 108px; letter-spacing: -4px; line-height: .95; text-shadow: none;
                  background: linear-gradient(180deg, #FFFFFF 0%, #DDE3EC 28%, #7D8796 50%, #F4F7FB 54%, #AEB7C4 78%, #5B6573 100%);
                  -webkit-background-clip: text; color: rgba(0,0,0,0);
                  filter: drop-shadow(0 2px 0 #9AA3B0) drop-shadow(0 4px 0 #6F7886) drop-shadow(0 6px 0 #4A525E) drop-shadow(0 16px 26px rgba(0,0,0,.6)); }}
      .stk .x {{ --x: 0%; font-weight: 900; font-size: 110px; letter-spacing: -3px; color: #fff; display: inline-block;
                 background-image: linear-gradient(#FF4458, #FF4458); background-repeat: no-repeat; background-position: 0 55%; background-size: var(--x) 12px; }}
      .stk .xw {{ position: relative; display: inline-block; }}
      .stk .strk {{ position: absolute; left: -2%; top: 50%; height: 14px; width: 0; border-radius: 7px; background: #FF4458;
                    box-shadow: 0 0 18px rgba(255,68,88,.7); }}
      .stk .w {{ font-weight: 900; font-size: 84px; letter-spacing: -2px; }}
      .vt {{ transform-origin: 0 0; white-space: nowrap; font-weight: 900; font-size: 58px; color: #fff; letter-spacing: -1px;
             text-shadow: 0 6px 24px rgba(0,0,0,.5); }}
      .vt i {{ font-style: normal; }}
      .arcw {{ position: absolute; left: 0; top: 0; width: {W}px; height: {H}px; z-index: 5; pointer-events: none; }}
      .arcw text {{ font-weight: 900; letter-spacing: 1px; paint-order: stroke; stroke: rgba(0,0,0,.35); stroke-width: 6px; }}
      .arcw tspan {{ fill-opacity: 0; stroke-opacity: 0; }}  /* opacity на tspan Chrome не применяет */
      .gl3 {{ perspective: 1400px; }}
      /* backdrop-filter не используем: рендер виснет (таймаут 08.10) — «стекло» имитируем тёмным градиентом */
      .glass {{ background: linear-gradient(160deg, rgba(60,72,96,.78), rgba(14,18,28,.82)); border: 1.5px solid rgba(255,255,255,.28);
                border-radius: 34px; padding: 26px 30px; color: #fff; box-shadow: 0 40px 100px rgba(0,0,0,.45), inset 0 1px 0 rgba(255,255,255,.35);
                transform-style: preserve-3d; }}
      .glass .gh {{ font-weight: 700; font-size: 26px; color: rgba(255,255,255,.7); letter-spacing: 2px; text-transform: uppercase; margin-bottom: 10px; }}
      .glass .gv {{ font-weight: 900; font-size: 92px; letter-spacing: -3px; line-height: 1; }}
      .glass .gv b {{ color: #6CC4FF; }}
      .glass .gr {{ display: flex; align-items: center; gap: 16px; font-weight: 700; font-size: 34px; padding: 10px 0;
                    border-top: 1px solid rgba(255,255,255,.14); opacity: 0; }}
      .glass .gr em {{ font-style: normal; color: #6CC4FF; font-weight: 900; min-width: 56px; }}
      .sec {{ left: 50px; top: 272px; display: flex; align-items: center; gap: 12px; font-weight: 800; font-size: 26px; letter-spacing: 3px;
              text-transform: uppercase; color: rgba(255,255,255,.88); background: rgba(10,14,24,.55); border: 1px solid rgba(255,255,255,.16);
              padding: 10px 20px; border-radius: 12px; }}
      .sec i {{ width: 10px; height: 10px; border-radius: 50%; background: #3AA8FF; box-shadow: 0 0 12px #3AA8FF; }}
      .cbar {{ left: 60px; right: 60px; top: 1420px; display: flex; align-items: center; gap: 18px; background: rgba(18,22,32,.82);
               border: 1.5px solid rgba(255,255,255,.18); border-radius: 99px; padding: 14px 14px 14px 18px; }}
      .cbar .av {{ width: 64px; height: 64px; border-radius: 50%; background: linear-gradient(135deg, #3AA8FF, #7B5CFF); flex: none; }}
      .cbar .ci {{ flex: 1; font-weight: 800; font-size: 50px; color: #fff; }}
      .cbar .sd {{ width: 70px; height: 70px; border-radius: 50%; background: #7B5CFF; color: #fff; font-weight: 900; font-size: 38px;
                   display: flex; align-items: center; justify-content: center; }}
      /* мини-субтитры: мелко, внизу, ключ — синим (как в уроке) */
      .cap-mini {{ top: 1500px; left: 80px; right: 80px; text-shadow: 0 3px 16px rgba(0,0,0,.75), 0 1px 3px rgba(0,0,0,.7); z-index: 6; }}
      .cap-mini .s {{ font-family: "Inter"; font-style: normal; font-weight: 800; font-size: 44px; margin: 0; }}
      .cap-mini .b {{ font-weight: 900; font-size: 50px; letter-spacing: -.5px; }}
      .cap-mini .k {{ color: #5AB4FF; }}
"""

    HELPERS = r"""
      // стартовое состояние анимации применяется только когда до неё дошло время — иначе поздние сцены
      // заранее перетирают ранние (кадр в начале «прыгал» по крупности)
      const _fromTo = tl.fromTo.bind(tl);
      tl.fromTo = (t, a, b, p) => _fromTo(t, a, Object.assign({}, b, { immediateRender: false }), p);
      function countUp(sel, a, b, at, dur, suffix) {
        const el = document.querySelector(sel), o = { v: a };
        const fmt = (v) => Math.round(v).toString().replace(/\B(?=(\d{3})+(?!\d))/g, " ") + (suffix || "");
        tl.fromTo(o, { v: a }, { v: b, duration: dur, ease: "power3.out", onUpdate: () => { el.textContent = fmt(o.v); } }, at);
      }
      function scramble(sel, at, dur) {
        const el = document.querySelector(sel); if (!el) return; const code = el.dataset.code || el.textContent, junk = "#%{[<>$@01E!&*";
        const o = { p: 0 };
        tl.fromTo(o, { p: 0 }, { p: 1, duration: dur, ease: "none", onUpdate: () => {
          const n = Math.floor(o.p * code.length), f = Math.floor(o.p * 24);
          el.textContent = code.split("").map((ch, i) => i < n || ch === " " ? ch : junk[(i * 7 + f * 3) % junk.length]).join("");
        } }, at);
      }
"""

    def write(self, extra_css: str = "") -> Path:
        out = self.wd / "craft" / "hf"
        out.mkdir(parents=True, exist_ok=True)
        for sub in ("fonts", "vendor", "logos"):
            shutil.copytree(ENGINE / "assets" / sub, out / "assets" / sub, dirs_exist_ok=True, copy_function=shutil.copyfile)
        src = self.wd / "master.mp4"
        if not (out / "master.mp4").exists() or (out / "master.mp4").stat().st_mtime < src.stat().st_mtime:
            shutil.copyfile(src, out / "master.mp4")
        # depth: глубина собирается в render() тремя проходами + ffmpeg (второе видео в браузере на 8 ГБ виснет — 08.10)
        (out / "depth.flag").write_text("1" if self.depth else "0")
        self.js.append(f'tl.fromTo("#glow", {{x: -120, y: 0, scale: 1}}, {{x: 140, y: 120, scale: 1.25, duration: {self.dur:.2f}, ease: "sine.inOut"}}, 0);')
        self.js.append(f'tl.fromTo("#glow2", {{x: 100, y: 0}}, {{x: -160, y: -140, duration: {self.dur:.2f}, ease: "sine.inOut"}}, 0);')
        fonts = "\n".join(l for l in C.TEMPLATE.splitlines() if "@font-face" in l).replace("{{", "{").replace("}}", "}")
        fonts += ('\n      @font-face { font-family: "Inter"; font-weight: 900; src: url(assets/fonts/inter-cyrillic-900-normal.woff2) format("woff2"); unicode-range: U+0400-04FF; }'
                  '\n      @font-face { font-family: "Inter"; font-weight: 900; src: url(assets/fonts/inter-latin-900-normal.woff2) format("woff2"); unicode-range: U+0000-00FF, U+2000-206F, U+20AC, U+2192, U+2193; }')
        P, dur = self.P, self.dur
        person_html = ""
        doc = f"""<!doctype html>
<html lang="ru" data-resolution="portrait">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width={W}, height={H}" />
    <script src="assets/vendor/gsap.min.js"></script>
    <style>
{fonts}
      * {{ margin: 0; padding: 0; box-sizing: border-box; }}
      html, body {{ width: {W}px; height: {H}px; overflow: hidden; background: {P['bg']}; }}
      body {{ font-family: "Inter", sans-serif; color: {P['ink']}; }}
{self.css()}
{extra_css}
    </style>
  </head>
  <body>
    <div id="root" data-composition-id="main" data-start="0" data-duration="{dur:.3f}" data-width="{W}" data-height="{H}">
      <div id="glow"></div><div id="glow2"></div><div id="grid"></div>
      <div id="cardglow"></div>
      <div id="camwrap">
        <video id="cam" class="clip" src="master.mp4" muted playsinline data-start="0" data-duration="{dur:.3f}" data-track-index="0"></video>
      </div>
{person_html}
      <audio id="voice" src="master.mp4" data-start="0" data-duration="{dur:.3f}" data-track-index="2" data-volume="1"></audio>
{chr(10).join('      ' + p for p in self.parts)}
    </div>
    <script>
      window.__timelines = window.__timelines || {{}};
      const tl = gsap.timeline({{ paused: true }});
{self.HELPERS}
{chr(10).join('      ' + x for x in self.js)}
      window.__timelines["main"] = tl;
    </script>
  </body>
</html>
"""
        (out / "index.html").write_text(doc, encoding="utf-8")
        (out / "hyperframes.json").write_text(json.dumps({"media": {"autoProxy": True}}), encoding="utf-8")
        (out / "sfx.json").write_text(json.dumps(self.sfx, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"{out / 'index.html'}: {len(self.parts)} клипов, {len(self.js)} анимаций, {len(self.sfx)} звуков, {dur:.1f} с")
        return out / "index.html"


PASS_CSS = {
    # только камера (по ней строится маска человека)
    "cam": ".scene, .stk, .vt, .gl3, .sec, .cbar, .cap, .arcw, video.scr, #bub { visibility: hidden !important; }",
    # всё, кроме графики «за спикером»
    "front": ".behind { visibility: hidden !important; }",
}


def _hf(hf: Path, out: Path, env: dict, workers: int, log: Path) -> None:
    import subprocess
    r = subprocess.run(["npx", "-y", "hyperframes@0.8.79", "render", "--workers", str(workers), "-o", str(out)],
                       cwd=hf, env=env, capture_output=True, text=True)
    log.write_text(r.stdout + r.stderr, encoding="utf-8")
    if r.returncode:
        raise RuntimeError((r.stdout + r.stderr)[-800:])


def _pass_dir(hf: Path, name: str) -> Path:
    """Копия проекта hf с добавленным CSS прохода (медиа — ссылками, без копирования)."""
    d = hf.parent / f"hf_{name}"
    if d.exists():
        shutil.rmtree(d)
    d.mkdir()
    for f in hf.iterdir():
        if f.name != "index.html":
            (d / f.name).symlink_to(f.resolve())
    html = (hf / "index.html").read_text(encoding="utf-8").replace("    </style>", f"      {PASS_CSS[name]}\n    </style>", 1)
    (d / "index.html").write_text(html, encoding="utf-8")
    return d


def render(wd: str | Path, version: int, workers: int = 2) -> Path:
    """Рендер HyperFrames + сведение звуков → work/<имя>/final_craft_v<N>.mp4.
    depth (Reel(..., depth=True)): 3 прохода — all (вся графика), front (без графики «за спикером»), cam (только камера);
    маска человека по cam → где человек — берём front, где фон — all. Так графика уходит ЗА спикера, а в браузере всегда одно видео."""
    import os
    import subprocess
    import mix
    wd = Path(wd)
    hf = wd / "craft" / "hf"
    env = {**os.environ, "PRODUCER_BROWSER_GPU_MODE": "hardware", "PRODUCER_PUPPETEER_PROTOCOL_TIMEOUT_MS": "900000"}
    out = wd / "craft" / "render.mp4"
    depth = (hf / "depth.flag").exists() and (hf / "depth.flag").read_text() == "1"
    if not depth:
        _hf(hf, out, env, workers, wd / "craft" / "render.log")
    else:
        import matte
        c = wd / "craft"
        _hf(hf, c / "pass_all.mp4", env, workers, c / "render.log")
        _hf(_pass_dir(hf, "front"), c / "pass_front.mp4", env, workers, c / "render_front.log")
        _hf(_pass_dir(hf, "cam"), c / "pass_cam.mp4", env, workers, c / "render_cam.log")
        matte.mask_video(c / "pass_cam.mp4", c / "mask.mp4")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", c / "pass_all.mp4", "-i", c / "pass_front.mp4", "-i", c / "mask.mp4",
                        "-filter_complex", "[2:v]format=gray[m];[1:v][m]alphamerge[p];[0:v][p]overlay=format=auto,format=yuv420p[v]",
                        "-map", "[v]", "-map", "0:a?", "-c:v", "libx264", "-crf", "16", "-preset", "medium", "-c:a", "copy",
                        "-movflags", "+faststart", out], check=True)
    final = wd / f"final_craft_v{version}.mp4"
    mix.mix(str(out), str(final), sfx=json.load(open(hf / "sfx.json", encoding="utf-8")))
    return final
