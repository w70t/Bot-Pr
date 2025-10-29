import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from datetime import datetime

from database import (
    get_user,
    is_subscribed,
    get_user_language
)

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

async def show_subscription_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض قائمة الاشتراك VIP"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    lang = get_user_language(user_id)
    user_data = get_user(user_id)
    
    if not user_data:
        return
    
    # حالة الاشتراك الحالية
    is_vip = is_subscribed(user_id)
    is_lifetime = user_data.get('is_lifetime_vip', False)
    subscription_end = user_data.get('subscription_end')
    successful_referrals = user_data.get('successful_referrals', 0)
    
    # بناء الرسالة
    if lang == 'ar':
        # حالة VIP
        if is_lifetime:
            vip_status = "♾️ **أنت عضو VIP مدى الحياة!**"
        elif is_vip and subscription_end:
            days_left = (subscription_end - datetime.now()).days
            vip_status = f"⭐ **اشتراكك VIP نشط**\nمتبقي: {days_left} يوم"
        else:
            vip_status = "🆓 **حساب مجاني**"
        
        text = (
            f"💎 **اشترك في VIP**\n\n"
            f"━━━━━━━━━━━━━━━\n"
            f"📊 **حالتك الحالية:**\n"
            f"{vip_status}\n\n"
            f"━━━━━━━━━━━━━━━\n"
            f"✨ **مميزات VIP:**\n\n"
            f"✅ تحميلات غير محدودة يومياً\n"
            f"✅ بدون لوجو على الفيديوهات\n"
            f"✅ جودة عالية (حتى 1080p)\n"
            f"✅ أولوية في التحميل\n"
            f"✅ دعم سريع ومميز\n\n"
            f"━━━━━━━━━━━━━━━\n"
            f"💰 **الأسعار:**\n\n"
            f"📅 أسبوع واحد: 3$\n"
            f"📅 شهر واحد: 10$\n"
            f"📅 3 أشهر: 25$ (وفّر 17%)\n"
            f"📅 6 أشهر: 45$ (وفّر 25%)\n"
            f"📅 سنة كاملة: 80$ (وفّر 33%)\n\n"
            f"━━━━━━━━━━━━━━━\n"
            f"🎁 **احصل على VIP مجاناً!**\n\n"
            f"👥 ادعو أصدقائك واحصل على:\n"
            f"• 25 إحالة ناجحة → 7 أيام VIP 🎁\n"
            f"• 50 إحالة ناجحة → 30 يوم VIP 👑\n"
            f"• 100 إحالة ناجحة → VIP مدى الحياة! ♾️🏆\n\n"
            f"تقدمك الحالي: {successful_referrals}/100 إحالة\n\n"
            f"━━━━━━━━━━━━━━━\n"
            f"📞 **للاشتراك:**\n"
            f"تواصل مع: @7kmmy\n\n"
            f"💳 طرق الدفع:\n"
            f"• PayPal\n"
            f"• البطاقات البنكية\n"
            f"• Cryptocurrency\n"
            f"• محافظ إلكترونية\n\n"
            f"🔒 الدفع آمن ومضمون 100%"
        )
        
        keyboard = [
            [InlineKeyboardButton("💬 تواصل مع @7kmmy", url="https://t.me/7kmmy")],
            [InlineKeyboardButton("👥 ادعو الأصدقاء (مجاناً)", callback_data='referral_menu')],
            [InlineKeyboardButton("🔙 العودة", callback_data='main_menu')],
        ]
    else:
        # English version
        if is_lifetime:
            vip_status = "♾️ **You're a Lifetime VIP member!**"
        elif is_vip and subscription_end:
            days_left = (subscription_end - datetime.now()).days
            vip_status = f"⭐ **Your VIP subscription is active**\nRemaining: {days_left} days"
        else:
            vip_status = "🆓 **Free Account**"
        
        text = (
            f"💎 **Subscribe to VIP**\n\n"
            f"━━━━━━━━━━━━━━━\n"
            f"📊 **Your Current Status:**\n"
            f"{vip_status}\n\n"
            f"━━━━━━━━━━━━━━━\n"
            f"✨ **VIP Features:**\n\n"
            f"✅ Unlimited daily downloads\n"
            f"✅ No watermark on videos\n"
            f"✅ High quality (up to 1080p)\n"
            f"✅ Download priority\n"
            f"✅ Fast premium support\n\n"
            f"━━━━━━━━━━━━━━━\n"
            f"💰 **Pricing:**\n\n"
            f"📅 1 Week: $3\n"
            f"📅 1 Month: $10\n"
            f"📅 3 Months: $25 (Save 17%)\n"
            f"📅 6 Months: $45 (Save 25%)\n"
            f"📅 1 Year: $80 (Save 33%)\n\n"
            f"━━━━━━━━━━━━━━━\n"
            f"🎁 **Get VIP for FREE!**\n\n"
            f"👥 Invite your friends and get:\n"
            f"• 25 successful referrals → 7 days VIP 🎁\n"
            f"• 50 successful referrals → 30 days VIP 👑\n"
            f"• 100 successful referrals → Lifetime VIP! ♾️🏆\n\n"
            f"Your progress: {successful_referrals}/100 referrals\n\n"
            f"━━━━━━━━━━━━━━━\n"
            f"📞 **To Subscribe:**\n"
            f"Contact: @7kmmy\n\n"
            f"💳 Payment Methods:\n"
            f"• PayPal\n"
            f"• Credit/Debit Cards\n"
            f"• Cryptocurrency\n"
            f"• E-Wallets\n\n"
            f"🔒 100% Safe & Secure Payment"
        )
        
        keyboard = [
            [InlineKeyboardButton("💬 Contact @7kmmy", url="https://t.me/7kmmy")],
            [InlineKeyboardButton("👥 Invite Friends (Free)", callback_data='referral_menu')],
            [InlineKeyboardButton("🔙 Back", callback_data='main_menu')],
        ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )