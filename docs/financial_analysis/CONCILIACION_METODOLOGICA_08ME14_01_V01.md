# Conciliación de reglas 08ME14-01 V01, versión que rige 27/06/2025

Estado: **validación técnica**. Este documento es una lista de diferencias y decisiones de gobierno metodológico; **no implica autorización para sustituir** el motor financiero certificado.

## Criterio definitivo

La metodología institucional 08ME14-01 V01 rige la calificación oficial en AIP. La escala del Excel solo se conserva como referencia no normativa de conciliación, sin potestad de modificar la nota oficial.

## Precedencia de fuentes

1. La metodología 08ME14-01, versión 01, establece en su sección 4.4 **umbrales fijos**: AA >73.319; A desde 64.690; BB desde 56.067; B desde 47.442; CC por debajo. La función `FinancialEntityRatingService.grade` de AIP mantiene estos umbrales.
2. La matriz de agosto de 2026 usa una **escala dinámica** tomando 85%, 75%, 65% y 55% del máximo mensual observado. Es un escenario histórico de comparación, no una regla explícita del documento. Ejemplo de divergencia: 64.7975 puntos con máximo 86.675 se clasifica A bajo la escala fija, BB bajo el Excel.
3. En la sección 4 de la metodología, el P15 es el límite inferior y P85 el superior; el documento no indica expresamente que se deba imponer un piso de cero. La matriz Excel sí establece `max(P15,0)` para margen de intermediación, ROA y ROE; por ello el ajuste **se conserva solo en** `MatrixReferenceRatingService`, sin modificar `FinancialEntityRatingService`.
4. La sección 4.3 asigna rentabilidad 20% y 6.67% a cada uno de tres indicadores. Eso suma 20.01% por redondeo en la hoja, mientras la fórmula histórica certificada reparte 20/3; la diferencia debe explicarse antes de cualquier traslado a la nota principal.
5. **Contradicción interna**: el apartado 3.6.1 codifica 1=aplica supervisión proporcional; la nota al pie de 4.3 utiliza 1=regulación plena y 0=proporcional. Se requiere interpretación formal del propietario metodológico; no cambiar el binario por inferencia.
6. La nota del apartado 4.3 contempla dos indicadores binarios de 5% cada uno: regulación y garantía estatal. La garantía del Estado favorable corresponde a 1.
7. Los percentiles requieren una cohorte identificable y de corte único. La matriz de referencia contiene 38 entidades, pero el universo publicado por SUGEF puede variar. Evitar presentar umbrales relativos como definitivos si faltan pares o indicadores.
8. Las cinco celdas de liquidez que están vacías en la matriz, pero puntuadas con 10, **no** autorizan imputar automáticamente 10 a datos ausentes en AIP.

## Implementación de control, no normativa

- `ratings.py`: motor certificado **sin cambios**.
- `rating_score_audit.py`: recalcula puntuación y verifica nivel, peso, factor y contribución; advierte contradicciones de codificación y diferencia de escala.
- `matrix_reference_rating.py`: motor experimental de réplica del Excel con categoría relativa; **no representa por sí solo la metodología aprobada**.
- `matrix_sugef_adapter.py`: identifica la cohorte y alimenta el escenario experimental desde datos SUGEF.
- Interfaz `Calificación > Auditoría del puntaje` y `Cohorte metodológica`: verificación de fuentes y diferencias, con exportación CSV.

## Criterios pendientes

- Confirmación de que la sección 4.4 y sus umbrales son los parámetros de producción para todo corte, incluida su precisión de redondeo.
- Aclaración formal de la codificación binaria en el documento y en el catálogo institucional.
- Decisión documentada sobre si P15 de rentabilidad tiene piso cero (solo Excel o regla normativa).
- Política para datos faltantes, excepciones de liquidez y cohortes cambiantes, sin notas implícitas.
- Conciliación del registro de entidad identificada de forma discordante como FINANCIERA MONGE / FINANCIERA CREDILAT en la matriz de agosto.
- Confirmación del repositorio SUGEF y test funcional con corte real en la instalación PySide6.

**Prohibido fusionar esta rama hacia release o sustituir `ratings.py` mientras la lista esté abierta.**
