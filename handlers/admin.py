import logging
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    filters,
)
from telegram.constants import ParseMode

from utils import get_message
from database import (
    is_admin,
    get_total_users_count,
    get_total_downloads_count,
    get_all_user_ids,
    get_user_language,
    set_user_subscription,
    get_user,
    get_subscribers_count,
    get_active_users_count
)

logger = logging.getLogger(__name__)

ADMIN_MENU, BROADCAST_MESSAGE, UPGRADE_USER_ID, DOWNGRADE_USER_ID = range(4)

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    عرض لوحة تحكم المدير
    """
    user_id = update.message.from_user.id
    if not is_admin(user_id):
        await update.message.reply_text("🔒 هذا الأمر مخصص للمدير فقط.")
        return ConversationHandler.END

    lang = get_user_language(user_id)
    
    keyboard = [
        [get_message(lang, "stats_button"), get_message(lang, "broadcast_button")],
        [get_message(lang, "upgrade_user_button"), get_message(lang, "downgrade_user_button")],
        [get_message(lang, "exit_button")],
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        get_message(lang, "admin_panel_welcome"),
        reply_markup=reply_markup,
    )
    return ADMIN_MENU

async def upgrade_user_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    طلب معرف المستخدم للترقية
    """
    lang = get_user_language(update.message.from_user.id)
    await update.message.reply_text(get_message(lang, "upgrade_prompt"))
    return UPGRADE_USER_ID

async def downgrade_user_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    طلب معرف المستخدم للتخفيض
    """
    lang = get_user_language(update.message.from_user.id)
    await update.message.reply_text(get_message(lang, "downgrade_prompt"))
    return DOWNGRADE_USER_ID

async def process_user_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE, upgrade: bool) -> int:
    """
    معالجة ترقية أو تخفيض اشتراك المستخدم
    """
    admin_lang = get_user_language(update.message.from_user.id)
    
    try:
        target_user_id = int(update.message.text)
    except ValueError:
        await update.message.reply_text(get_message(admin_lang, "invalid_user_id"))
        return await admin_panel(update, context)

    target_user = get_user(target_user_id)
    if not target_user:
        await update.message.reply_text(get_message(admin_lang, "user_not_found"))
        return await admin_panel(update, context)

    new_status = "pro" if upgrade else "free"
    success = set_user_subscription(target_user_id, new_status)

    if success:
        response_key = "upgrade_success" if upgrade else "downgrade_success"
        notification_key = "upgrade_notification" if upgrade else "downgrade_notification"
        
        await update.message.reply_text(
            get_message(admin_lang, response_key).format(user_id=target_user_id)
        )
        
        # إرسال إشعار للمستخدم المستهدف
        target_lang = get_user_language(target_user_id)
        try:
            await context.bot.send_message(
                chat_id=target_user_id,
                text=get_message(target_lang, notification_key)
            )
        except Exception as e:
            logger.error(f"❌ فشل إرسال إشعار للمستخدم {target_user_id}: {e}")
            
    else:
        await update.message.reply_text(get_message(admin_lang, "generic_error"))
        
    return await admin_panel(update, context)

async def upgrade_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    ترقية مستخدم إلى VIP
    """
    return await process_user_subscription(update, context, upgrade=True)

async def downgrade_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    تخفيض مستخدم إلى Free
    """
    return await process_user_subscription(update, context, upgrade=False)

async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    عرض إحصائيات البوت المفصلة
    """
    user_id = update.message.from_user.id
    lang = get_user_language(user_id)
    
    total_users = get_total_users_count()
    total_downloads = get_total_downloads_count()
    total_subscribers = get_subscribers_count()
    active_users_7d = get_active_users_count(7)
    active_users_30d = get_active_users_count(30)
    
    stats_message = (
        f"📈 **إحصائيات البوت الشاملة**\n\n"
        f"👥 **إجمالي المستخدمين:** {total_users}\n"
        f"💎 **المشتركين (VIP):** {total_subscribers}\n"
        f"📥 **إجمالي التحميلات:** {total_downloads}\n\n"
        f"📊 **المستخدمين النشطين:**\n"
        f"   • آخر 7 أيام: {active_users_7d}\n"
        f"   • آخر 30 يوم: {active_users_30d}"
    )
    
    await update.message.reply_text(stats_message, parse_mode=ParseMode.MARKDOWN)
    return ADMIN_MENU

async def broadcast_request(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    طلب رسالة البث الجماعي
    """
    lang = get_user_language(update.message.from_user.id)
    await update.message.reply_text(get_message(lang, "broadcast_prompt"))
    return BROADCAST_MESSAGE

async def broadcast_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    إرسال رسالة جماعية لجميع المستخدمين
    """
    lang = get_user_language(update.message.from_user.id)
    message_to_broadcast = update.message.text
    all_user_ids = get_all_user_ids()
    
    await update.message.reply_text(
        get_message(lang, "broadcast_started").format(user_count=len(all_user_ids))
    )
    
    sent_count = 0
    failed_count = 0
    
    for uid in all_user_ids:
        try:
            await context.bot.send_message(chat_id=uid, text=message_to_broadcast)
            sent_count += 1
        except Exception as e:
            logger.error(f"فشل إرسال رسالة البث إلى {uid}: {e}")
            failed_count += 1
    
    await update.message.reply_text(
        get_message(lang, "broadcast_finished").format(
            sent_count=sent_count, 
            failed_count=failed_count
        )
    )
    
    return await admin_panel(update, context)

async def exit_admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    الخروج من لوحة تحكم المدير
    """
    lang = get_user_language(update.message.from_user.id)
    await update.message.reply_text(
        get_message(lang, "exit_admin_panel"), 
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END

# نقاط الدخول للمحادثة
entry_points = [
    CommandHandler("admin", admin_panel),
    MessageHandler(filters.Regex("^/admin$"), admin_panel)
]

# تحميل نصوص الأزرار
upgrade_button_ar = get_message('ar', 'upgrade_user_button')
downgrade_button_ar = get_message('ar', 'downgrade_user_button')
upgrade_button_en = get_message('en', 'upgrade_user_button')
downgrade_button_en = get_message('en', 'downgrade_user_button')
stats_button_ar = get_message('ar', 'stats_button')
broadcast_button_ar = get_message('ar', 'broadcast_button')
exit_button_ar = get_message('ar', 'exit_button')
stats_button_en = get_message('en', 'stats_button')
broadcast_button_en = get_message('en', 'broadcast_button')
exit_button_en = get_message('en', 'exit_button')

# معالج المحادثة
admin_conv_handler = ConversationHandler(
    entry_points=entry_points,
    states={
        ADMIN_MENU: [
            MessageHandler(filters.Regex(f"^({stats_button_ar}|{stats_button_en})$"), show_stats),
            MessageHandler(filters.Regex(f"^({broadcast_button_ar}|{broadcast_button_en})$"), broadcast_request),
            MessageHandler(filters.Regex(f"^({upgrade_button_ar}|{upgrade_button_en})$"), upgrade_user_prompt),
            MessageHandler(filters.Regex(f"^({downgrade_button_ar}|{downgrade_button_en})$"), downgrade_user_prompt),
        ],
        BROADCAST_MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, broadcast_message)],
        UPGRADE_USER_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, upgrade_user)],
        DOWNGRADE_USER_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, downgrade_user)],
    },
    fallbacks=[MessageHandler(filters.Regex(f"^({exit_button_ar}|{exit_button_en})$"), exit_admin_panel)],
    allow_reentry=True
)