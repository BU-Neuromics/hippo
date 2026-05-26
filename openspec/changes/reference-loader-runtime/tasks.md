# Tasks — `reference-loader-runtime`

## 1. Runtime ABC + LoadResult

- [x] 1.1 Add `src/hippo/core/loaders/reference.py` with the verbatim
  §2.14 `ReferenceLoader` surface and the `LoadResult` dataclass
  (counts + optional `error_messages` + `entity_type`).
- [x] 1.2 Default `upgrade()` delegates to `load(to_version, params)`
  (D2.14.F).
- [x] 1.3 Default `validate()` raises `NotImplementedError` carrying
  the loader name in the message (D2.14.B).

## 2. Test fixture

- [x] 2.1 Add `src/hippo/testing/fake_reference_loader.py` with
  `FakeReferenceLoader` implementing every abstract method against an
  in-memory dataset (no network).
- [x] 2.2 Add `src/hippo/testing/__init__.py` so the test helper module
  is importable.

## 3. Entry-point discovery

- [x] 3.1 Update `src/hippo/cli/commands/reference.py:`
  `discover_reference_loaders()` to:
  - eagerly instantiate each loaded class,
  - raise `ReferenceLoaderRegistrationError` (a typed `TypeError`
    subclass) when the loaded object is not a `ReferenceLoader`
    subclass, with the entry-point name in the message.
- [x] 3.2 Register the fake fixture as a `hippo.reference_loaders`
  entry point in `hippo/pyproject.toml`.

## 4. Tests

- [x] 4.1 ABC subclass-must-implement enforcement (TypeError when
  instantiating partial subclasses).
- [x] 4.2 `LoadResult` defaults and per-instance isolation of mutable
  fields.
- [x] 4.3 Default `validate()` raises `NotImplementedError` with the
  loader name in the message.
- [x] 4.4 Default `upgrade()` calls `load(to_version, params)`.
- [x] 4.5 `FakeReferenceLoader` is a `ReferenceLoader`, returns a
  `LoadResult`, and surfaces an unknown-version error path.
- [x] 4.6 `discover_reference_loaders()` returns a discovery dict
  carrying a constructed `ReferenceLoader` instance for a valid entry
  point.
- [x] 4.7 `discover_reference_loaders()` raises
  `ReferenceLoaderRegistrationError` when the entry point points at a
  non-subclass.

## 5. Documentation

- [x] 5.1 Reference §2.14 and D2.14.A–I from this change's
  `proposal.md`.

## 6. Acceptance

- [x] 6.1 ABC importable from `hippo.core.loaders.reference`.
- [x] 6.2 `FakeReferenceLoader` registered as an entry point.
- [x] 6.3 Targeted test suite green (`tests/core/test_reference_loader.py`,
  `tests/core/test_loaders.py`, `tests/cli/test_reference_ingest.py`).
- [ ] 6.4 Full Hippo test suite re-run after merge.
