#!/usr/bin/env python3
"""Builds ielts/IELTS_4_Skills.html from the source files in ielts/src."""
import glob, html, json, os, re, shutil
from gram_build import build_grammar, STAGES
from live_build import script as live_script

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ROOT, "src")
OUT = os.path.join(ROOT, "IELTS_4_Skills.html")
E = html.escape

INSTR = {
    "TFNG": "Do the following statements agree with the information in the passage? Choose <b>TRUE</b>, <b>FALSE</b> or <b>NOT GIVEN</b>.",
    "YNNG": "Do the following statements agree with the views of the writer? Choose <b>YES</b>, <b>NO</b> or <b>NOT GIVEN</b>.",
    "TF": "Decide whether each statement is <b>TRUE</b> or <b>FALSE</b>.",
    "MCQ": "Choose the correct letter, <b>A</b>, <b>B</b>, <b>C</b> or <b>D</b>.",
    "GAP": "Complete the sentences. Write <b>NO MORE THAN TWO WORDS AND/OR A NUMBER</b> from the passage for each answer.",
    "SUM": "Complete the summary. Write <b>NO MORE THAN TWO WORDS AND/OR A NUMBER</b> from the passage for each answer.",
    "SHORT": "Answer the questions. Write <b>NO MORE THAN THREE WORDS AND/OR A NUMBER</b> from the passage for each answer.",
    "MATCH": "Which paragraph contains the following information? Choose the correct letter.",
    "HEAD": "Choose the correct heading for each paragraph from the list of headings below.",
    "LGAP": "Complete the notes. Write <b>NO MORE THAN TWO WORDS AND/OR A NUMBER</b> for each answer.",
    "LMCQ": "Choose the correct letter, <b>A</b>, <b>B</b> or <b>C</b>.",
    "LSHORT": "Answer the questions. Write <b>NO MORE THAN THREE WORDS AND/OR A NUMBER</b>.",
}
FULL = {"T": "TRUE", "F": "FALSE", "NG": "NOT GIVEN", "Y": "YES", "N": "NO"}


def select(opts):
    return "<select><option value=''>—</option>" + "".join(
        f"<option>{E(o)}</option>" for o in opts) + "</select>"


def render_questions(groups, nparas, errors, where):
    out, n = [], 0
    for kind, head, items in groups:
        if kind not in INSTR:
            errors.append(f"{where}: unknown question type {kind}")
            continue
        out.append(f"<div class='qgroup'><p class='instr'>{INSTR[kind]}</p>")
        heads = []
        if kind == "HEAD":
            heads = [h.strip() for h in head.split(";") if h.strip()]
            out.append("<ul class='heads'>" + "".join(f"<li>{E(h)}</li>" for h in heads) + "</ul>")
        for it in items:
            n += 1
            parts = [p.strip() for p in it.split("|")]
            ans = parts[-1]
            body = parts[0]
            if len(parts) < 2 or not ans:
                errors.append(f"{where}: question {n} has no answer: {it}")
                continue
            ctrl, shown = "", ans
            if kind in ("TFNG", "YNNG", "TF"):
                opts = {"TFNG": ["TRUE", "FALSE", "NOT GIVEN"], "YNNG": ["YES", "NO", "NOT GIVEN"], "TF": ["TRUE", "FALSE"]}[kind]
                if FULL.get(ans) not in opts:
                    errors.append(f"{where}: q{n} bad answer {ans}")
                shown = FULL.get(ans, ans)
                ctrl = select(opts)
                q = f"{E(body)} {ctrl}"
            elif kind in ("MCQ", "LMCQ"):
                opts = parts[1:-1]
                letters = [o[0] for o in opts]
                if ans not in letters:
                    errors.append(f"{where}: q{n} MCQ answer {ans} not in options")
                q = (f"{E(body)} {select(letters)}<ul class='opts'>" +
                     "".join(f"<li>{E(o)}</li>" for o in opts) + "</ul>")
            elif kind == "MATCH":
                letters = [chr(65 + i) for i in range(nparas)]
                if ans not in letters:
                    errors.append(f"{where}: q{n} MATCH answer {ans} out of range")
                q = f"{E(body)} {select(letters)}"
            elif kind == "HEAD":
                nums = [h.split(".")[0].strip() for h in heads]
                if ans not in nums:
                    errors.append(f"{where}: q{n} HEAD answer {ans} not in list")
                q = f"{E(body)} {select(nums)}"
            else:  # gap / short
                inp = "<input type='text' autocomplete='off'>"
                if "____" in body:
                    q = E(body).replace("____", inp, 1)
                else:
                    q = f"{E(body)} {inp}"
            out.append(f"<div class='q' data-a=\"{E(shown)}\"><span class='n'>{n}</span> "
                       f"<span class='qt'>{q}</span> <span class='ans'>✔ {E(shown)}</span></div>")
        out.append("</div>")
    out.append("<div class='btns'><button class='chk'>Проверить</button>"
               "<button class='shw'>Показать ответы</button>"
               "<button class='rst'>Сбросить</button><span class='score'></span></div>")
    return "\n".join(out), n


def parse_blocks(text):
    blocks = re.split(r"(?m)^## ", text)
    return [b for b in blocks[1:] if b.strip()]


def parse_block(block):
    lines = block.split("\n")
    title = lines[0].strip()
    sec = {"body": []}
    groups, cur = [], "body"
    for ln in lines[1:]:
        if ln.startswith("@"):
            tag = ln[1:].strip()
            if tag.startswith("Q "):
                rest = tag[2:].strip().split(" ", 1)
                groups.append((rest[0], rest[1] if len(rest) > 1 else "", []))
                cur = "Q"
            else:
                key = tag.split(" ", 1)
                cur = key[0]
                sec.setdefault(cur, [])
                if len(key) > 1:
                    sec[cur].append(key[1])
        elif ln.strip():
            if cur == "Q":
                groups[-1][2].append(ln.strip())
            else:
                sec[cur].append(ln.strip())
    return title, sec, groups


def bold_vocab(par, words):
    for w in words:
        base = re.escape(w)
        par, k = re.subn(rf"(?<![\w>])({base}\w*)", r"<b class='vw'>\1</b>", par, count=1, flags=re.I)
        if k:
            words.remove(w)
            return bold_vocab(par, words)
    return par


def load_extensions(errors):
    """Extra paragraphs, words and questions per passage (src/x*.txt), keyed by passage title."""
    ext = {}
    for f in sorted(glob.glob(os.path.join(SRC, "x*.txt"))):
        for block in parse_blocks(open(f, encoding="utf-8").read()):
            title, sec, groups = parse_block(block)
            if title in ext:
                errors.append(f"extension '{title}' defined twice")
            ext[title] = (sec, groups)
    return ext


def apply_extension(paras, vocab_lines, groups, ext, errors, where):
    sec, new_groups = ext
    # lines after "@INSERT n" are collected under that key: first item is n, the rest are paragraphs
    extra = sec["INSERT"][1:] if sec.get("INSERT") else sec["body"]
    ins = int(sec["INSERT"][0]) if sec.get("INSERT") else len(paras) - 1
    if not 0 < ins <= len(paras):
        errors.append(f"{where}: bad @INSERT {ins}")
    shift = lambda letter: chr(ord(letter) + len(extra)) if ord(letter) - 65 >= ins else letter
    fixed = []
    for kind, head, items in groups:  # old questions keep pointing at the same paragraphs
        if kind == "MATCH":
            items = [it.rsplit("|", 1)[0] + "| " + shift(it.rsplit("|", 1)[1].strip()) for it in items]
        elif kind == "HEAD":
            items = [re.sub(r"^Paragraph ([A-Z])", lambda m: "Paragraph " + shift(m.group(1)), it) for it in items]
        fixed.append((kind, head, items))
    return paras[:ins] + extra + paras[ins:], vocab_lines + sec.get("V", []), fixed + new_groups


def build_reading(errors):
    secs, toc, cats, total_q = [], [], {}, 0
    num = 0
    exts = load_extensions(errors)
    used = set()
    for f in sorted(glob.glob(os.path.join(SRC, "r*.txt"))):
        for block in parse_blocks(open(f, encoding="utf-8").read()):
            num += 1
            title, sec, groups = parse_block(block)
            name, _, cat = [x.strip() for x in title.partition("|")]
            where = f"Reading {num} ({name})"
            paras, vlines = sec["body"], sec.get("V", [])
            if name in exts:
                used.add(name)
                paras, vlines, groups = apply_extension(paras, vlines, groups, exts[name], errors, where)
            vocab = [v.split("=", 1) for v in vlines]
            if len(vocab) < 6:
                errors.append(f"{where}: only {len(vocab)} vocab items")
            pending = [v[0].strip().split(" (")[0] for v in vocab]
            full = " ".join(paras).lower()
            for w in pending:
                if w.lower()[: max(3, len(w) - 2)] not in full:
                    errors.append(f"{where}: vocab '{w}' not found in text")
            ptxt = []
            for i, p in enumerate(paras):
                ptxt.append(f"<p><span class='pl'>{chr(65+i)}</span> {bold_vocab(E(p), pending)}</p>")
            qhtml, nq = render_questions(groups, len(paras), errors, where)
            total_q += nq
            for kind, _, items in groups:
                if kind in ("GAP", "SUM", "SHORT"):
                    for it in items:
                        a = it.split("|")[-1].strip()
                        if not any(x.strip().lower() in full for x in a.split("/")):
                            errors.append(f"{where}: answer '{a}' not in text")
            if nq < 8 or (name in exts and nq != 13):
                errors.append(f"{where}: {nq} questions")
            words = sum(len(p.split()) for p in paras)
            vhtml = "".join(f"<li><b>{E(a.strip())}</b> — {E(b.strip())}</li>" for a, b in vocab)
            cats.setdefault(cat, []).append(num)
            toc.append(f"<a href='#r{num}' title='{E(name)}'>{num}</a>")
            secs.append(
                f"<section class='unit reading' id='r{num}' data-k='r{num}' data-n='{num}' data-title=\"{E(name)}\" "
                f"data-cat=\"{E(cat)}\" data-words='{words}' data-vocab=\"{E(' | '.join(a.strip() for a, _ in vocab))}\">"
                f"<div class='panes'><div class='pane pane-text'>"
                f"<details class='vocab' open><summary>Новые слова ({len(vocab)})</summary><ul>{vhtml}</ul></details>"
                f"<div class='text'>{''.join(ptxt)}</div></div>"
                f"<div class='pane pane-q'><div class='qs'>{qhtml}</div></div></div></section>")
    for t in exts:
        if t not in used:
            errors.append(f"extension '{t}' matches no passage")
    return num, total_q, "".join(toc), "\n".join(secs)


def listening_units():
    """All listening sections, ordered Section 1..4 (stable within a section)."""
    units = []
    for f in sorted(glob.glob(os.path.join(SRC, "l*.txt"))):
        for block in parse_blocks(open(f, encoding="utf-8").read()):
            title, sec, groups = parse_block(block)
            name, _, cat = [x.strip() for x in title.partition("|")]
            lines = []
            for ln in sec.get("S", []):
                m = re.match(r"^([A-Z][A-Za-z .]{0,18}):\s*(.*)$", ln)
                lines.append((m.group(1), m.group(2)) if m else ("", ln))
            voices = dict(x.split("=") for x in " ".join(sec.get("VOICES", [])).split())
            units.append({"name": name, "cat": cat, "ctx": " ".join(sec.get("CTX", [])),
                          "lines": lines, "voices": voices, "groups": groups})
    units.sort(key=lambda u: u["cat"])
    return units


def build_listening(errors):
    secs, toc = [], []
    units = listening_units()
    for num, u in enumerate(units, 1):
        name, cat = u["name"], u["cat"]
        where = f"Listening {num} ({name})"
        for sp, _ in u["lines"]:
            if sp not in u["voices"]:
                errors.append(f"{where}: no voice for speaker '{sp}'")
                break
        script = [f"<p data-sp=\"{E(sp)}\"><b>{E(sp)}{':' if sp else ''}</b> <span>{E(tx)}</span></p>"
                  for sp, tx in u["lines"]]
        qhtml, nq = render_questions(u["groups"], 0, errors, where)
        if nq != 10:
            errors.append(f"{where}: {nq} questions (expected 10)")
        audio = f"audio/listening-{num:02d}.mp3"
        if not os.path.exists(os.path.join(ROOT, audio)):
            errors.append(f"{where}: missing {audio}")
        toc.append(f"<a href='#l{num}' title='{E(name)}'>{num}</a>")
        secs.append(
            f"<section class='unit listen' id='l{num}' data-k='l{num}' data-n='{num}' data-title=\"{E(name)}\" "
            f"data-cat=\"{E(cat)}\"><p class='ctx'>{E(u['ctx'])}</p>"
            f"<div class='player'><audio controls preload='none' src='{audio}'></audio>"
            f"<label>Скорость <select class='rate'><option value='0.85'>0.85×</option>"
            f"<option value='1' selected>1×</option><option value='1.15'>1.15×</option></select></label>"
            f"<a class='dl' href='{audio}' download>mp3</a>"
            f"<span class='tts' hidden><button class='play'>▶ Озвучить браузером</button>"
            f"<button class='stop'>■ Стоп</button></span><span class='pstat'></span></div>"
            f"<div class='qs'>{qhtml}</div>"
            f"<details class='script'><summary>Транскрипт (открывай только после проверки)</summary>"
            f"{''.join(script)}</details></section>")
    return len(units), "".join(toc), "\n".join(secs)


def vocab_html(line):
    items = [x.strip() for x in line.split(";") if x.strip()]
    return "; ".join(f"<b>{E(a.strip())}</b> — {E(c.strip())}" for a, _, c in (x.partition("=") for x in items))


def load_card_answers(errors):
    ans = {}
    for f in sorted(glob.glob(os.path.join(SRC, "a2*.txt"))):
        cur = None
        for ln in open(f, encoding="utf-8"):
            ln = ln.strip()
            if not ln:
                continue
            if ln.startswith("# "):
                cur = ans.setdefault(int(ln[2:]), {"A": "", "V": "", "G": "", "3": []})
            elif ln[:2] in ("A:", "V:", "G:"):
                cur[ln[0]] = ln[2:].strip()
            elif ln.startswith("3:"):
                cur["3"].append(ln[2:].strip())
            else:
                errors.append(f"{os.path.basename(f)}: unexpected line: {ln[:40]}")
    return ans


def build_cards(errors):
    out, n = [], 0
    answers = load_card_answers(errors)
    for ln in open(os.path.join(SRC, "cards.txt"), encoding="utf-8"):
        ln = ln.strip()
        if not ln:
            continue
        if "|" not in ln:
            out.append(f"<h4>{E(ln)}</h4>")
            continue
        n += 1
        topic, new, bullets, qs = [x.strip() for x in ln.split("|")]
        qs = [q.strip() for q in qs.split(";")]
        a = answers.get(n)
        model = ""
        if not a or not a["A"] or len(a["3"]) != len(qs):
            errors.append(f"Speaking card {n}: missing model answer or Part 3 answers")
        else:
            wc = len(a["A"].split())
            if not 140 <= wc <= 230:
                errors.append(f"Speaking card {n}: model answer is {wc} words")
            model = (f"<details class='model'><summary>Образец ответа (Band 8), разбор и ответы Part 3</summary>"
                     f"<p>{E(a['A'])}</p><div class='note'><b>Лексика:</b> {vocab_html(a['V'])}</div>"
                     f"<div class='note'><b>Разбор:</b> {E(a['G'])}</div><div class='note'><b>Part 3 — образцы ответов</b></div><ol class='p3'>"
                     + "".join(f"<li><i>{E(q)}</i><p>{E(x)}</p></li>" for q, x in zip(qs, a["3"])) + "</ol></details>")
        out.append(
            f"<div class='cue' id='c{n}' data-k='c{n}' data-title=\"{E(topic)}\"><b>{n}. {E(topic)}</b>{'<b class=new>NEW</b>' if new else ''}"
            "<div>You should say:</div><ul>" + "".join(f"<li>{E(b.strip())}</li>" for b in bullets.split(";")) +
            "</ul><div><i>Part 3:</i></div><ul>" + "".join(f"<li>{E(q)}</li>" for q in qs) + "</ul>" + model
            + f"<button class='done' data-k='c{n}'>Отметить как сделано</button></div>")
    return "\n".join(out), n


def build_part1(errors):
    out, core_done = ["<h4>Обязательные темы (одна из них будет всегда)</h4>"], False
    pn = 0
    for block in parse_blocks(open(os.path.join(SRC, "p1.txt"), encoding="utf-8").read()):
        lines = [l.strip() for l in block.split("\n") if l.strip()]
        name, _, kind = [x.strip() for x in lines[0].partition("|")]
        if kind != "core" and not core_done:
            core_done = True
            out.append("<h4>Сменные темы сезона</h4>")
        qa, voc, note = [], "", ""
        for l in lines[1:]:
            if l.startswith("Q:"):
                q, _, a = l[2:].partition("|")
                if not a.strip():
                    errors.append(f"Part 1 {name}: no answer for {q}")
                qa.append((q.strip(), a.strip()))
            elif l.startswith("V:"):
                voc = l[2:].strip()
            elif l.startswith("N:"):
                note = l[2:].strip()
        pn += 1
        out.append(
            f"<details class='model p1' id='p{pn}' data-k='p{pn}' data-title=\"Part 1: {E(name)}\"><summary><span class='t'>{E(name)}.</span> " + " · ".join(E(q) for q, _ in qa) + "</summary>"
            + "".join(f"<p><i>{E(q)}</i><br>{E(a)}</p>" for q, a in qa)
            + (f"<div class='note'><b>Лексика:</b> {vocab_html(voc)}</div>" if voc else "")
            + (f"<div class='note'><b>Разбор:</b> {E(note)}</div>" if note else "")
            + f"<button class='done' data-k='p{pn}'>Отметить как сделано</button></details>")
    return "\n".join(out)


def load_models(errors):
    models = {}
    for f in sorted(glob.glob(os.path.join(SRC, "e*.txt"))):
        cur = None
        for ln in open(f, encoding="utf-8"):
            ln = ln.rstrip("\n").strip()
            if not ln:
                continue
            if ln.startswith("# "):
                cur = models.setdefault(ln[2:].strip(), {"P": "", "E": [], "V": "", "N": ""})
            elif ln[:2] in ("P:", "E:", "V:", "N:"):
                if ln[0] == "E":
                    cur["E"].append(ln[2:].strip())
                else:
                    cur[ln[0]] = ln[2:].strip()
            else:
                errors.append(f"{os.path.basename(f)}: unexpected line: {ln[:40]}")
    return models


def build_wex(errors, fname="wex.txt"):
    """Interactive Writing exercises (src/wex*.txt), keyed by id."""
    out = {}
    for block in parse_blocks(open(os.path.join(SRC, fname), encoding="utf-8").read()):
        title, sec, groups = parse_block(block)
        name, _, key = [x.strip() for x in title.partition("|")]
        qhtml, nq = render_questions(groups, 0, errors, f"Exercise {key}")
        for kind, _, items in groups:
            if kind in ("GAP", "SHORT"):
                for it in items:
                    if "____" not in it.split("|")[0]:
                        errors.append(f"Exercise {key}: gap marker missing in: {it[:40]}")
        intro = "".join(f"<p>{E(x)}</p>" for x in sec.get("INTRO", []))
        out[key] = (f"<section class='unit wex' id='wx-{key}' data-k='wx-{key}' data-title=\"{E(name)}\">"
                    f"<h4>{E(name)}</h4>{intro}<div class='qs'>{qhtml}</div></section>")
    return out


def build_task1(errors):
    """Writing Task 1 section: layout + old and new practice cards + exercises, numbered in order."""
    rd = lambda n: open(os.path.join(SRC, n), encoding="utf-8").read()
    layout = rd("w1_layout.html")
    pieces = {}
    for f in ("w1_old.html", "w1_new.html"):
        for m in re.finditer(r"<!--(OLD|NEW):(\w+)-->\n(.*?)(?=\n<!--(?:OLD|NEW):|\Z)", rd(f), flags=re.S):
            pieces[(m.group(1), m.group(2))] = m.group(3).strip()
    wex = build_wex(errors)

    def sub(m):
        token = m.group(1)
        if token.startswith("WEX:"):
            key = token[4:]
            if key not in wex:
                errors.append(f"Task 1: missing exercise {key}"); return ""
            return wex.pop(key)
        kind, key = ("NEW", token[4:]) if token.startswith("NEW:") else ("OLD", token[3:])
        if (kind, key) not in pieces:
            errors.append(f"Task 1: missing {kind} {key}"); return ""
        return pieces.pop((kind, key))

    page = re.sub(r"\{\{(OLD\d+|NEW:\w+|WEX:\w+)\}\}", sub, layout)
    for k in list(pieces) + list(wex):
        errors.append(f"Task 1: unused piece {k}")
    n = [0]
    def num(m):
        n[0] += 1
        return f"<h3>Practice {n[0]} — "
    return re.sub(r"<h3>Practice(?: Task 1\.\d+)? — ", num, page)


def vocab_items(line):
    out = []
    for x in line.split(";"):
        a, _, c = x.strip().partition("=")
        if a.strip():
            mean, _, use = c.strip().partition(" — ")
            out.append((a.strip(), mean.strip(), use.strip()))
    return out


def highlight(paras, items, key, warn):
    """Wrap the first occurrence of each vocabulary phrase in the essay in <mark class=kw>."""
    text = "\n".join(paras)
    spans = []
    for phrase, _, _ in sorted(items, key=lambda x: -len(x[0])):
        core = re.sub(r"\s*\(.*?\)", "", phrase).strip()
        pat = r"(?<![A-Za-z])" + r".{1,40}?".join(re.escape(x.strip()) for x in core.split("…")) + r"(?![A-Za-z])"
        for m in re.finditer(pat, text, flags=re.I):
            if all(m.end() <= a or m.start() >= b for a, b in spans):
                spans.append((m.start(), m.end()))
                break
        else:
            warn.append(f"{key}: phrase not in text: {core}")
    spans.sort()
    html, pos = [], 0
    for a, b in spans:
        html.append(E(text[pos:a]) + "<mark class='kw'>" + E(text[a:b]) + "</mark>")
        pos = b
    html.append(E(text[pos:]))
    return ["<p>" + p + "</p>" for p in "".join(html).split("\n")]


def build_writing(errors):
    page = open(os.path.join(SRC, "writing.html"), encoding="utf-8").read()
    page = page.replace("{{TASK1}}", build_task1(errors))
    models = load_models(errors)
    used = set()

    def render(m):
        key = m.group(1)
        md = models.get(key)
        if not md or not md["E"]:
            errors.append(f"Writing: no model answer for {key}")
            return ""
        used.add(key)
        body = [p for p in md["E"]]
        letter = key.startswith("g")
        words = sum(len(p.split()) for p in (body[1:-2] if letter else body))
        lo, hi = (150, 230) if (letter or key.startswith("t")) else (250, 340)
        if not lo <= words <= hi:
            errors.append(f"Writing {key}: {words} words")
        items = vocab_items(md["V"])
        if len(items) < 10:
            errors.append(f"Writing {key}: only {len(items)} vocabulary items")
        paras = "".join(highlight(body, items, key, errors))
        rows = "".join(f"<tr><td>{E(a)}</td><td>{E(m)}" + (f"<span class='u'>{E(u)}</span>" if u else "") + "</td></tr>" for a, m, u in items)
        return (f"<button class='done' data-k='w-{key}'>Отметить как сделано</button>"
                f"<details class='model'><summary>Образец (Band {8 if letter else 9}), {words} слов — план, лексика, разбор</summary>"
                f"<div class='note'><b>План:</b> {E(md['P'])}</div><div class='essay'>{paras}</div>"
                f"<div class='note'><b>Полезная лексика из образца</b> (выделена в тексте)<table class='vt'>{rows}</table></div>"
                f"<div class='note'><b>Разбор:</b> {E(re.sub(r'^\d+ слов\w*\. ', '', md['N']))}</div></details>")

    page = re.sub(r"\{\{E:([A-Za-z0-9]+)\}\}", render, page)
    wex2 = build_wex(errors, "wex2.txt")
    def sub2(m):
        if m.group(1) not in wex2:
            errors.append(f"Writing: missing exercise {m.group(1)}"); return ""
        return wex2.pop(m.group(1))
    page = re.sub(r"\{\{WEX2:(\w+)\}\}", sub2, page)
    for k in wex2:
        errors.append(f"Writing: unused exercise {k}")
    for k in models:
        if k not in used:
            errors.append(f"Writing model {k} is not used on the page")
    return page


def main():
    errors = []
    os.makedirs(os.path.join(ROOT, "web"), exist_ok=True)
    nr, nq, rtoc, reading = build_reading(errors)
    nl, ltoc, listening = build_listening(errors)
    rd = lambda n: open(os.path.join(SRC, n), encoding="utf-8").read()
    page = rd("template.html")
    gt, gs = build_grammar(errors)
    gdata = {"stages": STAGES, "topics": [{k: x[k] for k in ("k", "n", "st", "title", "desc", "np", "nt", "pi")} for x in gt],
             "tests": [{k: x[k] for k in ("k", "st", "n", "title")} for x in gs]}
    page = page.replace("{{GRAMMAR}}", "\n".join(x["html"] for x in gt + gs)).replace(
        "{{GDATA}}", json.dumps(gdata, ensure_ascii=False).replace("</", "<\\/")).replace(
        "{{NG}}", str(len(gt))).replace(
        "{{LDATA}}", json.dumps(live_script(), ensure_ascii=False).replace("</", "<\\/"))
    for k, v in {
        "{{READING}}": reading, "{{RTOC}}": rtoc, "{{NR}}": str(nr), "{{NQ}}": str(nq),
        "{{LISTENING}}": listening, "{{LTOC}}": ltoc, "{{NL}}": str(nl),
        "{{WRITING}}": build_writing(errors), "{{SPEAKING}}": rd("speaking.html").replace("{{CARDS}}", build_cards(errors)[0]).replace("{{PART1}}", build_part1(errors)),
    }.items():
        page = page.replace(k, v)
    head, body = page.split("<!--BODY-->")
    note = " Аудиофайлы лежат в папке <b>audio</b> — она должна находиться рядом с этим файлом."
    # 1) standalone file: a full HTML document that plays audio from ./audio
    open(OUT, "w", encoding="utf-8").write(
        "<!doctype html>\n<html lang=\"ru\">\n<head>\n<meta charset=\"utf-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
        + head + "</head>\n<body>\n" + body.replace("{{AUDIONOTE}}", note) + "</body>\n</html>\n")
    # 2) page body for publishing as an artifact (the host adds the document skeleton;
    #    download links do nothing there, so they are dropped)
    web = re.sub(r"<a class='dl'[^>]*>mp3</a>", "", head + body.replace("{{AUDIONOTE}}", ""))
    open(os.path.join(ROOT, "web", "index.html"), "w", encoding="utf-8").write(web)
    # 3) public website (GitHub Pages serves the repository's docs/ folder)
    site = os.path.join(os.path.dirname(ROOT), "docs")
    os.makedirs(os.path.join(site, "audio"), exist_ok=True)
    open(os.path.join(site, "index.html"), "w", encoding="utf-8").write(
        "<!doctype html>\n<html lang=\"ru\">\n<head>\n<meta charset=\"utf-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1, viewport-fit=cover\">\n<meta name=\"color-scheme\" content=\"light\">\n"
        + head + "</head>\n<body>\n" + body.replace("{{AUDIONOTE}}", "") + "</body>\n</html>\n")
    open(os.path.join(site, ".nojekyll"), "w").close()
    os.makedirs(os.path.join(site, "audio", "sp"), exist_ok=True)
    for f in glob.glob(os.path.join(ROOT, "audio", "*.mp3")) + glob.glob(os.path.join(ROOT, "audio", "sp", "*.mp3")):
        dst = os.path.join(site, "audio", os.path.relpath(f, os.path.join(ROOT, "audio")))
        if not os.path.exists(dst) or os.path.getsize(dst) != os.path.getsize(f):
            shutil.copyfile(f, dst)
    print(f"reading passages: {nr}, reading questions: {nq}, listening: {nl}")
    print(f"output: {OUT} ({os.path.getsize(OUT)//1024} KB)")
    for e in errors:
        print("ERROR:", e)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
