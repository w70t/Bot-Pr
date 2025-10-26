import json
import logging
from datetime import datetime, timedelta, timezone

# --- Constants ---
STATS_FILE = 'stats.json'

# --- Logging Setup ---
logger = logging.getLogger(__name__)

# --- Helper Functions for JSON data ---
def load_stats():
    """Loads stats data from stats.json."""
    try:
        with open(STATS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        logger.error("stats.json not found or is invalid. Cannot perform payment logic.")
        return None

def save_stats(data):
    """Saves data to stats.json."""
    with open(STATS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

# --- Core Subscription Logic ---

def get_subscription_status(user_id: int) -> dict:
    """
    Checks the subscription status of a user.
    Returns a dictionary with subscription details.
    """
    user_id_str = str(user_id)
    stats_data = load_stats()
    
    if not stats_data:
        return {"is_active": False, "plan_name": "Free", "expiry_date": None}

    user_data = stats_data.get("users", {}).get(user_id_str)

    if not user_data or "subscription" not in user_data:
        return {"is_active": False, "plan_name": "Free", "expiry_date": None}

    subscription = user_data["subscription"]
    
    if subscription.get("is_active"):
        expiry_date_str = subscription.get("expiry_date")
        if expiry_date_str:
            try:
                expiry_date = datetime.fromisoformat(expiry_date_str)
                if datetime.now(timezone.utc) < expiry_date:
                    return subscription
            except ValueError:
                logger.error(f"Invalid expiry_date format for user {user_id_str}")

    return {"is_active": False, "plan_name": "Free", "expiry_date": None}


def activate_pro_subscription(user_id: int, days: int = 30) -> bool:
    """
    Activates a PRO subscription for a user for a specified number of days.
    Returns True on success, False on failure.
    """
    user_id_str = str(user_id)
    stats_data = load_stats()
    
    if not stats_data or "users" not in stats_data or user_id_str not in stats_data["users"]:
        logger.error(f"Cannot activate subscription for non-existent user: {user_id}")
        return False
        
    now = datetime.now(timezone.utc)
    
    # Check if user already has an active subscription to extend it
    current_status = get_subscription_status(user_id)
    if current_status["is_active"]:
        start_date = datetime.fromisoformat(current_status["expiry_date"])
    else:
        start_date = now

    expiry_date = start_date + timedelta(days=days)

    subscription_info = {
        "is_active": True,
        "plan_name": "PRO",
        "start_date": now.isoformat(),
        "expiry_date": expiry_date.isoformat()
    }
    
    stats_data["users"][user_id_str]["subscription"] = subscription_info
    
    save_stats(stats_data)
    logger.info(f"PRO subscription activated/extended for user {user_id} for {days} days.")
    return True
