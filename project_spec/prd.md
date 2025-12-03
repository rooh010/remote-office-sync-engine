# Remote Office Bi-directional File Sync - Product Requirements Document

## ⚠️ TESTING AND EDUCATIONAL USE ONLY

**IMPORTANT DISCLAIMER:** This product specification describes software intended for testing and educational purposes only. This software should NOT be deployed in any production environment. The author accepts NO RESPONSIBILITY for any data loss, file corruption, or other damages that may result from using this software. Users assume all risks associated with its use.

---

## 1. Document Info

Product name: Remote Office File Sync Script (Python)

Version: v0.1 - Script implementation

Owner: IT / Infrastructure

Target platform: Windows Server (file server)

## 2. Background & Context

A remote office uses:

A local Windows file server with a share at C:\local_share (used by in-office staff over LAN).

A remote drive mapped as R:\ (cloud storage, used by remote/home workers).

Internet connectivity from the office to the internet is slow and unreliable, so office users should primarily use the local file server, while external workers use remote drive.

Currently:

There is a basic script that syncs R:\ and C:\local_share, but it is not robust.

Conflict handling is manual and error prone.

There is no clear strategy for real-time or near real-time sync.

File volume is significant:

~90,000 files

~550 GB total

Mix of documents, spreadsheets, and large media files (Adobe Premiere video files).

Goal: Build a robust Python-based sync script that can later be turned into a Windows service running on the file server, keeping the two locations in sync with well-defined conflict resolution and configurable behavior.

## 3. Objectives

### 3.1 Primary Goals

Bi-directional sync between:

Left: Local file server share (C:\local_share)

Right: remote drive (R:\)

Ensure data consistency across both sides with clear, predictable conflict handling.

Run in near real time with a target of ~10 second latency between a change and sync.

Operate reliably as a Windows service on the file server (even when no user is logged in), after initial script development.

Allow runtime behavior (paths, conflict options, email, thresholds) to be controlled by a config file.

### 3.2 Non-Goals (for v0.1)

Complex UI or GUI - configuration is via file(s) and logs.

Full-blown version-control or document management system.

Cross-platform operation (Linux/macOS) - focus is Windows file server.

Dedupe or compression of files.

Content-aware merge (for documents or media) beyond the defined conflict rules.

## 4. High-level Solution Overview

A Python script runs on the Windows file server.

It treats the local share and remote drive as two roots:

Left root: C:\local_share

Right root: R:\

The script:

Maintains a state database (e.g. SQLite or similar) to track last known state (timestamps, hashes or size) of files on both sides.

Performs change detection either via file system watching or frequent scans with optimizations.

Applies a set of deterministic sync rules to decide:

Copy left → right

Copy right → left

Delete on one or both sides

Create conflict copies and send alerts

Runs continuously in a loop to approximate real-time sync (target: ~10 seconds from change to sync).

The script is designed so it can later be wrapped as a Windows service that starts at boot and runs with no interactive user session.

## 5. Stakeholders & Users

Office workers (local network): access files via C:\local_share share.

Remote/external workers: access files via remote drive (R:\).

IT / Admin:

Configure and maintain sync script and service.

Handle conflict alerts and resolve issues.

Monitor logs and capacity (including soft delete space).

## 6. Detailed Requirements

### 6.1 Functional Requirements

#### 6.1.1 Bi-directional Sync Semantics

The system is explicitly bi-directional.

There is no permanent master side. Either side can be the origin of changes.

Each sync cycle considers the latest known state of each file on both sides.

#### 6.1.2 File Types and Volume

Handle ~90k files and ~550 GB.

Support:

Documents, spreadsheets, PDFs, images.

Large media files, including Adobe Premiere video files.

Conflict rules apply equally to small and large files, but soft delete and prioritization behave differently based on size thresholds.

### 6.2 Sync Rules (Core Logic)

Below, Left = C:\local_share, Right = R:\.

Note: “Changed” means content modified since last sync snapshot. “New” means file exists on one or both sides when it did not exist at last snapshot. “Properties” includes metadata such as timestamps, attributes, and filename case.

#### 6.2.1 Same file changed on both Left and Right

If the same file has changed on both sides since last sync:

Preferred option (Option 1 - default):

Create copies of both the older and newer files on both sides.

Append " - clash" (or similar suffix) to the older file’s filename.

Send an email alert to admin describing:

File path

Which side was newer

Timestamps and sizes

Do not silently drop either version.

Alternate options (configurable, not default):

Option 2: Do nothing, and notify admin via email.

Option 3: Newer file overwrites older file automatically.

#### 6.2.2 New file created on both Left and Right and are different

If a file with the same path is newly created on both sides and contents differ:

Option 1 (preferred for consistency with above):

Treat same as “same file changed on both sides”.

Create conflict copies on both sides, mark older with " - clash", email admin.

Alternate option (configurable):

Option 2: Newer file overwrites older file.

#### 6.2.3 File changed on Left only

If the file has only been changed on Left but is unchanged on Right:

Behavior:

Left overwrites Right.

Copy file from Left to Right.

#### 6.2.4 File changed on Right only

If the file has only been changed on Right but is unchanged on Left:

Behavior:

Right overwrites Left.

Copy file from Right to Left.

#### 6.2.5 File deleted on Left but changed or created on Right

If file is deleted on Left but was changed or created on Right since last snapshot:

Behavior:

Treat Right as authoritative in this case.

Copy file from Right to Left (effectively “undelete” on Left).

#### 6.2.6 File deleted on Right but changed or created on Left

If file is deleted on Right but was changed or created on Left:

Behavior:

Treat Left as authoritative.

Copy file from Left to Right (effectively “undelete” on Right).

#### 6.2.7 File deleted on Left, unchanged on Right

If a file is deleted from Left but is unchanged on Right (since last state):

Behavior:

Propagate deletion: delete file from Right, subject to soft delete policy.

#### 6.2.8 File deleted on Right, unchanged on Left

If file is deleted from Right but unchanged on Left:

Behavior:

Propagate deletion: delete file from Left, subject to soft delete policy.

#### 6.2.9 New file created on Left only

If a new file has been created on Left only:

Behavior:

Copy file to Right.

#### 6.2.10 New file created on Right only

If a new file has been created on Right only:

Behavior:

Copy file to Left.

#### 6.2.11 Properties or filename case changed on Left (unchanged on Right)

If file properties or filename case have changed on Left only:

Behavior:

Rename file on Right to match Left.

Copy file properties from Left to Right.

#### 6.2.12 Properties or filename case changed on Right (unchanged on Left)

If file properties or filename case have changed on Right only:

Behavior:

Rename file on Left to match Right.

Copy file properties from Right to Left.

#### 6.2.13 Properties or filename case changed and differ on both sides

If properties or filename case differ on both Left and Right:

Option 1 (preferred default for consistency):

Create conflict copies on both sides.

Mark older with " - clash".

Email admin.

Option 2:

Do nothing, notify admin via email.

Option 3:

Newer properties/filename overwrite older.

### 6.3 Soft Delete Policy

Soft delete is required for safety, but with constraints.

#### 6.3.1 General Soft Delete Rules

When the sync logic issues a delete (for a file < size threshold):

Move the file to a configurable soft delete folder instead of permanent deletion:

Example:

On Left: C:\local_share\.sync_trash\<original_path_structure>

On Right: R:\.sync_trash\<original_path_structure>

Record metadata in sync state (original path, delete time, source side, size).

No soft delete for files larger than a configured size threshold:

Threshold: 20 MB (default).

Files larger than this are deleted hard (no soft delete), but events are logged.

Soft delete behavior is symmetric for both Left and Right.

#### 6.3.2 Soft Delete Configuration

Configurable parameters (via config file):

soft_delete.enabled (bool, default: true).

soft_delete.max_size_bytes (default: 20 MB).

soft_delete.left_trash_root path.

soft_delete.right_trash_root path.

soft_delete.retention_days:

Implemented as:

Optionally configured but not applied in v0.1 (keep for future).

v0.1 may simply store but not auto-clean, or implement basic cleanup if agreed.

### 6.4 Real-time Behavior and Performance

#### 6.4.1 Real-time Target

Target: changes propagated within ~10 seconds.

Implementation approach:

Continuous loop with a short sleep (configurable, default 10 seconds).

Optionally integrate file-system watchers (if reliable with remote drive) for future enhancement.

#### 6.4.2 Prioritization of Small Files

Because the environment includes large media files:

The sync engine must prioritize small files for faster visible consistency for everyday documents.

Strategy (high level):

Maintain a queue of pending operations, ordered by:

Primary key: file size ascending (small files first).

Secondary key: change time.

Large files are still synced but should not block small change propagation.

#### 6.4.3 Impact of File Size

The system must function with large files but:

Avoid re-hashing entire large files unnecessarily.

Use metadata first (timestamps, size) and only fall back to content hashing if needed and cost is acceptable.

### 6.5 Configuration

All major behavior must be driven by a config file, for example sync_config.json or sync_config.toml.

#### 6.5.1 Required Config Options

Paths:

left_root: e.g. C:\\local_share

right_root: e.g. R:\\

Polling / real-time settings:

sync_interval_seconds (default 10).

Conflict resolution options:

same_file_changed_both:

"option1" (default), "option2", "option3"

new_file_both_different:

"option1" (default), "option2"

properties_conflict_both:

"option1" (default), "option2", "option3"

Soft delete settings:

soft_delete.enabled

soft_delete.max_size_bytes (default corresponds to 20 MB).

soft_delete.left_trash_root

soft_delete.right_trash_root

soft_delete.retention_days (stored, may be inactive in v0.1).

Email / alert settings:

SMTP host, port.

Auth mode (for Gmail or other providers).

Username, app password or token.

from_address.

to_addresses list for alerts.

TLS/SSL flags.

Logging:

log_file_path.

log_level (info, debug, warn, error).

max_log_size and rotation settings (optional).

#### 6.5.2 Future Config Options (vNext, placeholder only)

Enable/disable content hashing for verification.

Per-path rules (e.g. exclude certain folders, different rules for media).

Different thresholds for small/large file classification.

### 6.6 Email Alerts

The system must send email notifications to a configured address when:

Any conflict is detected and handled according to an option that requires alerts (Option 1 or 2).

Any operation fails (e.g. unable to copy file, permission denied, path too long) where admin intervention may be needed.

Optionally, periodic summary (daily) of number of operations and conflicts (could be vNext).

Details in email:

Timestamp.

File path relative to root.

Involved sides (Left/Right).

Operation result (conflict with copies, overwrite, delete).

Key metadata (size, last modified times on both sides).

Error message if any.

### 6.7 Logging & Observability

The script must log to a local file.

Log entries must include:

Timestamp.

Operation type (scan, copy, delete, conflict, error).

Path(s) involved.

Result (success/failure).

Basic metrics that should be easy to derive from logs:

Number of files scanned per interval.

Number of changes detected per interval.

Number of conflicts.

Number of soft deletes vs hard deletes.

Logs should be suitable for later consumption by log tools (CSV, structured text, or JSON-based logging).

### 6.8 Service Behavior (Future Phase)

For v0.1, a script is built with clear entry point and configuration. For later conversion into a Windows service:

Must be able to run:

When no user is logged in.

Under a dedicated service account with necessary file and network permissions.

Service requirements:

Starts at boot.

Recovers on failure (e.g. set up restart-on-failure at OS level).

Stops cleanly, flushing any in-memory state.

## 7. Non-functional Requirements

### 7.1 Reliability

Sync must be resilient to:

Temporary remote drive unavailability.

Network interruptions.

Server restarts.

On restart, script must:

Reload state from the state database.

Resume syncing without user intervention.

### 7.2 Performance

Target:

Handle ~90k files without excessive CPU usage.

Normal operations should not saturate slow WAN.

Strategies:

Incremental scanning instead of scanning entire tree every loop.

Avoid re-copying unchanged files.

Prioritize small files.

### 7.3 Safety

Soft delete for safety, with:

No soft delete for files > 20 MB.

Logging of all destructive operations.

Rely on existing backup (Backblaze) as an additional safety net, but script should not depend on backup to function.

### 7.4 Security

Service account must have least-privilege access to:

Local share.

remote drive.

Soft delete locations.

Email credentials (for Gmail or other SMTP) must not be hard-coded:

Stored in config file with appropriate access permissions, or in Windows credential store if implemented later.

### 7.5 Maintainability

Code structured into clear modules:

Config management.

State tracking.

Change detection.

Decision engine (sync rules).

Executors (copy/delete/rename).

Logging and alerting.

Generic enough that adding new rules or additional storage endpoints later is straightforward.

## 8. Data Model & State

### 8.1 State Database

Local state database (likely SQLite file) storing:

File relative path.

Last known:

Existence status on Left and Right.

Size on each side.

Last modified timestamp on each side.

Properties (basic flags).

Last action performed by sync engine for that file.

Used to:

Detect changes between runs.

Resolve which side changed since last sync.

## 9. Error Handling Scenarios

The system must handle and log:

Permission errors on either side.

Paths that exceed Windows path length limits.

Files locked by another process.

Temporary remote drive disconnection or drive letter not mounted.

Out-of-space conditions on either side or in soft delete storage.

For each, behavior is:

Log to file with details.

Send email if the error affects sync correctness.

Skip or retry based on type and severity (policy defined in implementation detail, but logged either way).

## 10. Future Enhancements (Out of Scope for v0.1)

GUI to show sync status, conflicts, and statistics.

Web dashboard with metrics and manual conflict resolution tools.

Configurable rules per folder (e.g. always hard delete in temp folders).

Smart bandwidth throttling based on time of day or WAN usage.

Integration with remote drive APIs directly (instead of only via mapped drive) for more efficient operations.

Automatic cleanup of soft delete folder based on retention and size thresholds.

test suite written in powershell that we can run on a windows machine, often the unit tests are not picking up issues due to windows specific issues

## 11. Acceptance Criteria

A first version is considered acceptable when:

Script can be run on the Windows file server pointing at:

C:\local_share and R:\.

After initial scan:

New or changed files on Left appear on Right, and vice versa.

Conflicts (files changed on both sides) result in:

Two copies preserved, older one tagged with " - clash" suffix.

Email alert sent with correct information.

Deletes are propagated according to rules, with:

Soft delete behavior applied for files <= 20 MB.

No soft delete for files > 20 MB, but deletion logged.

Common operations (create, modify, delete on either side) are reflected on the other side within roughly 10 seconds under normal load.

Script can be stopped and restarted:

Without losing track of what has changed.

Without duplicate or missed operations (beyond acceptable edge race conditions).

All key behaviors are controllable via a single config file, without code changes.