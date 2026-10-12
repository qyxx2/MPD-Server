# Live MPD bounded-buffer experiment — archived evidence

Experiment date: 2026-10-12 (Asia/Shanghai). Frozen baseline: `92b44c913e49052d2fd113b77eda0b13c429c0fc`, branch `refactor/mpd-bounded-execution`, repository `qyxx2/MPD-Server`.

Start with [the full report](REPORT.md). The final five successful trials and latency samples are in [controlled-run-final/results.json](controlled-run-final/results.json), with [key logs](control-final-console.log). Earlier failed attempts are retained as evidence; they are not included in the final successful-run statistics. The report does not claim B1 implementation or Web/DAC acceptance.

## Archive boundary

The user explicitly excluded backups from the commit. Every full queue snapshot named `original.json` or `final.json` is retained only in the original local artifact directory, `/home/Gold/WorkSpace/MPD-Server/mpd-bounded-experiment-artifacts`; none is published here. References to those files in the original report describe local experimental evidence, not files included in this archive. `post-check.json` contains only a status and short current window, not a full queue backup.

Scripts, original report, all console/event logs, successful and failed result JSON, environment evidence and derived timing statistics are copied byte-for-byte. `SHA256SUMS` records their hashes. Do not overwrite archived logs when rerunning.

## Rerun from a repository checkout

Use an existing project virtual environment, with the checkout root passed explicitly because the historical scripts default to the original machine paths. Use a fresh output directory outside this committed archive.

Read-only probe:

```bash
/path/to/existing/.venv/bin/python docs/superpowers/experiments/2026-10-12-mpd-bounded-execution/probe.py --repo "$PWD" --samples 50 --observe-seconds 300 --out /tmp/mpd-readonly-new-run
```

Control probe — this explicitly authorizes clearing the current MPD queue, saves a local backup, and attempts restoration:

```bash
/path/to/existing/.venv/bin/python docs/superpowers/experiments/2026-10-12-mpd-bounded-execution/control_probe.py --repo "$PWD" --authorize-clear-existing --trials 5 --out /tmp/mpd-controlled-new-run
```

Use only during an authorized maintenance window with competing controllers excluded. Clearing destroys original MPD Song IDs even when URI order and playback are restored. These scripts never modify MS databases or music files. Do not treat the 1-second playing-seek probe tolerance as a newly accepted production contract.

No production code, dependency declarations, database, virtual environment or music files are part of this commit.
