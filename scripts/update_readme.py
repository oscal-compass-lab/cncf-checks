#!/usr/bin/env python3
"""Update README.md with summary statistics, generated PNG chart, and control-rule-check tables."""

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import yaml


def generate_png_chart(group_counts: Dict[str, int], output_png: Path) -> None:
    """Generate a high-quality horizontal bar chart PNG for capabilities and controls."""
    output_png.parent.mkdir(parents=True, exist_ok=True)

    groups = list(group_counts.keys())
    counts = [group_counts[g] for g in groups]

    plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")
    fig, ax = plt.subplots(figsize=(10, 5), dpi=300)

    colors = ["#2563eb", "#0284c7", "#0d9488", "#16a34a", "#ca8a04", "#dc2626", "#7c3aed", "#db2777"][: len(groups)]
    bars = ax.barh(groups, counts, color=colors, height=0.55, edgecolor="none")

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#cbd5e1")
    ax.spines["bottom"].set_color("#cbd5e1")

    ax.set_xlabel("Number of Capabilities & Rules", fontsize=11, fontweight="bold", color="#1e293b", labelpad=10)
    ax.set_title("Privateer Capabilities & Rules per Group", fontsize=13, fontweight="bold", color="#0f172a", pad=15)
    ax.tick_params(axis="both", labelsize=10, colors="#334155")
    ax.grid(axis="x", linestyle="--", alpha=0.5, color="#cbd5e1")

    for bar in bars:
        width = bar.get_width()
        ax.text(
            width + max(counts) * 0.015,
            bar.get_y() + bar.get_height() / 2,
            f"{int(width)}",
            ha="left",
            va="center",
            fontsize=10,
            fontweight="bold",
            color="#1e293b",
        )

    max_val = max(counts) if counts else 10
    ax.set_xlim(0, max_val * 1.15)
    ax.invert_yaxis()
    plt.tight_layout()
    plt.savefig(output_png, bbox_inches="tight", dpi=300)
    plt.close(fig)
    print(f"✓ Generated chart: {output_png}")


def generate_summary_table(
    group_data: Dict[str, Dict[str, Any]],
    total_rules: int,
    total_checks: int,
    total_controls: int,
) -> str:
    """Generate Markdown summary table by capability group / family."""
    lines = [
        "| Group / Family | Controls / Targets | Rules | Privateer Checks / Capabilities | Mapped IDs |",
        "|---|:---:|:---:|:---:|---|",
    ]
    for group, data in sorted(group_data.items(), key=lambda x: x[0]):
        ctrl_list = ", ".join(sorted(data["items"]))
        lines.append(
            f"| {group} | {len(data['controls'])} | {len(data['rules'])} | {len(data['checks'])} | {ctrl_list} |"
        )
    lines.append(
        f"| **Total** | **{total_controls}** | **{total_rules}** | **{total_checks}** | |"
    )
    return "\n".join(lines)


def parse_download_dir(download_dir: Path) -> Dict[str, Any]:
    """Parse all downloaded YAML/JSON files from Privateer repository."""
    capabilities = []
    controls = []
    checks = []

    files = sorted(
        list(download_dir.glob("*.yaml"))
        + list(download_dir.glob("*.yml"))
        + list(download_dir.glob("*.json"))
    )
    for file_path in files:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f) if file_path.suffix == ".json" else yaml.safe_load(f)
        if not data:
            continue
        if isinstance(data, dict):
            if "capabilities" in data:
                capabilities.extend(data["capabilities"])
            if "controls" in data:
                controls.extend(data["controls"])
            if "checks" in data:
                checks.extend(data["checks"])
        elif isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    if "capabilities" in item:
                        capabilities.extend(item["capabilities"])
                    elif "controls" in item:
                        controls.extend(item["controls"])
                    elif "id" in item:
                        checks.append(item)
    return {"capabilities": capabilities, "controls": controls, "checks": checks}


def update_readme(
    readme_path: Path, compdef_path: Path, download_dir: Path, chart_png_path: Path
) -> None:
    """Read downloaded checks, generate chart, and update README.md between marker tags."""
    if not readme_path.exists():
        print(f"Error: README file not found: {readme_path}", file=sys.stderr)
        sys.exit(1)

    parsed = parse_download_dir(download_dir)
    capabilities = parsed["capabilities"]
    controls = parsed["controls"]
    checks = parsed["checks"]

    group_data = defaultdict(lambda: {"controls": set(), "rules": set(), "checks": set(), "items": set()})

    for cap in capabilities:
        grp = cap.get("group", "general").capitalize()
        cap_id = cap.get("id", "")
        group_data[grp]["controls"].add(grp)
        group_data[grp]["rules"].add(cap_id.lower().replace(".", "_"))
        group_data[grp]["checks"].add(cap_id)
        group_data[grp]["items"].add(cap_id)

    for ctrl in controls:
        ctrl_id = ctrl.get("id", "")
        prefix = ctrl_id.split("-")[1] if "-" in ctrl_id else "Security"
        grp = f"Security: {prefix}"
        group_data[grp]["controls"].add(ctrl_id)
        group_data[grp]["rules"].add(f"rule_{ctrl_id.replace('-', '_')}")
        group_data[grp]["checks"].add(f"check_{ctrl_id}")
        group_data[grp]["items"].add(ctrl_id)

    for chk in checks:
        chk_id = chk.get("id", "")
        grp = chk.get("category", "General Checks").capitalize()
        group_data[grp]["controls"].add(chk_id)
        group_data[grp]["rules"].add(chk.get("rule_id", chk_id))
        group_data[grp]["checks"].add(chk_id)
        group_data[grp]["items"].add(chk_id)

    total_rules = sum(len(d["rules"]) for d in group_data.values())
    total_checks = sum(len(d["checks"]) for d in group_data.values())
    total_controls = sum(len(d["controls"]) for d in group_data.values())

    group_counts = {grp: len(data["rules"]) for grp, data in sorted(group_data.items(), key=lambda x: x[0])}

    generate_png_chart(group_counts, chart_png_path)

    chart_rel = chart_png_path.as_posix()
    chart_md = f"![Mapped Rules per Group]({chart_rel})"
    table_md = generate_summary_table(group_data, total_rules, total_checks, total_controls)

    with open(readme_path, "r", encoding="utf-8") as f:
        content = f.read()

    chart_pattern = r"(<!-- chart-start -->)(.*?)(<!-- chart-end -->)"
    chart_replacement = f"\\1\n\n{chart_md}\n\n\\3"
    if re.search(chart_pattern, content, re.DOTALL):
        content = re.sub(chart_pattern, chart_replacement, content, flags=re.DOTALL)

    table_pattern = r"(<!-- table-start -->)(.*?)(<!-- table-end -->)"
    table_replacement = f"\\1\n\n{table_md}\n\n\\3"
    if re.search(table_pattern, content, re.DOTALL):
        content = re.sub(table_pattern, table_replacement, content, flags=re.DOTALL)

    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"✓ Updated {readme_path} with stats ({total_controls} controls, {total_rules} rules, {total_checks} checks)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Update README.md with component definition statistics and chart")
    parser.add_argument(
        "--readme",
        "-r",
        type=Path,
        default=Path("README.md"),
        help="Path to README.md (default: README.md)",
    )
    parser.add_argument(
        "--compdef",
        "-c",
        type=Path,
        default=Path("trestle.ws/component-definitions/privateer/component-definition.json"),
        help="Path to component-definition.json",
    )
    parser.add_argument(
        "--download-dir",
        "-d",
        type=Path,
        default=Path("download"),
        help="Directory containing downloaded raw Privateer check files",
    )
    parser.add_argument(
        "--chart-out",
        type=Path,
        default=Path("docs/compdef-chart.png"),
        help="Path for generated PNG chart",
    )
    args = parser.parse_args()

    update_readme(args.readme, args.compdef, args.download_dir, args.chart_out)


if __name__ == "__main__":
    main()
