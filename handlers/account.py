from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from datetime import datetime

from database import get_user, is_admin, get_user_language, is_subscribed
from utils import get_message

FREE_USER_DOWNLOAD_LIMIT = 5

async def account_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    عرض معلومات حساب المستخدم بشكل تفصيلي وجميل
    """
    user_id = update.message.from_user.id
    lang = get_user_language(user_id)
    user_data = get_user(user_id)

    if not user_data:
        await update.message.reply_text(get_message(lang, "error_finding_user"))
        return

    # جلب البيانات
    download_count = user_data.get("daily_download_count", 0)
    subscription_status = user_data.get("subscription_status", "free")
    subscription_expiry = user_data.get("subscription_expiry")
    
    # تحديد الحالة
    if is_admin(user_id):
        remaining_downloads = "∞ (مدير)"
        sub_status_translated = "👑 مدير البوت"
        subscription_details = (
            "🔑 **صلاحيات المدير:**\n"
            "• ♾️ تحميلات غير محدودة\n"
            "• 🎨 بدون لوجو\n"
            "• ⚙️ الوصول للوحة التحكم\n"
            "• 👥 إدارة المستخدمين\n"
            "• 📊 عرض الإحصائيات"
        )
    elif is_subscribed(user_id):
        remaining_downloads = "∞"
        sub_status_translated = get_message(lang, "sub_pro")
        
        # تنسيق تاريخ انتهاء الاشتراك
        expiry_date_str = "غير محدد"
        if subscription_expiry:
            try:
                expiry_date_str = subscription_expiry.strftime("%Y-%m-%d")
            except:
                expiry_date_str = str(subscription_expiry)
        
        subscription_details = get_message(lang, "account_pro_details").format(
            expiry_date=expiry_date_str
        )
    else:
        remaining_downloads = max(0, FREE_USER_DOWNLOAD_LIMIT - download_count)
        sub_status_translated = get_message(lang, "sub_free")
        subscription_details = get_message(lang, "account_free_details")

    # رسالة معلومات الحساب
    account_message = get_message(lang, "account_info").format(
        user_id=user_id,
        subscription_status=sub_status_translated,
        downloads_used=download_count,
        downloads_remaining=remaining_downloads,
        subscription_details=subscription_details
    )

    await update.message.reply_text(account_message, parse_mode=ParseMode.MARKDOWN)

async def test_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    اختبار حالة الاشتراك (للمدراء فقط)
    """
    user_id = update.message.from_user.id
    lang = get_user_language(user_id)

    if not is_admin(user_id):
        await update.message.reply_text(get_message(lang, "admin_only_command"))
        return

    # جلب معلومات المستخدم
    user_data = get_user(user_id)
    
    if not user_data:
        await update.message.reply_text("❌ لم يتم العثور على بياناتك!")
        return
    
    subscription_status = user_data.get("subscription_status", "free")
    subscription_expiry = user_data.get("subscription_expiry")
    is_sub = is_subscribed(user_id)
    
    test_message = (
        "🧪 **اختبار حالة الاشتراك**\n\n"
        f"🆔 **User ID:** `{user_id}`\n"
        f"💎 **الحالة في DB:** `{subscription_status}`\n"
        f"📅 **تاريخ الانتهاء:** `{subscription_expiry}`\n"
        f"✅ **is_subscribed():** `{is_sub}`\n\n"
        f"{'✔️ الاشتراك نشط' if is_sub else '❌ الاشتراك غير نشط'}"
    )
    
    await update.message.reply_text(test_message, parse_mode=ParseMode.MARKDOWN)