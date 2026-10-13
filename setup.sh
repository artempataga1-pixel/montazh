#!/usr/bin/env bash
# Установка монтажёра рилсов (macOS / Linux). Запуск: bash setup.sh
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"

command -v ffmpeg >/dev/null || { echo "Нужен ffmpeg: brew install ffmpeg"; exit 1; }
command -v node >/dev/null || { echo "Нужен Node.js 22+: https://nodejs.org"; exit 1; }
PY=$(command -v python3.11 || true)
[ -n "$PY" ] || { echo "Нужен Python 3.11 (compose.pyc собран под 3.11): brew install python@3.11"; exit 1; }

# окружение вне iCloud/облачных папок — иначе файлы «выгружаются» и всё виснет
"$PY" -m venv ~/.venvs/montazh
~/.venvs/montazh/bin/pip install -q --upgrade pip
~/.venvs/montazh/bin/pip install -q "faster-whisper==1.2.1" "mediapipe==0.10.35" numpy opencv-python-headless fonttools brotli yt-dlp

# модели MediaPipe (Apache 2.0): маска человека и сетка лица
mkdir -p "$HERE/engine/assets/cv"
curl -sSL -o "$HERE/engine/assets/cv/face_landmarker.task" \
  https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task
curl -sSL -o "$HERE/engine/assets/cv/selfie_multiclass_256x256.tflite" \
  https://storage.googleapis.com/mediapipe-models/image_segmenter/selfie_multiclass_256x256/float32/latest/selfie_multiclass_256x256.tflite

# первая загрузка рендера HyperFrames (скачает Chrome)
(cd "$HERE" && npx -y hyperframes@0.8.79 --version >/dev/null 2>&1 || true)

echo "Готово. Дальше:"
echo "  1) положи звуки в engine/assets/sfx (список — ЗВУКИ.md)"
echo "  2) положи свою аватарку в engine/assets/avatar.jpg (для CTA-поля комментария)"
echo "  3) в Claude Code: «смонтируй рилс <путь к видео>»"
