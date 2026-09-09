# Unattended run supervisor

Start Quill once, leave it, and have it keep going until it hits the day's
target. Notice when it has stopped, and bring it back.

## Why

A day of real running produced six ways the unattended loop dies quietly. Five
are fixed. The sixth is that nothing is watching:

- This morning `live_mode` was true and both processes were dead. Quill had
  been doing nothing for hours and nothing said so. The dashboard reported
  "live" because the flag survives the processes.
- The existing watchdog (`ops/health.py`) alerts on stale heartbeats, but it
  runs *inside the worker*, so it cannot report a dead worker and cannot
  restart anything.
- There is no notion of a target, so "behind" is not a state the system can be
  in, and there is nothing to act on.

## What this is not

It does not raise the governor's caps, shorten write spacing, or touch the
reply quality bar. The governor stays the single authority on how much Quill
may write, and `foryou_auto_min` stays the single authority on whether a
drafted reply is good enough to send.

## The run record

One record per local day, stored in settings alongside `_pending_auto`:

```
run_session = {
  day:            "2026-09-09",       # local date; a change rolls the record
  started_at:     ISO8601,            # when live mode came up, not first tick
  target:         40,
  deadline:       "22:00",            # local
  relax_level:    0,                  # 0-3
  relax_changed_at: ISO8601,
  restarts:       [{at, process, reason}],
  alerted:        {unreachable: bool, ceiling: [process]},
}
```

`started_at` is taken from the launcher's existing `live_started_at` when that
falls on the same day, so a supervisor that first ticks a minute after launch
still records the real start. On rollover the finished record moves to
`run_history` (14 days kept) for the dashboard.

## Where the supervisor runs

The API process. It is the only one that outlives the worker and the browser,
it already owns `launcher.start()`, and `quill.bat` runs a single uvicorn
worker with no reloader, so there is exactly one of it. It gets a background
scheduler ticking every 60 seconds, which is the same mechanism the worker and
browser processes already use.

Each tick, in order:

1. If live mode is off, do nothing. That flag is off because a human pressed
   Stop, and the supervisor must never undo that.
2. Get or start today's run record.
3. Check both processes and restart what needs it.
4. Compute pace and adjust the relaxation level.

## Restart policy

A process needs restarting when its pid is gone, or when its pid is alive but
its heartbeat has been stale past `WATCHDOG_STALE_S` (5 minutes), which means
it is wedged. A dead process is started; a wedged one is terminated first.
Restarting goes through `launcher.start()`, which is already idempotent and
already records `live_pids`.

Three limits, because the cost of restarting too eagerly is higher than the
cost of restarting late. Chromium's profile directory takes exactly one owner,
and losing the signed-in X session is the one failure only a human can undo:

- **Cooldown.** 5 minutes between restarts of the same process, so a process
  that crashes on boot cannot become a loop.
- **Ceiling.** 6 restarts per process per day. On the seventh, alert and stop
  trying. Past that it is a human problem and more restarts will not help.
- **Suppressions.** Never while live mode is off. Never restart the browser
  while the manual login window is open: `launcher.open_login` deliberately
  kills the browser process to hand the profile to the login window, and
  restarting it there would put two processes on one profile. `open_login`
  stamps `login_window_until`, and the supervisor respects it.

Restarting mid-send is safe because of the startup reconcile: the browser
process opens the post, looks for the reply, and marks it sent or re-queues it.

## Pace and relaxation

Expected progress is `target * elapsed / window`, where the window runs from
the recorded start to the deadline. Being behind widens what the For You sweep
will *consider*, never what it will *send*:

| Level | Behind by | Max age | Relevance floor | Author cooldown |
|-------|-----------|---------|-----------------|-----------------|
| 0     | on pace   | 6h      | 40              | 24h             |
| 1     | 3         | 9h      | 35              | 18h             |
| 2     | 8         | 12h     | 30              | 12h             |
| 3     | 15        | 24h     | 25              | 8h              |

Those three settings are the largest sources of loss in the measured sweeps:
of 55 posts scanned, typically 17-21 are dropped as too old, 8-12 below the
relevance floor, and 8-9 on author cooldown.

The level moves at most one step per 15 minutes in either direction, so a
single slow half hour does not slam it to the bottom and a single burst does
not snap it back. Level 3 is the floor; nothing goes below relevance 25.

**Never touched by relaxation:** `foryou_auto_min` (the drafted reply's
confidence bar), the persona guards, `min_write_spacing_s`, and every governor
cap. Volume is bought by considering more posts, never by lowering the bar on
what gets said.

**Unreachable targets.** When the time left divided by the write spacing is
less than the replies still owed, the target cannot be hit however wide the
intake. Relaxation then freezes where it stands, and the shortfall is logged
and alerted once. Without this the last hour of every day would relax to the
floor and spend the remaining sends on the worst posts available. Tonight is
exactly that case: 12 sent at 20:35 local, 85 minutes to the deadline, room
for about 17 more at 5-minute spacing, so 40 is out of reach and chasing it
would only cost quality.

## Errors fixed alongside

`watch_all` calls `sweep_home` outside the per-account guard added earlier, so
a selector miss on the home timeline still aborts the whole sweep including
every deep read after it. It has fired three times since the last restart.
Same treatment as a dead handle: log it, count it, carry on.

## Surfacing

`GET /api/run` returns the record plus computed pace: started at, sent,
expected, behind by, level, reachable, restarts. A compact card on the
dashboard Home tab shows the same, so the run's health is visible without
reading logs.

## Testing

- Pace maths: on pace, behind, past deadline, and the unreachable case.
- Ladder: steps up and down, honours the 15-minute hysteresis, stops at the
  floor, and leaves `foryou_auto_min` untouched.
- Restart rules: dead pid starts; stale heartbeat terminates then starts;
  cooldown blocks a rapid repeat; the ceiling exhausts and alerts once; live
  mode off does nothing; an open login window blocks a browser restart.
- Day rollover archives the record and starts a fresh one.
- `sweep_home` failure no longer stops the deep reads.
