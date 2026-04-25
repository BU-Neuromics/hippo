# Tasks — `reference-loader-shape`

## 1. Resolve design questions

- [x] 1.1 Multi-class loaders: `entity_type` is `multivalued: true` over `range: string`, declarative-only (provenance + discoverability); loader code owns runtime ingestion order; per-class metadata not modeled. Logged as Decision 9.5.F in `design/sec9_decisions.md` (PTS-67).
- [x] 1.2 `schema_fragment` load-order: fragment merges at plugin registration; ReferenceLoader instance validates against the merged SchemaView immediately after; either failure aborts plugin registration with a single error path. Logged as Decision 9.5.E in `design/sec9_decisions.md` (PTS-67).

## 2. Finalize `hippo_core` declaration

- [x] 2.1 Update `ReferenceLoader` in `src/hippo/schemas/hippo_core.yaml` with the full slot inventory (name, entity_type multivalued, source, schema_fragment, plus any others from §1.1).
- [x] 2.2 Bump `hippo_core` minor version.
- [x] 2.3 Validate via `linkml-validate`.

## 3. Migrate existing loaders

- [x] 3.1 Audit plugins registered under the `hippo.reference_loaders` entry point. No concrete plugin packages exist in this repo; `cli/commands/reference.py:discover_reference_loaders()` enumerates entry points at runtime but does not construct `ReferenceLoader` instances. §3.2 is a no-op today.
- [x] 3.2 No existing plugins to migrate — acceptance criterion §6.2 is trivially satisfied.
- [x] 3.3 Existing CLI discovery tests pass unchanged; no loader-shape tests were broken.

## 4. Introspection

- [x] 4.1 `SchemaRegistry` exposes `reference_loaders()` returning the list of registered loaders.
- [ ] 4.2 Optional REST endpoint (gated by `generated-rest-surface` scope): `GET /schemas/reference_loaders`. Deferred.

## 5. Documentation

- [x] 5.1 Update `design/reference_hippo_core.md` `ReferenceLoader` section from placeholder to the finalized inventory.
- [x] 5.2 Logged the two design resolutions in `sec9_decisions.md` as Decision 9.5.E (fragment merge timing) and Decision 9.5.F (entity_type semantics).
- [x] 5.3 Developer documentation in `design/reference_hippo_core.md` §"Developer responsibility — data-loading semantics" explicitly calls out the loader's responsibility for correct ingestion order. (Per Decision 9.5.F.)

## 6. Acceptance

- [x] 6.1 `ReferenceLoader` has a committed slot inventory in `hippo_core.yaml`.
- [x] 6.2 No existing plugin packages to migrate; acceptance trivially satisfied (see §3.1 note).
- [x] 6.3 Full suite green. 866 passed, 8 skipped (CLI integration tests skipped due to pre-existing system-binary environment mismatch; that failure pre-dates this change).
