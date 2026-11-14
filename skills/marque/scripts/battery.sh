#!/bin/sh
# battery.sh now                 print "capacity status adapter=0|1"
# battery.sh watch MODE [LOG]    sample every 60 s into LOG; exit, printing why, when MODE's condition trips:
#   run   : capacity < LOW (EMERGENCY under EMERG), or a drop of more than DROP points over 15 min on mains
#   wait  : capacity >= RESUME (dispatch may resume), or EMERGENCY
#   emerg : capacity >= LOW (paused processes may resume)
# Thresholds from the environment: SYMPHONY_BATTERY_LOW (40), _RESUME (60), _EMERG (20), _DROP (5).
# The battery and the mains adapter are found under /sys/class/power_supply (no root).
# Run `watch` in the background: its exit is what wakes the orchestrator.
set -u
LOW=${SYMPHONY_BATTERY_LOW:-40}; RESUME=${SYMPHONY_BATTERY_RESUME:-60}
EMERG=${SYMPHONY_BATTERY_EMERG:-20}; DROP=${SYMPHONY_BATTERY_DROP:-5}
P=/sys/class/power_supply
B=; A=
for d in "$P"/*; do
  [ -r "$d/type" ] || continue
  case $(cat "$d/type") in
    Battery) [ -z "$B" ] && [ -r "$d/capacity" ] && B=$d ;;
    Mains)   [ -z "$A" ] && A=$d ;;
  esac
done
[ -n "$B" ] || { echo "battery.sh: no battery under $P" >&2; exit 2; }
adapter() { if [ -n "$A" ]; then cat "$A/online"; else echo 0; fi; }

case ${1:-now} in
  now) echo "$(cat "$B/capacity") $(cat "$B/status") adapter=$(adapter)"; exit 0 ;;
  watch) MODE=${2:-run}; LOG=${3:-${SYMPHONY_BATTERY_LOG:-./battery.log}} ;;
  *) echo "usage: battery.sh now | watch run|wait|emerg [LOG]" >&2; exit 2 ;;
esac

while :; do
  c=$(cat "$B/capacity"); s=$(cat "$B/status"); a=$(adapter)
  echo "$(date -u +%FT%TZ) $c $s $a" >> "$LOG"
  case $MODE in
    run)
      [ "$c" -lt "$EMERG" ] && { echo "EMERGENCY $c"; exit 0; }
      [ "$c" -lt "$LOW" ] && { echo "LOW $c"; exit 0; }
      if [ "$(wc -l < "$LOG")" -ge 16 ] && [ "$a" = 1 ]; then
        old=$(tail -n 16 "$LOG" | head -n 1 | awk '{print $2}')
        [ $((old - c)) -gt "$DROP" ] && { echo "FALLING $old->$c"; exit 0; }
      fi ;;
    wait)  [ "$c" -ge "$RESUME" ] && { echo "RESUME $c"; exit 0; }
           [ "$c" -lt "$EMERG" ] && { echo "EMERGENCY $c"; exit 0; } ;;
    emerg) [ "$c" -ge "$LOW" ] && { echo "RECOVERED $c"; exit 0; } ;;
    *) echo "battery.sh: unknown mode $MODE" >&2; exit 2 ;;
  esac
  sleep 60
done
