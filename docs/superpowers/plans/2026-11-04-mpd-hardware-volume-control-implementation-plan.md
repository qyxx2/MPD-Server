# MPD Hardware Volume Control Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Add a server-owned hardware-volume state and control capability backed by the verified MPD ALSA hardware Mixer, with REST access and authoritative realtime invalidation.

**Architecture:** A dedicated HardwareVolumeManager reads PlayerPort.status().volume and writes through PlayerPort.set_volume(), guarded by an explicit operator setting that asserts the selected MPD ALSA output uses mixer_type=hardware. The manager participates in the existing playback operation boundary, StateObserver, FullStateSnapshot and RealtimeCoordinator; clients refresh the canonical full snapshot after a hardware_volume invalidation.

**Tech Stack:** Python 3.13, FastAPI, Pydantic, existing MPD PlayerPort / VerifiedPlayerPort, SQLite transaction boundary, StateObserver, RealtimeCoordinator, pytest, Docker Compose deployment configuration.

**Spec:** docs/superpowers/specs/2026-11-04-mpd-hardware-volume-control-design.md

## Global Constraints

- Hardware volume is disabled by default; MPD_HARDWARE_VOLUME_ENABLED must be explicitly enabled only after the NAS MPD ALSA output is configured with mixer_type=hardware.
- The service uses PlayerPort.set_volume() and PlayerStatus.volume; it must not directly open /dev/snd or invent raw ALSA / dB readings.
- The selected ALSA output must be uniquely identified using the existing OutputManager selector contract; never persist or assume a numeric MPD output ID.
- Hardware volume is an ephemeral runtime fact; do not add SQLite persistence.
- A successful PUT requires MPD readback to equal the requested 0–100 integer.
- Volume changes must not alter playback identity, Queue, natural progress, repeat/random, History or AutoPlay.
- Realtime frames remain invalidations only; clients re-read GET /api/state.
- FullStateSnapshot revisions remain library / playlist only; protocol_version remains 1 for the additive field.
- Do not modify Web or Android client code in this branch. Do not commit, push or merge unless explicitly requested.

## Review Focus

1. Hardware-volume mode disabled or incorrectly asserted: must never call setvol unless the explicit config gate and runtime checks pass. Test in Task 1.
2. Missing, duplicate or changing ALSA output candidates: reject ambiguous selection and never reuse a stale MPD output ID. Test in Task 2.
3. Concurrent playback/output operations and natural elapsed time: only the requested volume field may differ; other playback and queue facts must be preserved. Test in Task 2.
4. MPD disconnect, missing volume field, timeout, and readback mismatch: preserve last-known value only with stale/error metadata, and never coerce unknown to zero. Test in Task 2.
5. Third-party ALSA volume changes: prove whether MPD status follows an out-of-band hardware write before claiming that such changes are broadcast. Verify in Task 5; if MPD cannot observe them, block that acceptance and raise a separate ALSA-reader design.

---

### Task 1: Configuration Gate and Output Target Contract

**Batch:** B0 — safe capability enablement

**Files:**
- Modify: server/app/config.py
- Modify: deploy/docker-compose.yml
- Modify: deploy/.env.example
- Modify: deploy/README.md
- Test: server/tests/test_config.py
- Test: server/tests/invariants/test_config_composition.py
- Test: server/tests/test_deploy_contracts.py

**Interfaces:**
- AppConfig adds mpd_hardware_volume_enabled: bool = False.
- Environment mapping adds MPD_HARDWARE_VOLUME_ENABLED.
- The immutable setting is consumed by HardwareVolumeManager composition after its implementation in Task 2.
- The operator flag attests the selected MPD ALSA output has mixer_type=hardware; it is not inferred from the MPD TCP config command.

- [x] **Step 1: Add failing config tests** for default-disabled behavior, JSON/env precedence, boolean parsing, and immutable AppConfig.
- [x] **Step 2: Run the focused config tests** and confirm the new cases fail because the field/mapping is absent.
- [x] **Step 3: Add the explicit config field and environment mapping** without changing the existing defaults for other settings.
- [x] **Step 4: Add deployment wiring and operator documentation** describing the MPD mixer_type=hardware prerequisite and the exact verified NAS Mixer mapping; keep .env.example disabled.
- [x] **Step 5: Add deployment-contract tests** proving Compose wires the flag and does not map /dev/snd into the container.
- [x] **Step 6: Run config and deployment tests**:
  - .venv/bin/python -m pytest -q server/tests/test_config.py server/tests/invariants/test_config_composition.py server/tests/test_deploy_contracts.py
- [x] **Step 7: Inspect config/deployment diff** and confirm no secret, NAS-local .env, or unrelated deploy behavior changed.

### Task 2: Hardware Volume Domain Model and Manager

**Batch:** B1 — authoritative read/write service

**Files:**
- Create: server/app/models/hardware_volume.py
- Create: server/app/services/hardware_volume_manager.py
- Modify: server/app/main.py (construct and expose the manager using the existing output selector and operation runner)
- Test: server/tests/services/test_hardware_volume_manager.py
- Test: server/tests/invariants/test_hardware_volume_manager.py

**Interfaces:**
- HardwareVolumeState: status, volume_percent, output_name, output_plugin, output_enabled, control_source, error_code, error_message, updated_at, stale.
- HardwareVolumeRequestState: requested_percent, status, error_code, error_message, updated_at.
- HardwareVolumeSnapshot: state, last_request.
- HardwareVolumeObservation: observed_at, freshness, error_code, error_message.
- HardwareVolumeManager constructor receives PlayerPort, MPDCapabilities, explicit enabled flag, existing ALSA output selector, OutputOperationRunner, optional RealtimeCoordinator, observation clock and max age (6 seconds).
- Public methods: get_cached_state() -> HardwareVolumeSnapshot; get_state(read_timeout=None) -> HardwareVolumeSnapshot; set_volume(volume_percent: int) -> HardwareVolumeSnapshot; get_observation() -> HardwareVolumeObservation.

- [x] **Step 1: Write failing model tests** for enum values, nullable unknown volume, strict range constraints, stale state and last-request status.
- [x] **Step 2: Write failing manager tests** for disabled gate (no set_volume call), missing capability, no/ambiguous/disabled ALSA output, missing MPD volume, fresh read, stale expiry and MPD failures.
- [x] **Step 3: Write failing mutation tests** for 0/100 boundaries, set_volume call, exact status readback, mismatch failure, and failure never reporting success.
- [x] **Step 4: Write playback-preservation tests**: status excluding volume remains unchanged, elapsed may naturally advance while playing, queue entries remain identical, and no history/queue mutation occurs.
- [x] **Step 5: Run the new focused tests** and verify the expected red failures.
- [x] **Step 6: Implement domain models and HardwareVolumeManager**. Reuse PlayerPort.status(), PlayerPort.set_volume(), existing capability checks, current selector semantics and OutputOperationRunner. Keep current MPD output ID request-local only.
- [x] **Step 7: Implement accepted-sample ordering, stale tracking and observation staging**. Exclude timestamps from change comparison so unchanged one-second polls do not create changes.
- [x] **Step 8: Run focused manager/model tests**:
  - .venv/bin/python -m pytest -q server/tests/services/test_hardware_volume_manager.py server/tests/invariants/test_hardware_volume_playback_preservation.py
- [x] **Step 9: Inspect service diff** for playback side effects, request/observation ownership, stale-value semantics and error-code stability.

### Task 3: Full State and Realtime Invalidation

**Batch:** B2 — server state propagation

**Files:**
- Modify: server/app/models/realtime.py
- Modify: server/app/services/state_service.py
- Modify: server/app/services/state_observer.py
- Modify: server/app/api/realtime_schemas.py
- Modify: server/app/main.py
- Test: server/tests/api/test_realtime_state.py
- Test: server/tests/api/test_realtime.py
- Test: server/tests/invariants/test_realtime_hardware_volume.py
- Update: existing full-snapshot / realtime wire fixtures that instantiate FullStateSnapshot.

**Interfaces:**
- FullStateSnapshot adds hardware_volume and hardware_volume_observation.
- StateService receives synchronous cached snapshot and async observation readers, matching the existing output injection pattern.
- StateObserver receives the manager and samples it once per loop; one observer remains process-owned.
- Realtime invalidation domain is exactly hardware_volume; no new payload-bearing WebSocket frame and no hardware-volume revision counter.

- [x] **Step 1: Add failing FullStateSnapshot and wire-schema tests** requiring hardware_volume and hardware_volume_observation in REST /api/state and WebSocket initial snapshots.
- [x] **Step 2: Add failing StateObserver tests** for one sample per cycle, bounded budget, independent failure handling, stale expiry and close lifecycle.
- [x] **Step 3: Add failing RealtimeCoordinator tests** proving a net hardware-volume change emits domains=["hardware_volume"], unchanged polls emit nothing, and a stale/fresh transition invalidates once.
- [x] **Step 4: Run the targeted realtime tests** and confirm the new cases fail.
- [x] **Step 5: Extend FullStateSnapshot, StateService, realtime response schemas and startup injection**. Keep existing snake_case /api/state serialization and protocol_version 1.
- [x] **Step 6: Extend StateObserver** to sample hardware volume without allowing volume failures to prevent playback/output samples.
- [x] **Step 7: Stage accepted hardware-volume observations via RealtimeCoordinator.stage_observation** so invalidation is committed, coalescible and uses the existing epoch/sequence boundary.
- [x] **Step 8: Update all existing FullStateSnapshot fixtures** with explicit unknown/default hardware-volume state rather than silently omitting the field.
- [x] **Step 9: Run targeted realtime tests**:
  - .venv/bin/python -m pytest -q server/tests/api/test_realtime_state.py server/tests/api/test_realtime.py server/tests/invariants/test_realtime_hardware_volume.py
- [x] **Step 10: Run relevant snapshot / observer regression tests**:
  - .venv/bin/python -m pytest -q server/tests/invariants/test_realtime_snapshot.py server/tests/invariants/test_realtime_observer_lifecycle.py server/tests/invariants/test_realtime_delivery.py
- [x] **Step 11: Inspect wire fixtures** and confirm no unrelated domain/revision semantics changed.

### Task 4: REST State and Control API

**Batch:** B3 — client-callable server contract

**Files:**
- Modify: server/app/api/system_schemas.py
- Modify: server/app/api/system.py
- Modify: server/app/api/dependencies.py
- Test: server/tests/api/test_system_hardware_volume.py
- Test: server/tests/api/test_system_reads.py
- Test: server/tests/api/test_system_output_mutations.py (only shared middleware/serialization assertions if needed)
- Test: server/tests/api/test_web_wire_fixture.py

**Interfaces:**
- GET /api/system/hardware-volume -> HardwareVolumeSnapshotResponse with state, observation, lastRequest.
- PUT /api/system/hardware-volume body: {"volumePercent": integer 0..100}; response is the confirmed full snapshot.
- Use strict integer validation and system_schemas camelCase aliases.
- PUT inherits the global Idempotency-Key requirement; do not add an idempotency bypass.
- Map documented hardware-volume errors to 400/422/502/503 using the existing ErrorResponse envelope.

- [ ] **Step 1: Write failing API tests** for GET fresh/unavailable/stale states, alias casing, strict input rejection, and complete readback response.
- [ ] **Step 2: Write failing mutation tests** for missing Idempotency-Key, successful idempotent replay, same-key/different-payload conflict, MPD error, unavailable target, and readback mismatch.
- [ ] **Step 3: Run new API tests** and confirm the expected red failures.
- [ ] **Step 4: Add Pydantic API DTOs** with exact state/request/observation fields and no raw ALSA/dB claims.
- [ ] **Step 5: Add GET and PUT routes** using the HardwareVolumeManager dependency; GET returns a state snapshot for unavailable conditions, PUT requires confirmed post-write readback.
- [ ] **Step 6: Add error/status mappings** consistent with the spec; preserve global mutation middleware behavior.
- [ ] **Step 7: Validate OpenAPI response/request schemas and wire fixture**.
- [ ] **Step 8: Run focused API tests**:
  - .venv/bin/python -m pytest -q server/tests/api/test_system_hardware_volume.py server/tests/api/test_system_reads.py server/tests/api/test_web_wire_fixture.py
- [ ] **Step 9: Run idempotency and shared system API regression tests**:
  - .venv/bin/python -m pytest -q server/tests/invariants/test_output_idempotency.py server/tests/api/test_system_output_mutations.py
- [ ] **Step 10: Review OpenAPI contract** against Section 6 of the spec field by field.

### Task 5: Deployment and Real NAS Acceptance

**Batch:** B4 — end-to-end hardware proof

**Files:**
- Modify if needed: deploy/README.md
- Modify if needed: deploy/.env.example
- Modify if needed: deploy/docker-compose.yml
- Create: docs/superpowers/reports/2026-11-04-hardware-volume-control-nas-acceptance.md
- Test: server/tests/test_deploy_contracts.py

**Interfaces:**
- Production remains disabled until MPD_HARDWARE_VOLUME_ENABLED=true is explicitly set by the operator after confirming the selected MPD ALSA output's mixer_type=hardware.
- No container /dev/snd device mapping is required for the adopted MPD-backed path.
- Real NAS validation must distinguish MPD logical percent from direct ALSA raw channel value.

- [ ] **Step 1: Run deployment contract tests** with the feature flag disabled and confirm no host sound device mapping is added.
- [ ] **Step 2: Deploy only after the NAS MPD mixer configuration is checked** and enable the flag in the deployment's local environment (never commit secrets or NAS-local .env).
- [ ] **Step 3: Verify GET state** against MPD status and current output selection.
- [ ] **Step 4: Set a reversible test level through PUT**; record prior level, requested level, MPD readback, and ALSA PCM Playback Volume raw readback; restore the exact prior level and verify restoration.
- [ ] **Step 5: Test out-of-band ALSA mixer change** and immediately query MPD status / GET API. Record whether MPD reflects it; if not, explicitly mark external-change broadcasting unsupported and do not pass that acceptance criterion.
- [ ] **Step 6: Verify WebSocket invalidation** on a real value change and absence of repeated invalidations while the value is stable.
- [ ] **Step 7: Verify MPD disconnect / output disappearance / reappearance** produces stale or unknown state and recovers after fresh sampling.
- [ ] **Step 8: Record exact environment, commands, before/after raw hardware readings, errors and limitations** in the acceptance report.
- [ ] **Step 9: Run final targeted server and deployment regression tests** using repository commands; report NAS checks separately from local automated tests.

---

## Batch Decision

This work should be implemented in five batches (B0–B4), not as one large change. Configuration safety and target selection are prerequisites; the manager owns the write/readback and playback-preservation proof; state propagation is separately reviewable from REST; the REST API then exposes the stable contract; real NAS acceptance is the final hardware gate. Client adaptation is a later, separate phase and must consume the completed server contract without changing this branch.

## Plan Self-Review

- Spec coverage: Sections 4–7 are covered by B0/B1/B3; Section 8 by B2; Section 9 and real hardware caveats by B4; exclusions remain out of scope.
- Interface consistency: FullStateSnapshot, StateService, StateObserver, REST schemas and manager all use the same HardwareVolumeSnapshot / HardwareVolumeObservation names.
- Transaction/realtime boundary: manager stages observations through the current coordinator; WS sends invalidation only; clients fetch canonical state.
- Concurrency and preservation: Task 2 explicitly tests volume-only delta and shared output/playback serialization.
- Deployment safety: B0 defaults disabled and B4 uses real NAS proof; no new device node permissions are granted.
- No client files or code are in the plan.
