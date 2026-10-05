from __future__ import annotations

from html import escape
from pathlib import Path

from .io import read_json
from .ledger import Ledger


COLORS = {
    "evidence": "#E8F1FB", "decision": "#FFF3D6", "execution": "#E8F5E9",
    "ledger": "#F1E8FA", "paper": "#FDEBEC", "ink": "#1F2937",
}


def _text(x: float, y: float, value: str, size: int = 25, weight: str = "400", anchor: str = "middle") -> str:
    lines = value.split("\\n")
    return "".join(f'<text x="{x}" y="{y + i*31}" text-anchor="{anchor}" font-family="DejaVu Sans,Arial" font-size="{size}px" font-weight="{weight}" fill="{COLORS["ink"]}">{escape(line)}</text>' for i, line in enumerate(lines))


def _box(x: int, y: int, w: int, h: int, fill: str, label: str, stroke: str = "#334155") -> str:
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="18" fill="{fill}" stroke="{stroke}" stroke-width="3"/>' + _text(x+w/2, y+h/2-12, label, 24, "600")


def _arrow(x1: int, y1: int, x2: int, y2: int, kind: str = "solid") -> str:
    dash = "" if kind == "solid" else ('stroke-dasharray="12 10"' if kind == "dashed" else 'stroke-dasharray="3 9"')
    return f'<path d="M{x1},{y1} C{(x1+x2)//2},{y1} {(x1+x2)//2},{y2} {x2},{y2}" fill="none" stroke="#475569" stroke-width="4" {dash} marker-end="url(#arrow)"/>'


def architecture_svg() -> str:
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="1800" height="1050" viewBox="0 0 1800 1050">',
             '<defs><marker id="arrow" markerWidth="12" markerHeight="12" refX="9" refY="4" orient="auto"><path d="M0,0 L0,8 L10,4 z" fill="#475569"/></marker></defs>',
             '<rect width="1800" height="1050" fill="#FFFFFF"/>',
             _text(900, 55, "Autoresearch Lab: evidence-gated research loop", 34, "700"),
             _text(900, 92, "Architecture derived from the pinned autoresearch protocol and the implemented local runner", 20, "400"),
             _box(80, 180, 260, 120, COLORS["evidence"], "Literature evidence\\nofficial paper pages"),
             _box(410, 180, 260, 120, COLORS["decision"], "Experiment card\\nhypothesis + budget"),
             _box(740, 180, 260, 120, COLORS["decision"], "Human approval\\nhard gate"),
             _box(1070, 180, 260, 120, COLORS["execution"], "Preflight\\nGPU + hashes + scope"),
             _box(1400, 180, 300, 120, COLORS["execution"], "Run funnel\\nbaseline → pilot → full"),
             _arrow(340, 240, 410, 240), _arrow(670, 240, 740, 240), _arrow(1000, 240, 1070, 240), _arrow(1330, 240, 1400, 240),
             _box(1400, 480, 300, 120, COLORS["ledger"], "Integrity receipt\\nmetric + file hashes"),
             _box(1070, 700, 260, 120, COLORS["ledger"], "SQLite ledger\\nlogs + cost + artifacts"),
             _box(740, 700, 260, 120, COLORS["paper"], "Evidence report\\nmissing = TBD"),
             _box(410, 700, 260, 120, COLORS["evidence"], "Reviewed memory\\nnext hypothesis"),
             _arrow(1550, 300, 1550, 480), _arrow(1400, 540, 1200, 700), _arrow(1070, 760, 1000, 760), _arrow(740, 760, 670, 760),
             _arrow(540, 700, 540, 300, "dashed"), _arrow(1250, 600, 1250, 700, "dotted"),
             _text(1115, 650, "audited evidence", 18, "400"),
             _text(170, 1000, "Solid = process    Dashed = reviewed feedback    Dotted = artifact evidence binding", 18, "400", "start"),
             '</svg>']
    return "".join(parts)


def funnel_svg() -> str:
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="1800" height="1000" viewBox="0 0 1800 1000">',
             '<defs><marker id="arrow" markerWidth="12" markerHeight="12" refX="9" refY="4" orient="auto"><path d="M0,0 L0,8 L10,4 z" fill="#475569"/></marker></defs>',
             '<rect width="1800" height="1000" fill="#FFFFFF"/>',
             _text(900, 58, "Budget-aware experiment funnel and evidence boundary", 34, "700"),
             _text(900, 95, "The system spends expensive compute only after cheaper evidence passes", 20),
             _box(110, 210, 300, 150, COLORS["evidence"], "Idea pool\\nsource + prediction"),
             _box(510, 210, 300, 150, COLORS["decision"], "Smoke\\ncheap failure filter"),
             _box(910, 210, 300, 150, COLORS["execution"], "Verify\\nmultiple seeds"),
             _box(1310, 210, 300, 150, COLORS["execution"], "Full\\nfixed budget"),
             _arrow(410, 285, 510, 285), _arrow(810, 285, 910, 285), _arrow(1210, 285, 1310, 285),
             _box(910, 540, 300, 150, COLORS["ledger"], "Independent test\\nseparate from selection"),
             _box(1310, 540, 300, 150, COLORS["paper"], "Paper claim\\nonly verified numbers"),
             _arrow(1460, 360, 1060, 540, "dashed"), _arrow(1210, 615, 1310, 615),
             _text(160, 520, "Not a claim", 21, "700", "start"),
             _text(160, 555, "Hypothesis and predicted gain", 19, "400", "start"),
             _text(160, 590, "are stored before the run", 19, "400", "start"),
             _text(900, 820, "Pilot selects candidates; multi-seed and independent testing support claims.", 25, "600"),
             _text(900, 865, "A missing artifact remains TBD; the writer cannot synthesize a result.", 21, "400"),
             '</svg>']
    return "".join(parts)


def pilot_result_svg(root: str | Path) -> str | None:
    root = Path(root)
    project = read_json(root / "config" / "project.json")
    ledger = Ledger(root / project["ledger_path"])
    baseline = [r for r in ledger.runs("nanochat-rtx4060-b16") if r["status"] == "keep" and r.get("metric") is not None]
    pilot = [r for r in ledger.runs("nanochat-window-slll-b16") if r.get("metric") is not None]
    if not baseline or not pilot:
        return None
    values = [("SSSL\nbaseline", float(baseline[-1]["metric"]), "#8FB8DE"), ("SLLL\npilot", float(pilot[-1]["metric"]), "#E6A6A6")]
    width, height = 1800, 1000
    left, right, top, bottom = 180, 80, 150, 190
    chart_w, chart_h = width - left - right, height - top - bottom
    ymax = 2.0
    bars = []
    slot = chart_w / len(values)
    for index, (label, value, color) in enumerate(values):
        x = left + slot * (index + 0.5)
        bar_w = 220
        bar_h = chart_h * value / ymax
        y = top + chart_h - bar_h
        bars.append(f'<rect x="{x-bar_w/2:.1f}" y="{y:.1f}" width="{bar_w}" height="{bar_h:.1f}" fill="{color}" stroke="#334155" stroke-width="3"/>')
        bars.append(_text(x, y - 22, f"{value:.6f}", 25, "700"))
        bars.append(_text(x, height - 150, label, 24, "600"))
    grid = []
    for tick in (0.0, 0.5, 1.0, 1.5, 2.0):
        y = top + chart_h - chart_h * tick / ymax
        grid.append(f'<line x1="{left}" y1="{y:.1f}" x2="{width-right}" y2="{y:.1f}" stroke="#CBD5E1" stroke-width="2"/>')
        grid.append(_text(left - 25, y + 8, f"{tick:.1f}", 20, "400", "end"))
    return "".join([
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="1800" height="1000" fill="#FFFFFF"/>',
        _text(900, 55, "Exploratory paired pilot on RTX 4060 Laptop", 34, "700"),
        _text(900, 95, "Validation bits per byte, lower is better; one seed and no multi-seed inference", 20),
        *grid,
        f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top+chart_h}" stroke="#334155" stroke-width="4"/>',
        f'<line x1="{left}" y1="{top+chart_h}" x2="{width-right}" y2="{top+chart_h}" stroke="#334155" stroke-width="4"/>',
        *bars,
        _text(65, top + chart_h / 2, "val_bpb", 22, "600"),
        _text(900, 945, "Reference SSSL: 1.698031    |    SLLL pilot: 1.715169    |    pilot discarded", 24, "600"),
        '</svg>',
    ])


def write_figures(root: str | Path) -> list[Path]:
    target = Path(root) / "figures"
    target.mkdir(parents=True, exist_ok=True)
    outputs = [(target / "autoresearch-architecture.svg", architecture_svg()), (target / "experiment-funnel.svg", funnel_svg())]
    pilot = pilot_result_svg(root)
    if pilot is not None:
        outputs.append((target / "pilot-result.svg", pilot))
    for path, content in outputs:
        path.write_text(content, encoding="utf-8")
    return [path for path, _ in outputs]
