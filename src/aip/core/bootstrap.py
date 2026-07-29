from __future__ import annotations

from dataclasses import dataclass

from aip.core.container import Container
from aip.core.paths import ProjectPaths
from aip.infrastructure.audit.service import AuditService
from aip.infrastructure.configuration.manager import ConfigurationManager
from aip.infrastructure.database.manager import DatabaseManager
from aip.infrastructure.logging.manager import LoggingManager


@dataclass(frozen=True, slots=True)
class BootstrapServices:
    container: Container
    configuration: ConfigurationManager
    logging: LoggingManager
    database: DatabaseManager
    audit: AuditService


class Bootstrap:
    def __init__(self, paths: ProjectPaths) -> None:
        self._paths = paths

    def initialize(self) -> BootstrapServices:
        self._paths.ensure()
        configuration = ConfigurationManager(self._paths.config)
        configuration.load()

        logging_manager = LoggingManager(configuration.settings.logging, self._paths.root)
        logging_manager.configure()
        logger = logging_manager.bind(component="BOOTSTRAP")
        logger.info("Inicio del bootstrap")

        database = DatabaseManager(configuration.settings.database, self._paths.root)
        database.initialize()

        audit = AuditService(logging_manager)
        audit.record("SYSTEM_BOOTSTRAP_COMPLETED", {"database": str(database.path)})

        container = Container()
        container.register_instance(ConfigurationManager, configuration)
        container.register_instance(LoggingManager, logging_manager)
        container.register_instance(DatabaseManager, database)
        container.register_instance(AuditService, audit)

        logger.info("Bootstrap completado")
        return BootstrapServices(container, configuration, logging_manager, database, audit)
