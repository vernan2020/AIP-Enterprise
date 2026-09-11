from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from aip.domain.intelligence.models import (
    FinancialIntelligenceContext,
    FinancialIntelligenceReport,
    IntelligenceEvidence,
    IntelligenceFinding,
    IntelligenceKind,
    IntelligenceSeverity,
)


class FinancialIntelligenceEngine:
    """Deterministic, auditable first layer of AIP financial intelligence."""

    _DURATION_MAX = Decimal("3.00")
    _DURATION_WARNING = Decimal("2.50")
    _GOVERNMENT_BCCR_MAX = Decimal("90.00")
    _BUCKET_UNDER_1_MAX = Decimal("37.00")
    _BUCKET_1_5_MAX = Decimal("48.00")
    _BUCKET_OVER_5_MAX = Decimal("30.00")
    _HHI_ANALYTICAL_HIGH = Decimal("2500")

    def analyze(self, context: FinancialIntelligenceContext) -> FinancialIntelligenceReport:
        findings: list[IntelligenceFinding] = []
        findings.extend(self._data_quality_findings(context))
        findings.extend(self._portfolio_findings(context))
        findings.extend(self._liquidity_findings(context))
        findings.extend(self._market_findings(context))
        findings.sort(key=self._sort_key)

        executive_summary = self._executive_summary(context, tuple(findings))
        return FinancialIntelligenceReport(
            generated_at=datetime.now(timezone.utc),
            cutoff_date=context.cutoff_date,
            mode="ANALYTICAL_DETERMINISTIC",
            coverage=("Portafolio", "Mercado", "Liquidez"),
            executive_summary=executive_summary,
            findings=tuple(findings),
            warnings=context.warnings,
        )

    def answer(
        self,
        report: FinancialIntelligenceReport,
        question: str,
    ) -> str:
        """Evidence-grounded local answer used until an external LLM is enabled."""

        normalized = question.strip().casefold()
        if not normalized:
            return report.executive_summary

        selected = report.findings
        if any(token in normalized for token in ("liquidez", "hqla", "icl", "mil")):
            selected = tuple(item for item in selected if item.domain == "Liquidez")
        elif any(token in normalized for token in ("duración", "duracion", "dv01", "portafolio")):
            selected = tuple(item for item in selected if item.domain == "Portafolio")
        elif any(token in normalized for token in ("mercado", "spread", "compra", "oportunidad")):
            selected = tuple(item for item in selected if item.domain == "Mercado")
        elif any(token in normalized for token in ("alerta", "riesgo", "incumpl")):
            selected = tuple(
                item
                for item in selected
                if item.severity
                in {
                    IntelligenceSeverity.CRITICAL,
                    IntelligenceSeverity.HIGH,
                    IntelligenceSeverity.ATTENTION,
                }
            )
        elif any(token in normalized for token in ("estrategia", "recomienda", "hacer")):
            selected = tuple(item for item in selected if item.recommendation)

        if not selected:
            return (
                "No existe una conclusión específica respaldada por la evidencia disponible "
                "para esa consulta en el corte actual. No se generará una respuesta sintética."
            )

        lines = [f"Análisis sobre el corte {report.cutoff_date:%d/%m/%Y}:"]
        for item in selected[:5]:
            lines.append(
                f"• [{item.severity.value}] {item.title}: {item.summary} "
                f"Recomendación: {item.recommendation}"
            )
        lines.append(
            "\nModo actual: análisis determinístico. Las conclusiones se generan únicamente "
            "desde evidencia calculada por AIP y no ejecutan operaciones."
        )
        return "\n".join(lines)

    def _portfolio_findings(
        self,
        context: FinancialIntelligenceContext,
    ) -> tuple[IntelligenceFinding, ...]:
        findings: list[IntelligenceFinding] = []

        duration = context.modified_duration
        if duration is not None and duration > self._DURATION_MAX:
            findings.append(
                self._finding(
                    "portfolio-duration-limit",
                    IntelligenceKind.ALERT,
                    IntelligenceSeverity.CRITICAL,
                    "Portafolio",
                    "Duración modificada supera el objetivo institucional",
                    f"La duración modificada es {duration:.2f} años, por encima del máximo de 3.00.",
                    "Reducir sensibilidad mediante vencimientos más cortos, ventas selectivas o cobertura, "
                    "validando previamente impacto en TIR, HQLA y resultado.",
                    (self._evidence("Duración modificada", f"{duration:.2f}", "Portafolio"),),
                    "Objetivo institucional de duración modificada ≤ 3 años",
                )
            )
        elif duration is not None and duration >= self._DURATION_WARNING:
            findings.append(
                self._finding(
                    "portfolio-duration-buffer",
                    IntelligenceKind.OBSERVATION,
                    IntelligenceSeverity.ATTENTION,
                    "Portafolio",
                    "Margen de duración reducido",
                    f"La duración modificada es {duration:.2f}; permanece dentro del objetivo, "
                    "pero con menor holgura frente al máximo de 3.00 años.",
                    "Evaluar nuevas compras por su efecto marginal en duración y DV01 antes de incrementar plazo.",
                    (self._evidence("Duración modificada", f"{duration:.2f}", "Portafolio"),),
                    "Objetivo institucional de duración modificada ≤ 3 años",
                )
            )

        concentration = context.government_bccr_share_percent
        if concentration is not None and concentration > self._GOVERNMENT_BCCR_MAX:
            findings.append(
                self._finding(
                    "portfolio-sovereign-concentration",
                    IntelligenceKind.ALERT,
                    IntelligenceSeverity.HIGH,
                    "Portafolio",
                    "Concentración Gobierno + BCCR supera el límite",
                    f"La concentración estimada es {concentration:.2f}% frente al máximo institucional de 90%.",
                    "Priorizar reinversión en emisores elegibles alternativos sin deteriorar HQLA ni exceder límites individuales.",
                    (
                        self._evidence(
                            "Gobierno + BCCR",
                            f"{concentration:.2f}%",
                            "Portafolio",
                        ),
                    ),
                    "Límite institucional Gobierno + BCCR ≤ 90%",
                )
            )
        elif concentration is not None and concentration >= Decimal("85"):
            findings.append(
                self._finding(
                    "portfolio-sovereign-concentration-buffer",
                    IntelligenceKind.OBSERVATION,
                    IntelligenceSeverity.ATTENTION,
                    "Portafolio",
                    "Concentración soberana próxima al límite",
                    f"Gobierno + BCCR representan {concentration:.2f}% del valor de mercado.",
                    "Reservar capacidad de límite para compras tácticas y evaluar diversificación en emisores permitidos.",
                    (
                        self._evidence(
                            "Gobierno + BCCR",
                            f"{concentration:.2f}%",
                            "Portafolio",
                        ),
                    ),
                    "Límite institucional Gobierno + BCCR ≤ 90%",
                )
            )

        bucket_rules = (
            (
                "< 1 año",
                context.duration_under_1_share_percent,
                self._BUCKET_UNDER_1_MAX,
                "portfolio-bucket-under-1",
            ),
            (
                "1 a 5 años",
                context.duration_1_5_share_percent,
                self._BUCKET_1_5_MAX,
                "portfolio-bucket-1-5",
            ),
            (
                "> 5 años",
                context.duration_over_5_share_percent,
                self._BUCKET_OVER_5_MAX,
                "portfolio-bucket-over-5",
            ),
        )
        for label, value, maximum, finding_id in bucket_rules:
            if value is None or value <= maximum:
                continue
            findings.append(
                self._finding(
                    finding_id,
                    IntelligenceKind.ALERT,
                    IntelligenceSeverity.HIGH,
                    "Portafolio",
                    f"Tramo {label} supera su máximo",
                    f"El tramo representa {value:.2f}% frente al máximo de {maximum:.2f}%.",
                    "Rebalancear gradualmente el tramo mediante vencimientos, reinversión y operaciones de mercado, "
                    "preservando liquidez y rendimiento.",
                    (self._evidence(f"Tramo {label}", f"{value:.2f}%", "Portafolio"),),
                    f"Límite institucional del tramo {label}: {maximum:.0f}%",
                )
            )

        if context.issuer_hhi is not None and context.issuer_hhi >= self._HHI_ANALYTICAL_HIGH:
            findings.append(
                self._finding(
                    "portfolio-hhi",
                    IntelligenceKind.OBSERVATION,
                    IntelligenceSeverity.ATTENTION,
                    "Portafolio",
                    "Concentración por emisor elevada",
                    f"El HHI del portafolio es {context.issuer_hhi:,.0f}.",
                    "Analizar el HHI junto con los límites por emisor antes de nuevas concentraciones. "
                    "Este umbral es una señal analítica, no un límite regulatorio.",
                    (
                        self._evidence(
                            "HHI por emisor",
                            f"{context.issuer_hhi:,.0f}",
                            "Portafolio",
                        ),
                    ),
                )
            )

        return tuple(findings)

    def _liquidity_findings(
        self,
        context: FinancialIntelligenceContext,
    ) -> tuple[IntelligenceFinding, ...]:
        findings: list[IntelligenceFinding] = []
        status = context.liquidity_policy_status.strip().casefold()
        if status and status not in {"healthy", "cumple", "compliant", "no evaluado"}:
            severity = (
                IntelligenceSeverity.CRITICAL
                if any(token in status for token in ("incumpl", "breach", "critical"))
                else IntelligenceSeverity.HIGH
            )
            findings.append(
                self._finding(
                    "liquidity-policy-status",
                    IntelligenceKind.ALERT,
                    severity,
                    "Liquidez",
                    "Estado de política de liquidez requiere atención",
                    f"AIP reporta el estado: {context.liquidity_policy_status}.",
                    "Revisar las métricas de liquidez que originan el estado antes de tomar decisiones de fondeo o inversión.",
                    (
                        self._evidence(
                            "Estado de política",
                            context.liquidity_policy_status,
                            "Liquidez",
                        ),
                    ),
                )
            )

        if context.hqla_restricted_count > 0:
            findings.append(
                self._finding(
                    "liquidity-restricted-hqla",
                    IntelligenceKind.OBSERVATION,
                    IntelligenceSeverity.ATTENTION,
                    "Liquidez",
                    "Existen posiciones restringidas para HQLA",
                    f"Se identifican {context.hqla_restricted_count} posiciones restringidas en la clasificación HQLA.",
                    "Revisar liberación, sustitución o vencimiento de posiciones restringidas para maximizar capacidad líquida utilizable.",
                    (
                        self._evidence(
                            "Posiciones HQLA restringidas",
                            str(context.hqla_restricted_count),
                            "Liquidez",
                        ),
                    ),
                )
            )

        return tuple(findings)

    def _market_findings(
        self,
        context: FinancialIntelligenceContext,
    ) -> tuple[IntelligenceFinding, ...]:
        if not context.opportunities:
            return ()
        top = context.opportunities[0]
        if top.spread_bp <= 0:
            return ()
        return (
            self._finding(
                "market-relative-value",
                IntelligenceKind.OPPORTUNITY,
                IntelligenceSeverity.OPPORTUNITY,
                "Mercado",
                "Oportunidad de valor relativo detectada",
                f"{top.series or top.issuer} presenta un spread de {top.spread_bp:.1f} pb dentro del universo analizado.",
                "Validar liquidez, riesgo de emisor, duración, HQLA y límites antes de considerar una compra o rotación. "
                "La señal de spread no constituye una orden de inversión.",
                (
                    self._evidence("Spread", f"{top.spread_bp:.1f} pb", "Mercado"),
                    self._evidence("Emisor", top.issuer or "N/D", "Mercado"),
                ),
            ),
        )

    def _data_quality_findings(
        self,
        context: FinancialIntelligenceContext,
    ) -> tuple[IntelligenceFinding, ...]:
        if context.data_quality_status.strip().upper() in {"HEALTHY", "OK", "READY"}:
            return ()
        return (
            self._finding(
                "data-quality",
                IntelligenceKind.ALERT,
                IntelligenceSeverity.HIGH,
                "Datos",
                "Calidad de datos no está en estado saludable",
                f"El estado de calidad reportado es {context.data_quality_status or 'N/D'}.",
                "No ejecutar una estrategia basada en estos resultados hasta revisar las advertencias y fuentes afectadas.",
                (
                    self._evidence(
                        "Calidad de datos",
                        context.data_quality_status or "N/D",
                        "AIP Runtime",
                    ),
                ),
            ),
        )

    @staticmethod
    def _executive_summary(
        context: FinancialIntelligenceContext,
        findings: tuple[IntelligenceFinding, ...],
    ) -> str:
        alerts = sum(
            item.severity
            in {
                IntelligenceSeverity.CRITICAL,
                IntelligenceSeverity.HIGH,
                IntelligenceSeverity.ATTENTION,
            }
            for item in findings
        )
        opportunities = sum(item.severity is IntelligenceSeverity.OPPORTUNITY for item in findings)
        if not findings:
            return (
                f"Corte {context.cutoff_date:%d/%m/%Y}: no se identificaron alertas ni oportunidades "
                "con las reglas activas. Esto no sustituye la revisión profesional de los módulos de AIP."
            )
        return (
            f"Corte {context.cutoff_date:%d/%m/%Y}: AIP identificó {alerts} señal(es) de atención "
            f"y {opportunities} oportunidad(es). Las prioridades se ordenan por severidad y cada "
            "recomendación conserva evidencia y referencia de política cuando corresponde."
        )

    @staticmethod
    def _evidence(metric: str, value: str, source: str) -> IntelligenceEvidence:
        return IntelligenceEvidence(metric=metric, value=value, source=source)

    @staticmethod
    def _finding(
        finding_id: str,
        kind: IntelligenceKind,
        severity: IntelligenceSeverity,
        domain: str,
        title: str,
        summary: str,
        recommendation: str,
        evidence: tuple[IntelligenceEvidence, ...],
        policy_reference: str = "",
    ) -> IntelligenceFinding:
        return IntelligenceFinding(
            finding_id=finding_id,
            kind=kind,
            severity=severity,
            domain=domain,
            title=title,
            summary=summary,
            recommendation=recommendation,
            evidence=evidence,
            confidence=Decimal("1.00"),
            policy_reference=policy_reference,
        )

    @staticmethod
    def _sort_key(finding: IntelligenceFinding) -> tuple[int, str, str]:
        rank = {
            IntelligenceSeverity.CRITICAL: 0,
            IntelligenceSeverity.HIGH: 1,
            IntelligenceSeverity.ATTENTION: 2,
            IntelligenceSeverity.OPPORTUNITY: 3,
            IntelligenceSeverity.NORMAL: 4,
        }
        return (rank[finding.severity], finding.domain, finding.title)
