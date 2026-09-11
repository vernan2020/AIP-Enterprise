from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from threading import Barrier, Thread
from typing import Protocol

from aip.domain.irrbb.nii_run_audit import (
    NIIRunAuditRecord,
    NIIRunAuditRepositoryIntegrityError,
    NIIRunAuditRepositoryPutResult,
)
from aip.domain.irrbb.nii_run_audit_ports import NIIRunAuditRepository


class NIIAuditRepositoryConformanceCheck(str, Enum):
    """Executable repository behaviors covered by the Phase 31 conformance suite."""

    FIRST_WRITE = "FIRST_WRITE"
    IDEMPOTENT_REPEAT = "IDEMPOTENT_REPEAT"
    UNIQUE_RUN_REFERENCE = "UNIQUE_RUN_REFERENCE"
    ROUND_TRIP = "ROUND_TRIP"
    READ_AFTER_WRITE = "READ_AFTER_WRITE"
    ATOMIC_CONCURRENT_PUT_IF_ABSENT = "ATOMIC_CONCURRENT_PUT_IF_ABSENT"
    RECOVERY_REOPEN = "RECOVERY_REOPEN"
    INTEGRITY_DETECTION = "INTEGRITY_DETECTION"


@dataclass(frozen=True, slots=True)
class NIIAuditRepositoryConformanceFixture:
    """Valid records used to exercise one repository implementation."""

    primary: NIIRunAuditRecord
    conflicting: NIIRunAuditRecord
    secondary: NIIRunAuditRecord

    def __post_init__(self) -> None:
        if self.primary.run_reference != self.conflicting.run_reference:
            raise ValueError("Conformance conflicting record must reuse the primary run_reference")
        if self.primary == self.conflicting:
            raise ValueError("Conformance conflicting record must differ from the primary record")
        if self.secondary.run_reference == self.primary.run_reference:
            raise ValueError("Conformance secondary record must use a distinct run_reference")


class NIIAuditRepositoryConformanceHarness(Protocol):
    """Test-only lifecycle hooks supplied by a physical persistence adapter.

    ``reset`` must provision an empty isolated backing store for the next check.
    ``reopen_repository`` must reconnect to that same store without reconstructing
    data from the in-memory domain objects. ``corrupt_persisted_record`` must alter
    persisted bytes/state outside the repository API so integrity detection can be
    exercised fail-closed.
    """

    def reset(self) -> None: ...

    def repository(self) -> NIIRunAuditRepository: ...

    def reopen_repository(self) -> NIIRunAuditRepository: ...

    def corrupt_persisted_record(self, *, run_reference: str) -> None: ...


@dataclass(frozen=True, slots=True)
class NIIAuditRepositoryConformanceFailure:
    check: NIIAuditRepositoryConformanceCheck
    message: str


@dataclass(frozen=True, slots=True)
class NIIAuditRepositoryConformanceResult:
    adapter_reference: str
    passed: frozenset[NIIAuditRepositoryConformanceCheck]
    failures: tuple[NIIAuditRepositoryConformanceFailure, ...]

    def __post_init__(self) -> None:
        if not self.adapter_reference.strip():
            raise ValueError("NII audit repository conformance adapter_reference is required")
        failed = {failure.check for failure in self.failures}
        if self.passed & failed:
            raise ValueError("A conformance check cannot be both passed and failed")
        if self.passed | failed != frozenset(NIIAuditRepositoryConformanceCheck):
            raise ValueError("Conformance result must cover every executable check")

    @property
    def is_conformant(self) -> bool:
        return not self.failures


class NIIAuditRepositoryConformanceSuite:
    """Execute source-neutral behavioral checks against one physical repository."""

    @classmethod
    def run(
        cls,
        *,
        adapter_reference: str,
        harness: NIIAuditRepositoryConformanceHarness,
        fixture: NIIAuditRepositoryConformanceFixture,
    ) -> NIIAuditRepositoryConformanceResult:
        if not adapter_reference.strip():
            raise ValueError("NII audit repository conformance adapter_reference is required")

        checks = (
            cls._first_write,
            cls._idempotent_repeat,
            cls._unique_run_reference,
            cls._round_trip,
            cls._read_after_write,
            cls._atomic_concurrent_put_if_absent,
            cls._recovery_reopen,
            cls._integrity_detection,
        )
        passed: set[NIIAuditRepositoryConformanceCheck] = set()
        failures: list[NIIAuditRepositoryConformanceFailure] = []
        for check in checks:
            check_name, message = check(harness=harness, fixture=fixture)
            if message is None:
                passed.add(check_name)
            else:
                failures.append(
                    NIIAuditRepositoryConformanceFailure(check=check_name, message=message)
                )

        return NIIAuditRepositoryConformanceResult(
            adapter_reference=adapter_reference,
            passed=frozenset(passed),
            failures=tuple(failures),
        )

    @staticmethod
    def _fresh_repository(
        *, harness: NIIAuditRepositoryConformanceHarness,
    ) -> NIIRunAuditRepository:
        harness.reset()
        return harness.repository()

    @classmethod
    def _first_write(
        cls,
        *,
        harness: NIIAuditRepositoryConformanceHarness,
        fixture: NIIAuditRepositoryConformanceFixture,
    ) -> tuple[NIIAuditRepositoryConformanceCheck, str | None]:
        check = NIIAuditRepositoryConformanceCheck.FIRST_WRITE
        repository = cls._fresh_repository(harness=harness)
        result = repository.put_if_absent(record=fixture.primary)
        if not result.created or result.record != fixture.primary:
            return check, "First put_if_absent must create and return the submitted record"
        return check, None

    @classmethod
    def _idempotent_repeat(
        cls,
        *,
        harness: NIIAuditRepositoryConformanceHarness,
        fixture: NIIAuditRepositoryConformanceFixture,
    ) -> tuple[NIIAuditRepositoryConformanceCheck, str | None]:
        check = NIIAuditRepositoryConformanceCheck.IDEMPOTENT_REPEAT
        repository = cls._fresh_repository(harness=harness)
        repository.put_if_absent(record=fixture.primary)
        repeated = repository.put_if_absent(record=fixture.primary)
        if repeated.created or repeated.record != fixture.primary:
            return check, "Exact repeat must be non-creating and return the persisted record"
        return check, None

    @classmethod
    def _unique_run_reference(
        cls,
        *,
        harness: NIIAuditRepositoryConformanceHarness,
        fixture: NIIAuditRepositoryConformanceFixture,
    ) -> tuple[NIIAuditRepositoryConformanceCheck, str | None]:
        check = NIIAuditRepositoryConformanceCheck.UNIQUE_RUN_REFERENCE
        repository = cls._fresh_repository(harness=harness)
        repository.put_if_absent(record=fixture.primary)
        conflicting = repository.put_if_absent(record=fixture.conflicting)
        if conflicting.created or conflicting.record != fixture.primary:
            return check, "Conflicting reuse of run_reference must preserve and return the first record"
        return check, None

    @classmethod
    def _round_trip(
        cls,
        *,
        harness: NIIAuditRepositoryConformanceHarness,
        fixture: NIIAuditRepositoryConformanceFixture,
    ) -> tuple[NIIAuditRepositoryConformanceCheck, str | None]:
        check = NIIAuditRepositoryConformanceCheck.ROUND_TRIP
        repository = cls._fresh_repository(harness=harness)
        repository.put_if_absent(record=fixture.secondary)
        loaded = repository.get_by_run_reference(run_reference=fixture.secondary.run_reference)
        if loaded != fixture.secondary:
            return check, "Persisted audit record must survive an exact domain round-trip"
        return check, None

    @classmethod
    def _read_after_write(
        cls,
        *,
        harness: NIIAuditRepositoryConformanceHarness,
        fixture: NIIAuditRepositoryConformanceFixture,
    ) -> tuple[NIIAuditRepositoryConformanceCheck, str | None]:
        check = NIIAuditRepositoryConformanceCheck.READ_AFTER_WRITE
        repository = cls._fresh_repository(harness=harness)
        repository.put_if_absent(record=fixture.primary)
        loaded = repository.get_by_run_reference(run_reference=fixture.primary.run_reference)
        if loaded != fixture.primary:
            return check, "Successful put_if_absent must be immediately visible to a subsequent read"
        return check, None

    @classmethod
    def _atomic_concurrent_put_if_absent(
        cls,
        *,
        harness: NIIAuditRepositoryConformanceHarness,
        fixture: NIIAuditRepositoryConformanceFixture,
    ) -> tuple[NIIAuditRepositoryConformanceCheck, str | None]:
        check = NIIAuditRepositoryConformanceCheck.ATOMIC_CONCURRENT_PUT_IF_ABSENT
        harness.reset()
        barrier = Barrier(2)
        results: list[NIIRunAuditRepositoryPutResult] = []
        errors: list[BaseException] = []

        def write(record: NIIRunAuditRecord) -> None:
            try:
                repository = harness.repository()
                barrier.wait()
                results.append(repository.put_if_absent(record=record))
            except BaseException as exc:  # pragma: no cover - adapter failures are reported below
                errors.append(exc)

        threads = (
            Thread(target=write, args=(fixture.primary,)),
            Thread(target=write, args=(fixture.conflicting,)),
        )
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        if errors:
            return check, f"Concurrent put_if_absent raised {type(errors[0]).__name__}: {errors[0]}"
        if len(results) != 2 or sum(result.created for result in results) != 1:
            return check, "Exactly one concurrent writer must create the run_reference"
        persisted = harness.reopen_repository().get_by_run_reference(
            run_reference=fixture.primary.run_reference
        )
        if persisted is None or any(result.record != persisted for result in results):
            return check, "Concurrent writers must converge on the single persisted record"
        return check, None

    @classmethod
    def _recovery_reopen(
        cls,
        *,
        harness: NIIAuditRepositoryConformanceHarness,
        fixture: NIIAuditRepositoryConformanceFixture,
    ) -> tuple[NIIAuditRepositoryConformanceCheck, str | None]:
        check = NIIAuditRepositoryConformanceCheck.RECOVERY_REOPEN
        repository = cls._fresh_repository(harness=harness)
        repository.put_if_absent(record=fixture.secondary)
        reopened = harness.reopen_repository()
        loaded = reopened.get_by_run_reference(run_reference=fixture.secondary.run_reference)
        if loaded != fixture.secondary:
            return check, "Reopened repository must recover the previously persisted audit record"
        return check, None

    @classmethod
    def _integrity_detection(
        cls,
        *,
        harness: NIIAuditRepositoryConformanceHarness,
        fixture: NIIAuditRepositoryConformanceFixture,
    ) -> tuple[NIIAuditRepositoryConformanceCheck, str | None]:
        check = NIIAuditRepositoryConformanceCheck.INTEGRITY_DETECTION
        repository = cls._fresh_repository(harness=harness)
        repository.put_if_absent(record=fixture.primary)
        harness.corrupt_persisted_record(run_reference=fixture.primary.run_reference)
        reopened = harness.reopen_repository()
        try:
            reopened.get_by_run_reference(run_reference=fixture.primary.run_reference)
        except NIIRunAuditRepositoryIntegrityError:
            return check, None
        except BaseException as exc:
            return check, (
                "Corruption must raise NIIRunAuditRepositoryIntegrityError, got "
                f"{type(exc).__name__}: {exc}"
            )
        return check, "Corrupted persisted audit data must not be returned as a valid record"
