import os
import logging
from pymongo import MongoClient
from datetime import datetime, timedelta

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# الاتصال بقاعدة البيانات
MONGODB_URI = os.getenv("MONGODB_URI")
ADMIN_IDS_STR = os.getenv("ADMIN_ID", "")

try:
    if not MONGODB_URI:
        raise ValueError("متغير البيئة MONGODB_URI غير موجود.")
    
    client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
    client.server_info()
    
    db = client.telegram_bot
    users_collection = db.users
    
    logger.info("✅ تم الاتصال بقاعدة البيانات بنجاح.")
except Exception as e:
    logger.error(f"!!! خطأ في الاتصال بقاعدة البيانات: {e}")
    db = None
    users_collection = None

def init_db():
    """التحقق من الاتصال بقاعدة البيانات"""
    if db is None or users_collection is None:
        logger.error("!!! قاعدة البيانات غير متصلة.")
        return False
    return True

def is_admin(user_id: int) -> bool:
    """التحقق من صلاحيات المدير"""
    admin_ids = [int(admin_id.strip()) for admin_id in ADMIN_IDS_STR.split(',') if admin_id.strip()]
    return user_id in admin_ids

def add_user(user_id: int, username: str = None, full_name: str = None, language: str = 'ar'):
    """إضافة مستخدم جديد"""
    try:
        user_data = {
            'user_id': user_id,
            'username': username,
            'full_name': full_name,
            'language': language,
            'join_date': datetime.now(),
            'last_interaction': datetime.now(),
            'download_count': 0,
            'daily_downloads': [],
            'subscription_end': None
        }
        
        users_collection.update_one(
            {'user_id': user_id},
            {'$setOnInsert': user_data},
            upsert=True
        )
        logger.info(f"✅ تم إضافة/تحديث المستخدم {user_id}")
        return True
    except Exception as e:
        logger.error(f"❌ فشل إضافة المستخدم: {e}")
        return False

def get_user(user_id: int):
    """جلب بيانات مستخدم"""
    try:
        user = users_collection.find_one({'user_id': user_id})
        return user
    except Exception as e:
        logger.error(f"❌ فشل جلب بيانات المستخدم: {e}")
        return None

def get_all_users():
    """جلب جميع المستخدمين"""
    try:
        users = list(users_collection.find())
        return users
    except Exception as e:
        logger.error(f"❌ فشل جلب المستخدمين: {e}")
        return []

def update_user_language(user_id: int, language: str):
    """تحديث لغة المستخدم"""
    try:
        users_collection.update_one(
            {'user_id': user_id},
            {'$set': {'language': language}}
        )
        logger.info(f"✅ تم تحديث لغة المستخدم {user_id} إلى {language}")
        return True
    except Exception as e:
        logger.error(f"❌ فشل تحديث اللغة: {e}")
        return False

def get_user_language(user_id: int) -> str:
    """جلب لغة المستخدم"""
    try:
        user = users_collection.find_one({'user_id': user_id})
        if user and 'language' in user:
            return user['language']
        return 'ar'
    except Exception as e:
        logger.error(f"❌ فشل جلب اللغة: {e}")
        return 'ar'

def update_user_interaction(user_id: int):
    """تحديث آخر تفاعل للمستخدم"""
    try:
        users_collection.update_one(
            {'user_id': user_id},
            {'$set': {'last_interaction': datetime.now()}}
        )
        return True
    except Exception as e:
        logger.error(f"❌ فشل تحديث التفاعل: {e}")
        return False

def is_subscribed(user_id: int) -> bool:
    """التحقق من اشتراك المستخدم"""
    try:
        user = users_collection.find_one({'user_id': user_id})
        if user and user.get('subscription_end'):
            if isinstance(user['subscription_end'], datetime):
                return user['subscription_end'] > datetime.now()
        return False
    except Exception as e:
        logger.error(f"❌ فشل التحقق من الاشتراك: {e}")
        return False

def add_subscription(user_id: int, subscription_end: datetime):
    """إضافة اشتراك للمستخدم"""
    try:
        users_collection.update_one(
            {'user_id': user_id},
            {'$set': {'subscription_end': subscription_end}}
        )
        logger.info(f"✅ تمت إضافة اشتراك للمستخدم {user_id} حتى {subscription_end}")
        return True
    except Exception as e:
        logger.error(f"❌ فشل إضافة الاشتراك: {e}")
        return False

def increment_download_count(user_id: int):
    """زيادة عداد التحميلات"""
    try:
        today = datetime.now().date()
        
        users_collection.update_one(
            {'user_id': user_id},
            {
                '$inc': {'download_count': 1},
                '$push': {
                    'daily_downloads': {
                        'date': datetime.combine(today, datetime.min.time()),
                        'count': 1
                    }
                }
            }
        )
        logger.info(f"✅ تم زيادة عداد التحميلات للمستخدم {user_id}")
        return True
    except Exception as e:
        logger.error(f"❌ فشل زيادة العداد: {e}")
        return False

def get_daily_download_count(user_id: int) -> int:
    """جلب عدد التحميلات اليومية"""
    try:
        user = users_collection.find_one({'user_id': user_id})
        if not user:
            return 0
        
        today = datetime.now().date()
        daily_downloads = user.get('daily_downloads', [])
        
        today_count = sum(
            1 for download in daily_downloads
            if isinstance(download.get('date'), datetime) and download['date'].date() == today
        )
        
        return today_count
    except Exception as e:
        logger.error(f"❌ فشل جلب العداد اليومي: {e}")
        return 0

def get_total_downloads_count() -> int:
    """جلب إجمالي التحميلات"""
    try:
        pipeline = [
            {'$group': {'_id': None, 'total': {'$sum': '$download_count'}}}
        ]
        result = list(users_collection.aggregate(pipeline))
        if result:
            return result[0]['total']
        return 0
    except Exception as e:
        logger.error(f"❌ فشل جلب الإجمالي: {e}")
        return 0

def reset_daily_downloads():
    """إعادة تعيين التحميلات اليومية (يتم تشغيله تلقائياً)"""
    try:
        yesterday = datetime.now() - timedelta(days=1)
        users_collection.update_many(
            {},
            {
                '$pull': {
                    'daily_downloads': {
                        'date': {'$lt': yesterday}
                    }
                }
            }
        )
        logger.info("✅ تم تنظيف السجلات القديمة")
        return True
    except Exception as e:
        logger.error(f"❌ فشل تنظيف السجلات: {e}")
        return False

def get_user_stats(user_id: int):
    """جلب إحصائيات المستخدم"""
    try:
        user = users_collection.find_one({'user_id': user_id})
        if not user:
            return None
        
        stats = {
            'total_downloads': user.get('download_count', 0),
            'daily_downloads': get_daily_download_count(user_id),
            'is_vip': is_subscribed(user_id),
            'join_date': user.get('join_date'),
            'subscription_end': user.get('subscription_end')
        }
        
        return stats
    except Exception as e:
        logger.error(f"❌ فشل جلب الإحصائيات: {e}")
        return None

def delete_user(user_id: int):
    """حذف مستخدم"""
    try:
        result = users_collection.delete_one({'user_id': user_id})
        if result.deleted_count > 0:
            logger.info(f"✅ تم حذف المستخدم {user_id}")
            return True
        return False
    except Exception as e:
        logger.error(f"❌ فشل حذف المستخدم: {e}")
        return False

def get_users_count() -> dict:
    """جلب عدد المستخدمين"""
    try:
        total = users_collection.count_documents({})
        vip = users_collection.count_documents({
            'subscription_end': {'$gt': datetime.now()}
        })
        
        return {
            'total': total,
            'vip': vip,
            'free': total - vip
        }
    except Exception as e:
        logger.error(f"❌ فشل جلب العدد: {e}")
        return {'total': 0, 'vip': 0, 'free': 0}

def set_logo_status(enabled: bool):
    """تفعيل/إيقاف اللوجو للجميع"""
    try:
        # حفظ الحالة في مستند خاص بالإعدادات
        db.settings.update_one(
            {'_id': 'logo_settings'},
            {'$set': {'enabled': enabled, 'updated_at': datetime.now()}},
            upsert=True
        )
        logger.info(f"✅ تم {'تفعيل' if enabled else 'إيقاف'} اللوجو")
        return True
    except Exception as e:
        logger.error(f"❌ فشل تحديث حالة اللوجو: {e}")
        return False

def is_logo_enabled() -> bool:
    """التحقق من حالة اللوجو"""
    try:
        settings = db.settings.find_one({'_id': 'logo_settings'})
        if settings:
            return settings.get('enabled', True)
        return True  # افتراضياً مفعّل
    except Exception as e:
        logger.error(f"❌ فشل جلب حالة اللوجو: {e}")
        return True