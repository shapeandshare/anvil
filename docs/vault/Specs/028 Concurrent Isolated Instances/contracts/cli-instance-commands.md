# Contract: Instance Lifecycle CLI

CLI-first instance management (FR-022–FR-026, US4). Mirrors the existing `anvil-backup` argparse pattern: `build_parser()` → `main(argv)` → `async def _run(args)` → `_cmd_*` dispatch, using `async with AsyncSessionLocal()`/`AnvilWorkbench` for the registry session. New console entry in `pyproject [project.scripts]`: `anvil-instance = "anvil.services.instances.cli:main"`.

All commands operate against the **global registry** (`~/.anvil/registry.db`) and per-workspace boot files. Each command emits an audit entry (FR-029) for the instance it acts on.

## `anvil-instance create`

Create + register an instance and initialize its workspace (FR-023, FR-023a).

| Arg | Required | Notes |
|---|---|---|
| `name` | yes | Unique, filesystem/URL-safe identifier. Rejected if already registered. |
| `--workspace PATH` | yes | Workspace root. Rejected if equal to / overlapping a registered workspace. |
| `--web-port N` | no | Pinned web port. Omit → auto-allocate a free port (FR-019a). |
| `--mlflow-port N` | no | Pinned MLflow port. Omit → auto-allocate. |

**Behavior**: validate name format + uniqueness; resolve ports (auto or pinned, verified free); create `workspace/` + write `instance.json`; insert `instance_records` row (atomic unique-constraint check); audit `INSTANCE_CREATE`.
**Output**: prints instance name + assigned `web_port`/`mlflow_port`.
**Errors**: duplicate name → exit non-zero, clear message; port/workspace conflict → names the conflict + owning instance.

## `anvil-instance list [--json]`

Enumerate registered instances (FR-024). Columns: `NAME`, `WORKSPACE`, `WEB`, `MLFLOW`, `STATUS`. Status is **recomputed** (PID/process/port probe), never read as stored truth.

## `anvil-instance start <name>`

Acquire the workspace lock (reclaim if stale per FR-021), spawn the instance process detached: `Popen([...serve...], start_new_session=True, cwd=workspace, env=<boot env>)`, write `{workspace}/logs/web.pid`. The instance's lifespan starts MLflow on its `mlflow_port`. Refuse if ports/workspace conflict with a running instance (FR-019/FR-020). Audit `INSTANCE_START`.

## `anvil-instance stop <name>`

`SIGTERM` the recorded process group (verify the PID belongs to this workspace first), wait, escalate to `SIGKILL`; release the workspace lock. Audit `INSTANCE_STOP`.

## `anvil-instance restart <name>`

`stop` then `start` (research.md E). Applies any pending boot-critical config changes on the new boot. Audit `INSTANCE_RESTART`.

## `anvil-instance destroy <name>`

Remove from registry; **delete workspace data by default** (FR-026, clarified). Requires explicit confirmation.

| Arg | Notes |
|---|---|
| `--keep-data` | Preserve workspace on disk; only unregister. |
| `--yes` / typed confirm | Required to proceed (destructive default). |
| `--force` | Stop the instance first if running. |

**Behavior**: require stopped (or `--force`); require confirmation; deregister; delete workspace unless `--keep-data`; audit `INSTANCE_DESTROY` (records whether data deleted or preserved).
**Output**: states clearly whether data was **deleted** or **preserved**.

## Exit codes

`0` success; non-zero on validation failure, collision, missing instance, or confirmation declined. Errors are specific (name the conflict/setting). Status probing never fails the command.
