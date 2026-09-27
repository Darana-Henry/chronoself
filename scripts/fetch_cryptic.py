#!/usr/bin/env python3
"""Build data/minute-cryptic.json from two public sources:

- Community "clue chart" Google Sheet: answers, enumeration, wordplay breakdown, indicators
- Official Minute Cryptic YouTube channel (via yt-dlp): official clue wording and walkthrough videos

Usage: python3 scripts/fetch_cryptic.py      (requires yt-dlp on PATH)
"""

import csv
import datetime
import difflib
import io
import json
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

SHEET_ID = "1gl05ZiRxt0aX6IvgLTWnCy1uc4AP0Y8QU-3y5Wnhsjs"
CLUE_GID = "1753526836"
GLOSSARY_GID = "988853849"
INDICATOR_GID = "1355312085"
CHANNEL = "https://www.youtube.com/@MinuteCryptic"
FIRST_DATE = datetime.date(2024, 6, 26)
OUT = Path(__file__).resolve().parent.parent / "data" / "minute-cryptic.json"

NUMBERED = re.compile(r"^Minute Cryptic(?: Clue)? #?(\d+)\b[^:]*:\s*(.+)$", re.I)
EDITOR = re.compile(r"^The Editor Solves:\s*(.+)$", re.I)
ENUM = re.compile(r"\s*\(([\d,\- ]+)\)\s*$")
# YouTube titles can't hold "<", so the sheet's wording is the faithful one here
KEEP_SHEET_WORDING = {577}

LINK_WORDS = {
    "in", "for", "with", "and", "&", "is", "from", "to", "of", "by", "at", "as", "or", "the", "a", "an",
    "that", "when", "so", "then", "on", "gives", "makes", "making", "producing", "yields", "being",
    "are", "was", "it", "its", "into", "providing", "creates", "showing", "reveals", "leads", "leading", "means",
}
WORD = re.compile(r"[A-Za-z0-9’'&$%#@]+|[^\sA-Za-z0-9’'\-.,!?:;\"“”‘()*…–—/]+")


def fetch_csv(gid):
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={gid}"
    with urllib.request.urlopen(url, timeout=60) as r:
        return list(csv.reader(io.StringIO(r.read().decode("utf-8"))))


def fetch_videos():
    rows = []
    for tab in ("videos", "shorts"):
        out = subprocess.run(
            ["yt-dlp", "--flat-playlist", "--print", "%(id)s\t%(title)s", f"{CHANNEL}/{tab}"],
            capture_output=True, text=True, check=True,
        ).stdout
        rows += [line.split("\t", 1) for line in out.splitlines() if "\t" in line]
    return rows


def letters(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())


def fits(enum, answer):
    return sum(int(x) for x in re.findall(r"\d+", enum)) == len(re.sub(r"[^A-Z]", "", answer))


def strip_tags(title):
    return re.sub(r"(\s+#\w+)+\s*$", "", title).strip()


def plain_clue(marked):
    s = marked.replace("[", "").replace("]", "")
    s = re.sub(r"\s+/\s+", " ", s)
    return re.sub(r"\s{2,}", " ", s).strip()


def overlaps(a, ranges):
    return any(a[0] < b[1] and b[0] < a[1] for b in ranges)


def parse_marked(marked):
    plain, fodder, start = "", [], None
    for ch in marked:
        if ch == "[":
            start = len(plain)
        elif ch == "]":
            if start is not None:
                fodder.append((start, len(plain)))
            start = None
        else:
            plain += ch
    return plain, fodder


def indicator_fragments(template):
    body = re.sub(r"\([^)]*\)", " ", template)
    parts = re.split(r"\[[^\]]*\]|\.\.+|…", body)
    return body, [p.strip(" -") for p in parts if p.strip(" -'\".,!?")]


def find_word(frag, text):
    pre = r"(?<![A-Za-z])" if frag[:1].isalnum() else ""
    post = r"(?![A-Za-z])" if frag[-1:].isalnum() else ""
    return [(m.start(), m.end()) for m in re.finditer(pre + re.escape(frag) + post, text, re.I)]


def highlights(marked, lit, templates):
    """Best-effort fodder / indicator / definition spans over the sheet's clue text.

    Fodder is bracketed in the sheet. Indicators come from the indicator chart; when its wording
    doesn't appear verbatim (it's normalised, e.g. "reverse" for "Rewind"), the word beside the
    fodder on the template's side is taken. The definition is the free run of words at the start
    or end of the clue, minus link words.
    """
    plain, fod = parse_marked(marked)
    toks = [(m.start(), m.end()) for m in WORD.finditer(plain)]
    ind = []
    for tpl in templates:
        body, frags = indicator_fragments(tpl)
        for f in frags:
            hit = next((r for r in find_word(f, plain) if not overlaps(r, fod) and not overlaps(r, ind)), None)
            if hit:
                ind.append(hit)
                continue
            before = body.find(f) < body.find("[") if "[" in body else True
            for fa, fb in fod:
                free = [t for t in toks if not overlaps(t, fod + ind)]
                adj = [t for t in free if t[1] <= fa] if before else [t for t in free if t[0] >= fb]
                t = (adj[-1] if before else adj[0]) if adj else None
                if t and not plain[t[1]:fa if before else t[0]].strip(" '’-"):
                    ind.append(t)
                    break
    if lit:
        return plain, fod, ind, [(0, len(plain))]
    if " / " in plain:
        i = plain.index(" / ")
        return plain, fod, ind, [(0, i), (i + 3, len(plain))]

    free = [not overlaps(t, fod + ind) for t in toks]

    def run(pairs):
        out = []
        for t, f in pairs:
            if not f:
                break
            out.append(t)
        return out

    word = lambda t: plain[t[0]:t[1]].lower()
    lead = run(zip(toks, free))
    trail = run(reversed(list(zip(toks, free))))[::-1]
    while len(lead) > 1 and word(lead[-1]) in LINK_WORDS:
        lead.pop()
    while len(trail) > 1 and word(trail[0]) in LINK_WORDS:
        trail.pop(0)
    if lead and word(lead[-1]) in LINK_WORDS:
        lead = []
    if trail and word(trail[0]) in LINK_WORDS:
        trail = []
    if len(lead) == len(toks):
        return plain, fod, ind, []
    cands = [x for x in (lead, trail) if x]
    if not cands:
        return plain, fod, ind, []
    best = max(cands, key=len)
    return plain, fod, ind, [(best[0][0], best[-1][1])]


def map_spans(src, dst, spans):
    """Carry character spans from the sheet's wording over to the displayed (official) wording."""
    sm = difflib.SequenceMatcher(None, src.lower(), dst.lower(), autojunk=False)
    pos = {}
    for a, b, size in sm.get_matching_blocks():
        for k in range(size):
            pos[a + k] = b + k
    out = []
    for s, e in sorted(spans):
        while s < e and src[s] == " ":
            s += 1
        while e > s and src[e - 1] == " ":
            e -= 1
        if s < e and s in pos and (e - 1) in pos and pos[s] <= pos[e - 1]:
            out.append([pos[s], pos[e - 1] + 1])
    return out


def main():
    rows = fetch_csv(CLUE_GID)
    header_idx = next(i for i, r in enumerate(rows) if r and r[0] == "no.")
    header = rows[header_idx]
    col = {name: i for i, name in enumerate(header)}
    type_cols = header[col["alias"]:col["full clue"]]

    glossary = {}
    for r in fetch_csv(GLOSSARY_GID):
        if len(r) >= 2 and r[0] in type_cols and r[1]:
            glossary[r[0]] = r[1]

    ind_rows = fetch_csv(INDICATOR_GID)
    ind_header = next(i for i, r in enumerate(ind_rows) if r and r[0] == "no.")
    indicators = {
        int(r[0]): [c.strip() for c in r[2:] if c.strip()]
        for r in ind_rows[ind_header + 1:] if r and r[0].isdigit()
    }

    sheet = {}
    for r in rows[header_idx + 1:]:
        if not r or not r[0].isdigit():
            continue
        n = int(r[0])
        parts = [{"type": t, "text": r[col[t]].strip()} for t in type_cols if r[col[t]].strip()]
        sheet[n] = {
            "answer": r[col["answer"]].strip().upper(),
            "marked": r[col["full clue"]].strip(),
            "enum": r[col["length"]].strip(),
            "lit": r[col["&lit."]].strip().lower() == "yes",
            "parts": parts,
        }

    yt, editor = {}, {}
    for vid, title in fetch_videos():
        title = strip_tags(title)
        m = NUMBERED.match(title)
        if m:
            yt.setdefault(int(m.group(1)), (vid, m.group(2).strip()))
            continue
        m = EDITOR.match(title)
        if m:
            editor.setdefault(letters(ENUM.sub("", m.group(1))), vid)

    clues, warnings = [], []
    for n in sorted(sheet):
        s = sheet[n]
        clue, enum = plain_clue(s["marked"]), s["enum"]
        video = None
        if n in yt:
            video, title = yt[n]
            em = ENUM.search(title)
            if em:
                yt_clue = ENUM.sub("", title).strip()
                if letters(yt_clue) != letters(clue):
                    warnings.append(f"#{n} wording differs\n    sheet:   {clue}\n    youtube: {yt_clue}")
                if n not in KEEP_SHEET_WORDING:
                    clue = yt_clue
                yt_enum = em.group(1).replace(" ", "")
                if fits(yt_enum, s["answer"]):
                    enum = yt_enum
                else:
                    warnings.append(f"#{n} youtube enumeration ({yt_enum}) doesn't fit {s['answer']}, kept sheet ({enum})")
        if not fits(enum, s["answer"]):
            warnings.append(f"#{n} enumeration ({enum}) doesn't fit answer {s['answer']}")
        plain, fod, ind, dfn = highlights(s["marked"], s["lit"], indicators.get(n, []))
        hl = {k: map_spans(plain, clue, v) for k, v in (("fod", fod), ("ind", ind), ("def", dfn))}
        clues.append({
            "n": n,
            "date": (FIRST_DATE + datetime.timedelta(days=n - 1)).isoformat(),
            "clue": clue,
            "enum": enum,
            "answer": s["answer"],
            "marked": s["marked"],
            "lit": s["lit"],
            "parts": s["parts"],
            "hl": hl,
            "video": video,
            "editor": editor.get(letters(clue)),
        })

    missing = [n for n in range(1, max(sheet) + 1) if n not in sheet]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "updated": datetime.date.today().isoformat(),
        "sources": {
            "sheet": f"https://docs.google.com/spreadsheets/d/{SHEET_ID}",
            "youtube": CHANNEL,
        },
        "glossary": glossary,
        "clues": clues,
    }, ensure_ascii=False, indent=1) + "\n")

    print(f"Wrote {len(clues)} clues (#1–#{max(sheet)}) → {OUT}")
    print(f"Definition found: {sum(1 for c in clues if c['hl']['def'])}/{len(clues)}")
    print(f"YouTube matched: {sum(1 for c in clues if c['video'])}, editor videos: {sum(1 for c in clues if c['editor'])}")
    if missing:
        print(f"Missing from sheet: {missing}")
    for w in warnings:
        print("WARN", w, file=sys.stderr)


if __name__ == "__main__":
    main()
