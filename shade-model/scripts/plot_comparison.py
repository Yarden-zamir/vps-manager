"""Draw the model against Sun Beta for a handful of sectors.

    uv run --extra plots python scripts/plot_comparison.py
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

PICK = [("Ein Fara", "Academy"), ("Ein Fara", "Monk"), ("Gita East", "Fuel"),
        ("Zanoah", "Boulder"), ("Beit Arye", "Shelf"), ("Yonim", "Hamsa")]
DAYS = ["2026-01-21", "2026-07-21"]


def main() -> int:
    report = json.loads(Path("out/report.json").read_text())
    auto = {(r["area"], r["sector"]): r for r in report["auto"]}
    given = {(r["area"], r["sector"]): r for r in report["given"]}
    fig, axes = plt.subplots(len(PICK), len(DAYS), figsize=(11, 2.0 * len(PICK)), sharex=True)
    for row, key in enumerate(PICK):
        for col, day in enumerate(DAYS):
            ax = axes[row, col]
            a, g = auto[key]["curves"][day], given[key]["curves"][day]
            ax.fill_between(a["hours"], a["truth"], step="post", color="0.82", label="Sun Beta")
            ax.plot(a["hours"], a["model"], color="#c0392b", lw=1.6, label="model, direction derived")
            ax.plot(g["hours"], g["model"], color="#1f6feb", lw=1.6, ls="--", label="model, direction given")
            ax.set_ylim(-0.05, 1.05)
            ax.set_yticks([0, 1])
            ax.set_yticklabels(["sun", "shade"])
            if row == 0:
                ax.set_title(day)
            if col == 0:
                ax.set_ylabel(f"{key[0]}\n{key[1]}", fontsize=8)
    axes[0, 0].legend(fontsize=7, loc="center left")
    for ax in axes[-1]:
        ax.set_xlabel("local time")
    plt.tight_layout()
    Path("docs").mkdir(exist_ok=True)
    plt.savefig("docs/compare_israel.png", dpi=110)
    print("docs/compare_israel.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
