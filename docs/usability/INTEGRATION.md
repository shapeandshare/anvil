# Integration — Spec Kit + OpenCode + OMO (repo-internal)

The ruleset and skills live **inside the host repo** at each framework's default
path. Nothing fetches over the network. One ruleset, two projections (skills),
two checkers — a deterministic gate (`make ux-lint`) and an optional AI deep-pass
(`make ux-review`).

```
docs/ux-rules.md                       ← single source of truth, read locally
.opencode/skills/ux-review/SKILL.md    ← review projection  (audit → findings)
.opencode/skills/ux-generate/SKILL.md  ← generate projection (compliant by construction)
ci/ux_lint.py                          ← deterministic mechanical-S4 linter (zero-dep)
ci/ux_review.py                        ← AI full-ruleset review (optional)
Makefile                               ← make ux-lint / make ux-review
```

## 1. Skills → `.opencode/skills/`

OpenCode loads `.opencode/skills/*/SKILL.md` (plural is the default; singular is
back-compat), walking up to the git worktree, and also reads `.claude/skills/`
and `.agents/skills/` for compatibility. SKILL.md must begin with YAML
frontmatter; only recognized fields are read, unknown ones ignored — so `name` +
`description` drive everything (`argument-hint` is harmless/ignored in OpenCode,
used by Claude Code).
→ https://opencode.ai/docs/skills · https://opencode.ai/docs/config

**OMO** is an OpenCode plugin (`.opencode/oh-my-opencode.json`). Its skill load
priority is **project > user > opencode > builtin/plugin**, so these project-level
skills win, and OMO's agent fleet (Sisyphus, Atlas, …) invokes them through the
`skill` tool. No OMO-specific path or wiring is needed.
→ https://github.com/code-yeongyu/oh-my-openagent (docs/reference/features.md)

## 2. Ruleset → `docs/ux-rules.md`

Kept in `docs/`, **not** `.specify/memory/`, because Spec Kit's `specify init
--force` overwrites `.specify/memory/` on upgrade. `docs/` is durable and
referenceable.
→ https://github.com/github/spec-kit/blob/main/docs/upgrade.md

Both skills read this path. The linter (`ux_lint.py`) does **not** read it — it
carries its own regex `CHECKS`; the ruleset is for the AI review and humans.

## 3. Generate mode (compliance by construction)

With `ux-generate` loaded, builder agents read `docs/ux-rules.md` and treat S4/S3
as hard constraints while writing. The owned sections (server-render
`|safe`/CSRF, coalesced SSE `aria-live`, composited CRT contrast) are where
off-the-shelf agents fail; the skill points them there. For *always-on* context
instead of on-demand, add the path to `opencode.json` `instructions`
(`"instructions": ["docs/ux-rules.md"]`) — heavier, but loaded every turn.
→ https://opencode.ai/docs/rules

## 4. Deterministic gate → `make ux-lint`

`ux_lint.py` is the gate. Pattern-based, zero-dep, no network, no API key.
`make ux-lint` runs it on changed UI/template/`.py` files (vs `origin/main`;
override with `FILES=`). Wire `make ux-lint` into CI when ready; a pre-commit hook
is a deliberate later step (per current decision). OMO's tooling scans the
Makefile, so the targets are discoverable in your workflow.

**Suppression.** The linter flags every `|safe` and `outline:none` for audit, and
blanks delimited comments so a *mention* inside a comment doesn't false-positive.
Clear a verified case with `ux-lint:allow` on the finding's own line, or
`ux-lint:allow-next` on the line above:

```jinja
{{ value | safe }}        {# ux-lint:allow sanitized in service layer #}
```
```css
*:focus { outline: 0 }    /* ux-lint:allow box-shadow focus ring below */
```

## 5. AI review → `make ux-review`

The full-ruleset pass for depth the linter can't reach (keyboard traps,
per-chunk-vs-coalesced SSE, semantic nuance). Reads the repo-internal ruleset by
default. Two routes for the model:
- **Script route** (`make ux-review`): set `UX_API_KEY` and point
  `UX_MODEL_BASE_URL`/`UX_MODEL` at your fleet/router (OpenRouter or local —
  OpenAI-compatible). `temperature: 0`.
- **Agent route:** the `ux-review` skill invoked by an OMO agent uses that agent's
  assigned model (OMO agents ignore the UI-selected model by design).

## 6. Severity × enforceability

Per `docs/ux-rules.md`. **Severity** (S4–S1) = how bad. **Enforceability**:
`(lint)` rules are what the deterministic gate proves; *unmarked* rules are
AI-review-judgeable from source; `(test)` rules (composited CRT contrast,
input-length robustness) are runtime/visual and **never gate**. The linter's
`aria-live="assertive"` check is a *proxy* — a per-chunk `polite` stream still
needs the AI review or a runtime test.

## 7. Spec Kit SDD wiring

Add a principle to `.specify/memory/constitution.md`, e.g.:

> **UI compliance (MUST).** All UI, template, and CSS work MUST comply with
> `docs/ux-rules.md`. S4/S3 findings block; resolve them, never dilute the rule.

`/speckit.analyze` treats constitution MUST principles as CRITICAL, so UX
violations surface in the spec→plan→tasks consistency pass before
`/speckit.implement`. Optionally, `/speckit.tasks` output can include a
`make ux-lint` verification task per UI feature.
→ https://github.com/github/spec-kit

## 8. Rebind points

The repo will likely namespace these — change deliberately, in one pass:

- **Ruleset path** `docs/ux-rules.md` — in both SKILL.md bodies + `ux_review.py:DEFAULT_RULES`.
- **Env vars** `UX_API_KEY` / `UX_MODEL` / `UX_MODEL_BASE_URL` / `UX_RULES` / `UX_GATE`.
- **Suppression directive** `ux-lint:allow` / `ux-lint:allow-next` (in `ux_lint.py`).
- **Finding format** `[S<n>] <category> — …` and the `GATE: PASS|FAIL` tally.
- **Skill names** `ux-review` / `ux-generate`.

## Lineage / license

Behavioral core adapted from the Vercel Web Interface Guidelines (MIT) with
framework- and brand-specific rules removed; severity / dedup / injection-
quarantine model adapted from Rune; owned sections original. Keep the Vercel
attribution in `docs/ux-rules.md` if you redistribute.
