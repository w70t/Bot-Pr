"""
⚠️ نسخة اختبارية بدون MongoDB
تستخدم ملف JSON بسيط
"""
import os
import json
import random
import string
import logging
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ملف JSON للتخزين المؤقت
DB_FILE = "temp_database.json"

def load_db():
    """تحميل قاعدة البيانات من الملف"""
    if os.path.exists(DB_FILE):
        with open(DB_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"users": {}, "config": {}}

def save_db(data):
    """حفظ قاعدة البيانات في الملف"""
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)

db = load_db()

def init_db():
    """تهيئة قاعدة البيانات"""
    try:
        logger.info("✅ قاعدة البيانات المؤقتة جاهزة (JSON)")
        return True
    except Exception as e:
        logger.error(f"❌ خطأ: {e}")
        return False

def generate_referral_code():
    """توليد كود إحالة فريد"""
    while True:
        code = 'REF' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        if code not in [u.get('referral_code') for u in db['users'].values()]:
            return code

def add_user(user_id: int, username: str, full_name: str):
    """إضافة مستخدم جديد"""
    try:
        user_id_str = str(user_id)
        if user_id_str in db['users']:
            return True
        
        referral_code = generate_referral_code()
        
        db['users'][user_id_str] = {
            "user_id": user_id,
            "username": username,
            "full_name": full_name,
            "referral_code": referral_code,
            "language": "ar",
            "registration_date": datetime.now().isoformat(),
            "download_count": 0,
            "daily_downloads": {},
            "subscription_end": None,
            "is_lifetime_vip": False,
            "referred_by": None,
            "referrals": [],
            "successful_referrals": 0,
            "bonus_downloads": 50,
            "achievements": {}
        }
        
        save_db(db)
        logger.info(f"✅ تم إضافة المستخدم: {user_id}")
        return True
    except Exception as e:
        logger.error(f"❌ خطأ في إضافة المستخدم: {e}")
        return False

def get_user(user_id: int):
    """الحصول على بيانات المستخدم"""
    user = db['users'].get(str(user_id))
    if user and 'registration_date' in user and isinstance(user['registration_date'], str):
        user['registration_date'] = datetime.fromisoformat(user['registration_date'])
    if user and 'subscription_end' in user and isinstance(user['subscription_end'], str):
        user['subscription_end'] = datetime.fromisoformat(user['subscription_end'])
    return user

def get_all_users():
    """الحصول على جميع المستخدمين"""
    return list(db['users'].values())

def update_user_language(user_id: int, language: str):
    """تحديث لغة المستخدم"""
    try:
        user_id_str = str(user_id)
        if user_id_str in db['users']:
            db['users'][user_id_str]['language'] = language
            save_db(db)
        return True
    except Exception as e:
        logger.error(f"❌ خطأ: {e}")
        return False

def get_user_language(user_id: int):
    """الحصول على لغة المستخدم"""
    user = get_user(user_id)
    return user.get('language', 'ar') if user else 'ar'

def register_referral(user_id: int, referral_code: str):
    """تسجيل إحالة جديدة"""
    try:
        referrer = None
        for u in db['users'].values():
            if u.get('referral_code') == referral_code:
                referrer = u
                break
        
        if not referrer:
            return False, "كود إحالة غير صحيح"
        
        referrer_id = referrer['user_id']
        
        if referrer_id == user_id:
            return False, "لا يمكنك استخدام كود الإحالة الخاص بك"
        
        db['users'][str(user_id)]['referred_by'] = referrer_id
        db['users'][str(referrer_id)]['referrals'].append(user_id)
        save_db(db)
        
        return True, "تم تسجيل الإحالة بنجاح"
    except Exception as e:
        logger.error(f"❌ خطأ: {e}")
        return False, str(e)

def increment_download_count(user_id: int):
    """زيادة عداد التحميل"""
    try:
        user_id_str = str(user_id)
        today = datetime.now().strftime('%Y-%m-%d')
        
        if user_id_str in db['users']:
            db['users'][user_id_str]['download_count'] += 1
            
            if today not in db['users'][user_id_str]['daily_downloads']:
                db['users'][user_id_str]['daily_downloads'][today] = 0
            db['users'][user_id_str]['daily_downloads'][today] += 1
            
            if db['users'][user_id_str]['download_count'] == 10:
                referred_by = db['users'][user_id_str].get('referred_by')
                if referred_by and str(referred_by) in db['users']:
                    db['users'][str(referred_by)]['bonus_downloads'] += 10
                    db['users'][str(referred_by)]['successful_referrals'] += 1
            
            save_db(db)
        
        return True
    except Exception as e:
        logger.error(f"❌ خطأ: {e}")
        return False

def get_daily_download_count(user_id: int):
    """عدد التحميلات اليومية"""
    user = get_user(user_id)
    if not user:
        return 0
    
    today = datetime.now().strftime('%Y-%m-%d')
    return user.get('daily_downloads', {}).get(today, 0)

def get_bonus_downloads(user_id: int):
    """الحصول على التحميلات الإضافية"""
    user = get_user(user_id)
    return user.get('bonus_downloads', 0) if user else 0

def use_bonus_download(user_id: int):
    """استخدام تحميل من الرصيد الاحتياطي"""
    try:
        user_id_str = str(user_id)
        if user_id_str in db['users'] and db['users'][user_id_str].get('bonus_downloads', 0) > 0:
            db['users'][user_id_str]['bonus_downloads'] -= 1
            save_db(db)
            return True
        return False
    except Exception as e:
        logger.error(f"❌ خطأ: {e}")
        return False

def is_subscribed(user_id: int):
    """التحقق من اشتراك VIP"""
    user = get_user(user_id)
    if not user:
        return False
    
    if user.get('is_lifetime_vip'):
        return True
    
    subscription_end = user.get('subscription_end')
    if subscription_end and subscription_end > datetime.now():
        return True
    
    return False

def add_subscription(user_id: int, days: int):
    """إضافة اشتراك VIP"""
    try:
        user_id_str = str(user_id)
        if user_id_str not in db['users']:
            return False
        
        current_end = db['users'][user_id_str].get('subscription_end')
        
        if current_end and isinstance(current_end, str):
            current_end = datetime.fromisoformat(current_end)
        
        if current_end and current_end > datetime.now():
            new_end = current_end + timedelta(days=days)
        else:
            new_end = datetime.now() + timedelta(days=days)
        
        db['users'][user_id_str]['subscription_end'] = new_end.isoformat()
        save_db(db)
        
        return True
    except Exception as e:
        logger.error(f"❌ خطأ: {e}")
        return False

def set_lifetime_vip(user_id: int):
    """تعيين VIP مدى الحياة"""
    try:
        user_id_str = str(user_id)
        if user_id_str in db['users']:
            db['users'][user_id_str]['is_lifetime_vip'] = True
            save_db(db)
        return True
    except Exception as e:
        logger.error(f"❌ خطأ: {e}")
        return False

def is_admin(user_id: int):
    """التحقق من صلاحيات الأدمن"""
    admin_ids = os.getenv("ADMIN_IDS", "").split(",")
    return str(user_id) in admin_ids

def get_total_downloads_count():
    """إجمالي التحميلات"""
    total = sum(u.get('download_count', 0) for u in db['users'].values())
    return total

def get_users_count():
    """عدد المستخدمين"""
    total = len(db['users'])
    vip = sum(1 for u in db['users'].values() if u.get('subscription_end'))
    lifetime_vip = sum(1 for u in db['users'].values() if u.get('is_lifetime_vip'))
    free = total - vip - lifetime_vip
    
    return {
        "total": total,
        "vip": vip,
        "lifetime_vip": lifetime_vip,
        "free": free
    }

def get_referral_statistics():
    """إحصائيات الإحالات"""
    total_successful_referrals = sum(u.get('successful_referrals', 0) for u in db['users'].values())
    total_bonus_downloads = sum(u.get('bonus_downloads', 0) for u in db['users'].values())
    lifetime_vip_count = sum(1 for u in db['users'].values() if u.get('is_lifetime_vip'))
    
    return {
        'total_successful_referrals': total_successful_referrals,
        'total_bonus_downloads': total_bonus_downloads,
        'lifetime_vip_count': lifetime_vip_count
    }

def get_top_referrers(limit: int = 20):
    """أكثر المحيلين"""
    users = [u for u in db['users'].values() if u.get('successful_referrals', 0) > 0]
    users.sort(key=lambda x: x.get('successful_referrals', 0), reverse=True)
    return users[:limit]

def is_logo_enabled():
    """حالة اللوجو"""
    return db['config'].get('logo_enabled', True)

def set_logo_status(enabled: bool):
    """تفعيل/تعطيل اللوجو"""
    try:
        db['config']['logo_enabled'] = enabled
        save_db(db)
        return True
    except Exception as e:
        logger.error(f"❌ خطأ: {e}")
        return False

def update_user_interaction(user_id: int):
    """تحديث آخر تفاعل"""
    try:
        user_id_str = str(user_id)
        if user_id_str in db['users']:
            db['users'][user_id_str]['last_interaction'] = datetime.now().isoformat()
            save_db(db)
    except Exception as e:
        logger.error(f"❌ خطأ: {e}")

def get_user_by_referral_code(referral_code: str):
    """الحصول على المستخدم من كود الإحالة"""
    for user in db['users'].values():
        if user.get('referral_code') == referral_code:
            return user
    return None

def check_referral_achievements(user_id: int):
    """التحقق من إنجازات الإحالة"""
    # وظيفة بسيطة للنسخة المؤقتة
    pass

# تهيئة عند الاستيراد
init_db()
logger.info("⚠️ تستخدم قاعدة بيانات JSON مؤقتة - ليست للإنتاج!")