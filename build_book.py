#!/usr/bin/env python3
"""Combine 24 songs (from PDFs) + 15 legends (from A5 Legendy.docx) into one
A5-printable HTML book. Order: blocks of 3 songs then 2 legends, repeating."""
import fitz, glob, os, io, re, html, unicodedata, difflib
from docx import Document
from docx.text.paragraph import Paragraph
from docx.oxml.ns import qn
from PIL import Image

SRC = "/Users/jankapusta/Documents/Skaut/song book"
SEZNAM = os.path.join(SRC, "seznam.txt")
LEGENDY = os.path.join(SRC, "A5 Legendy.docx")
IMGDIR = os.path.join(SRC, "legend_images")
OUT = os.path.join(SRC, "Zpevnik_a_legendy.html")

# ============================================================ SONGS
FOOTER_MARKERS = ("pisnicky-akordy", "sponzor:", "powered by tcpdf", "srovnavac", "tcpdf")
def clean(s): return s.replace("​", "").replace("\xad", "")
def is_footer(line):
    l = line.lower(); return any(m in l for m in FOOTER_MARKERS)
def mono_char_width(page):
    for b in page.get_text("dict")["blocks"]:
        for ln in b.get("lines", []):
            for s in ln["spans"]:
                if ("Mono" in s["font"] or "Courier" in s["font"]) and len(s["text"]) >= 3:
                    return (s["bbox"][2] - s["bbox"][0]) / len(s["text"])
    return 7.2
def mono_origin(page):
    xs = [s["bbox"][0] for b in page.get_text("dict")["blocks"]
          for ln in b.get("lines", []) for s in ln["spans"]
          if "Mono" in s["font"] or "Courier" in s["font"]]
    return min(xs) if xs else 0.0
def build_line(spans, origin, cw):
    chars = []
    for s in sorted(spans, key=lambda s: s["bbox"][0]):
        txt = clean(s["text"])
        if not txt: continue
        bold = "Bold" in s["font"] or bool(s["flags"] & 16)
        col = max(0, round((s["bbox"][0] - origin) / cw))
        while len(chars) < col: chars.append([" ", False])
        for ch in txt: chars.append([ch, bold])
    while chars and chars[-1][0] == " ": chars.pop()
    runs = []
    for ch, b in chars:
        if runs and runs[-1][1] == b: runs[-1][0] += ch
        else: runs.append([ch, b])
    return [(t, b) for t, b in runs]
def extract_song(path):
    doc = fitz.open(path)
    if sum(len(p.get_text()) for p in doc) == 0:
        return {"title": None, "subtitle": None, "body": []}
    title = subtitle = None; body = []
    for pno, page in enumerate(doc):
        origin, cw = mono_origin(page), mono_char_width(page)
        lines = []
        for b in page.get_text("dict")["blocks"]:
            for ln in b.get("lines", []):
                if ln["spans"]:
                    lines.append((min(s["bbox"][1] for s in ln["spans"]), ln["spans"]))
        lines.sort(key=lambda t: t[0])
        for _, spans in lines:
            raw = clean("".join(s["text"] for s in spans)).strip()
            if not raw or is_footer(raw): continue
            is_mono = any("Mono" in s["font"] or "Courier" in s["font"] for s in spans)
            if pno == 0 and title is None and not is_mono: title = raw; continue
            if pno == 0 and subtitle is None and not is_mono and not body: subtitle = raw; continue
            body.append(build_line(spans, origin, cw))
    if title is None: title = os.path.splitext(os.path.basename(path))[0]
    return {"title": title, "subtitle": subtitle, "body": body}

available = []
for f in glob.glob(os.path.join(SRC, "*.pdf")):
    s = extract_song(f)
    if s["title"] is None: s["title"] = os.path.splitext(os.path.basename(f))[0].replace("_", " ")
    available.append(s)

def norm(t):
    t = unicodedata.normalize("NFKD", t)
    t = "".join(c for c in t if not unicodedata.combining(c)).lower().split(" - ")[0]
    return " ".join("".join(c if c.isalnum() or c == " " else " " for c in t).split())
avail_norm = [(norm(s["title"]), s) for s in available]
with open(SEZNAM, encoding="utf-8") as fh:
    wanted = [ln.strip() for ln in fh if ln.strip()]
songs, seen = [], set()
for w in wanted:
    nw = norm(w)
    if nw in seen: continue
    seen.add(nw)
    best, best_score = None, 0.0
    for an, s in avail_norm:
        score = difflib.SequenceMatcher(None, nw, an).ratio()
        if an == nw or nw in an or an in nw: score = max(score, 0.95)
        if score > best_score: best, best_score = s, score
    if best_score >= 0.82: songs.append(best)

# A5 usable text width in pt (page 148mm - 2*10mm margin)
USABLE_PT = (148 - 2*10) / 25.4 * 72
def song_font_pt(song):
    maxlen = max((len("".join(t for t, _ in ln)) for ln in song["body"]), default=40)
    v = max(7.5, min(10.5, USABLE_PT / (maxlen * 0.60)))  # 0.60 = safe mono advance
    return int(v * 4) / 4                                  # floor to 0.25pt so it never overflows

def line_html(runs):
    out = []
    for text, bold in runs:
        t = html.escape(text)
        out.append(f"<b>{t}</b>" if (bold and text.strip()) else t)
    return "".join(out)
def song_html(song):
    sz = song_font_pt(song)
    sub = f'<p class="artist">{html.escape(song["subtitle"])}</p>' if song["subtitle"] else ""
    pre = "\n".join(line_html(ln) for ln in song["body"])
    return (f'<section class="song">\n<h2 class="song-title">{html.escape(song["title"])}</h2>\n'
            f'{sub}\n<pre style="font-size:{sz}pt">{pre}</pre>\n</section>')

# ============================================================ LEGENDS
os.makedirs(IMGDIR, exist_ok=True)
ldoc = Document(LEGENDY)
def save_image(blob, idx, maxw=1200):
    im = Image.open(io.BytesIO(blob))
    if im.mode in ("P", "RGBA"): im = im.convert("RGB") if im.mode == "P" else im
    if im.width > maxw:
        im = im.resize((maxw, round(im.height * maxw / im.width)), Image.LANCZOS)
    name = f"img{idx:02d}.png"; im.save(os.path.join(IMGDIR, name)); return name
def para_image_blobs(p):
    blobs = []
    for blip in p._p.findall(".//" + qn("a:blip")):
        rid = blip.get(qn("r:embed"))
        if rid: blobs.append(ldoc.part.related_parts[rid].blob)
    return blobs
def runs_html(p):
    out = []
    for r in p.runs:
        t = html.escape(r.text)
        if not t: continue
        if r.bold: t = f"<b>{t}</b>"
        if r.italic: t = f"<i>{t}</i>"
        out.append(t)
    return "".join(out)

front = []            # html blocks for title page
legends = []          # list of {title, blocks:[html]}
cur = None
img_idx = 0
for child in ldoc.element.body.iterchildren():
    if child.tag != qn("w:p"): continue
    p = Paragraph(child, ldoc)
    st = p.style.name
    txt = p.text.strip()
    # images in this paragraph
    for blob in para_image_blobs(p):
        img_idx += 1
        name = save_image(blob, img_idx)
        tag = f'<img src="legend_images/{name}" alt="">'
        (legends[-1]["blocks"] if cur is not None else front).append(tag)
    if st == "Heading 1":
        if txt: front.append(f"<h1>{html.escape(txt)}</h1>")
        continue
    if st == "Heading 2":
        if txt:                       # ignore stray empty H2 paragraphs
            cur = {"title": txt, "blocks": []}; legends.append(cur)
        continue
    if not txt:
        continue
    if st == "Heading 3":
        legends[-1]["blocks"].append(f"<h3>{html.escape(txt)}</h3>"); continue
    # normal paragraph
    inner = runs_html(p) or html.escape(txt)
    if cur is None:
        front.append(f'<p class="edition">{inner}</p>')
    else:
        cls = ' class="legend-meta"' if re.match(r"^\s*\[", txt) else ""
        legends[-1]["blocks"].append(f"<p{cls}>{inner}</p>")

def legend_html(leg):
    return (f'<section class="legend">\n<h2 class="legend-title">{html.escape(leg["title"])}</h2>\n'
            + "\n".join(leg["blocks"]) + "\n</section>")

# ============================================================ INTERLEAVE 3 songs / 2 legends
seq = []
si = li = 0
while si < len(songs) or li < len(legends):
    for _ in range(3):
        if si < len(songs): seq.append(song_html(songs[si])); si += 1
    for _ in range(2):
        if li < len(legends): seq.append(legend_html(legends[li])); li += 1

# ============================================================ ASSEMBLE
cover = front[0] if front and front[0].startswith("<img") else ""
title_blocks = "\n".join(b for b in front if b != cover)
titlepage = f'<section class="titlepage">\n{cover}\n{title_blocks}\n</section>'

# printed contents page (no links) — grouped Písně / Legendy
s_items = "".join(f"<li>{html.escape(s['title'])}</li>" for s in songs)
l_items = "".join(f"<li>{html.escape(l['title'])}</li>" for l in legends)
contents = (f'<section class="contents">\n<h1>Obsah</h1>\n'
            f'<h2 class="c-head">Písně</h2>\n<ol class="c-list c-songs">{s_items}</ol>\n'
            f'<h2 class="c-head">Legendy</h2>\n<ol class="c-list c-legends">{l_items}</ol>\n'
            f'</section>')

CSS = """
@page { size: 148mm 210mm; margin: 12mm 10mm; }
* { box-sizing: border-box; }
body { margin: 0; font-family: Georgia, "Times New Roman", serif;
       color: #1a1a1a; line-height: 1.4; }
h1 { font-family: "Helvetica Neue", Arial, sans-serif; font-size: 30pt;
     text-align: center; margin: 0.3em 0; }
.titlepage { text-align: center; break-after: page; padding-top: 10mm; }
.titlepage img.cover { max-width: 100%; max-height: 150mm; display: block; margin: 0 auto 8mm; }
.edition { text-align: center; color: #555; font-style: italic; margin: 2px 0; }

/* printed contents page */
.contents { break-after: page; }
.contents h1 { font-size: 22pt; margin: 0 0 6px; }
.c-head { font-family: "Helvetica Neue", Arial, sans-serif; font-size: 13pt;
          margin: 12px 0 4px; color: #7a3b12; }
.c-list { columns: 2; column-gap: 8mm; margin: 0; padding-left: 1.3em;
          font-size: 9.5pt; line-height: 1.35; }
.c-list li { break-inside: avoid; margin: 0 0 2px; padding-left: 2px; }
.c-legends { font-size: 9pt; }

section.song, section.legend { break-before: page; }

/* songs */
.song-title { font-family: "Helvetica Neue", Arial, sans-serif;
              font-size: 16pt; margin: 0 0 1px; }
.artist { font-style: italic; color: #666; margin: 0 0 8px; font-size: 10pt; }
.song pre { font-family: Consolas, "DejaVu Sans Mono", "Courier New", monospace;
            white-space: pre; margin: 0; line-height: 1.18;
            font-variant-ligatures: none; }
.song pre b { font-weight: 700; }

/* legends */
.legend-title { font-family: "Helvetica Neue", Arial, sans-serif;
                font-size: 17pt; margin: 0 0 4px; color: #7a3b12; }
.legend-meta { color: #888; font-style: italic; font-size: 10pt; margin: 0 0 8px; }
.legend h3 { font-family: "Helvetica Neue", Arial, sans-serif; font-size: 12.5pt;
             margin: 14px 0 4px; color: #33691e; }
.legend p { margin: 0 0 7px; text-align: justify; hyphens: auto; }
.legend img { max-width: 100%; height: auto; display: block; margin: 10px auto; border-radius: 4px; }

/* on-screen: show page-like cards */
@media screen {
  body { background: #e7e7e7; padding: 20px; }
  section, .titlepage { background: #fff; width: 148mm; min-height: 210mm;
    margin: 0 auto 16px; padding: 12mm 10mm; box-shadow: 0 2px 10px rgba(0,0,0,.2); }
}
"""

htmlout = f"""<!DOCTYPE html>
<html lang="cs">
<head>
<meta charset="utf-8">
<title>Zpěvník a Legendy Svišťů</title>
<style>{CSS}</style>
</head>
<body>
{titlepage}
{contents}
{chr(10).join(seq)}
</body>
</html>
"""
with open(OUT, "w", encoding="utf-8") as f:
    f.write(htmlout)

print(f"Wrote {OUT}")
print(f"songs={len(songs)} legends={len(legends)} images={img_idx}")
print(f"sequence items={len(seq)}  (title page + these)")
# show interleave order
order = []
si = li = 0
while si < len(songs) or li < len(legends):
    for _ in range(3):
        if si < len(songs): order.append("S"+str(si+1)); si += 1
    for _ in range(2):
        if li < len(legends): order.append("L"+str(li+1)); li += 1
print("order:", " ".join(order))
