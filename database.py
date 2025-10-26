import os
import logging
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, OperationFailure
from datetime import datetime, timezone, timedelta

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

client = None
db = None

def init_db():
    """
    تهيئة الاتصال بقاعدة بيانات MongoDB
    """
    global client, db
    
    # التحقق من الاتصال الموجود
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
    """
    جلب بيانات مستخدم من قاعدة البيانات
    """
    if db is None: 
        return None
    return db.users.find_one({"user_id": user_id})

def add_user(user):
    """
    إضافة مستخدم جديد إلى قاعدة البيانات
    """
    if db is None: 
        return
    
    if get_user(user.id):
        logger.info(f"المستخدم {user.id} موجود بالفعل.")
        return
    
    user_data = {
        "user_id": user.id,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "username": user.username,
        "language_code": "ar",
        "registration_date": datetime.now(timezone.utc),
        "last_interaction_date": datetime.now(timezone.utc),
        "download_count": 0,
        "daily_download_count": 0,  # للحدود اليومية
        "last_download_reset": datetime.now(timezone.utc),  # تاريخ آخر إعادة تعيين
        "subscription_status": "free",
        "subscription_expiry": None,
        "watermark_enabled": False
    }
    
    db.users.insert_one(user_data)
    logger.info(f"✅ تم إضافة مستخدم جديد: {user.full_name} ({user.id})")

def is_subscribed(user_id):
    """
    التحقق من حالة اشتراك المستخدم
    """
    if db is None: 
        return False
    
    user = get_user(user_id)
    if not user:
        return False
    
    # التحقق من حالة الاشتراك
    status = user.get("subscription_status", "free")
    if status in ["pro", "premium"]:
        # التحقق من تاريخ انتهاء الاشتراك
        expiry = user.get("subscription_expiry")
        if expiry and expiry > datetime.now(timezone.utc):
            return True
        else:
            # انتهى الاشتراك، نعيده إلى free
            set_user_subscription(user_id, "free", None)
            return False
    
    return False

def update_user_interaction(user_id):
    """
    تحديث تاريخ آخر تفاعل للمستخدم
    """
    if db is None: 
        return
    db.users.update_one(
        {"user_id": user_id}, 
        {"$set": {"last_interaction_date": datetime.now(timezone.utc)}}
    )

def increment_download_count(user_id):
    """
    زيادة عداد التحميلات للمستخدم (الإجمالي واليومي)
    """
    if db is None: 
        return
    
    user = get_user(user_id)
    if not user:
        return
    
    # التحقق من الحدود اليومية
    last_reset = user.get("last_download_reset", datetime.now(timezone.utc))
    now = datetime.now(timezone.utc)
    
    # إذا مر 24 ساعة، نعيد تعيين العداد اليومي
    if (now - last_reset).total_seconds() > 86400:  # 24 ساعة
        db.users.update_one(
            {"user_id": user_id}, 
            {
                "$inc": {"download_count": 1},
                "$set": {
                    "daily_download_count": 1,
                    "last_download_reset": now
                }
            }
        )
    else:
        # زيادة العدادين
        db.users.update_one(
            {"user_id": user_id}, 
            {
                "$inc": {
                    "download_count": 1,
                    "daily_download_count": 1
                }
            }
        )

def get_daily_download_count(user_id):
    """
    جلب عدد التحميلات اليومية للمستخدم
    """
    if db is None:
        return 0
    
    user = get_user(user_id)
    if not user:
        return 0
    
    last_reset = user.get("last_download_reset", datetime.now(timezone.utc))
    now = datetime.now(timezone.utc)
    
    # إذا مر 24 ساعة، العداد اليومي = 0
    if (now - last_reset).total_seconds() > 86400:
        return 0
    
    return user.get("daily_download_count", 0)

def get_total_users_count():
    """
    جلب إجمالي عدد المستخدمين
    """
    if db is None: 
        return 0
    return db.users.count_documents({})

def get_total_downloads_count():
    """
    جلب إجمالي عدد التحميلات
    """
    if db is None: 
        return 0
    pipeline = [{"$group": {"_id": None, "total_downloads": {"$sum": "$download_count"}}}]
    result = list(db.users.aggregate(pipeline))
    return result[0].get("total_downloads", 0) if result else 0

def get_all_user_ids():
    """
    جلب قائمة بجميع معرفات المستخدمين
    """
    if db is None: 
        return []
    return [user["user_id"] for user in db.users.find({}, {"user_id": 1})]

def get_user_language(user_id):
    """
    جلب لغة المستخدم المفضلة
    """
    user = get_user(user_id)
    return user.get("language_code", "ar") if user else "ar"

def set_user_language(user_id: int, lang_code: str):
    """
    تعيين لغة المستخدم
    """
    if db is None: 
        return False
    result = db.users.update_one(
        {"user_id": user_id}, 
        {"$set": {"language_code": lang_code}}
    )
    return result.modified_count > 0

def is_admin(user_id):
    """
    التحقق من صلاحيات المدير
    """
    admin_id = os.getenv("ADMIN_ID")
    if not admin_id:
        return False
    return str(user_id) == str(admin_id)

def set_user_subscription(user_id: int, status: str, expiry_date: datetime = None):
    """
    تعيين حالة اشتراك المستخدم
    """
    if db is None: 
        return False
    
    update_fields = {"subscription_status": status}
    
    if status in ["pro", "premium"]:
        # إذا لم يتم تحديد تاريخ انتهاء، نضيف 30 يوم افتراضياً
        if expiry_date is None:
            expiry_date = datetime.now(timezone.utc) + timedelta(days=30)
        update_fields["subscription_expiry"] = expiry_date
    else:
        # إذا كان free، نحذف تاريخ الانتهاء
        update_fields["subscription_expiry"] = None
    
    result = db.users.update_one(
        {"user_id": user_id}, 
        {"$set": update_fields}
    )
    
    return result.modified_count > 0

def get_subscribers_count():
    """
    جلب عدد المشتركين (Pro/Premium)
    """
    if db is None:
        return 0
    return db.users.count_documents({
        "subscription_status": {"$in": ["pro", "premium"]},
        "subscription_expiry": {"$gt": datetime.now(timezone.utc)}
    })

def get_active_users_count(days=7):
    """
    جلب عدد المستخدمين النشطين خلال فترة معينة
    """
    if db is None:
        return 0
    since_date = datetime.now(timezone.utc) - timedelta(days=days)
    return db.users.count_documents({
        "last_interaction_date": {"$gte": since_date}
    })
