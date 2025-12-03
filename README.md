# Remote Office Sync Engine

## ⚠️ IMPORTANT DISCLAIMER

**THIS CODE IS FOR TESTING AND EDUCATIONAL PURPOSES ONLY.**

- **DO NOT USE THIS CODE IN ANY PRODUCTION ENVIRONMENT**
- This software is provided as-is, without any warranties or guarantees of any kind
- The author takes NO RESPONSIBILITY for any data loss, corruption, or other issues that may arise from using this code
- Use at your own risk - always maintain proper backups of your data
- This is experimental software and has not been validated for production use
- No support or maintenance is provided

---

A Python-based bidirectional file synchronization tool for syncing between two directories (e.g., a mapped network drive and a local folder, or any two local folders). Perfect for remote office environments where you need to keep files in sync between a central location and a local workstation.

## Features

- **Dry Run Mode**: Preview all changes with visual diagrams before making any modifications (enabled by default)
- **Bidirectional Sync**: Automatically sync files between left and right directories
- **Conflict Resolution**: Multiple strategies (clash, overwrite newer, notify-only)
- **Soft Delete**: Safely move deleted files to a `.deleted/` folder before permanent deletion
- **Ignore Rules**: Skip files by extension, prefix, or exact name
- **State Tracking**: SQLite database remembers last sync state
- **File Attributes**: Synchronize Windows file attributes (Hidden, ReadOnly, Archive)
- **Email Alerts**: Get notified of conflicts and errors (optional)
- **Comprehensive Logging**: Full audit trail of all sync operations
- **Case-Sensitive**: File name case changes (e.g., `Document.txt` → `document.txt`) are synced

## Installation

### Prerequisites
- Python 3.11 or higher
- Git (optional, for cloning)

### Windows Setup

1. **Clone the repository** (or download as ZIP)
   ```bash
   git clone https://github.com/rooh010/remote-office-sync-engine.git
   cd remote-office-sync-engine
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Create config file from template**
   ```bash
   copy config.template.yaml config.yaml
   ```
   Edit `config.yaml` with your environment-specific paths and settings:
   ```yaml
   left_root: "C:/local_share/"
   right_root: "R:/remote_share/"
   ```
   **IMPORTANT:** Paths MUST use forward slashes (`/`) not backslashes (`\`). YAML will fail to parse backslashes.

   **Note:** `config.yaml` is gitignored and should not be committed. Keep `config.template.yaml` updated in the repository with your standard configuration.

## Usage

### Run Sync

**Windows Command Prompt (cmd.exe):**
```cmd
REM Dry run mode - preview changes only, no actual modifications
run_sync.bat

REM Perform actual synchronization
run_sync.bat --no-dry-run
```

**Windows PowerShell:**
```powershell
# Dry run mode - preview changes only, no actual modifications
.\run_sync.ps1

# Perform actual synchronization
.\run_sync.ps1 --no-dry-run
```

**Python Direct (all platforms):**
```bash
# Dry run mode (uses config.yaml dry_run setting)
python -m remote_office_sync.main --config config.yaml

# Override config and perform actual synchronization
python -m remote_office_sync.main --config config.yaml --no-dry-run

# Use custom config location
python -m remote_office_sync.main --config C:/path/to/custom-config.yaml --no-dry-run
```

**Command-line Arguments:**
- `--config <path>` - Path to config.yaml file (default: config.yaml)
- `--no-dry-run` - Override config and perform actual synchronization (bypasses dry_run: true in config)
- `--use-env` - Load config path from SYNC_CONFIG environment variable (advanced)

### Run Tests

#### Unit Tests
```bash
pytest -v
```

#### Manual Integration Tests (Windows)

The project includes a comprehensive manual test suite that validates all sync scenarios with real file operations:

```powershell
# Run with default test directories
.\run_manual_tests.ps1 -LeftPath "C:\local_share" -RightPath "R:\remote_share"

# Run with custom directories
.\run_manual_tests.ps1 -LeftPath "C:\path\to\left" -RightPath "C:\path\to\right"
```
The script builds a temporary config (`config.manualtest.tmp.yaml`) using the paths you pass in and forces `dry_run: false`; your real `config.yaml` is never modified.

You can also run the manual suite in CI on a free GitHub Actions Windows runner using temp folders via `.github/workflows/manual-tests.yml` (trigger with `workflow_dispatch`).
The workflow fails if any manual test fails.
Manual suite now includes 26 tests, adding a case-conflict check that ensures newer content wins and conflict artifacts are created on both sides.

**The 26 manual test cases verify:**

1. **File Creation L→R**: Create file on left, sync, verify on right with matching content
2. **File Creation R→L**: Create file on right, sync, verify on left with matching content
3. **File Modification L→R**: Modify file on left, sync, verify on right with matching content
4. **File Modification R→L**: Modify file on right, sync, verify on left with matching content
5. **File Deletion from Left**: Delete file from left, sync, verify deleted from both sides
6. **File Deletion from Right**: Delete file from right, sync, verify deleted from both sides
7. **Directory Sync**: Create directory on left, sync, verify on right
8. **Modify-Modify Conflict**: Modify same file differently on both sides, verify:
   - Main file exists on both sides with newest content
   - .CONFLICT file exists on both sides with oldest content
9. **New-New Conflict**: Create same filename on both sides with different content, verify:
   - Main file exists on both sides with newest content
   - .CONFLICT file exists on both sides with oldest content
10. **Case Conflict**: Rename file with different casing, verify:
    - Main file exists on both sides with consistent casing
    - Content matches on both sides
11. **Subdirectory Files**: Create file in nested subdirectory, verify:
    - Directory structure preserved on both sides
    - File content matches on both sides
12. **Directory Deletion**: Create directory with files on both sides, delete from one side, sync, verify files are deleted from the other side
13. **Empty Directory Creation R→L**: Create empty directory on right, sync, verify it appears on left
14. **Conflict Files in Subdirectory**: Create modify-modify conflict in subdirectory, verify conflict files are created in same subdirectory (not at root level)
15. **Comprehensive Stress Test**: Create complex multi-operation scenario with multiple simultaneous operations:
    - Multiple file creations on both sides
    - Multiple file modifications (including conflicts)
    - Multiple file deletions across directories
    - Multiple directory creations with nested structures
    - Verify all operations sync correctly and conflicts are properly handled
16. **Case Conflict in Subdirectory**: Create case-insensitive conflict in subdirectory, verify conflict files exist in subdirectory with proper casing
17. **File Attribute Synchronization**: Create file with attributes, sync, set different attributes on each side, verify attributes sync bidirectionally (Hidden, ReadOnly, Archive)

18. **Directory Rename L→R:** Rename folder on left only → sync → verify renamed folder exists on both sides with all files
19. **Directory Rename R→L:** Rename folder on right only → sync → verify renamed folder exists on both sides with all files
20. **Directory Rename Same Name:** Rename folder to same name on both sides → sync → verify no conflicts and folder exists with correct name
21. **Directory Rename Conflict:** Rename folder to different names on both sides → sync → verify conflict handled without crash
22. **Nested Directory Rename:** Rename parent folder containing nested subdirectories → sync → verify entire structure renamed correctly
23. **Directory Rename Content Verification:** Rename folder → sync → verify content and structure preserved in renamed folder
24. **Directory Content Preservation:** Rename folder with multiple files in nested subdirectories → sync → verify all files exist in new location with correct content on both sides
25. **Directory Case Change:** Change only the case of a directory name (MyFolder → myfolder) → sync → verify case change syncs to both sides
26. **File Case Conflict Resolution:** Create same file with different casing on each side (CaseTest.txt on left with older mtime, casetest.txt on right with newer mtime) with different content → sync twice → verify canonical file (lowercase) exists on both sides with NEWER content, conflict file exists on both sides with OLDER content, and old casing is removed

The script automatically:
- Sets `dry_run: false` in config.yaml before testing
- Restores `dry_run: true` after testing
- Reports pass/fail for each test case
- Cleans up test files after completion

**IMPORTANT**: Before pushing to the repository, ensure ALL unit tests pass:
```bash
pytest
```

Then run the manual test suite to validate real-world file sync behavior:
```powershell
.\run_manual_tests.ps1 -LeftPath "C:\local_share" -RightPath "R:\remote_share"
```

### Check Code Quality

```bash
black . --check
ruff check .
```

## Configuration

### Basic Config

```yaml
# IMPORTANT: Paths MUST use forward slashes (/) not backslashes (\)
# Backslashes will cause YAML parsing errors!
left_root: "C:/local_share/"
right_root: "R:/remote_share/"

dry_run: true  # RECOMMENDED: Preview changes without modifying files

soft_delete:
  enabled: true
  max_size_mb: null  # null = soft delete ALL files (recommended). Or set a number (e.g., 20) for size limit

conflict_policy:
  modify_modify: clash
  new_new: clash
  metadata_conflict: clash

ignore:
  extensions: [.tmp, .bak, .log]
  filenames_prefix: [., ~]
  filenames_exact: [thumbs.db]

logging:
  level: INFO
  file_path: sync.log
  rotation_enabled: true
  max_size_mb: 10
  backup_count: 5

```

**CRITICAL:** Windows paths in YAML **MUST use forward slashes (`/`)**:
- ✅ **CORRECT**: `"C:/Users/Documents"`
- ❌ **WRONG**: `"C:\Users\Documents"` (will cause YAML parsing error: "unknown escape character")

### Logging

The sync engine includes comprehensive logging with automatic log rotation:

- **level**: Log verbosity (DEBUG, INFO, WARNING, ERROR)
- **file_path**: Location of log file
- **rotation_enabled**: Enable/disable automatic log rotation (default: true)
- **max_size_mb**: Maximum log file size before rotation (default: 10 MB)
- **backup_count**: Number of old log files to keep (default: 5)

Log files include the username of the user running the sync process, useful for tracking who made changes in multi-user environments. Set `rotation_enabled: false` to disable rotation and keep all logs in a single file for debugging.

### Email Notifications (Optional)

```yaml
email:
  enabled: true
  smtp_host: smtp.gmail.com
  smtp_port: 587
  username: your-email@gmail.com
  password: your-app-password
  from: your-email@gmail.com
  to:
    - recipient@example.com
```

## Sync Rules

The engine applies 13 sync rules to determine what to do with each file:

### New Files
- **New on left only** → Copy to right
- **New on right only** → Copy to left

### Changed Files
- **Changed on left only** → Copy to right
- **Changed on right only** → Copy to left
- **Changed on both sides** → Apply conflict policy

### Deleted Files
- **Deleted on left, unchanged on right** → Delete right (or soft delete)
- **Deleted on left, changed on right** → Copy right to left (right authoritative)
- **Deleted on right, unchanged on left** → Delete left (or soft delete)
- **Deleted on right, changed on left** → Copy left to right (left authoritative)

### Conflicts
- **Modify-Modify**: File changed on both sides → Apply `modify_modify` policy
- **New-New**: File created on both sides with different content → Apply `new_new` policy
- **Metadata**: File sizes differ significantly → Apply `metadata_conflict` policy

## Conflict Policies

### clash (Default)
Creates a timestamped conflict file from the older version:
- **Older version** → Saved as `filename.conflict.20250101_120000.ext`
- **Newer version** → Kept as the main file on both sides
- Both versions preserved, but newer content is active

### overwrite_newer
Automatically overwrites older version with newer one (no clash file created)

### notify_only
Sends email alert but doesn't modify files

## Dry Run Mode

**RECOMMENDED**: Keep dry run mode enabled until you're confident in the sync behavior!

When `dry_run: true` (default), the sync engine will:
- Scan both directories and analyze what needs to sync
- Show a detailed preview with visual diagrams
- Display exactly what would change with arrows showing file movements
- Make **NO actual changes** to your files

Example dry run output:
```
================================================================================
DRY RUN MODE - NO CHANGES WILL BE MADE
================================================================================

The following 5 operations would be performed:

Summary by Action:
--------------------------------------------------------------------------------
  → Copy LEFT → RIGHT: 2 files
  ← Copy RIGHT → LEFT: 1 files
  ⊗ Soft delete from RIGHT: 2 files

Detailed Changes:
--------------------------------------------------------------------------------

Copy LEFT → RIGHT:
  [LEFT] documents/report.docx → [RIGHT]
  [LEFT] images/logo.png → [RIGHT]

Copy RIGHT → LEFT:
  [LEFT] ← data/spreadsheet.xlsx [RIGHT]

Soft delete from RIGHT:
  [RIGHT] old_file.txt ⊗ (move to .deleted/)
  [RIGHT] temp_data.csv ⊗ (move to .deleted/)

================================================================================
END DRY RUN - To perform these changes, set dry_run: false in config
================================================================================
```

**To perform actual synchronization**, you have two options:
1. **Command-line override**: `run_sync.bat --no-dry-run` (keeps config safe)
2. **Config file**: Set `dry_run: false` in your config.yaml (permanent change)

## Soft Delete

Deleted files are moved to `.deleted/` instead of permanently deleted.

Configuration options:
- `max_size_mb: null` - Soft delete ALL files regardless of size (recommended default)
- `max_size_mb: 20` - Only soft delete files ≤ 20MB; larger files are permanently deleted

This allows recovery if a file was deleted by mistake. Files in `.deleted/` can be:
- Manually recovered
- Permanently purged after N days
- Cleaned with `SoftDeleteManager.clear_all_deleted()`

## Output

After each sync, you'll see:

```
==================================================
Sync Summary
==================================================
Total files processed: 1523
Sync jobs executed: 47
Jobs failed: 0
Conflicts detected: 2
Errors: 0
Soft delete directory size: 2.35 MB
==================================================
```

## Logging

All operations logged to `sync.log` with timestamps:

```
2025-01-22 14:30:45 - sync - INFO - Starting sync engine
2025-01-22 14:30:45 - sync - INFO - Scanned 1523 files in C:\local_share
2025-01-22 14:30:45 - sync - INFO - Scanned 1520 files in R:\remote_share
2025-01-22 14:30:46 - sync - INFO - [COPY_LEFT_TO_RIGHT] documents/report.docx
2025-01-22 14:30:46 - sync - WARNING - Conflict detected: data.xlsx
2025-01-22 14:30:47 - sync - INFO - Sync completed: 47 jobs executed, 0 failed
```

## Troubleshooting

### "Config file not found"
Make sure `config.yaml` exists in current directory or use `--config path/to/config.yaml`

### "Path does not exist"
Check that `left_root` and `right_root` in config.yaml are valid Windows paths

### Permission denied
- Ensure you have read/write permissions on both directories
- Run Command Prompt as Administrator if needed
- Close files in the directories before syncing

### Email not sending
- Enable 2FA on your email account
- Use app-specific passwords (not your actual password)
- Check SMTP host and port are correct for your email provider

## Project Structure

```
remote_office_sync/
├── __init__.py           # Package exports
├── config_loader.py      # Configuration parsing
├── scanner.py            # Directory scanning
├── state_db.py           # SQLite state tracking
├── sync_logic.py         # Sync decision engine
├── file_ops.py           # File operations
├── conflict.py           # Conflict detection/resolution
├── soft_delete.py        # Soft delete management
├── email_notifications.py # Email alerts
├── logging_setup.py      # Logging configuration
└── main.py               # Entry point

tests/
├── conftest.py           # Test fixtures
├── test_scanner.py       # Scanner tests
├── test_state_db.py      # Database tests
├── test_file_ops.py      # File operations tests
├── test_conflict.py      # Conflict detection tests
└── test_sync_logic.py    # Sync engine tests
```

## Testing

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_scanner.py

# Run with coverage
pytest --cov=remote_office_sync
```

## Development

Code quality tools:

```bash
# Format code
black .

# Check for lint errors
ruff check .

# Fix auto-fixable lint issues
ruff check . --fix
```

## Performance

For typical use cases:
- Scanning 10,000 files: ~2-3 seconds
- Sync decision making: ~1-2 seconds
- Copying 100MB file: ~5-10 seconds (depends on drive speed)
- Full sync cycle: ~30-60 seconds for typical office shares

## Limitations

- Not real-time (requires manual execution or scheduled task)
- No compression or bandwidth optimization
- Requires network connectivity for network drive
- Windows only (uses Windows paths)

## Future Enhancements

- **Windows Service** - Convert to a Windows Service for automated scheduled execution without user interaction
- Real-time file watching (FSEvents)
- Scheduled sync via Windows Task Scheduler
- Incremental sync (only changed files)
- File checksums for safety verification
- Web UI for configuration and monitoring
- Support for Linux/Mac paths

## License

MIT License

## Support

No support provided.
