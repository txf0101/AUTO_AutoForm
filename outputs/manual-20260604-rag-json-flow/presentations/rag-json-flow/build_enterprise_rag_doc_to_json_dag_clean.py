from __future__ import annotations

import math
from pathlib import Path
from xml.sax.saxutils import escape

from PIL import Image, ImageDraw, ImageFont


OUT_DIR = Path(__file__).resolve().parent / "output"
OUT_DIR.mkdir(parents=True, exist_ok=True)
PNG_PATH = OUT_DIR / "enterprise_rag_doc_to_json_dag_clean.png"
SVG_PATH = OUT_DIR / "enterprise_rag_doc_to_json_dag_clean.svg"

W, H = 3840, 2160
BG = "#F7F8F4"
INK = "#1B2430"
MUTED = "#5D6875"
WHITE = "#FFFFFF"


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates: list[str] = []
    if bold:
        candidates += ["C:/Windows/Fonts/msyhbd.ttc", "C:/Windows/Fonts/simhei.ttf"]
    candidates += ["C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/simsun.ttc", "C:/Windows/Fonts/arial.ttf"]
    for item in candidates:
        if Path(item).exists():
            return ImageFont.truetype(item, size)
    return ImageFont.load_default()


F_TITLE = font(68, True)
F_SUB = font(30)
F_GROUP = font(34, True)
F_NODE = font(27, True)
F_BODY = font(21)
F_SMALL = font(18)
F_TINY = font(16)

SCHEMES = {
    "doc": ("#E6EEF4", "#4B6B88"),
    "source": ("#F3E7D4", "#B67A2A"),
    "partner": ("#E8ECF6", "#5965A0"),
    "internal": ("#EAF1E1", "#6B8142"),
    "raw": ("#DDEDEA", "#28786E"),
    "rag": ("#E7E8F2", "#626A9B"),
    "plan": ("#ECE8F1", "#725B8F"),
    "index": ("#E2F0EF", "#2D777A"),
    "eval": ("#F1E0E4", "#9B4E5F"),
    "block": ("#FFF7F7", "#C7838B"),
    "future": ("#E3EAE4", "#425D4E"),
    "plain": ("#FFFFFF", "#C8D1CC"),
}

img = Image.new("RGB", (W, H), BG)
d = ImageDraw.Draw(img)
svg_items: list[str] = []


def svg_add(item: str) -> None:
    svg_items.append(item)


def rect(x: int, y: int, w: int, h: int, fill: str, stroke: str | None = None, radius: int = 22, width: int = 2) -> None:
    d.rounded_rectangle([x, y, x + w, y + h], radius=radius, fill=fill, outline=stroke or fill, width=width)
    svg_add(
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" '
        f'fill="{fill}" stroke="{stroke or fill}" stroke-width="{width}"/>'
    )


def text(x: int, y: int, value: str, fnt: ImageFont.FreeTypeFont, fill: str = INK, center: bool = False) -> None:
    if center:
        d.text((x, y), value, font=fnt, fill=fill, anchor="mt")
        anchor = ' text-anchor="middle"'
    else:
        d.text((x, y), value, font=fnt, fill=fill)
        anchor = ""
    weight = "700" if fnt in {F_TITLE, F_GROUP, F_NODE} else "400"
    svg_add(
        f'<text x="{x}" y="{y + fnt.size}" fill="{fill}" font-family="Microsoft YaHei, Arial" '
        f'font-size="{fnt.size}" font-weight="{weight}"{anchor}>{escape(value)}</text>'
    )


def text_width(value: str, fnt: ImageFont.FreeTypeFont) -> int:
    box = d.textbbox((0, 0), value, font=fnt)
    return box[2] - box[0]


def wrap(value: str, fnt: ImageFont.FreeTypeFont, max_width: int, max_lines: int = 3) -> list[str]:
    words: list[str] = []
    for token in value.split(" "):
        if len(token) > 22 and "/" in token:
            words.extend([part for part in token.replace("/", "/ ").split(" ") if part])
        else:
            words.append(token)
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = word if not current else current + " " + word
        if text_width(candidate, fnt) <= max_width:
            current = candidate
            continue
        if current:
            lines.append(current)
        current = word
        while text_width(current, fnt) > max_width and len(current) > 8:
            cut = len(current)
            while cut > 6 and text_width(current[:cut] + "…", fnt) > max_width:
                cut -= 1
            lines.append(current[:cut] + "…")
            current = current[cut:]
        if len(lines) >= max_lines:
            break
    if current and len(lines) < max_lines:
        lines.append(current)
    return lines[:max_lines]


def bullets(x: int, y: int, values: list[str], fnt: ImageFont.FreeTypeFont, max_width: int, fill: str = INK, gap: int | None = None) -> int:
    gap = gap or int(fnt.size * 1.35)
    yy = y
    for value in values:
        for idx, line in enumerate(wrap(value, fnt, max_width, 3)):
            prefix = "• " if idx == 0 else "  "
            text(x, yy, prefix + line, fnt, fill)
            yy += gap
    return yy


def arrow(x1: int, y1: int, x2: int, y2: int, color: str = "#7F8A91", width: int = 4) -> None:
    d.line([x1, y1, x2, y2], fill=color, width=width)
    svg_add(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="{width}" stroke-linecap="round"/>')
    angle = math.atan2(y2 - y1, x2 - x1)
    size = 18
    p1 = (x2 + size * math.cos(angle + math.pi * 0.82), y2 + size * math.sin(angle + math.pi * 0.82))
    p2 = (x2 + size * math.cos(angle - math.pi * 0.82), y2 + size * math.sin(angle - math.pi * 0.82))
    pts = [(x2, y2), p1, p2]
    d.polygon(pts, fill=color)
    svg_add('<polygon points="' + " ".join(f"{int(px)},{int(py)}" for px, py in pts) + f'" fill="{color}"/>')


def bus_arrow(points: list[tuple[int, int]], color: str = "#7F8A91", width: int = 4) -> None:
    for a, b in zip(points, points[1:]):
        d.line([a[0], a[1], b[0], b[1]], fill=color, width=width)
        svg_add(f'<line x1="{a[0]}" y1="{a[1]}" x2="{b[0]}" y2="{b[1]}" stroke="{color}" stroke-width="{width}" stroke-linecap="round"/>')
    x1, y1 = points[-2]
    x2, y2 = points[-1]
    angle = math.atan2(y2 - y1, x2 - x1)
    size = 18
    p1 = (x2 + size * math.cos(angle + math.pi * 0.82), y2 + size * math.sin(angle + math.pi * 0.82))
    p2 = (x2 + size * math.cos(angle - math.pi * 0.82), y2 + size * math.sin(angle - math.pi * 0.82))
    pts = [(x2, y2), p1, p2]
    d.polygon(pts, fill=color)
    svg_add('<polygon points="' + " ".join(f"{int(px)},{int(py)}" for px, py in pts) + f'" fill="{color}"/>')


def group_box(x: int, y: int, w: int, h: int, title: str) -> None:
    rect(x, y, w, h, "#FFFFFF", "#CBD5CF", 28, 2)
    rect(x + 18, y + 18, w - 36, 52, "#E3ECE7", "#BFCBC3", 18, 2)
    text(x + 42, y + 29, title, F_GROUP, "#385D52")


def node(x: int, y: int, w: int, h: int, tag: str, title: str, subtitle: str, items: list[str], scheme: str) -> dict[str, int]:
    fill, stroke = SCHEMES[scheme]
    rect(x, y, w, h, fill, stroke, 24, 3)
    rect(x + 20, y + 20, 84, 54, stroke, stroke, 14, 2)
    text(x + 62, y + 31, tag, F_NODE, WHITE, True)
    text(x + 122, y + 24, title, F_NODE, stroke)
    text(x + 122, y + 58, subtitle, F_SMALL, MUTED)
    bullets(x + 28, y + 92, items, F_BODY, w - 56, INK, 29)
    return {"x": x, "y": y, "w": w, "h": h, "l": x, "r": x + w, "t": y, "b": y + h, "cx": x + w // 2, "cy": y + h // 2}


for x in range(180, W, 240):
    d.line([x, 220, x, H - 160], fill="#EEF1EB", width=1)
for y in range(280, H - 150, 160):
    d.line([120, y, W - 120, y], fill="#EEF1EB", width=1)

text(150, 70, "企业工艺 RAG：文档到 JSON 的分层 DAG", F_TITLE)
text(152, 152, "多入口、多门禁、多分支：公开元数据、合作企业输入、内部样本和 VC DOCX 依据并行汇入候选 RAG 资产", F_SUB, MUTED)
rect(2940, 58, 760, 126, "#EEF4F0", "#C7D6CB", 28, 3)
bullets(2980, 84, ["R13-R25：候选链路已形成", "正式索引、embedding、求解器仍关闭"], F_SMALL, 700, "#315242", 31)

group_box(110, 260, 870, 1650, "1. 输入来源")
group_box(1040, 260, 760, 1650, "2. 治理与清洗")
group_box(1860, 260, 970, 1650, "3. 候选知识与检索")
group_box(2890, 260, 840, 1650, "4. 评测、反馈与审批")

n: dict[str, dict[str, int]] = {}
n["doc"] = node(160, 360, 770, 250, "DOCX", "VC 开发文档", "只读抽取时间戳和采用结论", ["02_RAG 工艺数据库计划", "03_工艺规划 Agent 计划", "字段设计和门禁依据"], "doc")
n["public"] = node(160, 690, 770, 250, "外源", "公开元数据", "先确认访问边界", ["source_whitelist.csv", "source_review_registry.csv", "NIST / AutoForm / Crossref / arXiv"], "source")
n["partner"] = node(160, 1020, 770, 250, "企业", "合作企业输入", "metadata envelope", ["owner、agreement、confidentiality", "缓存范围、撤回机制、责任人", "P3 权限样例"], "partner")
n["internal"] = node(160, 1350, 770, 250, "内部", "内部小样本", "低风险验证和演示链", ["DC04 / D-20 / blank thickness", "R15 内部候选卡", "仍需 owner 和质量复核"], "internal")

n["review"] = node(1095, 360, 650, 245, "复核", "来源复核", "robots / terms / license", ["allowed_actions", "prohibited_actions", "rate / cache 边界"], "source")
n["manifest"] = node(1095, 695, 650, 245, "清单", "manifest 与暂存", "raw_data/manifests/*.csv", ["checksum", "retrieved_at / accessed_at", "local_file_relpath"], "raw")
n["r14"] = node(1095, 1030, 650, 245, "R14", "清洗记录 JSONL", "EnterpriseCleanedRecord", ["normalized_payload", "source_hash", "errors / quarantine"], "raw")
n["quarantine"] = node(1095, 1365, 650, 245, "隔离", "失败或阻断样本", "进入 quarantine 或 blocked report", ["license unclear", "rate limit cooling", "protected / paid content"], "block")

n["r15"] = node(1915, 390, 840, 245, "R15", "候选知识卡", "ProcessKnowledgeCard", ["*_cards.candidate.json", "applicability / evidence_refs", "formal_index_allowed=false"], "internal")
n["r16"] = node(1915, 735, 840, 245, "R16", "证据包", "EvidenceBundle", ["source_refs / card_refs", "ranking_explanation", "human_review_status=required"], "rag")
n["r17"] = node(1915, 1080, 840, 245, "R17", "工艺规划候选", "ProcessPlanCard + ContextPatch candidate", ["只给候选路线和参数", "不触发求解器", "正式写回需审批"], "plan")
n["r24"] = node(1915, 1425, 840, 245, "R24", "候选索引快照", "ProcessRagCandidateIndexSnapshot", ["37 entries", "结构过滤、关键词、证据图", "embedding_status=not_built"], "index")

n["r25"] = node(2955, 390, 710, 250, "R25", "索引评测", "ProcessRagCandidateIndexEvaluationReport", ["6/6 pass", "recall@k=1.0", "duplicate_card_id_count=0"], "eval")
n["feedback"] = node(2955, 735, 710, 250, "反馈", "复核反馈", "回补来源、清洗、卡片和查询集", ["补 terms / license", "修正字段映射", "增加误召回样例"], "source")
n["approval"] = node(2955, 1080, 710, 250, "审批", "正式索引审批门", "owner / license / security / scope", ["责任矩阵", "保密与缓存范围", "质量阈值"], "future")
n["blocked"] = node(2955, 1425, 710, 250, "阻断", "当前禁止动作", "R25 不触发执行", ["bulk_crawl / bulk_download", "auto_ingest / compute_embedding", "train_neural_index / write_formal_index", "submit_solver / control_gui"], "block")

bus_x1, bus_x2 = 980, 1040
for key in ["doc", "public", "partner", "internal"]:
    bus_arrow([(n[key]["r"], n[key]["cy"]), (bus_x1, n[key]["cy"]), (bus_x1, n["review"]["cy"]), (n["review"]["l"], n["review"]["cy"])], "#8A98A0", 3)

arrow(n["review"]["cx"], n["review"]["b"], n["manifest"]["cx"], n["manifest"]["t"], "#9C7B42", 5)
arrow(n["manifest"]["cx"], n["manifest"]["b"], n["r14"]["cx"], n["r14"]["t"], "#28786E", 5)
arrow(n["r14"]["cx"], n["r14"]["b"], n["quarantine"]["cx"], n["quarantine"]["t"], "#C7838B", 4)
bus_arrow([(n["r14"]["r"], n["r14"]["cy"]), (1810, n["r14"]["cy"]), (1810, n["r15"]["cy"]), (n["r15"]["l"], n["r15"]["cy"])], "#6B8142", 5)
arrow(n["r15"]["cx"], n["r15"]["b"], n["r16"]["cx"], n["r16"]["t"], "#626A9B", 5)
arrow(n["r16"]["cx"], n["r16"]["b"], n["r17"]["cx"], n["r17"]["t"], "#725B8F", 5)
arrow(n["r17"]["cx"], n["r17"]["b"], n["r24"]["cx"], n["r24"]["t"], "#2D777A", 5)
bus_arrow([(n["r15"]["r"], n["r15"]["cy"]), (2830, n["r15"]["cy"]), (2830, n["r25"]["cy"]), (n["r25"]["l"], n["r25"]["cy"])], "#2D777A", 4)
bus_arrow([(n["r24"]["r"], n["r24"]["cy"]), (2830, n["r24"]["cy"]), (2830, n["r25"]["cy"]), (n["r25"]["l"], n["r25"]["cy"])], "#9B4E5F", 5)
arrow(n["r25"]["cx"], n["r25"]["b"], n["feedback"]["cx"], n["feedback"]["t"], "#B67A2A", 5)
arrow(n["feedback"]["cx"], n["feedback"]["b"], n["approval"]["cx"], n["approval"]["t"], "#425D4E", 5)
arrow(n["approval"]["cx"], n["approval"]["b"], n["blocked"]["cx"], n["blocked"]["t"], "#C7838B", 4)

# Feedback bus back to governance and cards.
bus_arrow([(n["feedback"]["l"], n["feedback"]["cy"]), (2860, n["feedback"]["cy"]), (2860, 1835), (1020, 1835), (1020, n["review"]["cy"]), (n["review"]["l"], n["review"]["cy"])], "#B67A2A", 3)
bus_arrow([(n["feedback"]["l"], n["feedback"]["cy"] + 45), (2860, n["feedback"]["cy"] + 45), (2860, 1880), (1850, 1880), (1850, n["r15"]["cy"]), (n["r15"]["l"], n["r15"]["cy"])], "#B67A2A", 3)

rect(110, 1975, 1990, 90, "#FFFFFF", "#CDD6D0", 18, 2)
text(140, 1992, "展示样例：NIST PDR 制造元数据链、合作企业输入链、AutoForm 官网公开页链、内部 DC04 小样本链。", F_SMALL, MUTED)
text(140, 2024, "每条链都能回到 source_hash、evidence_refs、review_status，并保留人工复核状态。", F_SMALL, MUTED)
rect(2150, 1975, 1580, 90, "#FFF7F7", "#C7838B", 18, 2)
text(2180, 1992, "汇报口径：这是受控 DAG 和候选评测层，正式工程索引仍需审批。", F_SMALL, "#8B3D49")
text(2180, 2024, "生成日期：2026-06-04；依据 enterprise_data R13-R25 样例、白名单、复核记录和 raw_data manifest。", F_SMALL, "#8B3D49")

img.save(PNG_PATH, "PNG")
svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">
<rect width="{W}" height="{H}" fill="{BG}"/>
<style>text {{ font-family: "Microsoft YaHei", "Microsoft JhengHei", Arial, sans-serif; }}</style>
''' + "\n".join(svg_items) + "\n</svg>\n"
SVG_PATH.write_text(svg, encoding="utf-8")
print(PNG_PATH)
print(SVG_PATH)
