import sys, json
sys.path.insert(0, "../../engine")
from pathlib import Path
import montage
wd = Path(".")
src = Path("src/source.mov")  # исходник автора
if not (wd/"proxy.mp4").exists():
    montage.log("proxy"); montage.proxy(src, wd/"proxy.mp4")
if not (wd/"audio.wav").exists():
    montage.run(["ffmpeg","-v","error","-y","-i","proxy.mp4","-vn","-ac","1","-ar","16000","audio.wav"])
from transcribe import transcribe, refine, fill_gaps
montage.log("transcribe")
t = transcribe("audio.wav", "transcript.json")
t = json.load(open("transcript.json"))
t["words"] = refine("audio.wav", t["words"]); t["refined"] = True
t["words"] = fill_gaps("audio.wav", t["words"]); t["gaps_filled"] = True
json.dump(t, open("transcript.json","w"), ensure_ascii=False, indent=1)
from freeze import face_stats
Path("face.json").write_text(json.dumps(face_stats("proxy.mp4")))
montage.log("done")
