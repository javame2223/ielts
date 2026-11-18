"""Grammar section: lessons, practice blocks, topic tests and stage tests from src/gram/*.txt."""
import glob, html, os, re

E = html.escape
STAGES = {1: "Этап 1 — база", 2: "Этап 2 — основные конструкции", 3: "Этап 3 — средний уровень", 4: "Этап 4 — продвинутый уровень"}
GI = {
    "MCQ": "Выбери правильный вариант.",
    "GAP": "Впиши правильную форму или слово. Подсказка — в скобках.",
    "TR": "Перепиши предложение так, чтобы смысл не изменился. Впиши только недостающую часть.",
    "ERR": "Найди ошибку: выбери букву части, в которой она есть.",
    "CI": "Предложение правильное (C) или с ошибкой (I)?",
}


def inline(s):
    s = E(s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<i>\1</i>", s)
    return s


def theory_html(lines):
    out, lst, tbl = [], [], []
    def flush():
        if lst:
            out.append("<ul class='ql'>" + "".join(f"<li>{inline(x)}</li>" for x in lst) + "</ul>"); lst.clear()
        if tbl:
            rows = [[c.strip() for c in r.strip().strip("|").split("|")] for r in tbl]
            h = "<tr>" + "".join(f"<th>{inline(c)}</th>" for c in rows[0]) + "</tr>"
            b = "".join("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>" for r in rows[1:])
            out.append(f"<div class='tw'><table>{h}{b}</table></div>"); tbl.clear()
    for ln in lines:
        if ln.startswith("- "):
            if tbl: flush()
            lst.append(ln[2:]); continue
        if ln.startswith("|"):
            if lst: flush()
            tbl.append(ln); continue
        flush()
        if ln.startswith("### "):
            out.append(f"<h4>{inline(ln[4:])}</h4>")
        elif ln.startswith("> "):
            out.append(f"<p class='gex'>{inline(ln[2:])}</p>")
        elif ln.startswith("✗"):
            bad, _, good = ln[1:].partition("→")
            good = good.strip().lstrip("✓").strip()
            out.append(f"<p class='gerr'><span class='no'>✗ {inline(bad.strip())}</span> <span class='yes'>✓ {inline(good)}</span></p>")
        elif ln.startswith("IELTS:"):
            out.append(f"<div class='gtip'><span class='lab'>IELTS</span> {inline(ln[6:].strip())}</div>")
        else:
            out.append(f"<p>{inline(ln)}</p>")
    flush()
    return "\n".join(out)


def gq(kind, items, errors, where):
    out = []
    for n, it in enumerate(items, 1):
        parts = [p.strip() for p in it.split(" | ")]
        expl = ""
        if parts and parts[-1].startswith("#"):
            expl = parts.pop()[1:].strip()
        if len(parts) < 2 or not parts[-1]:
            errors.append(f"{where}: no answer: {it[:60]}"); continue
        body, ans = parts[0], parts[-1]
        shown = ans
        if kind == "MCQ":
            opts = parts[1:-1]
            letters = [o[0] for o in opts]
            if len(opts) < 2 or ans not in letters or any(len(o) < 3 or o[1] != " " for o in opts):
                errors.append(f"{where}: bad MCQ: {it[:70]}")
            sel = "<select><option value=''>—</option>" + "".join(f"<option>{l}</option>" for l in letters) + "</select>"
            shown = next((o for o in opts if o[0] == ans), ans)
            q = f"{inline(body)} {sel}<ul class='opts'>" + "".join(f"<li>{inline(o)}</li>" for o in opts) + "</ul>"
        elif kind in ("ERR", "CI"):
            letters = ["A", "B", "C", "D"] if kind == "ERR" else ["C", "I"]
            if ans not in letters:
                errors.append(f"{where}: bad {kind} answer: {it[:70]}")
            if kind == "ERR" and not all(f"({l})" in body for l in "ABCD"):
                errors.append(f"{where}: ERR needs (A)-(D): {it[:70]}")
            sel = "<select><option value=''>—</option>" + "".join(f"<option>{l}</option>" for l in letters) + "</select>"
            b = inline(body)
            if kind == "ERR":
                b = re.sub(r"\(([ABCD])\)", r"<sup class='el'>\1</sup>", b)
            q = f"{b} {sel}"
            if kind == "CI":
                shown = "C — correct" if ans == "C" else "I — incorrect"
        elif kind in ("GAP", "TR"):
            if "____" not in body:
                errors.append(f"{where}: gap marker missing: {it[:70]}")
            cls = " class='wide'" if kind == "TR" else ""
            q = inline(body).replace("____", f"<input type='text' autocomplete='off' spellcheck='false'{cls}>", 1)
            shown = ans.split("/")[0]
        else:
            errors.append(f"{where}: unknown kind {kind}"); continue
        data = ans if kind in ("GAP", "TR") else ans
        ex = f"<span class='gx-e'>{inline(expl)}</span>" if expl else ""
        out.append(f"<div class='q' data-a=\"{E(data)}\"><span class='n'>{n}</span> <span class='qt'>{q}</span> "
                   f"<span class='ans'>✔ {E(shown)}{' — ' if expl else ''}</span>{ex}</div>")
    return out


BTNS = ("<div class='btns'><button class='chk'>Проверить</button><button class='shw'>Показать ответы</button>"
        "<button class='rst'>Сбросить</button><span class='score'></span></div>")


def parse(path, errors):
    meta, sec, blocks, cur = None, {}, [], None
    for raw in open(path, encoding="utf-8"):
        ln = raw.rstrip("\n").strip()
        if not ln or ln.startswith("//"):
            continue
        if ln.startswith("# ") and meta is None:
            meta = [x.strip() for x in ln[2:].split("|")]
        elif ln.startswith("@EX ") or ln.startswith("@TEST "):
            tag, rest = ln[1:].split(" ", 1)
            kind, _, title = rest.partition(" ")
            blocks.append({"test": tag == "TEST", "kind": kind, "title": title.strip(), "items": []}); cur = "Q"
        elif ln.startswith("@"):
            k, _, v = ln[1:].partition(" ")
            cur = k; sec.setdefault(k, [])
            if v: sec[k].append(v)
        elif cur == "Q":
            blocks[-1]["items"].append(ln)
        elif cur:
            sec[cur].append(ln)
        else:
            errors.append(f"{os.path.basename(path)}: stray line {ln[:40]}")
    return meta, sec, blocks


def unit(key, title, sub, qhtml, test=False):
    cls = "unit gx gtest" if test else "unit gx"
    return (f"<section class='{cls}' data-k='{key}' data-title=\"{E(title)}\"><h3>{E(title)}</h3>"
            + (f"<p class='src'>{inline(sub)}</p>" if sub else "") + "<div class='qs'>" + "\n".join(qhtml) + "</div>" + BTNS + "</section>")


def group_html(b, errors, where, number=True):
    qs = gq(b["kind"], b["items"], errors, where)
    return f"<div class='qgroup'><p class='instr'>{GI[b['kind']]}</p>" + "\n".join(qs) + "</div>", len(qs)


def renumber(h):
    c = [0]
    def f(m):
        c[0] += 1
        return f"<span class='n'>{c[0]}</span>"
    return re.sub(r"<span class='n'>\d+</span>", f, h)


def build_grammar(errors):
    topics, tests = [], []
    for path in sorted(glob.glob(os.path.join(os.path.dirname(__file__), "src", "gram", "*.txt"))):
        meta, sec, blocks = parse(path, errors)
        name = os.path.basename(path)
        if not meta:
            errors.append(f"{name}: no header"); continue
        if meta[0].startswith("S"):
            st = int(meta[0][1:])
            parts, n = [], 0
            for b in blocks:
                g, c = group_html(b, errors, name)
                parts.append((f"<h4>{E(b['title'])}</h4>" if b["title"] else "") + g); n += c
            if n != 100:
                errors.append(f"{name}: stage test has {n} questions, expected 100")
            body = renumber(unit(f"gs{st}", f"Итоговый тест: {STAGES[st]}", "", parts))
            intro = "".join(f"<p>{inline(x)}</p>" for x in sec.get("INTRO", []))
            tests.append(dict(k=f"gs{st}", st=st, n=n, title=f"Итоговый тест этапа {st}", html=(
                f"<article class='gtopic' id='gs{st}' hidden data-st='{st}'><div class='ghead'><a class='btn' href='#grammar'>← Все темы</a>"
                f"<p class='eyebrow'>{E(STAGES[st])} · 100 вопросов</p><h1>Итоговый тест этапа {st}</h1>{intro}</div>{body}</article>"), text=""))
            continue
        num, title, st, desc = int(meta[0]), meta[1], int(meta[2]), (meta[3] if len(meta) > 3 else "")
        k = f"g{num}"
        prac, tparts, np, nt = [], [], 0, 0
        pi = 0
        for b in blocks:
            g, c = group_html(b, errors, f"{name} {b['title'][:20]}")
            if b["test"]:
                tparts.append((f"<h4>{E(b['title'])}</h4>" if b["title"] else "") + g); nt += c
            else:
                pi += 1; np += c
                prac.append(unit(f"{k}-p{pi}", f"Практика {pi}. {b['title']}", "", [g]))
        if not tparts:
            errors.append(f"{name}: no topic test")
        plan = "".join(f"<li>{inline(x.lstrip('0123456789. '))}</li>" for x in sec.get("PLAN", []))
        theory = theory_html(sec.get("THEORY", []))
        use = theory_html(sec.get("USE", [])) if sec.get("USE") else ""
        testu = renumber(unit(f"{k}-t", f"Тест по теме: {title}", f"{nt} вопросов. Тема освоена, если результат 85% и выше.", tparts, True))
        html_ = (f"<article class='gtopic' id='{k}' hidden data-st='{st}' data-n='{num}' data-title=\"{E(title)}\">"
                 f"<div class='ghead'><a class='btn' href='#grammar'>← Все темы</a><p class='eyebrow'>{E(STAGES[st])} · тема {num}</p>"
                 f"<h1>{num}. {E(title)}</h1>" + (f"<p class='lead'>{inline(desc)}</p>" if desc else "") +
                 f"<div class='gnav'></div></div>"
                 f"<div class='card'><h3>План урока</h3>" + (f"<p><b>Цель:</b> {inline(' '.join(sec.get('GOAL', [])))}</p>" if sec.get("GOAL") else "") +
                 f"<ol class='ql'>{plan}</ol><p class='src'>Практика: {np} заданий в {pi} блоках · тест: {nt} вопросов</p></div>"
                 f"<div class='card gth'><h3>Теория</h3>{theory}</div>"
                 + (f"<div class='card gth'><h3>Как это использовать на IELTS</h3>{use}</div>" if use else "")
                 + "".join(prac) + testu + "</article>")
        text = " ".join(sec.get("THEORY", []))
        topics.append(dict(k=k, n=num, st=st, title=title, desc=desc, np=np, nt=nt, pi=pi, html=html_, text=re.sub(r"[*#>|]", " ", text)[:4000]))
    topics.sort(key=lambda t: t["n"])
    return topics, tests
