# Personal Trainer

Local running coach: reads Garmin data, checks recovery, builds today's run with a local LLM (`qwen3:8b` via Ollama).

## Status

**Done**
- Garmin login (`garmin_connect/garmin_connector.py`)
- `get_user_current_condition`: stress, body battery, resting HR vs baseline, HRV, Training Readiness, sleep, VO2max, weight, last workout
- `save_snapshot_to_file`

**Not started**
- `build_workout`, `get_historical_workout_data_past_month`, `get_best_activity_records` (stubs)
- `user_data/profile.json` (empty)
- `qwen3:8b` not downloaded

## Next steps

**Goal:** build a running workout on demand, based on today's condition and recent runs.

Approach still to be decided.

**Later:** weekly plan, progression, chat, UI
