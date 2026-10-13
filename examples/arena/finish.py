"""Финал ARENA (по образцу IMG_9199) — ТЕСТ ЗВУКА (автор 06.10: «со звуком ничего не делай»).
Голос режется прямо из оригинального MOV (без прокси и промежуточных AAC), без loudnorm, highpass, компрессии и
пересэмплинга: исходные 44,1 кГц моно. Стыки — микро-фейды 10 мс (как в мастере), чтобы не щёлкало.
Делает два файла:
  final_v{V}.mp4        — голос + звуки эффектов (amix normalize=0: громкость голоса не меняется)
  голос-без-эффектов_v{V}.mp4  — только голос
Метаданные (в т.ч. GPS из iPhone) не переносятся."""
import json
import subprocess
from pathlib import Path

WD = Path(__file__).resolve().parent
SRC = "src/source.mov"  # исходник: голос берём из оригинала
QUIET = (-1, -1)  # тихих кусков нет
R = json.load(open(WD / "master_words.json", encoding="utf-8"))["ranges"]
sfx = json.load(open(WD / "craft" / "hf" / "sfx.json", encoding="utf-8"))
import sys
V = sys.argv[1] if len(sys.argv) > 1 else "1"
render = WD / "craft" / "render.mp4"

parts, labels = [], []
for i, (a, b) in enumerate(R):
    d = b - a
    g = ",highpass=f=80,volume=15dB,alimiter=limit=0.9" if abs(a - QUIET[0]) < 0.05 else ""
    parts.append(f"[0:a]atrim={a}:{b},asetpts=PTS-STARTPTS{g},afade=t=in:d=0.01,afade=t=out:st={d - 0.01:.3f}:d=0.01[a{i}];")
    labels.append(f"[a{i}]")
voice = "".join(parts) + "".join(labels) + f"concat=n={len(R)}:v=0:a=1[voice]"
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", SRC, "-filter_complex", voice, "-map", "[voice]",
                "-ar", "48000", "-c:a", "pcm_s16le", str(WD / "voice_raw.wav")], check=True)

# только голос
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(render), "-i", str(WD / "voice_raw.wav"), "-map", "0:v", "-map", "1:a",
                "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-map_metadata", "-1", "-shortest", "-movflags", "+faststart",
                str(WD / f"голос-без-эффектов_v{V}.mp4")], check=True)

# голос + эффекты. Правка автора 12.10: эффекты НИКОГДА не громче голоса («звуки начинаются — меня не слышно»).
# 1) все эффекты ×0,16 и пиковый лимит на их сумму; 2) пока звучит голос, эффекты приглушаются (sidechain по голосу);
# голос не обрабатывается.
SFX_GAIN = 1.0
PER = {"riser": 0.35, "whoosh-cinematic": 0.6, "impact-bass-1": 0.7, "impact-bass-2": 0.7, "glitch-1": 0.8, "pop": 0.6}  # длинные/жирные звуки тише
FX_BUS = 0.42  # громкость шины эффектов после компрессора (подбирается замером: худшее окно ≈ −5 дБ к голосу)
ins, fl, mix = ["-i", str(WD / "voice_raw.wav")], [], []
for k, s in enumerate(sfx, 1):
    ins += ["-i", s["file"]]
    ms = int(s["at"] * 1000)
    fl.append(f"[{k}:a]aresample=48000,aformat=channel_layouts=mono,volume={s['volume'] * SFX_GAIN * PER.get(Path(s['file']).stem, 1):.4f},adelay={ms}|{ms}[s{k}];")
    mix.append(f"[s{k}]")
graph = ("[0:a]aresample=48000,asplit=2[v][key];" + "".join(fl) + "".join(mix) +
         f"amix=inputs={len(mix)}:normalize=0:duration=longest,acompressor=threshold=0.01:ratio=12:attack=1:release=120:makeup=6,volume={FX_BUS},alimiter=limit=0.2:level=false[fx];"
         "[fx][key]sidechaincompress=threshold=0.012:ratio=4:attack=10:release=250:makeup=1[duck];"
         "[v][duck]amix=inputs=2:normalize=0:duration=first[mix]")
subprocess.run(["ffmpeg", "-v", "error", "-y", *ins, "-filter_complex", graph, "-map", "[mix]", "-c:a", "pcm_s16le",
                str(WD / "voice_sfx.wav")], check=True)
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(render), "-i", str(WD / "voice_sfx.wav"), "-map", "0:v", "-map", "1:a",
                "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-map_metadata", "-1", "-shortest", "-movflags", "+faststart",
                str(WD / f"final_v{V}.mp4")], check=True)
print(WD / f"final_v{V}.mp4", WD / f"голос-без-эффектов_v{V}.mp4")
