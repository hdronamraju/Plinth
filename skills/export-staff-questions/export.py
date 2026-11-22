"""Fillable staff-questions PDF (PLAN.md §5). Letter, Helvetica, black + Pool Teal.

build_pdf(path, doc_id, version, address, property_facts, project, questions, attachments)
questions: [{id, title, context, code_ref (quote or ""), code_cite, precedent, proposed}]
Field names: q{n}_decision (radio), q{n}_notes, q{n}_section, reviewer_name/title/date, general_notes.
"""
from __future__ import annotations

import json
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph

TEAL = colors.HexColor("#3A6E69")
INK = colors.black
GREY = colors.HexColor("#555555")
W, H = letter
M = 0.75 * inch
CW = W - 2 * M
FOOT = "Prepared with Plinth. Not an application or permit."
OPTIONS = ["Confirmed", "Not as proposed", "Need more info"]

# ---- brand (brand/README.md). The mark is the only place brand colors besides teal appear.
OCHRE = colors.HexColor("#C8A55E")
NIGHT = colors.HexColor("#262E33")
STUCCO = colors.HexColor("#EDE8DE")
BRAND_DIR = Path(__file__).resolve().parents[2] / "brand"
YELLOWTAIL = BRAND_DIR / "fonts" / "Yellowtail-Regular.ttf"
WORDMARK_FONT = "Helvetica-Bold"
try:  # optional script wordmark; falls back to bold sans if the font file isn't there
    if YELLOWTAIL.exists():
        pdfmetrics.registerFont(TTFont("Yellowtail", str(YELLOWTAIL)))
        WORDMARK_FONT = "Yellowtail"
except Exception:
    WORDMARK_FONT = "Helvetica-Bold"


def draw_mark(c, x, y, size):
    """Draw brand/plinth-mark.svg (120x120 viewBox, y down) with its bottom-left at (x, y)."""
    k = size / 120.0

    def P(px, py):
        return x + px * k, y + (120 - py) * k

    def poly(pts, fill):
        path = c.beginPath()
        path.moveTo(*P(*pts[0]))
        for pt in pts[1:]:
            path.lineTo(*P(*pt))
        path.close()
        c.setFillColor(fill)
        c.drawPath(path, fill=1, stroke=0)

    def rect(px, py, w, h, fill):
        c.setFillColor(fill)
        c.rect(x + px * k, y + (120 - py - h) * k, w * k, h * k, fill=1, stroke=0)

    c.saveState()
    c.setFillColor(OCHRE)
    c.circle(*P(60, 48), 34 * k, fill=1, stroke=0)
    poly([(34, 52), (60, 61), (86, 48), (86, 80), (34, 80)], TEAL)
    poly([(26, 44), (60, 55), (94, 40), (94, 47), (60, 62), (26, 51)], NIGHT)
    rect(40, 64, 14, 10, STUCCO)
    rect(66, 62, 10, 18, OCHRE)
    rect(22, 80, 76, 9, NIGHT)
    rect(12, 91, 96, 11, NIGHT)
    c.restoreState()


def draw_brand_header(c, x, top):
    """Logo lockup on the cover: mark + "Plinth" wordmark + tagline. Returns its height."""
    size = 0.55 * inch
    draw_mark(c, x, top - size, size)
    tx = x + size + 9
    c.setFillColor(TEAL)
    if WORDMARK_FONT == "Yellowtail":
        c.setFont("Yellowtail", 26)
        c.drawString(tx, top - 26, "Plinth")
    else:
        c.setFont("Helvetica-Bold", 20)
        c.drawString(tx, top - 24, "Plinth")
    c.setFillColor(GREY)
    c.setFont("Helvetica-Bold", 7)
    c.drawString(tx, top - size + 3, "P E R M I T S ,   H A N D L E D .")
    return size

S = {
    "body": ParagraphStyle("body", fontName="Helvetica", fontSize=9.5, leading=12.5, textColor=INK),
    "quote": ParagraphStyle("quote", fontName="Helvetica-Oblique", fontSize=9, leading=11.5, textColor=GREY,
                            leftIndent=8),
    "label": ParagraphStyle("label", fontName="Helvetica-Bold", fontSize=8, leading=10, textColor=TEAL),
}


def _p(c, text, style, x, y, width=CW):
    p = Paragraph(text, S[style])
    _, h = p.wrap(width, 10_000)
    p.drawOn(c, x, y - h)
    return y - h


def _height(text, style, width=CW):
    return Paragraph(text, S[style]).wrap(width, 10_000)[1]


def _clip(text: str, n: int = 700) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= n else text[:n].rsplit(" ", 1)[0] + " …"


class Doc:
    def __init__(self, path, doc_id, version, address):
        self.c = canvas.Canvas(str(path), pagesize=letter, pageCompression=1)
        self.doc_id, self.version, self.address = doc_id, version, address
        self.page = 0
        self.pages: list[str] = []
        self.index: list[tuple[str, int]] = []
        self.c.setTitle(f"Planning questions for {address}")
        self.c.setAuthor("Plinth")
        self.y = H - M

    def new_page(self):
        if self.page:
            self.footer_final()
            self.c.showPage()
        self.page += 1
        self.y = H - M


def build_pdf(path, doc_id, version, address, property_facts, project, questions, attachments=None):
    attachments = attachments or []
    path = Path(path)
    # Pass 1 counts pages, pass 2 writes "Page X of Y" and the index page numbers.
    layout = _render(path, doc_id, version, address, property_facts, project, questions, attachments, None)
    _render(path, doc_id, version, address, property_facts, project, questions, attachments, layout)
    return path


def _render(path, doc_id, version, address, facts, project, questions, attachments, layout):
    total = layout["total"] if layout else 99
    qpages = layout["qpages"] if layout else {}
    d = Doc(path, doc_id, version, address)
    c = d.c
    d.footer_final = lambda d=d: _footer(d, total)
    d.new_page()

    # ---- cover
    d.y -= draw_brand_header(c, M, d.y) + 20
    c.setFillColor(TEAL)
    c.setFont("Helvetica-Bold", 20)
    c.drawString(M, d.y - 20, "Planning questions")
    c.setFillColor(INK)
    c.setFont("Helvetica", 13)
    c.drawString(M, d.y - 40, f"for {address}")
    c.setStrokeColor(TEAL)
    c.setLineWidth(1.5)
    c.line(M, d.y - 50, W - M, d.y - 50)
    d.y -= 66
    d.y = _p(c, "<b>How to use this form.</b> Each question below states the planning-code text we found, "
             "any earlier staff answer, and our proposed reading. For each, please mark one response, add "
             "notes, and cite the code section you rely on. Fields can be filled in any PDF reader, or "
             "printed and handwritten.", "body", M, d.y) - 12

    d.y = _p(c, "PROPERTY SUMMARY", "label", M, d.y) - 4
    for label, val, src in facts:
        txt = f"<b>{escape(label)}:</b> {escape(val) if val else '<i>not provided</i>'} " \
              f"<font color='#777777' size='8'>({escape(src)})</font>"
        d.y = _p(c, txt, "body", M + 6, d.y) - 2
    d.y -= 10
    d.y = _p(c, "PROJECT DESCRIPTION", "label", M, d.y) - 4
    d.y = _p(c, escape(project or "Not provided.").replace("\n", "<br/>"), "body", M, d.y) - 10
    if attachments:
        d.y = _p(c, "ATTACHMENTS", "label", M, d.y) - 4
        for a in attachments:
            d.y = _p(c, f"• {escape(a)}", "body", M + 6, d.y) - 1
        d.y -= 8
    d.y = _p(c, "INDEX", "label", M, d.y) - 4
    for n, q in enumerate(questions, 1):
        pg = qpages.get(n, "")
        d.y = _p(c, f"Q{n} · {escape(q['title'])} <font color='#777777'>— page {pg}</font>", "body",
                 M + 6, d.y) - 2

    # ---- questions: 2 per page, never split
    used = {}
    d.new_page()
    on_page = 0
    for n, q in enumerate(questions, 1):
        need = _block_height(q)
        if on_page and d.y - need < 0.9 * inch:
            d.new_page()
            on_page = 0
        used[n] = d.page
        _question(d, n, q)
        on_page += 1
    # ---- last page
    d.new_page()
    c.setFillColor(TEAL)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(M, d.y - 14, "Reviewer")
    d.y -= 40
    f = c.acroForm
    for i, (name, label, wd) in enumerate([("reviewer_name", "Name", 260), ("reviewer_title", "Title", 200),
                                           ("reviewer_date", "Date", 100)]):
        x = M if i < 2 else M
        yy = d.y - i * 40
        c.setFillColor(GREY)
        c.setFont("Helvetica", 8)
        c.drawString(x, yy + 2, label)
        f.textfield(name=name, x=x, y=yy - 20, width=wd, height=18, borderColor=colors.grey,
                    fillColor=colors.white, textColor=INK, fontSize=10, borderWidth=0.5, forceBorder=True)
    d.y -= 140
    c.setFillColor(GREY)
    c.setFont("Helvetica", 8)
    c.drawString(M, d.y, "General notes")
    f.textfield(name="general_notes", x=M, y=d.y - 190, width=CW, height=180, fieldFlags="multiline",
                borderColor=colors.grey, fillColor=colors.white, textColor=INK, fontSize=10,
                borderWidth=0.5, forceBorder=True)
    d.footer_final()
    c.setSubject(json.dumps({"plinth_doc_id": doc_id, "version": version,
                             "questions": {f"q{n}": q.get("id", f"q{n}") for n, q in enumerate(questions, 1)}}))
    c.setKeywords(f"plinth,{doc_id},v{version}")
    c.showPage()
    c.save()
    return {"total": d.page, "qpages": used}


def _footer(d, total):
    c = d.c
    c.setFont("Helvetica", 7.5)
    c.setFillColor(GREY)
    c.setStrokeColor(colors.lightgrey)
    c.line(M, 0.6 * inch, W - M, 0.6 * inch)
    c.drawString(M, 0.42 * inch, f"{d.address} · {d.doc_id} v{d.version}")
    c.drawRightString(W - M, 0.42 * inch, f"Page {d.page} of {total}")
    c.drawCentredString(W / 2, 0.28 * inch, FOOT)
    # small mark just left of the centered line, so any page that gets photographed or forwarded
    # still carries the brand
    mark = 0.15 * inch
    draw_mark(c, W / 2 - c.stringWidth(FOOT, "Helvetica", 7.5) / 2 - mark - 4, 0.2 * inch, mark)


FIELDS_H = 150


def _sections(q):
    quote = _clip(q.get("code_ref"))
    code = (f"“{escape(quote)}” — <i>{escape(q.get('code_cite') or '')}</i>" if quote
            else "No section found in the knowledge base.")
    prec = escape(_clip(q.get("precedent"), 500)) if q.get("precedent") else "None found."
    return [("CONTEXT", escape(_clip(q.get("context"), 600)) or "—", "body"),
            ("CODE REFERENCE", code, "quote" if quote else "body"),
            ("PRECEDENT FOUND", prec, "body"),
            ("OUR PROPOSED READING", escape(_clip(q.get("proposed"), 600)) or "—", "body")]


def _block_height(q):
    h = 28
    for _, t, st in _sections(q):
        h += 12 + _height(t, st) + 4
    return h + FIELDS_H


def _question(d, n, q):
    c = d.c
    c.setFillColor(TEAL)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(M, d.y - 12, f"Q{n} · {q['title']}"[:90])
    c.setStrokeColor(TEAL)
    c.setLineWidth(0.75)
    c.line(M, d.y - 18, W - M, d.y - 18)
    d.y -= 26
    for label, text, style in _sections(q):
        d.y = _p(c, label, "label", M, d.y) - 1
        d.y = _p(c, text, style, M + (0 if style == "body" else 0), d.y) - 5
    # response fields
    f = c.acroForm
    y = d.y - 6
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(M, y - 8, "Response")
    x = M + 60
    for opt in OPTIONS:
        f.radio(name=f"q{n}_decision", value=opt, selected=False, x=x, y=y - 10, size=11,
                buttonStyle="circle", borderColor=colors.grey, fillColor=colors.white, textColor=INK,
                forceBorder=True)
        c.setFont("Helvetica", 9)
        c.drawString(x + 16, y - 8, opt)
        x += 16 + c.stringWidth(opt, "Helvetica", 9) + 22
    y -= 24
    c.setFillColor(GREY)
    c.setFont("Helvetica", 8)
    c.drawString(M, y - 6, "Notes")
    f.textfield(name=f"q{n}_notes", x=M + 60, y=y - 50, width=CW - 60, height=52, fieldFlags="multiline",
                borderColor=colors.grey, fillColor=colors.white, textColor=INK, fontSize=9,
                borderWidth=0.5, forceBorder=True)
    y -= 66
    c.drawString(M, y - 4, "Code section relied on")
    f.textfield(name=f"q{n}_section", x=M + 110, y=y - 8, width=200, height=16, borderColor=colors.grey,
                fillColor=colors.white, textColor=INK, fontSize=9, borderWidth=0.5, forceBorder=True)
    d.y = y - 34
