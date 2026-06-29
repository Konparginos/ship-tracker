#!/usr/bin/env python3
"""
Telegram Ship Tracker Bot
Responds to /location command and sends alerts on ship movement
"""

import requests
import json
import math
import asyncio
import logging
from datetime import datetime
from pathlib import Path
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# Configuration
IMO = "9005871"
TELEGRAM_BOT_TOKEN = "8977424709:AAG7rEB7QhNvG3_ypI7tabRQw66TUQ78Zbc"
TELEGRAM_CHAT_ID = "6198515219"

TARGET_LAT = 37.8447
TARGET_LON = 23.7744
GEOFENCE_RADIUS_KM = 5

STATE_FILE = Path("ship_state.json")
CHECK_INTERVAL = 600  # 10 minutes

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


def load_state():
    """Load previous ship state"""
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            return json.load(f)
    return {
        "last_lat": None,
        "last_lon": None,
        "last_distance": None,
        "in_geofence": False,
        "last_alert": None
    }


def save_state(state):
    """Save ship state"""
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)


def get_ship_position():
    """Fetch current ship position from VesselFinder"""
    try:
        url = f"https://www.vesselfinder.com/api/pub/click/{IMO}"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        response = requests.get(url, headers=headers, timeout=10)

        if response.status_code == 200:
            data = response.json()
            if 'position' in data:
                return {
                    'lat': data['position']['latitude'],
                    'lon': data['position']['longitude'],
                    'speed': data.get('speed', 0),
                    'course': data.get('course', 0),
                    'timestamp': datetime.now().isoformat()
                }
    except Exception as e:
        logger.error(f"Error fetching from VesselFinder: {e}")

    return None


def calculate_distance(lat1, lon1, lat2, lon2):
    """Calculate distance between two coordinates in km"""
    R = 6371
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)

    a = math.sin(delta_lat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

    return R * c


def is_approaching(current_distance, last_distance):
    """Determine if ship is approaching"""
    if last_distance is None:
        return None
    return current_distance < last_distance


async def send_telegram_message(context, message):
    """Send message via Telegram"""
    try:
        await context.bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=message,
            parse_mode='HTML'
        )
        logger.info(f"Message sent: {message[:50]}...")
        return True
    except Exception as e:
        logger.error(f"Error sending message: {e}")
        return False


async def check_ship(context):
    """Background task to check ship location every 10 minutes"""
    logger.info("Checking ship position...")

    position = get_ship_position()
    if not position:
        logger.error("Could not fetch ship position")
        return

    current_lat = position['lat']
    current_lon = position['lon']

    logger.info(f"Position: {current_lat:.4f}, {current_lon:.4f}")

    state = load_state()
    current_distance = calculate_distance(current_lat, current_lon, TARGET_LAT, TARGET_LON)

    logger.info(f"Distance to Vouliagmeni: {current_distance:.2f} km")

    in_geofence_now = current_distance <= GEOFENCE_RADIUS_KM
    was_in_geofence = state['in_geofence']

    # Check for state changes
    if in_geofence_now and not was_in_geofence:
        approaching = is_approaching(current_distance, state['last_distance'])
        direction = "approaching" if approaching else "entering"
        message = (
            f"🚢 <b>Ship Alert</b>\n"
            f"Vessel IMO {IMO} is <b>{direction}</b> Vouliagmeni!\n"
            f"Distance: {current_distance:.2f} km\n"
            f"Speed: {position['speed']} kts\n"
            f"Course: {position['course']}°\n"
            f"Time: {datetime.now().strftime('%H:%M:%S')}"
        )
        await send_telegram_message(context, message)

    elif not in_geofence_now and was_in_geofence:
        message = (
            f"🚢 <b>Ship Alert</b>\n"
            f"Vessel IMO {IMO} is <b>departing</b> Vouliagmeni!\n"
            f"Distance: {current_distance:.2f} km\n"
            f"Speed: {position['speed']} kts\n"
            f"Time: {datetime.now().strftime('%H:%M:%S')}"
        )
        await send_telegram_message(context, message)

    elif in_geofence_now and was_in_geofence and current_distance < 2:
        approaching = is_approaching(current_distance, state['last_distance'])
        if approaching:
            message = (
                f"🚢 <b>Ship Update</b>\n"
                f"Vessel IMO {IMO} is <b>very close</b> to Vouliagmeni!\n"
                f"Distance: {current_distance:.2f} km\n"
                f"Speed: {position['speed']} kts\n"
                f"Time: {datetime.now().strftime('%H:%M:%S')}"
            )
            await send_telegram_message(context, message)

    # Update state
    state['last_lat'] = current_lat
    state['last_lon'] = current_lon
    state['last_distance'] = current_distance
    state['in_geofence'] = in_geofence_now
    state['last_alert'] = datetime.now().isoformat()
    save_state(state)


async def location_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /location command"""
    position = get_ship_position()

    if not position:
        await update.message.reply_text("❌ Could not fetch ship position")
        return

    state = load_state()
    distance = calculate_distance(position['lat'], position['lon'], TARGET_LAT, TARGET_LON)

    in_geofence = distance <= GEOFENCE_RADIUS_KM
    status = "🔴 IN GEOFENCE" if in_geofence else "🟢 Outside geofence"

    message = (
        f"🚢 <b>Ship Position</b>\n\n"
        f"<b>Location:</b>\n"
        f"Latitude: {position['lat']:.4f}\n"
        f"Longitude: {position['lon']:.4f}\n\n"
        f"<b>Vouliagmeni:</b>\n"
        f"Distance: {distance:.2f} km\n"
        f"Status: {status}\n\n"
        f"<b>Movement:</b>\n"
        f"Speed: {position['speed']} kts\n"
        f"Course: {position['course']}°\n\n"
        f"<b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )

    await update.message.reply_text(message, parse_mode='HTML')


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /status command"""
    state = load_state()

    if state['last_lat'] is None:
        await update.message.reply_text("⏳ No data yet. Waiting for first check...")
        return

    distance = state['last_distance']
    in_geofence = state['in_geofence']
    status = "🔴 IN GEOFENCE" if in_geofence else "🟢 Outside geofence"

    message = (
        f"📊 <b>Tracker Status</b>\n\n"
        f"<b>Current Status:</b> {status}\n"
        f"<b>Distance to Vouliagmeni:</b> {distance:.2f} km\n"
        f"<b>Last Position:</b> ({state['last_lat']:.4f}, {state['last_lon']:.4f})\n"
        f"<b>Last Update:</b> {state['last_alert']}\n\n"
        f"<b>Bot Status:</b> ✅ Running\n"
        f"<b>Check Interval:</b> Every 10 minutes"
    )

    await update.message.reply_text(message, parse_mode='HTML')


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    message = (
        f"🚢 <b>Ship Tracker Bot</b>\n\n"
        f"Track vessel IMO {IMO} near Vouliagmeni, Greece\n\n"
        f"<b>Commands:</b>\n"
        f"/location - Get current ship position\n"
        f"/status - Get tracker status\n"
        f"/help - Show this message\n\n"
        f"<b>Alerts:</b> Automatic alerts when ship enters/exits the area"
    )
    await update.message.reply_text(message, parse_mode='HTML')


def main():
    """Start the bot"""
    # Create application
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Add handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", start_command))
    app.add_handler(CommandHandler("location", location_command))
    app.add_handler(CommandHandler("status", status_command))

    # Add job to check ship every 10 minutes
    app.job_queue.run_repeating(check_ship, interval=CHECK_INTERVAL, first=1)

    # Start the bot
    logger.info("Bot starting...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
