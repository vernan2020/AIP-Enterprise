# AIP Enterprise Local — Portfolio Advanced Analytics (Fase 1)

## Propósito
Integrar a la aplicación de escritorio PySide6 un conjunto de herramientas de decisión sobre inversiones, tomando como referencia funcional el producto privado TicoTrader Portafolio 360, **sin depender de su API o copiar su código privado**.

## Inventario contrastado (repositorios, 2026-10-11)

| Capacidad | TicoTrader develop | AIP release/core-v1.0 | Acción AIP |
|---|---|---|---|
| Composición, concentración, valuación y P&L | Funciones de cartera y análisis de venta | Panel institucional, valuación y comparación | Ampliar por serie, emisor, posición y fecha |
| Rotación/optimización de títulos | `OptimizeInternalRotation`: objetivos duración, DV01, rendimiento, concentración, balanceados; simula cambios de renta fija de la misma moneda | Sin comparador equivalente de rotaciones | Implementar adaptador AIP de escenario **no transaccional**, sujeto a política |
| Optimización Markowitz | **No se verificó un optimizador de frontera eficiente en develop**; no confundir la rotación existente con Markowitz | No implementada en UI | Nuevo motor separado de media-varianza con insumos válidos, restricciones y backtesting |
| Simulador compra/venta | `PortfolioTradeSimulator`, análisis de venta y cupón | Simuladores VaR; datos de portafolio disponibles | Simulador bruto/neto con intereses devengados, comisiones y FX si aplica |
| Apalancamiento y márgenes | Modelo de venta apalancada | No habilitado como flujo de Portafolio | Módulo opcional con mensaje explícito **sin posiciones apalancadas** cuando corresponda |
| Stress testing | Escenarios de renta fija y acciones/ETF | DV01, escenarios tasa, VaR, stress liquidez | Consolidar sensibilidad de precio y shocks para cartera |
| Riesgo por título | Key-rate duration, equity/ETF risk | Duración, DV01, VaR | Puente por serie y emisor; marcar insumos no disponibles |
| Curvas, spreads, valor relativo | Análisis soberano/curvas | Mercado y curvas | Recomendaciones con fuente, fecha y limitaciones |
| Alertas y reportes | Evaluación de escenarios, impactos y reportes | Reportes, UI ejecutiva | Alertas configurables y reporte de simulación trazable |

## Restricciones y decisiones de producto

1. **Prioridad local.** PySide6, entorno Windows/CMD. Esta rama no es SaaS ni exige servidor nuevo.
2. **Integración por servicios, no porting literal.** TicoTrader es privado y AIP es público: no copiar datos, secretos, conectores corporativos, componentes internos ni código entre repositorios hasta definir autorización/licencia y seguridad. La funcionalidad se especifica y desarrolla de forma original en AIP.
3. **Sin cálculos inventados.** Para Markowitz son indispensables series temporales alineadas de retorno total ajustadas por flujos, denominación homogénea, frecuencia, fecha, matriz de covarianza y condiciones de cobertura. **No usar rendimientos al vencimiento (YTM) como retornos históricos**, ni fabricar correlaciones.
4. **Política institucional como restricción.** Verificar límites vigentes por categoría/emisor, tipo de moneda, tramos de vencimiento, duración y liquidez; nunca asumir que una propuesta que maximiza rendimiento es admisible por política.
5. **No ejecutar transacciones.** Los resultados son propuestas y simulaciones; compra/venta requiere decisión humana.
6. **Sin cambios retroactivos** a servicios certificados VaR, DV01, ALM, IRRBB o sus métodos; resultados antes/después reproducibles.
7. **No bloquear el hilo Qt.** Cálculos asíncronos, cancelación/cierre seguro, invalidación de resultados por corte y soporte de falta de datos.
8. **Control de calidad.** Pruebas matemáticas con fixtures sintéticos *solo en tests*; aceptación institucional exclusivamente con datos autorizados, equivalencia y gates CI/Security/Recovery.

## Orden de entrega

### Slice 1 — Diagnóstico de datos y capacidades
- Contrato `PortfolioOptimizationInputs`: corte, series/ISIN, moneda, precios/retornos históricos, universo elegible, política, restricciones y fuente.
- Preflight de cobertura por título y de matriz temporal; estados `READY`, `INSUFFICIENT_HISTORY`, `MISSING_RETURNS`, `INCOMPATIBLE_CURRENCY`, `POLICY_UNVERIFIED`.
- UI institucional «Optimización», visible pero sin mostrar fronteras/carteras simuladas cuando no haya series válidas.

### Slice 2 — Motor Markowitz (original)
- Estimaciones de retorno esperado y covarianza explícitas, regularización justificada, cartera mínima varianza y frontera eficiente con restricciones convexas.
- Límites por título, emisor, categoría, moneda y liquidez, además de presupuesto y no ventas en corto.
- Métricas ex-ante y ex-post, verificación de restricciones y robustez ante colinealidad; escenarios alternativos.
- Separar **optimización estadística de retornos totales** de rotación de bonos guiada por rendimiento, duración y DV01.

### Slice 3 — Rotación interna y simuladores
- Escenarios antes/después: títulos a vender/comprar, flujo de caja, costos, interés corrido, cambios en duración, DV01, rendimiento, exposición y cumplimiento.
- Restricción por universo disponible, fecha/precios de mercado y emisor, sin replicar dependencias TicoTrader.

### Slice 4 — Herramientas complementarias
- Rentabilidad histórica, contribuciones, estrés, ranking de concentración, curvas/spreads, alertas, reportes y exportación Excel.
- Ensayos de regresión con cartera real autorizada, pruebas de memoria/latencia, benchmark y control de cierre Qt.

## Separación de desarrollo
Esta rama es independiente del PR #343 `feature/ux-v4-5-1-performance-responsiveness`. No integrar cambios de UI avanzada ni su motor en `release/core-v1.0` mientras el desempeño actual no esté estabilizado y certificado.


## Herramienta adicional — Consumo de capital del portafolio (SUGEF 3-06 v75)

- Fuente pública: SUGEF 3-06, versión 75 (26-jun-2026), Capítulo III, artículos 41 a 48.
- Motor inicial: `PortfolioCapitalConsumptionService` calcula **APR de riesgo de crédito de inversiones**, posición a posición, mediante `exposición regulatoria aprobada × ponderador`.
- Ponderaciones referenciales: BCCR/Gobierno CRC 0%; calificaciones 0-6: 0%, 10%, 25%, 50%, 75%, 90%, 100%; no calificado: 100%; recompra (pacto de reventa) 75%.
- La exposición regulatoria debe proceder de la cuenta/valuación normativa aprobada; **no presumir que equivale al precio de mercado**.
- Coocique es el emisor sin calificación reportado en el portafolio actual: **dato declarado por el usuario, a corroborar en el maestro institucional por corte**. No tratarlo como lista permanente/exhaustiva.
- El usuario indicó para soberanos USD '75% o 100%'. La versión 75 muestra derogada la regla histórica de 10% para soberanos USD; la clasificación exacta requiere instrumento, calificación aplicable y versión normativa. **No fijar automáticamente ninguno de esos porcentajes.**
- El APR de crédito de inversiones es solo una parte del denominador de suficiencia patrimonial; no equivale por sí solo al capital mínimo requerido, ni cubre riesgo de precio, tipo de cambio u operacional.
- Módulo UI previsto: detalle por ISIN/serie/emisor/calificación/moneda/ponderador/APR; clasificación auditada, totales, antes/después de transacciones y restricción de consumo de capital para Markowitz/rotaciones.
- Fase siguiente: adaptador de datos reales, selector de versión normativa y reglas de rating/emisor, parámetros de capital base y denominador institucional; control de calidad y comparación con SUGEF antes de activar reportes regulatorios.
