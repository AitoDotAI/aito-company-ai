# 21 · Backups & restore

The agent writes to the real instance (`add_todo`, `log_touch`, deal updates,
…), and so does the dashboard. A bad write — or a bad batch —
needs a cheap undo. This is it.

## The mechanism: Aito environments

An Aito **environment** (env) is a copy-on-write branch of the whole database
([aito.ai/docs/api/envs](https://aito.ai/docs/api/envs/)). Branching master to a
snapshot is a **millisecond, ~zero-disk** operation; only later changes take
space. That is what makes frequent snapshots affordable where a daily full CSV
dump would not be.

Four admin calls on `AitoClient` (the `_envs` endpoints; a read-write key):

| | Call | Meaning |
|---|---|---|
| list | `GET /api/v1/_envs` | master + every snapshot |
| snapshot | `POST /api/v1/_envs` `{name}` | branch master (the backup) |
| restore | `POST /api/v1/_envs/{name}/promote` | atomic swap into master |
| drop | `DELETE /api/v1/_envs/{name}` | rotate a snapshot out |

## What we keep (`src/company_ai/backups.py`)

Two rolling sets, rotated automatically after each backup:

- **`daily-<YYYY-MM-DD>`** — the last **7** days.
- **`tx-<epoch>`** — the last **16**, for snapshotting *before* a risky
  write-burst (a bulk edit, a migration, letting the agent loose on a batch).

`stale(names, kind, keep)` is a pure function — our stamps sort lexically =
chronologically, so the newest `keep` are kept and the rest dropped. Booktested.

## Using it

```
company-ai backup                 # daily snapshot + rotate (keep 7)
company-ai backup --kind tx        # tx snapshot + rotate (keep 16)
company-ai backups                 # list restore points
company-ai restore daily-2026-07-13         # DRY RUN: prints the per-table diff
company-ai restore daily-2026-07-13 --force # actually promote it into master
```

**Restore is guarded.** It prints the current-vs-snapshot row counts per table
(so you see exactly what master becomes), and does nothing without `--force`.
When you do restore, it **first snapshots the current state** as
`prerestore-<epoch>` — so a restore is itself undoable (promote that back). It
targets `.env.aito` by default; `→ aito: <host>` is echoed before it acts.

**The agent can snapshot, but not restore.** MCP exposes `create_backup` (so
Claude can snapshot before a risky change it's about to make), but **not**
restore — promoting over master is an operator decision, CLI + `--force` only.

## Scheduling

A daily snapshot via a `systemd --user` timer (same pattern as the board timers,
`ops/`):

```
cp ops/systemd/company-ai-backup.{service,timer} ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now company-ai-backup.timer   # daily 03:30 Europe/Helsinki
systemctl --user list-timers 'company-ai-*'
```

`ops/backup.sh daily|tx` is the entry point (self-locating, enters the Nix
shell, defaults `COMPANY_AI_ENV=.env.aito`). For transaction snapshots, call
`ops/backup.sh tx` before a risky run, or wire a more frequent timer.

## The second plane: off-box

An env snapshot is a branch **inside the instance**. It undoes a bad write; it
does **not** survive losing the VM — same disk, same box. So a snapshot alone
is not a backup of the machine, only of the data's history on it.

`ops/backup-offbox.sh` is the other plane: `export-all` dumps every table to
CSVs, then rsync pushes them **off** the machine.

```
cp ops/systemd/company-ai-backup-offbox.{service,timer} ~/.config/systemd/user/
systemctl --user edit company-ai-backup-offbox.service   # set COMPANY_AI_OFFBOX_DEST
systemctl --user enable --now company-ai-backup-offbox.timer  # daily 03:50
```

The destination has **no default** and the script refuses to run without
`COMPANY_AI_OFFBOX_DEST` — an on-box-only copy that *looks* like a backup is
worse than none. Staging lands in `.backups/` (gitignored: it is the real
dataset). `COMPANY_AI_OFFBOX_KEEP` rotates local staging copies; retention on
the far side belongs to the destination, not to this script.

## Restore runbook

Pick by what broke. Every command that *writes* (`restore`, `create-schema`,
`load-all`, `backup`) echoes `→ aito: <host>` before it acts — read that line
before answering the prompt, especially under stress.

**A · A bad write or a bad batch, instance healthy.** The common case.

```
company-ai backups                       # list restore points
company-ai restore daily-2026-09-22      # DRY RUN: per-table diff, changes nothing
company-ai restore daily-2026-09-22 --force
```

The dry run prints current-vs-snapshot row counts per table — that is your
confirmation that master becomes what you expect. `--force` promotes, and
first snapshots the current state as `prerestore-<epoch>`, so the restore is
itself undoable (promote that back).

**B · Instance is up but the data is wrong beyond one batch.** Same as A;
reach further back through `company-ai backups`. If every snapshot is also
bad, the env plane is exhausted — go to C with the newest good off-box dump.

**C · The VM or the instance is gone.** The env snapshots went with it; this is
what the off-box CSVs are for.

1. Stand up an Aito instance and point `.env.aito` at it (`AITO_INSTANCE_URL`,
   `AITO_API_KEY`).
2. `company-ai create-schema` — an empty instance has no tables.
3. Fetch the newest `offbox-<stamp>/` from `COMPANY_AI_OFFBOX_DEST`.
4. `company-ai load-all --dir <that directory>`.
5. Verify before trusting it: `company-ai doctor`, then open the dashboard and
   check the counts against the dump (`wc -l` the CSVs).
6. Re-enable both timers on the new box, and take an immediate
   `ops/backup.sh daily` so there is a restore point on the new instance.

What you lose in C is everything written since the last off-box run — up to 24
hours at the default schedule. Run `ops/backup-offbox.sh` by hand before any
migration or risky operator work.

**Rehearsal status.** Plane A (env promote) is exercised by the booktests and
in normal use. **Plane C has not been rehearsed end-to-end** on this
deployment — until someone walks steps 1–5 against a scratch instance and
writes the date here, treat C as a documented intention, not a proven path.
An untested backup is a belief, not a backup.

## Notes

- Envs are database-scoped; a read-write key reads/writes any env in the
  database (no per-env credentials). Cross-tenant isolation is a separate
  database, not a separate env.
- Promote is an atomic swap, not a move: the snapshot env survives a restore
  and stays queryable, so you can re-promote or inspect it. Clean it up with
  `company-ai backups` + a delete when you're sure.
- This is the shallow, transaction-granular complement to Plane B (the CSV
  `export-all`/`load-all`, `docs/06`), which remains the portable, off-instance
  backup.
