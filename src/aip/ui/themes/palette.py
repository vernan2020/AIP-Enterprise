from __future__ import annotations


class ThemePalette:
    """AIP Enterprise 2.0 visual tokens.

    Design direction:
    - 35% FactSet: institutional structure, restrained surfaces and information hierarchy.
    - 30% Koyfin: dashboard readability, compact KPI cards and analytical spacing.
    - 20% Bloomberg: data density, market emphasis and trading-desk contrast.
    - 15% TradingView/LSEG: chart legibility, interaction states and market visuals.
    """

    # Institutional navy foundation — FactSet/LSEG influence.
    navy_950 = "#0B1F33"
    navy_900 = "#102A43"
    navy_800 = "#173F63"
    navy_700 = "#1F567D"
    navy_600 = "#2B6F9F"

    # Analytical blues — Koyfin/TradingView influence.
    blue_600 = "#246B9C"
    blue_500 = "#3182B7"
    blue_300 = "#8EB9D5"
    blue_100 = "#E7F0F6"
    blue_050 = "#F3F8FB"

    # Market emphasis — Bloomberg-inspired restrained amber.
    amber_600 = "#B87520"
    amber_500 = "#C9892B"
    amber_100 = "#F8EBD8"

    # Semantic states.
    positive = "#1F7A63"
    positive_bg = "#E8F5F0"
    negative = "#B44F4A"
    negative_bg = "#FBEDEC"
    warning = "#A66A16"
    warning_bg = "#FFF3DE"
    info = "#246B9C"
    info_bg = "#EAF3F8"

    # Neutral surfaces.
    canvas = "#EEF2F5"
    surface = "#FFFFFF"
    surface_alt = "#F7F9FB"
    surface_hover = "#EEF4F8"
    surface_selected = "#E2EDF5"
    border = "#D3DDE5"
    border_strong = "#AFC0CC"
    grid = "#E3E9EE"

    # Typography.
    text = "#15293B"
    text_secondary = "#53697C"
    muted = "#7D8C99"
    disabled = "#A9B4BD"
    inverse = "#FFFFFF"

    # Backwards-compatible aliases.
    primary = blue_600


class DarkThemePalette:
    """Dark analytical palette for AIP Enterprise 2.0."""

    canvas = "#08131F"
    surface = "#0E1C2A"
    surface_alt = "#122536"
    surface_hover = "#173047"
    surface_selected = "#1A3A55"
    border = "#29445A"
    border_strong = "#3D607A"
    grid = "#20384B"

    text = "#EAF1F6"
    text_secondary = "#AFC0CC"
    muted = "#7E94A6"
    disabled = "#587083"
    inverse = "#09141F"

    primary = "#5EA6D1"
    primary_soft = "#193E58"
    amber = "#D9A24F"
    positive = "#55B695"
    negative = "#E07A73"
    warning = "#E0B05D"
