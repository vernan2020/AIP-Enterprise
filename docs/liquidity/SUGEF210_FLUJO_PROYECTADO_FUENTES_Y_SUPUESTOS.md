# AIP Enterprise · Flujo proyectado de liquidez · SUGEF 2-10

**Estado: en desarrollo PREVIEW. No representa una certificación regulatoria ni sustituye ICL, RTILB, ΔEVE o ΔNII.**

## Ventanas de proyección

- Día 0: caja intradía y capacidad de financiación diaria.
- Días 1–7: apertura diaria.
- Días 8–30: apertura semanal, en cuatro tramos no solapados: 8–14, 15–21, 22–28 y 29–30.
- Después del día 30: días 31–60, 61–90, 91–180, 181–270 y 271–365; son intervalos fijos de días desde el corte (no cierres mensuales calendario).

## Matriz de fuentes institucionales

| Fuente | Función en la proyección | Regla de control |
|---|---|---|
| NEC2024_Operaciones_5103.Nuevo.xml | Cobros de crédito | Fechas contractuales y amortizaciones certificadas. No convertir próximo pago en tabla de amortización completa |
| Pasivos_Cuentas_Contables_210.xml | Captaciones plazo/demanda | Plazo: vencimientos contractuales; vista: retiro conductual bajo supuesto aprobado |
| Pasivos_Cuentas_Contables_220_230_260_270_280.xml | Obligaciones | Pago principal/interés respaldado por cronogramas |
| Pasivos_Tabla_Vencimiento_Obligaciones.xml | Conciliación regulatoria | Rangos agregados NO son flujos diarios fechados |
| Maestro de inversiones | Cupones y amortizaciones | Importes y fechas certificados; mantener divisa de origen |
| Crediticio_InversionesActivas.xml | **Inversiones en cuentas corrientes fuera del Maestro** | Catálogo de cuentas contables aprobado, sin duplicados, saldo disponible y restricciones confirmados |
| Disponibilidades / ICL | Liquidez inicial | Conciliar y excluir fondos restringidos |
| HQLA, MIL, líneas fondeo | Capacidad contingente | No es caja hasta desembolso; verificar garantías y líneas no duplicadas |
| Compromisos por desembolsar, avales y contingentes | Fuera de balance | Uso potencial bajo escenarios y supuestos aprobados |
| Plan de negocios y presupuesto | Eventos de negocio | Supuesto, fuente, vigencia, fundamento y autorización documentados |

## Controles y trazabilidad

Cada flujo conserva la fuente, fecha de pago real, divisa, área del balance, sentido, identificador único y condición contractual o supuesto aprobado. La fecha de reprecio de RTILB no reemplaza la fecha de liquidación.

El XML de inversiones tiene campos CuentaContablePrincipal, SaldoPrincipal, TipoMonedaValorFacial, IdInstrumento, CodISIN y SerieInstrumento. No posee una marca universal que por sí sola pruebe que un saldo se pueda retirar el mismo día. La lectura produce un inventario por cuenta contable y divisa. No incorpora automáticamente valores a caja disponible ni supone que registros sin ISIN no se dupliquen con el Maestro. Se requiere conciliación con el Maestro, ICL y otras disponibilidades.

Las inversiones en cuenta corriente solo integran apertura de caja si existe aprobación de clasificación de cuenta, saldo libre de restricciones, disponibilidad operacional al corte, moneda certificada y conciliación de no duplicidad. Los saldos no se suman también como cobro futuro. Los escenarios de estrés no pueden crear salidas o entradas sin supuesto, fundamento y aprobación.

El reporte debe conservar CRC y USD separados, mostrar entradas y salidas por perímetro, acumulado, necesidad de fondeo diaria, posibles déficits sin financiación y con financiación confirmada, y advertencias de fuente incompleta. **N/D** significa dato no sustentado, no saldo cero.

## Pendiente para uso institucional

Integrar cronogramas realmente certificados de cartera, inversiones, captaciones y obligaciones; acreditar fondos a la vista, clasificar compromisos contingentes, confirmar caja y facilidades, probar corte real, conciliar y aprobar gobierno de supuestos. Hasta entonces, no publicar flujo integral como certificado.

## Validación real de caja inicial — PREVIEW

El módulo **Liquidez → Flujo proyectado · SUGEF 2-10** incorpora la opción **Validar caja inicial XML + Tesorería/ICL**. Se seleccionan dos documentos locales separados, sin cargar ninguno al repositorio GitHub:

1. Autorización de inversiones a la vista en JSON (`SUGEF210_SIGHT_OPENING_V1`), con `cutoff`, `xml_sha256`, `approved_account_codes`, `approved_currency_mapping`, `account_classification_approval`, `currency_mapping_approval_reference`, `opening_reconciliation_reference` y `approved_records`. Cada registro aprobado identifica la referencia XML, cuenta contable, moneda, principal XML, saldo realmente disponible, fecha de retiro, soporte de disponibilidad, no duplicación y liberación de restricciones.
2. Conciliación de Tesorería/ICL en JSON (`SUGEF210_BANK_OPENING_V1`) para el mismo corte, con `bank_opening_excluding_sight` (importes como cadenas decimales originales CRC y USD, **sin incluir** las inversiones que se agregarán después), `opening_certifications` en ambas monedas, `opening_reconciliation_reference`, `bank_or_icl_source_file` (ruta absoluta del documento de respaldo) y `bank_or_icl_source_sha256` (SHA-256 del archivo respaldatorio original).

La aplicación lee nuevamente los XML CONFÍA y el Maestro **del corte exacto** desde su configuración institucional. No acepta Maestro faltante, duplicado, con lectura no saludable, fuente XML con principal/cuentas inválidas ni diferencias de hash o período. Las entradas se verifican individualmente, se suman al saldo inicial solo después de pasar todos los controles y **no se suman como entradas futuras**. Si el escenario o corte cambia, la proyección cargada queda invalidada.

**Límite importante:** disponer de un archivo JSON con referencias de aprobación y un hash de respaldo no demuestra por sí mismo la autenticidad de firmas ni reconcilia automáticamente las cifras internas de un extracto bancario. Tesorería debe validar esos extremos y autorizar la conciliación original de manera independiente. Por esa razón, la proyección permanece expresamente **PARCIAL**, incluso si todas las inversiones a la vista pasan las validaciones del sistema; aún requieren integración los cronogramas de créditos, captaciones, obligaciones, inversiones con cupón, contingentes y supuestos aprobados.

### Vencimientos de principal del Maestro, autorizados por título

Opcionalmente, el JSON de autorizaciones de inversiones puede incluir `master_principal_authorization` con `master_sha256`, `approval_reference` y `approved_principal_records`. Cada registro contiene `cashflow_reference` exactamente igual a la referencia producida por el lector del Maestro, `payment_date` ISO, `original_principal` como texto decimal, `currency`, `settlement_availability_reference`, `restriction_clearance_reference` y `nonduplication_reference` únicos.

Se vuelve a leer el Maestro **original del mismo corte**; cada título debe conciliar importe principal, fecha contractual, moneda y SHA-256. Los títulos sin autorización individual se excluyen, nunca se reconocen por defecto; no se estiman cupones ni se usa el valor de mercado como principal. Los vencimientos autorizados se muestran como entradas futuras del activo en su banda diaria/semanal/mensual/trimestral correspondiente, siempre identificando la proyección como **parcial**.

## Ejecución directa desde CMD en Windows

Con el ZIP incremental instalado de forma segura en `C:\\Proyectos\\AIP-V451-PREVIEW`, ejecute desde la raíz PREVIEW:

```bat
DIAGNOSTICAR_LIQUIDEZ_SUGEF210_FLUJO.cmd --cutoff 2026-09-30 --scenario BASE --approval "RUTA_DEL_MANIFIESTO_APROBADO.json" --bank "RUTA_DE_CONCILIACION_TESORERIA_ICL.json"
```

El comando usa únicamente el entorno `CONFIGURED`, el XML institucional, el Maestro de fecha exacta y los soportes conservados localmente. Produce un JSON de **34 filas** (17 bandas por CRC/USD), informa fuentes faltantes y deja como `null` los flujos de bandas no documentadas. Un resultado de ejecución exitoso no constituye certificación regulatoria. Un error de fuente u aprobación retorna código 2 y una categoría, sin imprimir rutas internas ni secretos.

### Cronogramas fechados de cartera, captaciones y obligaciones

El flujo PREVIEW admite un apartado opcional `xml_contractual_schedule` dentro del JSON institucional `SUGEF210_SIGHT_OPENING_V1`, **solo si** existe un cronograma de pagos externo con importes y fechas originales, respaldado por una aprobación independiente. Los campos son `ledger_file` (ruta local absoluta al CSV), `ledger_sha256`, `approved_xml_sha256` (diccionario por fuente `CREDIT`, `CAPTACIONES` y/o `BORROWING`), `approved_currency_codes` (mapa de códigos originales a CRC/USD), `approved_term_deposit_codes` (tipos de cuenta de captación a plazo validados), `source_payment_approval`, `settlement_approval` y `nonduplication_reference`.

El CSV debe contener exactamente las columnas `source_key,source_ordinal,source_record_id,account_code,original_currency_code,currency,original_principal,maturity_date,payment_reference,payment_date,flow_type,amount,availability_reference`. Las fechas del CSV son ISO (`YYYY-MM-DD`) y los importes son decimales en la moneda original, sin colonizar. `flow_type` solo admite `PRINCIPAL` e `INTEREST`; cada `payment_reference` identifica una liquidación diferente. Se requiere cronograma de amortización principal **completo hasta el vencimiento**, incluso cuando parte de sus pagos ocurra después del horizonte de 365 días, y la suma de principal debe igualar el saldo de principal leído del registro XML. No se convierte automáticamente una `FechaVencimiento` en un pago bullet, no se calculan cuotas teóricas ni se deriva interés de tasas o de brechas RTILB.

La vinculación se efectúa contra el archivo CONFÍA del corte seleccionado, mediante hash SHA-256, ordinal del registro, ID XML, cuenta contable, moneda original, saldo principal y fecha de vencimiento. Adicionalmente se exige una misma entidad reportante en todas las fuentes seleccionadas y la ausencia de identificadores duplicados o vacíos en cada XML. Si ya se utiliza el cronograma contractual certificado integral procedente de RTILB, los pagos seleccionados de CONFÍA de esos mismos perímetros se bloquean para evitar duplicación. Las captaciones con tipo de cuenta fuera del catálogo **a plazo aprobado** se rechazan; los depósitos a la vista requieren supuestos conductuales separados. Los importes se contabilizan solo cuando pasan todos los controles y siempre como **flujo parcial de eventos seleccionados**, nunca como cobertura certificada de todas las captaciones, créditos, obligaciones o fuera de balance. La existencia de referencias textuales de aprobación no sustituye validar su firma y autenticidad fuera de la aplicación.

## Compromisos fuera de balance: uso contingente bajo escenarios aprobados

El PREVIEW dispone de una ruta adicional, opcional, para estimar salidas de fondos por compromisos **efectivamente no desembolsados** y legalmente exigibles, siempre sujeta a aprobación específica por escenario. El JSON principal de autorización del corte admite la entrada `offbalance_scenario`, con las rutas locales absolutas `register_file` y `approval_file`. Son archivos independientes del Maestro, los XML, la conciliación bancaria y el cronograma de pagos. **No se registran como caja disponible ni como obligaciones contractuales vencidas.**

El **registro original** es un CSV con encabezados exactos `commitment_reference,account_code,original_currency_code,native_currency,committed_limit,already_disbursed,restricted_amount,available_undrawn,expiration_date,category,nonduplication_reference,source_evidence_reference`. Para cada compromiso, se comprueba en moneda original que `committed_limit - already_disbursed - restricted_amount = available_undrawn`, que no esté vencido y que los identificadores y conciliaciones sean únicos. No se admiten moneda, cuenta ni categoría sin catálogo y soporte institucional aprobado.

El **archivo de políticas** es un JSON con `schema="SUGEF210_OFFBALANCE_SCENARIO_V1"`, `cutoff`, `scenario` (BASE, IDIOSYNCRATIC, SYSTEMIC o COMBINED), `source_sha256`, `approved_currency_codes`, `approved_account_codes`, `classification_approval`, `nonduplication_approval`, `currency_mapping_approval` y `approved_rules`. Cada regla debe contener `reference`, `exposure_category`, `factor` (decimal de 0 a 1), `projection_day` (0–365), `rationale`, `approval_reference`, `source_reference`, `version`, `approved_on`, `valid_from`, `valid_to` y `explicitly_approved=true`. No hay tasas de utilización o probabilidades predeterminadas. No se admiten reglas sin categorías en la fuente, categorías sin una regla, factores superiores al 100%, reglas vencidas ni fechas de salida posteriores al vencimiento del compromiso original.

El módulo emplea el motor común de supuestos `generate_approved_scenario_events`, registra la aprobación y su vigencia y emite únicamente movimientos `OFF_BALANCE / OUTFLOW / GOVERNED_ASSUMPTION`. El escenario seleccionado en la interfaz y en CMD debe corresponder **exactamente** al escenario de la autorización; cualquier cambio obliga a revalidar. El flujo exporta por separado las salidas contingentes y conserva CRC/USD. Aunque el registro y las reglas estén documentados, la proyección global sigue marcada como **PARCIAL**: estos eventos representan solo los compromisos incluidos y no acreditan cobertura integral, ni autenticidad criptográfica de firmas.

### Procedimiento de validación institucional en PREVIEW

1. Confirmar que la aplicación tenga configuradas las carpetas reales de XML CONFÍA y del Maestro para el **mismo corte**. La lectura de fuentes nunca se sustituye por datos ilustrativos.
2. Conservar en el entorno institucional el CSV original de compromisos, su hash SHA-256 y la autorización `SUGEF210_OFFBALANCE_SCENARIO_V1` para el escenario expresamente seleccionado. Identificar la evidencia legal, las cuentas y la conciliación de registros con operaciones ya desembolsadas.
3. Agregar las rutas absolutas del CSV y JSON en `offbalance_scenario.register_file` y `offbalance_scenario.approval_file` del manifiesto principal; mantener independientes los archivos de caja Tesorería/ICL y su respaldo documental.
4. Ejecutar el comando `DIAGNOSTICAR_LIQUIDEZ_SUGEF210_FLUJO.cmd --cutoff AAAA-MM-DD --scenario SYSTEMIC --approval RUTA_APROBACION.json --bank RUTA_ICL.json` y revisar el desglose por banda de `offbalance_cash_outflow_partial`, junto con `missing_evidence` y las conciliaciones en moneda de origen.
5. Repetir desde la pestaña **Flujo proyectado · SUGEF 2-10** de AIP PREVIEW. Cambiar el escenario invalida los resultados anteriores. Un escenario contingente no se usa para certificar tasas de retiro de depósitos ni la totalidad del perímetro fuera de balance.

Un hash confirma **integridad**, no veracidad económica ni firma de la aprobación. La aplicación debe mantenerse en estado **PARCIAL** hasta efectuar la conciliación real de saldos, confirmar legalmente los compromisos e integrar todos los demás flujos institucionales.

## Retiros de captaciones a la vista, con factores aprobados

El nuevo lector `sugef210_demand_deposit_runoff.py` utiliza directamente `Pasivos_Cuentas_Contables_210.xml` del corte configurado. El XML aporta **saldo y clasificación**, no una fecha cierta de retiro. Para activar una proyección conductual se añade en el manifiesto institucional `demand_deposit_runoff: {"approval_file": "RUTA_ABSOLUTA_APROBACION.json"}`, apuntando a un documento **independiente** con esquema `SUGEF210_DEMAND_RUNOFF_V1`.

La aprobación debe contener `cutoff`, `scenario`, `entity_id`, `xml_sha256`, `approved_sight_account_codes`, `approved_sight_type_codes`, `approved_currency_codes`, `classification_approval`, `currency_mapping_approval`, `nonduplication_approval` y `approved_rules`. Se seleccionan únicamente las filas originales donde **ambos** códigos —cuenta contable y tipo de cuenta— están expresamente aprobados. La referencia y el importe original de cada fila se conservan; las restantes quedan excluidas del cálculo, no son iguales a cero y tampoco acreditan cobertura integral.

Cada regla de `approved_rules` usa `exposure_category = "SIGHT:<CuentaContablePrincipal>:<TipoCuenta>"`, `factor` (decimal de 0 a 1), `projection_day` (0–365), `reference`, `rationale`, `approval_reference`, `source_reference`, `version`, `approved_on`, `valid_from`, `valid_to` y `explicitly_approved = true`. Son posibles varias fechas de retiro para una misma categoría, por ejemplo dentro de 1–7 días y en los tramos 8–30, **únicamente si ambas fechas están aprobadas y la suma de sus factores no supera el 100% del saldo original**. Las reglas con fechas duplicadas en la misma categoría se rechazan.

Se verifica entidad, mes, hash SHA-256, código original de moneda, saldo principal no negativo, identidad de registro y doble programación. Las filas de `CAPTACIONES` que ya se incluyeron en el cronograma contractual aprobado se bloquean: no pueden generar simultáneamente un vencimiento a plazo y un retiro conductual. Además del catálogo de cuentas, tipos y monedas, la aprobación exige `approved_native_balance_reconciliation`: una lista de grupos con `account_code`, `type_code`, `currency_source_code`, `currency`, `source_record_count`, `original_native_balance` y `reconciliation_reference`. La cantidad de registros y el saldo de **cada combinación exacta** deben coincidir con el XML original; una lista de cuentas y tipos no autoriza todas sus combinaciones automáticamente. Los factores de retiro se vinculan a `exposure_category = "SIGHT:<CuentaContablePrincipal>:<TipoCuenta>:<CRC|USD>"` para no aplicar en USD una regla destinada a CRC. Una `FechaVencimiento` contractual no vacía bloquea el tratamiento como depósito a la vista aunque el tipo haya sido mal clasificado.

El cálculo produce salidas `LIABILITY / OUTFLOW / GOVERNED_ASSUMPTION`, siempre separadas en CRC y USD. Al cambiar de corte o escenario, los resultados anteriores se invalidan. Este mecanismo no asigna tasas históricas, estrés, renovación ni hipótesis por defecto.

**Importante:** la aprobación documentada habilita solo las filas y reglas consideradas; los demás depósitos y el resto del flujo institucional permanecen como **fuentes pendientes**. Se deben verificar los saldos en su moneda de origen contra la conciliación contable del corte antes de presentar cualquier brecha agregada; **el resultado parcial no sustituye el ICL ni permite inferir que una captación no seleccionada tenga retiro cero**. La autenticidad de la política y la conciliación del saldo XML con contabilidad deben verificarse por Tesorería y Riesgos antes de considerar el resultado apto para uso regulatorio.

### Auditoría visible del XML 210 y retención del estado parcial

Después de cargar el flujo en **Liquidez → Flujo proyectado · SUGEF 2-10**, la pestaña **Conciliación captaciones vista** exhibe, para cada combinación de cuenta contable, clasificación y código original de moneda, el número de registros y el saldo nativo conciliado, junto al hash del XML que respalda esa verificación. La salida CMD añade `demand_deposit_reconciled_source_groups` al JSON para revisión por Tesorería y Riesgos. Ninguna fila se marca como cobertura integral. Si se cambia el corte o escenario, la información de aprobación anterior se invalida y se elimina de la tabla.

La exportación Excel de la conciliación incorpora la hoja **Captaciones vista XML210**, con esos mismos campos, sin aplicar tipo de cambio a importes nativos. Cuando el XML no fue autorizado o la proyección no fue cargada, la hoja permanece únicamente con encabezados: **sin datos no equivale a saldo cero**. La pestaña y la exportación reflejan estrictamente el corte y el escenario activos.

### Datos desconocidos: distinguir cero certificado de fuente no disponible

En el detalle de bandas y en la exportación **Flujo proyectado 365d**, un movimiento positivo documentado en un área no demuestra ausencia de movimientos en otra. Por eso, cuando la proyección es parcial, los subtotales nulos por **área y sentido** sin respaldo integral muestran `N/D` y no `0`, incluso cuando hay otros flujos documentados en esa misma banda y moneda. El GAP calculado sigue identificado como **parcial** y no sustituye el flujo institucional íntegro. Solo una proyección integral certificada permite presentar ceros de fuentes sin movimientos. Esta distinción también se verifica mediante pruebas automáticas de la pestaña de fuentes y del libro Excel, comparando un cobro de activo documentado contra pasivos y contingencias todavía no disponibles. No modificar este control con heurísticas ni completar fuentes no autorizadas con saldos XML.

## Vinculación gobernada del Plan Financiero 2026 al flujo

La sesión configurada ahora admite la sección opcional `financial_plan_scenario` dentro del
manifiesto existente `SUGEF210_SIGHT_OPENING_V1`. Incluye únicamente las rutas absolutas
locales `source_file` (libro institucional .xlsx) y `approval_file` (autorización independiente
de Tesorería/ALCO). Ambos se conservan fuera de GitHub y no pueden coincidir entre sí, con el
Maestro ni con otras fuentes o respaldos usados en la sesión.

La autorización JSON tiene `schema="SUGEF210_FINANCIAL_PLAN_ALLOCATION_V1"`,
`cutoff`, `scenario`, `source_sha256` y una lista no vacía `allocations`. Cada asignación
identifica: `driver`, `year`, `month`, `payment_date`, `currency`,
`incremental_native_amount`, `overlap_crc_amount`, `fx_crc_per_usd` (obligatorio
únicamente para USD), `fx_reference`, `source_sha256`, `assumption_id`,
`approval_reference`, `plan_document_version`, `rationale`,
`treasury_reconciliation_reference`, `nonduplication_reference`,
`valid_from`, `valid_to` y `explicitly_approved=true`.

Los importes financieros de la matriz son **millones equivalentes CRC**, no importes
contratados en una divisa. Por ello solo entra a las bandas la **porción incremental
aprobada**, expresada en moneda original y conciliada con la asignación mensual,
comprobando su equivalente CRC y el solapamiento reconocido. No se infiere reparto
diario, tipo de cambio, renovación de depósitos ni conversión de presupuesto a efectivo.
Los desembolsos de `Colocación bruta` generan salidas del activo; las emisiones nuevas
CAP, entradas del pasivo. La conciliación rechaza referencias repetidas, fechas vencidas,
autorizaciones de otros escenarios o cambios de SHA-256. Las asignaciones deben excluir
los flujos ya recogidos en cronogramas contractuales mediante una conciliación de
Tesorería documentada e independiente.

Sin esta sección opcional, se mantiene el comportamiento anterior: ninguna cifra del
presupuesto se incorpora al flujo proyectado. Incluso con asignaciones aprobadas,
el resultado permanece **PARCIAL** y se informa el número de eventos añadidos y el
hash del Plan Financiero en el diagnóstico CMD. La autenticidad material de firmas
y la reconciliación de los documentos de origen son controles institucionales externos.

## Cupones de inversiones — cronograma fechado de custodia

La proyección configurada admite ahora, de manera **opcional**, `investment_coupon_schedule`
en el manifiesto de apertura ya existente `SUGEF210_SIGHT_OPENING_V1`, con
`ledger_file`, `approval_file` y `custodian_document_file` (rutas institucionales
absolutas y distintas entre sí y de todas las demás fuentes del corte).

- El ledger es CSV UTF-8 con exactamente las columnas
  `master_principal_reference,payment_reference,payment_date,currency,amount,settlement_reference,nonduplication_reference`.
  La referencia principal corresponde a `MASTER:<SHA256>:<fila>:PRINCIPAL` tal como la
  produce el lector **original** del Maestro; no representa un cobro de principal.
- La autorización JSON independiente tiene el esquema
  `SUGEF210_MASTER_COUPONS_V1`, `cutoff`, `master_sha256`, `ledger_sha256`,
  `custodian_document_sha256`, `custodian_approval_reference`,
  `treasury_settlement_approval`, `nonduplication_approval` y
  `approved_payment_records`. Cada pago aprobado repite exactamente sus siete
  campos del CSV y añade `explicitly_approved=true`.
- Se verifica el mismo Maestro real del corte, identificador de fila original, moneda
  nativa y vida contractual del instrumento. El cupón tiene que tener fecha posterior
  al corte y no posterior al vencimiento original. Importes y fechas se **leen del
  cronograma de custodia** y se reconcilian contra la autorización; **nunca** se
  calculan usando TIR, tasa nominal, precio, duración o periodicidades supuestas.
- Hashes, referencias duplicadas, aprobaciones parciales, importes no finitos, fechas
  inconsistentes y documentos cruzados se rechazan. Se releen los hashes antes
  de finalizar para detectar modificaciones durante la conciliación.
- Los cupones se reportan como `ASSET/INFLOW/CONTRACTUAL`, por moneda original,
  dentro de las 17 bandas del mismo motor, también en Excel y diagnóstico CMD.
  Un cupón **no** sustituye un vencimiento de principal y no se contabiliza
  adicionalmente como caja inicial. El flujo resultante permanece **PARCIAL**.
- La autorización textual y un SHA-256 no autentican por sí mismos la firma de
  Tesorería o Custodia: el comprobante original debe verificarse institucionalmente.
  Solo los registros autorizados quedan incorporados; otros cupones siguen `N/D`
  en la evaluación de cobertura.

**Controles adicionales de integridad:** el hash del Maestro se comprueba antes y
después de la lectura y otra vez antes de ensamblar el flujo; cualquier cambio
invalida el corte. Por seguridad, se rechaza registrar más de un cupón para la
misma fila original del Maestro y fecha de pago, aunque las referencias del
ledger sean distintas. Las pruebas ficticias de estos rechazos se limitan al
entorno automatizado, nunca al PREVIEW institucional.

## Pestaña y Excel: conciliación de inversiones por moneda

La interfaz **Liquidez → Flujo proyectado → Conciliación inversiones** presenta, por
separado para **CRC y USD**, tres conceptos de distinta naturaleza:

- **Inversiones a la vista XML:** importes originales admitidos **únicamente en la apertura**,
  una vez aprobadas disponibilidad, ausencia de restricciones y conciliación con Maestro/ICL.
  Nunca se presentan como cobros de inversión futuros.
- **Principal del Maestro:** únicamente vencimientos individualmente aprobados, con
  eventos y monto dentro de 365 días, y número de eventos posteriores al horizonte.
- **Cupones de Custodia:** únicamente pagos documentados y aprobados con fechas
  contractuales; separados del principal y sin derivar intereses de tasas o precios.

Las filas incluyen estado de cobertura parcial y SHA-256 de la fuente aplicable.
Cuando falta aprobación o desglose sustentado, el importe o conteo es **N/D**,
nunca un cero fabricado. Si la autorización de origen corresponde a solo una moneda,
los registros de la otra moneda muestran cero **solo dentro de esa fuente ya
reconciliada**; ello no demuestra cobertura total del portafolio.

La exportación añade la hoja **Conciliacion inversiones** con importes y
conteos como celdas numéricas, y `N/D` como texto; el control de fórmulas de
Excel impide que un identificador no confiable se ejecute como fórmula.
El cambio de fecha o escenario invalida también esta pestaña. Antes de cargar
el flujo se reconcilian los eventos de principal y cupones de la sesión contra
los conteos originales del ensamblador; una discrepancia bloquea la visualización.

## Auditoría individual por evento y banda (17 × 2)

La sesión gobernada conserva cada evento reconocido del motor con la referencia
individual de operación, grupo y referencia de la fuente, fecha, importe en
moneda original, área contable, entrada/salida, evidencia, ID de supuesto
aprobado y banda asignada. El estado `OUTSIDE_365D / AFTER_365D` identifica
pagos posteriores al horizonte y evita asignarlos artificialmente al último
trimestre. Los registros de inversiones a la vista añadidos a la apertura no
son eventos futuros y **no** se incluyen en esta lista.

Antes de presentar el resultado se verifican los 34 renglones: conteos exactos
y ocho categorías (entradas/salidas de activos, pasivos, fuera de balance y
negocio), en CRC y USD sin compensación entre monedas. Las diferencias
bloquean el ensamblaje. La interfaz valida además referencia única, moneda,
importe positivo, estado de horizonte y conteos antes de modificar el tablero.

La pestaña **Trazabilidad por operación** muestra los primeros 300 flujos
ordenados por fecha y moneda, para evitar latencia excesiva. La hoja Excel
**Trazabilidad eventos** exporta **todos** los eventos admitidos, con importe
original en celda numérica y referencias de origen escapadas contra inyección
de fórmulas. La hoja Control registra el número de eventos exportados y
mostrados. Cambios de corte/escenario invalidan los datos visibles y su
exportación. No se modifica la fórmula del GAP ni se convierte una fuente
parcial en certificación integral.

## Instalación y ejecución de la herramienta REAL V4.5.1 (Windows CMD)

**No se instala Git en Windows ni se fusiona el PR ni se modifica el release.**
Usar exclusivamente el paquete ZIP incremental verificado por GitHub Actions
en `C:\\Proyectos\\AIP-V451-PREVIEW`. El ZIP se descarga desde el workflow
**AIP V4.5.1 Preview Incremental ZIP**, se extrae fuera de la instalación y
se ejecuta `INSTALAR_PREVIEW.cmd --dry-run` para comprobar la integridad.
Con AIP cerrado, `INSTALAR_PREVIEW.cmd` aplica los cambios con respaldo
automático; no modifica `.venv`, fuentes de datos, credenciales ni DuckDB.

Desde **CMD**, en la carpeta PREVIEW:

```bat
cd /d C:\Proyectos\AIP-V451-PREVIEW
VERIFICAR_LIQUIDEZ_SUGEF210_OPERATIVO.cmd --cutoff 2026-09-30
```

La verificación de solo lectura confirma los XML CONFÍA y Maestro exacto
del corte, sin proyectar caja no autorizada. `SOURCE_READY_APPROVALS_REQUIRED`
significa **fuentes detectadas, pendiente la conciliación**; no significa
flujo certificado. `BLOCKED_...` significa que se necesita corregir una
fuente, corte o autorización.

Con archivos reales **independientes y aprobados** por Tesorería/ALCO:

```bat
VERIFICAR_LIQUIDEZ_SUGEF210_OPERATIVO.cmd --cutoff 2026-09-30 --scenario BASE --approval "RUTA_AUTORIZACION_REAL.json" --bank "RUTA_CONCILIACION_ICL_REAL.json"
```

Una salida `PARTIAL_GOVERNED_PROJECTION` confirma que se ejecutó
el motor sobre las 17 bandas/34 filas; `PARTIAL_OPENING_ONLY_NO_FUTURE_FLOWS`
indica caja inicial, pero sin eventos contractuales aprobados.
No se imprimen rutas internas, certificados bancarios, importes o tokens.

Para abrir **la misma herramienta AIP**, sin demos:

```bat
INICIAR_AIP_LIQUIDEZ_SUGEF210.cmd
```

Navegar a **Liquidez → Flujo proyectado · SUGEF 2-10**. Usar
**Inspeccionar XML de inversiones** para el inventario y
**Validar caja inicial XML + Tesorería/ICL** para seleccionar los dos
archivos institucionales. La interfaz incluye conciliación de inversiones,
captaciones a la vista, cobertura de fuentes y trazabilidad por operación.
Un estado **PARCIAL** es correcto mientras falte cualquier perímetro.
Para corte o escenario distinto se necesitan autorizaciones específicas.

**Control operativo:** no se declara producción validada con datos reales
hasta ejecutar estos comandos en el equipo que contiene los XML, el Maestro,
el soporte de ICL y las conciliaciones originales y revisar sus resultados.

### Corte sugerido y preparación visible

El panel Liquidez/SUGEF 2-10 ahora sugiere inicialmente **el último día del
mes calendario anterior**, con edición manual. Esta sugerencia **no afirma
que el archivo mensual ya esté publicado**; un XML o Maestro faltante conserva
su estado de bloqueo, sin utilizar datos de un corte distinto. La pantalla
explica si el Maestro exacto fue localizado o si debe revisarse la ruta
institucional antes de seleccionar los dos documentos de autorización.
La carga inicial nunca activa caja ni flujos por el solo hecho de identificar
un mes cerrado.

### Autoprueba sin acceso a información institucional

Después de instalar el parche, en CMD ejecutar:

```bat
cd /d C:\Proyectos\AIP-V451-PREVIEW
VERIFICAR_LIQUIDEZ_SUGEF210_OPERATIVO.cmd --self-test
```

El verificador comprueba la capacidad de iniciar el panel Qt real, las 17 bandas
SUGEF 2-10, la disponibilidad de las pestañas de conciliación y trazabilidad,
y que los indicadores estén en **N/D** antes de cargar información. No lee
archivos de Tesorería, Maestro ni XML y nunca genera importes. El resultado
`RUNTIME_SELFTEST_OK` significa que el módulo gráfico está correctamente
instalado, **no** que el cálculo con fuentes reales o la integridad de los
insumos institucionales esté certificado. `BLOCKED_RUNTIME_SELFTEST`
separa un problema de instalación o dependencias de la falta de fuentes.
Después ejecutar `--cutoff 2026-09-30` para validar el origen real.

