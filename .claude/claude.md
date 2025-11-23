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
5. **Run:** Start the application and verify it responds correctly
6. **Docker:** `docker compose up --build -d` - Verify all services start successfully

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
