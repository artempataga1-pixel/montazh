"""Музыка под голос: фон тише, под речью автоматически проваливается (sidechain), плавные вход и выход.

Параметры — стартовая точка из гайда: музыка −17 dB, порог голоса −28 dB, ratio 8:1, attack 5 ms, release 300 ms.

Восстановлено из mix.pyc 2026-10-03 с двумя исправлениями звука (жалоба автора: «звук как будто микрофон конченый,
после музыки в Instagram — дичь»):
1. loudnorm был однопроходным (динамический режим): на тихой записи с шумодавом микрофона он «качал» громкость
   между фразами. Теперь два прохода: замер, затем линейное усиление (linear=true) — громкость ровная, без накачки.
2. loudnorm отдаёт 192 кГц, и AAC сохранялся в 96 кГц — нестандарт для Instagram (пересжатие при добавлении музыки).
   Теперь выход строго 48 кГц.
"""
import json
import re
import subprocess

TARGET_I, TARGET_TP, TARGET_LRA = -14.0, -1.5, 11.0


def _graph(video, sfx, music, dur, gain_db, threshold_db, ratio, attack_ms, release_ms, music_start, tail):
    inputs, chains, mixes = ["-i", video], ["[0:a]aresample=48000,highpass=f=70,asplit=2[voice][key]"], ["[voice]"]
    n = 1
    for k, s in enumerate(sfx or []):
        inputs += ["-i", s["file"]]
        ms = int(s["at"] * 1000)
        chains.append(f"[{n}:a]aresample=48000,volume={s.get('volume', 0.35)},adelay={ms}|{ms}[s{k}]")
        mixes.append(f"[s{k}]")
        n += 1
    if music:
        inputs += ["-i", music]
        thr = 10 ** (threshold_db / 20)
        chains.append(f"[{n}:a]aresample=48000,atrim=start={music_start},asetpts=PTS-STARTPTS,aloop=loop=-1:size=2e9,"
                      f"atrim=0:{dur},volume={gain_db}dB,afade=t=in:d=0.8,afade=t=out:st={max(0, dur - 1.5)}:d=1.5[m]")
        chains.append(f"[m][key]sidechaincompress=threshold={thr:.4f}:ratio={ratio}:attack={attack_ms}:release={release_ms}[duck]")
        mixes.append("[duck]")
    else:
        chains.append("[key]anullsink")
    return inputs, ";".join(chains) + ";" + "".join(mixes) + f"amix=inputs={len(mixes)}:duration=first:normalize=0{tail}"


def mix(video: str, out: str, music: str | None = None, sfx: list[dict] | None = None, gain_db: float = -17,
        threshold_db: float = -28, ratio: float = 8, attack_ms: float = 5, release_ms: float = 300,
        music_start: float = 0.0) -> None:
    """Голос из рендера + звуки на сменах сцен + музыка, приглушённая под голос. Видео копируется без перекодирования."""
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", video],
                               capture_output=True, text=True).stdout)
    args = (video, sfx, music, dur, gain_db, threshold_db, ratio, attack_ms, release_ms, music_start)
    # проход 1: замер громкости итоговой смеси
    inputs, g = _graph(*args, f",loudnorm=I={TARGET_I}:TP={TARGET_TP}:LRA={TARGET_LRA}:print_format=json[a]")
    r = subprocess.run(["ffmpeg", "-hide_banner", "-y", *inputs, "-filter_complex", g, "-map", "[a]", "-f", "null", "-"],
                       capture_output=True, text=True)
    m = json.loads(re.findall(r"\{[^{}]*\"input_i\"[^{}]*\}", r.stderr)[-1])
    # проход 2: линейная нормализация (без «накачки»), выход 48 кГц
    ln = (f",loudnorm=I={TARGET_I}:TP={TARGET_TP}:LRA={TARGET_LRA}:measured_I={m['input_i']}:measured_TP={m['input_tp']}"
          f":measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true,"
          f"aresample=48000[a]")
    inputs, g = _graph(*args, ln)
    subprocess.run(["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", g, "-map", "0:v", "-map", "[a]",
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", out],
                   check=True)
