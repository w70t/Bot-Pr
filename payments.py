import os
import json
import logging
from datetime import datetime, timedelta, timezone

# --- File Paths ---
STATS_FILE = 'stats.json'

# --- Setup Logging ---
logger = logging.getLogger(__name__)

# --- Helper functions for file operations ---
def load_json_data(filename, default_data):
    """Loads data from a JSON file."""
    try:
        if os.path.exists(filename):
            with open(filename, 'r', encoding='utf-8') as f:
                return json.load(f)
    except (json.JSONDecodeError, IOError):
        logger.warning(f"Could not read or parse {filename}, starting with default data.")
    return default_data

def save_json_data(filename, data):
    """Saves data to a JSON file."""
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except IOError as e:
        logger.error(f"Could not save data to {filename}: {e}")

# --- Core Subscription Logic ---

def get_subscription_status(user_id: int) -> dict:
    """
    Checks a user's subscription status.
    If the subscription is expired, it deactivates it.
    Returns the current subscription dictionary.
    """
    stats = load_json_data(STATS_FILE, {"users": {}})
    user_id_str = str(user_id)
    
    # Default subscription status for a user who might not have one yet
    default_subscription = {
        "is_active": False,
        "plan_name": "Free",
        "start_date": None,
        "expiry_date": None
    }

    user_data = stats.get("users", {}).get(user_id_str)
    if not user_data or "subscription" not in user_data:
        return default_subscription

    subscription = user_data["subscription"]

    # Check if the subscription has expired
    if subscription.get("is_active") and subscription.get("expiry_date"):
        expiry_date = datetime.fromisoformat(subscription["expiry_date"])
        if datetime.now(timezone.utc) > expiry_date:
            logger.info(f"Subscription for user {user_id} has expired. Deactivating.")
            subscription["is_active"] = False
            subscription["plan_name"] = "Free"
            # We keep expiry_date to know when it expired
            
            # Save the updated status back to the file
            stats["users"][user_id_str]["subscription"] = subscription
            save_json_data(STATS_FILE, stats)

    return subscription


def activate_pro_subscription(user_id: int, duration_days: int = 30) -> bool:
    """
    Activates a Pro subscription for a user.
    This function would be called after a successful payment.
    """
    stats = load_json_data(STATS_FILE, {"users": {}})
    user_id_str = str(user_id)

    if user_id_str not in stats.get("users", {}):
        logger.warning(f"Attempted to activate subscription for non-existent user: {user_id}")
        return False

    now = datetime.now(timezone.utc)
    expiry_date = now + timedelta(days=duration_days)

    new_subscription_status = {
        "is_active": True,
        "plan_name": "Pro",
        "start_date": now.isoformat(),
        "expiry_date": expiry_date.isoformat()
    }

    stats["users"][user_id_str]["subscription"] = new_subscription_status
    save_json_data(STATS_FILE, stats)
    
    logger.info(f"Successfully activated Pro subscription for user {user_id} until {expiry_date.strftime('%Y-%m-%d')}.")
    return True

# --- Payment Gateway Functions (Placeholders for now) ---

def create_payment_link(user_id: int, plan: str, config: dict) -> str:
    """
    Creates a payment link for the user.
    This is a placeholder. In the future, it will call Binance/Stripe APIs.
    """
    logger.info(f"Placeholder: Creating payment link for user {user_id} for plan '{plan}'.")
    # In a real scenario, you would use the config to get API keys
    # and generate a unique link.
    return "https://example.com/dummy-payment-link"

