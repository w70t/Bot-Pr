import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from database import (
    get_user,
    get_user_language,
    get_all_users
)

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

async def show_referral_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض قائمة الإحالة"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    lang = get_user_language(user_id)
    user_data = get_user(user_id)
    
    if not user_data:
        if lang == 'ar':
            await query.edit_message_text("❌ لم يتم العثور على بياناتك!")
        else:
            await query.edit_message_text("❌ User data not found!")
        return
    
    # معلومات الإحالة
    referral_code = user_data.get('referral_code', 'N/A')
    bot_username = context.bot.username
    referral_link = f"https://t.me/{bot_username}?start={referral_code}"
    
    referrals_count = len(user_data.get('referrals', []))
    successful_referrals = user_data.get('successful_referrals', 0)
    bonus_downloads = user_data.get('bonus_downloads', 0)
    
    # بناء الرسالة
    if lang == 'ar':
        text = (
            f"👥 **نظام الإحالة**\n\n"
            f"━━━━━━━━━━━━━━━\n"
            f"🎁 **كود الإحالة الخاص بك:**\n"
            f"`{referral_code}`\n\n"
            f"🔗 **رابط الدعوة:**\n"
            f"`{referral_link}`\n\n"
            f"━━━━━━━━━━━━━━━\n"
            f"📊 **إحصائياتك:**\n"
            f"• إجمالي الدعوات: {referrals_count}\n"
            f"• الإحالات الناجحة: {successful_referrals} 🎯\n"
            f"• رصيدك الإضافي: {bonus_downloads} تحميل 💎\n\n"
            f"━━━━━━━━━━━━━━━\n"
            f"💡 **كيف يعمل؟**\n"
            f"1️⃣ شارك رابط الدعوة مع أصدقائك\n"
            f"2️⃣ عندما يحمّل صديقك 10 فيديوهات\n"
            f"3️⃣ تحصل على +10 تحميلات إضافية! 🎉\n\n"
            f"━━━━━━━━━━━━━━━\n"
            f"🏆 **الإنجازات والمكافآت:**\n"
            f"• 5 إحالات → +50 تحميل 🌟\n"
            f"• 10 إحالات → +100 تحميل 💎\n"
            f"• 25 إحالة → 7 أيام VIP 🎁\n"
            f"• 50 إحالة → 30 يوم VIP 👑\n"
            f"• 100 إحالة → VIP مدى الحياة! ♾️🏆\n\n"
            f"🚀 ابدأ الدعوة الآن واربح!"
        )
        
        keyboard = [
            [InlineKeyboardButton("👥 قائمة الأصدقاء", callback_data='ref_friends_list')],
            [InlineKeyboardButton("🏆 إنجازاتي", callback_data='ref_achievements')],
            [InlineKeyboardButton("🔙 العودة", callback_data='main_menu')],
        ]
    else:
        text = (
            f"👥 **Referral System**\n\n"
            f"━━━━━━━━━━━━━━━\n"
            f"🎁 **Your Referral Code:**\n"
            f"`{referral_code}`\n\n"
            f"🔗 **Invitation Link:**\n"
            f"`{referral_link}`\n\n"
            f"━━━━━━━━━━━━━━━\n"
            f"📊 **Your Stats:**\n"
            f"• Total invites: {referrals_count}\n"
            f"• Successful referrals: {successful_referrals} 🎯\n"
            f"• Bonus balance: {bonus_downloads} downloads 💎\n\n"
            f"━━━━━━━━━━━━━━━\n"
            f"💡 **How it works?**\n"
            f"1️⃣ Share your invite link with friends\n"
            f"2️⃣ When your friend downloads 10 videos\n"
            f"3️⃣ You get +10 bonus downloads! 🎉\n\n"
            f"━━━━━━━━━━━━━━━\n"
            f"🏆 **Achievements & Rewards:**\n"
            f"• 5 referrals → +50 downloads 🌟\n"
            f"• 10 referrals → +100 downloads 💎\n"
            f"• 25 referrals → 7 days VIP 🎁\n"
            f"• 50 referrals → 30 days VIP 👑\n"
            f"• 100 referrals → Lifetime VIP! ♾️🏆\n\n"
            f"🚀 Start inviting and earn!"
        )
        
        keyboard = [
            [InlineKeyboardButton("👥 Friends List", callback_data='ref_friends_list')],
            [InlineKeyboardButton("🏆 My Achievements", callback_data='ref_achievements')],
            [InlineKeyboardButton("🔙 Back", callback_data='main_menu')],
        ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def show_friends_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض قائمة الأصدقاء المُحالين"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    lang = get_user_language(user_id)
    user_data = get_user(user_id)
    
    if not user_data:
        return
    
    referrals = user_data.get('referrals', [])
    
    if not referrals:
        if lang == 'ar':
            text = (
                "👥 **قائمة الأصدقاء**\n\n"
                "لم تقم بدعوة أي أصدقاء بعد!\n\n"
                "💡 شارك رابط الدعوة الخاص بك واربح مكافآت رائعة!"
            )
        else:
            text = (
                "👥 **Friends List**\n\n"
                "You haven't invited any friends yet!\n\n"
                "💡 Share your invite link and earn great rewards!"
            )
    else:
        if lang == 'ar':
            text = f"👥 **قائمة الأصدقاء** ({len(referrals)})\n\n"
        else:
            text = f"👥 **Friends List** ({len(referrals)})\n\n"
        
        # عرض أول 20 صديق فقط
        for idx, ref_id in enumerate(referrals[:20], 1):
            ref_user = get_user(ref_id)
            if ref_user:
                username = ref_user.get('username', 'N/A')
                full_name = ref_user.get('full_name', 'User')
                download_count = ref_user.get('download_count', 0)
                
                # حالة الإحالة
                if download_count >= 10:
                    status = "✅"
                else:
                    status = f"⏳ {download_count}/10"
                
                text += f"{idx}. {status} @{username} - {full_name}\n"
        
        if len(referrals) > 20:
            text += f"\n... و {len(referrals) - 20} صديق آخر"
    
    if lang == 'ar':
        keyboard = [[InlineKeyboardButton("🔙 العودة", callback_data='referral_menu')]]
    else:
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data='referral_menu')]]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def show_achievements(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض الإنجازات"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    lang = get_user_language(user_id)
    user_data = get_user(user_id)
    
    if not user_data:
        return
    
    successful_referrals = user_data.get('successful_referrals', 0)
    achievements = user_data.get('achievements', {})
    is_lifetime_vip = user_data.get('is_lifetime_vip', False)
    
    if lang == 'ar':
        text = (
            f"🏆 **إنجازاتي**\n\n"
            f"إحالاتك الناجحة: {successful_referrals}\n\n"
            f"━━━━━━━━━━━━━━━\n"
        )
        
        # الإنجازات
        achievements_list = [
            (5, '5_referrals', '🌟 محيل ذهبي', '+50 تحميل'),
            (10, '10_referrals', '💎 محيل ماسي', '+100 تحميل'),
            (25, '25_referrals', '🎁 محيل بلاتيني', '7 أيام VIP'),
            (50, '50_referrals', '👑 محيل ملكي', '30 يوم VIP'),
            (100, '100_referrals', '♾️ محيل أسطوري', 'VIP مدى الحياة'),
        ]
        
        for threshold, key, title, reward in achievements_list:
            if achievements.get(key) or (threshold == 100 and is_lifetime_vip):
                status = "✅"
                progress = ""
            elif successful_referrals >= threshold:
                status = "🔓"
                progress = ""
            else:
                status = "🔒"
                progress = f" ({successful_referrals}/{threshold})"
            
            text += f"{status} {title}{progress}\n"
            text += f"   المكافأة: {reward}\n\n"
        
        keyboard = [[InlineKeyboardButton("🔙 العودة", callback_data='referral_menu')]]
    else:
        text = (
            f"🏆 **My Achievements**\n\n"
            f"Successful referrals: {successful_referrals}\n\n"
            f"━━━━━━━━━━━━━━━\n"
        )
        
        achievements_list = [
            (5, '5_referrals', '🌟 Golden Referrer', '+50 downloads'),
            (10, '10_referrals', '💎 Diamond Referrer', '+100 downloads'),
            (25, '25_referrals', '🎁 Platinum Referrer', '7 days VIP'),
            (50, '50_referrals', '👑 Royal Referrer', '30 days VIP'),
            (100, '100_referrals', '♾️ Legendary Referrer', 'Lifetime VIP'),
        ]
        
        for threshold, key, title, reward in achievements_list:
            if achievements.get(key) or (threshold == 100 and is_lifetime_vip):
                status = "✅"
                progress = ""
            elif successful_referrals >= threshold:
                status = "🔓"
                progress = ""
            else:
                status = "🔒"
                progress = f" ({successful_referrals}/{threshold})"
            
            text += f"{status} {title}{progress}\n"
            text += f"   Reward: {reward}\n\n"
        
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data='referral_menu')]]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def referral_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج callbacks الإحالة"""
    query = update.callback_query
    data = query.data
    
    if data == 'referral_menu':
        await show_referral_menu(update, context)
    elif data == 'ref_friends_list':
        await show_friends_list(update, context)
    elif data == 'ref_achievements':
        await show_achievements(update, context)