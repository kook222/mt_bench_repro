#!/usr/bin/env python3
"""
Generate KCI-style paper figures and copy-ready result tables.

The repository includes raw judge JSONL files, but this paper figure script uses
the committed aggregate CSVs so the manuscript figures remain compact and stable.
Raw judgments can be used to audit or recompute the aggregate statistics.

Usage:
    python3 scripts/tools/generate_figures.py
"""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import FancyBboxPatch


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "figures" / "paper"
OUT.mkdir(parents=True, exist_ok=True)

SCORE_FILES = {
    ("EN", "Qwen-7B"): ROOT / "data/en/results/results_phase3_judge_7B.csv",
    ("EN", "Qwen-14B"): ROOT / "data/en/results/results_phase3_judge_14B.csv",
    ("EN", "Qwen-32B"): ROOT / "data/en/results/results_phase3_judge_32B.csv",
    ("EN", "EXAONE-32B"): ROOT / "data/en/results/results_phase3_judge_exaone32B.csv",
    ("EN", "GPT-4o-mini"): ROOT / "data/en/results/results_en_judge_gpt4omini.csv",
    ("KO", "Qwen-7B"): ROOT / "data/ko/results/results_ko_judge_7B.csv",
    ("KO", "Qwen-14B"): ROOT / "data/ko/results/results_ko_judge_14B.csv",
    ("KO", "Qwen-32B"): ROOT / "data/ko/results/results_ko_judge_32B.csv",
    ("KO", "EXAONE-32B"): ROOT / "data/ko/results/results_ko_judge_exaone32B.csv",
    ("KO", "GPT-4o-mini"): ROOT / "data/ko/results/results_ko_judge_gpt4omini.csv",
}

REF_FILES = {
    ("EN", "Qwen-7B"): ROOT / "data/en/results/results_phase3_judge_7B_reference.csv",
    ("EN", "Qwen-14B"): ROOT / "data/en/results/results_phase3_judge_14B_reference.csv",
    ("EN", "Qwen-32B"): ROOT / "data/en/results/results_phase3_judge_32B_reference.csv",
    ("EN", "EXAONE-32B"): ROOT / "data/en/results/results_phase3_judge_exaone32B_reference.csv",
    ("EN", "GPT-4o-mini"): ROOT / "data/en/results/results_en_judge_gpt4omini_ref.csv",
    ("KO", "Qwen-7B"): ROOT / "data/ko/results/results_ko_judge_7B_reference.csv",
    ("KO", "Qwen-14B"): ROOT / "data/ko/results/results_ko_judge_14B_reference.csv",
    ("KO", "Qwen-32B"): ROOT / "data/ko/results/results_ko_judge_32B_reference.csv",
    ("KO", "EXAONE-32B"): ROOT / "data/ko/results/results_ko_judge_exaone32B_reference.csv",
    ("KO", "GPT-4o-mini"): ROOT / "data/ko/results/results_ko_judge_gpt4omini_ref.csv",
}

MODEL_LABELS = {
    "EXAONE-3.5-7.8B-Instruct": "EXAONE-7.8B",
    "EEVE-Korean-Instruct-10.8B": "EEVE-10.8B",
    "gemma-2-9b-it": "Gemma-9B",
    "Llama-3.1-8B-Instruct": "Llama-8B",
    "Mistral-7B-Instruct-v0.3": "Mistral-7B",
    "Phi-3.5-mini-Instruct": "Phi-3.5",
}

JUDGE_LABELS = {
    "qwen_7B": "Qwen-7B",
    "qwen_14B": "Qwen-14B",
    "qwen_32B": "Qwen-32B",
    "exaone_32B": "EXAONE-32B",
    "gpt4omini": "GPT-4o-mini",
}

MONO = {
    "black": "#111111",
    "dark": "#333333",
    "mid": "#777777",
    "light": "#D9D9D9",
    "pale": "#F3F3F3",
    "accent": "#555555",
}


def setup_style() -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Serif",
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.edgecolor": MONO["black"],
            "axes.linewidth": 0.8,
            "axes.grid": False,
            "figure.dpi": 140,
            "savefig.dpi": 300,
            "savefig.bbox": "tight",
            "savefig.facecolor": "white",
            "font.size": 8.5,
            "axes.titlesize": 9.5,
            "axes.labelsize": 9,
            "xtick.labelsize": 7.8,
            "ytick.labelsize": 7.8,
            "legend.fontsize": 8,
        }
    )


def read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path)


def p_label(p_value: float) -> str:
    if p_value < 0.001:
        return "p<.001"
    if p_value < 0.01:
        return "p<.01"
    if p_value < 0.05:
        return "p<.05"
    return f"p={p_value:.3f}"


def save(fig: plt.Figure, stem: str) -> None:
    png = OUT / f"{stem}.png"
    pdf = OUT / f"{stem}.pdf"
    fig.savefig(png)
    fig.savefig(pdf)
    plt.close(fig)
    print(f"saved {png.relative_to(ROOT)}")
    print(f"saved {pdf.relative_to(ROOT)}")


def add_panel_label(ax: plt.Axes, label: str) -> None:
    ax.text(
        -0.08,
        1.05,
        label,
        transform=ax.transAxes,
        ha="left",
        va="bottom",
        fontsize=10,
        fontweight="bold",
    )


def fig1_protocol() -> None:
    fig, ax = plt.subplots(figsize=(7.2, 3.4))
    ax.set_axis_off()

    boxes = [
        (0.03, 0.58, 0.18, 0.24, "MT-Bench\n80 EN items"),
        (0.29, 0.58, 0.18, 0.24, "Manual KO\ntranslation"),
        (0.55, 0.58, 0.18, 0.24, "6 evaluated\nLLMs"),
        (0.79, 0.58, 0.18, 0.24, "EN/KO\nanswers"),
        (0.29, 0.16, 0.18, 0.24, "Back-translation\nvalidity check"),
        (0.55, 0.16, 0.18, 0.24, "5 judge settings\nQwen/EXAONE/GPT"),
        (0.79, 0.16, 0.18, 0.24, "Score gap,\ninconsistency,\nparse failure"),
    ]

    for x, y, w, h, text in boxes:
        patch = FancyBboxPatch(
            (x, y),
            w,
            h,
            boxstyle="round,pad=0.012,rounding_size=0.012",
            facecolor=MONO["pale"],
            edgecolor=MONO["black"],
            linewidth=0.9,
        )
        ax.add_patch(patch)
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=8.5)

    arrows = [
        ((0.21, 0.70), (0.29, 0.70)),
        ((0.47, 0.70), (0.55, 0.70)),
        ((0.73, 0.70), (0.79, 0.70)),
        ((0.38, 0.58), (0.38, 0.40)),
        ((0.64, 0.58), (0.64, 0.40)),
        ((0.73, 0.28), (0.79, 0.28)),
    ]
    for start, end in arrows:
        ax.annotate(
            "",
            xy=end,
            xytext=start,
            arrowprops=dict(arrowstyle="->", color=MONO["black"], lw=0.9),
        )

    ax.text(
        0.03,
        0.93,
        "Experimental protocol for Korean MT-Bench reliability analysis",
        fontsize=9.5,
        fontweight="bold",
    )
    ax.text(
        0.03,
        0.04,
        "Note. Raw pairwise, single-grade, and reference-guided judgments are included for audit and recomputation.",
        fontsize=7.5,
        color=MONO["dark"],
    )
    save(fig, "fig1_protocol")


def qwen32_gap_frame() -> pd.DataFrame:
    en = read_csv(SCORE_FILES[("EN", "Qwen-32B")])
    ko = read_csv(SCORE_FILES[("KO", "Qwen-32B")])
    stat = read_csv(ROOT / "data/ko/results/results_stat_en_ko_diff.csv")
    stat = stat[stat["judge"] == "Qwen-32B"].set_index("model")

    df = en[["model", "overall", "n_samples"]].merge(
        ko[["model", "overall", "n_samples"]], on="model", suffixes=("_en", "_ko")
    )
    df["gap"] = df["overall_ko"] - df["overall_en"]
    df["paired_diff"] = df["model"].map(stat["mean_diff"])
    df["p_value"] = df["model"].map(stat["p_value"])
    df["label"] = df["model"].map(MODEL_LABELS)
    return df.sort_values("gap")


def fig2_score_gap() -> None:
    df = qwen32_gap_frame()
    y = np.arange(len(df))

    fig, ax = plt.subplots(figsize=(6.8, 3.9))
    ax.hlines(y, df["overall_ko"], df["overall_en"], color=MONO["light"], lw=2.4, zorder=1)
    ax.plot(df["overall_en"], y, "o", ms=5.5, mfc="white", mec=MONO["black"], label="EN", zorder=3)
    ax.plot(df["overall_ko"], y, "s", ms=5.2, mfc=MONO["black"], mec=MONO["black"], label="KO", zorder=3)

    for idx, row in enumerate(df.itertuples(index=False)):
        ax.text(
            min(row.overall_en, row.overall_ko) - 0.07,
            idx,
            f"{row.gap:+.2f}",
            ha="right",
            va="center",
            fontsize=8,
        )
        ax.text(
            max(row.overall_en, row.overall_ko) + 0.08,
            idx,
            p_label(row.p_value),
            ha="left",
            va="center",
            fontsize=7.6,
            color=MONO["dark"],
        )

    ax.set_yticks(y)
    ax.set_yticklabels(df["label"])
    ax.set_xlabel("MT-Bench score (1-10)")
    ax.set_xlim(4.2, 8.9)
    ax.set_title("Qwen-32B single-grade score: English vs. Korean")
    ax.grid(axis="x", color="#E6E6E6", lw=0.6)
    ax.text(
        0.0,
        -0.20,
        "Open circle=EN, filled square=KO. Left annotations show KO-EN gaps; right annotations show paired permutation-test results.",
        transform=ax.transAxes,
        fontsize=7.2,
        color=MONO["dark"],
    )
    save(fig, "fig2_score_gap_qwen32")


def fig3_reliability_bias() -> None:
    comp = read_csv(ROOT / "data/ko/results/results_en_ko_comparison.csv")
    comp["judge_label"] = comp["judge"].map(JUDGE_LABELS)
    comp["en_fp_in_incon"] = comp["en_fp_pct"] / comp["en_incon_pct"] * 100
    comp["ko_fp_in_incon"] = comp["ko_fp_pct"] / comp["ko_incon_pct"] * 100

    x = np.arange(len(comp))
    fig, axes = plt.subplots(1, 2, figsize=(7.4, 3.2), sharex=True)

    ax = axes[0]
    ax.plot(x, comp["en_incon_pct"], "-o", color=MONO["black"], mfc="white", ms=4.5, label="EN")
    ax.plot(x, comp["ko_incon_pct"], "--s", color=MONO["dark"], mfc=MONO["dark"], ms=4.2, label="KO")
    ax.set_ylabel("Inconsistency (%)")
    ax.set_ylim(0, 85)
    ax.set_title("AB/BA inconsistency")
    ax.grid(axis="y", color="#E6E6E6", lw=0.6)
    ax.legend(frameon=False, loc="upper right")
    add_panel_label(ax, "(a)")

    ax = axes[1]
    ax.plot(x, comp["en_fp_in_incon"], "-o", color=MONO["black"], mfc="white", ms=4.5, label="EN")
    ax.plot(x, comp["ko_fp_in_incon"], "--s", color=MONO["dark"], mfc=MONO["dark"], ms=4.2, label="KO")
    ax.axhline(50, color=MONO["mid"], ls=":", lw=1)
    ax.set_ylabel("First-position share (%)")
    ax.set_ylim(0, 105)
    ax.set_title("Among inconsistent pairs")
    ax.grid(axis="y", color="#E6E6E6", lw=0.6)
    add_panel_label(ax, "(b)")

    for ax in axes:
        ax.set_xticks(x)
        ax.set_xticklabels(comp["judge_label"], rotation=35, ha="right")

    fig.text(
        0.5,
        -0.05,
        "Note. First-position share is computed within inconsistent pairs, not over all pairs.",
        ha="center",
        fontsize=7.2,
        color=MONO["dark"],
    )
    fig.tight_layout()
    save(fig, "fig3_reliability_bias")


def collect_parse_coverage() -> pd.DataFrame:
    rows = []
    for (lang, judge), path in SCORE_FILES.items():
        df = read_csv(path)
        for row in df.itertuples(index=False):
            expected = float(row.expected_count) * 2
            rows.append(
                {
                    "lang": lang,
                    "judge": judge,
                    "type": "single",
                    "model": row.model,
                    "valid": float(row.n_samples),
                    "expected": expected,
                    "failure_rate": 1.0 - float(row.n_samples) / expected,
                }
            )
    for (lang, judge), path in REF_FILES.items():
        df = read_csv(path)
        for row in df.itertuples(index=False):
            expected = float(row.expected_count)
            rows.append(
                {
                    "lang": lang,
                    "judge": judge,
                    "type": "reference",
                    "model": row.model,
                    "valid": float(row.n_samples),
                    "expected": expected,
                    "failure_rate": 1.0 - float(row.n_samples) / expected,
                }
            )
    return pd.DataFrame(rows)


def fig4_ref_parse() -> None:
    ref = read_csv(ROOT / "data/ko/results/results_stat_ref_vs_nonref.csv")
    ref = ref[ref["judge"].isin(["Qwen-7B", "Qwen-14B", "Qwen-32B"])].copy()
    ref["label"] = ref["lang"] + "\n" + ref["judge"]

    coverage = collect_parse_coverage()
    summary = (
        coverage.groupby(["lang", "judge", "type"], as_index=False)
        .agg(valid=("valid", "sum"), expected=("expected", "sum"))
        .assign(failure_rate=lambda d: 1 - d["valid"] / d["expected"])
    )
    top = summary.sort_values("failure_rate", ascending=False).head(6)
    top["label"] = top["lang"] + " " + top["judge"] + "\n" + top["type"]

    fig, axes = plt.subplots(1, 2, figsize=(7.4, 3.4))

    ax = axes[0]
    x = np.arange(len(ref))
    hatch = ["///" if lang == "KO" else "" for lang in ref["lang"]]
    bars = ax.bar(x, ref["diff_ref_minus_nonref"], color=MONO["light"], edgecolor=MONO["black"], lw=0.7)
    for bar, h in zip(bars, hatch):
        bar.set_hatch(h)
    ax.axhline(0, color=MONO["black"], lw=0.8)
    ax.set_ylabel("Ref - non-ref score")
    ax.set_title("Reference-guided scoring")
    ax.set_xticks(x)
    ax.set_xticklabels(ref["label"], rotation=40, ha="right")
    ax.set_ylim(-2.8, 0.3)
    ax.grid(axis="y", color="#E6E6E6", lw=0.6)
    for idx, row in enumerate(ref.itertuples(index=False)):
        ax.text(idx, row.diff_ref_minus_nonref - 0.12, p_label(row.p_value), ha="center", va="top", fontsize=7)
    add_panel_label(ax, "(a)")

    ax = axes[1]
    y = np.arange(len(top))[::-1]
    ax.barh(y, top["failure_rate"] * 100, color=MONO["light"], edgecolor=MONO["black"], lw=0.7)
    ax.set_yticks(y)
    ax.set_yticklabels(top["label"])
    ax.set_xlabel("Parse failure (%)")
    ax.set_title("Highest parse-failure settings")
    ax.set_xlim(0, max(36, top["failure_rate"].max() * 115))
    ax.grid(axis="x", color="#E6E6E6", lw=0.6)
    for ypos, row in zip(y, top.itertuples(index=False)):
        failed = int(round(row.expected - row.valid))
        total = int(round(row.expected))
        ax.text(row.failure_rate * 100 + 0.6, ypos, f"{row.failure_rate*100:.1f}% ({failed}/{total})", va="center", fontsize=7)
    add_panel_label(ax, "(b)")

    fig.tight_layout()
    save(fig, "fig4_ref_parse_failure")


def write_tables() -> None:
    gap = qwen32_gap_frame().copy()
    gap["Model"] = gap["label"]
    gap["EN"] = gap["overall_en"].map(lambda x: f"{x:.2f}")
    gap["KO"] = gap["overall_ko"].map(lambda x: f"{x:.2f}")
    gap["KO-EN"] = gap["gap"].map(lambda x: f"{x:+.2f}")
    gap["p"] = gap["p_value"].map(p_label)

    comp = read_csv(ROOT / "data/ko/results/results_en_ko_comparison.csv").copy()
    comp["Judge"] = comp["judge"].map(JUDGE_LABELS)
    comp["EN inconsistency"] = comp["en_incon_pct"].map(lambda x: f"{x:.1f}%")
    comp["KO inconsistency"] = comp["ko_incon_pct"].map(lambda x: f"{x:.1f}%")
    comp["Delta"] = comp["delta_incon_pct"].map(lambda x: f"{x:+.1f} pp")
    comp["EN first-pos/incon"] = (comp["en_fp_pct"] / comp["en_incon_pct"] * 100).map(lambda x: f"{x:.0f}%")
    comp["KO first-pos/incon"] = (comp["ko_fp_pct"] / comp["ko_incon_pct"] * 100).map(lambda x: f"{x:.0f}%")

    stat = read_csv(ROOT / "data/ko/results/results_stat_inconsistency.csv")
    stat = stat[stat["comparison"].notna() & (stat["comparison"].astype(str) != "")].copy()
    stat["Comparison"] = stat["lang"] + " " + stat["judge"]
    stat["Observed diff"] = stat["obs_diff"].map(lambda x: f"{float(x):+.4f}")
    stat["p"] = stat["p_value"].map(lambda x: p_label(float(x)))

    content = "# KCI-style Copy Tables\n\n"
    content += "## Table 1. Qwen-32B EN-KO single-grade score gap\n\n"
    content += gap[["Model", "EN", "KO", "KO-EN", "p"]].to_markdown(index=False)
    content += "\n\n## Table 2. Inconsistency and first-position tendency\n\n"
    content += comp[
        [
            "Judge",
            "EN inconsistency",
            "KO inconsistency",
            "Delta",
            "EN first-pos/incon",
            "KO first-pos/incon",
        ]
    ].to_markdown(index=False)
    content += "\n\n## Table 3. Permutation tests for inconsistency rates\n\n"
    content += stat[["Comparison", "Observed diff", "p", "sig"]].to_markdown(index=False)
    content += "\n"

    path = OUT / "kci_tables.md"
    path.write_text(content, encoding="utf-8")
    print(f"saved {path.relative_to(ROOT)}")


def write_notes() -> None:
    notes = dedent(
        """
        # KCI Figure Notes

        이 도표 세트는 한국어 LLM 벤치마크/평가 논문에 맞춰 본문 삽입용으로 설계했다.
        색 의존도를 줄이고, 흑백 인쇄에서도 구분되도록 marker shape, line style, hatch를 사용한다.

        ## Suggested Figure Order

        1. **Fig. 1. Experimental protocol.**
           방법론 섹션 마지막 또는 실험 설계 첫 부분에 배치한다.
        2. **Fig. 2. Qwen-32B single-grade score gap.**
           핵심 결과 1: 범용 영어 모델의 KO 하락폭과 한국어 특화 모델의 완충 효과.
        3. **Fig. 3. Pairwise inconsistency and residual position tendency.**
           핵심 결과 2: judge reliability와 position-sensitive residual error.
        4. **Fig. 4. Reference-guided scoring and parse failure.**
           핵심 결과 3 및 한계: reference 제공 효과와 KO 7B ref parse failure.

        ## Caption Drafts

        - **Fig. 1.** Overview of the Korean MT-Bench evaluation protocol.
        - **Fig. 2.** English and Korean MT-Bench scores under the Qwen-32B judge.
          The left annotation denotes the KO-EN score gap, and the right annotation
          denotes the paired permutation-test result.
        - **Fig. 3.** Pairwise inconsistency and first-position tendency across judge
          settings. First-position share is computed within inconsistent pairs.
        - **Fig. 4.** Reference-guided scoring effects and parse-failure settings in
          the committed aggregate CSVs. Raw JSONL judgments are included for
          independent audit and recomputation.
        """
    ).strip()
    path = OUT / "README.md"
    path.write_text(notes + "\n", encoding="utf-8")
    print(f"saved {path.relative_to(ROOT)}")


def print_audit() -> None:
    coverage = collect_parse_coverage()
    coverage["valid_rate"] = coverage["valid"] / coverage["expected"]
    bad = coverage[coverage["valid_rate"] < 0.995].sort_values("valid_rate")
    print("\ncoverage audit: rows with valid sample coverage < 99.5%")
    if bad.empty:
        print("  none")
        return
    for row in bad.itertuples(index=False):
        print(
            f"  {row.lang:2s} {row.judge:12s} {row.type:9s} "
            f"{row.model:35s} {int(row.valid):3d}/{int(row.expected):3d} "
            f"valid={row.valid_rate:.1%}"
        )


def main() -> None:
    setup_style()
    print(f"Generating KCI-style figures under {OUT.relative_to(ROOT)}/")
    fig1_protocol()
    fig2_score_gap()
    fig3_reliability_bias()
    fig4_ref_parse()
    write_tables()
    write_notes()
    print_audit()


if __name__ == "__main__":
    main()
