#!/usr/bin/env python3
"""
Render a to-scale, address-based flash memory map (with sector boundaries) from a
YAML memory-map file. See flash_map_part2.yaml for the expected schema.

Usage:
    python3 render_flash_map.py flash_map_part2.yaml flash-map-part2.svg

Requires: pyyaml, matplotlib (pip install pyyaml matplotlib)
"""
import sys
import yaml
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import Rectangle

MAX_SECTOR_LINES = 64        # above this, annotate sector count as text instead of drawing every line
DETAIL_ZONE_FRACTION = 0.05  # leading regions smaller than this fraction of the bank get zoomed separately
LABEL_PITCH_FRACTION = 0.068 # min vertical distance between two 3-line region labels, as fraction of panel height

# attrs is a closed keyword vocabulary (see the YAML header comment). Color priority,
# most visually important first: otp-ness, then safety classification, then bank identity.
CATEGORY_COLORS = {
    "otp":         "#8d99ae",
    "hsm":         "#ffd166",
    "asil_b":      "#f3722c",
    "qm":          "#4d96ff",
    "reserved":    "#e9ecef",
    "chip_dflash": "#2ec4b6",
    "dflash":      "#9b5de5",
    "pflash":      "#90be6d",
}
COLOR_PRIORITY = ["otp", "hsm", "asil_b", "qm", "reserved", "chip_dflash", "dflash", "pflash"]
DEFAULT_COLOR = "#adb5bd"
FLAG_HATCH_COLOR = "#d90429"


def region_color(attrs):
    for key in COLOR_PRIORITY:
        if key in attrs:
            return CATEGORY_COLORS[key]
    return DEFAULT_COLOR


def is_pow2(n):
    return n > 0 and n & (n - 1) == 0


def check_layout(doc):
    """Hard layout rules. Returns a list of violations (empty = OK).

    - every bank is a power of two, aligned to its size (one MPU region per bank)
    - every region tagged `mpu` is a power of two, aligned to its size
      (ARMv7-M MPU: RASR size is 2^n, RBAR base must be size-aligned)
    - every region is a whole number of sectors and starts on a sector boundary
    - regions inside a bank are contiguous and fill the bank exactly
    """
    errors = []
    for bank in doc["banks"]:
        if not is_pow2(bank["size"]) or bank["base"] % bank["size"]:
            errors.append(f"bank {bank['name']}: {fmt_size(bank['size'])} at {fmt_addr(bank['base'])} "
                          "is not a size-aligned power of two")
        addr = bank["base"]
        for r in bank["regions"]:
            name, start, size = r["name"], r["start"], r["size"]
            if start != addr:
                errors.append(f"{name}: starts at {fmt_addr(start)}, expected {fmt_addr(addr)} (gap/overlap)")
            addr = start + size
            sector = r.get("sector_size")
            if sector and (size % sector or start % sector):
                errors.append(f"{name}: not a whole number of {fmt_size(sector)} sectors")
            if "mpu" in r.get("attrs", []):
                if not is_pow2(size):
                    errors.append(f"{name}: {fmt_size(size)} is not a power of two (MPU region)")
                elif start % size:
                    errors.append(f"{name}: {fmt_addr(start)} is not aligned to its {fmt_size(size)} size (MPU region)")
        if addr != bank["base"] + bank["size"]:
            errors.append(f"bank {bank['name']}: regions end at {fmt_addr(addr)}, bank ends at "
                          f"{fmt_addr(bank['base'] + bank['size'])}")
    return errors


def fmt_addr(addr):
    return f"0x{addr:08X}"


def fmt_size(size_bytes):
    if size_bytes >= 1024 * 1024:
        v = size_bytes / (1024 * 1024)
        return f"{v:g} MB"
    if size_bytes >= 1024:
        v = size_bytes / 1024
        return f"{v:g} KB"
    return f"{size_bytes} B"


def draw_bank(ax, regions, y0, y1, draw_sector_lines=True, label_size=8,
              skip_labels_for=None, min_label_frac=0.0):
    """Draw one bank's regions as a stacked vertical bar between y-limits y0..y1
    (address space mapped linearly onto that pixel range).

    skip_labels_for: set of region names to draw without a text label (still drawn
    as colored blocks + tick marks) — used to avoid clutter for regions that are
    small at this scale but shown in detail elsewhere (see the zoom panel).
    """
    skip_labels_for = skip_labels_for or set()
    lo = regions[0]["start"]
    hi = regions[-1]["start"] + regions[-1]["size"]
    span = hi - lo

    def to_y(addr):
        return y0 + (addr - lo) / span * (y1 - y0)

    labels = []  # (block center y, text, flagged note or None)
    for r in regions:
        y_bot = to_y(r["start"])
        y_top = to_y(r["start"] + r["size"])
        h = y_top - y_bot
        attrs = r.get("attrs", [])
        color = region_color(attrs)
        flagged = r.get("flag") is not None
        rect = Rectangle((0, y_bot), 1, h, facecolor=color, edgecolor="black",
                          linewidth=0.8, zorder=2)
        if flagged:
            rect.set_hatch("////")
            rect.set_edgecolor(FLAG_HATCH_COLOR)
            rect.set_linewidth(1.6)
        ax.add_patch(rect)

        sector = r.get("sector_size")
        if draw_sector_lines and sector:
            n_sectors = r["size"] / sector
            if n_sectors <= MAX_SECTOR_LINES and n_sectors > 1:
                n_full = int(n_sectors)
                for i in range(1, n_full + 1):
                    y = to_y(r["start"] + i * sector)
                    if y <= y_top + 1e-9:
                        ax.plot([0, 1], [y, y], color="white", linewidth=0.6, zorder=3, alpha=0.9)

        skip_label = r["name"] in skip_labels_for or h < min_label_frac * (y1 - y0)

        if not skip_label:
            ax.plot([-0.03, 0], [y_bot, y_bot], color="black", linewidth=0.8, zorder=4)
            ax.text(-0.05, y_bot, fmt_addr(r["start"]), ha="right", va="center",
                     fontsize=label_size - 1.5, family="monospace")

            label = f"{r['name']}\n{fmt_size(r['size'])}"
            if sector:
                n_sectors = r["size"] / sector
                if float(n_sectors).is_integer():
                    label += f" · {int(n_sectors)}× {fmt_size(sector)} sectors"
                else:
                    label += f" · {n_sectors:.1f}× {fmt_size(sector)} sectors (!)"
            label += "\n[" + ", ".join(attrs) + "]"
            note = r.get("note", "").split(".")[0] + "." if flagged else None
            labels.append(((y_bot + y_top) / 2, label, note))

    # Small regions get labels taller than their block: push labels apart so they
    # never overlap, and draw a leader line from each moved label back to its block.
    pitch = LABEL_PITCH_FRACTION * (y1 - y0)
    placed = [y for y, _, _ in labels]
    for i in range(1, len(placed)):
        placed[i] = max(placed[i], placed[i - 1] + pitch)
    if placed and placed[-1] > y1:
        placed[-1] = y1
        for i in range(len(placed) - 2, -1, -1):
            placed[i] = min(placed[i], placed[i + 1] - pitch)
    moved = any(abs(p - y) > 1e-9 for p, (y, _, _) in zip(placed, labels))
    x_text = 1.32 if moved else 1.05
    for (y_block, label, note), y_label in zip(labels, placed):
        if moved:
            ax.plot([1, 1.1, 1.25, 1.3], [y_block, y_block, y_label, y_label],
                     color="#555", linewidth=0.7, zorder=4)
        ax.text(x_text, y_label, label, ha="left", va="center",
                 fontsize=label_size, linespacing=1.3)
        if note:
            ax.text(x_text, y_label - 0.022 * (y1 - y0), note,
                     ha="left", va="top", fontsize=label_size - 1.5, color=FLAG_HATCH_COLOR)

    if skip_labels_for:
        collapsed = [r for r in regions if r["name"] in skip_labels_for]
        if collapsed:
            y_bot = to_y(collapsed[0]["start"])
            y_top = to_y(collapsed[-1]["start"] + collapsed[-1]["size"])
            ax.text(1.05, (y_bot + y_top) / 2, "small leading regions — see zoom panel",
                     ha="left", va="center", fontsize=label_size - 1, style="italic", color="#555")

    y_top_final = to_y(hi)
    ax.plot([-0.03, 0], [y_top_final, y_top_final], color="black", linewidth=0.8, zorder=4)
    ax.text(-0.05, y_top_final, fmt_addr(hi), ha="right", va="center",
             fontsize=label_size - 1.5, family="monospace")

    ax.set_xlim(-0.9, 3.9)
    ax.set_ylim(y0 - 0.02 * (y1 - y0), y1 + 0.02 * (y1 - y0))
    ax.axis("off")


def leading_detail_zone(regions, bank_size, fraction=DETAIL_ZONE_FRACTION):
    """Return the contiguous run of regions from the start of the bank whose
    individual sizes are each below `fraction` of the bank's total size — the
    small leading cluster that needs its own zoom panel."""
    threshold = bank_size * fraction
    detail = []
    for r in regions:
        if r["size"] < threshold:
            detail.append(r)
        else:
            break
    return detail


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)
    yaml_path, out_path = sys.argv[1], sys.argv[2]

    with open(yaml_path, "r", encoding="utf-8") as f:
        doc = yaml.safe_load(f)

    errors = check_layout(doc)
    if errors:
        print("Layout check FAILED:", *errors, sep="\n  ")
        sys.exit(2)

    banks = {b["name"]: b for b in doc["banks"]}
    program_flash = banks["Program Flash"]
    data_flash = banks["Data Flash"]
    chip_dflash = banks.get("Chip D-Flash")

    pf_regions = program_flash["regions"]
    df_regions = data_flash["regions"]

    detail_regions = leading_detail_zone(pf_regions, program_flash["size"])
    detail_names = {r["name"] for r in detail_regions}
    detail_hi = detail_regions[-1]["start"] + detail_regions[-1]["size"] if detail_regions else pf_regions[0]["start"]

    n_panels = 3 + (1 if chip_dflash else 0)
    width_ratios = ([0.5] if chip_dflash else []) + [1.15, 0.95, 0.6]
    fig = plt.figure(figsize=(3.6 * n_panels, 9))
    gs = fig.add_gridspec(1, n_panels, width_ratios=width_ratios, wspace=1.5)

    col = 0
    if chip_dflash:
        ax_chip = fig.add_subplot(gs[0, col]); col += 1
        cd_regions = chip_dflash["regions"]
        draw_bank(ax_chip, cd_regions, 0, 10, draw_sector_lines=True, label_size=8)
        ax_chip.set_title(f"Chip D-Flash — {fmt_size(chip_dflash['size'])}\n"
                            f"{fmt_addr(chip_dflash['base'])} .. "
                            f"{fmt_addr(chip_dflash['base'] + chip_dflash['size'] - 1)}\n"
                            "(separate factory array)",
                            fontsize=10, fontweight="bold")

    ax_full = fig.add_subplot(gs[0, col]); col += 1
    ax_zoom = fig.add_subplot(gs[0, col]); col += 1
    ax_data = fig.add_subplot(gs[0, col]); col += 1

    draw_bank(ax_full, pf_regions, 0, 10, draw_sector_lines=True, label_size=8,
              skip_labels_for=detail_names)
    ax_full.set_title(f"Program Flash — {fmt_size(program_flash['size'])}\n"
                        f"{fmt_addr(program_flash['base'])} .. {fmt_addr(program_flash['base'] + program_flash['size'] - 1)}",
                        fontsize=10, fontweight="bold")

    if detail_regions:
        lo_full = pf_regions[0]["start"]
        hi_full = pf_regions[-1]["start"] + pf_regions[-1]["size"]
        y_detail_top = 10 * (detail_hi - lo_full) / (hi_full - lo_full)
        ax_full.add_patch(Rectangle((0, 0), 1, y_detail_top, facecolor="none",
                                      edgecolor="#2b2d42", linewidth=1.4, linestyle="--", zorder=5))

        draw_bank(ax_zoom, detail_regions, 0, 10, draw_sector_lines=True, label_size=8)
        ax_zoom.set_title(f"Zoom: small leading regions\n{fmt_addr(pf_regions[0]['start'])} .. {fmt_addr(detail_hi - 1)}",
                            fontsize=10, fontweight="bold")
    else:
        ax_zoom.axis("off")

    draw_bank(ax_data, df_regions, 0, 10, draw_sector_lines=True, label_size=8)
    ax_data.set_title(f"Data Flash — {fmt_size(data_flash['size'])}\n"
                        f"{fmt_addr(data_flash['base'])} .. {fmt_addr(data_flash['base'] + data_flash['size'] - 1)}",
                        fontsize=10, fontweight="bold")

    legend_handles = [mpatches.Patch(facecolor=c, edgecolor="black", label=k)
                       for k, c in CATEGORY_COLORS.items()]
    legend_handles.append(mpatches.Patch(facecolor="#adb5bd", edgecolor=FLAG_HATCH_COLOR,
                                          hatch="////", label="flagged (see note)"))
    fig.legend(handles=legend_handles, loc="lower center", ncol=4, fontsize=8,
                frameon=False, bbox_to_anchor=(0.5, -0.03))

    title = doc["document"]["title"]
    subtitle = doc["document"].get("subtitle", "")
    fig.suptitle(f"{title}\n{subtitle}", fontsize=13, fontweight="bold", y=1.03)

    fmt = "png" if out_path.lower().endswith(".png") else "svg"
    fig.savefig(out_path, format=fmt, bbox_inches="tight", dpi=150 if fmt == "png" else None)
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
