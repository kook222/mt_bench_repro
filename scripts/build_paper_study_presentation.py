#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_AUTO_SHAPE_TYPE
from pptx.enum.text import MSO_ANCHOR, MSO_AUTO_SIZE, PP_ALIGN
from pptx.util import Inches, Pt


ROOT = Path(__file__).resolve().parent.parent
FIG = ROOT / "figures"
BASE_FIG = FIG / "base_paper"
OUT_DIR = ROOT / "presentation"
OUT_DIR.mkdir(exist_ok=True)
PPTX_PATH = OUT_DIR / "mt_bench_paper_study.pptx"
NOTES_MD_PATH = OUT_DIR / "mt_bench_paper_study_notes.md"


BG = RGBColor(246, 242, 235)
DEEP = RGBColor(40, 44, 58)
NAVY = RGBColor(55, 86, 103)
TEAL = RGBColor(181, 101, 78)
SEA = RGBColor(128, 151, 140)
GOLD = RGBColor(191, 154, 94)
GREEN = RGBColor(102, 129, 133)
TEXT = RGBColor(54, 58, 72)
MUTED = RGBColor(112, 118, 125)
WHITE = RGBColor(255, 255, 255)
LINE = RGBColor(218, 212, 202)
PALE = RGBColor(239, 233, 225)
PALE2 = RGBColor(232, 238, 235)
PAPER_BG = RGBColor(247, 243, 237)
PAPER_RAIL = RGBColor(167, 97, 77)
PAPER_TINT = RGBColor(240, 232, 223)
RESEARCH_BG = RGBColor(239, 244, 246)
RESEARCH_RAIL = RGBColor(59, 88, 110)
RESEARCH_TINT = RGBColor(226, 234, 239)

FONT = "Apple SD Gothic Neo"
TITLE_SIZE = 26
BODY_SIZE = 17
SMALL_SIZE = 10

GRID_LEFT = 0.55
GRID_TOP = 1.42
GRID_WIDTH = 12.2
GRID_GAP = 0.28
GRID_HALF = (GRID_WIDTH - GRID_GAP) / 2
PANEL_H = 4.95


@dataclass
class SlideSpec:
    title: str
    section: str
    purpose: str
    bullets: list[str]
    notes: str
    layout: str = "content"
    takeaway: str | None = None
    images: list[Path] = field(default_factory=list)
    image_captions: list[str] = field(default_factory=list)
    stat_boxes: list[tuple[str, str]] = field(default_factory=list)
    cards: list[tuple[str, str]] = field(default_factory=list)
    compare_columns: list[tuple[str, list[str]]] = field(default_factory=list)


def section_theme(section: str) -> dict[str, RGBColor | str]:
    if section in {"Base Paper"}:
        return {
            "bg": PAPER_BG,
            "rail": PAPER_RAIL,
            "tint": PAPER_TINT,
            "footer": "논문 리뷰 | base paper and original claims",
            "section_label": "논문 리뷰",
        }
    if section in {"Reproduction", "Results", "Wrap-up", "Q&A"}:
        return {
            "bg": RESEARCH_BG,
            "rail": RESEARCH_RAIL,
            "tint": RESEARCH_TINT,
            "footer": "내 실험 | reproduction and extensions",
            "section_label": "내 실험",
        }
    return {
        "bg": BG,
        "rail": TEAL,
        "tint": PALE,
        "footer": "MT-Bench paper study | base paper + reproduction repo",
        "section_label": section,
    }


def add_textbox(
    slide,
    left,
    top,
    width,
    height,
    text="",
    *,
    font_size=BODY_SIZE,
    bold=False,
    color=TEXT,
    align=PP_ALIGN.LEFT,
    fill=None,
    line=None,
    margin=0.07,
    valign=MSO_ANCHOR.TOP,
    auto_fit=True,
):
    box = slide.shapes.add_textbox(left, top, width, height)
    tf = box.text_frame
    tf.clear()
    tf.word_wrap = True
    tf.margin_left = Inches(margin)
    tf.margin_right = Inches(margin)
    tf.margin_top = Inches(margin)
    tf.margin_bottom = Inches(margin)
    tf.vertical_anchor = valign
    if auto_fit:
        tf.auto_size = MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE
    p = tf.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text = text
    run.font.name = FONT
    run.font.size = Pt(font_size)
    run.font.bold = bold
    run.font.color.rgb = color
    if fill is not None:
        box.fill.solid()
        box.fill.fore_color.rgb = fill
    else:
        box.fill.background()
    if line is not None:
        box.line.color.rgb = line
    else:
        box.line.fill.background()
    return box


def header_title_size(text: str) -> int:
    n = len(text)
    if n >= 34:
        return 21
    if n >= 26:
        return 22
    return 24


def add_bullets(box, bullets: Iterable[str], *, font_size=BODY_SIZE, color=TEXT):
    tf = box.text_frame
    tf.clear()
    first = True
    for bullet in bullets:
        p = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        p.text = f"• {bullet}"
        p.level = 0
        p.space_after = Pt(8)
        p.space_before = Pt(0)
        p.line_spacing = 1.12
        p.font.name = FONT
        p.font.size = Pt(font_size)
        p.font.color.rgb = color
    return box


def add_picture(slide, path: Path, left, top, width=None, height=None):
    if width is not None and height is not None:
        return slide.shapes.add_picture(str(path), left, top, width=width, height=height)
    if width is not None:
        return slide.shapes.add_picture(str(path), left, top, width=width)
    if height is not None:
        return slide.shapes.add_picture(str(path), left, top, height=height)
    return slide.shapes.add_picture(str(path), left, top)


def add_panel(slide, left, top, width, height, *, fill=WHITE, line=LINE, margin=0.12):
    return add_textbox(slide, left, top, width, height, "", fill=fill, line=line, margin=margin)


def add_fitted_picture_panel(slide, path: Path, left, top, width, height, *, padding=0.12, fill=WHITE, line=LINE):
    add_panel(slide, left, top, width, height, fill=fill, line=line, margin=padding)
    pad = Inches(padding)
    inner_left = left + pad
    inner_top = top + pad
    inner_w = width - 2 * pad
    inner_h = height - 2 * pad

    with Image.open(path) as img:
        img_w, img_h = img.size

    scale = min(inner_w / img_w, inner_h / img_h)
    draw_w = int(img_w * scale)
    draw_h = int(img_h * scale)
    pic_left = int(left + (width - draw_w) / 2)
    pic_top = int(top + (height - draw_h) / 2)
    return add_picture(slide, path, pic_left, pic_top, width=draw_w, height=draw_h)


def add_stat_box(slide, left, top, label, value, accent):
    add_textbox(slide, left, top, Inches(2.22), Inches(0.96), "", fill=WHITE, line=LINE, margin=0.06)
    slide.shapes.add_shape(
        MSO_AUTO_SHAPE_TYPE.RECTANGLE,
        left + Inches(0.12),
        top + Inches(0.12),
        Inches(0.55),
        Inches(0.2),
    )
    chip = slide.shapes[-1]
    chip.fill.solid()
    chip.fill.fore_color.rgb = accent
    chip.line.fill.background()
    add_textbox(
        slide,
        left + Inches(0.14),
        top + Inches(0.12),
        Inches(1.85),
        Inches(0.2),
        label,
        font_size=9,
        bold=True,
        color=WHITE,
        margin=0.01,
        valign=MSO_ANCHOR.MIDDLE,
    )
    add_textbox(
        slide,
        left + Inches(0.12),
        top + Inches(0.38),
        Inches(1.9),
        Inches(0.34),
        value,
        font_size=19,
        bold=True,
        color=DEEP,
        margin=0.01,
    )


def paint_background(slide, color=BG):
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = color


def add_header(slide, title: str, section: str, idx: int, total: int):
    theme = section_theme(section)
    paint_background(slide, theme["bg"])
    slide.shapes.add_shape(MSO_AUTO_SHAPE_TYPE.RECTANGLE, Inches(0.36), Inches(0.42), Inches(0.14), Inches(0.92))
    rail = slide.shapes[-1]
    rail.fill.solid()
    rail.fill.fore_color.rgb = theme["rail"]
    rail.line.fill.background()
    slide.shapes.add_shape(MSO_AUTO_SHAPE_TYPE.RECTANGLE, Inches(0.36), Inches(0.2), Inches(12.45), Inches(0.04))
    top_line = slide.shapes[-1]
    top_line.fill.solid()
    top_line.fill.fore_color.rgb = LINE
    top_line.line.fill.background()
    add_textbox(
        slide,
        Inches(0.68),
        Inches(0.36),
        Inches(9.4),
        Inches(0.58),
        title,
        font_size=header_title_size(title),
        bold=True,
        color=DEEP,
        margin=0.0,
    )
    add_textbox(
        slide,
        Inches(10.5),
        Inches(0.44),
        Inches(1.55),
        Inches(0.22),
        theme["section_label"],
        font_size=10,
        bold=True,
        color=DEEP,
        align=PP_ALIGN.CENTER,
        fill=theme["tint"],
        line=theme["tint"],
        margin=0.01,
        valign=MSO_ANCHOR.MIDDLE,
    )
    add_textbox(
        slide,
        Inches(12.1),
        Inches(0.46),
        Inches(0.75),
        Inches(0.18),
        f"{idx}/{total}",
        font_size=10,
        bold=True,
        color=MUTED,
        align=PP_ALIGN.RIGHT,
        margin=0.0,
        valign=MSO_ANCHOR.MIDDLE,
    )
    slide.shapes.add_shape(MSO_AUTO_SHAPE_TYPE.RECTANGLE, Inches(0.52), Inches(7.02), Inches(12.25), Inches(0.04))
    foot = slide.shapes[-1]
    foot.fill.solid()
    foot.fill.fore_color.rgb = LINE
    foot.line.fill.background()
    add_textbox(
        slide,
        Inches(0.55),
        Inches(7.06),
        Inches(5.1),
        Inches(0.18),
        theme["footer"],
        font_size=8,
        color=MUTED,
        margin=0.0,
    )


def add_purpose_box(slide, purpose: str, section: str):
    theme = section_theme(section)
    add_textbox(
        slide,
        Inches(0.48),
        Inches(0.76),
        Inches(12.35),
        Inches(0.4),
        f"이 슬라이드의 목적: {purpose}",
        font_size=12,
        bold=True,
        color=DEEP,
        fill=theme["tint"],
        line=theme["tint"],
        margin=0.03,
        valign=MSO_ANCHOR.MIDDLE,
    )


def build_title_slide(prs: Presentation, spec: SlideSpec, total: int):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    paint_background(slide, PAPER_BG)
    slide.shapes.add_shape(MSO_AUTO_SHAPE_TYPE.RECTANGLE, Inches(0), Inches(0), Inches(6.86), Inches(7.5))
    left_panel = slide.shapes[-1]
    left_panel.fill.solid()
    left_panel.fill.fore_color.rgb = PAPER_BG
    left_panel.line.fill.background()
    slide.shapes.add_shape(MSO_AUTO_SHAPE_TYPE.RECTANGLE, Inches(6.86), Inches(0), Inches(6.47), Inches(7.5))
    right_panel = slide.shapes[-1]
    right_panel.fill.solid()
    right_panel.fill.fore_color.rgb = RESEARCH_BG
    right_panel.line.fill.background()
    slide.shapes.add_shape(MSO_AUTO_SHAPE_TYPE.RECTANGLE, Inches(0.28), Inches(0.55), Inches(0.16), Inches(5.45))
    accent = slide.shapes[-1]
    accent.fill.solid()
    accent.fill.fore_color.rgb = PAPER_RAIL
    accent.line.fill.background()
    slide.shapes.add_shape(MSO_AUTO_SHAPE_TYPE.RECTANGLE, Inches(7.12), Inches(0.72), Inches(0.14), Inches(4.9))
    accent2 = slide.shapes[-1]
    accent2.fill.solid()
    accent2.fill.fore_color.rgb = RESEARCH_RAIL
    accent2.line.fill.background()
    slide.shapes.add_shape(MSO_AUTO_SHAPE_TYPE.RECTANGLE, Inches(0.62), Inches(6.28), Inches(12.08), Inches(0.82))
    bottom = slide.shapes[-1]
    bottom.fill.solid()
    bottom.fill.fore_color.rgb = DEEP
    bottom.line.fill.background()

    add_textbox(
        slide,
        Inches(0.78),
        Inches(0.82),
        Inches(5.88),
        Inches(1.7),
        "Judging LLM-as-a-Judge\nwith MT-Bench\nand Chatbot Arena",
        font_size=27,
        bold=True,
        color=DEEP,
        margin=0.0,
    )
    add_textbox(
        slide,
        Inches(0.8),
        Inches(2.78),
        Inches(5.3),
        Inches(0.48),
        "1부 논문 발표 / 2부 내 실험",
        font_size=13,
        color=PAPER_RAIL,
        bold=True,
        margin=0.0,
    )
    add_textbox(
        slide,
        Inches(0.8),
        Inches(3.26),
        Inches(5.55),
        Inches(1.18),
        "앞 절반은 Zheng et al.의 MT-Bench / Chatbot Arena 논문을 읽고,\n뒤 절반은 그 프로토콜을 내 오픈소스 judge 실험으로 어떻게 옮겼는지 설명합니다.",
        font_size=15,
        color=TEXT,
    )
    add_textbox(slide, Inches(7.42), Inches(0.9), Inches(4.9), Inches(0.26), "Base paper figures that anchor the talk", font_size=14, bold=True, color=RESEARCH_RAIL, margin=0.0)
    add_picture(slide, BASE_FIG / "paper_chatbot_arena_ui.png", Inches(7.38), Inches(1.3), width=Inches(5.25))
    add_picture(slide, BASE_FIG / "paper_table8_scores.png", Inches(7.72), Inches(4.22), width=Inches(4.55))
    add_textbox(slide, Inches(7.42), Inches(4.0), Inches(5.18), Inches(0.18), "Original paper Figure 19", font_size=9, color=MUTED, align=PP_ALIGN.RIGHT, margin=0.0)
    add_textbox(slide, Inches(7.78), Inches(6.0), Inches(4.42), Inches(0.18), "Original paper Table 8", font_size=9, color=MUTED, align=PP_ALIGN.RIGHT, margin=0.0)

    add_textbox(
        slide,
        Inches(0.84),
        Inches(6.46),
        Inches(11.4),
        Inches(0.26),
        "핵심 질문: 원 논문의 strong-judge 메시지가 내 오픈소스 judge 실험에서는 어디까지 유지되는가?",
        font_size=15,
        bold=True,
        color=WHITE,
        margin=0.0,
    )
    add_textbox(
        slide,
        Inches(0.84),
        Inches(6.82),
        Inches(6.4),
        Inches(0.18),
        "박승현 | CLINK Lab | paper study + experiments",
        font_size=10,
        color=PALE2,
        margin=0.0,
    )
    slide.notes_slide.notes_text_frame.text = spec.notes


def build_divider_slide(prs: Presentation, spec: SlideSpec, idx: int, total: int):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    theme = section_theme(spec.section)
    paint_background(slide, theme["bg"])
    slide.shapes.add_shape(MSO_AUTO_SHAPE_TYPE.RECTANGLE, Inches(0.5), Inches(0.45), Inches(12.2), Inches(0.04))
    top = slide.shapes[-1]
    top.fill.solid()
    top.fill.fore_color.rgb = LINE
    top.line.fill.background()
    slide.shapes.add_shape(MSO_AUTO_SHAPE_TYPE.RECTANGLE, Inches(0.62), Inches(1.08), Inches(0.14), Inches(3.15))
    stripe = slide.shapes[-1]
    stripe.fill.solid()
    stripe.fill.fore_color.rgb = theme["rail"]
    stripe.line.fill.background()
    number = spec.title.split(".")[0] if "." in spec.title else str(idx)
    add_textbox(
        slide,
        Inches(9.35),
        Inches(1.15),
        Inches(2.9),
        Inches(1.55),
        number,
        font_size=74,
        bold=True,
        color=LINE,
        align=PP_ALIGN.RIGHT,
        margin=0.0,
    )

    add_textbox(
        slide,
        Inches(0.94),
        Inches(1.1),
        Inches(6.8),
        Inches(0.38),
        theme["section_label"],
        font_size=15,
        bold=True,
        color=theme["rail"],
        margin=0.0,
    )
    add_textbox(
        slide,
        Inches(0.94),
        Inches(1.7),
        Inches(7.6),
        Inches(0.95),
        spec.title,
        font_size=28,
        bold=True,
        color=DEEP,
        margin=0.0,
    )
    add_textbox(
        slide,
        Inches(0.94),
        Inches(3.02),
        Inches(7.45),
        Inches(1.05),
        spec.takeaway or "",
        font_size=18,
        color=DEEP,
        fill=theme["tint"],
        line=theme["tint"],
        margin=0.12,
    )
    add_textbox(
        slide,
        Inches(12.0),
        Inches(0.48),
        Inches(0.72),
        Inches(0.16),
        f"{idx}/{total}",
        font_size=10,
        bold=True,
        color=MUTED,
        align=PP_ALIGN.RIGHT,
        margin=0.0,
    )
    slide.notes_slide.notes_text_frame.text = spec.notes


def build_overview_slide(prs: Presentation, spec: SlideSpec, idx: int, total: int):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    theme = section_theme(spec.section)
    add_header(slide, spec.title, spec.section, idx, total)
    add_purpose_box(slide, spec.purpose, spec.section)
    left = add_textbox(slide, Inches(0.55), Inches(1.42), Inches(7.0), Inches(4.95), "", fill=WHITE, line=LINE, margin=0.12)
    add_bullets(left, spec.bullets, font_size=20)
    add_textbox(
        slide,
        Inches(7.85),
        Inches(1.42),
        Inches(4.95),
        Inches(0.32),
        "오늘 발표를 듣는 포인트",
        font_size=18,
        bold=True,
        color=DEEP,
    )
    insight = add_textbox(slide, Inches(7.85), Inches(1.86), Inches(4.95), Inches(3.9), "", fill=theme["tint"], line=theme["tint"], margin=0.14)
    add_bullets(
        insight,
        [
            "원 논문이 왜 영향력이 컸는지 먼저 이해한다.",
            "내 재현은 어디까지가 faithful reproduction이고 어디부터가 extension인지 구분한다.",
            "결과는 same-family / cross-family / hold-out 순서로 보수적으로 읽는다.",
        ],
        font_size=17,
    )
    if spec.takeaway:
        add_textbox(
            slide,
            Inches(7.85),
            Inches(6.0),
            Inches(4.95),
            Inches(0.65),
            spec.takeaway,
            font_size=16,
            bold=True,
            color=DEEP,
            fill=theme["tint"],
            line=theme["tint"],
            valign=MSO_ANCHOR.MIDDLE,
        )
    slide.notes_slide.notes_text_frame.text = spec.notes


def build_cards_slide(prs: Presentation, spec: SlideSpec, idx: int, total: int):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    theme = section_theme(spec.section)
    add_header(slide, spec.title, spec.section, idx, total)
    add_purpose_box(slide, spec.purpose, spec.section)

    if spec.takeaway:
        add_textbox(
            slide,
            Inches(0.55),
            Inches(1.42),
            Inches(12.2),
            Inches(0.62),
            spec.takeaway,
            font_size=19,
            bold=True,
            color=DEEP,
            fill=theme["tint"],
            line=theme["tint"],
            valign=MSO_ANCHOR.MIDDLE,
        )
        card_top = Inches(2.24)
    else:
        card_top = Inches(1.42)

    count = max(1, len(spec.cards))
    if count == 4:
        card_h = 1.58
        row_gap = 0.2
        row_tops = [card_top, card_top + Inches(card_h + row_gap)]
        col_lefts = [Inches(GRID_LEFT), Inches(GRID_LEFT + GRID_HALF + GRID_GAP)]
        card_w = Inches(GRID_HALF)
        for i, (head, body) in enumerate(spec.cards):
            row = i // 2
            col = i % 2
            left = col_lefts[col]
            top = row_tops[row]
            add_panel(slide, left, top, card_w, Inches(card_h), fill=WHITE, line=LINE, margin=0.12)
            add_textbox(slide, left + Inches(0.1), top + Inches(0.12), card_w - Inches(0.2), Inches(0.22), head, font_size=15, bold=True, color=theme["rail"], margin=0.0)
            add_textbox(slide, left + Inches(0.1), top + Inches(0.44), card_w - Inches(0.2), Inches(0.88), body, font_size=13.5, color=TEXT, margin=0.0)
        bullet_top = row_tops[-1] + Inches(card_h + 0.18)
        bullet_h = Inches(0.82)
    else:
        gap = 0.22
        width = (GRID_WIDTH - gap * (count - 1)) / count
        card_w = Inches(width)
        for i, (head, body) in enumerate(spec.cards):
            left = Inches(GRID_LEFT + i * (width + gap))
            add_panel(slide, left, card_top, card_w, Inches(2.22), fill=WHITE, line=LINE, margin=0.12)
            add_textbox(slide, left + Inches(0.08), card_top + Inches(0.12), card_w - Inches(0.16), Inches(0.26), head, font_size=15, bold=True, color=theme["rail"], margin=0.0)
            add_textbox(slide, left + Inches(0.08), card_top + Inches(0.52), card_w - Inches(0.16), Inches(1.3), body, font_size=14, color=TEXT, margin=0.0)
        bullet_top = Inches(4.82)
        bullet_h = Inches(1.42)

    if spec.bullets:
        body = add_textbox(slide, Inches(GRID_LEFT), bullet_top, Inches(GRID_WIDTH), bullet_h, "", fill=WHITE, line=LINE, margin=0.13)
        add_bullets(body, spec.bullets, font_size=15 if count == 4 else 16)
    slide.notes_slide.notes_text_frame.text = spec.notes


def build_compare_slide(prs: Presentation, spec: SlideSpec, idx: int, total: int):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    theme = section_theme(spec.section)
    add_header(slide, spec.title, spec.section, idx, total)
    add_purpose_box(slide, spec.purpose, spec.section)

    if spec.takeaway:
        add_textbox(
            slide,
            Inches(0.55),
            Inches(1.42),
            Inches(12.2),
            Inches(0.54),
            spec.takeaway,
            font_size=17,
            bold=True,
            color=DEEP,
            fill=theme["tint"],
            line=theme["tint"],
            valign=MSO_ANCHOR.MIDDLE,
        )
        top = Inches(2.16)
    else:
        top = Inches(1.42)

    for i, (head, items) in enumerate(spec.compare_columns[:2]):
        left = Inches(GRID_LEFT + i * (GRID_HALF + GRID_GAP))
        add_panel(slide, left, top, Inches(GRID_HALF), Inches(4.78), fill=WHITE, line=LINE, margin=0.13)
        add_textbox(slide, left + Inches(0.1), top + Inches(0.12), Inches(GRID_HALF - 0.2), Inches(0.26), head, font_size=18, bold=True, color=DEEP, margin=0.0)
        body = add_textbox(slide, left + Inches(0.1), top + Inches(0.52), Inches(GRID_HALF - 0.2), Inches(3.9), "", fill=None, line=None, margin=0.0)
        add_bullets(body, items, font_size=17)
    slide.notes_slide.notes_text_frame.text = spec.notes


def build_content_slide(prs: Presentation, spec: SlideSpec, idx: int, total: int):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    theme = section_theme(spec.section)
    add_header(slide, spec.title, spec.section, idx, total)
    add_purpose_box(slide, spec.purpose, spec.section)
    total_chars = sum(len(b) for b in spec.bullets)

    if len(spec.images) == 2:
        panel_top = Inches(1.38)
        panel_h = Inches(3.18)
        left_x = Inches(GRID_LEFT)
        right_x = Inches(GRID_LEFT + GRID_HALF + GRID_GAP)
        add_fitted_picture_panel(slide, spec.images[0], left_x, panel_top, Inches(GRID_HALF), panel_h)
        add_fitted_picture_panel(slide, spec.images[1], right_x, panel_top, Inches(GRID_HALF), panel_h)
        if spec.image_captions:
            add_textbox(slide, left_x, Inches(4.68), Inches(GRID_HALF), Inches(0.22), spec.image_captions[0], font_size=10, color=MUTED, align=PP_ALIGN.CENTER)
            add_textbox(slide, right_x, Inches(4.68), Inches(GRID_HALF), Inches(0.22), spec.image_captions[1], font_size=10, color=MUTED, align=PP_ALIGN.CENTER)
        body = add_textbox(slide, Inches(GRID_LEFT), Inches(4.96), Inches(GRID_WIDTH), Inches(1.48), "", fill=WHITE, line=LINE, margin=0.13)
        add_bullets(body, spec.bullets, font_size=15 if total_chars > 260 else 16)
        if spec.stat_boxes:
            for i, (label, value) in enumerate(spec.stat_boxes):
                accent = [NAVY, TEAL, GOLD, GREEN][i % 4]
                add_stat_box(slide, Inches(0.62 + i * 2.42), Inches(6.1), label, value, accent)
        elif spec.takeaway:
            add_textbox(
                slide,
                Inches(GRID_LEFT),
                Inches(6.12),
                Inches(GRID_WIDTH),
                Inches(0.6),
                spec.takeaway,
                font_size=16,
                bold=True,
                color=DEEP,
                fill=theme["tint"],
                line=theme["tint"],
                valign=MSO_ANCHOR.MIDDLE,
            )
    elif len(spec.images) == 1:
        image_left = Inches(0.45)
        image_top = Inches(1.38)
        image_w = Inches(7.72)
        image_h = Inches(4.35)
        add_fitted_picture_panel(slide, spec.images[0], image_left, image_top, image_w, image_h)
        if spec.image_captions:
            add_textbox(slide, Inches(0.62), Inches(5.88), Inches(7.48), Inches(0.22), spec.image_captions[0], font_size=10, color=MUTED, align=PP_ALIGN.CENTER)
        body = add_textbox(slide, Inches(8.38), Inches(1.38), Inches(4.35), Inches(4.35), "", fill=WHITE, line=LINE, margin=0.13)
        add_bullets(body, spec.bullets, font_size=15 if total_chars > 240 else 16)
        if spec.stat_boxes:
            for i, (label, value) in enumerate(spec.stat_boxes):
                accent = [NAVY, TEAL, GOLD, GREEN][i % 4]
                x = 8.45 + (i % 2) * 2.12
                y = 5.94 + (i // 2) * 0.98
                add_stat_box(slide, Inches(x), Inches(y), label, value, accent)
        elif spec.takeaway:
            add_textbox(
                slide,
                Inches(8.38),
                Inches(5.96),
                Inches(4.35),
                Inches(0.75),
                spec.takeaway,
                font_size=15,
                bold=True,
                color=DEEP,
                fill=theme["tint"],
                line=theme["tint"],
                valign=MSO_ANCHOR.MIDDLE,
            )
    else:
        body = add_textbox(slide, Inches(0.55), Inches(1.42), Inches(7.65), Inches(4.95), "", fill=WHITE, line=LINE, margin=0.14)
        add_bullets(body, spec.bullets, font_size=15 if total_chars > 320 else 16)
        add_textbox(slide, Inches(8.45), Inches(1.42), Inches(4.3), Inches(0.32), "핵심 해석", font_size=18, bold=True, color=DEEP)
        right = add_textbox(slide, Inches(8.45), Inches(1.8), Inches(4.3), Inches(4.57), "", fill=theme["tint"], line=theme["tint"], margin=0.14)
        if spec.takeaway:
            add_textbox(slide, Inches(8.62), Inches(2.02), Inches(3.9), Inches(1.28), spec.takeaway, font_size=16, bold=True, color=DEEP, margin=0.0)
        if spec.stat_boxes:
            for i, (label, value) in enumerate(spec.stat_boxes):
                accent = [NAVY, TEAL, GOLD, GREEN][i % 4]
                x = 8.62 + (i % 2) * 2.02
                y = 3.62 + (i // 2) * 1.0
                add_stat_box(slide, Inches(x), Inches(y), label, value, accent)
        else:
            add_textbox(slide, Inches(8.62), Inches(3.82), Inches(3.78), Inches(1.6), "이 슬라이드는 세부 실험보다도\n왜 이 논점이 다음 슬라이드의 전제가 되는지\n이해시키는 역할을 합니다.", font_size=14, color=TEXT)
    slide.notes_slide.notes_text_frame.text = spec.notes


def build_timeline_slide(prs: Presentation, spec: SlideSpec, idx: int, total: int):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    theme = section_theme(spec.section)
    add_header(slide, spec.title, spec.section, idx, total)
    add_purpose_box(slide, spec.purpose, spec.section)

    phases = [
        ("P1", "Self-judge"),
        ("P2", "Sanity"),
        ("P3", "Scaling"),
        ("P4", "InternLM"),
        ("P5", "GPT-4o-mini"),
        ("P6", "Hold-out"),
    ]
    slide.shapes.add_shape(MSO_AUTO_SHAPE_TYPE.RECTANGLE, Inches(1.0), Inches(2.1), Inches(11.1), Inches(0.06))
    line = slide.shapes[-1]
    line.fill.solid()
    line.fill.fore_color.rgb = LINE
    line.line.fill.background()
    xs = [1.0, 2.95, 4.9, 6.85, 8.8, 10.75]
    accents = [GOLD, TEAL, NAVY, GREEN, DEEP, NAVY]
    for x, (tag, label), accent in zip(xs, phases, accents):
        slide.shapes.add_shape(MSO_AUTO_SHAPE_TYPE.OVAL, Inches(x), Inches(1.72), Inches(0.72), Inches(0.72))
        circ = slide.shapes[-1]
        circ.fill.solid()
        circ.fill.fore_color.rgb = accent
        circ.line.fill.background()
        add_textbox(slide, Inches(x), Inches(1.91), Inches(0.72), Inches(0.15), tag, font_size=11, bold=True, color=WHITE, align=PP_ALIGN.CENTER, margin=0.0)
        add_textbox(slide, Inches(x - 0.18), Inches(2.48), Inches(1.08), Inches(0.35), label, font_size=12, bold=True, color=DEEP, align=PP_ALIGN.CENTER, margin=0.0)

    body = add_textbox(slide, Inches(GRID_LEFT), Inches(3.18), Inches(GRID_WIDTH), Inches(3.08), "", fill=WHITE, line=LINE, margin=0.13)
    add_bullets(body, spec.bullets, font_size=17)
    if spec.takeaway:
        add_textbox(slide, Inches(GRID_LEFT), Inches(6.38), Inches(GRID_WIDTH), Inches(0.42), spec.takeaway, font_size=15, bold=True, color=DEEP, fill=theme["tint"], line=theme["tint"], valign=MSO_ANCHOR.MIDDLE)
    slide.notes_slide.notes_text_frame.text = spec.notes


def build_notes_md(slides: list[SlideSpec]):
    lines = ["# MT-Bench Paper Study Notes", ""]
    for idx, spec in enumerate(slides, 1):
        lines.append(f"## Slide {idx}. {spec.title}")
        lines.append(f"- Section: {spec.section}")
        lines.append(f"- Purpose: {spec.purpose}")
        lines.append(f"- Layout: {spec.layout}")
        if spec.images:
            lines.append("- Visuals:")
            for img, cap in zip(spec.images, spec.image_captions or [p.name for p in spec.images]):
                lines.append(f"  - {img.name}: {cap}")
        if spec.bullets:
            lines.append("- Slide bullets:")
            for bullet in spec.bullets:
                lines.append(f"  - {bullet}")
        if spec.takeaway:
            lines.append(f"- Takeaway: {spec.takeaway}")
        if spec.stat_boxes:
            lines.append("- Stat boxes:")
            for label, value in spec.stat_boxes:
                lines.append(f"  - {label}: {value}")
        lines.append("")
        lines.append("### Speaker Notes")
        lines.append(spec.notes.strip())
        lines.append("")
    NOTES_MD_PATH.write_text("\n".join(lines), encoding="utf-8")


def get_slide_specs() -> list[SlideSpec]:
    return [
        SlideSpec(
            title="MT-Bench / Chatbot Arena\n논문 스터디와 내 실험",
            section="Title",
            purpose="앞은 논문 스터디, 뒤는 그 프로토콜을 따른 내 실험이라는 구조를 먼저 알린다.",
            bullets=[],
            layout="title",
            notes="""오늘 발표는 두 부분으로 나뉩니다.
앞 절반은 Zheng et al.의 MT-Bench / Chatbot Arena 논문 자체를 읽는 시간이 되고,
뒤 절반은 그 프로토콜을 제가 오픈소스 judge 환경에서 어떻게 옮겨 실험했는지 설명하는 구조입니다.

즉 먼저 논문이 해결한 문제와 핵심 주장, 한계를 이해하고,
그 다음에 제 실험이 그 논문에 어떤 질문을 더 던졌는지를 보겠습니다.

오늘의 최종 메시지는 간단합니다.
원 논문은 strong judge의 가능성을 설득력 있게 보여준 기준점이고,
제 실험은 그 메시지를 오픈소스 judge 환경으로 옮겼을 때 어디까지 유지되는지를 보여줍니다.""",
        ),
        SlideSpec(
            title="오늘 발표는 1부 논문 발표, 2부 내 실험입니다",
            section="Roadmap",
            purpose="앞의 paper study와 뒤의 experiment block을 한 번에 보여준다.",
            bullets=[],
            layout="cards",
            takeaway="핵심 질문: 원 논문의 strong-judge 메시지가 오픈소스 judge 실험에서는 어디까지 유지되는가?",
            cards=[
                ("1부. 논문 발표", "MT-Bench와 Chatbot Arena의 문제의식, judge 프로토콜, 핵심 결과와 한계를 먼저 정리합니다."),
                ("2부. 내 실험", "같은 프로토콜을 Qwen · InternLM · GPT-4o-mini judge 조합으로 어떻게 옮겼는지 설명합니다."),
                ("최종 메시지", "논문은 strong judge의 기준점을 주고, 내 실험은 그 결론을 오픈소스 judge 환경에서 어디까지 믿을 수 있는지 보여줍니다."),
            ],
            notes="""이 슬라이드는 오늘 발표의 구조를 정하는 슬라이드입니다.
앞에서는 논문 자체를 하나의 완결된 주장으로 읽고,
뒤에서는 그 프로토콜을 제가 어떻게 재현하고 확장했는지 보여드리겠습니다.

그래서 발표의 흐름은 자연스럽게 이어집니다.
먼저 원 논문이 strong judge를 어떻게 설득했는지 보고,
그 다음에 그 메시지가 오픈소스 judge 환경에서도 얼마나 유지되는지를 제 실험으로 확인합니다.

즉 오늘 발표는 paper review와 experiment review가 연결된 구조라고 보시면 됩니다.""",
        ),
        SlideSpec(
            title="논문 발표",
            section="Base Paper",
            purpose="이제부터는 원 논문 자체를 집중해서 읽는 파트라는 점을 분명히 한다.",
            bullets=[],
            layout="divider",
            takeaway="지금부터는 MT-Bench / Chatbot Arena 논문 자체의 문제의식과 설계를 순서대로 읽겠습니다.",
            notes="""이 슬라이드는 분위기를 한 번 정리하기 위한 divider입니다.
여기부터는 원 논문만 집중해서 보겠습니다.

즉 benchmark가 왜 필요했는지, Arena와 어떻게 연결되는지,
judge prompt와 scoring flow는 어떤 형태인지,
그리고 핵심 결과와 한계가 무엇인지 차례대로 보겠습니다.""",
        ),
        SlideSpec(
            title="1. 왜 MT-Bench가 필요했는가",
            section="Base Paper",
            purpose="원 논문이 겨냥한 평가 문제를 먼저 선명하게 만든다.",
            bullets=[
                "기존 객관식/단답형 벤치마크는 open-ended, multi-turn 대화 품질을 충분히 반영하지 못한다.",
                "사람 preference 평가만으로는 비용과 시간이 너무 커서 빠른 모델 개발 루프에 맞지 않는다.",
                "그래서 원 논문은 ‘사람 선호를 근사하는 실용적 자동 judge’를 핵심 문제로 세운다.",
            ],
            images=[BASE_FIG / "paper_chatbot_arena_ui.png", BASE_FIG / "paper_mtbench_winrate_fig3.png"],
            image_captions=["Original paper Figure 19: Chatbot Arena UI", "Original paper Figure 3: MT-Bench score와 Arena 승률 관계"],
            takeaway="이 논문의 중심은 benchmark 하나를 새로 만드는 것이 아니라, 사람 평가를 실용적으로 대체할 judge 체계를 세우는 데 있습니다.",
            notes="""이 논문의 출발점은 매우 현실적입니다.
대화형 모델을 평가하려면 open-ended 품질과 multi-turn 능력을 봐야 하는데,
기존 객관식 벤치마크만으로는 그 부분이 잘 드러나지 않습니다.
반대로 사람 선호를 직접 평가하면 정확하지만 너무 비싸고 느립니다.

그래서 저자들은 controlled benchmark와 in-the-wild preference를 함께 설계합니다.
왼쪽 그림은 Chatbot Arena의 실제 사용자 인터페이스고,
오른쪽 그림은 MT-Bench 점수와 Arena 승률 사이 관계를 보여줍니다.
즉 이 논문은 benchmark와 실제 선호를 연결해서 judge의 타당성을 설명하려 했습니다.""",
        ),
        SlideSpec(
            title="2. MT-Bench와 Chatbot Arena는 어떻게 역할을 나눴는가",
            section="Base Paper",
            purpose="두 자산의 역할 분담을 명확히 이해하게 한다.",
            bullets=[
                "MT-Bench는 8개 카테고리, 80문항의 multi-turn benchmark로 controlled comparison을 담당한다.",
                "Chatbot Arena는 실제 사용자 pairwise preference를 모아 ecological validity를 제공한다.",
                "즉 MT-Bench는 재현 가능성, Arena는 현실 적합성을 제공하는 쌍으로 설계되었다.",
            ],
            stat_boxes=[("MT-Bench", "80문항"), ("Category", "8개"), ("Arena", "익명 pairwise"), ("Goal", "human preference")],
            takeaway="논문의 힘은 MT-Bench 하나가 아니라, benchmark와 crowd preference를 함께 설계했다는 데 있습니다.",
            notes="""MT-Bench와 Arena는 둘 다 평가 자산이지만 역할이 다릅니다.
MT-Bench는 controlled benchmark라서 같은 질문 세트로 모델들을 반복 비교할 수 있고,
카테고리별 분석도 가능합니다.

반면 Arena는 실제 사용자 환경입니다.
질문도 자유롭고 사용자는 모델 이름을 모른 채 두 응답 중 더 나은 쪽을 고릅니다.
재현성은 떨어지지만 현실의 인간 선호를 더 잘 반영합니다.

원 논문은 바로 이 둘을 함께 묶음으로써,
benchmark 점수가 실제 선호와도 연결될 수 있다는 점을 설득합니다.""",
        ),
        SlideSpec(
            title="3. 원 논문은 judge를 어떻게 썼는가",
            section="Base Paper",
            purpose="single, pairwise, reference-guided judge mode를 구조적으로 소개한다.",
            bullets=[
                "논문은 single, pairwise, reference-guided judge를 함께 사용하면서 bias 분석까지 병행한다.",
            ],
            layout="cards",
            cards=[
                ("Single-answer grading", "답변 하나를 절대 점수로 채점해 모델 서열과 카테고리별 분포를 보기 좋습니다."),
                ("Pairwise comparison", "두 응답 중 winner를 직접 고르게 해 실제 사용자 pairwise preference와 닮은 평가를 만듭니다."),
                ("Reference-guided grading", "수학·코딩처럼 정답 기준이 중요한 영역에서는 reference answer를 함께 제공합니다."),
            ],
            takeaway="이 논문의 핵심은 GPT-4를 막연히 채점기로 쓴 것이 아니라, judge mode를 문제 유형에 맞게 나눴다는 점입니다.",
            notes="""이 슬라이드는 judge 프로토콜의 뼈대를 설명합니다.
single-answer grading은 절대 점수 평가이고, pairwise는 두 응답의 상대 비교입니다.
reference-guided grading은 특히 math와 coding처럼 정답 기준이 중요한 영역에서 필요합니다.

중요한 점은 원 논문이 judge를 하나의 단일 API 호출로 다루지 않았다는 것입니다.
task 특성에 따라 다른 judge mode를 쓰고,
그 위에서 bias를 따로 분석합니다.
이 점이 이후 LLM-as-a-Judge 연구의 기본 틀을 만든 부분이라고 볼 수 있습니다.""",
        ),
        SlideSpec(
            title="4. MT-Bench judge prompt는 어떤 형식으로 주어지는가",
            section="Base Paper",
            purpose="judge prompt의 입력/출력 contract를 이해하게 한다.",
            bullets=[
                "핵심은 judge가 자유롭게 서술하는 것이 아니라, parse 가능한 형식으로 답하게 만든다는 점이다.",
            ],
            layout="compare",
            compare_columns=[
                ("입력 prompt 구조", [
                    "single: question + answer + rubric",
                    "pairwise: question + answer A/B + 비교 지시",
                    "turn2: q1-a1-q2-a2를 포함한 multi-turn context",
                    "math/coding: reference answer가 추가된 prompt",
                ]),
                ("출력 형식과 의미", [
                    "single: [[rating]] 형태의 점수",
                    "pairwise: [[A]], [[B]], [[C]]로 winner/tie 표시",
                    "prompt는 평가 내용뿐 아니라 output format까지 강하게 제약",
                    "즉 prompt engineering보다 output contract가 중요하다",
                ]),
            ],
            takeaway="원 논문의 judge는 자유 응답형 채점기가 아니라, 입력과 출력 형식을 강하게 통제한 평가 프로토콜입니다.",
            notes="""이 슬라이드는 judge prompt를 설명하는 슬라이드입니다.
여기서 중요한 포인트는 judge가 단순히 똑똑한 모델이어서 잘 평가하는 것이 아니라,
입력과 출력 형식이 상당히 엄격하게 설계되어 있다는 점입니다.

single은 [[rating]] 점수, pairwise는 [[A]], [[B]], [[C]] 형식을 요구합니다.
turn2는 두 번째 턴만 따로 보지 않고 q1, a1, q2, a2를 함께 넣어 multi-turn 문맥을 유지합니다.
math와 coding은 reference answer를 추가합니다.

즉 MT-Bench judge는 모델 자체 능력뿐 아니라,
parse 가능하고 안정적인 출력을 강제하는 프로토콜 설계가 함께 작동하는 구조입니다.""",
        ),
        SlideSpec(
            title="5. judge 점수평가는 실제로 어떻게 흘러가는가",
            section="Base Paper",
            purpose="answer generation부터 parse와 aggregation까지 흐름을 한 번에 보여준다.",
            bullets=[
                "generation과 judging의 temperature를 분리해 답변 다양성과 평가 결정성을 अलग 계층으로 관리한다.",
                "single은 turn1 독립 prompt와 turn2 multi-turn prompt를 구분한다.",
                "pairwise는 AB/BA swap 뒤에도 유지되는 winner만 채택해 순서 민감성을 직접 점검한다.",
            ],
            layout="cards",
            cards=[
                ("Step 1. 답변 생성", "각 모델이 80문항 2-turn 답변을 생성합니다."),
                ("Step 2. judge 호출", "single과 pairwise prompt를 사용해 모델 응답을 채점합니다."),
                ("Step 3. 파싱", "점수나 winner를 파싱 가능한 토큰으로 추출합니다."),
                ("Step 4. 집계", "turn 평균, swap consistency 등 규칙을 적용해 최종 score와 winner를 정합니다."),
            ],
            takeaway="논문의 재현성 핵심은 prompt 문구보다도 parse와 aggregation rule을 명확히 정의한 데 있습니다.",
            notes="""judge 시스템을 이해하려면 prompt만 보면 부족하고,
실제 scoring flow 전체를 봐야 합니다.
먼저 답변을 생성하고, judge를 호출한 뒤,
출력을 파싱하고 마지막으로 aggregation 규칙을 적용합니다.

특히 pairwise에서는 AB와 BA를 모두 봅니다.
핵심은 한 번 winner를 맞히는 것이 아니라,
순서를 바꿔도 같은 winner가 유지되는지를 확인하는 것입니다.
이 점이 원 논문이 위치 편향을 단순 추측이 아니라 실험적으로 다룰 수 있게 만든 이유입니다.""",
        ),
        SlideSpec(
            title="6. 원 논문의 두 핵심 주장은 무엇이었나",
            section="Base Paper",
            purpose="논문의 가장 중요한 두 메시지를 또렷하게 세운다.",
            bullets=[
                "핵심 주장 1: GPT-4 judge는 MT-Bench에서 human expert와 non-tie agreement 85%, human-human 81% 수준으로 맞는다.",
                "핵심 주장 2: MT-Bench 점수는 GPT-4 8.99, GPT-3.5 7.94, Vicuna-13B 6.39, LLaMA-13B 2.61처럼 모델 품질 차이를 설득력 있게 서열화한다.",
                "즉 이 논문은 judge-human agreement와 model ranking validity를 동시에 주장한다.",
            ],
            images=[BASE_FIG / "paper_mtbench_agreement_table5.png", BASE_FIG / "paper_table8_scores.png"],
            image_captions=["Original paper Table 5: judge-human agreement", "Original paper Table 8: MT-Bench model scores"],
            takeaway="이 논문의 영향력은 결국 ‘judge가 인간과 꽤 맞는다’와 ‘score가 모델 품질을 반영한다’는 두 메시지에서 나옵니다.",
            notes="""이 슬라이드는 원 논문을 가장 직접적으로 요약하는 슬라이드입니다.
왼쪽은 judge-human agreement, 오른쪽은 model ranking입니다.

저자들은 GPT-4 judge가 human expert와 높은 agreement를 보인다고 주장하고,
동시에 MT-Bench score가 모델 품질 차이를 설득력 있게 드러낸다고 말합니다.
이 두 메시지가 결합되면서 LLM-as-a-Judge라는 프레임이 매우 강해졌습니다.

즉 이 논문은 단순히 새로운 benchmark를 만든 것이 아니라,
strong judge를 기반으로 한 evaluation 체계의 가능성을 보여준 논문입니다.""",
        ),
        SlideSpec(
            title="7. 원 논문은 bias를 무시하지 않았다",
            section="Base Paper",
            purpose="원 논문이 judge를 편향이 있는 measurement system으로 다뤘음을 보여준다.",
            bullets=[],
            layout="compare",
            compare_columns=[
                ("논문이 직접 본 편향", [
                    "position bias: 응답 순서가 바뀌면 winner가 달라질 수 있다.",
                    "verbosity bias: 더 긴 답변이 유리할 수 있다.",
                    "self-enhancement bias: judge가 자기 계열 모델에 유리할 수 있다.",
                ]),
                ("왜 중요한가", [
                    "agreement 숫자가 높아도 남는 오류 구조를 따로 봐야 한다.",
                    "judge는 완벽한 oracle이 아니라 편향이 있는 measurement system이다.",
                    "이 논문이 이후 연구의 baseline이 된 이유도 바로 이 분석적 태도에 있다.",
                ]),
            ],
            takeaway="원 논문의 진짜 장점은 strong judge를 자랑한 데만 있지 않고, judge를 편향이 있는 시스템으로 분석했다는 데 있습니다.",
            notes="""많은 사람이 이 논문을 agreement 숫자로만 기억하지만,
사실 더 중요한 부분은 bias analysis입니다.
position bias, verbosity bias, self-enhancement bias를 별도로 본다는 것은,
저자들이 judge를 완벽한 채점기가 아니라 편향을 가진 measurement system으로 취급했다는 뜻입니다.

이 태도가 논문을 더 강하게 만듭니다.
왜냐하면 strong result를 주장하면서도 동시에 그 경계를 함께 말하기 때문입니다.
그래서 이 슬라이드는 단순한 caveat가 아니라,
논문의 설득 방식 자체를 보여주는 슬라이드라고 보시면 됩니다.""",
        ),
        SlideSpec(
            title="8. 이 논문이 남긴 열린 질문은 무엇이었나",
            section="Base Paper",
            purpose="논문의 의의와 동시에 남는 한계를 균형 있게 정리한다.",
            bullets=[
                "GPT-4 judge는 강력하지만 closed API라 비용, 버전 drift, 재현성 문제가 남는다.",
                "MT-Bench와 Arena의 연결은 강하지만, strong judge 결론을 다른 judge family에 그대로 옮길 수는 없다.",
                "따라서 이 논문은 끝이라기보다, 이후 LLM-as-a-Judge 연구가 어디를 더 검증해야 하는지 기준점을 남긴 paper로 읽는 것이 맞다.",
            ],
            stat_boxes=[("의의 1", "strong judge"), ("의의 2", "benchmark + arena"), ("한계 1", "closed API"), ("한계 2", "generalization")],
            takeaway="좋은 paper study의 결론은 ‘대단하다’가 아니라, 이 논문이 무엇을 해결했고 무엇을 남겼는지 균형 있게 정리하는 것입니다.",
            notes="""마지막 내용 슬라이드에서는 이 논문을 균형 있게 닫겠습니다.
이 논문은 강합니다. strong judge 메시지, benchmark와 Arena의 결합,
bias analysis까지 모두 이후 연구의 기준점이 됐습니다.

하지만 동시에 한계도 분명합니다.
closed API 의존성, 비용, 재현성 문제,
그리고 strong judge 결론이 다른 family나 더 작은 judge에도 유지되는지는 아직 열려 있습니다.

그래서 이 논문은 완성형 답이라기보다,
이후 LLM-as-a-Judge 연구가 어디를 더 검증해야 하는지 방향을 정해 준 기준점으로 읽는 것이 가장 공정합니다.""",
        ),
        SlideSpec(
            title="정리: 이 논문을 어떻게 기억하면 되는가",
            section="Base Paper",
            purpose="논문 전체 메시지를 한 장에서 정리해 준다.",
            bullets=[],
            layout="cards",
            cards=[
                ("문제의식", "open-ended multi-turn 대화를 사람 평가만으로는 감당하기 어렵다는 현실적 문제를 정확히 짚었습니다."),
                ("기술적 기여", "MT-Bench와 Chatbot Arena를 묶고, single / pairwise / reference judge 프로토콜을 정교하게 설계했습니다."),
                ("핵심 결과", "GPT-4 judge-human agreement와 model ranking validity를 함께 설득했습니다."),
                ("남은 과제", "closed judge 의존성과 generalization 문제는 이후 연구가 이어서 풀어야 할 부분입니다."),
            ],
            takeaway="즉 이 논문은 LLM-as-a-Judge가 가능하다는 첫 강한 기준점을 남긴 논문으로 기억하는 것이 가장 적절합니다.",
            notes="""마지막 정리 슬라이드입니다.
이 논문은 왜 중요했는지, 무엇을 보여줬는지, 무엇이 아직 남았는지를 네 카드로 요약했습니다.

발표를 마치고 나면 이 네 가지만 기억하시면 됩니다.
문제의식은 현실적이었고, 기술적 설계는 정교했으며,
핵심 결과는 강했고, 동시에 남은 한계도 분명했습니다.

그래서 이 논문은 단순 benchmark paper가 아니라,
LLM-as-a-Judge 연구의 출발점을 만든 기준 논문으로 기억하는 것이 맞습니다.""",
        ),
        SlideSpec(
            title="2부. 내 실험",
            section="Reproduction",
            purpose="이제부터는 원 논문 프로토콜을 내 실험으로 어떻게 옮겼는지 설명한다.",
            bullets=[],
            layout="divider",
            takeaway="여기부터는 원 논문을 요약하는 것이 아니라, 그 judge 프로토콜을 오픈소스 judge 환경으로 옮긴 내 실험을 설명합니다.",
            notes="""앞 절반에서는 원 논문이 무엇을 주장했는지 정리했습니다.
이제부터는 그 프로토콜을 제가 어떻게 가져와서 실험했는지 설명드리겠습니다.

즉 MT-Bench 80문항과 single/pairwise/reference 구조는 유지하되,
judge를 Qwen, InternLM, GPT-4o-mini로 바꾸고
self-judge, scaling, hold-out까지 확장한 부분을 보겠습니다.""",
        ),
        SlideSpec(
            title="2-1. 원 논문 프로토콜을 내 실험으로 어떻게 옮겼는가",
            section="Reproduction",
            purpose="원 논문에서 그대로 가져온 것과 추가한 검증 축을 분리해 보여준다.",
            bullets=[],
            layout="compare",
            compare_columns=[
                ("그대로 가져온 것", [
                    "MT-Bench 80문항, 8개 카테고리, 2-turn 구조",
                    "single / pairwise / reference-guided judge mode",
                    "AB/BA swap 뒤 일치 winner만 채택하는 pairwise rule",
                    "math·coding에 reference-guided 채점 적용",
                ]),
                ("내가 추가한 것", [
                    "judge를 GPT-4 단일 축이 아니라 Qwen / InternLM / GPT-4o-mini로 확장",
                    "Phase 1–6로 self-judge, scaling, ensemble, hold-out 검증 추가",
                    "raw judgment JSONL, aggregate CSV, figure를 모두 저장소에 남김",
                    "same-set tinyMT뿐 아니라 repeated hold-out으로 운영점 검증",
                ]),
            ],
            takeaway="즉 핵심 judge protocol은 유지하되, 검증 축과 실험 범위를 오픈소스 환경으로 넓힌 것이 내 실험입니다.",
            notes="""이 슬라이드는 제 실험이 원 논문과 어떤 관계에 있는지 명확히 하는 슬라이드입니다.
왼쪽은 의도적으로 그대로 가져온 부분입니다.
MT-Bench 질문, judge mode, swap consistency rule 같은 핵심 프로토콜은 유지했습니다.

오른쪽은 제가 추가한 부분입니다.
judge family를 넓히고, self-judge부터 hold-out까지 단계별로 검증했고,
산출물도 raw judgment부터 figure까지 재현 가능하게 남겼습니다.

즉 이 실험은 원 논문과 별개가 아니라,
같은 protocol을 다른 judge 조건에서 더 넓게 시험한 작업이라고 이해하시면 됩니다.""",
        ),
        SlideSpec(
            title="2-2. 내 실험 세팅과 산출물은 어떻게 구성했는가",
            section="Reproduction",
            purpose="모델, judge, temperature, 산출물 구조를 한 장에서 설명한다.",
            bullets=[
                "generation은 temperature 0.7, judge는 temperature 0.0으로 분리해 답변 다양성과 평가 결정성을 따로 관리했다.",
                "산출물은 answer JSONL, single/pairwise/reference judgment JSONL, aggregate CSV, figure까지 단계별로 저장했다.",
                "즉 발표 수치는 raw judgment → aggregate → figure 경로를 따라 다시 검증할 수 있다.",
            ],
            layout="cards",
            cards=[
                ("평가 대상 모델", "seen 7개 모델과 hold-out용 unseen 확장 모델들을 사용했습니다."),
                ("judge 패밀리", "Qwen 7B/14B/32B, InternLM 7B/20B, GPT-4o-mini를 judge로 사용했습니다."),
                ("실행 규칙", "single은 점수, pairwise는 A/B/tie/error, reference는 math·coding 중심으로 따로 실행했습니다."),
                ("산출물 구조", "data에는 raw JSONL과 CSV, figures에는 시각화, paper에는 최종 해석을 남겼습니다."),
            ],
            takeaway="뒤의 결과는 단순 숫자가 아니라 generation → judge → aggregate → figure 파이프라인 전체에서 나온 값들입니다.",
            notes="""이 슬라이드는 제 실험이 실제로 어떻게 실행됐는지를 더 구체적으로 설명합니다.
결과만 보는 것보다 어떤 모델을 어떤 judge로 어떤 규칙 아래 돌렸는지를 알아야 수치가 더 설득력 있게 보입니다.

generation과 judging의 temperature를 분리했고,
judge는 Qwen, InternLM, GPT-4o-mini로 나눴습니다.
또 raw judgment에서 끝나지 않고 CSV와 figure까지 연결했습니다.

그래서 발표에서 보이는 숫자는 저장소에서 다시 따라가며 검증할 수 있습니다.""",
        ),
        SlideSpec(
            title="2-3. 내가 실제로 검증한 네 연구 질문",
            section="Reproduction",
            purpose="뒤 절반을 네 개의 연구 질문 구조로 듣게 한다.",
            bullets=[
                "즉 뒤 절반은 phase log가 아니라 RQ1부터 RQ4까지 답을 찾아가는 흐름으로 듣는 것이 가장 자연스럽다.",
            ],
            layout="cards",
            cards=[
                ("RQ1. judge scaling", "Qwen judge를 7B → 14B → 32B로 키우면 pairwise reliability가 실제로 단조 개선되는가?"),
                ("RQ2. residual error", "judge가 좋아진 뒤에도 남는 오류는 단순 noise인가, 아니면 순서 민감성과 format failure처럼 구조화되는가?"),
                ("RQ3. ensemble design", "작은 judge 여러 개를 합칠 때, 다수결보다 더 나은 decision rule이 실제로 존재하는가?"),
                ("RQ4. question reduction", "변별도 기반 subset으로 비용을 줄이면서도 모델 서열을 보존할 수 있는가?"),
            ],
            takeaway="이 뒤 절반은 phase 로그보다, 네 개의 연구 질문에 대한 답을 찾는 발표로 보는 것이 좋습니다.",
            notes="""이 슬라이드는 실험 파트 전체를 묶는 문제 정의 슬라이드입니다.
뒤쪽은 phase를 순서대로 듣기보다, 네 개의 연구 질문에 대한 답을 찾는 흐름으로 들으시면 더 자연스럽습니다.

judge scaling, residual error, ensemble rule, question reduction이라는 네 질문이
실험 파트 전체를 묶는 축이라고 생각하시면 됩니다.""",
        ),
        SlideSpec(
            title="2-4. 실험은 어떤 순서로 진행했는가",
            section="Reproduction",
            purpose="Phase 1부터 Phase 6까지의 실험 순서를 한 장에서 보여준다.",
            bullets=[
                "P1 self-judge 기준선으로 자기평가 편향을 확인하고, P2에서 외부 14B judge로 초기 sanity check를 했다.",
                "P3는 Qwen 7B/14B/32B를 이용한 메인 judge scaling 실험이고, 여기서 RQ1과 RQ2의 핵심 수치가 나온다.",
                "P3의 출력 위에서 RQ3로 ensemble decision rule을 비교하고, P4·P5는 Qwen 결과가 family가 바뀌어도 크게 무너지지 않는지 점검한다.",
                "P6는 11개 모델 풀의 repeated hold-out으로 RQ4, 즉 tinyMT-Bench subset의 운영 가능성을 same-set upper bound와 분리해 다시 본 단계다.",
            ],
            layout="timeline",
            takeaway="즉 오늘 결과는 self-judge 확인 → main scaling → ensemble / cross-family 보강 → repeated hold-out 검증의 순서로 쌓아 올린 것입니다.",
            notes="""이 슬라이드는 청중이 뒤의 결과를 phase log처럼 듣지 않도록 넣은 진행 순서 슬라이드입니다.
실험이 어떤 순서로 쌓였는지 보여주면 왜 각 phase가 필요한지가 더 잘 보입니다.

핵심은 P3의 Qwen judge scaling이고,
P4와 P5는 cross-family와 external anchor 역할을 합니다.
마지막 P6가 있어야 question reduction 결과를 same-set upper bound와 hold-out evidence로 나눠 말할 수 있습니다.""",
        ),
        SlideSpec(
            title="RQ1. Qwen judge scaling이 메인 결과다",
            section="Results",
            purpose="judge scaling이 reliability에 주는 효과를 가장 강하게 보여준다.",
            bullets=[
                "Pairwise inconsistency는 7B 78.75% → 14B 46.85% → 32B 32.86%로 단조 감소한다.",
                "Single-grade score range도 0.84 → 1.12 → 1.48로 확대되어 모델 간 변별력이 커진다.",
                "따라서 메인 결론은 ‘Qwen 기반 judge scaling의 same-family empirical trend’로 읽는 것이 맞다.",
            ],
            images=[FIG / "fig4_judge_scaling.png", FIG / "fig5_phase3_scores.png"],
            image_captions=["Judge scaling과 카테고리별 inconsistency", "Phase 3 single-grade 점수 분포"],
            stat_boxes=[("7B", "78.75%"), ("14B", "46.85%"), ("32B", "32.86%"), ("핵심", "same-family trend")],
            takeaway="RQ1의 현재 답은 예입니다. judge를 키우면 좋아집니다. 하지만 보수적으로는 same-family trend로 읽어야 합니다.",
            notes="""이 슬라이드가 실험 파트의 중심입니다.
Qwen judge를 7B에서 14B, 32B로 키우면 pairwise inconsistency가 크게 줄고,
single-grade의 score range도 넓어져 변별력이 커집니다.

다만 표현은 조심해야 합니다.
이건 universal scaling law가 아니라, Qwen 동일 family 안에서 관찰된 empirical trend입니다.""",
        ),
        SlideSpec(
            title="RQ2. judge가 좋아진 뒤에도 남는 오류는 무엇인가",
            section="Results",
            purpose="남는 오류가 단순 노이즈가 아니라 구조화된다는 점을 보여준다.",
            bullets=[
                "Qwen32, InternLM20B, GPT-4o-mini는 broad ranking은 대체로 맞지만, exact pairwise winner agreement는 0.50~0.58 수준에 머문다.",
                "특히 Qwen32의 남은 불일치 중 94.93%가 first-position win으로 연결되어, 잔여 오류가 순서 민감한 사례에 집중된다는 점이 드러난다.",
                "즉 ranking validity와 question-level decision cleanliness는 분리해서 읽어야 한다.",
            ],
            images=[FIG / "fig11_position_bias.png", FIG / "fig16_phase345_judge_summary.png"],
            image_captions=["Order-sensitive residual errors", "Cross-family and external judge summary"],
            takeaway="RQ2의 답은, judge가 좋아져도 남는 오류는 단순 noise가 아니라 순서 민감성과 운영 리스크의 형태로 남는다는 것입니다.",
            notes="""cross-family와 external judge를 보면 broad ranking은 꽤 유지됩니다.
하지만 exact pairwise agreement는 낮고,
특히 Qwen32에서는 남는 불일치가 first-position bias와 강하게 연결됩니다.

즉 큰 흐름의 ranking validity와, 질문 단위의 decision cleanliness는 다른 문제라는 뜻입니다.""",
        ),
        SlideSpec(
            title="RQ3. 왜 majority보다 abstain이 더 낫나",
            section="Results",
            purpose="기권 설계를 decision rule 차원에서 설명한다.",
            bullets=[
                "각 judge는 pairwise 한 쌍에 대해 {A, B, tie, inconsistent} 중 하나를 남긴다. inconsistent는 AB/BA swap이 충돌한 low-confidence case다.",
                "다수결은 inconsistent도 하나의 표처럼 세기 때문에 [inconsistent, inconsistent, A] 같은 경우 winner를 잃는다.",
                "abstain은 inconsistent를 기권으로 버리고, 남은 decisive vote가 충돌하지 않을 때만 winner를 선언한다.",
                "실제로 604쌍이 inconsistent→winner로 복구되고, inconsistency는 58.63%→24.70%, decisive rate는 41.37%→75.30%로 개선된다.",
            ],
            stat_boxes=[("Majority", "58.63%"), ("Abstain", "24.70%"), ("Recovered", "604쌍"), ("Decisive", "75.30%")],
            takeaway="RQ3의 답은 예입니다. 작은 judge를 다수결로 묶기보다, low-confidence vote를 기권으로 다루는 것이 훨씬 낫습니다.",
            notes="""이 슬라이드는 제가 실험 파트에서 꼭 분리해서 설명하고 싶은 부분입니다.
inconsistent를 일반 표처럼 세면 noisy judge가 aggregate를 오염시킵니다.
반대로 abstain은 그 불확실한 표를 기권으로 두고 decisive vote만 남깁니다.

그래서 더 보수적인 것처럼 보이지만 실제로는 더 많은 쌍을 더 깨끗하게 복구합니다.""",
        ),
        SlideSpec(
            title="RQ4. 문항을 줄여도 서열이 남는가",
            section="Results",
            purpose="same-set 결과와 hold-out 결과를 분리해서 question reduction을 설명한다.",
            bullets=[
                "TopDisc-40은 동일 7개 모델 집합에서 ρ=1.000, TopDisc-25는 ρ=0.964를 달성해 same-set upper bound로는 매우 강하다.",
                "Repeated hold-out 330 split에서는 40문항도 강하지만, 세 judge 모두에서 가장 안전한 운영점은 60문항이다.",
                "따라서 40문항은 공격적인 same-set 결과, 60문항은 더 안전한 hold-out 운영점으로 읽는 것이 맞다.",
            ],
            images=[FIG / "fig9_tiny_mt_bench.png", FIG / "fig15_tiny_mt_bench_generalization.png"],
            image_captions=["same-set tinyMT-Bench upper bound", "330-split repeated hold-out generalization"],
            stat_boxes=[("TopDisc-40", "ρ=1.000"), ("TopDisc-25", "ρ=0.964"), ("hold-out", "330 split"), ("safe zone", "60문항")],
            takeaway="RQ4의 답은 부분적으로 예입니다. same-set에서는 40문항이 강하지만, hold-out 기준 더 안전한 운영점은 60문항입니다.",
            notes="""question reduction은 same-set 결과만 보면 40문항이 매우 강합니다.
하지만 hold-out 반복 검증까지 보면 더 안전한 운영점은 60문항 쪽입니다.

그래서 이 결과는 ‘40문항이면 끝’이라고 과장하기보다,
same-set upper bound와 hold-out safe zone을 분리해서 말하는 것이 정직합니다.""",
        ),
        SlideSpec(
            title="내 실험 정리: 원 논문의 메시지는 어디까지 유지되는가",
            section="Wrap-up",
            purpose="실험 파트를 연구 질문 기준으로 닫는다.",
            bullets=[],
            layout="cards",
            cards=[
                ("RQ1", "judge scaling은 Qwen 동일 family 안에서는 분명한 개선 효과를 보였습니다."),
                ("RQ2", "남는 오류는 단순 noise가 아니라 순서 민감성과 format failure처럼 구조화됩니다."),
                ("RQ3", "다수결보다 abstain처럼 불확실성을 관리하는 rule이 더 낫습니다."),
                ("RQ4", "question reduction은 가능하지만 same-set upper bound와 hold-out safe zone을 분리해서 읽어야 합니다."),
            ],
            takeaway="즉 내 실험은 원 논문의 strong-judge 메시지를 완전히 부정하지 않으면서도, 오픈소스 judge 환경에서는 더 보수적인 해석과 운영 규칙이 필요함을 보여줍니다.",
            notes="""실험 파트를 한 장으로 닫는 슬라이드입니다.
judge scaling, residual error, ensemble rule, question reduction의 네 질문에 각각 어떤 답을 얻었는지를 요약했습니다.

핵심은 단순히 원 논문이 맞다 틀리다가 아니라,
원 논문의 strong-judge 메시지가 오픈소스 judge 환경에서도 부분적으로 유지되지만,
더 보수적인 해석과 운영 규칙이 필요하다는 점입니다.""",
        ),
        SlideSpec(
            title="질문 받겠습니다",
            section="Q&A",
            purpose="논문과 실험 두 파트를 모두 닫고 질문으로 자연스럽게 넘긴다.",
            bullets=[
                "질문은 크게 두 방향에서 나올 수 있습니다: 원 논문 자체의 설계와 해석, 그리고 내 실험이 그 논문을 어디까지 지지하는가.",
                "특히 토론 포인트로는 closed judge 의존성, same-family scaling 해석, residual bias와 hold-out generalization을 같이 보면 좋습니다.",
            ],
            stat_boxes=[("Paper", "benchmark"), ("Protocol", "judge design"), ("Experiment", "scaling"), ("Risk", "bias / hold-out")],
            takeaway="질문 받겠습니다.",
            notes="""이상으로 발표를 마치겠습니다.
질문은 논문 설계 자체에 대한 것이든, 제 실험이 그 논문을 어떻게 다시 읽게 만드는지에 대한 것이든 모두 좋습니다.

특히 closed judge 의존성, same-family scaling 해석,
그리고 residual bias와 hold-out question reduction을 같이 토론하면 의미가 있을 것 같습니다.""",
        ),
    ]


def build_deck():
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    slides = get_slide_specs()
    total = len(slides)
    for idx, spec in enumerate(slides, 1):
        if idx == 1:
            build_title_slide(prs, spec, total)
        elif spec.layout == "divider":
            build_divider_slide(prs, spec, idx, total)
        elif spec.layout == "overview":
            build_overview_slide(prs, spec, idx, total)
        elif spec.layout == "cards":
            build_cards_slide(prs, spec, idx, total)
        elif spec.layout == "compare":
            build_compare_slide(prs, spec, idx, total)
        elif spec.layout == "timeline":
            build_timeline_slide(prs, spec, idx, total)
        else:
            build_content_slide(prs, spec, idx, total)
    prs.save(PPTX_PATH)
    build_notes_md(slides)
    print(PPTX_PATH)
    print(NOTES_MD_PATH)


if __name__ == "__main__":
    build_deck()
