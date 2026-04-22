# Wave 3 Progress — Overnight Autonomous Session (2026-04-22)

Morning summary for the user who went to bed mid-Wave-2. Wave 3 work
executed autonomously per the scoping contract: full on
`validation-tiering-clarification` and `typed-client`;
`reference-loader-shape` explicitly skipped; non-sec9 scaffolds
(`drs-self-uri`, `reference-auto-discovery`, `unified-ingestion-framework`)
untouched.

## What landed

### `validation-tiering-clarification` — commit `b1412c6`

Formalizes the sec9 §9.9 three-tier pipeline (LinkML → CEL → Python)
with a unified envelope. Key additions:

- `ValidationFailure` dataclass (tier, rule, message, field, details)
  in `hippo.core.validation.validators`.
- `ValidationResult` extended with `failures: list[ValidationFailure]`
  alongside legacy `errors: list[str]`. `__post_init__` reconciles
  both views — legacy callers keep working (Decision 9.9.D's
  back-compat contract).
- `SchemaRegistry.validate_envelope()` returns tier-tagged failures
  for the LinkML-native tier; legacy `.validate()` preserved.
- `WriteValidator.tier` property for plugin authors.
- `ValidationResult.to_envelope()` / `.passed` / `.failures_for_tier()`.
- `ValidationFailed` exception (new, Decision 9.9.E — coexists with
  existing `ValidationFailure` exception to avoid a rename cascade).
- FastAPI handler maps `ValidationFailed` to HTTP 422 with the
  structured body.
- `design/reference_validators_yaml.md` prepended with the three-tier
  contract, boundary rules, and REST mapping.

**Tests:** 10 new in `test_validation_tiering.py`. 874 passed, 7 skipped.

### `typed-client` — commit `9a7b5f4`

Implements sec9 §9.8 — Pydantic surface over HippoClient with
namespace-aware accessors. Key additions:

- `hippo_accessor` and `hippo_namespace` class annotations added to
  `hippo_ext` (0.2.0 → 0.3.0).
- `hippo.core.typed_client` module — `generate_pydantic_models()`,
  `build_typed_surface()`, `EntityAccessor`, `Namespace`,
  `TypedClientError` with `.case` field.
- `HippoClient.__init__` grows a typed surface when a `SchemaRegistry`
  is supplied: flat root access (`client.samples`), explicit
  `client.root.samples` alias, non-root `client.tissue.samples`,
  nested dot-notation `client.assay.quant.measurements`.
- `EntityAccessor` forwards `.create/.put/.get/.query/.replace/
  .delete/.history/.state_at` to the generic client path.
  Decision 9.8.D — coequal surfaces.
- All four sec9 §9.8 collision cases raise at schema load with
  `.case` identifiers: `duplicate_accessor`,
  `accessor_vs_namespace`, `namespace_reserved`/`reserved_root`,
  `accessor_reserved`.
- `hippo_core` primitives (`Entity`, `ProvenanceRecord`, `Process`,
  `Validator`, `ReferenceLoader`) excluded from the typed surface.

**Decisions:**
- 9.8.H — Pydantic generation failures log `logger.warning` and
  degrade to dict-only accessors rather than raising (keeps typed
  client default-on for schemas the generator can't handle).

**Tests:** 23 new in `test_typed_client.py` covering:
- 4 default-accessor derivation cases (`DNASample` → `dna_samples`)
- 3 root access paths (flat, `root` alias, write-through)
- 3 non-root namespace patterns (single, nested, empty parent)
- 1 `hippo_accessor` override
- 5 collision cases
- 2 infrastructure exclusion
- 2 Pydantic model attachment + `create(PydanticInstance)`
- 2 generic/typed round-trip parity
- 1 no-registry path

**897 passed, 7 skipped (+23 from pre-typed baseline 874).**

## What was skipped and why

### `reference-loader-shape` — deliberately deferred for user review

Per my earlier scoping discussion with you, this change has **two
open design questions sec9 §9.5 explicitly flagged** as needing
discussion:

1. **Multi-class loader cardinality.** `entity_type` must be
   multivalued, but the spec is silent on ordered-vs-set cardinality
   and on where per-class metadata (count estimate, dependencies)
   lives.
2. **Referential boundary of `schema_fragment`.** When is the fragment
   merged vs. the loader instance validated? What's the error surface
   on mismatch?

These are architectural calls, not mechanical mappings — making them
in your sleep would be a bad pattern. The Wave 3 scaffold's
proposal.md flags them explicitly; the implementation waits on your
input.

### Non-Wave-3 scaffolds

`drs-self-uri`, `reference-auto-discovery`,
`unified-ingestion-framework` — not part of sec9 Wave 3 proper.
Separate initiatives you scaffolded for later. Not touched.

## Deferred items worth noting

From `typed-client`:

1. **`hippo.models` import surface** (`from hippo.models.tissue import
   Sample`). The generated Pydantic classes are attached to accessors
   via `EntityAccessor.model_class`; a separate importable namespace
   is a later ergonomics pass.
2. **`ValidationFailed` raise-on-write from typed accessors.** The
   exception class exists (`validation-tiering-clarification`);
   wiring it into `EntityAccessor.create`/`.put`/`.replace` needs the
   write-path integration currently handled by the generic client's
   Ingestion/Query services. Not a blocker — failures today surface
   through the generic path's existing exceptions; adding typed-side
   raise semantics is additive.
3. **Dedicated `reference_typed_client.md`.** Documentation can wait
   until deployments start consuming the surface; sec9 §9.8 + the
   test file document the contract for now.

From `validation-tiering-clarification`:

4. **Typed-client raises `ValidationFailed`** — see (2) above.
5. **Full FastAPI 422 integration test** — the handler is registered;
   a full end-to-end test exercising it lands with the typed-client
   write-path wiring so the two share fixture setup.

## Wave 3 status per sec9 §9.12

| Change | Status |
|---|---|
| `validation-tiering-clarification` | ✅ Landed |
| `typed-client` | ✅ Landed (6 items deferred as noted above) |
| `reference-loader-shape` | ⏸️ Blocked on design discussion |
| `generated-rest-surface` | Marked optional/deferred by sec9 itself |

Wave 3 is **effectively complete** modulo the `reference-loader-shape`
discussion and the small deferred follow-ups above.

## Commit sequence this session

```
9a7b5f4 feat(hippo): typed-client — Pydantic surface + namespace-aware accessors
b1412c6 feat(hippo): validation-tiering-clarification — unified envelope + REST surface
```

Neither commit was pushed. Push from your terminal when ready.

## Things worth a second look (flagged for morning review)

1. **Decision 9.8.H** (Pydantic failures → WARNING + degrade). This
   is a reversible call — if you prefer hard-fail semantics, the
   revert is a one-liner in `generate_pydantic_models()`.
2. **`EntityAccessor.delete` routes through `HippoClient.delete`**,
   not `storage.delete`. This is the correct behavior per the
   coequal-surface principle (Decision 9.8.D), but a reviewer might
   expect "typed client is a thin wrapper" to mean "bypasses all
   client hooks" — it doesn't.
3. **`SDK_RESERVED_NAMES`** (in `typed_client.py`) is a hand-curated
   set. If HippoClient grows a new public attribute that should be
   off-limits as an accessor name, that list needs updating. Worth
   a lint check or test-time assertion in a follow-up.
4. **The `test_single_level_namespace` test** now asserts
   `not isinstance(flat, EntityAccessor)` rather than the tautology
   it had at first. Verified by advisor; passed.

## What I'd do next

- **Discuss the two `reference-loader-shape` open questions** so it
  can land.
- **Wire `ValidationFailed` into `EntityAccessor` writes** — small
  scope, completes the envelope story end-to-end.
- **Add `hippo.models.<namespace>` import surface** if you see
  deployments starting to want it.

Rest well — the tree is green, every opinionated call is logged in
`sec9_decisions.md`, and the work undoes cleanly if any of the above
turns out to be wrong.
