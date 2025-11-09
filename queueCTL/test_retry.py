#!/usr/bin/env python3
"""
Test script to demonstrate the retry mechanism with exponential backoff.
This script enqueues a job that will fail and shows the retry behavior.
"""
import json
import subprocess
import time
import sys

def run_command(cmd):
    """Run a queuectl command and return output"""
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.stdout.strip(), result.stderr.strip(), result.returncode

def main():
    print("=" * 60)
    print("Testing Retry Mechanism with Exponential Backoff")
    print("=" * 60)
    print()
    
    # Step 1: Configure retry settings
    print("Step 1: Configuring retry settings...")
    print("  Setting max_retries to 3")
    run_command('queuectl config set max_retries 3')
    print("  Setting backoff_base to 2")
    run_command('queuectl config set backoff_base 2')
    print()
    
    # Step 2: Check current config
    print("Step 2: Verifying configuration...")
    stdout, _, _ = run_command('queuectl config list')
    print(stdout)
    print()
    
    # Step 3: Clear any existing jobs (optional)
    print("Step 3: Checking for existing jobs...")
    stdout, _, _ = run_command('queuectl status')
    print(stdout)
    print()
    
    # Step 4: Enqueue a job that will fail
    print("Step 4: Enqueueing a job that will fail...")
    
    # Determine OS and use appropriate failing command
    import platform
    if platform.system() == "Windows":
        failing_command = "exit /b 1"  # Windows command that fails
    else:
        failing_command = "false"  # Linux/Mac command that fails
    
    job_json = json.dumps({
        "id": "retry_test_job",
        "command": failing_command,
        "max_retries": 3
    })
    
    stdout, stderr, code = run_command(f'queuectl enqueue \'{job_json}\'')
    if code == 0:
        print(f"  ✓ {stdout}")
    else:
        print(f"  ✗ Error: {stderr}")
        return
    print()
    
    # Step 5: Show job details
    print("Step 5: Job details before processing...")
    stdout, _, _ = run_command('queuectl list --state pending')
    if stdout:
        print("  Pending jobs:")
        for line in stdout.split('\n'):
            if line.strip():
                job_data = json.loads(line)
                print(f"    ID: {job_data['id']}")
                print(f"    Command: {job_data['command']}")
                print(f"    Attempts: {job_data['attempts']}")
                print(f"    Max Retries: {job_data['max_retries']}")
    print()
    
    # Step 6: Instructions for manual worker start
    print("=" * 60)
    print("Step 6: Start a worker to process the job")
    print("=" * 60)
    print()
    print("In another terminal, run:")
    print("  queuectl worker start")
    print()
    print("Watch for:")
    print("  1. Job fails (attempt 0)")
    print("  2. Job retries after ~1 second (2^0 = 1s backoff)")
    print("  3. Job fails again (attempt 1)")
    print("  4. Job retries after ~2 seconds (2^1 = 2s backoff)")
    print("  5. Job fails again (attempt 2)")
    print("  6. Job retries after ~4 seconds (2^2 = 4s backoff)")
    print("  7. Job fails again (attempt 3)")
    print("  8. Job moves to DLQ (dead state)")
    print()
    print("After the worker finishes, check:")
    print("  queuectl status")
    print("  queuectl dlq list")
    print("  queuectl list --state dead")
    print()
    print("To retry from DLQ:")
    print("  queuectl dlq retry retry_test_job")
    print()

if __name__ == "__main__":
    main()

