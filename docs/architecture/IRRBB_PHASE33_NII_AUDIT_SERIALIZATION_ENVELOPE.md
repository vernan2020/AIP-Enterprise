# IRRBB Phase 33 — NII Audit Serialization Envelope / Codec Boundary

## Purpose

Phase 33 introduces a source-neutral boundary between the immutable `NIIRunAuditRecord`
and any future physical representation used by a persistence adapter.

The goal is to prevent storage technology, wire format, serializer implementation or
integrity mechanism from leaking into the IRRBB domain model.

## Core contract

`NIIRunAuditSerializationEnvelope` binds one serialized record to:

- `run_reference`;
- an explicit `NIIAuditSchemaVersion` from Phase 32;
- an explicit codec reference;
- an explicit integrity-mechanism reference;
- opaque payload bytes;
- an integrity digest for those exact bytes.

The envelope does not define JSON, MessagePack, protobuf, database columns or any
other physical encoding.

## Codec boundary

`NIIRunAuditRecordCodec` must explicitly declare:

- its stable reference;
- the schema versions it supports;
- how a record is encoded for one declared schema version;
- how a payload is decoded for one declared schema version.

Encoding fails closed when the codec does not support the current schema version.
Decoding fails closed when the envelope schema is not readable under the Phase 32
contract or is not supported by the supplied codec.

## Integrity boundary

`NIIRunAuditPayloadIntegrity` owns payload digest creation and verification.
Phase 33 deliberately does not prescribe SHA-256, HMAC, signatures or another
institutional mechanism.

Integrity verification happens before decoding. A tampered payload therefore cannot
reach the codec.

## Identity invariants

During decode, the service requires exact equality between:

- envelope codec reference and supplied codec reference;
- envelope integrity reference and supplied integrity reference;
- envelope `run_reference` and decoded record `run_reference`.

This prevents boundary substitution and record-identity substitution.

## Relationship with earlier phases

- Phase 29 defines immutable audited-run orchestration.
- Phase 30 defines persistence readiness requirements.
- Phase 31 provides executable repository conformance checks.
- Phase 32 governs schema evolution and readable versions.
- Phase 33 defines the serialization envelope and codec/integrity boundaries.

Passing Phase 33 behavior does not itself make a physical repository READY under
Phase 30.

## Explicit non-goals

Phase 33 does **not** implement or select:

- PostgreSQL or another database;
- SQLAlchemy ORM mappings;
- Alembic or another migration engine;
- JSON, MessagePack, protobuf or another physical serialization format;
- a mandated hashing/signature algorithm;
- encryption or key management;
- compression;
- retention policy;
- runtime DI, REST, API or UI integration;
- physical migration execution;
- external-source integrations blocked by Issue #66.

Future physical adapters must supply concrete codec and integrity implementations and
must still satisfy the Phase 30 and Phase 31 certification barriers.
