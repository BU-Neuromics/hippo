# Reference Loader Runtime ABC

## Why

`reference-loader-shape` finalized the **LinkML class** that records what
a reference loader populates (entity types, schema fragment, etc.). It
did not introduce the **Python runtime surface** that plugin authors
subclass and that the CLI invokes at install / upgrade time.

`hippo/design/sec2_architecture.md` §2.14 specifies that runtime surface
verbatim, and `hippo/design/sec9_decisions.md` D2.14.A–I lock the design
trade-offs. This change lands the concrete ABC, dataclass, fake fixture,
and entry-point discovery wiring so the rest of the §2.14 subissues
(install lifecycle, caching, CLI subcommands, fragment merge, upgrade)
have a foundation to build on.

## What Changes

### New runtime surface

- `hippo.core.loaders.reference.ReferenceLoader` — abstract base class
  with the verbatim §2.14 surface:
  - class-level: `name`, `description`, `subcommands_app`,
    `load_params_schema`
  - abstract methods: `versions()`, `entity_types()`,
    `schema_fragment()`, `load(client, version, params)`
  - default `upgrade(client, from_version, to_version, params)`
    delegating to `load(to_version, params)` (D2.14.F)
  - default `validate(user_artifact)` raising `NotImplementedError`
    with the loader name in the message (D2.14.B)
- `hippo.core.loaders.reference.LoadResult` — dataclass with
  `created`, `updated`, `unchanged`, `errors` counts, optional
  `error_messages: list[str]`, and `entity_type: str | None` for
  multi-class loaders.

### Test fixture

- `hippo.testing.fake_reference_loader.FakeReferenceLoader` — concrete,
  network-free `ReferenceLoader` over a tiny in-memory dataset.
  Implements every abstract method. Used as the discovery target for
  PTS-215.X3 / X5a / X5b tests.
- Registered as a `hippo.reference_loaders` entry point in
  `hippo/pyproject.toml` so the discovery path can pick it up without
  test-only metadata hacks.

### Discovery hardening

- `src/hippo/cli/commands/reference.py:discover_reference_loaders()`
  now eagerly instantiates each entry-point target and surfaces a
  `ReferenceLoaderRegistrationError` naming the offending entry point
  when the target is not a `ReferenceLoader` subclass. The prior
  silent-swallow behaviour is removed; broken entry points must be
  visible.

## Capabilities

### New Capabilities

- `reference-loader-runtime` — the runtime ABC, `LoadResult` envelope,
  fake fixture, and entry-point discovery contract that future
  subissues (caching, install lifecycle, fragment merge) extend.

### Modified Capabilities

- `hippo-reference-loaders` plugin entry point — now requires
  subclasses of the ABC; non-subclass entry points fail discovery
  loudly.

## Dependencies

- **Blocked by:** `reference-loader-shape` (LinkML class shape, closed).
- **Blocks:** PTS-215.X2 caching contract, .X3 install lifecycle,
  .X5a/.X5b fragment merge + CLI mounting.

## Acceptance

- `ReferenceLoader` importable from
  `hippo.core.loaders.reference`.
- ABC subclass-must-implement enforcement (TypeError on instantiating
  a concrete subclass missing any abstract method).
- Default `validate()` raises `NotImplementedError` with the loader
  name in the message.
- Default `upgrade()` invokes `load(to_version, params)`.
- `FakeReferenceLoader` discoverable through the
  `hippo.reference_loaders` entry-point group.
- A clear, typed error is raised when an entry point points at a class
  that is not a `ReferenceLoader` subclass; the message names the
  offending entry point.
- Targeted test suite green.
