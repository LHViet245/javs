# Documentation Restructure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure JavS documentation into a professional, role-based set of guides that lets new users succeed quickly, gives power users fast access to practical references, and gives contributors a clear development entrypoint.

**Architecture:** Keep `README.md` as the public landing page, create focused docs for end users, power users, and contributors, and reduce overlap in legacy docs by converting them into navigation or redirect pages. No runtime behavior should change; all work stays in documentation structure, navigation, and doc quality.

**Tech Stack:** Markdown, repo-local command examples, existing JavS CLI, pytest, Ruff, ripgrep

---

### Task 1: Audit Current Documentation Inputs

**Files:**
- Read: `README.md`
- Read: `docs/USAGE.md`
- Read: `docs/PLAYBOOK.md`
- Read: `CONTEXT.md`
- Read: `report.md`
- Read: `plan.md`
- Reference: `docs/superpowers/specs/2026-04-03-documentation-restructure-design.md`
- Output note: `docs/superpowers/plans/2026-04-03-documentation-restructure.md`

- [ ] **Step 1: Re-read the approved spec before implementation**

Run:

```bash
sed -n '1,260p' docs/superpowers/specs/2026-04-03-documentation-restructure-design.md
```

Expected: the approved architecture, reader journey, and writing standards are visible.

- [ ] **Step 2: Re-scan current user-facing docs for overlap**

Run:

```bash
sed -n '1,220p' README.md
sed -n '1,260p' docs/USAGE.md
sed -n '1,260p' docs/PLAYBOOK.md
```

Expected: enough context to identify duplicated sections, weak onboarding, and where old content should migrate.

- [ ] **Step 3: Re-scan contributor-facing project context docs**

Run:

```bash
sed -n '1,220p' CONTEXT.md
sed -n '1,220p' report.md
sed -n '1,220p' plan.md
```

Expected: contributor-facing context is visible so new docs can link correctly without duplicating internal project notes.

- [ ] **Step 4: Capture the final file map before editing**

Record this structure in implementation notes:

- `README.md` becomes the strong landing page
- `docs/getting-started.md` is the end-user tutorial
- `docs/configuration.md` is the practical config guide
- `docs/commands.md` is the command reference
- `docs/troubleshooting.md` is symptom-based support
- `docs/contributor-guide.md` is the contributor entrypoint
- `docs/USAGE.md` becomes a docs index
- `docs/PLAYBOOK.md` becomes a slim redirect/compatibility page

- [ ] **Step 5: Commit nothing in this task**

Reason: this task is context gathering only and should roll directly into the document rewrite tasks.

### Task 2: Rewrite `README.md` As The Public Landing Page

**Files:**
- Modify: `README.md`
- Reference: `docs/getting-started.md`
- Reference: `docs/configuration.md`
- Reference: `docs/commands.md`
- Reference: `docs/troubleshooting.md`
- Reference: `docs/contributor-guide.md`

- [ ] **Step 1: Write the new README outline before rewriting prose**

Draft these sections directly in `README.md`:

- Project summary
- Who JavS is for
- What JavS does well
- What JavS does not do
- 5-minute quick start
- First safe workflow
- Documentation map by role
- Feature overview
- Contributor and verification note

- [ ] **Step 2: Replace the current intro with a stronger landing-page intro**

Requirements:

- explain what JavS is in one paragraph
- explain why someone would choose it
- stay factual and professional
- do not bury the quick start below long feature marketing copy

- [ ] **Step 3: Add a 5-minute quick start with runnable commands**

Use repo-accurate commands such as:

```bash
python3 -m venv venv
./venv/bin/pip install -e ".[dev]"
./venv/bin/javs --help
./venv/bin/javs find "ABP-420"
```

The quick start should let a user confirm JavS works before they touch a real library.

- [ ] **Step 4: Add a “first safe workflow” section**

Include:

- test one ID with `find`
- preview a sort
- run a real sort on a small folder
- inspect results
- use `update` later for in-place refreshes

- [ ] **Step 5: Add a role-based docs map**

Link readers clearly to:

- `docs/getting-started.md`
- `docs/configuration.md`
- `docs/commands.md`
- `docs/troubleshooting.md`
- `docs/contributor-guide.md`

- [ ] **Step 6: Run a focused readability pass**

Checklist:

- remove duplicated explanations that belong in deeper docs
- keep headings short
- keep examples copy-pasteable
- ensure `README.md` reads well from top to bottom

- [ ] **Step 7: Run a targeted diff review**

Run:

```bash
git diff -- README.md
```

Expected: the file now reads like a strong landing page instead of a mixed summary/reference page.

- [ ] **Step 8: Commit the README rewrite**

Run:

```bash
git add README.md
git commit -m "docs: rewrite readme as landing page"
```

### Task 3: Create The New End-User And Power-User Docs

**Files:**
- Create: `docs/getting-started.md`
- Create: `docs/configuration.md`
- Create: `docs/commands.md`
- Create: `docs/troubleshooting.md`
- Reference: `README.md`
- Reference: `javs/data/default_config.yaml`
- Reference: `javs/cli.py`

- [ ] **Step 1: Create `docs/getting-started.md` with a complete beginner path**

Sections to include:

- who this guide is for
- before you start
- installation
- config creation/check
- first `find`
- preview sort
- first real sort
- checking output
- first `update`
- next steps

- [ ] **Step 2: Create `docs/configuration.md` as a practical config guide**

Sections to include:

- config file location
- safe starter defaults
- file locations
- matching modes
- scraper enablement and priorities
- sort and naming
- NFO options
- CSV templates
- translation
- proxy
- Javlibrary credentials
- config sync

- [ ] **Step 3: Create `docs/commands.md` as a command reference**

Cover:

- global usage pattern
- `find`
- `sort`
- `update`
- `config`
- `scrapers`

For each command include:

- purpose
- when to use it
- syntax
- examples
- expected outcome
- common mistakes

- [ ] **Step 4: Create `docs/troubleshooting.md` as a symptom-based guide**

Cover at least:

- no files were processed
- some files were skipped
- wrong ID matched
- Javlibrary blocked by Cloudflare
- proxy test failed
- translation provider unavailable
- update did not refresh what I expected
- source directory was not removed

- [ ] **Step 5: Run a consistency pass across the four new docs**

Checklist:

- no duplicated long explanations between files
- commands match the real CLI
- configuration names match the real config keys
- troubleshooting advice reflects current runtime behavior

- [ ] **Step 6: Run a focused diff review**

Run:

```bash
git diff -- docs/getting-started.md docs/configuration.md docs/commands.md docs/troubleshooting.md
```

Expected: the new docs exist, are clearly role-based, and do not read like raw notes.

- [ ] **Step 7: Commit the new user docs**

Run:

```bash
git add docs/getting-started.md docs/configuration.md docs/commands.md docs/troubleshooting.md
git commit -m "docs: add role-based user guides"
```

### Task 4: Add The Contributor Entry Point And Simplify Legacy Docs

**Files:**
- Create: `docs/contributor-guide.md`
- Modify: `docs/USAGE.md`
- Modify: `docs/PLAYBOOK.md`
- Reference: `AGENTS.md`
- Reference: `CONTEXT.md`
- Reference: `report.md`
- Reference: `plan.md`

- [ ] **Step 1: Create `docs/contributor-guide.md`**

Required sections:

- who this guide is for
- local setup
- required `venv` usage
- test and lint commands
- where runtime logic belongs
- regression expectations
- doc maintenance rules
- links to `AGENTS.md`, `CONTEXT.md`, `report.md`, `plan.md`

- [ ] **Step 2: Convert `docs/USAGE.md` into a docs index**

Requirements:

- keep the file path for continuity
- reduce it to a clean navigation page
- point to the new canonical docs by role and purpose
- avoid repeating full tutorial/reference content

- [ ] **Step 3: Convert `docs/PLAYBOOK.md` into a slim redirect or compatibility page**

Requirements:

- keep the path alive if possible
- explain that the canonical end-user path now starts in `docs/getting-started.md`
- point troubleshooting readers to `docs/troubleshooting.md`
- avoid leaving stale workflow details that can drift

- [ ] **Step 4: Run a navigation review**

Checklist:

- a new user can start from `README.md` and find the right next doc
- a contributor can start from `README.md` and find contributor docs
- `docs/USAGE.md` and `docs/PLAYBOOK.md` no longer compete with the new canonical docs

- [ ] **Step 5: Commit the navigation and contributor docs**

Run:

```bash
git add docs/contributor-guide.md docs/USAGE.md docs/PLAYBOOK.md
git commit -m "docs: add contributor guide and simplify legacy docs"
```

### Task 5: Final Polish, Verification, And Link Review

**Files:**
- Review: `README.md`
- Review: `docs/getting-started.md`
- Review: `docs/configuration.md`
- Review: `docs/commands.md`
- Review: `docs/troubleshooting.md`
- Review: `docs/contributor-guide.md`
- Review: `docs/USAGE.md`
- Review: `docs/PLAYBOOK.md`

- [ ] **Step 1: Run a repo docs link/content scan**

Run:

```bash
rg -n "docs/USAGE.md|docs/PLAYBOOK.md|getting-started|configuration.md|commands.md|troubleshooting.md|contributor-guide.md" README.md docs CONTEXT.md report.md plan.md
```

Expected: internal links point to the new canonical docs and no obvious stale navigation remains.

- [ ] **Step 2: Run the full verification suite**

Run:

```bash
./venv/bin/python -m pytest tests -q
./venv/bin/python -m ruff check javs tests
```

Expected:

- pytest passes
- Ruff passes

- [ ] **Step 3: Run a final status and diff review**

Run:

```bash
git status --short
git diff --stat
```

Expected: only the intended documentation files are changed.

- [ ] **Step 4: Write a concise summary in the final handoff**

Include:

- what changed in the docs structure
- which files are now canonical for which audience
- verification commands run and results
- any intentionally retained legacy redirects/pages

- [ ] **Step 5: Commit the final polish if needed**

Run:

```bash
git add README.md docs/getting-started.md docs/configuration.md docs/commands.md docs/troubleshooting.md docs/contributor-guide.md docs/USAGE.md docs/PLAYBOOK.md
git commit -m "docs: polish documentation navigation and guidance"
```

Only do this commit if the polish pass introduces additional changes beyond prior task commits.
