#!/usr/bin/env python3
"""
Telegram Ship Tracker Bot - Version for python-telegram-bot 13.14
"""

import requests
import json
import math
import logging
from datetime import datetime
from pathlib import Path
from telegram import Update
from telegram.ext import Updater, CommandHandler, CallbackContext
from telegram.error import TelegramError

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
        logger.error(f"Error fetching position: {e}")

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


def is_approaching(current_distance, last_distance):
    """Check if approaching"""
    if last_distance is None:
        return None
    return current_distance < last_distance


def send_telegram_message(update, context, message):
    """Send message"""
    try:
        update.message.reply_text(message, parse_mode='HTML')
        return True
    except Exception as e:
        logger.error(f"Error sending message: {e}")
        return False


def location_command(update: Update, context: CallbackContext):
    """Handle /location command"""
    try:
        position = get_ship_position()

        if not position:
            update.message.reply_text("❌ Could not fetch ship position")
            return

        distance = calculate_distance(position['lat'], position['lon'], TARGET_LAT, TARGET_LON)
        in_geofence = distance <= GEOFENCE_RADIUS_KM
        status = "🔴 IN GEOFENCE" if in_geofence else "🟢 Outside"

        message = (
            f"🚢 <b>Ship Position</b>\n\n"
            f"<b>Location:</b>\n"
            f"Lat: {position['lat']:.4f}\n"
            f"Lon: {position['lon']:.4f}\n\n"
            f"<b>Vouliagmeni:</b>\n"
            f"Distance: {distance:.2f} km\n"
            f"Status: {status}\n\n"
            f"<b>Movement:</b>\n"
            f"Speed: {position['speed']} kts\n"
            f"Course: {position['course']}°"
        )

        update.message.reply_text(message, parse_mode='HTML')

    except Exception as e:
        logger.error(f"Error in location_command: {e}")
        update.message.reply_text(f"❌ Error: {str(e)}")


def status_command(update: Update, context: CallbackContext):
    """Handle /status command"""
    try:
        state = load_state()

        if state['last_lat'] is None:
            update.message.reply_text("⏳ No data yet...")
            return

        distance = state['last_distance'] or 0
        in_geofence = state['in_geofence']
        status = "🔴 IN GEOFENCE" if in_geofence else "🟢 Outside"

        message = (
            f"📊 <b>Tracker Status</b>\n\n"
            f"Status: {status}\n"
            f"Distance: {distance:.2f} km\n"
            f"Position: ({state['last_lat']:.4f}, {state['last_lon']:.4f})\n\n"
            f"<b>Bot:</b> ✅ Running"
        )

        update.message.reply_text(message, parse_mode='HTML')

    except Exception as e:
        logger.error(f"Error in status_command: {e}")
        update.message.reply_text(f"❌ Error: {str(e)}")


def start_command(update: Update, context: CallbackContext):
    """Handle /start command"""
    message = (
        f"🚢 <b>Ship Tracker Bot</b>\n\n"
        f"Track vessel IMO {IMO}\n\n"
        f"<b>Commands:</b>\n"
        f"/location - Current position\n"
        f"/status - Tracker status\n"
        f"/help - Help"
    )
    update.message.reply_text(message, parse_mode='HTML')


def check_ship(context: CallbackContext):
    """Background location check"""
    try:
        logger.info("Checking ship...")
        position = get_ship_position()

        if not position:
            return

        state = load_state()
        distance = calculate_distance(position['lat'], position['lon'], TARGET_LAT, TARGET_LON)

        in_geofence_now = distance <= GEOFENCE_RADIUS_KM
        was_in_geofence = state['in_geofence']

        if in_geofence_now and not was_in_geofence:
            msg = f"🚢 Ship entering Vouliagmeni! ({distance:.2f} km)"
            context.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=msg)

        elif not in_geofence_now and was_in_geofence:
            msg = f"🚢 Ship leaving Vouliagmeni! ({distance:.2f} km)"
            context.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=msg)

        state['last_lat'] = position['lat']
        state['last_lon'] = position['lon']
        state['last_distance'] = distance
        state['in_geofence'] = in_geofence_now
        state['last_alert'] = datetime.now().isoformat()
        save_state(state)

    except Exception as e:
        logger.error(f"Error in check_ship: {e}")


def main():
    """Start the bot"""
    try:
        logger.info("Starting bot...")
        updater = Updater(token=TELEGRAM_BOT_TOKEN)
        dispatcher = updater.dispatcher

        # Add handlers
        dispatcher.add_handler(CommandHandler("start", start_command))
        dispatcher.add_handler(CommandHandler("help", start_command))
        dispatcher.add_handler(CommandHandler("location", location_command))
        dispatcher.add_handler(CommandHandler("status", status_command))

        # Add job
        job_queue = updater.job_queue
        job_queue.run_repeating(check_ship, interval=CHECK_INTERVAL, first=1)

        logger.info("Bot started successfully")
        updater.start_polling()
        updater.idle()

    except Exception as e:
        logger.error(f"Fatal error: {e}")


if __name__ == '__main__':
    main()
