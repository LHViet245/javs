# JavS Documentation Restructure Design

## Summary

This design restructures JavS documentation into one strong public landing page and a role-based
documentation set for end users, power users, and contributors.

The goal is to make JavS feel immediately usable and professionally documented:

- a new user should be able to install JavS and complete a safe first run without guessing
- a power user should be able to find configuration and command details quickly
- a contributor should know where to start, how to verify changes, and where architecture context lives

The documentation set should feel complete from A to Z without forcing readers to reconstruct the
workflow from multiple overlapping guides.

## Goals

- Make `README.md` strong enough to serve as a true landing page and onboarding entrypoint
- Separate tutorial content from command reference and configuration reference
- Organize docs by reader role instead of letting one large guide try to serve everyone
- Reduce overlap between `README.md`, `docs/USAGE.md`, and `docs/PLAYBOOK.md`
- Keep stable internal project documents (`CONTEXT.md`, `report.md`, `plan.md`) in place without
  mixing them into user onboarding
- Improve professionalism, scannability, and practical usability of the repo docs

## Non-Goals

- No product behavior changes
- No CLI redesign
- No config schema redesign
- No generated documentation site or external docs tooling in this phase
- No rewrite of archival design-plan documents under `docs/superpowers/`

## Target Audiences

### End Users

People who want to install JavS, test it safely, and organize a real media folder with minimal
friction.

They need:

- a short explanation of what JavS is
- a safe first-run path
- examples they can copy directly
- symptom-based troubleshooting when something goes wrong

### Power Users

People who want to tune scraper behavior, matching rules, translation, proxies, CSV templates, and
batch workflows.

They need:

- faster access to config guidance
- a complete but readable command reference
- practical defaults and warnings about common bad setups

### Contributors

People working on the repo itself.

They need:

- local setup
- verification workflow
- architecture/document map
- coding and testing expectations
- links to source-of-truth project context

## Proposed Documentation Architecture

### Keep

- `README.md`
- `CONTEXT.md`
- `report.md`
- `plan.md`

### Create

- `docs/getting-started.md`
- `docs/configuration.md`
- `docs/commands.md`
- `docs/troubleshooting.md`
- `docs/contributor-guide.md`

### Transform

- `docs/USAGE.md`
  - convert from mixed long-form guide into a concise documentation index / navigation page
  - keep the path for link continuity

### Retire Or Redirect

- `docs/PLAYBOOK.md`
  - stop treating it as the primary end-user guide
  - either replace it with a short redirect page or reduce it to a slim “workflow summary” that
    points to `docs/getting-started.md` and `docs/troubleshooting.md`

Recommendation:

- keep `docs/USAGE.md` as a docs index
- keep `docs/PLAYBOOK.md` only as a short compatibility/redirect page

## File Responsibilities

### `README.md`

Purpose:

- public landing page
- balanced overview plus quick start
- first page for all readers

Required sections:

- one-paragraph value proposition
- who JavS is for
- what JavS does well and what it does not do
- 5-minute quick start
- first safe workflow
- docs map by role
- feature overview
- development and verification note
- contribution links

What it must not become:

- a full config manual
- a giant command reference
- a contributor-only document

### `docs/getting-started.md`

Purpose:

- end-user tutorial from zero to successful first use

Required sections:

- before you start
- install
- create or inspect config
- test one movie with `find`
- preview a sort
- run a real sort
- inspect the output
- refresh metadata with `update`
- next steps
- when to read troubleshooting

### `docs/configuration.md`

Purpose:

- practical config guide for normal and advanced users

Required sections:

- config file location and lifecycle
- safe starter defaults
- locations
- matching modes
- scraper enablement and priorities
- sorting and naming
- NFO settings
- CSV templates
- translation
- proxy configuration
- Javlibrary Cloudflare credentials
- config sync workflow

Each config section should explain:

- what it controls
- recommended default
- when to change it
- common mistakes
- example YAML snippet

### `docs/commands.md`

Purpose:

- command reference that is easy to skim and use directly

Required sections:

- global command pattern
- `find`
- `sort`
- `update`
- `config`
- `scrapers`

Each command section should include:

- purpose
- when to use it
- syntax
- practical examples
- expected result
- common mistakes / gotchas

### `docs/troubleshooting.md`

Purpose:

- symptom-based support guide

Required sections:

- no files were processed
- some files were skipped
- wrong ID matched
- Javlibrary is blocked by Cloudflare
- proxy test failed
- translation provider unavailable
- update did not refresh what I expected
- sort did not remove the source directory
- why a file name was skipped

Each troubleshooting entry should include:

- what it usually means
- how to confirm it
- how to fix it
- when to move to another workaround

### `docs/contributor-guide.md`

Purpose:

- contributor/dev entrypoint

Required sections:

- local setup
- required `venv` usage
- test and lint commands
- docs map for contributors
- where major logic belongs
- regression testing expectations
- how to update docs when behavior changes
- pointers to `AGENTS.md`, `CONTEXT.md`, `report.md`, and `plan.md`

### `CONTEXT.md`

Purpose:

- stable architectural context and repo orientation

Keep it focused on:

- architecture map
- runtime contracts
- project maturity snapshot
- document roles

### `report.md`

Purpose:

- latest audit / verification snapshot

Keep it focused on:

- current verification evidence
- strengths
- risks
- deferred scope
- practical product state

### `plan.md`

Purpose:

- short roadmap and active priorities

Keep it focused on:

- current priorities
- guardrails
- definition of progress

## Reader Journey

### Default Path

1. Reader lands on `README.md`
2. Reader identifies their role
3. Reader follows the role-specific next link

### End User Path

`README.md` -> `docs/getting-started.md` -> `docs/configuration.md` -> `docs/troubleshooting.md`

### Power User Path

`README.md` -> `docs/configuration.md` -> `docs/commands.md` -> `docs/troubleshooting.md`

### Contributor Path

`README.md` -> `docs/contributor-guide.md` -> `CONTEXT.md` -> `AGENTS.md` -> `report.md` / `plan.md`

## Writing Standards

### Tone

- professional
- direct
- calm
- practical

Avoid:

- hype-heavy marketing language
- internal shorthand without explanation
- vague advice that does not tell the reader what to do next

### Structure

Every reader-facing doc should establish:

- who the guide is for
- when to read it
- what the reader will be able to do after reading it

### Style Rules

- prefer task-oriented writing over raw option dumps
- use runnable command examples
- use realistic paths and examples
- explain repo-specific terms the first time they appear
- prefer short sections with strong headings over very long continuous prose
- use bullets only when they improve scanning
- avoid duplicating the same explanation in multiple files; link to the canonical page instead

### Command Documentation Standard

Every documented command should include:

- purpose
- when to use it
- syntax
- examples
- expected output or result
- common mistakes

### Configuration Documentation Standard

Every config section should include:

- what it controls
- safe default recommendation
- when to change it
- example snippet
- warning about common bad configurations when relevant

### Troubleshooting Standard

Troubleshooting sections should be organized by symptom, not by subsystem.

## Migration Plan

### Step 1

Rewrite `README.md` into a true landing page with:

- balanced overview
- quick start
- first safe workflow
- role-based docs map

### Step 2

Create the new role-based docs:

- `docs/getting-started.md`
- `docs/configuration.md`
- `docs/commands.md`
- `docs/troubleshooting.md`
- `docs/contributor-guide.md`

### Step 3

Reduce overlap in old docs:

- convert `docs/USAGE.md` into a clean docs index
- retire or redirect `docs/PLAYBOOK.md`

### Step 4

Update internal links across the repo so navigation remains coherent.

### Step 5

Run verification and do a final docs navigation review.

## Risks

### Risk: Documentation Drift

If the new docs are more polished but not tied to runtime behavior, they can drift quickly.

Mitigation:

- keep runtime and verification as source of truth
- keep command examples close to actual CLI behavior
- keep contributor docs explicit about verification

### Risk: Link Breakage

Reorganizing docs can leave stale references.

Mitigation:

- keep `docs/USAGE.md` path alive as an index
- use redirect-style content for retired pages where practical
- scan the repo for outdated internal doc links

### Risk: Overlap Returns

New docs can drift back into duplication if responsibilities are not respected.

Mitigation:

- keep each file scoped to one role or one purpose
- link across docs instead of restating everything

## Verification Plan

Verification for this documentation restructure should include:

- review of internal links
- `./venv/bin/python -m pytest tests -q`
- `./venv/bin/python -m ruff check javs tests`
- final pass to ensure the documentation map is coherent and role-based navigation works

## Definition Of Success

This redesign succeeds when:

- a new user can install JavS and complete a safe first run without guessing the next step
- a power user can find command/config detail quickly without reading a tutorial from the top
- a contributor can find setup, verification, and architecture entrypoints from one doc
- the repo no longer relies on overlapping long-form guides to explain one workflow
- the docs feel complete, professional, and easy to trust
