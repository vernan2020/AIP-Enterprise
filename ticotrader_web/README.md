# TicoTrader Atlas · Inteligencia Financiera

Aplicación web privada de Análisis Financiero, Inteligencia Macroeconómica y Forecast Lab. Conserva los motores Python y los presentadores de AIP; la interfaz web usa la identidad TicoTrader y el logo del repositorio Portafolio 360.

## Arranque Windows

Ejecutar `INICIAR_TICOTRADER_WEB.cmd` desde la raíz del repositorio. Requiere Python 3.13 y acceso a Internet para instalar dependencias. El primer arranque solicita usuario y contraseña mediante entrada oculta; la clave se guarda como hash PBKDF2, nunca en texto plano. Abrir http://127.0.0.1:8080. No requiere PowerShell ni PySide6.

## Servidor privado / VPS

Desde la raíz:

```sh
python ticotrader_web/configure.py
# Configurar el dominio propio y TICOTRADER_COOKIE_SECURE=true en ticotrader_web/.env.
docker compose -f ticotrader_web/compose.yaml up -d --build
```

El servicio escucha solamente en 127.0.0.1:8080 del VPS. Colocar detrás del proxy HTTPS existente, con `TICOTRADER_ALLOWED_HOSTS` limitado al dominio elegido. El proxy debe preservar Host y transmitir X-Forwarded-Proto desde una dirección confiable. No reutilizar puertos, bases de datos ni variables de Portafolio 360. Verificar primero memoria, CPU, disco y puertos disponibles del VPS; no se ha inspeccionado su capacidad ni desplegado este servicio.

Se usa un solo proceso y una cola de cálculo para respetar el contexto mutable de AIP y evitar mezcla de cortes entre consultas. Los jobs se consultan asincrónicamente; los resultados temporales caducan después de una hora. La sesión dura ocho horas. En esta versión existe un único usuario administrador configurable; no se ofrece aún administración multiusuario ni SSO.

## Tokens personales

Ingresar a **Conexiones → BCCR · Token personal**, guardar la credencial y actualizar BCCR para verificarla. La respuesta muestra solo si existe una credencial; nunca devuelve el token. Se almacena en `~/.config/ticotrader/connections.json`, con archivo privado 0600 y reemplazo atómico. En Docker queda en el volumen `research-config`. También puede suministrarse mediante `TICOTRADER_BCCR_TOKEN` / `TICOTRADER_BCCR_EMAIL` o las variables compatibles `AIP_BCCR_*`. El token guardado en Conexiones tiene precedencia. No se han copiado credenciales institucionales o de otras aplicaciones.

SUGEF utiliza su API pública y no necesita token. `AIP_SUGEF_FINANCIAL_ENTITY_CODES` establece la entidad principal; el catálogo y los comparativos se obtienen por el motor original. El identificador inicial conserva el valor configurado en AIP y es modificable por el administrador.

## Cobertura de las páginas originales

| AIP | TicoTrader web | Motor reutilizado |
|---|---|---|
| Estados y cuentas; catálogo SUGEF | Tablas, búsqueda, filtros, históricos de cuentas | FinancialAnalysisPresenter |
| Comparativo de entidades | Tablas, barras y composición en porcentajes con detalle | FinancialAnalysisPresenter |
| KPIs históricos | Selector de serie, gráfico, tabla, Excel con gráfico | FinancialAnalysisPresenter |
| Comparativo gráfico | Hasta 5 entidades, 12/24/36 meses, 5 años, todo o fechas propias | build_comparison_view_model |
| Calificación | Ranking, cobertura, dimensiones, indicadores y reconciliación | Mismos cálculos y metodología de AIP |
| Calidad y trazabilidad | Corte, fuentes, estado, diagnósticos | Contratos originales |
| Indicadores macro observados | Tarjetas y matriz de observaciones | EconomicViewModel |
| Curvas TRI CRC/USD | Actual, anterior, variación y tabla | EconomicIndicatorsProvider |
| Forecast ejecutivo / matriz aprobada | Selector de escenario institucional, gráfico y matriz de siete variables | build_projection |
| Forecast Lab | Proyección, bandas 80/95%, modelos, métricas y pesos | build_forecast_lab |
| Transmisión | Explicación de macro → mercados → balance → resultados | Conserva la limitación del original: no hay motor de impacto publicado en esta página |
| Exportaciones | Excel, CSV, PNG, JSON vía API e impresión/PDF del navegador | Resultados del servidor; valores ausentes permanecen N/D |

Las composiciones se muestran como barras de participación en la web; el dato fuente no cambia. El PDF utiliza la impresión del navegador y corresponde a la pestaña visible. La estructura visual es nueva: no es una copia de widgets Qt.

El código base es `feature/v451-integrated-operational-20261028`, commit `c667b6184592499aa75333636feeb0dfea6b5e5f`. Se conserva `LICENSE.md` y la atribución del código original; el cambio de marca no transfiere derechos sobre el motor. El despliegue debe contar con autorización para reutilizarlo.

## Datos y aislamiento

No se incluyen datos privados, maestros de inversiones, XML CONFIA ni conexiones SQL de Coopealianza. El runtime web desactiva esas fuentes. Las fuentes que pertenecen a estas dos páginas (SUGEF, BCCR, históricos oficiales y escenario aprobado) conservan sus adaptadores. El modo DEMO está deshabilitado explícitamente.

La proyección institucional requiere un escenario aprobado disponible en la base de datos del nuevo servicio. No se copian bases institucionales. Sin escenario, se informa UNAVAILABLE. El token BCCR debe configurarse con una credencial autorizada del usuario; guardar el token no certifica una conexión exitosa.

## Validación y límites

- Suite web: autenticación, CSRF, aislamiento de sesiones, límites de consultas, exportación Excel con gráfico, neutralización de fórmulas CSV/Excel, credencial personal privada, valores faltantes y configuración real.
- Suite original: indicadores, calificaciones, reconciliación, análisis financiero, motores macro y universo de forecasting.
- Catálogo SUGEF real: respondió con 49 entidades durante la revisión.
- BCCR real: se comprobó el diagnóstico de credencial ausente; no está certificado con token personal todavía.
- Se revisó visualmente la pantalla de acceso Atlas mediante previsualización estática. El flujo autenticado completo no pudo revisarse en navegador porque el servicio de previsualización no tiene Python. El backend se prueba con TestClient y el JavaScript se verifica con Node.
- No se ha publicado en un VPS ni probado Docker en un servidor. Debe verificarse capacidad y conexión BCCR antes de declararlo operativo en producción.

```sh
PYTHONPATH=src:. python -m pytest tests/web -q
node --check ticotrader_web/static/app.js
```

## Forecast ligero para el piloto Atlas

Forecast admite únicamente TBP, tipo de cambio de compra/venta y TRI por moneda
(CRC/USD) y plazo. Se calcula una serie seleccionada por solicitud; no se ejecuta
una batería automática sobre todas las TRI. El catálogo macroeconómico conserva
sus indicadores de consulta.

El perfil Atlas usa NAIVE, DRIFT, AR(1) y AR(2), con hasta 12 orígenes de
backtesting por horizonte (1/3/6/12 meses), mínimo de 8 evaluaciones y hasta 3
modelos en el ensemble. Conserva los controles de fechas, datos faltantes y
selección del motor original. El universo general de AIP sigue con 16 modelos.
El perfil ligero no descarga variables SUGEF para Forecast porque sus candidatos
son univariados; Análisis Financiero conserva su conexión SUGEF. Los resultados
se reutilizan mientras no cambie la firma de fechas de las series históricas,
salvo actualización forzada. La API existente serializa los cálculos.

Esto reduce trabajo, no demuestra igual precisión que el universo completo:
la comparación fuera de muestra con históricos oficiales sigue pendiente.

Medición local del 5 de noviembre de 2026, Python 3.12, fixture sintético de 120
meses de `test_advanced_macro_forecasting.py`, BLAS/OMP limitados a un hilo:

| Serie | Segundos |
|---|---:|
| TBP | 0.531 |
| FX_SELL | 0.450 |
| TRI_CRC_12M | 0.483 |
| TRI_USD_12M | 0.588 |

Pico RSS del proceso: 182.6 MiB (incluye importaciones y cuatro cálculos
secuenciales). No incluye Streamlit, descarga de fuentes ni usuarios concurrentes.
Estas cifras no certifican el rendimiento del alojamiento. El fixture generó
advertencias de matriz singular en series deterministas; no se usa para evaluar
precisión financiera. Faltan la adaptación Streamlit, el límite duro de tiempo
por proceso y la prueba de carga del despliegue privado.
