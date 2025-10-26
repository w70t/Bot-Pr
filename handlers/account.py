from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from database import get_user, is_admin, get_user_language
from utils import get_message

# تعريف المتغير هنا ليكون متاحًا في كل الدوال
FREE_USER_DOWNLOAD_LIMIT = 5

async def account_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    
    lang = get_user_language(user_id)
    user_data = get_user(user_id)

    if not user_data:
        await update.message.reply_text(get_message(lang, "error_finding_user"))
        return

    download_count = user_data.get("download_count", 0)
    subscription_status = user_data.get("subscription_status", "free")
    
    # --- ✨ التصحيح هنا: إزالة await ✨ ---
    if is_admin(user_id):
        remaining_downloads = "∞"
    else:
        remaining_downloads = max(0, FREE_USER_DOWNLOAD_LIMIT - download_count)

    if subscription_status == "free":
        sub_status_translated = get_message(lang, "sub_free")
    else:
        sub_status_translated = get_message(lang, "sub_pro")

    account_message = get_message(lang, "account_info").format(
        user_id=user_id,
        subscription_status=sub_status_translated,
        downloads_used=download_count,
        downloads_remaining=remaining_downloads
    )

    await update.message.reply_text(account_message, parse_mode=ParseMode.MARKDOWN)

async def test_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    lang = get_user_language(user_id)

    # --- ✨ التصحيح هنا: إزالة await ✨ ---
    if not is_admin(user_id):
        await update.message.reply_text(get_message(lang, "admin_only_command"))
        return

    await update.message.reply_text("هذه الميزة قيد التطوير. (مخصصة للمدير فقط)")
