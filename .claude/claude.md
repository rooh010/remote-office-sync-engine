# Development Guidelines

## ⚠️ IMPORTANT DISCLAIMER

**THIS CODE IS FOR TESTING AND EDUCATIONAL PURPOSES ONLY.**

This project is experimental and should NOT be used in any production environment. The author takes NO RESPONSIBILITY for any data loss, corruption, or other issues arising from the use of this code. Use at your own risk.

---

## Project Context
- Keep `project_spec/` subfolder up to date as the project spec evolves

## Development Workflow Rules
- ALWAYS follow phased development workflow:
  - Break work into clear, incremental phases with defined scope and acceptance criteria
  - Create a new branch from `main` for each phase, e.g., `phase<number>/<short-name>`
  - **BEFORE EVERY COMMIT:**
    - Run `ruff check` and fix all errors
    - Run `black .` to format code
    - Run all tests with `pytest`
    - Verify the application runs and test critical functionality
    - Check Docker Compose builds and runs: `docker compose up --build -d`
  - Commit the completed phase with a concise summary of changes and rationale
  - **AFTER COMPLETING A PHASE (CRITICAL):**
    - Push all commits to remote: `git push origin <branch-name>`
    - **RESTART ALL DOCKER CONTAINERS** with full rebuild: `docker compose down -v && docker compose up --build -d`
    - Wait for all services to be healthy before testing
    - Test all features to verify the deployed changes work correctly
  - Open a Merge Request targeting `main`; address feedback until approved
  - Merge into `main`, then pull the latest `main` locally
  - Branch from updated `main` for the next phase
- ALWAYS create a new branch for changes

## MUST DO Rules
- NEVER commit PII, secrets, or tokens
- ALWAYS run a security check of the code before committing
- **ALWAYS test before committing** - Run full test suite and verify all tests pass
- **ALWAYS lint before committing** - Run `ruff check` AND `black --check`, fix ALL errors
- **ALWAYS verify the program runs** - Start the application and test critical endpoints
- ALWAYS test Docker containers start and work (`docker compose up --build -d`, verify endpoints, then `docker compose down`)
- Keep README.md in the root up to date with current project state and architecture
- ALWAYS ensure all applications run and work together
- ALWAYS be able to run locally through Docker
- ALWAYS use best practices and keep reliability and security in mind

## Tech Stack Rules
- Python >= 3.11
- Package manager: pip/venv

## Code Structure Rules
- Project structure:
  - `<app-name-here>/` - Main application code with logical module organization
  - `tests/` - Test suite with structure mirroring `src/`
  - `scripts/` - Utility scripts for development and operations
  - `docs/` - Documentation and architecture guides
  - `project_spec/` - Project specifications and requirements

## Configuration Rules
- Use environment variables for configuration
- Local dev: `.env` files are acceptable for convenience but MUST be gitignored. Use `env.template` files (committed) as templates
- NEVER commit `.env` files or secrets to git
- Docker Compose can load `.env` files for local development
- CI/QA/Prod: Use GitHub Actions Secrets and environment variables (not `.env` files)

## Error Handling Rules
- Use structured error handling with clear exception types
- Log errors with appropriate severity levels
- Provide meaningful error messages for debugging
- Use try/except blocks only where appropriate; don't suppress exceptions silently

## Quality Gates

### Pre-Commit Checklist (MANDATORY)
**NEVER commit without completing ALL of these steps:**

#### Python:
1. **Format:** `black .` - Must show "All done! ✨ 🍰 ✨"
2. **Lint:** `ruff check .` - Must show "All checks passed!"
3. **Type Check:** `mypy` (optional but recommended)
4. **Test:** `pytest` - All tests must pass
5. **Manual Tests:** Run critical manual tests (see Manual Testing section below)
6. **Run:** Start the application and verify it responds correctly
7. **Docker:** `docker compose up --build -d` - Verify all services start successfully (if applicable)

### Manual Testing Requirements (CRITICAL)
**Before every push, run the automated test suite using the PowerShell script below.**

#### Automated Testing (RECOMMENDED - Use This Method)
Instead of running tests manually, use the automated PowerShell script: `run_manual_tests.ps1`

```powershell
# Run with default test directories
.\run_manual_tests.ps1 -LeftPath "C:\pdrive_local" -RightPath "p:\"

# Run with custom directories
.\run_manual_tests.ps1 -LeftPath "C:\path\to\left" -RightPath "C:\path\to\right"
```

The script automatically:
- Sets `dry_run: false` in config.yaml before testing
- Restores `dry_run: true` after testing
- Runs all 13 test cases
- Reports pass/fail for each test
- Cleans up test files

**IMPORTANT - SYNCHRONIZATION REQUIREMENT:**
- Keep `run_manual_tests.ps1` synchronized with the test cases documented below
- If you add, remove, or modify any test cases, update BOTH:
  1. The test list in this document
  2. The PowerShell script in `run_manual_tests.ps1`
- Both must always have the same number of tests and same test names

#### Manual Testing (If Running Tests Manually)
**Before every push, manually verify these scenarios with real directories:**

Test directories: `C:\pdrive_local\` (left) and `p:\` (right)

Set `dry_run: false` in config.yaml for testing, restore to `true` after.

#### Core Operations (MUST ALL PASS):
1. **File Creation L→R:** Create file on left → sync → verify on right **and content matches**
2. **File Creation R→L:** Create file on right → sync → verify on left **and content matches**
3. **File Modification L→R:** Modify file on left → sync → verify on right **and content matches**
4. **File Modification R→L:** Modify file on right → sync → verify on left **and content matches**
5. **File Deletion (Left):** Delete from left → sync → verify deleted from right
6. **File Deletion (Right):** Delete from right → sync → verify deleted from left
7. **Directory Sync:** Create directory on one side → sync → verify on other side
8. **Modify-Modify Conflict:** Modify same file differently on both sides → verify conflict file created **ON BOTH SIDES (check content of both main file and conflict file)**
9. **New-New Conflict:** Create same filename on both sides with different content → verify conflict detected **AND conflict file exists on both sides with correct content**
10. **Case Change:** Rename file changing case → verify case conflict handled correctly
11. **Subdirectory Files:** Create file in nested subdirectory → sync → verify structure preserved **and content matches**
12. **Directory Deletion:** Create directory with files on both sides → delete directory from one side → sync → verify files deleted from other side
13. **Empty Directory Creation R→L:** Create empty directory on right → sync → verify appears on left

#### Content Verification (CRITICAL):
- **ALWAYS verify file content, not just existence!**
- Use file size comparison as quick check
- For text files, compare actual content: `diff C:\pdrive_local\file.txt p:\file.txt`
- For binary files, compare checksums: `Get-FileHash`
- Verify both the main file AND any conflict files have correct content

#### Conflict Resolution Behavior (CRITICAL):
**When conflicts occur (modify-modify or new-new), the expected behavior is:**
- **Main file (without .CONFLICT)** = The NEWEST version (by modification timestamp)
- **.CONFLICT file** = The OLDEST version (preserved for reference)
- **Both sides** must have BOTH files (main + conflict)

**To verify conflict resolution:**
1. Check that the main file contains the content from the file with the newer timestamp
2. Check that the .CONFLICT file contains the content from the file with the older timestamp
3. Verify BOTH files exist on BOTH sides (left and right)
4. Example: If left modified at 10:00 and right modified at 10:05:
   - Main file should have right's content (newer)
   - .CONFLICT file should have left's content (older)

#### Deletion Testing (CRITICAL - Previously Broken):
- **NEVER skip deletion tests** - this was a critical bug that wasn't caught by unit tests
- After sync, verify state database reflects actual filesystem (not pre-sync state)
- Ensure files are NOT copied back after deletion
- Verify soft-delete moves files to `.deleted/` folder when enabled

#### Quick Test Script Template:
```bash
# Enable real sync
# Change dry_run: false in config.yaml

# Test file creation & deletion
echo "test content" > C:\pdrive_local\manual_test.txt
python -m remote_office_sync.main  # Should copy to right
rm C:\pdrive_local\manual_test.txt
python -m remote_office_sync.main  # Should delete from right
# Verify p:\manual_test.txt is deleted (or in .deleted/)

# Restore dry run
# Change dry_run: true in config.yaml
```

#### Test Failure Protocol:
If ANY manual test fails:
1. **DO NOT COMMIT** - Fix the issue first
2. Add a unit test that reproduces the failure
3. Fix the bug
4. Verify unit test passes
5. Re-run ALL manual tests
6. Only then proceed with commit

### Python Quality Standards:
- Formatter: black (line length 100, enforced)
- Lint: ruff (all errors must be fixed, no exceptions)
- Types: mypy (incremental OK)
- Tests: pytest; keep unit tests fast and deterministic
- Coverage: Add tests for new behavior and critical bug fixes
- Style: Follow PEP 8; black and ruff enforce this

## Git & CI Rules
- Conventional commits preferred (feat, fix, chore, docs, test, refactor)
- Small, focused commits and PRs with clear summaries
- NEVER add AI-generated footers or attribution to commit messages
- Keep .gitignore up to date to exclude build artifacts, dependencies, IDE files, and environment-specific files

## AI Collaboration Rules
- Read PRD and System Design before implementing
- Propose changes that align with existing patterns and directory layout
- NEVER introduce new major dependencies without justification
- Add or update docs when behavior or public API changes
- NEVER include secrets, tokens, or PII in code, logs, or tests

## Task Execution Rules
- When starting a task, confirm target module(s) and constraints
- If unsure, ask for clarification on package choices or test setup
- Summarize changes and list impacted files upon completion
- Mark tasks as done on the task list

## Priority Rules
- Truth sources: `project_spec/prd.md` and `project_spec/system_design.md` are authoritative
- Goals first: Favor correctness, security, and maintainability over cleverness
- Least change: Modify the smallest surface area to achieve outcomes. Avoid unnecessary refactors

## Initial Setup Guidelines
- Create Python app scaffold with clear module organization
- Enable comprehensive testing setup (pytest with fixtures and mocks)
- Set up health checks and logging
- Bootstrap CI workflows for lint/test
- Document project architecture and setup instructions in README
