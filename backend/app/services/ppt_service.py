"""PPT rendering service using python-pptx with multiple style templates."""
from io import BytesIO
from typing import List
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
import os

# ── Colour palettes per style ────────────────────────────────────────

STYLES = {
    "academic": {
        "bg": RGBColor(0x1B, 0x2A, 0x4A),
        "title_color": RGBColor(0xFF, 0xFF, 0xFF),
        "body_color": RGBColor(0xE0, 0xE0, 0xE0),
        "accent": RGBColor(0x4F, 0xC3, 0xF7),
        "section_bg": RGBColor(0x15, 0x22, 0x3B),
        "bullet_color": RGBColor(0x4F, 0xC3, 0xF7),
    },
    "modern": {
        "bg": RGBColor(0x0F, 0x0F, 0x23),
        "title_color": RGBColor(0xFF, 0xFF, 0xFF),
        "body_color": RGBColor(0xCC, 0xCC, 0xCC),
        "accent": RGBColor(0x6C, 0x63, 0xFF),
        "section_bg": RGBColor(0x1A, 0x1A, 0x2E),
        "bullet_color": RGBColor(0x6C, 0x63, 0xFF),
    },
    "minimal": {
        "bg": RGBColor(0xFF, 0xFF, 0xFF),
        "title_color": RGBColor(0x22, 0x22, 0x22),
        "body_color": RGBColor(0x44, 0x44, 0x44),
        "accent": RGBColor(0x00, 0x7A, 0xFF),
        "section_bg": RGBColor(0xF5, 0xF5, 0xF5),
        "bullet_color": RGBColor(0x00, 0x7A, 0xFF),
    },
    "colorful": {
        "bg": RGBColor(0xFF, 0xF8, 0xE1),
        "title_color": RGBColor(0xE6, 0x5C, 0x00),
        "body_color": RGBColor(0x33, 0x33, 0x33),
        "accent": RGBColor(0xFF, 0x6F, 0x00),
        "section_bg": RGBColor(0xFF, 0xEC, 0xB3),
        "bullet_color": RGBColor(0xE6, 0x5C, 0x00),
    },
}

FONT_NAME = "Microsoft YaHei"
SLIDE_WIDTH = Inches(13.333)
SLIDE_HEIGHT = Inches(7.5)

PALETTE_KEYS = ("bg", "title_color", "body_color", "accent", "section_bg", "bullet_color")


def _hex_to_rgb(hex_str: str) -> RGBColor:
    """Turn '#FFF8E1' or 'FFF8E1' into an RGBColor; fall back to white on parse error."""
    try:
        s = (hex_str or "").strip().lstrip("#")
        if len(s) != 6:
            raise ValueError(f"bad hex length: {hex_str!r}")
        return RGBColor(int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))
    except Exception:
        return RGBColor(0xFF, 0xFF, 0xFF)


def _resolve_palette(style: str = "modern", palette: dict | None = None) -> dict:
    """Build the internal RGBColor palette dict used by renderers."""
    if palette:
        return {k: _hex_to_rgb(palette.get(k, "")) for k in PALETTE_KEYS}
    return STYLES.get(style, STYLES["modern"])


def _set_bg(slide, color: RGBColor):
    bg = slide.background
    fill = bg.fill
    fill.solid()
    fill.fore_color.rgb = color


def _add_text_box(slide, left, top, width, height, text, font_size, color, bold=False, alignment=PP_ALIGN.LEFT):
    txBox = slide.shapes.add_textbox(left, top, width, height)
    tf = txBox.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = text
    p.font.size = Pt(font_size)
    p.font.color.rgb = color
    p.font.bold = bold
    p.font.name = FONT_NAME
    p.alignment = alignment
    return txBox


def _render_title_slide(prs, slide_data, pal):
    slide = prs.slides.add_slide(prs.slide_layouts[6])  # blank
    _set_bg(slide, pal["bg"])

    title = slide_data.get("title", "")
    subtitle = slide_data.get("subtitle", "")

    _add_text_box(slide, Inches(1.5), Inches(2.2), Inches(10), Inches(1.5),
                  title, 44, pal["title_color"], bold=True, alignment=PP_ALIGN.CENTER)

    if subtitle:
        _add_text_box(slide, Inches(2), Inches(4.0), Inches(9), Inches(1),
                      subtitle, 22, pal["body_color"], alignment=PP_ALIGN.CENTER)

    # accent line
    from pptx.shapes.autoshape import Shape
    shape = slide.shapes.add_shape(1, Inches(4.5), Inches(3.8), Inches(4), Pt(3))
    shape.fill.solid()
    shape.fill.fore_color.rgb = pal["accent"]
    shape.line.fill.background()


def _render_section_header(prs, slide_data, pal):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _set_bg(slide, pal["section_bg"])

    title = slide_data.get("title", "")
    subtitle = slide_data.get("subtitle", "")

    _add_text_box(slide, Inches(1.5), Inches(2.5), Inches(10), Inches(1.5),
                  title, 36, pal["accent"], bold=True, alignment=PP_ALIGN.CENTER)
    if subtitle:
        _add_text_box(slide, Inches(2), Inches(4.2), Inches(9), Inches(1),
                      subtitle, 20, pal["body_color"], alignment=PP_ALIGN.CENTER)


def _render_content_slide(prs, slide_data, pal):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _set_bg(slide, pal["bg"])

    title = slide_data.get("title", "")
    bullets = slide_data.get("bullets", [])

    _add_text_box(slide, Inches(0.8), Inches(0.5), Inches(11.5), Inches(1),
                  title, 30, pal["title_color"], bold=True)

    # accent line under title
    shape = slide.shapes.add_shape(1, Inches(0.8), Inches(1.4), Inches(2), Pt(3))
    shape.fill.solid()
    shape.fill.fore_color.rgb = pal["accent"]
    shape.line.fill.background()

    # bullets
    txBox = slide.shapes.add_textbox(Inches(1.0), Inches(1.8), Inches(11), Inches(5))
    tf = txBox.text_frame
    tf.word_wrap = True

    for i, bullet in enumerate(bullets):
        if not bullet:
            continue
        p = tf.add_paragraph() if i > 0 else tf.paragraphs[0]
        p.text = f"●  {bullet}"
        p.font.size = Pt(18)
        p.font.color.rgb = pal["body_color"]
        p.font.name = FONT_NAME
        p.space_after = Pt(10)

    notes = slide_data.get("notes", "")
    if notes:
        slide.notes_slide.notes_text_frame.text = notes


def _render_closing_slide(prs, slide_data, pal):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _set_bg(slide, pal["bg"])

    title = slide_data.get("title", "谢谢")
    _add_text_box(slide, Inches(2), Inches(2.5), Inches(9), Inches(2),
                  title, 48, pal["accent"], bold=True, alignment=PP_ALIGN.CENTER)

    bullets = slide_data.get("bullets", [])
    if bullets:
        _add_text_box(slide, Inches(2), Inches(4.5), Inches(9), Inches(1.5),
                      "\n".join(bullets), 18, pal["body_color"], alignment=PP_ALIGN.CENTER)


def build_pptx(data: dict, style: str = "modern", palette: dict | None = None) -> bytes:
    pal = _resolve_palette(style, palette)
    prs = Presentation()
    prs.slide_width = SLIDE_WIDTH
    prs.slide_height = SLIDE_HEIGHT

    slides = data.get("slides", [])
    if not slides:
        slides = [{"layout": "title_slide", "title": data.get("title", "演示文稿"), "subtitle": "", "bullets": [], "notes": ""}]

    for sd in slides:
        layout = sd.get("layout", "content")
        if layout == "title_slide":
            _render_title_slide(prs, sd, pal)
        elif layout == "section_header":
            _render_section_header(prs, sd, pal)
        elif layout == "closing":
            _render_closing_slide(prs, sd, pal)
        else:
            _render_content_slide(prs, sd, pal)

    buf = BytesIO()
    prs.save(buf)
    return buf.getvalue()


def append_slides_to_pptx(existing_path: str, new_slides: list, style: str = "modern",
                          palette: dict | None = None) -> bytes:
    """Append extra slides to an existing .pptx and return the new file bytes."""
    pal = _resolve_palette(style, palette)
    prs = Presentation(existing_path)
    for sd in new_slides:
        layout = sd.get("layout", "content")
        if layout == "section_header":
            _render_section_header(prs, sd, pal)
        elif layout == "closing":
            _render_closing_slide(prs, sd, pal)
        else:
            _render_content_slide(prs, sd, pal)
    buf = BytesIO()
    prs.save(buf)
    return buf.getvalue()
