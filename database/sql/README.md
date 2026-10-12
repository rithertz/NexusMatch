# README

> Status: Draft

## Purpose

To be completed as this part of NexusMatch is designed and implemented.

## Decisions and implementation notes

- [ ] Document the design and its rationale.
- [ ] Record relevant implementation paths and configuration.
- [ ] Link to the corresponding tests and verification evidence.

## Verification

- [ ] Add reproducible verification steps when this component is implemented.

## Related documents

- Update this section with links as the project evolves.


## PostgreSQL migrations

Schema migrations are stored in `database/sql/schema` and are applied
in numeric version order by `backend/scripts/migrate.py`.

Configure the `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`,
`POSTGRES_USER`, and `POSTGRES_PASSWORD` environment variables, or use
the existing root `.env` configuration.

From the repository root, run:

```powershell
python backend/scripts/migrate.py
```

The runner creates `schema_migrations`, records applied versions and
SHA-256 checksums, skips already-applied migrations, and rejects changes
to recorded migration files.

Do not edit a migration that has already been shared or applied. Add a
new numbered migration for future schema changes.

For a database that was migrated manually before migration tracking
existed, first verify that every migration is already applied. Only then
may you run:

```powershell
python backend/scripts/migrate.py --baseline-existing
```

This command records versions without executing migration SQL. It is
not a schema validation or database repair command.

For automated tests, configure `NEXUSMATCH_TEST_DATABASE_URL` to point
to a dedicated test database. Never run destructive tests against a
database containing data you need to keep.
