# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project rules live in AGENTS.md

This repository already documents its conventions in `AGENTS.md` files — do not duplicate that content here. Before making changes, read:

- [`AGENTS.md`](AGENTS.md) at the repo root for the overall architecture, API conventions, code style rules, and commands.
- The `AGENTS.md` inside the specific package you're touching (e.g. `src/main/java/com/nmdw/ansimon/weather/AGENTS.md`, `.../guidance/AGENTS.md`, `.../global/AGENTS.md`, etc.) for domain-specific rules. Each of the ten domain packages (`global`, `elderly`, `weather`, `risk`, `shelter`, `guidance`, `contact`, `support`, `dispatch`, `dashboard`) has its own.
- `src/main/resources/db/migration/mysql/AGENTS.md` when adding or editing Flyway migrations.

Always check both the root `AGENTS.md` and the relevant package-level `AGENTS.md` before editing — the root file itself instructs this.

## Commands

- `./gradlew bootRun` (`.\gradlew.bat bootRun` on Windows) — run the dev server (default `http://localhost:8080`, health at `/actuator/health`)
- `./gradlew test` — run all tests (JUnit Platform)
- `./gradlew test --tests "com.nmdw.ansimon.global.error.ErrorCodeTest"` — run a single test class
- `./gradlew build` — full build

Local runs require `MYSQL_URL`, `MYSQL_USERNAME`, `MYSQL_PASSWORD`, and `SPRING_PROFILES_ACTIVE=local` set as environment variables (see `.env.example` for the full list of optional external-API keys). Flyway applies migrations from `src/main/resources/db/migration/mysql` on startup; JPA uses `ddl-auto=validate`, so schema changes must go through a migration, not entity annotations.

## Architecture

Spring Boot 4.1 / Java 21 API server organized as one package per business capability under `src/main/java/com/nmdw/ansimon/`, each following controller → application service → domain → adapter layering (see root `AGENTS.md` for the exact rule set). The packages form a pipeline for heatwave-vulnerable elderly care:

`elderly` (subject/consent data) → `weather` (KMA forecast ingestion) → `risk` (ML risk scoring) → `guidance` (Spring AI/RAG action-plan generation) → `contact` (automated preventive calls) → `support` (follow-up task creation) → `dispatch` (staffing/workload calc) → `dashboard` (summary views), with `shelter` (cooling shelter search/routing via TMAP) and `global` (shared config, WebClient, error handling, response envelope) supporting the rest.

Two datastores: MySQL for all service data (Flyway-migrated), and PostgreSQL+pgvector for RAG embeddings used by `guidance` (only active when `SPRING_AI_VECTORSTORE_TYPE=pgvector`).

Deployment is to Railway via GitHub Actions (`.github/workflows/ci-cd.yml`) on push to `main`; see `README.md` for the required repo secrets/variables and multi-stage `Dockerfile`.
