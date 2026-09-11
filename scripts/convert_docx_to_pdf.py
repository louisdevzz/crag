#!/usr/bin/env python3
"""Convert a .docx file to .pdf with full Unicode (Vietnamese) support,
preserving headings, lists, tables (with column widths and shading),
and inline images, managed with uv.

Usage:
    uv run python convert_docx_to_pdf.py <input.docx> [output.pdf]
"""
from __future__ import annotations

import sys
from io import BytesIO
from pathlib import Path

import docx
from docx.document import Document as DocxDocument
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.table import Table, _Cell
from docx.text.paragraph import Paragraph
from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.pdfmetrics import registerFontFamily
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    Image as RLImage,
    ListFlowable,
    ListItem,
    Paragraph as RLParagraph,
    SimpleDocTemplate,
    Spacer,
    Table as RLTable,
    TableStyle,
)

PAGE_WIDTH, PAGE_HEIGHT = A4
MARGIN = 1.8 * cm
AVAILABLE_WIDTH = PAGE_WIDTH - 2 * MARGIN
AVAILABLE_HEIGHT = PAGE_HEIGHT - 2 * MARGIN - 2 * cm

XML_ESCAPE = {"&": "&amp;", "<": "&lt;", ">": "&gt;"}


def esc(text: str) -> str:
    for a, b in XML_ESCAPE.items():
        text = text.replace(a, b)
    return text


def init_fonts():
    fonts_dir = Path(__file__).resolve().parent / "fonts"
    if not fonts_dir.exists():
        fonts_dir = Path(__file__).resolve().parent.parent / "fonts"
    pdfmetrics.registerFont(TTFont("Roboto", str(fonts_dir / "Roboto-Regular.ttf")))
    pdfmetrics.registerFont(TTFont("Roboto-Bold", str(fonts_dir / "Roboto-Bold.ttf")))
    pdfmetrics.registerFont(TTFont("Roboto-Italic", str(fonts_dir / "Roboto-Italic.ttf")))
    pdfmetrics.registerFont(TTFont("Roboto-BoldItalic", str(fonts_dir / "Roboto-BoldItalic.ttf")))
    registerFontFamily(
        "Roboto",
        normal="Roboto",
        bold="Roboto-Bold",
        italic="Roboto-Italic",
        boldItalic="Roboto-BoldItalic",
    )

    pdfmetrics.registerFont(TTFont("RobotoMono", str(fonts_dir / "RobotoMono-Regular.ttf")))
    pdfmetrics.registerFont(TTFont("RobotoMono-Bold", str(fonts_dir / "RobotoMono-Bold.ttf")))
    registerFontFamily(
        "RobotoMono",
        normal="RobotoMono",
        bold="RobotoMono-Bold",
        italic="RobotoMono",
        boldItalic="RobotoMono-Bold",
    )


def build_styles():
    base = getSampleStyleSheet()
    styles = {
        "Normal": ParagraphStyle(
            "DocNormal",
            parent=base["Normal"],
            fontName="Roboto",
            fontSize=10,
            leading=14.5,
            textColor=colors.HexColor("#222222"),
        ),
        "NormalCenter": ParagraphStyle(
            "DocNormalCenter",
            parent=base["Normal"],
            fontName="Roboto",
            fontSize=10,
            leading=14.5,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#222222"),
        ),
        "Title": ParagraphStyle(
            "DocTitle",
            parent=base["Title"],
            fontName="Roboto-Bold",
            fontSize=15,
            leading=20,
            alignment=TA_CENTER,
            spaceBefore=8,
            spaceAfter=6,
            textColor=colors.HexColor("#0f2b48"),
        ),
        "Heading1": ParagraphStyle(
            "DocHeading1",
            parent=base["Heading1"],
            fontName="Roboto-Bold",
            fontSize=14,
            leading=18,
            spaceBefore=14,
            spaceAfter=6,
            keepWithNext=True,
            textColor=colors.HexColor("#17365D"),
        ),
        "Heading2": ParagraphStyle(
            "DocHeading2",
            parent=base["Heading2"],
            fontName="Roboto-Bold",
            fontSize=11.5,
            leading=15.5,
            spaceBefore=10,
            spaceAfter=4,
            keepWithNext=True,
            textColor=colors.HexColor("#2b4a6f"),
        ),
        "Bullet": ParagraphStyle(
            "DocBullet",
            parent=base["Normal"],
            fontName="Roboto",
            fontSize=9.5,
            leading=13.5,
            textColor=colors.HexColor("#222222"),
        ),
        "Cell": ParagraphStyle(
            "DocCell",
            parent=base["Normal"],
            fontName="Roboto",
            fontSize=8.5,
            leading=11.5,
            alignment=TA_LEFT,
            textColor=colors.HexColor("#222222"),
        ),
        "CellHeader": ParagraphStyle(
            "DocCellHeader",
            parent=base["Normal"],
            fontName="Roboto-Bold",
            fontSize=8.5,
            leading=11.5,
            alignment=TA_LEFT,
            textColor=colors.white,
        ),
    }
    return styles


def runs_to_markup(paragraph: Paragraph) -> str:
    """Render paragraph runs to ReportLab mini-HTML with formatting."""
    parts: list[str] = []
    for run in paragraph.runs:
        text = esc(run.text or "")
        if not text:
            continue

        font_name = run.font.name or ""
        is_mono = font_name in ("Consolas", "Courier New", "Courier")

        color_hex = None
        if run.font.color and run.font.color.rgb:
            color_hex = f"#{run.font.color.rgb}"

        font_attrs = []
        if is_mono:
            font_attrs.append('name="RobotoMono"')
        if color_hex:
            font_attrs.append(f'color="{color_hex}"')

        inner = text
        if run.bold:
            inner = f"<b>{inner}</b>"
        if run.italic:
            inner = f"<i>{inner}</i>"
        if run.underline:
            inner = f"<u>{inner}</u>"

        if font_attrs:
            inner = f'<font {" ".join(font_attrs)}>{inner}</font>'

        parts.append(inner)
    return "".join(parts)


def iter_block_items(parent):
    """Yield Paragraph and Table elements in document flow order."""
    if isinstance(parent, DocxDocument):
        parent_elm = parent.element.body
    elif isinstance(parent, _Cell):
        parent_elm = parent._tc
    else:
        raise ValueError("unsupported parent type")

    for child in parent_elm.iterchildren():
        if child.tag == qn("w:p"):
            yield Paragraph(child, parent)
        elif child.tag == qn("w:tbl"):
            yield Table(child, parent)


def extract_inline_images(paragraph: Paragraph, doc: docx.document.Document) -> list[bytes]:
    images = []
    ns_r = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
    for drawing in paragraph._element.findall(".//" + qn("w:drawing")):
        blip = drawing.find(".//" + qn("a:blip"))
        if blip is None:
            continue
        rid = blip.get(ns_r + "embed")
        if not rid:
            continue
        try:
            part = doc.part.related_parts[rid]
        except KeyError:
            continue
        images.append(part.blob)
    return images


def render_image(blob: bytes, tmp_dir: Path, idx: int):
    buf = BytesIO(blob)
    try:
        pil_img = PILImage.open(buf)
        pil_img.load()
    except Exception:
        return None

    w, h = pil_img.size
    scale = min(1.0, AVAILABLE_WIDTH / float(w), AVAILABLE_HEIGHT / float(h))
    out_path = tmp_dir / f"_img_{idx}.png"

    if pil_img.mode not in ("RGB", "RGBA", "L"):
        pil_img = pil_img.convert("RGB")
    pil_img.save(out_path)
    return RLImage(str(out_path), width=w * scale, height=h * scale)


def get_cell_shading(cell: _Cell):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = tcPr.find(qn("w:shd"))
    if shd is not None:
        fill = shd.get(qn("w:fill"))
        if fill and fill.lower() not in ("auto", "none"):
            try:
                return colors.HexColor(f"#{fill}")
            except Exception:
                pass
    return None


def paragraph_flowables(p: Paragraph, doc, styles, tmp_dir, img_counter):
    flowables = []

    # Process inline images first
    images = extract_inline_images(p, doc)
    for blob in images:
        img_counter[0] += 1
        img = render_image(blob, tmp_dir, img_counter[0])
        if img is not None:
            flowables.append(Spacer(1, 4))
            flowables.append(img)
            flowables.append(Spacer(1, 6))

    text_markup = runs_to_markup(p)
    if not text_markup.strip():
        return flowables

    style_name = p.style.name if p.style else "Normal"
    align = p.alignment

    # Select appropriate style
    if style_name == "Heading 1":
        flowables.append(RLParagraph(text_markup, styles["Heading1"]))
    elif style_name == "Heading 2":
        flowables.append(RLParagraph(text_markup, styles["Heading2"]))
    elif style_name == "List Bullet":
        flowables.append(
            ListFlowable(
                [ListItem(RLParagraph(text_markup, styles["Bullet"]))],
                bulletType="bullet",
                start="•",
                leftIndent=16,
                bulletFontName="Roboto",
                bulletFontSize=9,
            )
        )
    elif style_name == "List Number":
        flowables.append(
            ListFlowable(
                [ListItem(RLParagraph(text_markup, styles["Bullet"]))],
                bulletType="1",
                leftIndent=16,
                bulletFontName="Roboto",
                bulletFontSize=9,
            )
        )
    else:
        if align == WD_ALIGN_PARAGRAPH.CENTER:
            # Check if this looks like a main title line (bold or first few paragraphs)
            is_bold = any(r.bold for r in p.runs)
            st = styles["Title"] if is_bold else styles["NormalCenter"]
        else:
            st = styles["Normal"]
        flowables.append(RLParagraph(text_markup, st))
        flowables.append(Spacer(1, 3))

    return flowables


def cell_flowables(cell: _Cell, doc, styles, tmp_dir, img_counter, is_header_cell: bool):
    flow = []
    for block in iter_block_items(cell):
        if isinstance(block, Paragraph):
            text_markup = runs_to_markup(block)
            if not text_markup.strip():
                continue
            st = styles["CellHeader"] if is_header_cell else styles["Cell"]
            flow.append(RLParagraph(text_markup, st))
        elif isinstance(block, Table):
            flow.append(render_table(block, doc, styles, tmp_dir, img_counter))
    if not flow:
        flow.append(RLParagraph("", styles["Cell"]))
    return flow


def compute_table_col_widths(table: Table) -> list[float]:
    """Compute column widths proportionally from docx cell dimensions."""
    n_cols = len(table.columns) if table.columns else (
        len(table.rows[0].cells) if table.rows else 0
    )
    if n_cols == 0:
        return [AVAILABLE_WIDTH]

    raw_widths = [0] * n_cols
    for row in table.rows:
        for idx, cell in enumerate(row.cells[:n_cols]):
            if cell.width and cell.width > raw_widths[idx]:
                raw_widths[idx] = cell.width

    total_raw = sum(raw_widths)
    if total_raw > 0:
        widths = [(w / total_raw) * AVAILABLE_WIDTH for w in raw_widths]
    else:
        widths = [AVAILABLE_WIDTH / n_cols] * n_cols
    return widths


def render_table(table: Table, doc, styles, tmp_dir, img_counter):
    col_widths = compute_table_col_widths(table)
    n_cols = len(col_widths)

    data = []
    style_cmds = [
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#C5CBD3")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]

    for r_idx, row in enumerate(table.rows):
        row_data = []
        for c_idx, cell in enumerate(row.cells[:n_cols]):
            shading = get_cell_shading(cell)
            if shading:
                style_cmds.append(("BACKGROUND", (c_idx, r_idx), (c_idx, r_idx), shading))

            # Header row styling if dark shading or top row of multi-row table
            is_dark_header = shading is not None and shading.hexval().upper() in ("17365D", "1F497D", "2C3E6B")
            is_header_cell = (r_idx == 0 and len(table.rows) > 1 and is_dark_header)

            flow = cell_flowables(cell, doc, styles, tmp_dir, img_counter, is_header_cell)
            row_data.append(flow)

        data.append(row_data)

    tbl = RLTable(data, colWidths=col_widths, repeatRows=1 if len(table.rows) > 1 else 0)
    tbl.setStyle(TableStyle(style_cmds))
    return tbl


class NumberedCanvas(canvas.Canvas):
    """Two-pass canvas to draw 'Trang X / Y' footer and subtle header."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_decorations(self, page_count: int):
        self.saveState()
        self.setFont("Roboto", 8)
        self.setFillColor(colors.HexColor("#777777"))

        # Footer
        footer_text = f"Trang {self._pageNumber} / {page_count}"
        self.drawRightString(PAGE_WIDTH - MARGIN, MARGIN / 2, footer_text)
        self.drawString(MARGIN, MARGIN / 2, "AI Agent Corrective RAG (CRAG) - V3")
        self.setStrokeColor(colors.HexColor("#E0E0E0"))
        self.setLineWidth(0.5)
        self.line(MARGIN, MARGIN / 2 + 12, PAGE_WIDTH - MARGIN, MARGIN / 2 + 12)

        self.restoreState()


def convert(input_path: Path, output_path: Path) -> None:
    init_fonts()
    doc = docx.Document(str(input_path))
    styles = build_styles()

    tmp_dir = output_path.parent / f".{output_path.stem}_tmp_images"
    tmp_dir.mkdir(exist_ok=True)

    story = []
    img_counter = [0]

    for block in iter_block_items(doc):
        if isinstance(block, Paragraph):
            story.extend(paragraph_flowables(block, doc, styles, tmp_dir, img_counter))
        elif isinstance(block, Table):
            story.append(Spacer(1, 4))
            story.append(render_table(block, doc, styles, tmp_dir, img_counter))
            story.append(Spacer(1, 6))

    pdf = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=MARGIN,
        bottomMargin=MARGIN,
        title=input_path.stem,
    )
    pdf.build(story, canvasmaker=NumberedCanvas)

    for f in tmp_dir.glob("_img_*.png"):
        f.unlink()
    try:
        tmp_dir.rmdir()
    except Exception:
        pass


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    input_path = Path(sys.argv[1]).resolve()
    if not input_path.exists():
        print(f"Input file not found: {input_path}")
        sys.exit(1)
    output_path = (
        Path(sys.argv[2]).resolve()
        if len(sys.argv) > 2
        else input_path.with_suffix(".pdf")
    )
    convert(input_path, output_path)
    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
