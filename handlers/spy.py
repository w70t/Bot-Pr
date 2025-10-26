import os
import logging
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

# استيراد الوحدات
from utils import escape_markdown

# إعداد التسجيل
logger = logging.getLogger(__name__)

# --- إعدادات ---
LOG_CHANNEL_ID = os.getenv("LOG_CHANNEL_ID")

async def spy_on_messages(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    يلتقط أي رسالة نصية غير معالجة ويرسلها إلى قناة السجلات.
    """
    if not LOG_CHANNEL_ID or not update.message or not update.message.text:
        return

    user = update.effective_user
    user_id = user.id
    user_mention = f"[{escape_markdown(user.full_name)}](tg://user?id={user_id})"
    message_text = escape_markdown(update.message.text)

    # لا نرسل الأوامر إلى قناة الجاسوس
    if message_text.startswith('/'):
        return

    message = (
        f"🕵️‍♂️ **رسالة مرصودة**\n\n"
        f"👤 **من المستخدم:** {user_mention}\n"
        f"🆔 **ID:** `{user_id}`\n\n"
        f"💬 **نص الرسالة:**\n`{message_text}`"
    )

    try:
        await context.bot.send_message(chat_id=LOG_CHANNEL_ID, text=message, parse_mode=ParseMode.MARKDOWN_V2)
    except Exception as e:
        logger.error(f"فشل في إرسال رسالة الجاسوس إلى قناة السجلات: {e}")

