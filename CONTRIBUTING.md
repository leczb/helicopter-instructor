# Contributing to Helicopter Virtual Flight Instructor

Thank you for your interest in contributing! This document explains how to
report bugs, request features, and submit code changes.

---

## Table of Contents

1. [Reporting Bugs](#1-reporting-bugs)
2. [Requesting Features](#2-requesting-features)
3. [Development Setup](#3-development-setup)
4. [Making Changes](#4-making-changes)
5. [Coding Standards](#5-coding-standards)
6. [Running the Tests](#6-running-the-tests)
7. [Pull Request Checklist](#7-pull-request-checklist)

---

## 1. Reporting Bugs

Please open a [GitHub Issue](https://github.com/leczb/helicopter-instructor/issues/new/choose) and choose the
**Bug Report** template. To help diagnose the problem quickly, include:

| Field | What to provide |
|---|---|
| **Plugin version** | Shown in `Plugins → Helicopter Instructor` (e.g. `v2.1.49`) |
| **X-Plane version** | e.g. `12.09r1` |
| **XPPython3 version** | e.g. `4.2.1` — shown in the XPPython3 plugin page |
| **Operating system** | e.g. `macOS 15.2`, `Windows 11` |
| **Aircraft** | e.g. `Robinson R22 Beta II` |
| **Steps to reproduce** | Numbered list of exact steps |
| **Expected behaviour** | What you expected to happen |
| **Actual behaviour** | What actually happened |
| **Log excerpt** | Paste relevant sections of both `Log.txt` and `XPPython3Log.txt` from your X-Plane root folder |

> **Tip:** Both log files are in your `<X-Plane 12>/` root folder.
> Search for `helicopter_instructor` to jump to the relevant lines.

---

## 2. Requesting Features

Open a [GitHub Issue](../../issues/new/choose) using the **Feature Request**
template. Describe:

- The problem you're trying to solve (not just the solution).
- How you think it should work from the student pilot's perspective.
- Any aircraft or hardware context that is relevant.

---

## 3. Development Setup

### Prerequisites

- **Python 3.12** (matches the XPPython3 v4 runtime bundled with X-Plane 12)
- **X-Plane 12** with [XPPython3](https://xppython3.readthedocs.io/) installed
  (needed for manual in-sim testing; not required to run the unit tests)

### Clone and prepare

```bash
git clone https://github.com/<your-fork>/helicopter-instructor.git
cd helicopter-instructor
```

No extra pip dependencies are required — the test suite mocks all X-Plane
APIs so it runs without X-Plane installed.

---

## 4. Making Changes

1. **Fork** the repository and create a branch from `main`:

   ```bash
   git checkout -b fix/brief-description-of-change
   ```

   Use the prefixes `feat/`, `fix/`, `refactor/`, `docs/`, `test/`, or
   `chore/` to match the project's commit convention.

2. **Make your changes** following the coding standards below.

3. **Run the full test suite** and confirm it passes (see
   [§6 Running the Tests](#6-running-the-tests)).

4. **Update `v2/docs/release_notes.md`** with a concise, user-friendly
   description of your change under a `## Unreleased` heading (or the
   current in-progress version if one is open):

   ```markdown
   ## Unreleased

   - **Fixed**: Brief description of what was fixed and why it matters.
   ```

5. **Commit** using a conventional commit message:

   ```
   fix: prevent audio overlap on rapid phase changes
   ```

6. **Open a Pull Request** against `main` and fill in the PR template.

---

## 5. Coding Standards

All code must follow the
[Google Python Style Guide](https://google.github.io/styleguide/pyguide.html).
The full coding rules are documented in
[`AGENTS.md`](AGENTS.md) and
[`v2/docs/developer_documentation.md`](v2/docs/developer_documentation.md).
Key rules at a glance:

### Architecture rules

- **`envelope_limits.py` is the single source of truth** for every safety
  threshold, scoring zone, and visual ring radius. Never hardcode a limit
  value in any other module.
- **No raw OpenGL 3D drawing.** All in-world 3D visualisation must use the
  `XPLMInstance` API (see `AGENTS.md §3.3`).
- **No disk I/O or blocking calls** inside `flight_loop_callback`.
- **No mutable module-level state** in sub-modules. Pass state as function
  arguments (dependency injection).

### Style

| Rule | Value |
|---|---|
| Line length | 80 characters |
| Indentation | 4 spaces, no tabs |
| Blank lines | 2 between top-level defs, 1 between methods |
| Docstrings | Google format with `Args:` / `Returns:` on every public function |
| Import order | stdlib → third-party (`xp`, `imgui`) → local (`helicopter_instructor.*`), each group alphabetically sorted |

---

## 6. Running the Tests

Run the full suite from the `v2/` directory:

```bash
cd v2
python3 -m unittest discover tests -v
```

All tests must pass before you submit a PR. To also check coverage:

```bash
python3 -m coverage run -m unittest discover tests
python3 -m coverage report -m
```

### Test conventions

| Change type | Required test |
|---|---|
| New scoring / safety limit | Contract assertion in `test_limits_contract.py` |
| New metrics behaviour | Unit test in `test_metrics.py` |
| New audio behaviour | Unit test in `test_audio.py` |

Tests must **not** import `xp`, `imgui`, or any other X-Plane module
directly — mock them at the top of the test file as shown in
`test_limits_contract.py`.

---

## 7. Pull Request Checklist

Before marking your PR ready for review, confirm:

- [ ] All existing tests pass (`python3 -m unittest discover tests -v`)
- [ ] New behaviour is covered by new or updated tests
- [ ] `v2/docs/release_notes.md` updated with a user-friendly entry
- [ ] No limit constants duplicated outside `envelope_limits.py`
- [ ] No raw OpenGL 3D calls added
- [ ] No disk I/O inside `flight_loop_callback`
- [ ] Commit message uses a conventional prefix (`feat:`, `fix:`, `refactor:`, `docs:`, `test:`, `chore:`)

---

*For questions, open a [Discussion](https://github.com/leczb/helicopter-instructor/discussions) rather than an Issue.*
