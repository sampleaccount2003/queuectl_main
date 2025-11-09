# QueueCTL - Background Job Queue System

A CLI-based background job queue system that manages background jobs with worker processes, handles retries using exponential backoff, and maintains a Dead Letter Queue (DLQ) for permanently failed jobs.

## 🚀 Quick Start

### Prerequisites

- Python 3.7 or higher
- pip (Python package installer)

### Installation

1. **Clone the repository** (or navigate to the project directory):
   ```bash
   cd queueCTL
   ```

2. **Install the package in development mode**:
   ```bash
   pip install -e .
   ```

   This will install `queuectl` as a command-line tool that you can use from anywhere.

3. **Verify installation**:
   ```bash
   queuectl --help
   ```

## 📖 Usage

### Basic Commands

#### 1. Enqueue a Job

Add a new job to the queue:

```bash
queuectl enqueue '{"id":"job1","command":"echo Hello World"}'
```

You can also omit the `id` field to auto-generate one:

```bash
queuectl enqueue '{"command":"sleep 2"}'
```

**Example:**
```bash
$ queuectl enqueue '{"id":"test1","command":"echo Hello World"}'
Enqueued job test1
```

**Note for Windows users:** The `sleep` command doesn't exist in Windows. Since commands run in cmd.exe by default, use:
- **CMD command:** `timeout /t 2 /nobreak` (recommended for Windows)
- **PowerShell command:** `powershell -Command "Start-Sleep -Seconds 2"` (if you need PowerShell)
- **Simple commands:** `echo`, `dir`, `type`, etc. work fine
- **Python scripts:** You can also run Python: `python -c "import time; time.sleep(2)"`

#### 2. Start Workers

Start one or more worker processes to process jobs:

```bash
# Start a single worker
queuectl worker start

# Start multiple workers (e.g., 3 workers)
queuectl worker start --count 3
```

**Example:**
```bash
$ queuectl worker start --count 2
Started 2 worker(s). Press Ctrl-C to stop.
[worker 1] started
[worker 2] started
[worker 1] processing job test1: echo Hello World
[worker 1] job test1 completed successfully
```

**Note:** If jobs complete very quickly (like `echo` commands), you might see only one worker processing them because it picks up the next job before other workers check. To see parallel processing:
1. Enqueue multiple jobs **before** starting workers
2. Use longer-running jobs (e.g., `timeout /t 2 /nobreak` on Windows, or `sleep 2` on Linux/Mac)
3. Enqueue jobs while workers are running (in another terminal)

Press `Ctrl-C` to gracefully stop all workers (they will finish their current job before exiting).

#### 3. Check Status

View a summary of all job states and configuration:

```bash
queuectl status
```

**Example Output:**
```
=== QueueCTL Status ===
Total Jobs: 5

Jobs by State:
  Pending: 2
  Processing: 1
  Completed: 1
  Failed: 0
  Dead: 1

Workers Active: Unknown (check worker processes)

Configuration:
  Max Retries: 3
  Backoff Base: 2
```

#### 4. List Jobs

List all jobs or filter by state:

```bash
# List all jobs
queuectl list

# List only pending jobs
queuectl list --state pending

# List only completed jobs
queuectl list --state completed
```

**Example:**
```bash
$ queuectl list --state pending
{"id": "job1", "command": "sleep 5", "state": "pending", "attempts": 0, ...}
```

#### 5. Dead Letter Queue (DLQ)

View jobs that have permanently failed:

```bash
# List all jobs in DLQ
queuectl dlq list

# Retry a job from DLQ
queuectl dlq retry job1
```

**Example:**
```bash
$ queuectl dlq list
{"id": "failed_job", "command": "invalid_command", "state": "dead", ...}

$ queuectl dlq retry failed_job
Requeued failed_job from DLQ
```

#### 6. Configuration

Manage system configuration:

```bash
# Set max retries
queuectl config set max_retries 5

# Set backoff base (for exponential backoff)
queuectl config set backoff_base 3

# Get a config value
queuectl config get max_retries

# List all configuration
queuectl config list
```

**Example:**
```bash
$ queuectl config set max_retries 5
Set max_retries=5

$ queuectl config get max_retries
max_retries=5
```

#### 7. Stop Workers

Stop running workers gracefully:

```bash
queuectl worker stop
```

This sets a flag that workers check, allowing them to finish their current job before exiting.

## 🏗️ Architecture Overview

### Job Lifecycle

```
pending → processing → completed
              ↓
           failed → (retry with backoff) → pending
              ↓
           (after max_retries) → dead (DLQ)
```

### Job States

- **pending**: Waiting to be picked up by a worker
- **processing**: Currently being executed by a worker
- **completed**: Successfully executed
- **failed**: Failed, but retryable (will retry with exponential backoff)
- **dead**: Permanently failed (moved to DLQ after exhausting retries)

### Data Persistence

- Jobs are stored in a SQLite database (`queuectl.db` by default)
- Database uses WAL (Write-Ahead Logging) mode for better concurrency
- All job data persists across restarts

### Retry Mechanism

- Failed jobs automatically retry with exponential backoff
- Delay formula: `delay = base ^ attempts` seconds
- Example with `backoff_base=2`:
  - Attempt 1: 2^0 = 1 second
  - Attempt 2: 2^1 = 2 seconds
  - Attempt 3: 2^2 = 4 seconds
  - Attempt 4: 2^3 = 8 seconds

### Worker Management

- Multiple workers can process jobs in parallel
- Jobs are locked when picked up (state changes to `processing`)
- Prevents duplicate processing
- Graceful shutdown: workers finish current job before exiting

## 🧪 Testing

### Manual Testing Examples

1. **Test successful job execution:**
   ```bash
   queuectl enqueue '{"id":"test1","command":"echo Success"}'
   queuectl worker start
   # Wait for completion
   queuectl list --state completed
   ```

2. **Test retry mechanism:**
   ```bash
   queuectl config set max_retries 3
   # On Linux/Mac:
   queuectl enqueue '{"id":"fail1","command":"false","max_retries":3}'
   # On Windows:
   queuectl enqueue '{"id":"fail1","command":"exit /b 1","max_retries":3}'
   queuectl worker start
   # Watch the job retry with exponential backoff
   queuectl list --state pending
   ```

3. **Test DLQ:**
   ```bash
   queuectl config set max_retries 1
   queuectl enqueue '{"id":"dlq_test","command":"invalid_command_xyz","max_retries":1}'
   queuectl worker start
   # After retries exhausted, check DLQ
   queuectl dlq list
   ```

4. **Test multiple workers:**
   ```bash
   # On Linux/Mac:
   queuectl enqueue '{"id":"job1","command":"sleep 2"}'
   queuectl enqueue '{"id":"job2","command":"sleep 2"}'
   queuectl enqueue '{"id":"job3","command":"sleep 2"}'
   # On Windows (CMD - recommended):
   queuectl enqueue '{"id":"job1","command":"timeout /t 2 /nobreak"}'
   queuectl enqueue '{"id":"job2","command":"timeout /t 2 /nobreak"}'
   queuectl enqueue '{"id":"job3","command":"timeout /t 2 /nobreak"}'
   # On Windows (PowerShell - if needed):
   queuectl enqueue '{"id":"job1","command":"powershell -Command \"Start-Sleep -Seconds 2\""}'
   queuectl worker start --count 3
   # Watch all 3 jobs process in parallel
   ```

### Running Automated Tests

If you have pytest installed:

```bash
pip install pytest
pytest tests/
```

## 📁 Project Structure

```
queueCTL/
├── queuectl/
│   ├── __init__.py      # Package marker
│   ├── cli.py           # Main CLI entry point
│   ├── db.py            # Database operations
│   ├── job.py           # Job management (enqueue, list, status)
│   ├── worker.py        # Worker process logic
│   ├── dlq.py           # Dead Letter Queue operations
│   ├── config.py        # Configuration management
│   └── utils.py         # Utility functions
├── tests/
│   ├── __init__.py
│   ├── test_enqueue.py
│   ├── test_worker.py
│   └── test_dlq.py
├── setup.py             # Package setup configuration
└── README.md            # This file
```

## ⚙️ Configuration

### Default Configuration

- **max_retries**: 3
- **backoff_base**: 2
- **Database**: `queuectl.db` (can be changed via `QUEUECTL_DB` environment variable)

### Environment Variables

- `QUEUECTL_DB`: Path to the SQLite database file (default: `queuectl.db`)

## 🔧 Assumptions & Trade-offs

### Assumptions

1. **Command Execution**: Commands are executed using shell execution (`subprocess.run` with `shell=True`)
2. **Exit Codes**: Exit code 0 = success, non-zero = failure
3. **Timeout**: Jobs have a 5-minute timeout (configurable in code)
4. **Database**: SQLite is sufficient for single-machine deployment

### Trade-offs

1. **Concurrency**: Uses SQLite with WAL mode for basic concurrency. For high-scale deployments, consider PostgreSQL or another database.
2. **Worker Management**: Workers are managed via threading. For distributed systems, consider process-based workers or a message queue.
3. **Job Locking**: Uses database state changes for locking. For high contention, consider explicit locking mechanisms.
4. **Monitoring**: Basic status command. For production, consider adding metrics, logging, and monitoring dashboards.

## 🐛 Troubleshooting

### Issue: `queuectl: command not found`

**Solution**: Make sure you installed the package:
```bash
pip install -e .
```

### Issue: Database locked errors

**Solution**: This can happen with multiple workers. The system uses WAL mode to minimize this. If it persists, ensure only one process is accessing the database at a time.

### Issue: Workers not processing jobs

**Solution**: 
1. Check if workers are actually running: `queuectl status`
2. Verify jobs are in `pending` state: `queuectl list --state pending`
3. Check if `next_run_at` is in the past (for retried jobs)

### Issue: Jobs stuck in processing state

**Solution**: This can happen if a worker crashes. You may need to manually reset the job state or implement a timeout mechanism.

## 📝 Example Workflow

Here's a complete example workflow:

```bash
# 1. Configure the system
queuectl config set max_retries 3
queuectl config set backoff_base 2

# 2. Enqueue some jobs
queuectl enqueue '{"id":"job1","command":"echo Hello"}'
# On Linux/Mac:
queuectl enqueue '{"id":"job2","command":"sleep 1"}'
queuectl enqueue '{"id":"job3","command":"false"}'  # This will fail
# On Windows:
queuectl enqueue '{"id":"job2","command":"timeout /t 1 /nobreak"}'
queuectl enqueue '{"id":"job3","command":"exit /b 1"}'  # This will fail

# 3. Check status
queuectl status

# 4. Start workers
queuectl worker start --count 2

# 5. In another terminal, monitor progress
queuectl list --state pending
queuectl list --state completed
queuectl list --state dead

# 6. Check DLQ for failed jobs
queuectl dlq list

# 7. Retry a job from DLQ
queuectl dlq retry job3
```

## 🎯 Features Implemented

✅ CLI-based job queue system  
✅ Job enqueueing with JSON input  
✅ Multiple worker support  
✅ Automatic retry with exponential backoff  
✅ Dead Letter Queue (DLQ)  
✅ Persistent job storage (SQLite)  
✅ Job state management  
✅ Configuration management  
✅ Graceful worker shutdown  
✅ Job locking to prevent duplicate processing  

## 📄 License

This project is part of a backend developer internship assignment.

## 🤝 Contributing

This is an assignment project. For questions or issues, please refer to the assignment requirements.

---

