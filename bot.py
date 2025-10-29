import os
import logging

from dotenv import load_dotenv
load_dotenv()

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)

# استيراد المكونات - مصحح
from handlers.start import (
    start, 
    select_language,
    handle_back_button,
    handle_download_button,
    handle_help_button,
    handle_settings_button
)
from handlers.download import handle_download, handle_quality_selection, handle_use_bonus_callback
from handlers.admin import admin_conv_handler
from handlers.account import show_account_info
from handlers.referral import referral_callback_handler, show_referral_menu
from handlers.subscription import show_subscription_menu
from handlers.video_info import handle_video_message
from utils import get_message, escape_markdown, get_config, load_config, setup_bot_menu
from database import init_db, update_user_interaction

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", 
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("RAILWAY_PUBLIC_DOMAIN")
PORT = int(os.getenv("PORT", 8443))
LOG_CHANNEL_ID = os.getenv("LOG_CHANNEL_ID")

async def forward_to_log_channel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """إعادة توجيه الرسائل إلى قناة اللوج"""
    if not LOG_CHANNEL_ID:
        return

    user = update.message.from_user
    
    escaped_full_name = escape_markdown(user.full_name)
    username_part = f"@{user.username}" if user.username else "لا يوجد"
    
    user_info = (
        f"📩 رسالة جديدة\n\n"
        f"👤 من: {escaped_full_name}\n"
        f"🆔 ID: `{user.id}`\n"
        f"🔗 Username: {username_part}\n\n"
        f"💬 الرسالة:\n{escape_markdown(update.message.text or 'رسالة فارغة')}"
    )
    
    try:
        await context.bot.send_message(
            chat_id=LOG_CHANNEL_ID,
            text=user_info,
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"❌ فشل إرسال الرسالة لقناة اللوج: {e}")

async def track_user_activity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تتبع نشاط المستخدم"""
    if update.effective_user:
        update_user_interaction(update.effective_user.id)

def main():
    """تشغيل البوت"""
    
    # التحقق من توفر التوكن
    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN غير موجود في متغيرات البيئة!")
        return
    
    # تهيئة قاعدة البيانات
    if not init_db():
        logger.error("❌ فشل الاتصال بقاعدة البيانات!")
        return
    
    # تحميل الإعدادات
    if not load_config():
        logger.error("❌ فشل تحميل ملف الإعدادات!")
        return
    
    # إنشاء التطبيق
    application = Application.builder().token(BOT_TOKEN).build()
    
    # تسجيل المعالجات
    logger.info("🔧 جاري تسجيل المعالجات...")
    
    # معالج /start
    application.add_handler(CommandHandler("start", start))
    
    # معالج اختيار اللغة
    application.add_handler(CallbackQueryHandler(select_language, pattern='^lang_'))
    
    # معالج القائمة الرئيسية والأزرار
    application.add_handler(CallbackQueryHandler(handle_back_button, pattern='^main_menu$'))
    application.add_handler(CallbackQueryHandler(handle_download_button, pattern='^download_video$'))
    application.add_handler(CallbackQueryHandler(handle_help_button, pattern='^help_menu$'))
    application.add_handler(CallbackQueryHandler(handle_settings_button, pattern='^settings_menu$'))
    application.add_handler(CallbackQueryHandler(select_language, pattern='^change_language$'))
    
    # معالج الحساب
    application.add_handler(CallbackQueryHandler(show_account_info, pattern='^account_menu$'))
    
    # معالج الإحالة
    application.add_handler(CallbackQueryHandler(show_referral_menu, pattern='^referral_menu$'))
    application.add_handler(CallbackQueryHandler(
        referral_callback_handler,
        pattern='^(ref_friends_list|ref_achievements)$'
    ))
    
    # معالج الاشتراك
    application.add_handler(CallbackQueryHandler(show_subscription_menu, pattern='^subscription_menu$'))
    
    # معالج اختيار الجودة
    application.add_handler(CallbackQueryHandler(handle_quality_selection, pattern='^quality_'))
    
    # معالج زر استخدام البونص
    application.add_handler(CallbackQueryHandler(handle_use_bonus_callback, pattern='^use_bonus$'))
    
    # معالج لوحة الأدمن
    application.add_handler(admin_conv_handler)
    
    # معالج الرسائل النصية (الروابط)
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.Regex(r'http[s]?://'),
        handle_download
    ))
    
    # معالج الفيديوهات
    application.add_handler(MessageHandler(filters.VIDEO, handle_video_message))
    
    # معالج تتبع النشاط
    application.add_handler(MessageHandler(filters.ALL, track_user_activity), group=1)
    
    logger.info("✅ تم تسجيل جميع المعالجات بنجاح.")
    
    # إعداد قائمة البوت
    try:
        import asyncio
        asyncio.get_event_loop().run_until_complete(setup_bot_menu(application.bot))
        logger.info("✅ تم إعداد قائمة البوت.")
    except Exception as e:
        logger.warning(f"⚠️ فشل إعداد قائمة البوت: {e}")
    
    # تشغيل البوت
    if WEBHOOK_URL:
        logger.info(f"🌐 تشغيل البوت باستخدام Webhook على {WEBHOOK_URL}")
        application.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path=BOT_TOKEN,
            webhook_url=f"{WEBHOOK_URL}/{BOT_TOKEN}"
        )
    else:
        logger.info("🚀 تشغيل البوت باستخدام Polling...")
        application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()