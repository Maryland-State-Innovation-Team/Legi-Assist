"""Render the Legi-Assist data-flow architecture diagram.

Run:
    python docs/architecture_diagram.py

Outputs docs/architecture.png next to this file.
"""
from __future__ import annotations

import os
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch


PALETTE = {
    "source":   "#E21833",  # MD red — external source
    "runner":   "#403F3F",  # dark gray — CI runner
    "pipeline": "#F2B90C",  # MD yellow — pipeline stages
    "llm":      "#7B4E9E",  # purple — external LLM
    "storage":  "#4B7BB8",  # blue — persisted artifacts
    "frontend": "#0F8B4C",  # green — user-facing site
    "text":     "#111111",
    "text_lt":  "#FFFFFF",
    "edge":     "#555555",
}


def box(ax, x, y, w, h, label, fill, text_color="#111111", fontsize=9, bold=False):
    patch = FancyBboxPatch(
        (x, y), w, h,
        boxstyle="round,pad=0.02,rounding_size=0.15",
        linewidth=1.2,
        edgecolor="#222222",
        facecolor=fill,
        zorder=2,
    )
    ax.add_patch(patch)
    weight = "bold" if bold else "normal"
    ax.text(
        x + w / 2, y + h / 2, label,
        ha="center", va="center",
        fontsize=fontsize, color=text_color, weight=weight,
        zorder=3,
    )
    return (x, y, w, h)


def edge_point(src, side):
    x, y, w, h = src
    if side == "right":  return (x + w, y + h / 2)
    if side == "left":   return (x, y + h / 2)
    if side == "top":    return (x + w / 2, y + h)
    if side == "bottom": return (x + w / 2, y)
    raise ValueError(side)


def arrow(ax, p0, p1, label=None, curve=0.0, ls="-", color=None):
    arr = FancyArrowPatch(
        p0, p1,
        arrowstyle="-|>",
        mutation_scale=13,
        linewidth=1.4,
        color=color or PALETTE["edge"],
        linestyle=ls,
        connectionstyle=f"arc3,rad={curve}",
        zorder=1,
    )
    ax.add_patch(arr)
    if label:
        mx = (p0[0] + p1[0]) / 2
        my = (p0[1] + p1[1]) / 2
        # nudge label off the line based on curve direction
        offset = 0.25 * (1 if curve >= 0 else -1)
        ax.text(
            mx, my + offset, label,
            fontsize=7.5, color="#333333",
            ha="center", va="center",
            bbox=dict(facecolor="white", edgecolor="none", pad=1.5),
            zorder=4,
        )


def main() -> None:
    fig, ax = plt.subplots(figsize=(17, 11), dpi=160)
    ax.set_xlim(0, 34)
    ax.set_ylim(0, 22)
    ax.set_aspect("equal")
    ax.axis("off")

    ax.text(17, 21.2,
            "Legi-Assist — Data Flow Architecture",
            ha="center", fontsize=17, weight="bold", color="#111111")
    ax.text(17, 20.5,
            "Maryland General Assembly  →  nightly GitHub Actions pipeline  →  static site",
            ha="center", fontsize=10.5, color="#444444")

    # ------------------------------------------------------------------
    # LEFT COLUMN — External source (top) and CI runner (bottom)
    # ------------------------------------------------------------------
    src_group = box(ax, 0.5, 12.5, 7.5, 6.8, "", "#FBECEE")
    ax.text(4.25, 18.7, "mgaleg.maryland.gov", ha="center",
            fontsize=11.5, weight="bold", color=PALETTE["source"])

    mga_master = box(ax, 1.0, 16.7, 6.5, 1.4,
                     "Master list JSON\n/{yr}rs/misc/billsmasterlist/legislation.json",
                     PALETTE["source"], PALETTE["text_lt"], fontsize=8)
    mga_detail = box(ax, 1.0, 15.0, 6.5, 1.4,
                     "Bill detail HTML\n/mgawebsite/Legislation/Details/{bill}",
                     PALETTE["source"], PALETTE["text_lt"], fontsize=8)
    mga_pdfs = box(ax, 1.0, 12.8, 6.5, 1.9,
                   "PDFs\nbill text · adopted amendments\nfiscal & policy notes",
                   PALETTE["source"], PALETTE["text_lt"], fontsize=8.5)

    trigger = box(ax, 0.5, 8.5, 7.5, 2.4,
                  "GitHub Actions runner\n.github/workflows/daily_pipeline.yml\ncron 05:00 UTC · ThreadPoolExecutor(workers=4)",
                  PALETTE["runner"], PALETTE["text_lt"], fontsize=9.5)

    # ------------------------------------------------------------------
    # MIDDLE — Pipeline stages
    # ------------------------------------------------------------------
    pipe_group = box(ax, 10.0, 3.0, 14.0, 16.5, "", "#FFF7DA")
    ax.text(17, 18.9, "Pipeline (run_pipeline.py)", ha="center",
            fontsize=12, weight="bold", color="#7A5A00")

    stage_dl = box(ax, 10.6, 16.6, 12.8, 1.7,
                   "1. download.py — scrape detail pages,\nfetch PDFs · MD5-hash bill records for skip logic",
                   PALETTE["pipeline"], fontsize=9.5)
    stage_conv = box(ax, 10.6, 14.4, 12.8, 1.7,
                     "2. convert.py — PDF → Markdown (PyMuPDF)\ndetect strikethroughs → wrap in ~~ ~~",
                     PALETTE["pipeline"], fontsize=9.5)
    stage_amend = box(ax, 10.6, 12.2, 12.8, 1.7,
                      "3. amend.py — LLM applies each adopted\namendment sequentially → {bill}_amended.md",
                      PALETTE["pipeline"], fontsize=9.5)
    stage_qa = box(ax, 10.6, 9.5, 12.8, 2.2,
                   "4. qa.py — two LLM calls per bill\n(a) general QA (summary, dates, funding, stakeholders)\n(b) agency-relevance scoring vs. maryland_agencies.csv",
                   PALETTE["pipeline"], fontsize=9.5)
    stage_export = box(ax, 10.6, 7.3, 12.8, 1.7,
                       "5. export_frontend_data — merge legislation.json\n+ QA results → frontend_data.json",
                       PALETTE["pipeline"], fontsize=9.5)
    state = box(ax, 10.6, 4.4, 12.8, 2.4,
                "pipeline/state.py — pipeline_state.json\nper-bill hashes + needs_{download,convert,amend,qa} flags\ninputs unchanged  →  LLM call skipped",
                "#F0E4B8", fontsize=8.5)

    # ------------------------------------------------------------------
    # RIGHT COLUMN — External LLM (top) and Static Frontend (bottom)
    # ------------------------------------------------------------------
    llm = box(ax, 25.5, 13.0, 8.0, 5.0,
              "Google Gemini API\n(gemini-3-flash-preview)\n\nStructured JSON via\nresponse_schema (Pydantic)\n\nRetry w/ exp. backoff on 429",
              PALETTE["llm"], PALETTE["text_lt"], fontsize=9.5)

    fe_group = box(ax, 25.5, 3.0, 8.0, 8.0, "", "#E8F3EC")
    ax.text(29.5, 10.55, "Static Frontend (GitHub Pages)", ha="center",
            fontsize=11, weight="bold", color="#0F8B4C")

    fe_root = box(ax, 26.0, 8.4, 7.0, 1.8,
                  "index.html\nVue 3 SPA + MDWDS\nsession picker · search · favorites",
                  PALETTE["frontend"], PALETTE["text_lt"], fontsize=8.5)
    fe_wrap = box(ax, 26.0, 6.3, 7.0, 1.8,
                  "legi-assist/index.html\nMaryland.gov chrome\nembeds SPA via iframe",
                  PALETTE["frontend"], PALETTE["text_lt"], fontsize=8.5)
    fe_user = box(ax, 26.0, 3.5, 7.0, 2.4,
                  "Browser\nfetch('./data/{yr}rs/\nfrontend_data.json')",
                  "#0B6238", PALETTE["text_lt"], fontsize=9.5)

    # ------------------------------------------------------------------
    # BOTTOM — Committed artifacts (in-repo)
    # ------------------------------------------------------------------
    art_group = box(ax, 0.5, 0.4, 23.5, 2.2, "", "#E4EEF9")
    ax.text(12.25, 2.75, "Committed back to repo (git push from Actions runner)",
            ha="center", fontsize=10.5, weight="bold", color="#204D80")

    art_pdf = box(ax, 1.0, 0.7, 5.4, 1.6,
                  "data/{yr}rs/pdf/\nraw downloads",
                  PALETTE["storage"], PALETTE["text_lt"], fontsize=8.5)
    art_md = box(ax, 6.7, 0.7, 5.4, 1.6,
                 "data/{yr}rs/md/\nbill · fn · amd · amended",
                 PALETTE["storage"], PALETTE["text_lt"], fontsize=8.5)
    art_state = box(ax, 12.4, 0.7, 5.4, 1.6,
                    "pipeline_state.json\nhashes + QA cache",
                    PALETTE["storage"], PALETTE["text_lt"], fontsize=8.5)
    art_fe = box(ax, 18.1, 0.7, 5.4, 1.6,
                 "frontend_data.json\nlegislation.json",
                 PALETTE["storage"], PALETTE["text_lt"], fontsize=8.5)

    # ------------------------------------------------------------------
    # ARROWS
    # ------------------------------------------------------------------
    # Runner → MGA (fetch)
    arrow(ax, edge_point(trigger, "top"), edge_point(mga_pdfs, "bottom"),
          "HTTPS")
    # MGA → download stage
    arrow(ax, edge_point(mga_master, "right"), edge_point(stage_dl, "left"),
          "master list", curve=0.05)
    arrow(ax, edge_point(mga_detail, "right"), edge_point(stage_dl, "left"),
          "scrape", curve=-0.05)
    arrow(ax, edge_point(mga_pdfs, "right"), (10.6, 17.0),
          "PDFs", curve=-0.1)

    # Pipeline stage chain
    arrow(ax, edge_point(stage_dl, "bottom"), edge_point(stage_conv, "top"))
    arrow(ax, edge_point(stage_conv, "bottom"), edge_point(stage_amend, "top"))
    arrow(ax, edge_point(stage_amend, "bottom"), edge_point(stage_qa, "top"))
    arrow(ax, edge_point(stage_qa, "bottom"), edge_point(stage_export, "top"))

    # LLM round-trips
    arrow(ax, edge_point(stage_amend, "right"), (25.5, 14.6),
          "apply amdt", curve=0.1)
    arrow(ax, (25.5, 15.3), (23.4, 13.4),
          "amended md", curve=0.1, ls="--")
    arrow(ax, edge_point(stage_qa, "right"), (25.5, 16.0),
          "bill + FN + agencies", curve=-0.1)
    arrow(ax, (25.5, 16.8), (23.4, 10.6),
          "structured JSON", curve=-0.1, ls="--")

    # State manager (dotted gates)
    arrow(ax, (11.5, edge_point(state, "top")[1]),
          (11.5, edge_point(stage_export, "bottom")[1]),
          "gates every stage", curve=0.0, ls=":")

    # Stages → committed artifacts
    arrow(ax, edge_point(stage_dl, "left"), edge_point(art_pdf, "top"),
          curve=-0.3)
    arrow(ax, (edge_point(stage_conv, "left")[0], 14.9),
          edge_point(art_md, "top"), curve=-0.25)
    arrow(ax, edge_point(state, "bottom"), edge_point(art_state, "top"),
          curve=0.15)
    arrow(ax, edge_point(stage_export, "bottom"), edge_point(art_fe, "top"),
          curve=0.15)

    # Frontend data → static site
    arrow(ax, edge_point(art_fe, "right"), edge_point(fe_root, "bottom"),
          "git push → Pages", curve=0.15)
    arrow(ax, edge_point(fe_root, "bottom"), edge_point(fe_wrap, "top"),
          "iframe")
    arrow(ax, edge_point(fe_wrap, "bottom"), edge_point(fe_user, "top"))

    # ------------------------------------------------------------------
    # LEGEND — top-right corner, clear of everything
    # ------------------------------------------------------------------
    lx, ly = 25.5, 19.0
    box(ax, lx, ly, 8.0, 2.2, "", "#FFFFFF")
    ax.text(lx + 0.3, ly + 1.85, "Legend",
            fontsize=9.5, weight="bold", ha="left", va="center")

    legend_items = [
        ("External source",  PALETTE["source"]),
        ("CI runner",        PALETTE["runner"]),
        ("Pipeline stage",   PALETTE["pipeline"]),
        ("External LLM",     PALETTE["llm"]),
        ("Committed data",   PALETTE["storage"]),
        ("Static frontend",  PALETTE["frontend"]),
    ]
    for i, (name, color) in enumerate(legend_items):
        col = i % 2
        row = i // 2
        cx = lx + 0.3 + col * 4.0
        cy = ly + 1.35 - row * 0.45
        ax.add_patch(FancyBboxPatch(
            (cx, cy - 0.15), 0.35, 0.3,
            boxstyle="round,pad=0.0,rounding_size=0.05",
            facecolor=color, edgecolor="#222",
        ))
        ax.text(cx + 0.5, cy, name, fontsize=8, va="center")

    ax.text(lx + 0.3, ly + 0.15,
            "solid = data flow · dashed = LLM response · dotted = state gate",
            fontsize=7.5, color="#555", style="italic")

    out_path = os.path.join(os.path.dirname(__file__), "architecture.png")
    plt.tight_layout()
    plt.savefig(out_path, dpi=160, bbox_inches="tight", facecolor="white")
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
