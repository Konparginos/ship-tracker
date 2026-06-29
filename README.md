# Ship Tracker - Vouliagmeni Monitor

Automatic ship tracking with Telegram alerts using GitHub Actions. Checks every 30 minutes, 24/7, completely free.

## Features

- 🚢 Tracks vessel IMO 9005871
- 📍 Monitors proximity to Vouliagmeni, Greece (Astir Marina)
- 🔔 Telegram alerts when:
  - Ship enters 5km zone (approaching)
  - Ship exits the zone (departing)
  - Ship gets very close (<2km)
- ⚙️ Runs automatically every 30 minutes via GitHub Actions
- 💾 Tracks state to detect entry/exit

## Setup (2 minutes)

### Step 1: Create GitHub Repository

1. Go to github.com
2. Click New (top left)
3. Name it: ship-tracker
4. Click Create repository

### Step 2: Upload Files

1. In your new repo, click Add file → Upload files
2. Drag and drop these files from your Downloads:
   - ship_tracker_github.py
   - requirements.txt
   - .github/workflows/ship-tracker.yml (create folder structure)
3. Click Commit changes

### Step 3: Enable GitHub Actions

1. Go to Settings → Actions → General
2. Under "Actions permissions", select Allow all actions and reusable workflows
3. Click Save

### Step 4: Add Initial State File

1. In repo, click Add file → Create new file
2. Name: ship_state.json
3. Paste the initial state JSON
4. Click Commit new file

## How It Works

- Schedule: Runs every 30 minutes automatically via GitHub Actions
- Storage: Tracks ship state in ship_state.json in the repo
- Alerts: Sends Telegram messages when ship approaches/leaves Vouliagmeni
- Logs: Check Actions tab to see run history

## Configuration

Edit these values in ship_tracker_github.py:
- GEOFENCE_RADIUS_KM (line 13): Alert radius in km (default: 5)
- TARGET_LAT/TARGET_LON (lines 14-15): Vouliagmeni coordinates
- IMO (line 10): Vessel IMO number

## Monitoring

1. Go to Actions tab in your repo
2. Click Ship Tracker to see recent runs
3. Click a run to see detailed logs
4. Check your Telegram bot for alerts

---

Your ship tracker is now running 24/7 in the cloud!
