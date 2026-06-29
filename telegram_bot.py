#!/usr/bin/env python3
"""
Ship Tracker Bot - Simple HTTP API version (no telegram library)
"""

import requests
import json
import math
import time
import logging
from datetime import datetime
from pathlib import Path
import threading

# Configuration
IMO = "9005871"
TELEGRAM_BOT_TOKEN = "8977424709:AAG7rEB7QhNvG3_ypI7tabRQw66TUQ78Zbc"
TELEGRAM_CHAT_ID = "6198515219"

TARGET_LAT = 37.8447
TARGET_LON = 23.7744
GEOFENCE_RADIUS_KM = 5

STATE_FILE = Path("ship_state.json")
CHECK_INTERVAL = 600  # 10 minutes
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_state():
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE) as f:
                return json.load(f)
        except:
            pass
    return {"last_lat": None, "last_lon": None, "last_distance": None, "in_geofence": False}


def save_state(state):
    try:
        with open(STATE_FILE, 'w') as f:
            json.dump(state, f)
    except:
        pass


def get_ship_position():
    try:
        url = f"https://www.vesselfinder.com/api/pub/click/{IMO}"
        r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
        if r.status_code == 200:
            data = r.json()
            if 'position' in data:
                return {
                    'lat': data['position']['latitude'],
                    'lon': data['position']['longitude'],
                    'speed': data.get('speed', 0),
                    'course': data.get('course', 0),
                }
    except Exception as e:
        logger.error(f"Fetch error: {e}")
    return None


def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    a = math.sin(delta_lat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c


def send_message(text):
    try:
        r = requests.post(f"{TELEGRAM_API}/sendMessage", json={"chat_id": TELEGRAM_CHAT_ID, "text": text}, timeout=5)
        return r.status_code == 200
    except:
        return False


def get_updates(offset=0):
    try:
        r = requests.get(f"{TELEGRAM_API}/getUpdates", params={"offset": offset}, timeout=5)
        if r.status_code == 200:
            return r.json().get("result", [])
    except:
        pass
    return []


def handle_message(update):
    if "message" not in update:
        return

    msg = update["message"]
    text = msg.get("text", "")
    chat_id = msg["chat"]["id"]

    if text == "/location":
        position = get_ship_position()
        if not position:
            send_message("❌ Error fetching position")
            return

        distance = calculate_distance(position['lat'], position['lon'], TARGET_LAT, TARGET_LON)
        status = "IN" if distance <= GEOFENCE_RADIUS_KM else "OUT"

        reply = f"🚢 Position:\nLat: {position['lat']:.4f}\nLon: {position['lon']:.4f}\n\nVouliagmeni:\nDistance: {distance:.2f} km\nStatus: {status}\nSpeed: {position['speed']} kts"
        send_message(reply)

    elif text == "/status":
        state = load_state()
        if state['last_lat'] is None:
            send_message("⏳ No data yet")
            return

        reply = f"Distance: {state['last_distance']:.2f} km\nStatus: {'IN' if state['in_geofence'] else 'OUT'}\nBot: Running"
        send_message(reply)

    elif text in ["/start", "/help"]:
        reply = "🚢 Ship Tracker\n\n/location - Get position\n/status - Status"
        send_message(reply)


def check_ship():
    while True:
        try:
            position = get_ship_position()
            if position:
                state = load_state()
                distance = calculate_distance(position['lat'], position['lon'], TARGET_LAT, TARGET_LON)
                in_geofence = distance <= GEOFENCE_RADIUS_KM

                if in_geofence and not state['in_geofence']:
                    send_message(f"🚢 Entering! {distance:.2f} km")
                elif not in_geofence and state['in_geofence']:
                    send_message(f"🚢 Leaving! {distance:.2f} km")

                state['last_lat'] = position['lat']
                state['last_lon'] = position['lon']
                state['last_distance'] = distance
                state['in_geofence'] = in_geofence
                save_state(state)
        except Exception as e:
            logger.error(f"Check error: {e}")

        time.sleep(CHECK_INTERVAL)


def main():
    logger.info("Bot starting...")

    # Start background check thread
    check_thread = threading.Thread(target=check_ship, daemon=True)
    check_thread.start()

    # Poll for messages
    offset = 0
    while True:
        try:
            updates = get_updates(offset)
            for update in updates:
                handle_message(update)
                offset = update["update_id"] + 1

            time.sleep(1)
        except Exception as e:
            logger.error(f"Poll error: {e}")
            time.sleep(5)


if __name__ == '__main__':
    main()
