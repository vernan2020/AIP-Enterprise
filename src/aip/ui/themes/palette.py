from __future__ import annotations


class ThemePalette:
    """Tokens visuales de AIP Enterprise 2.0 gobernados por Coopealianza.

    Jerarquía de diseño:
    1. El Libro de Marca de Coopealianza gobierna color, tipografía e identidad visual.
    2. FactSet/Koyfin/Bloomberg/TradingView-LSEG gobiernan patrones de UX financiera,
       densidad, jerarquía de información e interacción; nunca sustituyen la marca.

    Paleta oficial Coopealianza:
    - Azul Pantone 300: RGB 0, 94, 184 -> #005EB8
    - Celeste Pantone 2995: RGB 0, 169, 224 -> #00A9E0
    - Menta Pantone 7465: RGB 64, 193, 172 -> #40C1AC
    - Rojo Pantone 185: RGB 228, 0, 43 -> #E4002B
    - Naranja Pantone 151: RGB 255, 130, 0 -> #FF8200
    - Gris institucional: RGB 147, 149, 152 -> #939598
    """

    # Marca primaria oficial.
    brand_blue = "#005EB8"
    brand_celeste = "#00A9E0"
    brand_mint = "#40C1AC"
    brand_white = "#FFFFFF"

    # Marca secundaria oficial: acentos, nunca predominantes.
    brand_red = "#E4002B"
    brand_orange = "#FF8200"
    brand_gray = "#939598"

    # Matices derivados permitidos por el Libro de Marca.
    blue_900 = "#00345F"
    blue_800 = "#00477F"
    blue_700 = "#00549F"
    blue_600 = brand_blue
    blue_500 = "#1675C5"
    blue_300 = "#73B3DD"
    blue_100 = "#D9EDF9"
    blue_050 = "#F0F8FC"

    celeste_700 = "#0088B5"
    celeste_500 = brand_celeste
    celeste_100 = "#D9F4FC"

    mint_700 = "#2B9E8B"
    mint_500 = brand_mint
    mint_100 = "#E2F6F1"

    # Aliases históricos del shell, ahora derivados del Azul Coopealianza.
    navy_950 = "#002A4F"
    navy_900 = blue_900
    navy_800 = blue_800
    navy_700 = blue_700
    navy_600 = brand_blue

    # Acentos secundarios; no deben dominar la composición.
    amber_600 = "#D96F00"
    amber_500 = brand_orange
    amber_100 = "#FFF0DF"

    # Estados semánticos. Se mantienen separados conceptualmente de la marca.
    # Los valores se seleccionan por contraste y accesibilidad, no por significado del logo.
    positive = "#167A68"
    positive_bg = "#E7F5F1"
    negative = "#B42335"
    negative_bg = "#FCEBED"
    warning = "#A95B00"
    warning_bg = "#FFF1E0"
    info = brand_blue
    info_bg = blue_050

    # Superficies: blanco predominante, azul/celeste como estructura y énfasis.
    canvas = "#F2F6F8"
    surface = brand_white
    surface_alt = "#F7F9FA"
    surface_hover = "#EDF6FB"
    surface_selected = "#DDEFFA"
    border = "#D5DEE3"
    border_strong = "#B5C5CE"
    grid = "#E3E9EC"

    # Tipografía y texto.
    text = "#183247"
    text_secondary = "#566D7C"
    muted = "#7B8D98"
    disabled = "#A8B4BA"
    inverse = brand_white

    primary = brand_blue
    secondary = brand_celeste
    tertiary = brand_mint


class DarkThemePalette:
    """Variante analítica oscura derivada de la paleta Coopealianza."""

    canvas = "#001F3A"
    surface = "#002A4F"
    surface_alt = "#00345F"
    surface_hover = "#00477F"
    surface_selected = "#00549F"
    border = "#1F5F8D"
    border_strong = "#3481AD"
    grid = "#174C70"

    text = "#F4FAFD"
    text_secondary = "#C6E5F4"
    muted = "#8FC4DD"
    disabled = "#6596AC"
    inverse = "#002A4F"

    primary = "#45C2ED"
    primary_soft = "#00549F"
    celeste = "#00A9E0"
    mint = "#40C1AC"
    orange = "#FF9A35"
    red = "#F25B70"
    positive = "#63D2BB"
    negative = "#FF7A8D"
    warning = "#FFAE55"
