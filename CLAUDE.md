# SlurmHub

SlurmHub is a terminal-based user interface (TUI) application designed to monitor and display Slurm job statuses in real-time. It leverages the Textual framework for building rich terminal applications, giving users an intuitive interface for tracking their jobs on a Slurm-managed cluster. What follows is how to work in this codebase, read as a single set of instructions: the context and workflow to follow, the tooling, demo mode, and the behavioral guidelines that should shape every change.

Before taking actions, skim `CHANGELOG.md` for the latest release notes and the Sphinx documentation under `docs/` for user-facing behavior. After implementing code changes, update `CHANGELOG.md` (and `README.md` when the public surface changes), then create a git commit (pre-commit hooks will run automatically). When you add new features, create a new test under `tests/` to verify the feature works as intended.

The tooling is consistent throughout: use `uv` for running the application, `pytest` for the test suite, `pre-commit` for code quality, and `sphinx-build` (via `uv sync --group docs`) for building the documentation site locally. To work without a live cluster, `uv run slurmhub --demo` launches the app against a built-in fixture dataset (no SSH needed) — useful for screenshots, demos, and reproducing UI bugs. Screenshot generation for the docs lives at `docs/scripts/generate_screenshots.py`.

Alongside that workflow, the principles below reduce common LLM coding mistakes and apply to every change. They bias toward caution over speed, so for trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.
