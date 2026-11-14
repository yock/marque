## commission

Start `battery.sh` from Marque's `examples/battery-pacing/` as a background command that wakes you: `battery.sh watch run <state dir>/battery.log`. State the policy once and record it in `plan.md`: at 60 % or charging, full concurrency; at 40–60 % and falling, one fewer; below 40 %, no new dispatches; below 20 %, local builds pause.

## dispatch

Before each dispatch, run `battery.sh now`. At ≥ 60 % or charging, full concurrency; at 40–60 % and falling, one fewer; below 40 %, dispatch nothing new (running agents finish and land); below 20 %, pause local builds and notify. When the watcher exits, act on its line (`LOW`, `EMERGENCY`, `FALLING`) and restart it in the matching mode (`wait`, `emerg`, `run`).

## notify

Add the event "battery emergency (below 20 %)".
