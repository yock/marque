# Runners

A **runner** is where a suite runs. The local runner is the default and needs nothing: the command runs in the worktree. The **Beam** runner rents a sandbox, and Marque owns the whole lifecycle — nothing about the sandbox is left to the project's own tooling (ADR 0002). The project supplies only the environment and the suite command. This page is the Beam runner's contract, its accounting, its sweep and its limits.

## The Beam runner contract

1. Build the image from the project's Dockerfile, and cache it by the Dockerfile's hash.
2. Create a sandbox — always a sandbox, never a VM — passing `--ttl` on every create.
3. Upload the **exact tree** that will be tested, never the worktree: `git archive <tree>`.
4. Run each part's command at the uploaded tree's root, with a timeout on every exec.
5. Tear the sandbox down on every exit path — normal, error, SIGTERM, SIGHUP, SIGINT — and confirm it is gone.
6. Settle the cost from the provider's `started_at` and the commission's rate.
7. Call only the allowlisted CLI, so no token reaches Marque's context, arguments or files.
8. Record all of it: the tree, the runner, each container, every exit status, the cost and whether each teardown was confirmed.

## The `## Runner` block

A project's `docs/agents/marque.md` holds one `## Runner` section, one `key: value` per line:

```markdown
## Runner

runner: beam
dockerfile: tools/beam/Dockerfile
cpu: 4
memory: 8192
boxes: 1
max wall time: 1800
commands:
- cmake --build build && ctest --test-dir build
```

| Field | Unit | Used as |
|---|---|---|
| `runner` | `beam` | read, but the `--runner` flag decides |
| `dockerfile` | a repo path | `image build --dockerfile`; relative to the repo root |
| `cpu` | vCPUs | `container create --cpu` |
| `memory` | MiB | `container create --memory` |
| `boxes` | a count | the most sandboxes one run has live at once (default 1); parts beyond it start as earlier ones finish |
| `max wall time` | seconds | the TTL's base and every exec timeout; `--max-wall` overrides it |
| `local fallback` | `yes` or `no` | `no`: a refused run exits 3 instead of running locally (default `yes`) |
| `commands` | one `- ` line per command | `sh -c` at the uploaded tree's root |

`suite.py` reads the block from the worktree it runs in (`<worktree>/docs/agents/marque.md`). The block runs from the line `## Runner` to the next `## ` heading or the end of the file; blank lines and code fences are ignored; `commands:` starts a list and each following `- ` line is one item; every other `key: value` line sets that key. A missing file or a file without the block reads as no block.

Without `-- CMD`, the block's `commands` are what runs. A local run executes each one, in order, even when an earlier one fails, and records one `exit.<i>` each.

A Beam run gives each command its own sandbox. Each command is a **part**, numbered in command order, and up to `boxes` parts run at once; the rest start, in order, as earlier ones finish. Every sandbox is under the whole contract above: a TTL, its ID in the state dir the moment it exists, and a confirmed teardown on every exit path, including a signal. The verdict is `pass` only when every part exits 0, and the record carries one `exit.<i>` per part, so one failing half of a suite fails the run. `-- CMD` is a run of one part.

`ping`'s two halves are the model case: `cmake --build build && ctest --test-dir build`, or `make && make test`, is two commands and two sandboxes.

## The command line

```
suite.py run --record FILE --runner beam --state-dir DIR --rate PER_MINUTE --cap AMOUNT [--concurrency N] [--max-wall SECONDS] [-- CMD [ARG...]]
```

`--rate` is currency per **wall-minute**, passed by the orchestrator from the commission's Paid compute term. `--cap` is the commission's paid-compute cap, in the same currency. `suite.py` never reads `plan.md`. A Beam run without `--rate`, `--cap` or `--state-dir`, or with no max wall time, is refused with exit 2 before anything is created or written.

`MARGIN = 600` is a constant in `suite.py`: the TTL is the max wall time plus 600 seconds. That leaves ten minutes for the upload and the teardown after the suite's own deadline. The same margin sizes a reservation before the box exists.

With `-- CMD`, a Beam run sends the argv as one `sh -c <shlex.join(CMD)>`.

## Runner concurrency

Runner concurrency is the account's limit on **live sandboxes across every run that shares the state dir** — not on runs. The orchestrator passes it as `--concurrency N`, from the commission's Paid compute term, as it passes `--rate`; the default is 1, and a value that is not a positive integer is refused.

It is enforced with **slots**: one locked file per slot, `beam/slots/<k>` for `k` = 0 to N−1, in the state dir. A sandbox holds one slot from just before `container create` until its teardown ends, so a run with two boxes holds two slots. A run that finds no free slot **waits; it is not refused**, and starts as soon as one frees up. A process that dies releases its locks, so a slot never has to be reclaimed.

This is separate from implementer concurrency: it bounds live sandboxes, not agents.

## What a run does

1. Check the image cache and reserve the run's worst case against the cap (→ **The cap** below), then write the record's opening lines and build the image **once**, unless `<state>/beam/images/<sha256 of the Dockerfile>` names one `beam image get` still finds.
2. For each part, in order but up to `boxes` at once: take a runner slot, then create the sandbox with `container create --ttl <max wall time + 600>`. Record its ID in the state dir at once, then in the record as `container.<i>`.
3. Upload `git archive <tree>` with `container cp` and extract it at `/work`.
4. Run the part's command with `container exec --timeout <max wall time> --cwd /work`.
5. Stop the sandbox, confirm it is gone, and release the slot. A signal stops every sandbox still live, once each, before the record is closed.

The record reads `runner: beam` and carries each box's ID. Its keys are `tree, commit, runner, started`, then one `container.<i>` per box in creation order, then `ended`, `exit.1` … `exit.n`, `verdict`, `cost`, then `teardown.<i>` in part order, then `log`. A part that never got a box has no `container.<i>` or `teardown.<i>` line, and a run that created no box costs `0.0000`.

## `started_at` and the cost

`container create` does not print when the box started. The `started_at` comes from `container list`, which reports it once the box has started, and is read after the part's command. The cost is summed over the boxes: for each, the rate times the confirmed stop minus `started_at`, in minutes, written with four decimal places.

When a stop cannot be confirmed, that box is charged the **worst case**: the rate times the whole TTL in minutes. An unconfirmed teardown keeps the container's record in the state dir for the sweep to find.

## The cap: reserve, refuse, settle

The commission's cap is `--cap AMOUNT`, in the same currency as `--rate`. Every paid run — an implementer's, an integration run's, an image build's — touches one ledger before it starts.

**The ledger** is `<state>/spend.tsv`: tab-separated, one row per reservation and settlement, append-only under **`<state>/spend.lock`**, an exclusive blocking lock, with every append fsynced. Its header is `time`, `kind`, `run`, `amount`, `note`: `kind` is `reserve` or `settle`, `time` is UTC, `amount` has four decimal places, and `note` is the record path or `build`. A run id is its UTC start, its pid and eight random hex characters; its build's id is `<run id>.build`.

**Spend so far** is, for each run id, its last `settle` amount if it has one and its `reserve` amount otherwise, summed. Malformed lines are skipped.

**Reserve.** Before anything is created, the run reserves each part's worst case — `n_parts × rate × (max wall time + 600) / 60` — plus `rate × 600 / 60` under `<run id>.build` when the image has to be built. It is one check, taken before the build: if spend so far plus the whole reservation would pass the cap, nothing starts.

**Refuse and fall back.** A refused run prints `suite.py: paid compute refused: cap: spend … + reservation … > cap …` and falls back to the local runner, whose record reads `runner: local` and then `refused: <the same reason>`. When the block says `local fallback: no`, it exits 3 instead and writes no record.

**Settle.** At teardown the reservation is replaced by the rate times the confirmed stop minus `started_at`, summed over the boxes, and the build by the wall time `image build` took, each as its own row keyed by its run id. The record's `cost` is the boxes' cost plus the build's. A run that dies unsettled counts at its worst case until the sweep. A local run writes no rows.

## The sweep

No sandbox outlives Marque unnoticed, and a teardown that could not be confirmed never under-counts spend: `suite.py sweep --state-dir DIR` is what closes both gaps. `ledger.py recover` runs it on every restart, and the orchestrator runs it by hand when something looks stuck.

It acts only on the sandboxes Marque recorded in `beam/containers/`, and only on those whose run is no longer live. A run is **live** when another host recorded the box — another machine's run is never touched — or when its `pid` is still alive on this host. A file with no parsable `pid` is not live; a file written before the `host` line existed counts as this host's.

A state dir without `beam/` never used Beam: the sweep prints nothing, calls nothing and exits 0, so a local-only project needs no CLI. Otherwise it asks `container list` once; if that fails it prints `sweep: cannot list containers` to stderr, touches nothing and exits 1.

Each recorded box whose run is not live yields one line:

- `live <id>: its run is still running (pid <pid> on <host>)` — left alone, ID file and all;
- `gone <id>` — the box no longer exists; its ID file is removed;
- `stopped <id>: confirmed` — stopped and confirmed gone; its ID file is removed;
- `stopped <id>: unconfirmed` — the stop could not be confirmed; the ID file stays, and the sweep exits 1.

Then it settles every run it found dead that has a reservation and no settlement, at that reservation — the worst case — printing `settled <run> at worst case <amount>`. A run that already settled priced its own unconfirmed boxes itself, so it is left alone.

Every sandbox live on the account with no ID file of Marque's is reported as `unrecorded <id>: left alone`. The sweep never touches a sandbox it did not record, so other work on the same account is safe.

Exit codes: 0 swept, 1 a teardown could not be confirmed or the containers could not be listed.

### Unconfirmed teardown

A stop the sweep cannot confirm leaves the run at its worst case in the ledger and keeps the box's ID file in the state dir, so the next sweep tries again. An unconfirmed teardown is a core notification: `a runner teardown that could not be confirmed`.

## The state dir

- `beam/images/<sha256>` — the image ID for that Dockerfile's bytes. The image is built once per hash and reused while `beam image get` finds it.
- `beam/containers/<container id>` — the box's `pid`, the `host` that recorded it, the `run` it belongs to, the `record`, when it was `created`, and its `worst` case. Written the moment the sandbox exists. A confirmed stop, or a sweep that confirms one, removes it; an unconfirmed teardown leaves it for the sweep.
- `beam/slots/<k>` — the locked files that hold the account's live-sandbox slots. A process that dies frees its own.
- `spend.tsv` — the commission ledger: one row per reservation and settlement.
- `spend.lock` — the file lock every ledger read and append holds.

## The allowlist

Marque calls `beam` only through seven subcommands:

- `image build`
- `image get`
- `container create`
- `container cp`
- `container exec`
- `container stop`
- `container list`

Every call goes through one helper in `suite.py` that refuses anything else. `beam status` is **not** allowed: it prints a token prefix, and no token may enter Marque's context, arguments or files. There is no beam-client SDK; the runner stays on the standard library and the CLI.

## The CLI's limits

- The account's **default CPU tier** applies to every run: a run cannot pick a faster tier. The commission's rate must match the account's tier, or the cost recorded will be wrong.
- A TTL **cannot be renewed**. A suite that outlives it is stopped mid-run; size `max wall time` for the suite, and let the 600-second margin cover the upload and teardown.
- There is **no unlimited TTL**: the CLI accepts only a TTL of at least 1 second, so every create names one — the max wall time plus the margin.
