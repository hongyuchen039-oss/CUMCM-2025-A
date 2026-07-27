---
name: project-mainline-governance
description: Keep AI-assisted engineering and mathematical-modeling projects on the main delivery path. Prevent premature phase starts, role proliferation, design-review loops, fake progress, unsupported PASS claims, and cross-worktree contamination. Use at every new project start, every phase transition, and whenever multiple agents, worktrees, branches, audits, benchmarks, or PR gates are involved.
---

# Project Mainline Governance

## 1. Purpose

This skill converts lessons from the CUMCM-2025-A workflow into reusable project rules.

The central goal is not to maximize the number of agents, reports, gates, or branches. The goal is to move the project from one verified deliverable to the next with the least coordination overhead that still protects correctness.

Use this skill:

- when starting a new repository or competition project;
- before creating a new task branch or worktree;
- before activating a specialist agent;
- before moving from design to implementation;
- before claiming tests, benchmark, CI, PR, or result completion;
- when the process feels busy but the repository is not advancing.

## 2. Prime Directive

> One active project phase, one current task, one primary writer, one review target.

A future roadmap stage is not an active task.

A technically possible parallel activity is not automatically a justified parallel workstream.

Do not activate the next phase merely because its worktree or design can be prepared early. Activate it only when the current phase's exit gate is satisfied or when the user explicitly authorizes a narrowly bounded exception.

## 3. Mistakes This Skill Must Prevent

### 3.1 Starting the next phase before the current phase closes

Failure pattern:

- Foundation is still Draft or blocked;
- CI or semantic debt is still open;
- a Search, optimization, writing, or downstream agent is activated anyway;
- the next phase develops its own design, audit, worktree, and reports;
- the project now has two competing centers of gravity.

Rule:

- A downstream phase may be listed in the roadmap.
- It must not become an active construction stream until its entry gate is met.
- Read-only pre-research is allowed only when it has a fixed time box and cannot create a new governance chain.

### 3.2 Confusing a phase with a role

Failure pattern:

A task such as “Search design” becomes:

- Search CC;
- Search MAIN;
- Search Audit;
- Hermes Search governance;
- separate handoff reports for each.

The work has not become more correct; the communication surface has multiplied.

Rule:

Create a new role only when all are true:

1. it owns a distinct artifact;
2. it has the tools needed to produce or verify that artifact;
3. its activation reduces risk more than it adds coordination cost;
4. its stop condition is explicit.

Do not create a role merely because a topic exists.

### 3.3 Fake parallelism

Failure pattern:

- one agent lacks Write/Edit/Bash;
- other agents repeatedly review plans for code that does not exist;
- many sessions are active, but no artifact is produced.

Rule:

Before assigning construction work, verify tool capability in the actual session:

- terminal execution;
- file create/edit/delete;
- repository read/write access;
- test execution;
- commit/push capability when authorized.

If the session is read-only, classify it as review/research only. Never treat a read-only report as an implementation delivery.

### 3.4 Design-report loops

Failure pattern:

`V1 -> V2 -> V3 -> V4 -> V5 -> V5.1 -> V5.2`

Each round fixes smaller wording, table, naming, or serialization details while no implementation exists.

Rule:

For one phase, the default maximum is:

1. one design pass;
2. one targeted P0/P1 design repair;
3. implementation plus tests;
4. code review.

After the design is executable, remaining details should be frozen as binding implementation amendments and proved by code/tests.

Do not open a new design gate for:

- Markdown table shape;
- section order;
- label wording;
- a field that can be expressed as a test fixture;
- a deterministic rule already unambiguous enough to implement.

### 3.5 Treating format defects as phase blockers

Rule:

Format is blocking only when it creates two competing sources of truth or makes the contract unimplementable.

If the machine-readable source can be singular and tested, prefer:

- one config object;
- one schema;
- one fixture;
- one validation test.

Do not require a separate approval round merely to rearrange identical information into a prettier table.

### 3.6 Claiming work without evidence

Never accept these statements without direct evidence:

- “implemented” without changed files;
- “committed” without a real SHA;
- “pushed” without a remote branch/SHA;
- “PASS” without actual command output;
- “benchmark complete” without raw timing data;
- “CI passed” when the run is cancelled, timed out, skipped, or tied to an older SHA;
- “GitHub verified” when the evidence came only from a local agent report.

Required evidence hierarchy:

1. artifact or diff;
2. command and exit code;
3. test count and failures/skips;
4. commit SHA;
5. remote SHA;
6. CI run tied to that SHA;
7. PR metadata.

Plans and self-reports are not substitutes for these.

### 3.7 Auditing before there is an artifact

Rule:

Audit is activated when there is something concrete to inspect:

- a design that is genuinely needed before implementation;
- a commit;
- a PR diff;
- test output;
- benchmark data;
- a result file;
- a paper draft.

Do not keep Audit continuously active around hypothetical implementation.

Audit should focus on P0/P1 blockers. P2 issues should normally be recorded and deferred unless they combine into a correctness risk.

### 3.8 Letting audit scope expand indefinitely

Audit must review against a frozen rubric and approved scope.

An auditor may introduce a new blocker only when it is:

- P0/P1;
- supported by concrete evidence;
- relevant to the current task;
- impossible to defer safely.

The auditor must not restart previously accepted design sections merely because a more elegant design is imaginable.

### 3.9 Ignoring repository-native governance

At project start, read the repository's own rules before inventing new governance.

Priority:

1. user instruction;
2. repository root instructions such as `CLAUDE.md`;
3. approved project skill;
4. current task file;
5. model/spec documents;
6. PR description and CI state;
7. new process proposals.

If the repository says “one current task,” do not activate a parallel downstream task without explicit user authorization.

### 3.10 Overengineering before benchmark or reality check

Failure pattern:

- elaborate cache/checkpoint/runtime schemas are perfected;
- performance assumptions remain unmeasured;
- the real evaluator or minimal vertical slice has not run.

Rule:

Freeze only what must precede implementation.

Then build the smallest real vertical slice:

`input -> real evaluator -> result -> checkpoint -> resume -> test`

Benchmark before freezing large budgets or parallel topology.

Do not let infrastructure become the project.

### 3.11 Mixing local state and GitHub state

Always label evidence precisely:

- `LOCAL OBSERVED`;
- `REMOTE OBSERVED`;
- `GITHUB VERIFIED`;
- `AGENT SELF-REPORTED`.

A clean local worktree does not prove the remote branch is current.

A local commit does not prove it was pushed.

A PR description does not prove tests passed.

A CI run from an old SHA does not validate the new SHA.

### 3.12 Creating more governance files than project files

Do not create:

- report-of-report documents;
- repeated signoff files;
- duplicate gate documents;
- audit ZIPs for ordinary iterations;
- multiple status files carrying the same state.

Prefer:

- one current-task file;
- one PR;
- one machine-readable config;
- one test suite;
- concise PR comments for review outcomes.

## 4. Mandatory New-Project Bootstrap

Run this protocol at the start of every new project.

### Step 1: Define the final deliverable

Write one sentence:

> The project is finished when __________ is delivered and independently verifiable.

Examples:

- a reproducible result workbook;
- a tested application;
- a competition paper plus code and generated result files;
- a deployed service with acceptance tests.

### Step 2: Define the phase chain

Use 3-7 coarse phases only.

Example:

`Facts -> Model foundation -> Optimization -> Multi-agent extension -> Results -> Paper`

Do not create agents or branches for all phases at once.

### Step 3: Select exactly one current task

The current task must include:

- purpose;
- allowed files;
- forbidden files;
- completion evidence;
- stop condition;
- next phase entry gate.

### Step 4: Verify execution capability

Before sending a construction prompt, require a live tool check:

- repository path;
- branch;
- HEAD;
- worktree status;
- terminal execution;
- write/edit/delete test in an authorized temporary location;
- language/runtime version.

If any capability is missing, reassign the session before designing the implementation around nonexistent tools.

### Step 5: Assign minimal roles

Default roles:

- **MAIN**: roadmap, decisions, scope, final acceptance;
- **BUILD CC**: the only writer for the active task;
- **AUDIT**: activated only after an artifact exists;
- **GIT/GOVERNANCE**: optional, read-only branch/PR/CI verification.

Do not create a specialist role until its phase becomes active.

### Step 6: Establish evidence rules

Define in advance what counts as:

- implemented;
- tested;
- benchmarked;
- pushed;
- CI green;
- accepted;
- final.

### Step 7: Copy this skill

For a new repository, copy this file to:

`.claude/skills/project-mainline-governance/SKILL.md`

Then reference it from the repository's root agent instructions.

## 5. Phase Entry and Exit Gates

### Entry gate template

A phase starts only when:

- previous phase artifact exists;
- previous blocking PR is merged or explicitly waived;
- required CI is green;
- open P0/P1 debt is zero or explicitly accepted;
- the construction session has required tools;
- the user or MAIN explicitly authorizes the phase.

### Exit gate template

A phase ends only when:

- authorized files are complete;
- required tests ran and passed;
- no hidden skips or expected failures exist unless approved;
- commit SHA exists;
- push is verified;
- CI is tied to the same SHA;
- PR state is known;
- generated artifacts are validated;
- current task documentation is synchronized;
- agent stops and does not enter the next phase.

## 6. Review Budget

Default review budget for one active task:

- design review: one pass;
- targeted design repair: at most one pass;
- implementation review: one pass;
- P0/P1 code repair: at most one planned pass;
- final acceptance: one pass.

Exceed this budget only when new concrete evidence reveals a genuine blocker.

When the budget is exceeded, MAIN must issue one of these decisions:

- `ACCEPT WITH BINDING IMPLEMENTATION AMENDMENTS`;
- `REDUCE SCOPE TO MINIMAL VERTICAL SLICE`;
- `STOP AND CLOSE CURRENT PHASE`;
- `RETURN TO PREVIOUS PHASE DUE TO P0/P1 FAILURE`.

Do not default to another document version.

## 7. Mainline Health Check

Ask these questions whenever progress feels slow:

1. What is the single current task?
2. What concrete artifact changed since the last review?
3. Is the active writer able to write and run tools?
4. Are we reviewing code/results, or only reviewing another plan?
5. Did a downstream phase start before its gate?
6. Did a P2 or formatting issue become a blocker?
7. Are multiple roles duplicating the same judgment?
8. Is GitHub state verified against the current SHA?
9. What can be removed without reducing correctness?
10. What is the next irreversible evidence-producing action?

If answers 2 or 10 are empty, stop governance work and restore the implementation mainline.

## 8. Red Flags Requiring Immediate MAIN Intervention

- more than two consecutive design-report revisions;
- a construction agent reports no Bash/Write/Edit access;
- PASS appears without command output;
- placeholder SHA or placeholder benchmark data;
- an auditor reviews a nonexistent commit;
- a format-only issue opens a new gate;
- two active writers share one worktree;
- a next-phase branch is active while the current blocking PR is unmerged;
- a PR description is treated as test evidence;
- CI is cancelled but described as passed;
- the number of status reports grows faster than code/tests/results;
- a future result file is generated in the wrong phase.

Required response:

1. freeze all secondary roles;
2. name the single current task;
3. identify the nearest evidence-producing action;
4. issue one construction prompt;
5. review only the resulting artifact.

## 9. Role Contracts

### MAIN

MAIN must:

- protect the full roadmap;
- choose the current task;
- stop premature phase activation;
- resolve conflicts between rigor and progress;
- accept binding amendments when further prose review has diminishing returns;
- verify remote/GitHub state directly before final claims.

MAIN must not:

- create roles merely to distribute discussion;
- let audit become a second project manager;
- allow design loops to continue by inertia.

### BUILD CC

BUILD CC must:

- be the only writer for the active worktree;
- perform live preflight;
- edit only authorized files;
- run real commands;
- report exact evidence;
- stop after commit/push/PR update when instructed.

BUILD CC must not:

- submit plans as completed work;
- fabricate fixtures, SHA, timings, or PASS results;
- enter the next task automatically.

### AUDIT

AUDIT must:

- remain read-only;
- review a fixed artifact against a fixed rubric;
- separate P0/P1 from P2;
- provide minimal repair instructions;
- stop after the decision.

AUDIT must not:

- write repository files;
- create new project scope;
- repeatedly reopen accepted sections without new blocker evidence.

### GIT/GOVERNANCE

The governance role may verify:

- branch;
- SHA;
- worktree registration;
- changed-file whitelist;
- push;
- PR base/head/draft state;
- CI run and job conclusions.

It must not become a second writer or mathematical reviewer.

## 10. Evidence-First Status Vocabulary

Use only statuses supported by evidence:

- `PLANNED`: scope exists; no implementation.
- `IMPLEMENTED LOCALLY`: files changed; tests may be incomplete.
- `TESTED LOCALLY`: commands and outputs exist.
- `COMMITTED`: real local commit SHA exists.
- `PUSHED`: remote branch points to commit.
- `CI VERIFIED`: CI success is tied to that SHA.
- `REVIEWED`: audit examined the artifact.
- `ACCEPTED`: MAIN accepted the phase deliverable.
- `MERGED`: GitHub shows merged state.
- `FINAL`: only when the project-specific final-delivery criteria are met.

Never collapse these into a vague “done.”

## 11. Minimal Prompt Pattern for an Active Construction Task

Every construction prompt should contain only:

1. role and current task;
2. repository/worktree/branch/starting SHA;
3. allowed and forbidden files;
4. exact implementation objective;
5. exact tests and acceptance evidence;
6. commit/push/PR instructions;
7. hard stop conditions.

Do not include the entire project history unless it changes implementation decisions.

## 12. Lessons From the Search Detour

The specific failure sequence generalized here was:

1. a downstream Search phase existed in the roadmap;
2. it was mistaken for permission to activate a Search construction role early;
3. the role was activated before Foundation merge and CI closure;
4. separate Search MAIN, Search Audit, and governance threads formed;
5. the construction session lacked write/terminal capability;
6. design reviews continued despite no code artifact;
7. contract versions multiplied;
8. formatting and implementation details became separate gates;
9. progress was measured by report versions rather than repository evidence;
10. the project eventually had to return to Foundation final close.

Permanent correction:

- roadmap presence does not equal activation permission;
- downstream agents start only after phase entry gates;
- capability is checked before assigning construction;
- after one targeted design repair, implementation and tests become the proof mechanism;
- MAIN closes branches of discussion that no longer advance the deliverable.

## 13. Final Operating Rule

At all times, prefer this:

`one task -> one writer -> one artifact -> one test run -> one review -> one decision`

over this:

`many roles -> many reports -> many gates -> no artifact`

When in doubt, return to the nearest action that produces verifiable code, data, result files, or a reviewable draft without violating the current phase boundary.
