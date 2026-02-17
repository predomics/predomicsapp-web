"""Taxonomy-based color assignment for ecosystem network nodes.

Ports the SCAPIS coloring scheme: priority phylum colors with
family-level shading within each phylum (lighten→darken gradient).

Reference: internships/ecosystem/analyses/build_ecosystem_scapis.Rmd lines 292-338
"""

from __future__ import annotations

# Priority phylum colors (SCAPIS / GTDB taxonomy)
PHYLUM_PRIORITY_COLORS: dict[str, str] = {
    "Bacillota": "#08519c",
    "Bacillota_A": "#2171b5",
    "Bacillota_B": "#4292c6",
    "Bacillota_C": "#6baed6",
    "Bacillota_I": "#9ecae1",
    "Bacteroidota": "#d73027",
    "Pseudomonadota": "#1a9850",
    "Actinomycetota": "#ae017e",
    "Heterokonta": "#756bb1",
    # Classic taxonomy names (common in older datasets)
    "Firmicutes": "#4292c6",
    "Bacteroidetes": "#d73027",
    "Proteobacteria": "#1a9850",
    "Actinobacteria": "#ae017e",
    "Fusobacteria": "#e6ab02",
    "Verrucomicrobia": "#66c2a5",
    "Euryarchaeota": "#a6761d",
    "Tenericutes": "#e78ac3",
    "Spirochaetes": "#fc8d62",
}

# Fallback palette for phyla not in the priority list
_FALLBACK_PALETTE = [
    "#8dd3c7", "#ffffb3", "#bebada", "#fb8072", "#80b1d3",
    "#fdb462", "#b3de69", "#fccde5", "#d9d9d9", "#bc80bd",
    "#ccebc5", "#ffed6f",
]

# Module colors (for community detection)
MODULE_COLORS = [
    "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
    "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf",
    "#aec7e8", "#ffbb78",
]


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _rgb_to_hex(r: int, g: int, b: int) -> str:
    return f"#{r:02x}{g:02x}{b:02x}"


def lighten_color(hex_color: str, amount: float = 0.35) -> str:
    """Interpolate toward white by amount (0→no change, 1→white)."""
    r, g, b = _hex_to_rgb(hex_color)
    r = min(255, int(r + (255 - r) * amount))
    g = min(255, int(g + (255 - g) * amount))
    b = min(255, int(b + (255 - b) * amount))
    return _rgb_to_hex(r, g, b)


def darken_color(hex_color: str, amount: float = 0.35) -> str:
    """Interpolate toward black by amount (0→no change, 1→black)."""
    r, g, b = _hex_to_rgb(hex_color)
    r = max(0, int(r * (1 - amount)))
    g = max(0, int(g * (1 - amount)))
    b = max(0, int(b * (1 - amount)))
    return _rgb_to_hex(r, g, b)


def _color_panel(n: int, low: str, high: str) -> list[str]:
    """Generate n colors interpolated from low to high."""
    if n <= 0:
        return []
    if n == 1:
        return [low]
    r1, g1, b1 = _hex_to_rgb(low)
    r2, g2, b2 = _hex_to_rgb(high)
    colors = []
    for i in range(n):
        t = i / (n - 1)
        r = int(r1 + (r2 - r1) * t)
        g = int(g1 + (g2 - g1) * t)
        b = int(b1 + (b2 - b1) * t)
        colors.append(_rgb_to_hex(r, g, b))
    return colors


def assign_taxonomy_colors(
    nodes: list[dict],
) -> tuple[dict[str, str], list[dict]]:
    """Assign colors to nodes based on phylum→family hierarchy.

    Args:
        nodes: list of dicts, each must have 'phylum' and 'family' keys (can be None/empty).

    Returns:
        (family_colors, legend_entries)
        - family_colors: {family_name: hex_color}
        - legend_entries: [{phylum, family, color}] sorted by phylum then family
    """
    # Collect unique phylum→family mapping
    phylum_families: dict[str, set[str]] = {}
    for node in nodes:
        phy = node.get("phylum") or "Unknown"
        fam = node.get("family") or "Unknown"
        phylum_families.setdefault(phy, set()).add(fam)

    # Assign base colors to phyla
    phylum_base: dict[str, str] = {}
    fallback_idx = 0
    for phy in sorted(phylum_families.keys()):
        if phy in PHYLUM_PRIORITY_COLORS:
            phylum_base[phy] = PHYLUM_PRIORITY_COLORS[phy]
        else:
            phylum_base[phy] = _FALLBACK_PALETTE[fallback_idx % len(_FALLBACK_PALETTE)]
            fallback_idx += 1

    # Assign family-level colors within each phylum
    family_colors: dict[str, str] = {}
    legend_entries: list[dict] = []

    for phy in sorted(phylum_families.keys()):
        families = sorted(phylum_families[phy])
        base = phylum_base[phy]
        low = lighten_color(base, 0.35)
        high = darken_color(base, 0.35)
        panel = _color_panel(len(families), low, high)

        for i, fam in enumerate(families):
            color = panel[i]
            family_colors[fam] = color
            legend_entries.append({
                "phylum": phy,
                "family": fam,
                "color": color,
            })

    return family_colors, legend_entries
