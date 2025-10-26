from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

# --- ✨ التصحيح هنا: تغيير اسم الدالة المستوردة ---
from database import add_user, set_user_language 
from utils import get_message

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    يعالج أمر /start. يضيف المستخدم ويعرض خيارات اللغة.
    """
    user = update.message.from_user
    add_user(user)

    keyboard = [["English", "العربية"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    
    welcome_text = "Welcome! Please choose your language.\n\nأهلاً بك! من فضلك اختر لغتك."
    
    await update.message.reply_text(welcome_text, reply_markup=reply_markup)

async def select_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    يعالج اختيار اللغة من قبل المستخدم ويقوم بتنسيق رسالة الترحيب.
    """
    user = update.message.from_user
    user_id = user.id
    lang_choice = update.message.text
    
    if lang_choice == "English":
        lang_code = "en"
    else:
        lang_code = "ar"

    # --- ✨ التصحيح هنا: استخدام اسم الدالة الصحيح ---
    set_user_language(user_id, lang_code)
    
    # نحصل على الرسالة ونقوم بتنسيقها باستخدام اسم المستخدم
    welcome_message = get_message(lang_code, "welcome").format(name=user.first_name)
    
    # نرسل الرسالة كنص عادي لتجنب مشاكل Markdown
    await update.message.reply_text(
        welcome_message,
        reply_markup=ReplyKeyboardRemove()
    )
