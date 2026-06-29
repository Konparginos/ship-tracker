#!/usr/bin/env python3
"""
Ship tracker daemon - runs continuously with scheduled checks
"""

import schedule
import time
import subprocess
import sys
from datetime import datetime

# Check interval in minutes
CHECK_INTERVAL_MINUTES = 30  # Check every 30 minutes (adjust as needed)


def run_tracker():
    """Run the ship tracker"""
    try:
        subprocess.run([sys.executable, "ship_tracker.py"], check=True)
    except subprocess.CalledProcessError as e:
        print(f"✗ Tracker error: {e}")


def main():
    print("=" * 50)
    print(f"Ship Tracker Daemon Started")
    print(f"Checking every {CHECK_INTERVAL_MINUTES} minutes")
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("Press Ctrl+C to stop")
    print("=" * 50)

    # Schedule the job
    schedule.every(CHECK_INTERVAL_MINUTES).minutes.do(run_tracker)

    # Run initial check immediately
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Running initial check...")
    run_tracker()

    # Keep the scheduler running
    while True:
        schedule.run_pending()
        time.sleep(60)  # Check scheduler every minute


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n✓ Daemon stopped")
