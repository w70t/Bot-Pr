import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from datetime import datetime

from database import (
    get_user,
    is_subscribed,
    get_user_language,
    get_daily_download_count,
    get_bonus_downloads
)

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

FREE_USER_DOWNLOAD_LIMIT = 5

async def show_account_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض معلومات الحساب"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    lang = get_user_language(user_id)
    
    # جلب بيانات المستخدم
    user_data = get_user(user_id)
    
    if not user_data:
        if lang == 'ar':
            await query.edit_message_text("❌ لم يتم العثور على بياناتك!")
        else:
            await query.edit_message_text("❌ User data not found!")
        return
    
    # معلومات المستخدم
    username = user_data.get('username', 'N/A')
    full_name = user_data.get('full_name', 'User')
    registration_date = user_data.get('registration_date', datetime.now())
    download_count = user_data.get('download_count', 0)
    referral_code = user_data.get('referral_code', 'N/A')
    referrals_count = len(user_data.get('referrals', []))
    successful_referrals = user_data.get('successful_referrals', 0)
    bonus_downloads = get_bonus_downloads(user_id)
    
    # حالة الاشتراك
    is_vip = is_subscribed(user_id)
    is_lifetime = user_data.get('is_lifetime_vip', False)
    subscription_end = user_data.get('subscription_end')
    
    # التحميلات اليومية
    daily_downloads = get_daily_download_count(user_id)
    remaining_downloads = FREE_USER_DOWNLOAD_LIMIT - daily_downloads if not is_vip else "∞"
    
    # تنسيق التاريخ
    reg_date_str = registration_date.strftime('%Y-%m-%d') if isinstance(registration_date, datetime) else 'N/A'
    
    # حالة VIP
    if is_lifetime:
        vip_status_ar = "♾️ VIP مدى الحياة"
        vip_status_en = "♾️ Lifetime VIP"
    elif is_vip and subscription_end:
        days_left = (subscription_end - datetime.now()).days
        vip_status_ar = f"⭐ VIP (متبقي {days_left} يوم)"
        vip_status_en = f"⭐ VIP ({days_left} days left)"
    else:
        vip_status_ar = "🆓 مجاني"
        vip_status_en = "🆓 Free"
    
    # بناء الرسالة
    if lang == 'ar':
        text = (
            f"👤 **معلومات الحساب**\n\n"
            f"━━━━━━━━━━━━━━━\n"
            f"📝 **البيانات الأساسية:**\n"
            f"• الاسم: {full_name}\n"
            f"• المعرف: @{username}\n"
            f"• الآيدي: `{user_id}`\n"
            f"• تاريخ التسجيل: {reg_date_str}\n\n"
            f"━━━━━━━━━━━━━━━\n"
            f"💎 **الحالة:**\n"
            f"• {vip_status_ar}\n\n"
            f"━━━━━━━━━━━━━━━\n"
            f"📊 **إحصائيات التحميل:**\n"
            f"• إجمالي التحميلات: {download_count}\n"
            f"• التحميلات اليوم: {daily_downloads}/{FREE_USER_DOWNLOAD_LIMIT if not is_vip else '∞'}\n"
            f"• تحميلات إضافية: {bonus_downloads} 💎\n\n"
            f"━━━━━━━━━━━━━━━\n"
            f"👥 **نظام الإحالة:**\n"
            f"• كود الإحالة: `{referral_code}`\n"
            f"• إجمالي الدعوات: {referrals_count}\n"
            f"• الإحالات الناجحة: {successful_referrals} 🎯\n\n"
            f"💡 **نصيحة:** كل 10 تحميلات من صديقك = +10 تحميلات لك!\n"
            f"🏆 100 إحالة ناجحة = VIP مدى الحياة!"
        )
        back_text = "🔙 العودة"
    else:
        text = (
            f"👤 **Account Information**\n\n"
            f"━━━━━━━━━━━━━━━\n"
            f"📝 **Basic Info:**\n"
            f"• Name: {full_name}\n"
            f"• Username: @{username}\n"
            f"• ID: `{user_id}`\n"
            f"• Registration: {reg_date_str}\n\n"
            f"━━━━━━━━━━━━━━━\n"
            f"💎 **Status:**\n"
            f"• {vip_status_en}\n\n"
            f"━━━━━━━━━━━━━━━\n"
            f"📊 **Download Stats:**\n"
            f"• Total downloads: {download_count}\n"
            f"• Today's downloads: {daily_downloads}/{FREE_USER_DOWNLOAD_LIMIT if not is_vip else '∞'}\n"
            f"• Bonus downloads: {bonus_downloads} 💎\n\n"
            f"━━━━━━━━━━━━━━━\n"
            f"👥 **Referral System:**\n"
            f"• Referral code: `{referral_code}`\n"
            f"• Total invites: {referrals_count}\n"
            f"• Successful referrals: {successful_referrals} 🎯\n\n"
            f"💡 **Tip:** Every 10 downloads from your friend = +10 downloads for you!\n"
            f"🏆 100 successful referrals = Lifetime VIP!"
        )
        back_text = "🔙 Back"
    
    keyboard = [[InlineKeyboardButton(back_text, callback_data='main_menu')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )