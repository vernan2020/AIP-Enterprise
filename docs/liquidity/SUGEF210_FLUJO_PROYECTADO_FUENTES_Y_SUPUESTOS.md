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

La vinculación se efectúa contra el archivo CONFÍA del corte seleccionado, mediante hash SHA-256, ordinal del registro, ID XML, cuenta contable, moneda original, saldo principal y fecha de vencimiento. Las captaciones con tipo de cuenta fuera del catálogo **a plazo aprobado** se rechazan; los depósitos a la vista requieren supuestos conductuales separados. Los importes se contabilizan solo cuando pasan todos los controles y siempre como **flujo parcial de eventos seleccionados**, nunca como cobertura certificada de todas las captaciones, créditos, obligaciones o fuera de balance. La existencia de referencias textuales de aprobación no sustituye validar su firma y autenticidad fuera de la aplicación.
