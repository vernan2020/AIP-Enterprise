# AIP Enterprise RC1 — Runtime institucional recuperable

## Objetivo

AIP debe iniciar en modo `CONFIGURED` sin depender de variables temporales de una ventana CMD. Las rutas institucionales no secretas se resuelven desde el perfil Windows cuando existen. Las credenciales BCCR nunca se almacenan en GitHub.

## Arranque

Ejecutar `run_aip_configured.cmd` desde la raíz del proyecto. El cargador detecta automáticamente:

- raíz institucional del portafolio bajo el perfil Windows;
- raíz del vector PiPCA del año de valoración;
- raíz de ICL bajo `Liquidez e Inversiones - Documentos/General/Análisis Financiero`;
- último corte Maestro disponible cuando `AIP_DATA_CUTOFF_DATE` no está definido.

Las variables de entorno explícitas siempre prevalecen sobre los valores detectados.

## BCCR y continuidad operativa

Si `AIP_BCCR_TOKEN` está disponible, Macro Intelligence consulta BCCR y usa la caché optimizada. Si la credencial o la red no están disponibles, el proveedor usa únicamente el histórico oficial persistido en `database/aip.duckdb`; no imputa ni inventa observaciones. La UI identifica esta condición como histórico local.

## ICL

La fuente ICL usa el corte exacto cuando existe. Si no existe y `AIP_ALLOW_PRIOR_SOURCE_DATE=true` —valor institucional por defecto— selecciona el último archivo ICL con fecha documental menor o igual al corte. No utiliza archivos posteriores al corte.

## Escenario macroeconómico

Macro Intelligence muestra el último escenario `BASE-MACRO-INSTITUTIONAL` con estado `APPROVED` y sus drivers mensuales gobernados. El motor de transmisión financiera se mantiene separado y no se simula en la UI hasta que exista su servicio de dominio.

## Secretos

Nunca versionar `AIP_BCCR_TOKEN`, credenciales SQL, contraseñas ni archivos `.env` reales.
