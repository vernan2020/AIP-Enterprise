# AIP Enterprise RC1 — Runtime institucional certificado

## Objetivo

AIP Enterprise debe iniciar en modo `CONFIGURED` usando las fuentes institucionales reales, sin depender de variables temporales de una ventana CMD ni de una instalación local de Git. Las credenciales y secretos permanecen fuera del repositorio.

## Rama certificada

- Repositorio: `vernan2020/AIP-Enterprise`
- Rama: `recovery/full-runtime-rc1-20260829`
- Checkpoint: `recovery/checkpoints/rc1-final-20260829`
- SHA-256 del payload: `491ade50a8c6f0c5e02458050dabc7d8ed69a2088c4fcf78aa793c27f1ea0c72`
- Partes declaradas: 33

`recovery/checkpoints` contiene únicamente este checkpoint final.

## Instalación / actualización sin Git

El script `scripts/recovery/install_certified_runtime.py` actualiza una copia existente de AIP sin requerir Git:

1. crea un ZIP de rollback del árbol `src` existente;
2. descarga desde GitHub el manifiesto y exclusivamente las 33 partes declaradas;
3. elimina fragmentos locales del checkpoint que no estén declarados;
4. verifica base64, SHA-256, rutas seguras y miembros críticos del archivo;
5. restaura el `src` certificado;
6. escribe `.aip_runtime_checkpoint.sha256` con el digest restaurado;
7. ejecuta `compileall` sobre `src`;
8. ejecuta el preflight `CONFIGURED`;
9. ejecuta la certificación funcional profunda.

La instalación solo reporta `PASS` si todas esas etapas terminan correctamente.

## Arranque normal

Usar `run_aip_configured.cmd` desde la raíz del proyecto.

El launcher consulta `scripts/recovery/runtime_checkpoint_status.py`. Si el marcador no existe, no coincide con el manifiesto o falta un miembro crítico, restaura el checkpoint certificado antes de abrir AIP. De esta forma, un archivo presente pero obsoleto no puede evitar la recuperación.

Una vez restaurado el digest correcto, los siguientes arranques no reescriben `src` innecesariamente.

## Fuentes institucionales

El `EnvironmentLoader` prioriza variables explícitas y, cuando no se suministran, resuelve las rutas institucionales no secretas desde el perfil Windows:

- Maestro de inversiones;
- Vector PiPCA;
- ICL bajo `Liquidez e Inversiones - Documentos/General/Análisis Financiero`;
- último corte Maestro disponible cuando no existe `AIP_DATA_CUTOFF_DATE` explícito.

## BCCR y Macro Intelligence

Las credenciales BCCR live son opcionales en runtime. Si están disponibles, AIP puede consultar BCCR usando la integración configurada y su caché. Si no están disponibles, Macro Intelligence debe utilizar únicamente el histórico oficial persistido y el escenario institucional aprobado; no se imputan observaciones ni se almacenan secretos en GitHub.

## ICL

ICL usa el archivo del corte exacto cuando existe. Si `AIP_ALLOW_PRIOR_SOURCE_DATE=true`, puede seleccionar el último archivo documental menor o igual al corte, nunca uno posterior. La certificación profunda exige una métrica ICL positiva, además de HQLA y capacidad MIL positivas.

## Certificación profunda

`scripts/recovery/certify_installed_runtime.py` valida después de la restauración:

- modo `CONFIGURED`;
- composición de dependencias;
- Portafolio con posiciones y valor de mercado positivo;
- Mercado operativo;
- Liquidez con HQLA, MIL e ICL positivos;
- Macro Intelligence con escenario disponible y al menos 12 filas de horizonte;
- servicio VeR resoluble y, cuando expone una operación sin argumentos, ejecutable;
- `EconomicIndicatorsProvider` registrado en el contenedor.

Esta certificación se ejecuta en la estación institucional porque depende de archivos, DuckDB y demás fuentes locales reales.

## Configuración local y secretos

`config/runtime.local.cmd` está ignorado por Git y puede contener overrides locales. Nunca versionar:

- `AIP_BCCR_TOKEN`;
- correo/nombre BCCR si se consideran datos internos;
- credenciales SQL Server;
- contraseñas;
- archivos `.env` reales;
- bases DuckDB locales.

`config/runtime.local.example.cmd` contiene únicamente ejemplos comentados y valores no secretos.
