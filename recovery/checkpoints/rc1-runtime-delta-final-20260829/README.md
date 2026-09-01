# AIP Enterprise RC1 — Runtime delta final

Este directorio contiene el delta binario certificado que materializa las capas recuperadas sobre la rama `recovery/full-runtime-rc1-20260829`.

- Formato: `tar.gz`
- SHA-256 esperado: `6791a23279590846ed00c298ffd2a9434ef251c67bb5b44ed669c9347382c29b`
- Alcance: Configured runtime, repositorios históricos/econométricos, Macro Intelligence, BCCR, Price Risk y bootstrap/UI crítica.
- El archivo debe extraerse únicamente dentro de la raíz del repositorio y solo contiene rutas bajo `src/`.

El delta reemplaza el checkpoint monolítico anterior que fue descartado después de que CI detectara corrupción LZMA pese a coincidir su digest.
