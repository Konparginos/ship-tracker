import functions_framework
import requests
import json
import math
from datetime import datetime
from google.cloud import storage

# Configuration
IMO = "9005871"
TELEGRAM_BOT_TOKEN = "8977424709:AAG7rEB7QhNvG3_ypI7tabRQw66TUQ78Zbc"
TELEGRAM_CHAT_ID = "6198515219"

TARGET_LAT = 37.8447
TARGET_LON = 23.7744
GEOFENCE_RADIUS_KM = 5

BUCKET_NAME = "ship-tracker-state"
STATE_FILE = "ship_state.json"


def get_storage_client():
    """Get Google Cloud Storage client"""
    return storage.Client()


def load_state():
    """Load previous ship state from Cloud Storage"""
    try:
        client = get_storage_client()
        bucket = client.bucket(BUCKET_NAME)
        blob = bucket.blob(STATE_FILE)
        if blob.exists():
            return json.loads(blob.download_as_string())
    except Exception as e:
        print(f"Warning: Could not load state: {e}")

    return {
        "last_lat": None,
        "last_lon": None,
        "last_distance": None,
        "in_geofence": False,
        "last_alert": None
    }


def save_state(state):
    """Save ship state to Cloud Storage"""
    try:
        client = get_storage_client()
        bucket = client.bucket(BUCKET_NAME)
        blob = bucket.blob(STATE_FILE)
        blob.upload_from_string(json.dumps(state, indent=2))
    except Exception as e:
        print(f"Warning: Could not save state: {e}")


def get_ship_position():
    """Fetch current ship position from VesselFinder"""
    try:
        url = f"https://www.vesselfinder.com/api/pub/click/{IMO}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
        }
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
        print(f"Error fetching from VesselFinder: {e}")

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


def send_telegram_alert(message):
    """Send alert via Telegram"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML"
        }
        response = requests.post(url, json=payload, timeout=5)
        return response.status_code == 200
    except Exception as e:
        print(f"Error sending Telegram alert: {e}")
        return False


@functions_framework.http
def track_ship(request):
    """HTTP Cloud Function to track ship"""
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Checking ship position...")

    # Get current position
    position = get_ship_position()
    if not position:
        return "Could not fetch ship position", 500

    current_lat = position['lat']
    current_lon = position['lon']

    print(f"Position: {current_lat:.4f}, {current_lon:.4f}")
    print(f"Speed: {position['speed']} kts | Course: {position['course']}°")

    # Load previous state
    state = load_state()

    # Calculate distance
    current_distance = calculate_distance(
        current_lat, current_lon,
        TARGET_LAT, TARGET_LON
    )

    print(f"Distance to Vouliagmeni: {current_distance:.2f} km")

    # Check for state changes
    in_geofence_now = current_distance <= GEOFENCE_RADIUS_KM
    was_in_geofence = state['in_geofence']

    alert_sent = False

    if in_geofence_now and not was_in_geofence:
        # Entering geofence
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
        send_telegram_alert(message)
        alert_sent = True

    elif not in_geofence_now and was_in_geofence:
        # Leaving geofence
        message = (
            f"🚢 <b>Ship Alert</b>\n"
            f"Vessel IMO {IMO} is <b>departing</b> Vouliagmeni!\n"
            f"Distance: {current_distance:.2f} km\n"
            f"Speed: {position['speed']} kts\n"
            f"Time: {datetime.now().strftime('%H:%M:%S')}"
        )
        send_telegram_alert(message)
        alert_sent = True

    elif in_geofence_now and was_in_geofence:
        # Still in geofence
        approaching = is_approaching(current_distance, state['last_distance'])
        if approaching and current_distance < 2:
            message = (
                f"🚢 <b>Ship Update</b>\n"
                f"Vessel IMO {IMO} is <b>very close</b> to Vouliagmeni!\n"
                f"Distance: {current_distance:.2f} km\n"
                f"Speed: {position['speed']} kts\n"
                f"Time: {datetime.now().strftime('%H:%M:%S')}"
            )
            send_telegram_alert(message)
            alert_sent = True

    # Update state
    state['last_lat'] = current_lat
    state['last_lon'] = current_lon
    state['last_distance'] = current_distance
    state['in_geofence'] = in_geofence_now
    if alert_sent:
        state['last_alert'] = datetime.now().isoformat()

    save_state(state)

    return {
        "status": "ok",
        "distance_km": round(current_distance, 2),
        "in_geofence": in_geofence_now,
        "alert_sent": alert_sent
    }, 200
