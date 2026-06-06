from __future__ import annotations

import math
from pathlib import Path
from xml.sax.saxutils import escape

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[4]
OUT_DIR = Path(__file__).resolve().parent / "output"
OUT_DIR.mkdir(parents=True, exist_ok=True)
PNG_PATH = OUT_DIR / "enterprise_rag_doc_to_json_flow.png"
SVG_PATH = OUT_DIR / "enterprise_rag_doc_to_json_flow.svg"

W, H = 3840, 2160
BG = "#F7F8F4"
INK = "#1B2430"
MUTED = "#5D6875"
WHITE = "#FFFFFF"

COLORS = {
    "doc": "#4B6B88",
    "gate": "#B67A2A",
    "json": "#28786E",
    "card": "#6B8142",
    "rag": "#626A9B",
    "plan": "#725B8F",
    "eval": "#9B4E5F",
    "future": "#425D4E",
    "soft_doc": "#E6EEF4",
    "soft_gate": "#F3E7D4",
    "soft_json": "#DDEDEA",
    "soft_card": "#EAF1E1",
    "soft_rag": "#E7E8F2",
    "soft_plan": "#ECE8F1",
    "soft_eval": "#F1E0E4",
    "soft_future": "#E3EAE4",
}


def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates: list[str] = []
    if bold:
        candidates += ["C:/Windows/Fonts/msyhbd.ttc", "C:/Windows/Fonts/simhei.ttf"]
    candidates += ["C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/simsun.ttc", "C:/Windows/Fonts/arial.ttf"]
    for item in candidates:
        if Path(item).exists():
            return ImageFont.truetype(item, size)
    return ImageFont.load_default()


F_TITLE = load_font(68, True)
F_SUB = load_font(31)
F_SECTION = load_font(34, True)
F_CARD_TITLE = load_font(31, True)
F_BODY = load_font(24)
F_SMALL = load_font(21)
F_TINY = load_font(18)

img = Image.new("RGB", (W, H), BG)
d = ImageDraw.Draw(img)
svg_items: list[str] = []


def svg_add(item: str) -> None:
    svg_items.append(item)


def draw_rect(x: int, y: int, w: int, h: int, fill: str, stroke: str | None = None, radius: int = 20, width: int = 2) -> None:
    d.rounded_rectangle([x, y, x + w, y + h], radius=radius, fill=fill, outline=stroke or fill, width=width)
    svg_add(
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" '
        f'fill="{fill}" stroke="{stroke or fill}" stroke-width="{width}"/>'
    )


def draw_line(x1: int, y1: int, x2: int, y2: int, fill: str, width: int = 4, arrow: bool = False) -> None:
    d.line([x1, y1, x2, y2], fill=fill, width=width)
    svg_add(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{fill}" stroke-width="{width}" stroke-linecap="round"/>')
    if arrow:
        angle = math.atan2(y2 - y1, x2 - x1)
        size = 18
        p1 = (x2 + size * math.cos(angle + math.pi * 0.82), y2 + size * math.sin(angle + math.pi * 0.82))
        p2 = (x2 + size * math.cos(angle - math.pi * 0.82), y2 + size * math.sin(angle - math.pi * 0.82))
        poly = [(x2, y2), p1, p2]
        d.polygon(poly, fill=fill)
        svg_add('<polygon points="' + " ".join(f"{int(px)},{int(py)}" for px, py in poly) + f'" fill="{fill}"/>')


def text_width(value: str, font: ImageFont.FreeTypeFont) -> int:
    box = d.textbbox((0, 0), value, font=font)
    return box[2] - box[0]


def draw_text(x: int, y: int, value: str, font: ImageFont.FreeTypeFont, fill: str = INK, center: bool = False) -> None:
    if center:
        d.text((x, y), value, font=font, fill=fill, anchor="mt")
        svg_anchor = ' text-anchor="middle"'
    else:
        d.text((x, y), value, font=font, fill=fill)
        svg_anchor = ""
    weight = "700" if font in {F_TITLE, F_SECTION, F_CARD_TITLE} else "400"
    svg_add(
        f'<text x="{x}" y="{y + font.size}" fill="{fill}" font-family="Microsoft YaHei, Arial" '
        f'font-size="{font.size}" font-weight="{weight}"{svg_anchor}>{escape(value)}</text>'
    )


def wrap(value: str, font: ImageFont.FreeTypeFont, max_width: int, max_lines: int = 4) -> list[str]:
    words: list[str] = []
    for token in value.split(" "):
        if len(token) > 24 and "/" in token:
            words.extend([part for part in token.replace("/", "/ ").split(" ") if part])
        else:
            words.append(token)
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = word if not current else current + " " + word
        if text_width(candidate, font) <= max_width:
            current = candidate
            continue
        if current:
            lines.append(current)
        current = word
        while text_width(current, font) > max_width and len(current) > 8:
            cut = len(current)
            while cut > 6 and text_width(current[:cut] + "…", font) > max_width:
                cut -= 1
            lines.append(current[:cut] + "…")
            current = current[cut:]
        if len(lines) >= max_lines:
            break
    if current and len(lines) < max_lines:
        lines.append(current)
    return lines[:max_lines]


def draw_list(x: int, y: int, items: list[str], font: ImageFont.FreeTypeFont, fill: str = INK, max_width: int = 500, line_gap: int | None = None) -> int:
    yy = y
    line_gap = line_gap or int(font.size * 1.35)
    for item in items:
        lines = wrap(item, font, max_width, 3)
        for idx, line in enumerate(lines):
            prefix = "• " if idx == 0 else "  "
            draw_text(x, yy, prefix + line, font, fill)
            yy += line_gap
    return yy


for x in range(180, W, 240):
    d.line([x, 220, x, H - 190], fill="#EEF1EB", width=1)
for y in range(260, H - 180, 160):
    d.line([120, y, W - 120, y], fill="#EEF1EB", width=1)

draw_text(150, 70, "企业工艺 RAG：文档到 JSON 的受控转换链", F_TITLE)
draw_text(152, 152, "DOCX 依据、公开元数据和合作企业输入逐步沉淀为可审计 JSON；每一步保留来源、hash、权限和人工复核门禁", F_SUB, MUTED)
draw_rect(2920, 64, 770, 116, "#EEF4F0", "#C7D6CB", 28, 3)
draw_list(2960, 86, ["当前阶段：R13 至 R25", "状态：候选检索与评测，正式索引关闭"], F_SMALL, "#315242", 700, 33)

top_bands = [
    (
        150,
        250,
        1080,
        210,
        "输入依据：VC 开发 DOCX",
        COLORS["soft_doc"],
        COLORS["doc"],
        ["02_RAG工艺数据库详细架构计划与任务目标.docx", "03_工艺规划Agent详细架构计划与任务目标.docx", "采用结论：候选产物、EvidenceBundle、ContextPatch 门禁"],
    ),
    (
        1380,
        250,
        1080,
        210,
        "受控外部来源",
        COLORS["soft_gate"],
        COLORS["gate"],
        ["source_whitelist.csv / source_review_registry.csv", "robots、terms、license、rate、cache 边界", "NIST、AutoForm 官网、Crossref、arXiv 元数据"],
    ),
    (
        2610,
        250,
        1080,
        210,
        "合作企业输入接口",
        "#E8ECF6",
        "#5965A0",
        ["r22_partner_submission_metadata_samples.jsonl", "提交信封包含 owner、confidentiality、agreement", "撤回、缓存范围、正式索引均需人工复核"],
    ),
]

for x, y, w, h, title, fill, stroke, items in top_bands:
    draw_rect(x, y, w, h, fill, stroke, 28, 3)
    draw_text(x + 34, y + 26, title, F_SECTION, stroke)
    draw_list(x + 36, y + 82, items, F_SMALL, max_width=w - 70, line_gap=31)

cards = [
    ("R13", "来源契约", COLORS["soft_gate"], COLORS["gate"], ["source_whitelist.csv", "source_review_registry.csv", "allowed_actions / prohibited_actions", "来源进入目录登记"]),
    ("R14", "采集清洗", COLORS["soft_json"], COLORS["json"], ["raw_data/manifests/*.csv", "metadata_samples.jsonl", "checksum / retrieved_at / source_hash", "EnterpriseCleanedRecord"]),
    ("R15", "知识卡", COLORS["soft_card"], COLORS["card"], ["*_cards.candidate.json", "ProcessKnowledgeCard", "applicability / evidence_refs", "formal_index_allowed=false"]),
    ("R16", "证据包", COLORS["soft_rag"], COLORS["rag"], ["*_evidence_bundle.sample.json", "EvidenceBundle", "source_refs / card_refs / ranking", "human_review_status=required"]),
    ("R17", "工艺候选", COLORS["soft_plan"], COLORS["plan"], ["r17_enterprise_process_plan_candidate.sample.json", "ProcessPlanCard + ContextPatch candidate", "只给候选路线和参数", "不触发求解器"]),
    ("R24", "候选索引", "#E2F0EF", "#2D777A", ["r24_process_rag_candidate_index.sample.json", "37 entries；结构过滤、关键词、证据图", "text_hash 保留", "embedding_status=not_built"]),
    ("R25", "评测门禁", COLORS["soft_eval"], COLORS["eval"], ["r25_process_rag_index_eval_report.sample.json", "6/6 pass；recall@k=1.0", "duplicate_card_id_count=0", "write_formal_index blocked"]),
    ("审批后", "正式索引", COLORS["soft_future"], COLORS["future"], ["owner、license、security、scope 通过", "再进入 pgvector / ANN 方案", "命中仍返回 EvidenceBundle", "当前仍为未来门禁"]),
]

start_x, y0, cw, ch, gap = 150, 560, 405, 500, 45
for idx, (stage, title, fill, stroke, items) in enumerate(cards):
    x = start_x + idx * (cw + gap)
    draw_rect(x, y0, cw, ch, fill, stroke, 30, 4)
    draw_rect(x + 22, y0 + 24, 122, 86, stroke, stroke, 18, 2)
    draw_text(x + 83, y0 + 33, stage, F_CARD_TITLE, WHITE, center=True)
    draw_text(x + 83, y0 + 70, title, F_SMALL, WHITE, center=True)
    draw_text(x + 160, y0 + 35, "JSON 产物", F_SMALL, stroke)
    d.line([x + 160, y0 + 72, x + cw - 28, y0 + 72], fill=stroke, width=3)
    draw_list(x + 32, y0 + 128, items, F_BODY, max_width=cw - 60, line_gap=35)
    if idx < len(cards) - 1:
        draw_line(x + cw + 5, y0 + ch // 2, start_x + (idx + 1) * (cw + gap) - 10, y0 + ch // 2, "#7F8A91", 5, True)

rail_y = 1135
draw_rect(150, rail_y, 3540, 290, WHITE, "#C8D1CC", 28, 3)
draw_text(190, rail_y + 30, "证据链字段贯穿全流程", F_SECTION, "#385D52")
draw_text(190, rail_y + 82, "这些字段支撑汇报时的可追溯和可复核：原始响应、清洗记录、知识卡、证据包、候选索引和评测报告可以逐级回链。", F_SUB, MUTED)
chips = [
    ("checksum", "原始响应 SHA256"),
    ("retrieved_at / accessed_at", "采集或访问时间"),
    ("source_hash", "normalized_payload SHA256"),
    ("evidence_refs", "证据引用和 artifact_uri"),
    ("text_hash", "候选索引文本指纹"),
    ("review_status", "candidate / needs_license_review"),
]
chip_x = 195
for key, desc in chips:
    width = 520 if len(key) > 16 else 420
    draw_rect(chip_x, rail_y + 160, width, 82, "#EEF5F2", "#8FA69A", 18, 2)
    draw_text(chip_x + 24, rail_y + 172, key, F_BODY, "#254A42")
    draw_text(chip_x + 24, rail_y + 205, desc, F_TINY, MUTED)
    chip_x += width + 30

ex_y = 1490
draw_rect(150, ex_y, 2180, 470, "#FFFDF8", "#D8C69B", 28, 3)
draw_text(190, ex_y + 30, "推荐拿来讲的 4 条样例文件链", F_SECTION, "#835D1E")
examples = [
    ("NIST PDR 制造元数据", ["manifest CSV", "r23_*_metadata_samples.jsonl", "r23_*_cards.candidate.json", "R25 cost guide 命中"]),
    ("合作企业输入", ["r22_partner_submission_metadata_samples.jsonl", "r22_partner_submission_cards.candidate.json", "权限过滤失败样例"]),
    ("AutoForm 官网公开页", ["r21_autoform_public_site_metadata_samples.jsonl", "r21_autoform_public_site_cards.candidate.json", "BiW process-chain 命中"]),
    ("内部 DC04 小样本", ["r15_process_knowledge_cards.sample.json", "r16_process_rag_evidence_bundle.sample.json", "blank thickness 命中"]),
]
ex_w, ex_gap = 495, 30
for idx, (name, items) in enumerate(examples):
    x = 195 + idx * (ex_w + ex_gap)
    draw_rect(x, ex_y + 105, ex_w, 310, WHITE, "#E1D5B7", 22, 2)
    draw_text(x + 24, ex_y + 130, name, F_CARD_TITLE, "#694A16")
    draw_list(x + 26, ex_y + 188, items, F_SMALL, max_width=ex_w - 52, line_gap=30)

draw_rect(2390, ex_y, 1300, 470, "#FFF7F7", "#C7838B", 28, 3)
draw_text(2430, ex_y + 30, "当前仍阻断的动作", F_SECTION, "#8B3D49")
blocked = [
    "bulk_crawl",
    "bulk_download",
    "auto_ingest",
    "compute_embedding",
    "train_neural_index",
    "write_formal_index",
    "write_formal_engineering_state",
    "submit_solver / control_gui",
]
draw_list(2445, ex_y + 105, blocked[:4], F_BODY, max_width=560, line_gap=38)
draw_list(3025, ex_y + 105, blocked[4:], F_BODY, max_width=590, line_gap=38)
draw_text(2430, ex_y + 390, "汇报口径：当前做的是受控小样本和候选索引评测，正式工程索引需审批后进入。", F_SMALL, "#8B3D49")

draw_text(150, 2050, "依据：VC 开发 DOCX 时间戳 2026-06-01 至 2026-06-02；enterprise_data R13-R25 样例文件；source_whitelist / source_review_registry；raw_data manifest。", F_TINY, MUTED)
draw_text(3320, 2050, "生成日期：2026-06-04", F_TINY, MUTED)

img.save(PNG_PATH, "PNG")
svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">
<rect width="{W}" height="{H}" fill="{BG}"/>
<style>text {{ font-family: "Microsoft YaHei", "Microsoft JhengHei", Arial, sans-serif; }}</style>
''' + "\n".join(svg_items) + "\n</svg>\n"
SVG_PATH.write_text(svg, encoding="utf-8")
print(PNG_PATH)
print(SVG_PATH)
