# AIP Enterprise · Flujo proyectado de liquidez · SUGEF 2-10

**Estado: en desarrollo PREVIEW. No representa una certificación regulatoria ni sustituye ICL, RTILB, ΔEVE o ΔNII.**

## Ventanas de proyección

- Día 0: caja intradía y capacidad de financiación diaria.
- Días 1–7: apertura diaria.
- Días 8–30: apertura semanal, en cuatro tramos no solapados: 8–14, 15–21, 22–28 y 29–30.
- Después del día 30: dos ventanas mensuales calendario y después trimestres hasta cumplir un año.

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
