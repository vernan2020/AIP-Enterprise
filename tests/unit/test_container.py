import pytest

from aip.core.container import Container, ServiceNotRegisteredError


class Service:
    pass


def test_register_and_resolve_instance() -> None:
    container = Container()
    service = Service()
    container.register_instance(Service, service)
    assert container.resolve(Service) is service


def test_factory_is_singleton_after_first_resolution() -> None:
    container = Container()
    container.register_factory(Service, lambda _: Service())
    assert container.resolve(Service) is container.resolve(Service)


def test_unregistered_service_raises() -> None:
    with pytest.raises(ServiceNotRegisteredError):
        Container().resolve(Service)
