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

A Python-based bidirectional file synchronization tool for syncing between local and network drives with intelligent conflict resolution, soft delete, and email notifications.

## Features

- **Bidirectional Sync**: Automatically sync files between left and right directories
- **Conflict Resolution**: Multiple strategies (clash, overwrite newer, notify-only)
- **Soft Delete**: Safely move deleted files to a `.deleted/` folder before permanent deletion
- **Ignore Rules**: Skip files by extension, prefix, or exact name
- **State Tracking**: SQLite database remembers last sync state
- **Email Alerts**: Get notified of conflicts and errors
- **Comprehensive Logging**: Full audit trail of all sync operations
- **Case-Sensitive**: File name case changes (e.g., `Document.txt` → `document.txt`) are synced

## Installation

### Prerequisites
- Python 3.11 or higher
- Git (optional, for cloning)

### Windows Setup

1. **Clone the repository** (or download as ZIP)
   ```bash
   git clone https://github.com/rooh010/dink-claude-test.git
   cd dink-claude-test
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

4. **Create config file**
   ```bash
   copy config.example.yaml config.yaml
   ```
   Edit `config.yaml` with your paths:
   ```yaml
   left_root: C:\pdrive_local
   right_root: P:\
   ```

## Usage

### Run Sync

```bash
# Using config.yaml in current directory
python -m remote_office_sync.main --config config.yaml

# Or using environment variable
set SYNC_CONFIG=C:\path\to\config.yaml
python -m remote_office_sync.main --use-env
```

### Run Tests

```bash
pytest -v
```

### Check Code Quality

```bash
black . --check
ruff check .
```

## Configuration

### Basic Config

```yaml
# Windows paths must use escaped backslashes or forward slashes
left_root: "C:\\pdrive_local"
right_root: "P:\\"

soft_delete:
  enabled: true
  max_size_mb: 20

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
```

**Important:** Windows paths in YAML must be quoted and use either:
- Double backslashes: `"C:\\Users\\Documents"`
- Forward slashes: `"C:/Users/Documents"`

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

## Soft Delete

Files below the size threshold (default 20MB) are moved to `.deleted/` instead of permanently deleted.

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
2025-01-22 14:30:45 - sync - INFO - Scanned 1523 files in C:\pdrive_local
2025-01-22 14:30:45 - sync - INFO - Scanned 1520 files in P:\
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

- Real-time file watching (FSEvents)
- Scheduled sync via Windows Task Scheduler
- Incremental sync (only changed files)
- File checksums for safety verification
- Web UI for configuration and monitoring
- Support for Linux/Mac paths

## License

MIT License

## Support

For issues, questions, or contributions, visit the GitHub repository.