import os
import logging
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

# --- استيراد المكونات الأخرى ---
from handlers.start import start, select_language
from handlers.download import handle_download
from handlers.admin import admin_conv_handler
from handlers.account import account_info, test_subscription
from handlers.video_info import handle_video_message
from utils import get_message, escape_markdown, get_config, load_config
from database import init_db

# --- إعدادات أساسية ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
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
    
    # تهريب اسم المستخدم لـ MarkdownV2
    escaped_full_name = escape_markdown(user.full_name)
    username_part = f"@{user.username}" if user.username else "لا يوجد"
    
    user_info = (
        f"👤 **رسالة من:** {escaped_full_name}\n"
        f"🆔 **ID:** `{user.id}`\n"
        f"🔗 **Username:** {username_part}"
    )

    try:
        await context.bot.send_message(
            chat_id=LOG_CHANNEL_ID,
            text=user_info,
            parse_mode='MarkdownV2'
        )
        await context.bot.forward_message(
            chat_id=LOG_CHANNEL_ID,
            from_chat_id=update.message.chat_id,
            message_id=update.message.message_id
        )
    except Exception as e:
        logger.error(f"❌ فشل إعادة توجيه الرسالة إلى القناة {LOG_CHANNEL_ID}: {e}")

def main() -> None:
    """تشغيل البوت الرئيسي"""
    # تحميل الإعدادات
    load_config()
    config = get_config()
    
    # التحقق من قاعدة البيانات
    if not init_db():
        logger.critical("!!! فشل الاتصال بقاعدة البيانات.")
        return

    # إنشاء تطبيق البوت مرة واحدة فقط
    application = Application.builder().token(BOT_TOKEN).build()
    
    # تخزين الإعدادات في bot_data
    application.bot_data["config"] = config

    # تسجيل handler لإعادة توجيه الرسائل (يعمل قبل باقي الـ handlers)
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, forward_to_log_channel),
        group=-1
    )

    # تسجيل الـ handlers الرئيسية
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("account", account_info))
    application.add_handler(CommandHandler("testsub", test_subscription))
    
    # Handler للتعرف على الفيديوهات المرسلة
    application.add_handler(MessageHandler(filters.VIDEO, handle_video_message))
    
    # Handler لاختيار اللغة
    application.add_handler(MessageHandler(filters.Regex("^(English|العربية)$"), select_language))
    
    # Handler للوحة تحكم الأدمن
    application.add_handler(admin_conv_handler)
    
    # Handler لتحميل الفيديوهات من الروابط
    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND & filters.Regex(r"https?://\S+"),
            handle_download,
        )
    )
    
    logger.info("✅ تم تسجيل جميع المعالجات بنجاح.")

    # تشغيل البوت
    if WEBHOOK_URL:
        logger.info(f"🚀 بدء تشغيل البوت مع Webhook على البورت: {PORT}")
        logger.info(f"🔗 Webhook URL: https://{WEBHOOK_URL}/{BOT_TOKEN}")
        application.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path=BOT_TOKEN,
            webhook_url=f"https://{WEBHOOK_URL}/{BOT_TOKEN}"
        )
    else:
        logger.info("🔄 بدء تشغيل البوت في وضع الاستقصاء (Polling)...")
        application.run_polling()

if __name__ == "__main__":
    main()