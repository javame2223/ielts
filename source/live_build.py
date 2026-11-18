"""Live Speaking: the examiner's script (fixed phrases, reactions, Part 1 topics, Part 2 cards, Part 3 questions,
follow-up questions that depend on the candidate's answer). Every line gets audio in two voices:
audio/sp/f/<hash>.mp3 (female examiner) and audio/sp/m/<hash>.mp3 (male examiner), rendered by gen_examiner.py."""
import hashlib, os, re

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ROOT, "src")
VOICES = {"f": ("bf_alice", "Emma"), "m": ("bm_george", "James")}

PHRASES = {
    "call": "Nice to meet you! And what should I call you?",
    "call_strict": "Thank you. And what should I call you?",
    "from": "Great. And can you tell me where you're from?",
    "from_strict": "And can you tell me where you're from?",
    "p1intro": "Thank you. Now, in this first part of the test, I'd like to ask you some questions about yourself.",
    "p1intro_short": "In this part of the test, I'd like to ask you some questions about yourself.",
    "why": "Why?",
    "why2": "Why do you think that is?",
    "more": "Can you tell me a bit more about that?",
    "example": "Could you give me an example?",
    "p2intro": "Now, I'm going to give you a topic, and I'd like you to talk about it for one to two minutes. Before you talk, you'll have one minute to think about what you're going to say. You can make some notes if you wish.",
    "p2start": "All right? Remember, you have one to two minutes for this, so don't worry if I stop you. I'll tell you when the time is up. Can you start speaking now, please?",
    "p2add": "Is there anything else you'd like to add?",
    "p2good": "Thank you, that was a really good talk!",
    "thanks": "Thank you.",
    "stop": "Thank you. Can I have the paper back, please?",
    "p3intro": "We've been talking about this topic, and I'd like to discuss with you one or two more general questions related to it.",
    "end": "Thank you. That is the end of the speaking test.",
    "end_friendly": "Thank you very much! That is the end of the speaking test. Well done!",
}
REACT = {
    "long": ["Great answer, thank you! Let's move on to the next question.",
             "That's really interesting, thank you. Okay, next question.",
             "Lovely, thanks for sharing that! Let's move on.",
             "Excellent, that's a very full answer. Next question."],
    "mid": ["Okay, thank you. Let's move on.",
            "Good answer. Let's move on to the next question.",
            "Right, I see. Next question.",
            "Thanks! Now, here's another question."],
    "fu": ["I see, thank you.", "Okay, that makes sense.", "Interesting, thank you!", "Ah, right. Thank you."],
    "p3": ["That's a thoughtful answer, thank you.", "Good point! Let's think about another question.",
           "Interesting, thank you. Here's another one.", "I see what you mean. Okay, next question."],
}
GREET = "Good {tod}! My name is {name}, and I'll be your examiner today. Can you tell me your full name, please?"

TOPIC_NAME = {
    "Work or Study": "what you do", "Home and Accommodation": "where you live", "Hometown": "your hometown",
    "The Area You Live In": "the area you live in", "The City You Live In": "the city you live in",
    "Teacher": "teachers", "Clothing": "clothes", "Dream and Ambition": "dreams and ambitions",
    "Evening Time": "the evening", "Sports Programmes": "sports programmes on TV",
    "Feeling Bored": "feeling bored", "Outer Space and Stars": "outer space and the stars",
}


def h(text):
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]


def line(text):
    return [text, h(text)]


def followups():
    fu, cur = {}, None
    for ln in open(os.path.join(SRC, "live_fu.txt"), encoding="utf-8"):
        ln = ln.strip()
        if not ln or ln.startswith("//"):
            continue
        if ln.startswith("Q: "):
            cur = fu.setdefault(ln[3:].strip(), {})
        elif ln[:2] in ("+ ", "- ", "= "):
            cur[ln[0]] = line(ln[2:].strip())
    return fu


def script():
    fu = followups()
    q = lambda text: line(text) + [fu.get(text, {})]
    data = {"ph": {k: line(v) for k, v in PHRASES.items()},
            "react": {k: [line(x) for x in v] for k, v in REACT.items()},
            "greet": {v: {tod: line(GREET.format(tod=tod, name=name)) for tod in ("morning", "afternoon", "evening")}
                      for v, (_, name) in VOICES.items()},
            "p1": [], "cards": []}
    blocks = re.split(r"(?m)^## ", open(os.path.join(SRC, "p1.txt"), encoding="utf-8").read())[1:]
    for n, block in enumerate(blocks, 1):
        lines = [l.strip() for l in block.split("\n") if l.strip()]
        name, _, kind = [x.strip() for x in lines[0].partition("|")]
        topic = TOPIC_NAME.get(name, name.lower())
        intro = f"Let's talk about {topic}." if kind == "core" else f"Now, let's move on to talk about {topic}."
        qs = [q(l[2:].partition("|")[0].strip()) for l in lines[1:] if l.startswith("Q:")]
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
                              "ask": line(ask), "p3": [q(x.strip()) for x in p3.split(";") if x.strip()]})
    return data


def all_lines(data, voice):
    """Every (text, hash) the examiner with this voice can say."""
    out = list(data["ph"].values()) + [x for v in data["react"].values() for x in v] + list(data["greet"][voice].values())
    def add_q(qq):
        out.append(qq[:2])
        out.extend(qq[2].values())
    for t in data["p1"]:
        out.append(t["intro"])
        for qq in t["qs"]:
            add_q(qq)
    for c in data["cards"]:
        out.append(c["ask"])
        for qq in c["p3"]:
            add_q(qq)
    seen, uniq = set(), []
    for t, hh in out:
        if hh not in seen:
            seen.add(hh)
            uniq.append((t, hh))
    return uniq
