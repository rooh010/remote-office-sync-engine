# Phased Approach To Build The Sync Service

## Context

Python script, later run as a Windows service on the file server.

Bidirectional sync:

Left: local file server share (e.g. C:\pdrive_local)

Right: P:\ (pCloud drive)

Scale: ~90k files, ~550 GB.

Real time or near real time: target within ~10 seconds.

Prioritise small files over large ones when processing backlog.

Soft delete enabled, but:

Do not soft delete files larger than 20 MB.

Large deletes rely on existing backup (Backblaze).

Conflict policy as provided, with preference for "Option 1" where specified.

All key behaviour configurable via config file (paths, email, thresholds, conflict options, etc).

## Phase 1 - Foundations And Configuration

### Goals

Set up project structure.

Implement configuration system.

Implement basic scanning and metadata model without modifying files.

### Tasks

#### Create Python project structure:

src/ or similar layout.

sync_engine.py, config.py, scanner.py, models.py, logging_util.py.

#### Implement config loading:

Single config file (YAML or TOML recommended).

Configurable items:

Left root path (C:\pdrive_local).

Right root path (P:\).

Email settings (SMTP, from, to).

Scan interval and event debounce interval.

Soft delete enabled flag.

Soft delete max size threshold (default 20 MB).

Conflict resolution options for each rule block.

#### Define file metadata model:

Relative path (from root).

Last modified time.

File size.

Hash placeholder (may be delayed for performance).

#### Implement baseline scanner:

Walk left and right trees.

Build in memory index or store snapshot in a local SQLite DB.

#### Implement logging:

Structured logs to file and console.

Include correlation IDs for runs.

### Acceptance Criteria

- Application reads config file and validates required fields.
- Running a "dry run" scan prints a summary of:
  - File counts on left and right.
  - Files only on left, only on right, present on both.
- No files are created, deleted or modified.

## Phase 2 - One Shot Sync Engine (Core Logic, No Real Time)

### Goals

Implement the rules engine for file decisions using current snapshots.

Support all listed sync rules in a batch "one shot" run.

Still no file system watcher, just manual or scheduled execution.

### Tasks

#### Extend metadata model to include:

Per side last modified time.

Per side existence flags (present/absent).

Per side hash optional (configurable).

#### Implement decision engine that, for each relative path:

Evaluates "matrix" of state:

Exists left/right.

Modified left/right compared to previous known state.

Deleted left/right.

Property or case name change left/right.

Applies the user specified rules:

Same file changed on both left and right:

Implement Option 1, 2, 3 modes.

Default to Option 1.

New file created on both left and right and different:

Implement Option 1 and Option 2 modes.

Changed on left only:

Left overwrites right.

Changed on right only:

Right overwrites left.

Deleted on left but changed/created on right:

Copy file to left.

Deleted on right but changed/created on left:

Copy file to right.

Deleted on left, unchanged on right:

Delete from right.

Deleted on right, unchanged on left:

Delete from left.

New file only on left:

Copy to right.

New file only on right:

Copy to left.

Properties or case of file name changed on left (unchanged on right):

Rename and copy properties on right.

Properties or case changed on right (unchanged on left):

Rename and copy properties on left.

Properties or case changed on both:

Implement Option 1, 2, 3 modes.

#### Implement "soft delete" abstraction:

When soft delete is enabled and file size <= 20 MB:

Move file to a special archive folder (e.g. left\.sync_trash\... or right\.sync_trash\...).

Include timestamp in the archived path.

When file size > 20 MB:

Delete directly without soft delete.

#### Implement execution order:

Safe ordering to avoid conflicts:

Handle renames before deletes.

Handle copies after necessary parent directories exist.

### Acceptance Criteria

- Dry run mode prints intended actions without applying them.
- Live mode actually performs:
  - Copies.
  - Renames.
  - Deletes and soft deletes according to size.
- Conflicts trigger correct behaviour and can be unit tested with small test trees.
- Bidirectional sync is correct for the rule set in a controlled test scenario.

## Phase 3 - Conflict Handling, Clash Files, And Email Notifications

### Goals

Implement full conflict file handling with "clash" files.

Wire up email notifications for conflict events and summary email.

### Tasks

#### Implement clash creation for "Option 1":

For conflicts on both sides:

Create copies of both older and newer files on both left and right as required.

Append "clash" to the older file name.

Ensure naming scheme avoids collisions, for example:

filename_clash_YYYYMMDDHHMM.ext.

#### Implement configurable notification granularity:

Per conflict event email.

Or batched summary every run.

#### Implement email delivery:

Use SMTP settings from config (Gmail or other).

Support app password or OAuth if needed.

Configurable:

To addresses (admin list).

Subject prefix.

Email content:

For each conflict event:

File relative path.

Which rule was triggered.

Which side had newer file, sizes and timestamps.

What actions were taken.

Summary:

Counts of:

Files copied.

Renames.

Deletes and soft deletes.

Conflicts (by rule).

### Acceptance Criteria

- When a conflict scenario is created in a test folder:
  - Correct "clash" file appears on both sides with the expected naming convention.
  - Admin receives an email with the details.
- Email settings are fully driven by config file, no hard coded credentials.
- Errors in email sending are logged but do not break sync logic.

## Phase 4 - Real Time Sync With File System Watchers

### Goals

Move from one shot batch runs to near real time behaviour.

Target latency of around 10 seconds from change to sync.

### Tasks

#### Implement file system watching on the server:

Use watchdog or similar library for Windows file system events.

Monitor both:

Left path (local share).

Right path (pCloud drive P:\), if watcher events are reliable.

#### Build event queue:

Each file system event gets enqueued with:

Path.

Event type (created, modified, deleted, moved).

Side (left or right).

Timestamp.

#### Implement debounce and batching:

Worker loop wakes up at a short interval (e.g. every 3 to 10 seconds).

Coalesce multiple events for the same path.

Run the decision engine only on affected paths plus any linked paths for renames.

#### Prioritise small files:

When processing a backlog:

Sort queued events by estimated or actual file size, ascending.

Sync small files first.

Consider a size threshold above which files are processed with lower priority.

#### Fallback periodic full scan:

Configurable schedule (for example, every few hours).

Reconciles missed events and ensures eventual consistency.

### Acceptance Criteria

- In a test scenario, editing a small document on either side:
  - Changes propagate to the other side within roughly 10 seconds, under normal conditions.
- When many files are changed at once:
  - Small files are synced earlier than very large video files.
- Real time engine does not thrash the disk or saturate the poor internet link:
  - Throttling strategy can be configured (max concurrent copies, bandwidth hints).

## Phase 5 - Robust State Tracking And Recovery

### Goals

Ensure resilience across restarts and crashes.

Avoid misinterpreting old events as new conflicts.

### Tasks

#### Introduce persistent state store (SQLite or similar):

Store last known metadata per file:

Path.

Last modified time per side.

Size.

Hash if used.

Last operation performed.

#### On start up:

Load metadata.

Run a reconciliation pass to align state with reality.

#### Handle partial operations:

If the app crashes midway through a file copy:

Detect incomplete temp files and clean them up or retry.

#### Implement idempotent operations:

Sync run for a given change should be safe to reapply.

#### Ensure deletions are tracked:

Keep tombstones in state for deleted files for a configurable period.

### Acceptance Criteria

- After stopping and restarting the service:
  - The system does not re copy or re delete everything.
  - It continues where it left off.
- Corrupted partial files do not cause repeated crashes.

## Phase 6 - Windows Service Packaging And Operations

### Goals

Run as a proper Windows service on the file server.

Operate when no user is logged in.

### Tasks

#### Wrap the Python app as a Windows service:

Use pywin32 or nssm or similar mechanism.

Service start, stop, restart behaviour.

#### Service configuration:

Service account with correct permissions to:

Access C:\pdrive_local.

Access P:\ mapped drive or UNC path.

Access log directory.

#### Installer and upgrade story:

Simple install script:

Copies binaries and configs.

Registers the service.

Handling of config updates without full reinstall.

#### Logging and diagnostics:

Log rotation.

Separate log levels for debugging vs production.

Optional Windows Event Log integration.

### Acceptance Criteria

- Service starts at boot and runs without a user session.
- Manual start/stop from Services UI works.
- Logs show normal operation and errors clearly.

## Phase 7 - Monitoring, Metrics, And Admin Tools

### Goals

Provide visibility and simple admin controls.

Make it easy to diagnose sync problems.

### Tasks

#### Expose simple status information:

Last run time or last event processed.

Current backlog size.

Counts of operations in last N hours.

#### Optional lightweight admin CLI:

Commands like:

status.

dry-run.

resync PATH.

list-conflicts.

#### Optional health check endpoint (if you want to run external monitoring):

Simple HTTP server that reports health and key stats.

### Acceptance Criteria

- Admin can quickly see:
  - Whether sync is up to date.
  - Whether there are outstanding conflicts.
- There is a straightforward way to manually reprocess a folder or file.

## Phase 8 - Performance, Load Testing, And Tuning

### Goals

Validate behaviour at the real scale (90k files, 550 GB).

Tune settings for the poor internet link.

### Tasks

#### Create performance test plan:

Baseline full scan duration on real data.

Measure large batch changes (for example, 1000 file edits).

#### Tune:

Threading or async behaviour for file copy.

Maximum concurrent operations.

Debounce intervals.

#### Measure:

Time to first sync.

Time to steady state after big change bursts.

Impact on network utilisation.

### Acceptance Criteria

- Full reconciliation completes within an acceptable window.
- Normal office usage does not saturate the internet link.
- Real time target (~10 seconds for small files) still holds under typical usage.

## Phase 9 - Future Enhancements (Backlog)

These are not in the initial delivery but should be considered in the PRD backlog.

### Optional version history:

Keep multiple versions per file in a version store instead of simple soft delete.

### Web or desktop UI for:

Viewing conflicts.

Approving or overriding decisions.

### Smarter conflict resolution:

Per folder or per file type policies.

### Bandwidth aware scheduling:

Aggressive sync outside office hours.

Gentle mode during working hours.

### Integration with backup system:

Use Backblaze APIs for additional safety or faster restore.