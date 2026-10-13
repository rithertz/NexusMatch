# NexusMatch Database Design

**Status:** Relational schema and single-elimination engine implemented; schema behavior is covered by PostgreSQL-backed integration tests. Performance benchmarks are not claimed.

## 1. Purpose and scope

NexusMatch is an esports tournament application supporting both individual and team-based tournaments. Its relational design should support tournament registration, scheduling, match participation, and results without maintaining separate tournament and match schemas for individual and team competitions.

PostgreSQL is the source of truth for transactional tournament data and relational integrity. MongoDB is intended for high-volume or flexible telemetry/event documents. That MongoDB data separation is an architectural intention; the telemetry collections and their retention/indexing policies are not yet documented as implemented.

This document describes the schema currently represented by the SQL files under `database/sql/schema/`. Where a feature is planned rather than implemented, it is identified as future work.

## 2. Design goals

- **Support both competitor types:** individual players and teams can register for tournaments.
- **Enforce integrity in PostgreSQL:** use primary keys, foreign keys, unique constraints, check constraints, and triggers where appropriate.
- **Prevent cross-tournament participation:** a match participant's registration must belong to the same tournament as the match.
- **Enforce registration capacity:** pending and approved registrations consume tournament slots; rejected and withdrawn registrations do not.
- **Protect concurrent registration attempts:** serialize capacity checks for the same tournament using a row-level lock.
- **Keep schema changes reviewable:** add schema changes as ordered SQL migrations rather than silently editing migrations already applied to a database.

## 3. Relational entities

Names below use the actual SQL table and column names in the initial schema. They are not intended as a replacement for inspecting the migration itself.

| Table | Purpose | Important columns and constraints |
|---|---|---|
| `players` | Individual competitors | `player_id` primary key; `username` unique and required; `display_name` required; optional unique `email`; `created_at` |
| `teams` | Teams that can enter team tournaments | `team_id` primary key; unique required `team_name`; `created_at` |
| `team_members` | Many-to-many relationship between players and teams | Composite primary key (`team_id`, `player_id`); foreign keys to `teams` and `players`; `joined_at` |
| `tournaments` | Tournament configuration and lifecycle | `tournament_id` primary key; `name`; `game_name`; `tournament_type`; `format`; `status`; `max_entries`; optional `starts_at`; `created_at` |
| `registrations` | A player's or team's entry in a tournament | `registration_id` primary key; `tournament_id`; exactly one of `player_id` and `team_id`; `status`; `registered_at`; unique tournament/competitor combinations |
| `matches` | A fixture or bye within a tournament | `match_id` primary key; `tournament_id`; `round_number`; `match_number`; `status`; `is_bye`; optional scheduled/start/completion timestamps; unique (`tournament_id`, `round_number`, `match_number`) |
| `match_participants` | Connects registered competitors to a match and stores result fields | Composite primary key (`match_id`, `registration_id`); `tournament_id`; `slot_number` (1 or 2); optional nonnegative `score`; optional `placement`; `is_winner`; composite foreign keys enforcing tournament consistency |

### 3.1 Tournament attributes are separate concepts

`tournament_type` identifies who competes:

- `individual`
- `team`

`format` identifies how the competition is run:

- `single_elimination`
- `double_elimination`
- `round_robin`
- `swiss`

`status` describes the tournament lifecycle:

- `draft`
- `registration_open`
- `in_progress`
- `completed`
- `cancelled`

These columns must not be treated as interchangeable. For example, a team tournament can use a Swiss format.

### 3.2 Registration status

Registration statuses currently allowed by the schema are:

- `pending`
- `approved`
- `rejected`
- `withdrawn`

Pending and approved registrations count toward `max_entries`. Rejected and withdrawn registrations do not.

## 4. Integrity rules

### 4.1 A registration has exactly one competitor

A registration must reference either a player or a team, but not both and not neither. The `registrations` check constraint enforces this rule.

Unique constraints on (`tournament_id`, `player_id`) and (`tournament_id`, `team_id`) prevent the same player or team from being registered more than once in the same tournament. PostgreSQL permits multiple `NULL` values in ordinary unique constraints, which is appropriate for the unused competitor column.

### 4.2 Competitor type must match tournament type

The `validate_registration_type()` trigger function checks that:

- An `individual` tournament receives a player registration.
- A `team` tournament receives a team registration.

The registration trigger also locks the target tournament row and checks capacity. A separate trigger introduced in the capacity migration prevents changing a tournament's type when existing registrations would become incompatible.

### 4.3 Registration capacity and concurrent requests

The capacity migration uses `SELECT ... FOR UPDATE` on the relevant tournament row before counting active registrations. Registration transactions for the same tournament therefore serialize around that row lock. If the active count has reached `max_entries`, the trigger raises an exception instead of allowing the registration.

The database trigger serializes capacity checks against the tournament row. A later bracket migration also locks that same row while generating the bracket and prevents registration insertion, update, or direct deletion after match rows exist. Automated tests cover concurrent registration attempts and bracket operations; no broader load benchmark is claimed.

### 4.4 Match participants must belong to the match's tournament

The schema exposes composite unique keys on (`match_id`, `tournament_id`) in `matches` and (`registration_id`, `tournament_id`) in `registrations`. `match_participants` references those composite keys.

As a result, a participant cannot be attached to a match in a different tournament merely by supplying an existing registration ID. A manual negative test confirmed that PostgreSQL rejects this insert with a foreign-key violation.

### 4.5 Basic domain constraints

The schema also constrains values such as:

- `max_entries` must be at least 2.
- `round_number` and `match_number` must be positive.
- Tournament type, format, tournament status, match status, and registration status must use allowed values.

## 5. Indexes

The schema migrations create these explicit indexes:

- `idx_registrations_tournament_status` on registration tournament/status lookup.
- `idx_matches_tournament_round` on match tournament/round lookup.
- `idx_match_participants_registration` on match-participant registration lookup.
- `uq_match_participants_match_slot` (migration 005) ensures each match slot is populated at most once.
- `uq_match_participants_single_winner` (migration 005) permits at most one result winner per match.

Primary keys and unique constraints also create supporting indexes in PostgreSQL. Index effectiveness has not yet been established by recorded query plans or benchmarks. Do not claim a measured performance improvement until repeatable measurements, query details, and the relevant execution plans are saved under `database/experiments/query-plans/`.

PostgreSQL uses B-tree indexes by default for ordinary indexes; “B+ tree” is a useful conceptual description in database coursework, but performance claims should be supported by PostgreSQL's actual `EXPLAIN (ANALYZE, BUFFERS)` output.

## 6. Normalization and design considerations

The schema separates players, teams, team membership, tournaments, registrations, matches, and match participants into distinct relations. This reduces duplication and gives each entity a clear primary key.

That structural separation alone is not a formal proof of 3NF or BCNF. A complete normalization analysis still needs to record, for each relation:

1. Its relevant functional dependencies.
2. Candidate keys and prime attributes.
3. Whether every non-trivial functional dependency satisfies the target normal form.
4. Any decomposition argument, including losslessness and dependency preservation where decomposition is discussed.

The formal analysis belongs in `docs/database/NORMALIZATION.md`. Avoid claiming that every relation has been formally proven to be in 3NF or BCNF until that analysis is complete.

## 7. Single-elimination bracket lifecycle

Bracket generation is supported only for an open `single_elimination` tournament with at least two approved registrations. Registrations are ordered by `registered_at`, then `registration_id`; this is a deterministic registration-based seed order, not a skill ranking.

The engine rounds the entrant count up to the next power of two, creates all `P - 1` match rows for bracket size `P`, and inserts first-round pairings. For a non-power-of-two count, the earliest `P - N` registrations receive byes in the first `P / 2` match slots; remaining registrations are paired in registration order. A bye is persisted as a completed match with `is_bye=true`, one participant, no score, and no `is_winner` flag. Its participant is inserted into the correctly derived next-round slot; this is advancement without a fabricated result. Thus each actual two-competitor result still requires submission.

Match numbers map into the next round using `(match_number + 1) // 2`: odd matches feed slot 1 and even matches feed slot 2. Result submission locks the tournament and match, requires a non-tied score for exactly the two persisted registrations, marks the higher score as the winner, and atomically completes the match and populates the next slot. Completing the final also changes tournament status to `completed`. Completed results and bracket registrations cannot be overwritten through supported endpoints. The tournament API also locks the format and status after generation; the final match result is the operation that moves an in-progress tournament to completed.

## 8. Validation completed

PostgreSQL-backed integration tests cover the schema and API lifecycle, including 2-, 4-, 8-, and non-power-of-two brackets, byes, both competitor types, registration filtering, result advancement, final completion, duplicate and concurrent operations, cross-tournament isolation, and rollback when advancement cannot populate its slot. CI applies all numbered migrations to PostgreSQL before running the suite.

## 9. Known gaps and planned work

- **Concurrency benchmarks:** current concurrency tests assert safety, not high-volume throughput or latency.
- **Scoring model:** one numeric score per registration is supported; maps/sets, tie-breaks, and corrections require a future schema/API design.
- **Registration reassignment:** define and test rules for changing a registration's tournament, including concurrency implications.
- **Tournament lifecycle rules:** registration creation is gated by the API while the tournament is open and bracket mutations are frozen by PostgreSQL; additional policies for direct database operations can be considered separately.
- **Roster rules:** define team captain/ownership, minimum/maximum roster sizes, and when roster changes become prohibited. The current `teams` table does not yet have a captain/owner column.
- **Team roster snapshots:** a team registration identifies the team, not a frozen copy of its members; roster policy remains undefined.
- **Normalization documentation:** finish the functional-dependency, candidate-key, and normal-form analysis.
- **Index experiments:** capture representative `EXPLAIN (ANALYZE, BUFFERS)` output and compare measured plans/costs before making performance claims.
- **MongoDB telemetry design:** define document shapes, indexes, retention, and the relationship between telemetry references and relational match IDs.

## 10. Migration and environment policy

- Keep ordered SQL files under `database/sql/schema/`.
- Treat migrations already applied to a shared database as immutable; add a new migration for subsequent changes.
- Use a disposable test database for destructive schema and constraint tests.
- Never commit local `.env` files, credentials, or production data.
- Migration runner checks and CI verify ordered migration application; local integration testing must use a dedicated test database, never a manually maintained database.

## 11. Related documentation

- `docs/database/DATA_DICTIONARY.md` — table and column definitions.
- `docs/database/NORMALIZATION.md` — functional dependencies, candidate keys, and normal-form analysis.
- `docs/database/INDEXING_AND_QUERY_PLANS.md` — index rationale and query-plan experiments.
- `docs/database/TRANSACTIONS_AND_CONCURRENCY.md` — transaction boundaries, locking, and concurrency tests.
- `database/sql/schema/001_initial_schema.sql` — initial relational schema.
- `database/sql/schema/002_registration_capacity.sql` — registration capacity and tournament-type integrity migration.
- `database/sql/schema/005_single_elimination_brackets.sql` — match slots, bye state, and registration freezing after generation.
- `database/experiments/concurrency/README.md` — planned concurrency experiments.
- `database/experiments/query-plans/README.md` — planned query-plan experiments.
