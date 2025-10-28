import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)
from datetime import datetime, timedelta

from database import (
    get_all_users,
    get_user,
    add_subscription,
    is_admin,
    get_user_language,
    get_total_downloads_count
)
from utils import get_message, escape_markdown

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# حالات المحادثة
MAIN_MENU, AWAITING_USER_ID, AWAITING_DAYS, BROADCAST_MESSAGE = range(4)

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض لوحة التحكم الرئيسية"""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("⛔ ليس لديك صلاحيات المدير!")
        return ConversationHandler.END

    # جلب حالة اللوجو
    from database import is_logo_enabled
    logo_status = is_logo_enabled()
    logo_text = "✅ مفعّل" if logo_status else "❌ معطّل"

    keyboard = [
        [InlineKeyboardButton("📊 الإحصائيات", callback_data="admin_stats")],
        [InlineKeyboardButton("⭐ ترقية عضو", callback_data="admin_upgrade")],
        [InlineKeyboardButton(f"🎨 اللوجو ({logo_text})", callback_data="admin_logo")],
        [InlineKeyboardButton("👥 قائمة الأعضاء", callback_data="admin_list_users")],
        [InlineKeyboardButton("📢 إرسال رسالة جماعية", callback_data="admin_broadcast")],
        [InlineKeyboardButton("❌ إغلاق", callback_data="admin_close")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message_text = (
        "🔐 **لوحة تحكم المدير**\n\n"
        "اختر الإجراء المطلوب:"
    )
    
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            message_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(
            message_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    return MAIN_MENU

async def show_statistics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض الإحصائيات"""
    query = update.callback_query
    await query.answer()
    
    all_users = get_all_users()
    total_users = len(all_users)
    
    vip_users = [u for u in all_users if u.get('subscription_end')]
    total_vip = len(vip_users)
    
    total_downloads = get_total_downloads_count()
    
    stats_text = (
        "📊 **إحصائيات البوت**\n\n"
        f"👥 إجمالي المستخدمين: `{total_users}`\n"
        f"⭐ مشتركين VIP: `{total_vip}`\n"
        f"🆓 مستخدمين مجانيين: `{total_users - total_vip}`\n"
        f"📥 إجمالي التحميلات: `{total_downloads}`\n\n"
        f"📅 التاريخ: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    )
    
    keyboard = [[InlineKeyboardButton("🔙 العودة", callback_data="admin_back")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        stats_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    return MAIN_MENU

async def upgrade_user_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بدء عملية ترقية المستخدم"""
    query = update.callback_query
    await query.answer()
    
    text = (
        "⭐ ترقية عضو إلى VIP\n\n"
        "أرسل أحد التالي:\n\n"
        "1️⃣ User ID (رقم):\n"
        "   مثال: 123456789\n\n"
        "2️⃣ Username:\n"
        "   مثال: @username أو username\n\n"
        "💡 يمكنك الحصول على User ID من:\n"
        "• معلومات الحساب\n"
        "• رسائل السجل في القناة\n"
        "• أمر /account من المستخدم"
    )
    
    keyboard = [[InlineKeyboardButton("❌ إلغاء", callback_data="admin_back")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text,
        reply_markup=reply_markup
    )
    
    return AWAITING_USER_ID

async def receive_user_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """استقبال معرف المستخدم أو اليوزر نيم"""
    user_input = update.message.text.strip()
    user_id = None
    user_data = None
    
    # محاولة التعامل مع Username
    if user_input.startswith('@') or not user_input.isdigit():
        username = user_input.replace('@', '')  # إزالة @ إذا وجدت
        
        # البحث عن المستخدم بالـ username
        all_users = get_all_users()
        for user in all_users:
            if user.get('username') == username:
                user_id = user.get('user_id')
                user_data = user
                break
        
        if not user_id:
            await update.message.reply_text(
                f"❌ لم أجد مستخدم بالـ username: {username}\n\n"
                f"💡 تأكد من:\n"
                f"• اليوزر نيم صحيح\n"
                f"• المستخدم أرسل /start للبوت"
            )
            return AWAITING_USER_ID
    
    # محاولة التعامل مع User ID
    else:
        try:
            user_id = int(user_input)
            user_data = get_user(user_id)
        except ValueError:
            await update.message.reply_text(
                "❌ خطأ في الإدخال!\n\n"
                "أرسل:\n"
                "• User ID (رقم): مثال 123456789\n"
                "• أو Username: مثال @username"
            )
            return AWAITING_USER_ID
        
        if not user_data:
            await update.message.reply_text(
                "❌ المستخدم غير موجود في قاعدة البيانات!\n"
                "تأكد من أن المستخدم قام بإرسال /start للبوت."
            )
            return AWAITING_USER_ID
    
    context.user_data['upgrade_target_id'] = user_id
    
    user_name = user_data.get('full_name', 'غير معروف')
    username = user_data.get('username', 'لا يوجد')
    
    text = (
        f"✅ تم العثور على المستخدم:\n\n"
        f"👤 الاسم: {user_name}\n"
        f"🆔 المعرف: {user_id}\n"
        f"🔗 اليوزر: @{username if username != 'لا يوجد' else 'غير متوفر'}\n\n"
        f"📅 أرسل عدد الأيام للاشتراك:\n"
        f"مثال: 30 (شهر) | 365 (سنة)"
    )
    
    keyboard = [[InlineKeyboardButton("❌ إلغاء", callback_data="admin_back")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        text,
        reply_markup=reply_markup
    )
    
    return AWAITING_DAYS

async def receive_days(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """استقبال عدد الأيام وإتمام الترقية"""
    try:
        days = int(update.message.text.strip())
        if days <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ عدد أيام غير صحيح! أرسل رقم موجب.")
        return AWAITING_DAYS
    
    user_id = context.user_data.get('upgrade_target_id')
    
    if not user_id:
        await update.message.reply_text("❌ حدث خطأ! أعد المحاولة.")
        return ConversationHandler.END
    
    subscription_end = datetime.now() + timedelta(days=days)
    
    if add_subscription(user_id, subscription_end):
        user_data = get_user(user_id)
        user_name = user_data.get('full_name', 'المستخدم')
        
        success_text = (
            f"✅ تمت الترقية بنجاح!\n\n"
            f"👤 المستخدم: {user_name}\n"
            f"🆔 المعرف: {user_id}\n"
            f"📅 المدة: {days} يوم\n"
            f"⏰ تنتهي في: {subscription_end.strftime('%Y-%m-%d')}\n\n"
            f"🎉 تم إرسال إشعار للمستخدم"
        )
        
        await update.message.reply_text(success_text)
        
        # إرسال إشعار للمستخدم
        try:
            notification_text = (
                f"🎉 مبروك! تمت ترقيتك إلى VIP\n\n"
                f"⭐ مدة الاشتراك: {days} يوم\n"
                f"📅 ينتهي في: {subscription_end.strftime('%Y-%m-%d')}\n\n"
                f"✨ الآن يمكنك:\n"
                f"• تحميل بلا حدود ♾️\n"
                f"• فيديوهات بدون لوجو 🎨\n"
                f"• جودات عالية 4K/HD 📺\n"
                f"• أولوية في المعالجة ⚡\n\n"
                f"💎 شكراً لاشتراكك معنا!"
            )
            
            await context.bot.send_message(
                chat_id=user_id,
                text=notification_text
            )
            logger.info(f"✅ تم إرسال إشعار الترقية للمستخدم {user_id}")
        except Exception as e:
            logger.error(f"⚠️ فشل إرسال الإشعار للمستخدم {user_id}: {e}")
        
        del context.user_data['upgrade_target_id']
        
        keyboard = [[InlineKeyboardButton("🔙 العودة للوحة التحكم", callback_data="admin_main")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "اختر الإجراء التالي:",
            reply_markup=reply_markup
        )
        
        return MAIN_MENU
    else:
        await update.message.reply_text("❌ فشلت عملية الترقية!")
        return ConversationHandler.END

async def list_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض قائمة المستخدمين"""
    query = update.callback_query
    await query.answer()
    
    all_users = get_all_users()
    
    if not all_users:
        await query.edit_message_text("📭 لا يوجد مستخدمين حالياً")
        return MAIN_MENU
    
    users_text = "👥 قائمة المستخدمين (آخر 20)\n\n"
    
    for idx, user in enumerate(all_users[-20:], 1):
        user_id = user.get('user_id')
        name = user.get('full_name', 'غير معروف')[:20]
        username = user.get('username', 'لا يوجد')
        is_vip = "⭐" if user.get('subscription_end') else "🆓"
        
        users_text += f"{idx}. {is_vip} {user_id} - {name}\n"
    
    keyboard = [[InlineKeyboardButton("🔙 العودة", callback_data="admin_back")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        users_text,
        reply_markup=reply_markup
    )
    
    return MAIN_MENU

async def manage_logo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إدارة اللوجو - تفعيل/إيقاف"""
    query = update.callback_query
    await query.answer()
    
    from database import is_logo_enabled, set_logo_status
    
    current_status = is_logo_enabled()
    status_text = "✅ مفعّل حالياً" if current_status else "❌ معطّل حالياً"
    
    text = (
        f"🎨 إدارة اللوجو\n\n"
        f"الحالة: {status_text}\n\n"
        f"• عند التفعيل: المستخدمين المجانيين يحصلون على لوجو متحرك ✨\n"
        f"• عند الإيقاف: لا يُضاف لوجو لأي أحد ⭕\n"
        f"• VIP دائماً بدون لوجو 💎\n\n"
        f"اختر الإجراء:"
    )
    
    keyboard = [
        [InlineKeyboardButton("✅ تفعيل اللوجو", callback_data="logo_enable")],
        [InlineKeyboardButton("❌ إيقاف اللوجو", callback_data="logo_disable")],
        [InlineKeyboardButton("🔙 العودة", callback_data="admin_back")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text,
        reply_markup=reply_markup
    )
    
    return MAIN_MENU

async def toggle_logo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تبديل حالة اللوجو"""
    query = update.callback_query
    action = query.data
    
    from database import set_logo_status
    
    if action == "logo_enable":
        set_logo_status(True)
        await query.answer("✅ تم تفعيل اللوجو المتحرك!", show_alert=True)
    elif action == "logo_disable":
        set_logo_status(False)
        await query.answer("❌ تم إيقاف اللوجو!", show_alert=True)
    
    # العودة للقائمة الرئيسية
    return await admin_panel(update, context)

async def broadcast_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بدء الرسالة الجماعية"""
    query = update.callback_query
    await query.answer()
    
    text = (
        "📢 إرسال رسالة جماعية\n\n"
        "أرسل الرسالة التي تريد إرسالها لجميع المستخدمين:\n\n"
        "⚠️ تأكد من صياغة الرسالة بعناية!"
    )
    
    keyboard = [[InlineKeyboardButton("❌ إلغاء", callback_data="admin_back")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text,
        reply_markup=reply_markup
    )
    
    return BROADCAST_MESSAGE

async def send_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إرسال الرسالة الجماعية"""
    message_text = update.message.text
    all_users = get_all_users()
    
    await update.message.reply_text(
        f"📤 جاري الإرسال إلى {len(all_users)} مستخدم..."
    )
    
    success_count = 0
    failed_count = 0
    
    for user in all_users:
        try:
            await context.bot.send_message(
                chat_id=user['user_id'],
                text=message_text
            )
            success_count += 1
        except Exception as e:
            logger.error(f"فشل إرسال لـ {user['user_id']}: {e}")
            failed_count += 1
    
    result_text = (
        f"✅ تم الإرسال!\n\n"
        f"✔️ نجح: {success_count}\n"
        f"❌ فشل: {failed_count}\n"
        f"📊 الإجمالي: {len(all_users)}"
    )
    
    keyboard = [[InlineKeyboardButton("🔙 العودة", callback_data="admin_main")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        result_text,
        reply_markup=reply_markup
    )
    
    return MAIN_MENU

async def admin_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """العودة للقائمة الرئيسية"""
    return await admin_panel(update, context)

async def admin_close(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إغلاق لوحة التحكم"""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("✅ تم إغلاق لوحة التحكم")
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إلغاء المحادثة"""
    await update.message.reply_text("❌ تم الإلغاء")
    return ConversationHandler.END

# ConversationHandler للوحة التحكم
admin_conv_handler = ConversationHandler(
    entry_points=[CommandHandler('admin', admin_panel)],
    states={
        MAIN_MENU: [
            CallbackQueryHandler(show_statistics, pattern='^admin_stats$'),
            CallbackQueryHandler(upgrade_user_start, pattern='^admin_upgrade$'),
            CallbackQueryHandler(manage_logo, pattern='^admin_logo$'),
            CallbackQueryHandler(toggle_logo, pattern='^logo_(enable|disable)$'),
            CallbackQueryHandler(list_users, pattern='^admin_list_users$'),
            CallbackQueryHandler(broadcast_start, pattern='^admin_broadcast$'),
            CallbackQueryHandler(admin_back, pattern='^admin_back$'),
            CallbackQueryHandler(admin_panel, pattern='^admin_main$'),
            CallbackQueryHandler(admin_close, pattern='^admin_close$'),
        ],
        AWAITING_USER_ID: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, receive_user_id),
            CallbackQueryHandler(admin_back, pattern='^admin_back$'),
            CallbackQueryHandler(admin_back, pattern='^admin_main$'),
        ],
        AWAITING_DAYS: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, receive_days),
            CallbackQueryHandler(admin_back, pattern='^admin_back$'),
        ],
        BROADCAST_MESSAGE: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, send_broadcast),
            CallbackQueryHandler(admin_back, pattern='^admin_back$'),
        ],
    },
    fallbacks=[CommandHandler('cancel', cancel)],
)