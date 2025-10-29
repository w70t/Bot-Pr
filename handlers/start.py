import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from database import (
    add_user,
    get_user,
    update_user_language,
    get_user_language,
    register_referral
)

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج أمر /start"""
    user = update.message.from_user
    user_id = user.id
    username = user.username or "user"
    full_name = user.full_name or "User"
    
    # استخراج كود الإحالة
    referral_code = None
    if context.args and len(context.args) > 0:
        referral_code = context.args[0]
    
    # التحقق من وجود المستخدم
    existing_user = get_user(user_id)
    
    if not existing_user:
        # مستخدم جديد
        add_user(user_id, username, full_name)
        logger.info(f"✅ مستخدم جديد: {user_id} - @{username}")
        
        # تسجيل الإحالة
        if referral_code:
            success, message = register_referral(user_id, referral_code)
            if success:
                logger.info(f"✅ تم تسجيل إحالة: {user_id} بواسطة {referral_code}")
        
        # عرض اختيار اللغة
        await show_language_selection(update, context)
        return
    
    # مستخدم موجود
    lang = get_user_language(user_id)
    await show_main_menu(update, context, lang, is_start=True)

async def show_language_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض خيارات اللغة"""
    keyboard = [
        [
            InlineKeyboardButton("🇸🇦 العربية", callback_data='lang_ar'),
            InlineKeyboardButton("🇬🇧 English", callback_data='lang_en'),
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_text = (
        "👋 Welcome! أهلاً وسهلاً\n\n"
        "Please choose your language:\n"
        "الرجاء اختيار لغتك:"
    )
    
    if update.callback_query:
        await update.callback_query.edit_message_text(
            welcome_text,
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(
            welcome_text,
            reply_markup=reply_markup
        )

async def select_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج اختيار اللغة"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    # التحقق من نوع الـ callback
    if query.data == 'change_language':
        # من الإعدادات - عرض خيارات اللغة
        await show_language_selection(update, context)
        return
    
    # اختيار اللغة
    lang = query.data.split('_')[1]  # ar or en
    
    # حفظ اللغة
    update_user_language(user_id, lang)
    
    # عرض القائمة الرئيسية
    await show_main_menu(update, context, lang)

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, lang: str = 'ar', is_start: bool = False):
    """عرض القائمة الرئيسية"""
    
    if lang == 'ar':
        keyboard = [
            [InlineKeyboardButton("📥 تحميل فيديو 📹", callback_data='download_video')],
            [InlineKeyboardButton("👤 حسابي", callback_data='account_menu')],
            [
                InlineKeyboardButton("👥 دعوة صديق", callback_data='referral_menu'),
                InlineKeyboardButton("💎 اشترك في VIP ⭐", callback_data='subscription_menu'),
            ],
            [
                InlineKeyboardButton("❓ المساعدة", callback_data='help_menu'),
                InlineKeyboardButton("⚙️ الإعدادات", callback_data='settings_menu'),
            ],
        ]
        
        text = (
            "🎬 مرحباً بك في بوت تحميل الفيديوهات!\n\n"
            "📌 يمكنك تحميل من:\n"
            "• يوتيوب YouTube\n"
            "• فيسبوك Facebook\n"
            "• إنستغرام Instagram\n"
            "• تيك توك TikTok\n"
            "• تويتر Twitter\n"
            "• +1000 موقع آخر\n\n"
            "🎯 اختر ما تريد من القائمة:"
        )
    else:
        keyboard = [
            [InlineKeyboardButton("📥 Download Video 📹", callback_data='download_video')],
            [InlineKeyboardButton("👤 My Account", callback_data='account_menu')],
            [
                InlineKeyboardButton("👥 Invite Friend", callback_data='referral_menu'),
                InlineKeyboardButton("💎 Subscribe VIP ⭐", callback_data='subscription_menu'),
            ],
            [
                InlineKeyboardButton("❓ Help", callback_data='help_menu'),
                InlineKeyboardButton("⚙️ Settings", callback_data='settings_menu'),
            ],
        ]
        
        text = (
            "🎬 Welcome to Video Download Bot!\n\n"
            "📌 Download from:\n"
            "• YouTube\n"
            "• Facebook\n"
            "• Instagram\n"
            "• TikTok\n"
            "• Twitter\n"
            "• +1000 other sites\n\n"
            "🎯 Choose from the menu:"
        )
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            text,
            reply_markup=reply_markup
        )
    elif is_start:
        await update.message.reply_text(
            text,
            reply_markup=reply_markup
        )

async def handle_back_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """العودة للقائمة الرئيسية"""
    query = update.callback_query
    user_id = query.from_user.id
    lang = get_user_language(user_id)
    
    await show_main_menu(update, context, lang)

async def handle_download_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """زر التحميل"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    lang = get_user_language(user_id)
    
    if lang == 'ar':
        text = (
            "📥 تحميل فيديو\n\n"
            "أرسل رابط الفيديو الذي تريد تحميله:\n\n"
            "✅ يوتيوب\n"
            "✅ فيسبوك\n"
            "✅ إنستغرام\n"
            "✅ تيك توك\n"
            "✅ تويتر\n"
            "✅ المزيد...\n\n"
            "مثال:\n"
            "https://youtube.com/watch?v=xxxxx"
        )
        back_text = "🔙 العودة"
    else:
        text = (
            "📥 Download Video\n\n"
            "Send the video link:\n\n"
            "✅ YouTube\n"
            "✅ Facebook\n"
            "✅ Instagram\n"
            "✅ TikTok\n"
            "✅ Twitter\n"
            "✅ More...\n\n"
            "Example:\n"
            "https://youtube.com/watch?v=xxxxx"
        )
        back_text = "🔙 Back"
    
    keyboard = [[InlineKeyboardButton(back_text, callback_data='main_menu')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, reply_markup=reply_markup)

async def handle_help_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """زر المساعدة"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    lang = get_user_language(user_id)
    
    if lang == 'ar':
        text = (
            "❓ المساعدة\n\n"
            "🎬 كيفية الاستخدام:\n"
            "1️⃣ أرسل رابط الفيديو\n"
            "2️⃣ اختر الجودة المطلوبة\n"
            "3️⃣ انتظر التحميل\n"
            "4️⃣ استمتع بالفيديو!\n\n"
            "📊 الحد اليومي:\n"
            "• مجاناً: 5 فيديوهات/يوم\n"
            "• VIP: غير محدود ✨\n\n"
            "👥 نظام الإحالة:\n"
            "• ادعو أصدقائك\n"
            "• احصل على +10 تحميلات لكل صديق\n"
            "• 100 إحالة = VIP مدى الحياة! 🏆\n\n"
            "💎 اشترك في VIP:\n"
            "• تواصل مع: @7kmmy"
        )
        back_text = "🔙 العودة"
    else:
        text = (
            "❓ Help\n\n"
            "🎬 How to use:\n"
            "1️⃣ Send video link\n"
            "2️⃣ Choose quality\n"
            "3️⃣ Wait for download\n"
            "4️⃣ Enjoy!\n\n"
            "📊 Daily limit:\n"
            "• Free: 5 videos/day\n"
            "• VIP: Unlimited ✨\n\n"
            "👥 Referral system:\n"
            "• Invite friends\n"
            "• +10 downloads per friend\n"
            "• 100 referrals = Lifetime VIP! 🏆\n\n"
            "💎 Subscribe VIP:\n"
            "• Contact: @7kmmy"
        )
        back_text = "🔙 Back"
    
    keyboard = [[InlineKeyboardButton(back_text, callback_data='main_menu')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, reply_markup=reply_markup)

async def handle_settings_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """زر الإعدادات"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    lang = get_user_language(user_id)
    
    if lang == 'ar':
        text = "⚙️ الإعدادات\n\nاختر الإعداد:"
        keyboard = [
            [InlineKeyboardButton("🌐 تغيير اللغة", callback_data='change_language')],
            [InlineKeyboardButton("🔙 العودة", callback_data='main_menu')],
        ]
    else:
        text = "⚙️ Settings\n\nChoose setting:"
        keyboard = [
            [InlineKeyboardButton("🌐 Change Language", callback_data='change_language')],
            [InlineKeyboardButton("🔙 Back", callback_data='main_menu')],
        ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup)