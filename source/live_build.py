"""Live Speaking: the examiner's script (fixed phrases, Part 1 topics, Part 2 cards, Part 3 questions).
Every line the examiner says gets an audio file audio/sp/<hash>.mp3, rendered by gen_examiner.py."""
import hashlib, os, re

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ROOT, "src")

PHRASES = {
    "hi_morning": "Good morning. My name is Emma, and I'll be your examiner today. Can you tell me your full name, please?",
    "hi_afternoon": "Good afternoon. My name is Emma, and I'll be your examiner today. Can you tell me your full name, please?",
    "hi_evening": "Good evening. My name is Emma, and I'll be your examiner today. Can you tell me your full name, please?",
    "call": "Thank you. And what should I call you?",
    "from": "And can you tell me where you're from?",
    "p1intro": "Thank you. Now, in this first part of the test, I'd like to ask you some questions about yourself.",
    "p1intro_short": "In this part of the test, I'd like to ask you some questions about yourself.",
    "why": "Why?",
    "why2": "Why do you think that is?",
    "more": "Can you tell me a bit more about that?",
    "example": "Could you give me an example?",
    "p2intro": "Now, I'm going to give you a topic, and I'd like you to talk about it for one to two minutes. Before you talk, you'll have one minute to think about what you're going to say. You can make some notes if you wish.",
    "p2start": "All right? Remember, you have one to two minutes for this, so don't worry if I stop you. I'll tell you when the time is up. Can you start speaking now, please?",
    "p2add": "Is there anything else you'd like to add?",
    "thanks": "Thank you.",
    "stop": "Thank you. Can I have the paper back, please?",
    "p3intro": "We've been talking about this topic, and I'd like to discuss with you one or two more general questions related to it.",
    "end": "Thank you. That is the end of the speaking test.",
}

TOPIC_NAME = {
    "Work or Study": "what you do", "Home and Accommodation": "where you live", "Hometown": "your hometown",
    "The Area You Live In": "the area you live in", "The City You Live In": "the city you live in",
    "Teacher": "teachers", "Clothing": "clothes", "Dream and Ambition": "dreams and ambitions",
    "Evening Time": "the evening", "Sports Programmes": "sports programmes on TV",
    "Feeling Bored": "feeling bored", "Outer Space and Stars": "outer space and the stars",
}


def fname(text):
    return "sp/" + hashlib.sha1(text.encode("utf-8")).hexdigest()[:12] + ".mp3"


def line(text):
    return [text, fname(text)]


def script():
    data = {"ph": {k: line(v) for k, v in PHRASES.items()}, "p1": [], "cards": []}
    blocks = re.split(r"(?m)^## ", open(os.path.join(SRC, "p1.txt"), encoding="utf-8").read())[1:]
    for n, block in enumerate(blocks, 1):
        lines = [l.strip() for l in block.split("\n") if l.strip()]
        name, _, kind = [x.strip() for x in lines[0].partition("|")]
        topic = TOPIC_NAME.get(name, name.lower())
        intro = f"Let's talk about {topic}." if kind == "core" else f"Now, let's move on to talk about {topic}."
        qs = [line(l[2:].partition("|")[0].strip()) for l in lines[1:] if l.startswith("Q:")]
        data["p1"].append({"n": n, "t": name, "core": kind == "core", "intro": line(intro), "qs": qs})
    cn = 0
    for ln in open(os.path.join(SRC, "cards.txt"), encoding="utf-8"):
        ln = ln.strip()
        if "|" not in ln:
            continue
        cn += 1
        title, _, points, p3 = [x.strip() for x in ln.split("|")]
        ask = "Here is your topic. I'd like you to " + title[0].lower() + title[1:]
        data["cards"].append({"n": cn, "t": title, "pts": [p.strip() for p in points.split(";") if p.strip()],
                              "ask": line(ask), "p3": [line(q.strip()) for q in p3.split(";") if q.strip()]})
    return data


def all_lines(data):
    out = list(data["ph"].values())
    for t in data["p1"]:
        out += [t["intro"]] + t["qs"]
    for c in data["cards"]:
        out += [c["ask"]] + c["p3"]
    return out
