# Upgrading to Event Sourcing

This guide explains how to upgrade from CSV-only data management to the new event sourcing architecture.

## For Existing Users

If you have been using Finance with CSV files and want to upgrade to the event sourcing architecture (which enables duplicate detection, audit trails, and future features), you have two options:

### Option 1: One-Command Migration (Recommended)

The simplest way to migrate is using the new `migrate-to-events` command:

```bash
# 1. Dry run to see what will happen
finance migrate-to-events

# 2. Actually perform the migration
finance migrate-to-events --write
```

This command will:
1. Check that you have CSV data to migrate
2. Create an event store from your existing transactions
3. Build transaction and budget projections
4. Validate everything matches your original data
5. Show a success summary

After migration, all commands work as before, plus you get new capabilities like duplicate detection.

### Option 2: Manual Migration (Advanced)

If you prefer to understand each step or need more control:

```bash
# 1. Backfill events from existing CSVs
finance backfill-events --write

# 2. (Optional) Verify projections if needed
finance rebuild-projections --from-scratch
```

The `backfill-events` command automatically rebuilds projections and validates them.

## What Gets Created

After migration, you'll have these new files in `data/`:

- `events.db` - Event store (immutable audit log of all changes)
- `projections.db` - Transaction projections (current state)
- `budget_projections.db` - Budget projections (current state)

Your original CSV files remain unchanged and serve as backup.

## New Capabilities After Migration

Once migrated, you can use:

### Duplicate Detection
```bash
# Scan for duplicate transactions
finance duplicates

# Interactive mode with learning
finance duplicates --interactive
```

### Projection Rebuilding
```bash
# Rebuild projections from events (incremental)
finance rebuild-projections

# Full rebuild from scratch
finance rebuild-projections --from-scratch
```

### Continue Normal Workflows

All existing commands continue to work:
- `finance ingest --write` - Import new transactions
- `finance categorize` - Categorize transactions
- `finance budget` - View budget reports
- etc.

The difference is that now all changes are recorded as events, giving you an audit trail and enabling event sourcing features.

## Troubleshooting

### "Event store not found" Error

If you see this error, you need to migrate your data:

```bash
finance migrate-to-events --write
```

### "Projections not found" Error

This shouldn't happen with the new auto-rebuild feature, but if you see it:

```bash
finance rebuild-projections --from-scratch
```

### Migrating Again (Force)

If you need to re-migrate (e.g., after restoring old data):

```bash
# This will overwrite the existing event store
finance migrate-to-events --write --force
```

### Migration Failed or Incomplete

If migration fails partway through:

1. Delete the incomplete files:
   ```bash
   rm data/events.db data/projections.db data/budget_projections.db
   ```

2. Run migration again:
   ```bash
   finance migrate-to-events --write
   ```

## For New Users

If you're starting fresh, you don't need to worry about migration. Just:

1. Export CSV files from your bank
2. Place them in `ingest/` directory
3. Run `finance ingest --write`

This automatically creates the event store and projections for you.

## Technical Details

### Event Sourcing Architecture

The new architecture uses event sourcing where:

- **Events** are the source of truth (immutable log of what happened)
- **Projections** are derived views (current state, can be rebuilt)
- **CSV files** remain as backup and for manual inspection

Benefits:
- Complete audit trail of all changes
- Ability to rebuild state at any point in time
- Enables advanced features like duplicate detection with user feedback
- Safer data management (append-only, never lose history)

### What Happens During Migration

1. **Event Generation**: Creates `TransactionImported` and `TransactionCategorized` events from each CSV row
2. **Budget Events**: Creates `BudgetCreated` events from `categories.yml`
3. **Projection Building**: Processes events to create current state views
4. **Validation**: Compares projections against original CSVs to ensure accuracy

### Storage Space

The event store and projections add about 2-3x the size of your CSV files. This is acceptable because:
- Events provide audit trail and history
- Projections enable fast queries
- Storage is cheap
- You keep all the benefits of event sourcing

## Getting Help

If you encounter issues during migration:

1. Check this guide's troubleshooting section
2. Review the [Architecture Documentation](../../developer/architecture/system-design.md)
3. Run with `--help` for command-specific options:
   ```bash
   finance migrate-to-events --help
   ```
