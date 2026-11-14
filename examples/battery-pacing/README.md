# Battery pacing

A worked Marque extension that slows or holds dispatch as the battery falls, so a run on a laptop doesn't die mid-landing.

## Install

- Copy `marque.md` to `~/.config/marque/marque.md`; if you already have one, merge its three sections.
- Keep `battery.sh` somewhere stable and make it executable (`chmod +x battery.sh`).
- Adjust the paths in your copy of `marque.md` to where the script lives.

## Policy

- **60 % or charging:** full concurrency.
- **40–60 % and falling:** one fewer implementer.
- **Below 40 %:** dispatch nothing new; running agents finish and land.
- **Below 20 %:** pause local builds and send a notification.

The `## commission` section starts the watcher, which samples every 60 seconds and exits when its condition trips. The `## dispatch` section reads the battery before every dispatch and reacts to the watcher's line.

## Environment

- `BATTERY_PACING_LOW` (40): below this, `run` reports `LOW`.
- `BATTERY_PACING_RESUME` (60): at or above this, `wait` reports `RESUME`.
- `BATTERY_PACING_EMERG` (20): below this, `run` and `wait` report `EMERGENCY`.
- `BATTERY_PACING_DROP` (5): a fall of more than this many points over 15 minutes on mains reports `FALLING`.
- `BATTERY_PACING_LOG` (./battery.log): the watcher's log when no path is passed.
- `BATTERY_PACING_POWER_SUPPLY` (/sys/class/power_supply): where the battery and adapter live.

`battery.sh now` prints `capacity status adapter=0|1`. `battery.sh watch run|wait|emerg [LOG]` samples into the log and exits when its mode's condition trips.
