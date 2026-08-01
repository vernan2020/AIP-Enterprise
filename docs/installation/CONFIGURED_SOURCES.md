# Configured institutional sources

This document captures the safe, configuration-driven source settings for the configured product mode.

## Environment variables

- AIP_EXECUTION_MODE=CONFIGURED
- AIP_ENVIRONMENT=development
- AIP_DEMO_MODE_ENABLED=false
- AIP_SQLSERVER_ENABLED=false
- AIP_SQLSERVER_SERVER=
- AIP_SQLSERVER_DATABASE=
- AIP_SQLSERVER_AUTH_MODE=windows
- AIP_SQLSERVER_VIEW=VISTA_1514_1515_1516
- AIP_SQLSERVER_SCENARIOS=Reales,Presupuesto 2026%
- AIP_FOLDERWATCH_ENABLED=false
- AIP_PORTFOLIO_ROOT=
- AIP_PORTFOLIO_MASTER_PATTERN=Inversiones\\{year}\\maestro\\{month}\\*.xls*
- AIP_ICL_ROOT=
- AIP_ICL_FILE_PATTERN=ICL\\Reportes ICL\\*
- AIP_CURVES_ENABLED=false
- AIP_CURVES_WORKBOOK=
- AIP_VECTOR_ENABLED=false
- AIP_VECTOR_PATH=
- AIP_VECTOR_ROOT=
- AIP_VECTOR_DIRECTORY_ALIASES=vector,Vector,Vector Pip,vector pipca
- AIP_VECTOR_FILE_PATTERN=*.xls*
- AIP_VECTOR_SUPPORTED_EXTENSIONS=.xls,.xlsx
- AIP_ALLOW_PRIOR_SOURCE_DATE=false
- AIP_BCCR_ENABLED=false
- AIP_BCCR_BASE_URL=
- AIP_BCCR_TIMEOUT_SECONDS=30
- AIP_BCCR_RETRIES=3
- AIP_BCCR_CACHE_ENABLED=true
- AIP_INSTITUTIONAL_DATA_ROOT=

## Path resolution design

- Use pathlib.Path for all path handling.
- Expand environment variables and user home values before resolution.
- Support UNC paths, Windows paths with spaces, and accented characters.
- Avoid embedding personal profile paths in source code.
- Resolve relative logical paths below AIP_INSTITUTIONAL_DATA_ROOT when provided.
- For price-vector discovery, prefer AIP_VECTOR_ROOT when supplied; otherwise resolve the canonical year-based alias directory under the investment root.
- Supported vector aliases are configurable through AIP_VECTOR_DIRECTORY_ALIASES and default to vector, Vector, Vector Pip, and vector pipca.

## Source responsibilities

- Portfolio: portfolio master files, SQL Server, vector prices, and existing portfolio workflows.
- Market: BCCR, curves workbook, vector prices, and existing market workflows.
- Liquidity: SQL Server cash-flow data, ICL files, portfolio positions, and existing liquidity workflows.
- Executive: aggregate application-layer outputs only.
