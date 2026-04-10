#!/usr/bin/env python3
"""
scripts/analysis/analyze_phase345.py

Phase 3/4/5 judge 결과를 한 번에 요약하는 통합 분석 스크립트.

출력:
  - data/results_phase345_judge_summary.csv
  - data/results_phase345_judge_agreement.csv
  - figures/fig16_phase345_judge_summary.png

핵심 목적:
  1. same-family scaling claim(Phase 3)과 cross-family judge check(Phase 4/5)를 분리해 정리
  2. judge별 모델 서열, pairwise inconsistency, 불일치 내 first-position bias를 한 번에 확인
  3. judge 간 rank agreement / pairwise agreement를 실제 산출물 기준으로 다시 계산
"""

from __future__ import annotations

import csv
import json
import math
import sys
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
FIG_DIR = ROOT / "figures"
FIG_DIR.mkdir(exist_ok=True)


@dataclass(frozen=True)
class JudgeConfig:
    key: str
    phase: str
    family: str
    label: str
    params_b: str
    results_csv: Path
    pairwise_dir: Path


JUDGES: List[JudgeConfig] = [
    JudgeConfig(
        key="qwen7b",
        phase="phase3",
        family="Qwen2.5",
        label="Qwen2.5-7B",
        params_b="7",
        results_csv=DATA_DIR / "results_phase3_judge_7B.csv",
        pairwise_dir=DATA_DIR / "judgments_phase3" / "judge_7B" / "pairwise",
    ),
    JudgeConfig(
        key="qwen14b",
        phase="phase3",
        family="Qwen2.5",
        label="Qwen2.5-14B",
        params_b="14",
        results_csv=DATA_DIR / "results_phase3_judge_14B.csv",
        pairwise_dir=DATA_DIR / "judgments_phase3" / "judge_14B" / "pairwise",
    ),
    JudgeConfig(
        key="qwen32b",
        phase="phase3",
        family="Qwen2.5",
        label="Qwen2.5-32B",
        params_b="32",
        results_csv=DATA_DIR / "results_phase3_judge_32B.csv",
        pairwise_dir=DATA_DIR / "judgments_phase3" / "judge_32B" / "pairwise",
    ),
    JudgeConfig(
        key="internlm7b",
        phase="phase4",
        family="InternLM2.5",
        label="InternLM2.5-7B",
        params_b="7",
        results_csv=DATA_DIR / "results_phase4_judge_internlm7b.csv",
        pairwise_dir=DATA_DIR / "judgments_phase4" / "judge_internlm7b" / "pairwise",
    ),
    JudgeConfig(
        key="internlm20b",
        phase="phase4",
        family="InternLM2.5",
        label="InternLM2.5-20B",
        params_b="20",
        results_csv=DATA_DIR / "results_phase4_judge_internlm20b.csv",
        pairwise_dir=DATA_DIR / "judgments_phase4" / "judge_internlm20b" / "pairwise",
    ),
    JudgeConfig(
        key="gpt4omini",
        phase="phase5",
        family="OpenAI",
        label="GPT-4o-mini",
        params_b="api",
        results_csv=DATA_DIR / "results_phase5_gpt4omini.csv",
        pairwise_dir=DATA_DIR / "judgments_phase5" / "judge_gpt4omini" / "pairwise",
    ),
]


def load_overall_scores(path: Path) -> Dict[str, float]:
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return {row["model"]: float(row["overall"]) for row in rows}


def average_ranks_desc(scores: List[float]) -> List[float]:
    indexed = sorted(enumerate(scores), key=lambda x: (-x[1], x[0]))
    ranks = [0.0] * len(scores)
    pos = 1
    i = 0
    while i < len(indexed):
        j = i
        same = [indexed[i]]
        while j + 1 < len(indexed) and indexed[j + 1][1] == indexed[i][1]:
            j += 1
            same.append(indexed[j])
        avg_rank = (pos + pos + len(same) - 1) / 2.0
        for idx, _ in same:
            ranks[idx] = avg_rank
        pos += len(same)
        i = j + 1
    return ranks


def pearson_corr(xs: List[float], ys: List[float]) -> float:
    n = len(xs)
    mx = sum(xs) / n
    my = sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    vx = sum((x - mx) ** 2 for x in xs)
    vy = sum((y - my) ** 2 for y in ys)
    if vx == 0 or vy == 0:
        return float("nan")
    return cov / math.sqrt(vx * vy)


def spearman_rho(scores_a: Dict[str, float], scores_b: Dict[str, float]) -> float:
    common = sorted(set(scores_a) & set(scores_b))
    vals_a = [scores_a[m] for m in common]
    vals_b = [scores_b[m] for m in common]
    rank_a = average_ranks_desc(vals_a)
    rank_b = average_ranks_desc(vals_b)
    return pearson_corr(rank_a, rank_b)


def sign(x: float) -> int:
    if x > 0:
        return 1
    if x < 0:
        return -1
    return 0


def kendall_tau_b(scores_a: Dict[str, float], scores_b: Dict[str, float]) -> float:
    common = sorted(set(scores_a) & set(scores_b))
    if len(common) < 2:
        return float("nan")

    concordant = 0
    discordant = 0
    ties_a = 0
    ties_b = 0
    total = 0

    for model_i, model_j in combinations(common, 2):
        da = sign(scores_a[model_i] - scores_a[model_j])
        db = sign(scores_b[model_i] - scores_b[model_j])
        total += 1
        if da == 0:
            ties_a += 1
        if db == 0:
            ties_b += 1
        if da == 0 or db == 0:
            continue
        if da == db:
            concordant += 1
        else:
            discordant += 1

    denom = math.sqrt((total - ties_a) * (total - ties_b))
    if denom == 0:
        return float("nan")
    return (concordant - discordant) / denom


def iter_jsonl(path: Path) -> Iterable[dict]:
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def load_pairwise_records(pairwise_dir: Path) -> List[dict]:
    files = sorted(pairwise_dir.glob("*.jsonl"))
    expected_files = 21
    if len(files) != expected_files:
        raise ValueError(
            f"{pairwise_dir} should contain {expected_files} pairwise files, found {len(files)}"
        )
    records: List[dict] = []
    for fpath in files:
        for record in iter_jsonl(fpath):
            record["_pair_file"] = fpath.stem
            records.append(record)
    return records


def compute_pairwise_summary(records: List[dict]) -> dict:
    total = len(records)
    error_records = [r for r in records if r.get("winner") == "error"]
    valid_records = [r for r in records if r.get("winner") != "error"]
    inconsistent = [r for r in valid_records if r.get("winner") == "inconsistent"]
    decisive = [r for r in valid_records if r.get("winner") not in {"inconsistent", "error"}]
    first_pos_wins = 0
    for record in inconsistent:
        if record.get("winner_ab") == "A":
            first_pos_wins += 1
        elif record.get("winner_ba") == "B":
            first_pos_wins += 1

    error_n = len(error_records)
    valid_n = len(valid_records)
    inconsistent_n = len(inconsistent)
    decisive_n = len(decisive)
    error_rate = error_n / total if total else float("nan")
    inconsistency_rate_total = inconsistent_n / total if total else float("nan")
    inconsistency_rate_valid = inconsistent_n / valid_n if valid_n else float("nan")
    first_pos_rate = first_pos_wins / inconsistent_n if inconsistent_n else float("nan")
    decisive_rate_total = decisive_n / total if total else float("nan")
    decisive_rate_valid = decisive_n / valid_n if valid_n else float("nan")

    return {
        "total_pairwise": total,
        "valid_pairwise": valid_n,
        "error_n": error_n,
        "error_rate": error_rate,
        "inconsistent_n": inconsistent_n,
        "inconsistency_rate_total": inconsistency_rate_total,
        "inconsistency_rate_valid": inconsistency_rate_valid,
        "decisive_n": decisive_n,
        "decisive_rate_total": decisive_rate_total,
        "decisive_rate_valid": decisive_rate_valid,
        "first_pos_wins": first_pos_wins,
        "first_pos_rate": first_pos_rate,
    }


def pairwise_outcome_map(records: List[dict]) -> Dict[Tuple[str, int, int], str]:
    return {
        (r["_pair_file"], int(r["question_id"]), int(r.get("turn", 2))): str(r["winner"])
        for r in records
    }


def exact_agreement(map_a: Dict[Tuple[str, int, int], str], map_b: Dict[Tuple[str, int, int], str]) -> Tuple[float, int]:
    common = sorted(set(map_a) & set(map_b))
    common = [key for key in common if map_a[key] != "error" and map_b[key] != "error"]
    if not common:
        return float("nan"), 0
    agree = sum(1 for key in common if map_a[key] == map_b[key])
    return agree / len(common), len(common)


def build_summary_rows() -> Tuple[List[dict], Dict[str, Dict[str, float]], Dict[str, Dict[Tuple[str, int, int], str]]]:
    summary_rows: List[dict] = []
    score_map: Dict[str, Dict[str, float]] = {}
    winner_map: Dict[str, Dict[Tuple[str, int, int], str]] = {}

    for judge in JUDGES:
        scores = load_overall_scores(judge.results_csv)
        records = load_pairwise_records(judge.pairwise_dir)
        pairwise_summary = compute_pairwise_summary(records)
        pairwise_map = pairwise_outcome_map(records)

        ranked = sorted(scores.items(), key=lambda x: (-x[1], x[0]))
        top_model, top_score = ranked[0]
        bottom_model, bottom_score = ranked[-1]

        summary_rows.append(
            {
                "judge_key": judge.key,
                "phase": judge.phase,
                "family": judge.family,
                "judge_label": judge.label,
                "params_B": judge.params_b,
                "top_model": top_model,
                "top_score": round(top_score, 4),
                "bottom_model": bottom_model,
                "bottom_score": round(bottom_score, 4),
                "score_range": round(top_score - bottom_score, 4),
                **{
                    k: round(v, 4) if isinstance(v, float) and not math.isnan(v) else v
                    for k, v in pairwise_summary.items()
                },
            }
        )

        score_map[judge.key] = scores
        winner_map[judge.key] = pairwise_map

    return summary_rows, score_map, winner_map


def save_csv(path: Path, rows: List[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def make_matrix_figure(
    summary_rows: List[dict],
    spearman: np.ndarray,
    pairwise_agree: np.ndarray,
    labels: List[str],
    output_path: Path,
) -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "axes.spines.top": False,
            "axes.spines.right": False,
            "figure.dpi": 150,
            "savefig.dpi": 200,
            "savefig.bbox": "tight",
        }
    )

    decisive = [row["decisive_rate_total"] * 100 for row in summary_rows]
    inconsistent = [row["inconsistency_rate_total"] * 100 for row in summary_rows]
    error = [row["error_rate"] * 100 for row in summary_rows]
    first_pos = [row["first_pos_rate"] * 100 for row in summary_rows]
    inconsistent_n = [int(row["inconsistent_n"]) for row in summary_rows]
    colors = ["#1565C0", "#1E88E5", "#42A5F5", "#43A047", "#2E7D32", "#F57C00"]

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.patch.set_facecolor("white")

    x = np.arange(len(labels))

    ax = axes[0, 0]
    decisive_bars = ax.bar(x, decisive, color="#66BB6A", edgecolor="white", label="Decisive")
    inconsistent_bars = ax.bar(x, inconsistent, bottom=decisive, color="#EF5350", edgecolor="white", label="Inconsistent")
    error_bars = ax.bar(
        x,
        error,
        bottom=[d + inc for d, inc in zip(decisive, inconsistent)],
        color="#B0BEC5",
        edgecolor="white",
        label="Error",
    )
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=25, ha="right")
    ax.set_ylabel("Share of pairwise records (%)")
    ax.set_title("(A) Pairwise outcome composition", fontweight="bold")
    ax.set_ylim(0, 105)
    ax.legend(fontsize=8, framealpha=0.9, loc="upper right")
    for bars, vals in [
        (decisive_bars, decisive),
        (inconsistent_bars, inconsistent),
        (error_bars, error),
    ]:
        for bar, val in zip(bars, vals):
            if val < 6:
                continue
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_y() + bar.get_height() / 2,
                f"{val:.1f}%",
                ha="center",
                va="center",
                fontsize=8.5,
                color="white" if bar.get_facecolor()[1] < 0.6 else "black",
                fontweight="bold",
            )

    ax = axes[0, 1]
    bars = ax.bar(x, first_pos, color=colors, edgecolor="white")
    ax.axhline(50, color="gray", linestyle="--", linewidth=1.2, alpha=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=25, ha="right")
    ax.set_ylabel("First-position win rate (%)")
    ax.set_title("(B) First-position bias within inconsistent cases", fontweight="bold")
    ax.set_ylim(50, max(first_pos) + 5)
    for bar, val, n in zip(bars, first_pos, inconsistent_n):
        ax.text(bar.get_x() + bar.get_width() / 2, val + 0.6, f"{val:.1f}%\n(n={n})", ha="center", fontsize=8.5)

    for ax, matrix, title in [
        (axes[1, 0], spearman, "(C) Spearman rank agreement"),
        (axes[1, 1], pairwise_agree, "(D) Exact pairwise winner agreement"),
    ]:
        im = ax.imshow(matrix, cmap="YlGnBu", vmin=0.0, vmax=1.0)
        ax.set_xticks(np.arange(len(labels)))
        ax.set_yticks(np.arange(len(labels)))
        ax.set_xticklabels(labels, rotation=25, ha="right")
        ax.set_yticklabels(labels)
        ax.set_title(title, fontweight="bold")
        for i in range(len(labels)):
            for j in range(len(labels)):
                value = matrix[i, j]
                text = "---" if i == j and title.endswith("agreement") else f"{value:.3f}"
                color = "white" if value > 0.62 else "black"
                ax.text(j, i, text, ha="center", va="center", color=color, fontsize=9, fontweight="bold")
        fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)

    fig.suptitle(
        "Phase 3/4/5 Seen-7 Judge Summary\n"
        "same-family Qwen scaling + cross-family InternLM / GPT-4o-mini checks",
        fontsize=15,
        fontweight="bold",
        y=0.98,
    )
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    fig.savefig(output_path)
    plt.close(fig)


def main() -> None:
    missing = [judge.results_csv for judge in JUDGES if not judge.results_csv.exists()]
    missing += [judge.pairwise_dir for judge in JUDGES if not judge.pairwise_dir.exists()]
    if missing:
        raise FileNotFoundError("Missing required inputs:\n" + "\n".join(str(path) for path in missing))

    summary_rows, score_map, winner_map = build_summary_rows()
    label_map = {judge.key: judge.label for judge in JUDGES}
    judge_keys = [judge.key for judge in JUDGES]
    labels = [label_map[key] for key in judge_keys]

    n = len(judge_keys)
    spearman = np.eye(n)
    kendall = np.eye(n)
    pairwise_agree = np.eye(n)
    agreement_rows: List[dict] = []

    for i, key_a in enumerate(judge_keys):
        for j, key_b in enumerate(judge_keys):
            if i >= j:
                continue
            rho = spearman_rho(score_map[key_a], score_map[key_b])
            tau = kendall_tau_b(score_map[key_a], score_map[key_b])
            exact, common_n = exact_agreement(winner_map[key_a], winner_map[key_b])
            spearman[i, j] = spearman[j, i] = rho
            kendall[i, j] = kendall[j, i] = tau
            pairwise_agree[i, j] = pairwise_agree[j, i] = exact
            agreement_rows.append(
                {
                    "judge_a": label_map[key_a],
                    "judge_b": label_map[key_b],
                    "spearman_rho": round(rho, 4),
                    "kendall_tau_b": round(tau, 4),
                    "exact_pairwise_agreement_valid": round(exact, 4),
                    "common_valid_pairwise_records": common_n,
                }
            )

    save_csv(DATA_DIR / "results_phase345_judge_summary.csv", summary_rows)
    save_csv(DATA_DIR / "results_phase345_judge_agreement.csv", agreement_rows)
    make_matrix_figure(
        summary_rows=summary_rows,
        spearman=spearman,
        pairwise_agree=pairwise_agree,
        labels=labels,
        output_path=FIG_DIR / "fig16_phase345_judge_summary.png",
    )

    print("\nSaved:")
    print(f"  - {DATA_DIR / 'results_phase345_judge_summary.csv'}")
    print(f"  - {DATA_DIR / 'results_phase345_judge_agreement.csv'}")
    print(f"  - {FIG_DIR / 'fig16_phase345_judge_summary.png'}")


if __name__ == "__main__":
    main()
