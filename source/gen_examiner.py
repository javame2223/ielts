#!/usr/bin/env python3
"""Renders the Live Speaking examiner's lines with Kokoro in the same voices and sound as the Listening recordings:
a female examiner (bf_alice, the brighter, more expressive voice) and a male examiner (bm_george).
Usage: python3 gen_examiner.py <dir with kokoro-v1.0.onnx and voices-v1.0.bin> [f|m]"""
import os, subprocess, sys, tempfile
import numpy as np, soundfile as sf
from kokoro_onnx import Kokoro
from live_build import ROOT, VOICES, script, all_lines
from gen_audio import EQ, SR, trim

SPEED = 0.9  # the Listening Section 1-2 tempo (~185 words per minute inside phrases)


def main():
    mdir = sys.argv[1]
    only = sys.argv[2:] or list(VOICES)
    k = Kokoro(os.path.join(mdir, "kokoro-v1.0.onnx"), os.path.join(mdir, "voices-v1.0.bin"))
    data = script()
    for v in only:
        voice = VOICES[v][0]
        out_dir = os.path.join(ROOT, "audio", "sp", v)
        os.makedirs(out_dir, exist_ok=True)
        lines = all_lines(data, v)
        todo = [(t, hh) for t, hh in lines if not os.path.exists(os.path.join(out_dir, hh + ".mp3"))]
        print(f"{v}: {len(lines)} lines, {len(todo)} to render", flush=True)
        for i, (text, hh) in enumerate(todo, 1):
            s, sr = k.create(text, voice=voice, speed=SPEED, lang="en-gb")
            a = np.concatenate([np.zeros(int(SR * 0.12), np.float32), trim(s.astype(np.float32)), np.zeros(int(SR * 0.18), np.float32)])
            with tempfile.NamedTemporaryFile(suffix=".wav") as w:
                sf.write(w.name, a, SR)
                subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", w.name, "-af", EQ, "-ar", "24000", "-ac", "1",
                                "-b:a", "48k", os.path.join(out_dir, hh + ".mp3")], check=True)
            if i % 50 == 0:
                print(v, i, flush=True)
    print("done", flush=True)


if __name__ == "__main__":
    main()
