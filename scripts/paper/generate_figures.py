#!/usr/bin/env python3
"""
Generate KIPS-ready paper figures and copy-ready result tables.

The script uses committed aggregate CSVs for most panels and raw judge JSONL
files for the reference-guided turn-2 comparison so every judge family can be
reported with the same scoring rule.

Usage:
    python3 scripts/paper/generate_figures.py
"""

from __future__ import annotations

import json
from pathlib import Path
from textwrap import dedent

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Rectangle


ROOT = Path(__file__).resolve().parents[2]
FIG_OUT = ROOT / "paper" / "figures"
TABLE_OUT = ROOT / "paper" / "tables"
FIG_OUT.mkdir(parents=True, exist_ok=True)
TABLE_OUT.mkdir(parents=True, exist_ok=True)

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

RAW_JUDGE_DIRS = {
    ("EN", "Qwen-7B"): ROOT / "data/en/judgments/qwen/judge_7B",
    ("EN", "Qwen-14B"): ROOT / "data/en/judgments/qwen/judge_14B",
    ("EN", "Qwen-32B"): ROOT / "data/en/judgments/qwen/judge_32B",
    ("EN", "EXAONE-32B"): ROOT / "data/en/judgments/exaone/judge_32B",
    ("EN", "GPT-4o-mini"): ROOT / "data/en/judgments/gpt/judge_gpt4omini",
    ("KO", "Qwen-7B"): ROOT / "data/ko/judgments/qwen/judge_7B",
    ("KO", "Qwen-14B"): ROOT / "data/ko/judgments/qwen/judge_14B",
    ("KO", "Qwen-32B"): ROOT / "data/ko/judgments/qwen/judge_32B",
    ("KO", "EXAONE-32B"): ROOT / "data/ko/judgments/exaone/judge_32B",
    ("KO", "GPT-4o-mini"): ROOT / "data/ko/judgments/gpt/judge_gpt4omini",
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


def save(fig: plt.Figure, stem: str) -> None:
    png = FIG_OUT / f"{stem}.png"
    pdf = FIG_OUT / f"{stem}.pdf"
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
    fig, ax = plt.subplots(figsize=(7.2, 2.18))
    ax.set_axis_off()

    boxes = [
        (0.03, 0.58, 0.15, 0.23, "MT-Bench\n80 EN items"),
        (0.24, 0.58, 0.15, 0.23, "KO benchmark\nconstruction"),
        (0.45, 0.58, 0.15, 0.23, "EN/KO answer\ncollection"),
        (0.66, 0.58, 0.15, 0.23, "LLM-as-judge\nevaluation"),
        (0.84, 0.58, 0.13, 0.23, "Metric\naggregation"),
        (0.24, 0.19, 0.15, 0.20, "Back-translation\nvalidation"),
        (0.66, 0.19, 0.15, 0.20, "Qwen / EXAONE\nGPT-4o-mini"),
        (0.84, 0.19, 0.13, 0.20, "Score gap\ninconsistency\nparse failure"),
    ]

    for x, y, w, h, text in boxes:
        patch = Rectangle(
            (x, y),
            w,
            h,
            facecolor="white",
            edgecolor=MONO["black"],
            linewidth=0.8,
        )
        ax.add_patch(patch)
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=8.0)

    arrows = [
        ((0.18, 0.695), (0.24, 0.695)),
        ((0.39, 0.695), (0.45, 0.695)),
        ((0.60, 0.695), (0.66, 0.695)),
        ((0.81, 0.695), (0.84, 0.695)),
        ((0.735, 0.58), (0.735, 0.39)),
        ((0.81, 0.29), (0.84, 0.29)),
    ]
    for start, end in arrows:
        ax.annotate(
            "",
            xy=end,
            xytext=start,
            arrowprops=dict(arrowstyle="->", color=MONO["black"], lw=0.9),
        )

    ax.annotate(
        "",
        xy=(0.315, 0.39),
        xytext=(0.315, 0.58),
        arrowprops=dict(arrowstyle="<->", color=MONO["dark"], lw=0.8, linestyle="--"),
    )
    fig.tight_layout(pad=0.15)
    save(fig, "fig1_protocol")


def qwen32_gap_frame() -> pd.DataFrame:
    en = read_csv(SCORE_FILES[("EN", "Qwen-32B")])
    ko = read_csv(SCORE_FILES[("KO", "Qwen-32B")])

    df = en[["model", "overall", "n_samples"]].merge(
        ko[["model", "overall", "n_samples"]], on="model", suffixes=("_en", "_ko")
    )
    df["gap"] = df["overall_ko"] - df["overall_en"]
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
    ax.set_yticks(y)
    ax.set_yticklabels(df["label"])
    ax.set_xlabel("MT-Bench score (1-10)")
    ax.set_xlim(4.2, 8.9)
    ax.set_title("Qwen-32B single-grade score: English vs. Korean")
    ax.grid(axis="x", color="#E6E6E6", lw=0.6)
    ax.text(
        0.0,
        -0.20,
        "Open circle=EN, filled square=KO. Left annotations show the observed KO-EN score gaps.",
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


def valid_score(value: object) -> bool:
    return isinstance(value, (int, float)) and value > 0


def load_turn2_scores(path: Path) -> list[float]:
    scores = []
    if not path.exists():
        return scores
    with path.open(encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            score = d.get("score_turn2", -1.0)
            if valid_score(score):
                scores.append(float(score))
    return scores


def collect_ref_score_diff() -> pd.DataFrame:
    rows = []
    model_ids = list(MODEL_LABELS.keys())
    for (lang, judge), judge_dir in RAW_JUDGE_DIRS.items():
        nonref_scores = []
        ref_scores = []
        for model_id in model_ids:
            nonref_scores.extend(load_turn2_scores(judge_dir / "single_grade" / f"{model_id}.jsonl"))
            ref_scores.extend(load_turn2_scores(judge_dir / "single_grade_ref" / f"{model_id}.jsonl"))
        if not nonref_scores or not ref_scores:
            continue
        nonref_mean = float(np.mean(nonref_scores))
        ref_mean = float(np.mean(ref_scores))
        rows.append(
            {
                "lang": lang,
                "judge": judge,
                "n_nonref": len(nonref_scores),
                "nonref_mean": nonref_mean,
                "n_ref": len(ref_scores),
                "ref_mean": ref_mean,
                "diff_ref_minus_nonref": ref_mean - nonref_mean,
            }
        )
    return pd.DataFrame(rows)


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


def reference_parse_summary() -> pd.DataFrame:
    coverage = collect_parse_coverage()
    order = {key: idx for idx, key in enumerate(RAW_JUDGE_DIRS)}
    ref_parse = (
        coverage[coverage["type"] == "reference"]
        .groupby(["lang", "judge"], as_index=False)
        .agg(valid=("valid", "sum"), expected=("expected", "sum"))
        .assign(failure_rate=lambda d: 1 - d["valid"] / d["expected"])
    )
    ref_parse["order"] = ref_parse.apply(lambda row: order[(row["lang"], row["judge"])], axis=1)
    return ref_parse.sort_values("order")


def fig4_ref_parse() -> None:
    ref = collect_ref_score_diff()
    ref["label"] = ref["lang"] + " " + ref["judge"]
    ref_parse = reference_parse_summary()
    ref_parse["label"] = ref_parse["lang"] + " " + ref_parse["judge"]

    fig, axes = plt.subplots(1, 2, figsize=(8.8, 4.25))

    ax = axes[0]
    y = np.arange(len(ref))[::-1]
    hatch = ["///" if lang == "KO" else "" for lang in ref["lang"]]
    bars = ax.barh(
        y,
        ref["diff_ref_minus_nonref"],
        color=MONO["light"],
        edgecolor=MONO["black"],
        lw=0.7,
    )
    for bar, h in zip(bars, hatch):
        bar.set_hatch(h)
    ax.axvline(0, color=MONO["black"], lw=0.8)
    ax.set_xlabel("Ref - non-ref score")
    ax.set_title("Reference-guided scoring")
    ax.set_yticks(y)
    ax.set_yticklabels(ref["label"])
    ax.set_xlim(min(-3.0, ref["diff_ref_minus_nonref"].min() * 1.22), 0.35)
    ax.grid(axis="x", color="#E6E6E6", lw=0.6)
    for ypos, row in zip(y, ref.itertuples(index=False)):
        ax.text(
            row.diff_ref_minus_nonref - 0.06,
            ypos,
            f"{row.diff_ref_minus_nonref:+.2f}",
            ha="right",
            va="center",
            fontsize=7,
        )
    add_panel_label(ax, "(a)")

    ax = axes[1]
    y = np.arange(len(ref_parse))[::-1]
    hatch = ["///" if lang == "KO" else "" for lang in ref_parse["lang"]]
    bars = ax.barh(y, ref_parse["failure_rate"] * 100, color=MONO["light"], edgecolor=MONO["black"], lw=0.7)
    for bar, h in zip(bars, hatch):
        bar.set_hatch(h)
    ax.set_yticks(y)
    ax.set_yticklabels(ref_parse["label"])
    ax.set_xlabel("Parse failure (%)")
    ax.set_title("Reference-guided parse failure")
    ax.set_xlim(0, max(36, ref_parse["failure_rate"].max() * 115))
    ax.grid(axis="x", color="#E6E6E6", lw=0.6)
    for ypos, row in zip(y, ref_parse.itertuples(index=False)):
        failed = int(round(row.expected - row.valid))
        total = int(round(row.expected))
        label_x = max(row.failure_rate * 100 + 0.6, 0.45)
        ax.text(label_x, ypos, f"{row.failure_rate*100:.1f}% ({failed}/{total})", va="center", fontsize=7)
    add_panel_label(ax, "(b)")

    fig.tight_layout()
    save(fig, "fig4_ref_parse_failure")


def write_tables() -> None:
    gap = qwen32_gap_frame().copy()
    gap["Model"] = gap["label"]
    gap["EN"] = gap["overall_en"].map(lambda x: f"{x:.2f}")
    gap["KO"] = gap["overall_ko"].map(lambda x: f"{x:.2f}")
    gap["KO-EN"] = gap["gap"].map(lambda x: f"{x:+.2f}")

    comp = read_csv(ROOT / "data/ko/results/results_en_ko_comparison.csv").copy()
    comp["Judge"] = comp["judge"].map(JUDGE_LABELS)
    comp["EN inconsistency"] = comp["en_incon_pct"].map(lambda x: f"{x:.1f}%")
    comp["KO inconsistency"] = comp["ko_incon_pct"].map(lambda x: f"{x:.1f}%")
    comp["Delta"] = comp["delta_incon_pct"].map(lambda x: f"{x:+.1f} pp")
    comp["EN first-pos/incon"] = (comp["en_fp_pct"] / comp["en_incon_pct"] * 100).map(lambda x: f"{x:.0f}%")
    comp["KO first-pos/incon"] = (comp["ko_fp_pct"] / comp["ko_incon_pct"] * 100).map(lambda x: f"{x:.0f}%")

    ref = collect_ref_score_diff().copy()
    ref["Lang"] = ref["lang"]
    ref["Judge"] = ref["judge"]
    ref["Non-ref"] = ref["nonref_mean"].map(lambda x: f"{float(x):.2f}")
    ref["Ref"] = ref["ref_mean"].map(lambda x: f"{float(x):.2f}")
    ref["Ref - non-ref"] = ref["diff_ref_minus_nonref"].map(lambda x: f"{float(x):+.2f}")

    ref_parse = reference_parse_summary().copy()
    ref_parse["Lang"] = ref_parse["lang"]
    ref_parse["Judge"] = ref_parse["judge"]
    ref_parse["Failed"] = (ref_parse["expected"] - ref_parse["valid"]).map(lambda x: f"{int(round(x))}")
    ref_parse["Total"] = ref_parse["expected"].map(lambda x: f"{int(round(x))}")
    ref_parse["Failure rate"] = ref_parse["failure_rate"].map(lambda x: f"{x * 100:.1f}%")

    content = "# KIPS-ready Copy Tables\n\n"
    content += "## Table 1. Qwen-32B EN-KO single-grade score gap\n\n"
    content += gap[["Model", "EN", "KO", "KO-EN"]].to_markdown(index=False, disable_numparse=True)
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
    ].to_markdown(index=False, disable_numparse=True)
    content += "\n\n## Table 3. Reference-guided score difference by judge\n\n"
    content += ref[["Lang", "Judge", "Non-ref", "Ref", "Ref - non-ref"]].to_markdown(
        index=False, disable_numparse=True
    )
    content += "\n\n## Table 4. Reference-guided parse failure by judge\n\n"
    content += ref_parse[["Lang", "Judge", "Failed", "Total", "Failure rate"]].to_markdown(
        index=False, disable_numparse=True
    )
    content += "\n"

    path = TABLE_OUT / "kci_tables.md"
    path.write_text(content, encoding="utf-8")
    print(f"saved {path.relative_to(ROOT)}")


def write_notes() -> None:
    notes = dedent(
        """
        # KIPS Paper Artifacts

        이 도표 세트는 KIPS 정보처리학회논문지 투고 원고에 맞춰 본문 삽입용으로 설계했다.
        색 의존도를 줄이고, 흑백 인쇄에서도 구분되도록 marker shape, line style, hatch를 사용한다.

        ## Regeneration

        ```bash
        python3 scripts/paper/generate_figures.py
        ```

        Generated outputs:

        - `paper/figures/*.png`
        - `paper/figures/*.pdf`
        - `paper/tables/kci_tables.md`

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
          The annotation denotes the observed KO-EN score gap.
        - **Fig. 3.** Pairwise inconsistency and first-position tendency across judge
          settings. First-position share is computed within inconsistent pairs.
        - **Fig. 4.** Reference-guided scoring effects and reference-guided
          parse-failure rates across all judge settings. Raw JSONL judgments are
          included for independent audit and recomputation.
        """
    ).strip()
    path = ROOT / "paper" / "README.md"
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
    print(f"Generating KIPS-ready figures under {FIG_OUT.relative_to(ROOT)}/")
    fig1_protocol()
    fig2_score_gap()
    fig3_reliability_bias()
    fig4_ref_parse()
    write_tables()
    write_notes()
    print_audit()


if __name__ == "__main__":
    main()
