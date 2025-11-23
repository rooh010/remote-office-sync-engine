# MVP Task List

## ⚠️ TESTING PURPOSES ONLY

**DISCLAIMER:** This document describes software for testing and educational purposes only. DO NOT use in production environments. The author takes no responsibility for any data loss or issues arising from use of this code.

---

**Remote Office File Sync Script (Python)**
**Phase:** MVP 0.1

The goal of the MVP is to produce a working Python script that performs a correct one-shot bi-directional sync between the Left (C:\pdrive_local) and Right (P:\) paths using all sync rules, including conflict resolution, soft delete, and config-based behaviour.
Real-time watchers, Windows service integration, and advanced features are not included in MVP.

## 1. Project Setup

### 1.1 Repository Structure

Create Python project skeleton:

/config/ (optional)

/sync/ package with modules:

config_loader.py

scanner.py

state_db.py

sync_logic.py

file_ops.py

conflict.py

soft_delete.py

logging_setup.py

main.py

Add .gitignore for Python, logs, state DB, virtualenv.

### 1.2 Config File

Implement config.yaml with keys:

left_root

right_root

soft_delete.enabled

soft_delete.max_size_mb (20 default)

conflict_policy.modify_modify

conflict_policy.new_new

conflict_policy.metadata_conflict

email.smtp_host, smtp_port, username, password, from, to

ignore.extensions

ignore.filenames_prefix

ignore.filenames_exact

Implement config_loader.py to:

Parse config.

Validate required fields.

Expose config object.

## 2. Metadata & State

### 2.1 Define Metadata Model

For each file:

relative path

exists_left

exists_right

mtime_left

mtime_right

size_left

size_right

maybe: hash_left/hash_right for small files (optional for MVP)

### 2.2 State Database (SQLite)

Create SQLite DB file with table:

files (
  path TEXT PRIMARY KEY,
  exists_left INTEGER,
  exists_right INTEGER,
  mtime_left REAL,
  mtime_right REAL,
  size_left INTEGER,
  size_right INTEGER
)


Implement:

load previous state

write updated state

## 3. Scanning System

### 3.1 Implement Directory Scanner (scanner.py)

Recursively walk Left root.

Recursively walk Right root.

Apply ignore rules from config:

ignored extensions

ignored prefix

ignored exact filenames

Build fresh metadata snapshot for Left and Right.

### 3.2 Merge Scan Results

Merge Left + Right scans into combined structure of all relative paths.

## 4. Sync Decision Engine

Implement sync_logic.py that takes:

previous state

current state

config

Outputs:

list of sync actions in order.

Actions include:

COPY_LEFT_TO_RIGHT

COPY_RIGHT_TO_LEFT

DELETE_LEFT

DELETE_RIGHT

SOFT_DELETE_LEFT

SOFT_DELETE_RIGHT

CLASH_CREATE

RENAME_LEFT

RENAME_RIGHT

NOOP (for logging)

## 5. Implement All Sync Rules

### 5.1 Same file changed both sides

Compare mtime_left vs mtime_right.

If both changed:

If policy = clash:

Create clash copies on both sides.

Keep newer as main.

Queue CLASH_CREATE actions.

Queue COPY actions.

Queue email notification.

If policy = notify only:

Queue email, no overwrite.

If policy = overwrite:

Newer overwrites older.

### 5.2 New file on both sides, content differs

Apply same decision as above.

### 5.3 Changed on left only

Queue COPY_LEFT_TO_RIGHT.

### 5.4 Changed on right only

Queue COPY_RIGHT_TO_LEFT.

### 5.5 Deleted on left, changed or created on right

Treat Right as authoritative → COPY_RIGHT_TO_LEFT.

### 5.6 Deleted on right, changed or created on left

Treat Left as authoritative → COPY_LEFT_TO_RIGHT.

### 5.7 Deleted on left, unchanged on right

DELETE_RIGHT or SOFT_DELETE_RIGHT depending on size.

### 5.8 Deleted on right, unchanged on left

DELETE_LEFT or SOFT_DELETE_LEFT.

### 5.9 New file only on left

COPY_LEFT_TO_RIGHT.

### 5.10 New file only on right

COPY_RIGHT_TO_LEFT.

### 5.11 Properties or filename case changed on left only

RENAME_RIGHT.

### 5.12 Properties or filename case changed on right only

RENAME_LEFT.

### 5.13 Properties/case changed on both sides

Treat as conflict per policy.

## 6. File Operations Layer

Implement file_ops.py:

### 6.1 Copy operations

Ensure directories exist.

Copy with metadata (mtime, attributes).

### 6.2 Delete operations

If soft delete enabled AND size ≤ threshold:

Move to soft delete folder.

Else:

Hard delete.

### 6.3 Clash handling

Generate timestamped clash filename.

Copy older file → clash filename.

Copy newer file → main filename.

Mirror on both sides.

### 6.4 Renames

Perform rename.

Ensure consistency across Left/Right.

## 7. Email Notifications

Implement email_notifications.py:

Use Python smtplib.

Use config-specified SMTP host, TLS, username, password.

Function:

send_conflict_email(details)

send_error_email(details)

Content must include:

path

timestamps

sizes

what rule was triggered

actions performed

## 8. Logging

Implement logger with:

rotating logs

INFO for operations

WARNING for skipped items

ERROR for failures

Log every action taken by the engine.

Log all errors with stack traces.

## 9. Integrate Everything (main.py)

Steps in main:

Load config

Load previous state DB

Scan both sides

Merge into state snapshot

Run decision engine

Execute actions in order

Update state DB

Print summary

Exit

## 10. Testing & Validation

Create test folders:

left_test/

right_test/

Test scenarios for:

Single file create left → right

Single file create right → left

Change left only

Change right only

Delete on left only

Delete on right only

Delete + change conflict

Create on both with different content

Modify both → clash

Large file (over 20 MB) delete → hard delete

Rename on left only

Rename on right only

Metadata conflict

Ignored file types

Soft delete validation

## 11. MVP Completion Criteria

The MVP is complete when:

A single run of the script performs correct bidirectional sync with all rules.

Clash files are created where expected.

Soft delete works for files <= 20 MB.

Files over 20 MB skip soft delete.

Config file fully controls behaviour.

Email alerts fire correctly for conflict events.

Logging is complete and readable.

State DB correctly remembers last run.

All major rule paths tested manually and via synthetic test folders.