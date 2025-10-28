import logging
from telegram import Update
from telegram.ext import ContextTypes
from datetime import datetime

from database import (
    get_user,
    is_subscribed,
    get_user_language,
    update_user_interaction,
    get_daily_download_count
)
from utils import get_message

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def account_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض معلومات حساب المستخدم"""
    user = update.message.from_user
    user_id = user.id
    
    # تحديث آخر تفاعل
    update_user_interaction(user_id)
    
    # جلب بيانات المستخدم
    user_data = get_user(user_id)
    
    if not user_data:
        await update.message.reply_text(
            "❌ لم يتم العثور على بياناتك.\n\n"
            "الرجاء إرسال /start لتسجيل حسابك."
        )
        return
    
    # التحقق من الاشتراك
    is_vip = is_subscribed(user_id)
    subscription_end = user_data.get('subscription_end')
    daily_downloads = get_daily_download_count(user_id)
    
    # حساب الوقت المتبقي
    if is_vip and subscription_end:
        now = datetime.now()
        remaining = subscription_end - now
        
        if remaining.total_seconds() > 0:
            days = remaining.days
            hours = remaining.seconds // 3600
            minutes = (remaining.seconds % 3600) // 60
            
            # عرض الوقت المتبقي بشكل جميل
            if days > 0:
                remaining_text = f"{days} يوم، {hours} ساعة"
            elif hours > 0:
                remaining_text = f"{hours} ساعة، {minutes} دقيقة"
            else:
                remaining_text = f"{minutes} دقيقة"
            
            # تاريخ انتهاء الاشتراك بالتفصيل (24 ساعة)
            expiry_date = subscription_end.strftime("%Y-%m-%d %H:%M")
            expiry_status = "✅"
        else:
            remaining_text = "❌ منتهي"
            expiry_date = "منتهي"
            expiry_status = "❌"
            is_vip = False  # الاشتراك منتهي
    else:
        remaining_text = "لا يوجد"
        expiry_date = "لا يوجد اشتراك"
        expiry_status = "➖"
    
    # بناء رسالة البطاقة
    account_text = (
        f"🧑 **بطاقتك الشخصية**\n\n"
        f"🆔 **المعرف:** `{user_id}`\n"
        f"💎 **الحالة:** {'🔥 VIP' if is_vip else '🆓 مجاني'}\n"
        f"📊 **التحميلات اليوم:** {daily_downloads}/{5 if not is_vip else '∞'} 📈\n"
    )
    
    if is_vip:
        account_text += f"⏱️ **المتبقي:** {remaining_text} ⚡\n\n"
    else:
        account_text += f"⏱️ **المتبقي:** {remaining_text}\n\n"
    
    account_text += f"{'👑 **مشترك VIP** 👑' if is_vip else '🆓 مستخدم مجاني'}\n\n"
    
    if is_vip and subscription_end and expiry_status == "✅":
        account_text += (
            f"📦 **تفاصيل الاشتراك:**\n\n"
            f"✅ تحميلات: **غير محدودة** ∞\n"
            f"✅ مدة الفيديو: **بلا حدود** ⏰\n"
            f"✅ بدون لوجو 🎨\n"
            f"✅ جودات عالية 📺\n"
            f"✅ أولوية في المعالجة ⚡\n\n"
            f"⏰ **صالح حتى:** `{expiry_date}`\n"
            f"⌛ **الوقت المتبقي:** {remaining_text}"
        )
    else:
        account_text += (
            f"💡 **اشترك في VIP للحصول على:**\n\n"
            f"✅ تحميلات **غير محدودة** ∞\n"
            f"✅ بدون انتظار ⚡\n"
            f"✅ جودة **4K/8K** 🎬\n"
            f"✅ **بدون لوجو** 🎨\n"
            f"✅ دعم فني سريع 💬\n"
            f"✅ أولوية في الخادم 🚀\n\n"
            f"💰 باقات تبدأ من **$5/شهر**\n\n"
            f"📩 للاشتراك: @wahab161"
        )
    
    await update.message.reply_text(account_text, parse_mode='Markdown')

async def test_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """اختبار حالة الاشتراك (للتطوير فقط)"""
    user_id = update.message.from_user.id
    
    is_vip = is_subscribed(user_id)
    user_data = get_user(user_id)
    
    if not user_data:
        await update.message.reply_text("❌ لم يتم العثور على بياناتك")
        return
    
    subscription_end = user_data.get('subscription_end')
    
    test_text = (
        f"🧪 **اختبار الاشتراك**\n\n"
        f"🆔 User ID: `{user_id}`\n"
        f"💎 VIP: {'✅ نعم' if is_vip else '❌ لا'}\n"
    )
    
    if subscription_end:
        now = datetime.now()
        remaining = subscription_end - now
        
        test_text += (
            f"📅 تاريخ الانتهاء: `{subscription_end.strftime('%Y-%m-%d %H:%M:%S')}`\n"
            f"⏰ الآن: `{now.strftime('%Y-%m-%d %H:%M:%S')}`\n"
            f"⌛ الفرق: `{remaining.days} يوم، {remaining.seconds // 3600} ساعة، {(remaining.seconds % 3600) // 60} دقيقة`\n"
            f"✅ صالح: {'نعم' if remaining.total_seconds() > 0 else 'لا (منتهي)'}"
        )
    else:
        test_text += "📅 تاريخ الانتهاء: لا يوجد"
    
    await update.message.reply_text(test_text, parse_mode='Markdown')