#!/usr/bin/env python3
"""Renders the Live Speaking examiner's lines to audio/sp/*.mp3 with Kokoro (one British examiner voice).
Usage: python3 gen_examiner.py <dir with kokoro-v1.0.onnx and voices-v1.0.bin>"""
import os, subprocess, sys, tempfile
import numpy as np, soundfile as sf
from kokoro_onnx import Kokoro
from live_build import ROOT, script, all_lines
from gen_audio import EQ, SR, trim

VOICE, SPEED = "bf_emma", 0.9


def main():
    mdir = sys.argv[1]
    k = Kokoro(os.path.join(mdir, "kokoro-v1.0.onnx"), os.path.join(mdir, "voices-v1.0.bin"))
    lines = all_lines(script())
    todo = [(t, f) for t, f in lines if not os.path.exists(os.path.join(ROOT, "audio", f))]
    os.makedirs(os.path.join(ROOT, "audio", "sp"), exist_ok=True)
    print(f"{len(lines)} lines, {len(todo)} to render", flush=True)
    for i, (text, f) in enumerate(todo, 1):
        s, sr = k.create(text, voice=VOICE, speed=SPEED, lang="en-gb")
        a = np.concatenate([np.zeros(int(SR * 0.15), np.float32), trim(s.astype(np.float32)), np.zeros(int(SR * 0.2), np.float32)])
        with tempfile.NamedTemporaryFile(suffix=".wav") as w:
            sf.write(w.name, a, SR)
            subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", w.name, "-af", EQ, "-ar", "24000", "-ac", "1",
                            "-b:a", "48k", os.path.join(ROOT, "audio", f)], check=True)
        if i % 20 == 0:
            print(i, flush=True)
    print("done", flush=True)


if __name__ == "__main__":
    main()
