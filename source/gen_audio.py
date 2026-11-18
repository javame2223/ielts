#!/usr/bin/env python3
"""Renders every listening section to audio/listening-NN.mp3 with the Kokoro offline TTS model.

The delivery is tuned to a reference recording of a real IELTS Section 1 dialogue
(measured, not copied): British voices only, ~185 words per minute inside phrases,
~0.5 s between turns, presence-range EQ and -19.5 LUFS loudness.

Usage: python3 gen_audio.py <dir with kokoro-v1.0.onnx and voices-v1.0.bin> [--out DIR] [only_number ...]
"""
import os, random, subprocess, sys, tempfile
import numpy as np, soundfile as sf
from kokoro_onnx import Kokoro
from build import ROOT, listening_units

# British voices, ordered by role. The first woman in a dialogue (usually the person answering:
# receptionist, guide, tutor) gets the brighter, more expressive voice; the second a lower, steadier one.
FEMALE_FIRST = ["bf_alice", "bf_isabella", "bf_lily"]   # ~200-210 Hz, wide pitch range
FEMALE_SECOND = ["bf_emma", "bf_lily", "bf_isabella"]   # ~180-200 Hz, steadier
MALE = ["bm_george", "bm_fable", "bm_daniel"]
NARRATOR = "bm_daniel"
SPEED = {"Section 1": 0.88, "Section 2": 0.88, "Section 3": 0.92, "Section 4": 0.92}
NARRATOR_SPEED = 0.9
SR = 24000
# EQ measured against the reference: less low-mid body, more 2-6 kHz presence, softer top end.
EQ = ("lowshelf=f=180:g=-2,equalizer=f=380:t=o:w=1:g=1.5,equalizer=f=750:t=o:w=1:g=-2,"
      "equalizer=f=1500:t=o:w=1:g=1,equalizer=f=3000:t=o:w=1:g=4,equalizer=f=5000:t=o:w=1:g=2,"
      "highshelf=f=9000:g=2,highpass=f=70,"
      "loudnorm=I=-19.5:TP=-2:LRA=7")


def trim(a, thr=0.008, pad=0.04):
    """Cut the synthesizer's own leading and trailing silence so pauses are set here."""
    idx = np.where(np.abs(a) > thr)[0]
    if not len(idx):
        return a
    s = max(0, idx[0] - int(pad * SR)); e = min(len(a), idx[-1] + int(pad * SR))
    return a[s:e]


def assign_voices(n, voices):
    """Map each speaker of a unit to a voice, rotating choices between units for variety."""
    if len(voices) == 1:
        (sp, g), = voices.items()
        pool = ["bf_alice", "bf_isabella", "bf_lily", "bf_emma"] if g == "f" else ["bm_george", "bm_fable"]
        return {sp: pool[n % len(pool)]}
    vmap, women, men = {}, 0, 0
    for sp, g in voices.items():
        if g == "f":
            pool = FEMALE_FIRST if women == 0 else FEMALE_SECOND
            v = pool[n % len(pool)] if women == 0 else next(x for x in pool if x not in vmap.values())
            women += 1
        else:
            v = ["bm_george", "bm_fable"][men % 2]
            men += 1
        vmap[sp] = v
    return vmap


def main():
    args = sys.argv[1:]
    mdir = args.pop(0)
    out_dir = os.path.join(ROOT, "audio")
    if "--out" in args:
        i = args.index("--out"); out_dir = args[i + 1]; del args[i:i + 2]
    only = {int(x) for x in args}
    k = Kokoro(os.path.join(mdir, "kokoro-v1.0.onnx"), os.path.join(mdir, "voices-v1.0.bin"))
    os.makedirs(out_dir, exist_ok=True)

    def say(text, voice, speed):
        s, sr = k.create(text, voice=voice, speed=speed, lang="en-gb")
        assert sr == SR
        return trim(s.astype(np.float32))

    gap = lambda sec: np.zeros(int(SR * sec), dtype=np.float32)
    for n, u in enumerate(listening_units(), 1):
        out = os.path.join(out_dir, f"listening-{n:02d}.mp3")
        if only and n not in only:
            continue
        rnd = random.Random(n)
        vmap = assign_voices(n, u["voices"])
        speed = SPEED[u["cat"]]
        parts = [say(f"{u['cat']}. {u['ctx']}", NARRATOR, NARRATOR_SPEED), gap(1.0),
                 say("First, you have some time to look at questions one to ten.", NARRATOR, NARRATOR_SPEED), gap(20),
                 say("Now listen carefully and answer questions one to ten.", NARRATOR, NARRATOR_SPEED), gap(1.8)]
        prev = None
        for sp, tx in u["lines"]:
            if prev is not None:
                parts.append(gap(rnd.uniform(0.3, 0.6) if sp != prev else rnd.uniform(0.25, 0.4)))
            parts.append(say(tx, vmap[sp], speed))
            prev = sp
        parts += [gap(2.0), say(f"That is the end of {u['cat'].lower()}. You now have half a minute to check your answers.",
                                NARRATOR, NARRATOR_SPEED), gap(0.6)]
        audio = np.concatenate(parts)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as t:
            sf.write(t.name, audio, SR)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", t.name, "-af", EQ, "-ac", "1", "-ar", "24000",
                        "-codec:a", "libmp3lame", "-b:a", "64k",
                        "-metadata", f"title=Listening {n:02d}. {u['name']}",
                        "-metadata", "album=IELTS Skills Pack", "-metadata", f"track={n}", out], check=True)
        os.unlink(t.name)
        print(f"{n:02d} {u['name']} [{u['cat']}] {len(audio)/SR:.0f}s {vmap}", flush=True)


if __name__ == "__main__":
    main()
