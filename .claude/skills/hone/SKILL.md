---
name: hone
description: Run iterative codebase improvement with hone CLI; use when user asks to hone, iterate, maintain dependencies, assess, improve code quality, set up or fix quality gates, derive agents, mix agents, or check iteration history
---

# Hone CLI

Hone wraps an LLM in a deterministic verification loop to iteratively improve codebases. The agent proposes improvements; hone independently verifies them through quality gates. The agent never self-certifies.

## Quick Reference

| Task | Command |
|------|---------|
| First-time setup | `hone derive /path/to/project` |
| Run one improvement | `hone iterate <agent> /path/to/project` |
| Update dependencies | `hone maintain <agent> /path/to/project` |
| Augment a local agent | `hone mix <agent> <folder> --from <global-agent> --principles --gates` |
| Check available agents | `hone list-agents` |
| Show quality gates | `hone gates /path/to/project` |
| Run quality gates | `hone gates /path/to/project --run` |
| View past iterations | `hone history /path/to/project` |
| Iterate with external audit dir | `hone iterate <agent> /path/to/project --audit-dir /tmp/audits` |
| Show configuration | `hone config` |

## Prerequisites

Before using hone, verify:

1. **Claude Code CLI** (`claude`) is installed and authenticated
2. **hone** is installed (`brew install svetzal/tap/hone` on macOS)
3. For GitHub mode: **GitHub CLI** (`gh`) is installed and authenticated

```bash
hone --version
claude --version
```

## Establishing Quality Gates

Quality gates are the foundation of hone's value. Without reliable gates, the verify stage has nothing to enforce and the agent can self-certify by default. **Extracted gates from agents are unreliable** — they often reference wrong commands, missing tools, or incorrect paths for the specific project. Always establish gates manually through interactive validation.

### The Gate File

Gates live in `.hone-gates.json` in the project root. This file is version-controlled and takes priority over any LLM-based extraction.

```json
{
  "gates": [
    { "name": "test", "command": "bun test", "required": true },
    { "name": "typecheck", "command": "bunx tsc --noEmit", "required": true },
    { "name": "lint", "command": "bunx biome check src", "required": true },
    { "name": "security", "command": "osv-scanner .", "required": false }
  ]
}
```

Each gate has three fields:
- `name` — short identifier shown in output
- `command` — exact shell command run via `sh -c` in the project directory
- `required` — `true` triggers the retry loop on failure; `false` reports but doesn't block

### Interactive Gate Setup Workflow

When helping a user establish gates, work through this process **one gate at a time**:

#### Step 1: Discover what the project uses

Examine the project root for tooling signals:

| File | Likely gates |
|------|-------------|
| `package.json` | `npm test`, `npm run lint`, `npx tsc --noEmit`, `npm audit` |
| `mix.exs` | `mix test`, `mix credo --strict`, `mix format --check-formatted`, `mix deps.audit` |
| `pyproject.toml` | `pytest`, `ruff check src`, `ruff format --check src`, `pip-audit` |
| `CMakeLists.txt` | `ctest --output-on-failure`, `cppcheck --enable=all src/` |
| `Cargo.toml` | `cargo test`, `cargo clippy -- -D warnings`, `cargo audit` |
| `go.mod` | `go test ./...`, `golangci-lint run`, `govulncheck ./...` |
| `bun.lockb` / `bunfig.toml` | `bun test`, `bunx tsc --noEmit`, `bunx biome check src` |

Check `package.json` scripts, CI config files (`.github/workflows/`, `.gitlab-ci.yml`), Makefiles, and existing linter configs (`.eslintrc`, `biome.json`, `.credo.exs`, `ruff.toml`) for the **actual commands the project already uses**.

Do NOT guess — read the project files.

#### Step 2: Test each command individually

Before adding any gate, run the candidate command in the project directory and observe the result:

```bash
cd /path/to/project && bun test
```

There are only three outcomes:

1. **Passes (exit 0)** — Add it to `.hone-gates.json`
2. **Fails (non-zero exit)** — Investigate why. The project may have pre-existing failures, wrong paths, or missing configuration. Fix the underlying issue or adjust the command, then re-run.
3. **Command not found** — The tool isn't installed. Help the user install it or choose an alternative that's already available.

**Do not add a gate that doesn't pass on the unmodified codebase.** Hone's preflight stage runs all gates before any LLM work begins. If a required gate fails at preflight, hone stops immediately — the baseline is broken and there's no point sending an agent to fix environment problems.

#### Step 3: Build the gates file incrementally

Start with an empty gates file and add one gate at a time after each passes:

```json
{ "gates": [] }
```

Add the most important gate first (usually tests), verify it works, then add the next. A typical build order:

1. **test** — Does the test suite pass? This is the most critical gate.
2. **typecheck** — Does the project have static type checking configured?
3. **lint** — Is there a linter configured and passing?
4. **format** — Is there a formatter in check mode? (Often combined with lint via `&&`)
5. **security** — Is there an audit tool available? (Usually `required: false`)

#### Step 4: Verify the full gate set together

After building the file, run all gates through hone to confirm:

```bash
hone gates /path/to/project --run
```

This runs each gate sequentially and reports pass/fail per gate, just as hone's preflight and verify stages will.

### Common Gate Problems and Fixes

**Test gate fails with missing dependencies:**
The test suite needs setup first. Check if `npm install` / `bun install` / `mix deps.get` needs to run. Gates assume dependencies are already installed.

**Lint gate fails on files outside the project scope:**
Narrow the command path. Instead of `eslint .` try `eslint src` or check the lint config for `ignorePatterns`.

**Typecheck gate fails on generated files:**
Add excludes to `tsconfig.json` or narrow the scope: `tsc --noEmit --project tsconfig.build.json`.

**Security gate fails on known vulnerabilities:**
Mark security gates as `required: false` so they report without blocking. Or use `npm audit --audit-level=high` to only fail on high/critical.

**Format gate fails immediately:**
The codebase hasn't been formatted yet. Run the formatter once (`mix format`, `ruff format src`, `npx biome format --write src`) to establish the baseline, then add the check-mode gate.

**Command works in terminal but fails in hone:**
Hone runs commands via `sh -c` with the project directory as `cwd`. Check that:
- The command doesn't rely on shell aliases or functions
- PATH includes the tool (use full paths like `npx`, `bunx` if needed)
- The command doesn't need an interactive terminal

**Gate passes locally but takes too long:**
The default gate timeout is 120 seconds. Large test suites may need more time. Adjust `gateTimeout` in `~/.config/hone/config.json` or split slow gates so fast ones still provide quick feedback.

### Combining Related Commands

Use `&&` to combine commands that form a single logical gate:

```json
{ "name": "lint", "command": "mix credo --strict && mix format --check-formatted", "required": true }
```

Both must pass for the gate to pass. This keeps the gates file concise and groups related checks.

### When to Use `required: false`

Non-required gates provide information without blocking iteration. Use for:
- Security audits (often have findings outside developer control)
- Style checks that are aspirational rather than enforced
- Slow checks you want visibility into but don't want blocking the retry loop

A failed non-required gate still appears in output — the developer sees it, but hone won't send the agent into a retry loop over it.

## Workflows

### New Project Setup

For a project that has never used hone:

```bash
# 1. Generate agent (gates file from derive is a starting point only)
hone derive /path/to/project

# 2. Review the generated agent
hone list-agents

# 3. Establish quality gates interactively (see above)
#    Do NOT trust the derived .hone-gates.json — validate every gate

# 4. Run first iteration once gates are solid
hone iterate <agent-name> /path/to/project
```

### Running an Improvement Iteration (Local Mode)

Local mode executes immediately without approval gates:

```bash
# Basic iteration
hone iterate typescript-craftsperson ./src

# Skip quality gates (when setting up, before gates are established)
hone iterate python-craftsperson . --skip-gates

# More retries for complex fixes
hone iterate elixir-phoenix-craftsperson ./apps/web --max-retries 5

# Skip triage to force execution of even low-severity findings
hone iterate cpp-qt-craftsperson . --skip-triage

# Raise the severity bar (only fix critical issues)
hone iterate typescript-craftsperson . --severity-threshold 4

# Send audit logs to an external directory (absolute path)
hone iterate typescript-craftsperson . --audit-dir ~/hone-audits/my-project
```

### Running an Improvement Iteration (GitHub Mode)

GitHub mode creates issues for human approval before executing:

```bash
# Single proposal
hone iterate typescript-craftsperson ./src --mode github

# Multiple proposals per run
hone iterate typescript-craftsperson ./src --mode github --proposals 3
```

Each GitHub-mode invocation:
1. Closes issues the repo owner has thumbs-downed
2. Executes approved (thumbs-up) issues oldest-first
3. Creates new proposal issues

Re-invoke via cron or CI to process approvals — hone does not poll.

### Maintaining Dependencies

Maintain proactively updates dependencies and verifies gates still pass. Unlike iterate, there is no assess/triage/plan pipeline — it goes straight to execution with a verify/retry loop.

```bash
# Basic dependency update
hone maintain typescript-craftsperson ./src

# More retries for complex breakage
hone maintain python-craftsperson . --max-retries 5

# Use a stronger model for tricky updates
hone maintain elixir-craftsperson . --execute-model opus

# Send audit logs to an external directory
hone maintain typescript-craftsperson . --audit-dir ~/hone-audits/my-project
```

Maintain requires gates to be configured — it exits with an error if no gates are found. The agent provides coding context/principles for making good fixes during retries.

Audit files use `maintain-YYYY-MM-DD-HHMMSS` naming in the project's audit directory.

### Mixing Agents

Mix augments a local (project-specific) agent with ideas from a global agent. Useful when you've derived a local agent and want to incorporate principles or gates from a broader agent:

```bash
# Mix engineering principles from a global agent into a local one
hone mix local-agent . --from typescript-craftsperson --principles

# Mix quality gates
hone mix local-agent . --from typescript-craftsperson --gates

# Mix both
hone mix local-agent . --from typescript-craftsperson --principles --gates
```

The local agent must exist in `<folder>/.claude/agents/`. The foreign agent (`--from`) must exist in `~/.claude/agents/`. Separate Claude calls per aspect prevent cross-contamination.

### Reviewing History

```bash
hone history /path/to/project

# History from an external audit directory
hone history /path/to/project --audit-dir ~/hone-audits/my-project
```

Audit files live in `<project>/audit/` (or the path specified by `--audit-dir`) as markdown:
- `<name>.md` — Assessment
- `<name>-plan.md` — Plan
- `<name>-actions.md` — What the agent did
- `<name>-retry-N-actions.md` — Retry attempts

## Pipeline Stages

Each `hone iterate` runs this pipeline:

```
Charter Check → Preflight → Assess → Name → Triage → Plan → Execute → Verify → Summarize
```

| Stage | Model | Access | Skip Flag |
|-------|-------|--------|-----------|
| Charter Check | none | read-only | `--skip-charter` |
| Preflight | none | subprocess | `--skip-gates` |
| Assess | opus | read-only | — |
| Name | haiku | read-only | — |
| Triage | haiku | read-only | `--skip-triage` |
| Plan | opus | read-only | — |
| Execute | sonnet | full | — |
| Verify | none | subprocess | `--skip-gates` |
| Summarize | haiku | read-only | — (only runs on success) |

Override models with `--assess-model`, `--plan-model`, `--execute-model`, `--summarize-model`.

Override audit directory with `--audit-dir <path>` (relative to project, or absolute). Available on `iterate`, `maintain`, and `history` commands.

## Charter Requirement

Hone requires project intent documentation before it will run. It looks for:
- `CHARTER.md`
- `CLAUDE.md` with a `## Project Charter` section
- `README.md`
- A `description` field in package manager config

Content must meet minimum length (default 100 chars, override with `--min-charter-length`). Skip with `--skip-charter`.

## Triage Behavior

After assessment, proposals pass through two filters:

1. **Severity threshold** — Below the threshold (default 3, scale 1-5) rejects immediately
2. **Busy-work detection** — Rejects: adding comments to unchanged logic, reorganizing imports, single-use abstractions, "consistency" refactors

When triage rejects, hone exits with success — the codebase is in good shape.

## JSON Output

All commands support `--json` for machine-readable output:

```bash
hone iterate typescript-craftsperson . --json 2>/dev/null | jq .success
hone gates . --run --json | jq '.results[] | select(.passed == false)'
```

Successful runs include `headline` (max 72 chars, imperative, for git commit subject) and `summary` (2-5 lines, for git commit body) fields:

```bash
hone iterate agent . --json 2>/dev/null | jq -r '.headline'
hone maintain agent . --json 2>/dev/null | jq -r '.summary'
```

## Configuration

Defaults in `~/.config/hone/config.json`:

```json
{
  "models": {
    "assess": "opus",
    "name": "haiku",
    "plan": "opus",
    "execute": "sonnet",
    "gates": "sonnet",
    "derive": "opus",
    "triage": "haiku",
    "mix": "opus",
    "summarize": "haiku"
  },
  "auditDir": "audit",          // relative to project, or absolute path
  "maxRetries": 3,
  "gateTimeout": 120000,
  "mode": "local",
  "minCharterLength": 100,
  "severityThreshold": 3
}
```

CLI flags override config per invocation.

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "No charter found" | Add CHARTER.md, README.md, or use `--skip-charter` |
| Preflight fails | Gates are broken on the unmodified codebase — fix gates before iterating |
| Triage rejects everything | Codebase is in good shape, or lower `--severity-threshold` |
| Agent can't fix gate failures | Increase `--max-retries` or fix manually and re-run |
| No agents found | Run `hone list-agents` and `hone derive .` to generate one |
| Gates not detected | Create `.hone-gates.json` manually — don't rely on extraction |
| Iterate hangs at verify | A gate command may be hanging — check `gateTimeout` and test commands individually |
