from __future__ import annotations

import math
from pathlib import Path
from xml.sax.saxutils import escape

from PIL import Image, ImageDraw, ImageFont


OUT_DIR = Path(__file__).resolve().parent / "output"
OUT_DIR.mkdir(parents=True, exist_ok=True)
PNG_PATH = OUT_DIR / "enterprise_rag_doc_to_json_dag.png"
SVG_PATH = OUT_DIR / "enterprise_rag_doc_to_json_dag.svg"

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
F_LANE = font(32, True)
F_NODE = font(28, True)
F_BODY = font(22)
F_SMALL = font(19)
F_TINY = font(17)

COLORS = {
    "doc": ("#E6EEF4", "#4B6B88"),
    "source": ("#F3E7D4", "#B67A2A"),
    "partner": ("#E8ECF6", "#5965A0"),
    "raw": ("#DDEDEA", "#28786E"),
    "card": ("#EAF1E1", "#6B8142"),
    "rag": ("#E7E8F2", "#626A9B"),
    "plan": ("#ECE8F1", "#725B8F"),
    "index": ("#E2F0EF", "#2D777A"),
    "eval": ("#F1E0E4", "#9B4E5F"),
    "block": ("#FFF7F7", "#C7838B"),
    "future": ("#E3EAE4", "#425D4E"),
}

img = Image.new("RGB", (W, H), BG)
d = ImageDraw.Draw(img)
svg_items: list[str] = []


def svg_add(value: str) -> None:
    svg_items.append(value)


def rect(x: int, y: int, w: int, h: int, fill: str, stroke: str | None = None, radius: int = 22, width: int = 2) -> None:
    d.rounded_rectangle([x, y, x + w, y + h], radius=radius, fill=fill, outline=stroke or fill, width=width)
    svg_add(
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" '
        f'fill="{fill}" stroke="{stroke or fill}" stroke-width="{width}"/>'
    )


def line(x1: int, y1: int, x2: int, y2: int, color: str = "#7F8A91", width: int = 4, arrow: bool = True) -> None:
    d.line([x1, y1, x2, y2], fill=color, width=width)
    svg_add(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="{width}" stroke-linecap="round"/>')
    if arrow:
        angle = math.atan2(y2 - y1, x2 - x1)
        size = 17
        p1 = (x2 + size * math.cos(angle + math.pi * 0.82), y2 + size * math.sin(angle + math.pi * 0.82))
        p2 = (x2 + size * math.cos(angle - math.pi * 0.82), y2 + size * math.sin(angle - math.pi * 0.82))
        pts = [(x2, y2), p1, p2]
        d.polygon(pts, fill=color)
        svg_add('<polygon points="' + " ".join(f"{int(px)},{int(py)}" for px, py in pts) + f'" fill="{color}"/>')


def t(x: int, y: int, value: str, fnt: ImageFont.FreeTypeFont, fill: str = INK, center: bool = False) -> None:
    if center:
        d.text((x, y), value, font=fnt, fill=fill, anchor="mt")
        anchor = ' text-anchor="middle"'
    else:
        d.text((x, y), value, font=fnt, fill=fill)
        anchor = ""
    weight = "700" if fnt in {F_TITLE, F_LANE, F_NODE} else "400"
    svg_add(
        f'<text x="{x}" y="{y + fnt.size}" fill="{fill}" font-family="Microsoft YaHei, Arial" '
        f'font-size="{fnt.size}" font-weight="{weight}"{anchor}>{escape(value)}</text>'
    )


def text_width(value: str, fnt: ImageFont.FreeTypeFont) -> int:
    box = d.textbbox((0, 0), value, font=fnt)
    return box[2] - box[0]


def wrap(value: str, fnt: ImageFont.FreeTypeFont, max_width: int, max_lines: int = 3) -> list[str]:
    tokens: list[str] = []
    for token in value.split(" "):
        if len(token) > 24 and "/" in token:
            tokens.extend([item for item in token.replace("/", "/ ").split(" ") if item])
        else:
            tokens.append(token)
    lines: list[str] = []
    current = ""
    for token in tokens:
        candidate = token if not current else current + " " + token
        if text_width(candidate, fnt) <= max_width:
            current = candidate
            continue
        if current:
            lines.append(current)
        current = token
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


def bullet_list(x: int, y: int, values: list[str], fnt: ImageFont.FreeTypeFont, width: int, color: str = INK, gap: int | None = None) -> int:
    yy = y
    gap = gap or int(fnt.size * 1.33)
    for value in values:
        for idx, part in enumerate(wrap(value, fnt, width, 3)):
            prefix = "• " if idx == 0 else "  "
            t(x, yy, prefix + part, fnt, color)
            yy += gap
    return yy


def node(key: str, x: int, y: int, w: int, h: int, title: str, subtitle: str, items: list[str], scheme: str) -> dict[str, int]:
    fill, stroke = COLORS[scheme]
    rect(x, y, w, h, fill, stroke, 26, 3)
    rect(x + 22, y + 22, 96, 58, stroke, stroke, 16, 2)
    t(x + 70, y + 33, key, F_NODE, WHITE, True)
    t(x + 136, y + 26, title, F_NODE, stroke)
    t(x + 136, y + 62, subtitle, F_SMALL, MUTED)
    bullet_list(x + 30, y + 104, items, F_BODY, w - 58, INK, 30)
    return {"x": x, "y": y, "w": w, "h": h, "cx": x + w // 2, "cy": y + h // 2, "l": x, "r": x + w, "t": y, "b": y + h}


for x in range(180, W, 240):
    d.line([x, 220, x, H - 160], fill="#EEF1EB", width=1)
for y in range(280, H - 150, 160):
    d.line([120, y, W - 120, y], fill="#EEF1EB", width=1)

t(150, 70, "企业工艺 RAG：文档到 JSON 的多入口 DAG", F_TITLE)
t(152, 152, "准确形态是分层图：资料依据、来源治理、清洗转换、候选知识、检索评测和审批后索引并行协同", F_SUB, MUTED)
rect(2970, 58, 725, 124, "#EEF4F0", "#C7D6CB", 28, 3)
bullet_list(3010, 82, ["R13-R25 已形成候选链路", "正式索引、embedding、求解器仍关闭"], F_SMALL, 660, "#315242", 32)

# Lane labels.
lanes = [
    (120, 250, 3600, 64, "A. 输入与治理层：DOCX 依据、外部来源、合作企业输入、内部样本并行进入", "#DDE7E1"),
    (120, 740, 3600, 64, "B. 转换层：manifest 与 R14 清洗把输入变成可审计 JSON 记录", "#DDE7E1"),
    (120, 1120, 3600, 64, "C. 知识与检索层：候选卡、证据包、候选索引和评测报告互相回链", "#DDE7E1"),
    (120, 1695, 3600, 64, "D. 分支与门禁层：隔离、反馈、人工复核和审批后正式索引", "#DDE7E1"),
]
for x, y, w, h, label, fill in lanes:
    rect(x, y, w, h, fill, "#BFCBC3", 18, 2)
    t(x + 28, y + 16, label, F_LANE, "#385D52")

nodes: dict[str, dict[str, int]] = {}
nodes["doc"] = node("DOCX", 170, 350, 660, 280, "需求与架构依据", "VC 开发文档，只读抽取时间戳和采用结论", ["02_RAG 工艺数据库计划", "03_工艺规划 Agent 计划", "结论进入字段设计和门禁说明"], "doc")
nodes["public"] = node("外源", 950, 350, 660, 280, "公开元数据来源", "先过 robots、terms、license、rate、cache", ["source_whitelist.csv", "source_review_registry.csv", "NIST / AutoForm / Crossref / arXiv"], "source")
nodes["partner"] = node("企业", 1730, 350, 660, 280, "合作企业输入信封", "企业侧提交前置为 metadata envelope", ["owner、agreement、confidentiality", "缓存范围、撤回机制、责任人", "P3 权限样例进入 R22"], "partner")
nodes["internal"] = node("内部", 2510, 350, 660, 280, "内部小样本与历史经验", "用于低风险验证和示例链", ["DC04 / D-20 / blank thickness", "R15 内部候选卡", "仍需 owner 与质量复核"], "card")

nodes["manifest"] = node("清单", 470, 835, 620, 260, "manifest 与原始暂存", "raw_data/manifests/*.csv", ["checksum", "retrieved_at / accessed_at", "local_file_relpath", "collection_status"], "raw")
nodes["r14"] = node("R14", 1280, 835, 620, 260, "清洗记录 JSONL", "EnterpriseCleanedRecord", ["normalized_payload", "source_hash", "errors / quarantine", "review_status"], "raw")
nodes["quarantine"] = node("隔离", 2090, 835, 620, 260, "失败或阻断样本", "许可、访问边界或清洗失败时进入隔离", ["license unclear", "rate limit cooling", "protected / paid content", "no formal ingest"], "block")
nodes["review"] = node("复核", 2900, 835, 620, 260, "人工复核记录", "source_review_registry 与 handoff", ["采用结论", "仍需验证问题", "后续门禁", "责任矩阵待补"], "source")

nodes["r15"] = node("R15", 250, 1215, 600, 310, "候选知识卡", "ProcessKnowledgeCard", ["*_cards.candidate.json", "applicability", "evidence_refs", "formal_index_allowed=false"], "card")
nodes["r16"] = node("R16", 990, 1215, 600, 310, "证据包", "EvidenceBundle", ["source_refs / card_refs", "ranking_explanation", "human_review_status=required", "blocked_actions"], "rag")
nodes["r17"] = node("R17", 1730, 1215, 600, 310, "工艺规划候选", "ProcessPlanCard + ContextPatch candidate", ["只生成候选路线、参数、仿真计划", "正式写回交给审批", "不触发求解器"], "plan")
nodes["r24"] = node("R24", 2470, 1215, 600, 310, "候选索引快照", "ProcessRagCandidateIndexSnapshot", ["37 entries", "结构化过滤、关键词、证据图", "text_hash", "embedding_status=not_built"], "index")
nodes["r25"] = node("R25", 3185, 1215, 520, 310, "索引评测", "ProcessRagCandidateIndexEvaluationReport", ["6/6 pass", "recall@k=1.0", "duplicate_card_id_count=0", "write_formal_index blocked"], "eval")

nodes["feedback"] = node("反馈", 210, 1795, 680, 250, "评测与复核反馈", "回到来源、清洗、卡片和查询集", ["补 robots/terms/license", "修正 source_hash 或字段映射", "增加误召回样例", "保留 handoff 复盘"], "source")
nodes["approval"] = node("审批", 1115, 1795, 680, 250, "正式索引审批门", "owner、license、security、scope、quality 全部通过", ["审批责任矩阵", "保密与缓存范围", "适用范围和质量阈值", "版本治理"], "future")
nodes["formal"] = node("索引", 2020, 1795, 680, 250, "审批后正式索引", "未来 pgvector / ANN / OpenSearch", ["写入 approved cards", "保留 model_version / index_version", "命中仍返回 EvidenceBundle", "当前仍未启用"], "future")
nodes["blocked"] = node("阻断", 2925, 1795, 680, 250, "当前禁止动作", "R25 报告不会触发执行", ["bulk_crawl / bulk_download", "auto_ingest / compute_embedding", "train_neural_index / write_formal_index", "submit_solver / control_gui"], "block")

# Edges from inputs to transformation layer.
line(nodes["doc"]["cx"], nodes["doc"]["b"], nodes["r15"]["cx"], nodes["r15"]["t"], "#8A98A0", 4)
line(nodes["doc"]["cx"], nodes["doc"]["b"], nodes["review"]["l"] + 60, nodes["review"]["t"], "#8A98A0", 4)
line(nodes["public"]["cx"], nodes["public"]["b"], nodes["manifest"]["cx"], nodes["manifest"]["t"], "#8A98A0", 4)
line(nodes["partner"]["cx"], nodes["partner"]["b"], nodes["r14"]["cx"], nodes["r14"]["t"], "#8A98A0", 4)
line(nodes["internal"]["cx"], nodes["internal"]["b"], nodes["r15"]["r"] - 90, nodes["r15"]["t"], "#8A98A0", 4)

# Governance and cleaning edges.
line(nodes["manifest"]["r"], nodes["manifest"]["cy"], nodes["r14"]["l"], nodes["r14"]["cy"], "#7A8C85", 5)
line(nodes["r14"]["r"], nodes["r14"]["cy"], nodes["quarantine"]["l"], nodes["quarantine"]["cy"], "#B66A72", 4)
line(nodes["quarantine"]["r"], nodes["quarantine"]["cy"], nodes["review"]["l"], nodes["review"]["cy"], "#B66A72", 4)
line(nodes["r14"]["cx"], nodes["r14"]["b"], nodes["r15"]["cx"], nodes["r15"]["t"], "#67845D", 5)
line(nodes["review"]["cx"], nodes["review"]["b"], nodes["r24"]["cx"], nodes["r24"]["t"], "#9C7B42", 4)

# Knowledge and retrieval edges.
line(nodes["r15"]["r"], nodes["r15"]["cy"], nodes["r16"]["l"], nodes["r16"]["cy"], "#6A719B", 5)
line(nodes["r16"]["r"], nodes["r16"]["cy"], nodes["r17"]["l"], nodes["r17"]["cy"], "#6A719B", 5)
line(nodes["r15"]["cx"], nodes["r15"]["b"], nodes["r24"]["l"] + 100, nodes["r24"]["t"], "#2D777A", 5)
line(nodes["r16"]["cx"], nodes["r16"]["b"], nodes["r24"]["l"] + 250, nodes["r24"]["t"], "#2D777A", 4)
line(nodes["r24"]["r"], nodes["r24"]["cy"], nodes["r25"]["l"], nodes["r25"]["cy"], "#9B4E5F", 5)

# Gate and feedback edges.
line(nodes["r25"]["cx"], nodes["r25"]["b"], nodes["feedback"]["r"] - 60, nodes["feedback"]["t"], "#B67A2A", 4)
line(nodes["r25"]["cx"], nodes["r25"]["b"], nodes["approval"]["cx"], nodes["approval"]["t"], "#425D4E", 4)
line(nodes["r25"]["cx"], nodes["r25"]["b"], nodes["blocked"]["cx"], nodes["blocked"]["t"], "#C7838B", 4)
line(nodes["approval"]["r"], nodes["approval"]["cy"], nodes["formal"]["l"], nodes["formal"]["cy"], "#425D4E", 5)
line(nodes["formal"]["r"], nodes["formal"]["cy"], nodes["blocked"]["l"], nodes["blocked"]["cy"], "#C7838B", 3, False)

# Feedback loop hints.
line(nodes["feedback"]["cx"], nodes["feedback"]["t"], nodes["r14"]["l"] + 80, nodes["r14"]["b"], "#B67A2A", 3)
line(nodes["feedback"]["cx"], nodes["feedback"]["t"], nodes["r15"]["cx"], nodes["r15"]["b"], "#B67A2A", 3)

# Legend and examples.
rect(150, 2065, 2460, 60, WHITE, "#CDD6D0", 18, 2)
t(178, 2080, "适合展示的例子：NIST PDR 制造元数据链、合作企业输入链、AutoForm 官网公开页链、内部 DC04 小样本链。每条链都能回到 source_hash、evidence_refs、review_status。", F_TINY, MUTED)
rect(2670, 2065, 1045, 60, "#FFF7F7", "#C7838B", 18, 2)
t(2698, 2080, "汇报口径：这是受控 DAG 和候选评测层，正式工程索引仍需审批。生成日期：2026-06-04", F_TINY, "#8B3D49")

img.save(PNG_PATH, "PNG")
svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">
<rect width="{W}" height="{H}" fill="{BG}"/>
<style>text {{ font-family: "Microsoft YaHei", "Microsoft JhengHei", Arial, sans-serif; }}</style>
''' + "\n".join(svg_items) + "\n</svg>\n"
SVG_PATH.write_text(svg, encoding="utf-8")
print(PNG_PATH)
print(SVG_PATH)
