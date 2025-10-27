from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, KeyboardButton
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from database import add_user, update_user_language, update_user_interaction, get_user_language
from utils import get_message

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    معالج أمر /start - يعرض اختيار اللغة وأزرار القائمة
    """
    user = update.message.from_user
    add_user(user.id, user.username, user.full_name)
    update_user_interaction(user.id)

    keyboard = [["العربية 🇸🇦", "English 🇬🇧"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    
    welcome_text = (
        "🎉 **مرحباً! Welcome!** 🎉\n\n"
        "🌍 **اختر لغتك | Choose your language:**"
    )
    
    await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='Markdown')

async def select_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    معالج اختيار اللغة - يعرض القائمة الرئيسية
    """
    user = update.message.from_user
    user_id = user.id
    lang_choice = update.message.text
    
    # تحديد اللغة
    if "English" in lang_choice or "🇬🇧" in lang_choice:
        lang_code = "en"
    else:
        lang_code = "ar"

    update_user_language(user_id, lang_code)
    
    # الرسالة الترحيبية
    welcome_message = get_message(lang_code, "welcome").format(name=user.first_name)
    
    # إنشاء لوحة المفاتيح الرئيسية
    keyboard = create_main_keyboard(lang_code)
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        welcome_message,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

def create_main_keyboard(lang_code: str):
    """
    إنشاء لوحة المفاتيح الرئيسية حسب اللغة
    """
    if lang_code == "ar":
        keyboard = [
            ["📥 تحميل فيديو", "👤 حسابي"],
            ["❓ المساعدة", "⭐ الاشتراك VIP"],
            ["🌐 تغيير اللغة"]
        ]
    else:
        keyboard = [
            ["📥 Download Video", "👤 My Account"],
            ["❓ Help", "⭐ Subscribe VIP"],
            ["🌐 Change Language"]
        ]
    
    return keyboard

async def handle_menu_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    معالج أزرار القائمة الرئيسية
    """
    user_id = update.message.from_user.id
    text = update.message.text
    lang = get_user_language(user_id)
    
    # استيراد محلي لتجنب الاستيراد الدائري
    from handlers.account import account_info
    
    # تحديث آخر تفاعل
    update_user_interaction(user_id)
    
    if text in ["📥 تحميل فيديو", "📥 Download Video"]:
        message = (
            "🎬 **أرسل رابط الفيديو الآن!**\n\n"
            "✅ **المنصات المدعومة:**\n"
            "• YouTube\n"
            "• Instagram\n"
            "• Facebook\n"
            "• TikTok\n"
            "• Twitter\n"
            "• وأكثر من 1000+ موقع!"
        ) if lang == "ar" else (
            "🎬 **Send video link now!**\n\n"
            "✅ **Supported platforms:**\n"
            "• YouTube\n"
            "• Instagram\n"
            "• Facebook\n"
            "• TikTok\n"
            "• Twitter\n"
            "• And 1000+ more sites!"
        )
        await update.message.reply_text(message, parse_mode='Markdown')
    
    elif text in ["👤 حسابي", "👤 My Account"]:
        await account_info(update, context)
    
    elif text in ["❓ المساعدة", "❓ Help"]:
        help_text = get_message(lang, "help_message")
        await update.message.reply_text(help_text, parse_mode='Markdown')
    
    elif text in ["⭐ الاشتراك VIP", "⭐ Subscribe VIP"]:
        subscribe_message = (
            "👑 **باقة VIP المميزة!**\n\n"
            "✨ **المميزات:**\n"
            "♾️ تحميلات غير محدودة\n"
            "⏱️ فيديوهات بأي طول\n"
            "🎨 بدون لوجو\n"
            "📺 جودات عالية 4K/HD\n"
            "⚡ أولوية في المعالجة\n"
            "🎵 تحميل صوتي MP3\n\n"
            "💰 **السعر:** 2$ شهرياً\n\n"
            "📞 **للاشتراك، تواصل مع:** @YourAdminUsername"
        ) if lang == "ar" else (
            "👑 **VIP Premium Plan!**\n\n"
            "✨ **Features:**\n"
            "♾️ Unlimited downloads\n"
            "⏱️ Any video length\n"
            "🎨 No watermark\n"
            "📺 High quality 4K/HD\n"
            "⚡ Priority processing\n"
            "🎵 Audio download MP3\n\n"
            "💰 **Price:** $2 monthly\n\n"
            "📞 **To subscribe, contact:** @YourAdminUsername"
        )
        await update.message.reply_text(subscribe_message, parse_mode='Markdown')
    
    elif text in ["🌐 تغيير اللغة", "🌐 Change Language"]:
        keyboard = [["العربية 🇸🇦", "English 🇬🇧"]]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        
        change_lang_text = "🌍 **اختر لغتك | Choose your language:**"
        await update.message.reply_text(change_lang_text, reply_markup=reply_markup, parse_mode='Markdown')