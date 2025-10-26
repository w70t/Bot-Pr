import json
import logging

# --- Constants ---
CONFIG_FILE = 'config.json'

# --- Logging Setup ---
logger = logging.getLogger(__name__)

# --- Helper Function for Config ---
def load_config():
    """Loads configuration from config.json."""
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        logger.error("config.json not found or is invalid. Payment gateway cannot function.")
        return None

# --- Payment Gateway Functions ---

def create_payment_link(user_id: int) -> str | None:
    """
    Creates a payment link for the user using the configured payment gateway.
    
    Returns:
        str: The payment URL if successful.
        None: If payments are disabled or an error occurs.
    """
    config = load_config()
    if not config or not config.get("payments_enabled"):
        logger.warning("Attempted to create payment link while payments are disabled.")
        return None

    price = config.get("subscription_price_usd", 2.0)
    api_key = config.get("binance_api_key")
    secret_key = config.get("binance_secret_key")

    # This is where the actual integration with Binance Pay SDK would go.
    # You would use the api_key and secret_key to make a request to Binance.
    # For now, we will just log it and return a placeholder.
    
    logger.info(f"Placeholder: Generating Binance Pay link for user {user_id} for ${price}.")
    
    # This is a placeholder link. In a real scenario, this would be the response from Binance.
    payment_url = f"https://pay.binance.com/checkout/placeholder-for-user-{user_id}"
    
    return payment_url


def verify_payment(transaction_id: str ) -> bool:
    """
    Verifies a payment transaction with the payment gateway.
    This is a placeholder for now.
    """
    config = load_config()
    if not config or not config.get("payments_enabled"):
        return False
        
    # In a real scenario, you would use the transaction_id to query the
    # Binance API to confirm the payment status.
    logger.info(f"Placeholder: Verifying payment with transaction ID: {transaction_id}")
    
    # For our testing purposes, we can create a simple rule.
    # If the transaction_id is 'test_success', we'll consider it valid.
    if transaction_id == 'test_success':
        logger.info("Test payment verification successful.")
        return True
        
    logger.warning(f"Test payment verification failed for ID: {transaction_id}")
    return False
