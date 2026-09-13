# IRRBB / RTILB — Integración con AIP Enterprise RC1

## Objetivo

Integrar el núcleo IRRBB/RTILB certificado en `feature/irrbb-domain-blueprint-20260909` con el runtime RC1 certificado en `release/core-v1.0`, preservando la arquitectura source-neutral y sin activar fuentes físicas que carezcan de evidencia institucional aprobada.

## Baselines certificados

- Runtime RC1 base: `42f85575304076e6b49be7ad84b3bacc052f93ee`.
- Blueprint IRRBB fuente: `1b3deb18a2e9293916f70ff5b9c38593e09f1d2d`.

La integración se construye sobre el runtime RC1 y no mediante una fusión forzada de las historias divergentes.

## Estrategia de integración

Se transplantan únicamente subárboles IRRBB autocontenidos y sus pruebas:

- `src/aip/domain/irrbb`
- `src/aip/application/irrbb`
- `src/aip/product/configured/irrbb`
- `src/aip/ui/modules/rate_risk`
- pruebas unitarias e integración IRRBB correspondientes.

Los árboles compartidos de runtime, bootstrap, shell y UI no se reemplazan de forma masiva. Solo se incorporan los puntos de composición estrictamente necesarios y verificados por pruebas.

## Glue compartido mínimo

La integración añade únicamente:

1. soporte opcional de `ConfiguredIRRBBRuntimeDependencies` en `DemoApplicationFactory`;
2. composición opcional de `ConfiguredIRRBBComposition` en `ConfiguredApplicationFactory`;
3. resolución de `RunIRRBBAnalysis` e `IRRBBAnalysisRequestProvider` desde el container en `FinancialIntelligenceMainWindow`;
4. exposición de `Riesgo de Tasas · RTILB` en ribbon y sidebar;
5. registro explícito de la ruta `rate_risk` en la extensión de shell.

Si no se proporcionan dependencias IRRBB configuradas, `ConfiguredIRRBBComposition.compose()` no registra servicios IRRBB y el workspace permanece explícitamente sin runtime físico. Esta condición es deliberadamente fail-closed.

## Límite de Issue #66

La presente integración no satisface ni evita Issue #66. Permanecen fuera de activación productiva las fuentes físicas que requieren evidencia institucional real para:

- Obligaciones / Borrowings;
- Power BI / Fabric para `Credito` y `Certificados`;
- Inversiones, incluyendo gobierno de mapeo, reset contractual, completitud y benchmark/parity aprobado.

No se incorporan credenciales, tokens, secretos, identidades de workspace/dataset inventadas, datos contractuales ficticios ni mecanismos de fallback que sustituyan la evidencia requerida.

## No objetivos

Esta integración no:

- ejecuta autenticación Microsoft;
- consulta Power BI/Fabric;
- activa un adapter físico sin certificación;
- modifica DSN, credenciales o secretos;
- cambia infraestructura, deployment o failover;
- sustituye el runtime configurado existente;
- altera las metodologías HQLA, VaR, DV01, EVE o NII fuera del dominio IRRBB incorporado;
- resuelve Issue #66 mediante supuestos.

## Criterios de aceptación

El merge a `release/core-v1.0` solo es admisible si el mismo HEAD supera:

- Ruff;
- Black;
- mypy;
- compileall;
- unit tests;
- integration tests;
- coverage;
- package;
- runtime-source;
- pip-audit;
- Bandit;
- Recovery Runtime Validation Linux y Windows, incluyendo checkpoint, regresión institucional, desktop workspace y paquete Windows certificado.

La existencia del workspace RTILB en la UI no implica que las fuentes físicas bloqueadas por Issue #66 estén activas.

## Baseline final integrado

La integración certificada de IRRBB/RTILB fue incorporada a `release/core-v1.0` mediante el merge `0b5f099ba1ba450da73b3352f1b06d1deaf22f89`, cuyos padres son el runtime RC1 sincronizado `2d8f9bd62b07e610789ce525c94cdc138da08ecb` y el HEAD IRRBB certificado `2d7f33e6c558eba495277014e2492f82a5fdb305`.

Este registro final de certificación no modifica código productivo. Su propósito es forzar una validación completa y la generación de un paquete Windows certificado desde el release ya integrado, de modo que el artifact entregable y el baseline de release correspondan al mismo árbol funcional.
