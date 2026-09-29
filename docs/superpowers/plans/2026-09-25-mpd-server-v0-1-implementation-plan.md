# MPD-Server v0.1 Implementation Plan

## Task 4：Queue、Playback Context、History、AutoPlay、Playback Service

Dependencies:
- Task 1R and Task 2R completed.
- Task 3 completed, including available-library queries and the DomainEvent contract.
- Task 5, Task 6, Task 7, Task 8, Task 9, Task 10, Task 11, Task 12 are not dependencies.

Files:
- Create: server/app/models/queue.py
- Create: server/app/repositories/queue_repository.py
- Create: server/app/repositories/playback_state_repository.py
- Create: server/app/services/queue_manager.py
- Create: server/app/services/history_service.py
- Create: server/app/services/autoplay.py
- Create: server/app/services/playback_service.py
- Create: server/tests/services/test_queue_manager.py
- Create: server/tests/services/test_history_service.py
- Create: server/tests/services/test_autoplay.py
- Create: server/tests/services/test_playback_service.py

Core models:
~~~python
class PlaybackContext(BaseModel):
    context_id: str
    source_type: str
    source_id: str | None = None
    ordered_song_ids: tuple[str, ...]
    random_seed: int | None = None

class QueueItem(BaseModel):
    queue_item_id: str
    song_id: str
    position: int
    source: Literal["MANUAL", "AUTOPLAY"]
    playback_context_id: str | None = None
~~~

MPD Queue mapping:
- Server queue_item_id and MPD mpd_song_id are separate identifiers.
- Server Queue is authoritative business state.
- Queue mutation is persisted through QueueRepository, then synchronized to MPD through PlayerPort Queue methods.
- MPD unavailability does not erase or silently replace the server Queue; synchronization state is explicit and can be reconciled later.
- Playback state advances only after MPD command success and status reconciliation.

- [x] Step 1: RED tests for Start Track replacing pending Up Next and creating PlaybackContext.
- [x] Step 2: RED tests for Queue Play Now preserving prior pending items after the selected song.
- [x] Step 3: RED tests for Play Next and Add to Queue insertion order.
- [x] Step 4: RED tests for reorder/delete/clear/save-as-playlist and current-song deletion.
- [x] Step 5: RED tests for Played view versus persistent History.
- [x] Step 6: RED tests for natural completion, skip, stop and switch-away reasons.
- [x] Step 7: Implement AutoPlay low-watermark 5/refill 5 using Task 3 available Songs while respecting PlaybackContext.
- [x] Step 8: Prevent AutoPlay from overwriting MANUAL items and mark every generated item source.
- [x] Step 9: Test empty library, one-song library, insufficient candidates and concurrent Queue mutation.
- [x] Step 10: Serialize Queue mutations using Repository transaction boundaries plus Queue revision/CAS.
- [x] Step 11: Test Pause keeps AutoPlay, Stop disables it, and Queue exhaustion is not terminal.
- [x] Step 12: Implement Playback Service as the sole orchestration layer between Queue/History/AutoPlay and PlayerPort.
- [x] Step 13: Test MPD failures do not falsely advance current-track service state and reconcile external status.
- [x] Step 14: Verify Queue/Playback persistence, MPD synchronization, compile/lint and diff.
- [x] Step 15: Commit: feat: implement authoritative playback model.
