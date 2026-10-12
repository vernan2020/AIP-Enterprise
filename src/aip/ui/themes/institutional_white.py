from __future__ import annotations

from aip.ui.themes.palette import ThemePalette


class InstitutionalWhiteDesign:
    """Shared institutional light design language for every AIP workspace.

    Presentation only: changes no data source, value, calculation or permission.
    Reuses Coopealianza's official palette and the application's existing font.
    """

    @staticmethod
    def kpi_card_style(object_name: str) -> str:
        """One reusable white KPI surface across financial workspaces."""
        return (
            f"QFrame#{object_name} {{background:#FFFFFF; border:1px solid #D8E6EF; "
            "border-radius:11px;}"
            f"QFrame#{object_name}:hover {{background:#F8FCFF; "
            "border:1px solid #90C8E7;}"
        )

    KPI_TITLE = "color:#42617A; font-size:9px; font-weight:600; border:none;"
    KPI_VALUE = "color:#00345F; font-weight:700; border:none;"
    KPI_NOTE = "color:#617B8C; font-size:8px; border:none;"

    @staticmethod
    def stylesheet() -> str:
        p = ThemePalette()
        return f"""
        /* UX V5: light institutional canvas, shared on every workspace. */
        QMainWindow, QDialog {{
            background: {p.canvas};
            color: {p.text};
        }}
        QWidget#homeWorkspace,
        QWidget#executiveWorkspace,
        QWidget#portfolioWorkspace,
        QWidget#marketWorkspace,
        QWidget#priceRiskWorkspace,
        QWidget#rateRiskWorkspace,
        QWidget#macroIntelligenceWorkspace,
        QWidget#liquidityWorkspace,
        QWidget#treasuryWorkspace,
        QWidget#financialAnalysisWorkspace {{
            background: #F5F8FB;
        }}
        QToolBar#aipRibbon {{
            background: #FFFFFF;
            border: none;
            border-bottom: 1px solid #DCE7EF;
            min-height: 48px;
            spacing: 2px;
            padding: 3px 9px;
        }}
        QToolBar#aipRibbon QToolButton {{
            background: transparent;
            color: {p.blue_800};
            border: 1px solid transparent;
            border-radius: 7px;
            font-size: 9pt;
            font-weight: 600;
            padding: 7px 9px;
        }}
        QToolBar#aipRibbon QToolButton:hover {{
            background: #EEF7FC;
            border: 1px solid #D5EAF5;
        }}
        QToolBar#aipRibbon QToolButton:checked {{
            background: {p.brand_blue};
            color: #FFFFFF;
            border: 1px solid {p.brand_blue};
        }}
        QToolBar#aipRibbon QToolButton:disabled {{
            background: #FFFFFF;
            color: #8C9EAB;
        }}
        QTabWidget::pane {{
            background: #FFFFFF;
            border: 1px solid #DFE8EE;
            border-radius: 10px;
            top: -1px;
        }}
        QTabBar::tab {{
            background: transparent;
            color: {p.text_secondary};
            min-height: 26px;
            padding: 7px 13px;
            margin-right: 3px;
            border: none;
            border-bottom: 2px solid transparent;
            border-radius: 6px 6px 0 0;
            font-weight: 600;
        }}
        QTabBar::tab:hover {{
            background: #EEF7FC;
            color: {p.brand_blue};
        }}
        QTabBar::tab:selected {{
            background: #F1F9FD;
            color: {p.blue_900};
            border-bottom: 3px solid {p.brand_celeste};
        }}
        QGroupBox {{
            background: #FFFFFF;
            border: 1px solid #D8E5EE;
            border-radius: 11px;
            margin-top: 12px;
            padding-top: 9px;
            color: {p.blue_900};
            font-weight: 700;
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 12px;
            padding: 0 7px;
            color: {p.blue_800};
        }}
        QTableView, QTableWidget {{
            background: #FFFFFF;
            alternate-background-color: #F7FAFD;
            gridline-color: #EDF2F6;
            color: {p.text};
            border: 1px solid #DBE7F0;
            border-radius: 6px;
            selection-background-color: #DDEFFA;
            selection-color: {p.blue_900};
        }}
        QHeaderView::section {{
            background: #EFF6FB;
            color: {p.blue_900};
            border: none;
            border-right: 1px solid #DFEAF2;
            border-bottom: 1px solid #D1DFEB;
            padding: 7px 8px;
            font-weight: 700;
        }}
        QPushButton {{
            min-height: 22px;
            background: #FFFFFF;
            color: {p.brand_blue};
            border: 1px solid #C8DBE9;
            border-radius: 7px;
            padding: 6px 10px;
            font-weight: 600;
        }}
        QPushButton:hover {{
            background: #EFF8FD;
            border-color: {p.brand_celeste};
        }}
        QPushButton:disabled {{
            background: #F3F6F8;
            color: #8C9CAA;
            border-color: #E0E8EC;
        }}
        QLineEdit, QComboBox, QDateEdit, QDoubleSpinBox, QSpinBox {{
            background: #FFFFFF;
            border: 1px solid #CFDEE9;
            border-radius: 7px;
            padding: 5px 8px;
            color: {p.text};
            selection-background-color: #DDEFFA;
        }}
        QLineEdit:focus, QComboBox:focus, QDateEdit:focus {{
            border: 1px solid {p.brand_celeste};
        }}
        QToolTip {{
            background: #002A4F;
            color: #FFFFFF;
            border: 1px solid {p.brand_celeste};
            padding: 8px 11px;
            font-size: 9pt;
        }}
        QFrame#homeContextCard, QFrame#homeModuleCard {{
            background: #FFFFFF;
            border: 1px solid #D8E5EE;
            border-radius: 11px;
        }}
        QFrame#homeModuleCard:hover {{
            background: #F7FCFF;
            border: 1px solid #90C8E7;
        }}
        QFrame#homeHero {{
            background: qlineargradient(
                x1:0, y1:0, x2:1, y2:0,
                stop:0 #00345F, stop:0.60 #005EB8, stop:1 #168AC7
            );
            border: 1px solid #2C85BC;
            border-radius: 12px;
        }}
        QFrame#portfolioMetricCard, QFrame#liquidityMetricCard,
        QFrame#riskMetricCard, QFrame#financialMetricCard,
        QFrame#macroMetricCard, QFrame#macroGovernanceCard,
        QFrame#marketMetricCard, QFrame#executiveMetricCard,
        QFrame#intelligenceMetricCard, QFrame#rateRiskMetricCard,
        QFrame#treasuryMetricCard {{
            background: #FFFFFF;
            border: 1px solid #D8E6EF;
            border-radius: 11px;
        }}
        """
