#!/usr/bin/env python3
"""
Telegram Ship Tracker Bot - Stable Version
"""

import requests
import json
import math
import logging
from datetime import datetime
from pathlib import Path
from telegram import Update
from telegram.ext import Updater, CommandHandler

# Configuration
IMO = "9005871"
TELEGRAM_BOT_TOKEN = "8977424709:AAG7rEB7QhNvG3_ypI7tabRQw66TUQ78Zbc"
TELEGRAM_CHAT_ID = "6198515219"

TARGET_LAT = 37.8447
TARGET_LON = 23.7744
GEOFENCE_RADIUS_KM = 5

STATE_FILE = Path("ship_state.json")
CHECK_INTERVAL = 600  # 10 minutes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_state():
    """Load previous ship state"""
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE) as f:
                return json.load(f)
        except:
            pass
    return {
        "last_lat": None,
        "last_lon": None,
        "last_distance": None,
        "in_geofence": False,
        "last_alert": None
    }


def save_state(state):
    """Save ship state"""
    try:
        with open(STATE_FILE, 'w') as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving state: {e}")


def get_ship_position():
    """Fetch current ship position"""
    try:
        url = f"https://www.vesselfinder.com/api/pub/click/{IMO}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)

        if response.status_code == 200:
            data = response.json()
            if 'position' in data:
                return {
                    'lat': data['position']['latitude'],
                    'lon': data['position']['longitude'],
                    'speed': data.get('speed', 0),
                    'course': data.get('course', 0),
                }
    except Exception as e:
        logger.error(f"Error fetching: {e}")
    return None


def calculate_distance(lat1, lon1, lat2, lon2):
    """Calculate distance in km"""
    R = 6371
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    a = math.sin(delta_lat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c


def location(update, context):
    """Handle /location"""
    try:
        position = get_ship_position()
        if not position:
            update.message.reply_text("Error fetching position")
            return

        distance = calculate_distance(position['lat'], position['lon'], TARGET_LAT, TARGET_LON)
        in_geofence = distance <= GEOFENCE_RADIUS_KM
        status = "IN GEOFENCE" if in_geofence else "Outside"

        msg = f"Ship Position:\nLat: {position['lat']:.4f}\nLon: {position['lon']:.4f}\n\nVouliagmeni:\nDistance: {distance:.2f} km\nStatus: {status}\n\nSpeed: {position['speed']} kts"
        update.message.reply_text(msg)
    except Exception as e:
        logger.error(f"Error: {e}")
        update.message.reply_text(f"Error: {e}")


def status(update, context):
    """Handle /status"""
    try:
        state = load_state()
        if state['last_lat'] is None:
            update.message.reply_text("No data yet")
            return

        msg = f"Distance: {state['last_distance']:.2f} km\nStatus: {'IN' if state['in_geofence'] else 'OUT'}\nLast: ({state['last_lat']:.2f}, {state['last_lon']:.2f})"
        update.message.reply_text(msg)
    except Exception as e:
        logger.error(f"Error: {e}")


def start(update, context):
    """Handle /start"""
    msg = "Ship Tracker Bot\n\n/location - Get position\n/status - Tracker status"
    update.message.reply_text(msg)


def check_ship(context):
    """Background check"""
    try:
        logger.info("Checking...")
        position = get_ship_position()
        if not position:
            return

        state = load_state()
        distance = calculate_distance(position['lat'], position['lon'], TARGET_LAT, TARGET_LON)
        in_geofence = distance <= GEOFENCE_RADIUS_KM
        was_in = state['in_geofence']

        if in_geofence and not was_in:
            context.bot.send_message(TELEGRAM_CHAT_ID, f"Ship entering! {distance:.2f} km")
        elif not in_geofence and was_in:
            context.bot.send_message(TELEGRAM_CHAT_ID, f"Ship leaving! {distance:.2f} km")

        state['last_lat'] = position['lat']
        state['last_lon'] = position['lon']
        state['last_distance'] = distance
        state['in_geofence'] = in_geofence
        save_state(state)
    except Exception as e:
        logger.error(f"Check error: {e}")


def main():
    """Start bot"""
    try:
        logger.info("Starting...")
        updater = Updater(TELEGRAM_BOT_TOKEN)
        dispatcher = updater.dispatcher

        dispatcher.add_handler(CommandHandler("start", start))
        dispatcher.add_handler(CommandHandler("location", location))
        dispatcher.add_handler(CommandHandler("status", status))

        updater.job_queue.run_repeating(check_ship, interval=CHECK_INTERVAL, first=1)

        logger.info("Bot running")
        updater.start_polling()
        updater.idle()
    except Exception as e:
        logger.error(f"Fatal: {e}")


if __name__ == '__main__':
    main()

