---
name: Review
description: "Review an implementation after a code change and before committing or pushing. Start a reviewer with fresh context and the project's established checks, then verify its findings before applying fixes."
metadata:
  opencode/autoinvoke: true
---

# Review

Use a reviewer with **fresh context** who did not take part in the
implementation. The checks come from failures the project has encountered.

The reviewer reports findings. The primary agent decides how to handle them
and applies any fixes. This preserves separation between author and reviewer.

## When to run it

Review is **not optional**: run it after implementation and before committing
or pushing.
Run it also when the user requests a review, second opinion, or audit.

Skip review for changes that leave behavior unchanged, such as comments,
prose, or a behavior-preserving refactor. Schema, configuration, tool
interface, and security changes require review.

## Time budget

**Run one review and complete it in under 10 minutes.**

Early reviews took between 5 and 66 minutes. Cloning, installing a new
environment, building mutation harnesses, and researching the platform
accounted for most of that time. The primary agent already has the
environment for any needed checks.

1. **The reviewer works in the existing tree.** It already contains the
   change and dependencies. The reviewer skips cloning and installation.
2. **The primary agent performs mutations.** If the reviewer questions a
   test's coverage, temporarily revert the fix yourself and run the test.
3. **Platform research is outside the review scope.** Record unclear
   OpenCode behavior in the unverified section of the report.

Run one review by default. If the reviewer identifies a critical defect,
fix it and decide whether the new change warrants another pass.

## Workflow

### 1. Prepare the scope

Give the reviewer the complete diff, including new files.

```bash
git status --short          # 1. look first at what is in the tree
git add -A                  # 2. stage everything
# 3. REMOVE from the index the work in progress that is not part of this change:
#    git restore --staged <file>
git diff --cached > /tmp/revision.diff   # 4. the diff, clean
git log --oneline -5
```

Run `git restore --staged` before writing the diff. Unstaging a file after
export leaves it in the saved diff.

`git add -A` prepares the index for the commit and includes new files in
the staged diff. It stages the entire tree, which may include unrelated
work in progress, notes, debugging files, or an unignored `.env`. Inspect
`git status` and unstage unrelated files before exporting the diff.

If the diff is empty and the change is already committed, supply that commit
with `git show <sha>` in `{{DIFF}}` and the SHA in `{{COMMITS}}`. Save the
`git show` output in `/tmp/revision.diff`, the path used in step 5.

Regenerate the diff from the corrected tree before repeating a review.

### 2. Run the checks and capture their output

The reviewer reads the supplied output and has no shell. A command allowlist
would still let commands write through arguments such as `ruff check --fix`,
`git diff --output=`, or `pytest --junit-xml=`.

Run and save tests and lint before starting the reviewer.

```bash
{
  echo "== pytest =="
  .venv/bin/pytest -q -ra 2>&1
  echo "exit=$?"
  echo "== ruff format --check =="
  .venv/bin/ruff format --check . 2>&1
  echo "exit=$?"
  echo "== ruff check =="
  .venv/bin/ruff check . 2>&1
  echo "exit=$?"
} > /tmp/revision-tests.txt 2>&1
```

`-ra` gives the reviewer the identities and reasons for skipped tests,
which helps determine whether the change caused any skips.

`ruff format .` rewrites files and can mask a pre-existing formatting
problem. Use `ruff format --check .` for verification.

Capture fresh output from the corrected code before repeating a review.

### 3. Start the reviewer

The reviewer is a subagent with fresh context. Read the full prompt at
`references/auditoria.md`, relative to this skill's base directory.
OpenCode supplies that directory in a line beginning with
`Base directory for this skill:`. Use the absolute path with `read` and
fill the scope placeholders in the prompt. Resolving it from the
repository root may fail when the session starts in a subdirectory.

Start it with the `subagent` tool.

- `agent`: `reviewer` (`.opencode/agents/reviewer.md`). This agent lacks
  shell, edit, and subagent permissions.
- `description` is `Review the implementation`.
- `prompt` is the text of `references/auditoria.md` with five placeholders
  filled in. Use `{{REPOSITORIO}}`, `{{DIFF}}`, `{{ALCANCE}}`, `{{COMMITS}}`,
  and `{{SALIDA_PRUEBAS}}`. The last one points to the test and lint output
  from step 2.

`{{DIFF}}` and `{{SALIDA_PRUEBAS}}` take file paths, so the reviewer can
open them with the read tool.

The `reviewer` sets the default model to MiniMax M3.1 Flash, as requested.
Pass a model override through the tool if the user asks for a different one.

The reviewer has no shell, and editing, writing, patching, subagent launches,
and Code Mode are denied. It can use the existing tree without applying
patches, reverting files, or installing dependencies. The read tool enforces
secret protection.

OpenCode's own worktree and session management tools do not pass through
these denials and do not edit project files.

### 4. Verify findings

The reviewer can miss defects or report issues that cannot be reproduced.
Verify each finding before acting.

- If a test allegedly fails, run it and inspect the failure.
- If an `ALTER TABLE` is allegedly missing, inspect the migration.
- If a test allegedly fails to cover a behavior, temporarily revert the fix
  and confirm whether the test fails. A manual check is enough.

Address confirmed defects and report any findings discarded after verification.

### 5. Complete the primary agent's checks

`AGENTS.md` assigns both checks below to the primary agent.

**a. Verify in a clean clone.** Do this after review. A fresh clone and
environment were a major source of review latency when the reviewer ran them.

Regenerate the diff after fixes. The original diff predates them and can
produce a false pass against the wrong code.

```bash
git add -A
git diff --cached > /tmp/revision.diff
```

A clone starts at the latest commit. For uncommitted work, apply the diff
with `--index` so the fictitious-data detector sees new tracked files. For
committed work, clone the commit and omit the patch step.

Make a failed `git apply` stop the script. Otherwise the checks may run
against the old code.

```bash
set -e
TMP=$(mktemp -d); git clone . "$TMP/ci"; cd "$TMP/ci"
# If the change is not committed, apply it (with --index).
# If it already is, the clone carries it: do not apply anything.
git apply --index /tmp/revision.diff
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt -r requirements-dev.txt
.venv/bin/ruff format --check . && .venv/bin/ruff check .
.venv/bin/pytest
PYTHONSAFEPATH=1 .venv/bin/pytest
```

Investigate both a `patch does not apply` error, which can mean the clone
already contains the change, and a `can't open` error, which indicates an
incorrect diff path.

**b. Verify that each new test fails without the fix.** Temporarily revert
only the fix, keep the new test, and run it. This confirms that the test
detects the intended regression.

Look for an assertion failure inside the test. An `ImportError` or
`AttributeError` fails for a different reason. If pytest reports
`no tests ran`, check whether you reverted the test itself.

### 6. Decide whether to repeat the review

**A review is not a cycle.** After fixing a critical finding, decide whether
another pass is needed.

- For a change to **behavior** or a **public interface**, regenerate the
  diff and run another review.
- For a prose edit, a test adjustment, or an internal detail, verify the
  result with tests yourself.

Additional reviews take time. The first pass supplies the fresh perspective.

### 7. Report the result

Tell the user what was reviewed, which findings were confirmed or dismissed,
and what remains unverified. For example, record that the image could not be
tested if Docker was unavailable.

## Review limits

- The reviewer reads test results. The primary agent must supply any missing
  coverage and run the checks.
- The reviewer sees the diff and the supplied context. Read the surrounding
  code to identify design defects beyond the diff.
- A reviewer using the same model as the primary agent can share its blind
  spots. Fresh context and the checklist still provide a separate pass.
- The ten-minute budget prioritizes deployment failures, security defects,
  and ineffective tests. Report which details were outside the review.

## Editing the report

Clean up mixed-language phrasing and other output artifacts before sharing the
report. Present the report to the user in Spanish, as requested by this
workflow.

MiniMax may also emit stray CJK characters. The optional global skill
`limpieza-cjk` can remove them. It is not part of this repository. If it is
unavailable, remove stray characters manually.
