import os
import logging
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, OperationFailure
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

client = None
db = None

def init_db():
    global client, db
    # --- ✨ التصحيح هنا ✨ ---
    if db is not None: 
        return True
        
    uri = os.getenv("MONGODB_URI")
    if not uri:
        logger.error("!!! متغير البيئة MONGODB_URI غير موجود.")
        return False
    try:
        client = MongoClient(uri)
        client.admin.command('ismaster')
        db = client.telegram_bot_db
        logger.info("✅ تم الاتصال بقاعدة البيانات بنجاح!")
        return True
    except (ConnectionFailure, OperationFailure) as e:
        logger.error(f"❌ فشل الاتصال بقاعدة البيانات: {e}")
        client = db = None
        return False

def get_user(user_id):
    if db is None: return None
    return db.users.find_one({"user_id": user_id})

def add_user(user):
    if db is None: return
    if get_user(user.id):
        logger.info(f"المستخدم {user.id} موجود بالفعل.")
        return
    user_data = {
        "user_id": user.id, "first_name": user.first_name, "last_name": user.last_name,
        "username": user.username, "language_code": "ar",
        "registration_date": datetime.now(timezone.utc), "last_interaction_date": datetime.now(timezone.utc),
        "download_count": 0, "subscription_status": "free", "subscription_expiry": None, "watermark_enabled": False
    }
    db.users.insert_one(user_data)
    
def is_subscribed(user_id):
    if db is None: return False
    user = get_user(user_id)
    if not user:
        return False
    
    # التحقق من حالة الاشتراك
    status = user.get("subscription_status", "free")
    if status in ["pro", "premium"]:
        return True
    
    # التحقق من تاريخ انتهاء الاشتراك
    expiry = user.get("subscription_expiry")
    if expiry and expiry > datetime.now(timezone.utc):
        return True
        
    return False
    logger.info(f"✅ تم إضافة مستخدم جديد: {user.full_name} ({user.id})")

def update_user_interaction(user_id):
    if db is None: return
    db.users.update_one({"user_id": user_id}, {"$set": {"last_interaction_date": datetime.now(timezone.utc)}})

def increment_download_count(user_id):
    if db is None: return
    db.users.update_one({"user_id": user_id}, {"$inc": {"download_count": 1}})

def get_total_users_count():
    if db is None: return 0
    return db.users.count_documents({})

def get_total_downloads_count():
    if db is None: return 0
    pipeline = [{"$group": {"_id": None, "total_downloads": {"$sum": "$download_count"}}}]
    result = list(db.users.aggregate(pipeline))
    return result[0].get("total_downloads", 0) if result else 0

def get_all_user_ids():
    if db is None: return []
    return [user["user_id"] for user in db.users.find({}, {"user_id": 1})]

def get_user_language(user_id):
    user = get_user(user_id)
    return user.get("language_code", "ar") if user else "ar"

def is_admin(user_id):
    admin_id = os.getenv("ADMIN_ID")
    return str(user_id) == str(admin_id)

def set_user_subscription(user_id: int, status: str, expiry_date: datetime = None):
    if db is None: return False
    update_fields = {"subscription_status": status}
    if expiry_date:
        update_fields["subscription_expiry"] = expiry_date
    result = db.users.update_one({"user_id": user_id}, {"$set": update_fields})
    return result.modified_count > 0
    if db is None: return False
    result = db.users.update_one({"user_id": user_id}, {"$set": {"subscription_status": status}})
    return result.modified_count > 0

def set_user_language(user_id: int, lang_code: str):
    if db is None: return False
    result = db.users.update_one({"user_id": user_id}, {"$set": {"language_code": lang_code}})
    return result.modified_count > 0

# لا نستدعي init_db() هنا، بل في bot.py
