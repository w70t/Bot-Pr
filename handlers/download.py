import os
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import yt_dlp
import logging

from database import (
    is_subscribed,
    get_user,
    increment_download_count,
    get_user_language,
    is_admin,
    get_daily_download_count
)
from utils import get_message, clean_filename, get_config, apply_watermark

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

LOG_CHANNEL_ID = os.getenv("LOG_CHANNEL_ID")
FREE_USER_DOWNLOAD_LIMIT = 5
VIDEO_PATH = 'videos'

if not os.path.exists(VIDEO_PATH):
    os.makedirs(VIDEO_PATH)

class DownloadProgressTracker:
    """تتبع تقدم التحميل مع تحديثات منتظمة"""
    def __init__(self, message, lang):
        self.message = message
        self.lang = lang
        self.last_update = 0
        self.last_percentage = 0
        
    def progress_hook(self, d):
        """يتم استدعاؤه من yt-dlp لتحديث التقدم"""
        if d['status'] == 'downloading':
            try:
                # حساب النسبة المئوية
                downloaded = d.get('downloaded_bytes', 0)
                total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
                
                if total > 0:
                    percentage = int((downloaded / total) * 100)
                    speed = d.get('speed', 0)
                    eta = d.get('eta', 0)
                    
                    # تحديث فقط كل 10% لتجنب الـ rate limit
                    if percentage >= self.last_percentage + 10:
                        self.last_percentage = percentage
                        
                        # تنسيق السرعة
                        speed_text = f"{speed / 1024 / 1024:.2f} MB/s" if speed else "..."
                        eta_text = f"{eta}s" if eta else "..."
                        
                        progress_bar = self._create_progress_bar(percentage)
                        
                        update_text = (
                            f"📥 **جاري التحميل...**\n\n"
                            f"{progress_bar}\n"
                            f"**النسبة:** {percentage}%\n"
                            f"⚡ **السرعة:** {speed_text}\n"
                            f"⏱️ **الوقت المتبقي:** {eta_text}"
                        )
                        
                        # تحديث الرسالة بشكل آمن
                        asyncio.create_task(self._safe_edit(update_text))
                        
            except Exception as e:
                logger.warning(f"خطأ في تحديث التقدم: {e}")
    
    def _create_progress_bar(self, percentage):
        """إنشاء شريط تقدم مرئي"""
        filled = int(percentage / 5)  # 20 خانة للشريط
        empty = 20 - filled
        return f"[{'█' * filled}{'░' * empty}]"
    
    async def _safe_edit(self, text):
        """تحديث آمن للرسالة"""
        try:
            await self.message.edit_text(text, parse_mode='Markdown')
        except Exception as e:
            logger.warning(f"فشل تحديث الرسالة: {e}")

async def send_log_to_channel(context: ContextTypes.DEFAULT_TYPE, user, video_info: dict, file_path: str):
    """إرسال سجل التحميل إلى قناة اللوج"""
    if not LOG_CHANNEL_ID:
        return

    user_id = user.id
    user_name = user.full_name
    username = f"@{user.username}" if user.username else "لا يوجد"
    
    video_title = video_info.get('title', 'N/A')
    video_url = video_info.get('webpage_url', 'N/A')
    duration = video_info.get('duration', 0)
    filesize = video_info.get('filesize', 0) or video_info.get('filesize_approx', 0)

    # تنسيق الحجم
    size_mb = filesize / (1024 * 1024) if filesize else 0
    
    log_caption = (
        f"✅ **تحميل جديد**\n\n"
        f"👤 **بواسطة:** {user_name}\n"
        f"🆔 **ID:** `{user_id}`\n"
        f"🔗 **Username:** {username}\n\n"
        f"🎬 **العنوان:** {video_title}\n"
        f"⏱️ **المدة:** {duration}s\n"
        f"📦 **الحجم:** {size_mb:.2f} MB\n"
        f"🌐 **الرابط:** {video_url}"
    )

    try:
        with open(file_path, 'rb') as video_file:
            await context.bot.send_video(
                chat_id=LOG_CHANNEL_ID,
                video=video_file,
                caption=log_caption,
                parse_mode='Markdown'
            )
    except Exception as e:
        logger.error(f"❌ فشل إرسال الفيديو إلى قناة السجل: {e}")
        try:
            await context.bot.send_message(
                chat_id=LOG_CHANNEL_ID,
                text=log_caption,
                disable_web_page_preview=True,
                parse_mode='Markdown'
            )
        except Exception as text_e:
            logger.error(f"❌ فشل إرسال السجل النصي أيضاً: {text_e}")

async def handle_download(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج تحميل الفيديوهات الرئيسي - محسّن"""
    user = update.message.from_user
    user_id = user.id
    url = update.message.text
    lang = get_user_language(user_id)
    user_data = get_user(user_id)
    
    if not user_data:
        await update.message.reply_text(get_message(lang, "error_finding_user"))
        return

    is_user_admin = is_admin(user_id)
    is_subscribed_user = is_subscribed(user_id)
    
    config = get_config()
    
    # 1. التحقق من حظر المواقع الإباحية
    blocked_domains = config.get("BLOCKED_DOMAINS", [])
    for domain in blocked_domains:
        if domain.lower() in url.lower():
            await update.message.reply_text(get_message(lang, "blocked_domain_message"))
            return

    # 2. التحقق من حد التحميل اليومي
    if not is_user_admin and not is_subscribed_user:
        daily_count = get_daily_download_count(user_id)
        if daily_count >= FREE_USER_DOWNLOAD_LIMIT:
            keyboard = [[InlineKeyboardButton(
                get_message(lang, "subscribe_button_text"), 
                url=get_message(lang, "subscribe_link")
            )]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                get_message(lang, "limit_reached"), 
                reply_markup=reply_markup
            )
            return

    # رسالة البداية
    processing_message = await update.message.reply_text(
        "🔍 **جاري التحليل...**\n\nيرجى الانتظار بينما أقوم بتحليل الرابط...",
        parse_mode='Markdown'
    )
    
    new_filepath = None
    temp_watermarked_path = None
    
    try:
        # إعداد تتبع التقدم
        progress_tracker = DownloadProgressTracker(processing_message, lang)
        
        # إعدادات yt-dlp محسّنة
        ydl_opts = {
            'format': 'best[ext=mp4][height<=720]/best[ext=mp4]/best',
            'outtmpl': os.path.join(VIDEO_PATH, '%(title)s.%(ext)s'),
            'noplaylist': True,
            'quiet': False,
            'no_warnings': False,
            'merge_output_format': 'mp4',
            'progress_hooks': [progress_tracker.progress_hook],  # إضافة تتبع التقدم
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            loop = asyncio.get_event_loop()
            
            # جلب معلومات الفيديو بدون تحميل
            logger.info(f"🔍 جلب معلومات الفيديو من: {url}")
            info_dict = await loop.run_in_executor(
                None, 
                lambda: ydl.extract_info(url, download=False)
            )
            
            # التحقق من صحة المعلومات
            if not info_dict:
                raise Exception("فشل في جلب معلومات الفيديو")
            
            title = info_dict.get('title', 'video')
            duration = info_dict.get('duration', 0)
            filesize = info_dict.get('filesize', 0) or info_dict.get('filesize_approx', 0)
            
            logger.info(f"✅ تم جلب المعلومات - العنوان: {title}, المدة: {duration}s")
            
            # عرض معلومات الفيديو للمستخدم
            size_mb = filesize / (1024 * 1024) if filesize else 0
            video_info_text = (
                f"📋 **معلومات الفيديو:**\n\n"
                f"🎬 **العنوان:** {title[:50]}...\n"
                f"⏱️ **المدة:** {duration // 60}:{duration % 60:02d}\n"
                f"📦 **الحجم:** ~{size_mb:.2f} MB\n\n"
                f"⏳ **جاري بدء التحميل...**"
            )
            await processing_message.edit_text(video_info_text, parse_mode='Markdown')
            await asyncio.sleep(2)
            
            # 3. التحقق من حد المدة للمستخدمين غير المشتركين
            max_free_duration = config.get("MAX_FREE_DURATION", 300)
            
            if not is_user_admin and not is_subscribed_user and duration and duration > max_free_duration:
                keyboard = [[InlineKeyboardButton(
                    get_message(lang, "subscribe_button_text"), 
                    url=get_message(lang, "subscribe_link")
                )]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await processing_message.edit_text(
                    get_message(lang, "duration_limit_exceeded").format(limit=max_free_duration // 60),
                    reply_markup=reply_markup
                )
                return

            # بدء التحميل مع شريط التقدم
            logger.info(f"📥 بدء تحميل الفيديو...")
            await processing_message.edit_text(
                "📥 **بدء التحميل...**\n\n[░░░░░░░░░░░░░░░░░░░░] 0%",
                parse_mode='Markdown'
            )
            
            await loop.run_in_executor(None, lambda: ydl.download([url]))
            
            # إعداد مسارات الملفات
            original_filepath = ydl.prepare_filename(info_dict)
            cleaned_title = clean_filename(title)
            new_filepath = os.path.join(VIDEO_PATH, f"{cleaned_title}.mp4")
            
            # إعادة تسمية الملف
            if os.path.exists(original_filepath):
                if os.path.exists(new_filepath) and original_filepath != new_filepath:
                    os.remove(new_filepath)
                os.rename(original_filepath, new_filepath)
            
            if not os.path.exists(new_filepath):
                raise FileNotFoundError(f"الفيديو المحمل غير موجود في: {new_filepath}")

            logger.info(f"✅ تم التحميل بنجاح: {new_filepath}")
            
            # 4. تطبيق اللوجو (للمستخدمين المجانيين فقط)
            logo_path = config.get("LOGO_PATH")
            final_video_path = new_filepath
            
            if not is_subscribed_user and not is_user_admin and logo_path and os.path.exists(logo_path):
                await processing_message.edit_text(
                    "🎨 **إضافة اللوجو...**\n\nيرجى الانتظار...",
                    parse_mode='Markdown'
                )
                
                temp_watermarked_path = new_filepath.replace(".mp4", "_watermarked.mp4")
                result_path = apply_watermark(new_filepath, temp_watermarked_path, logo_path)
                
                if result_path != new_filepath and os.path.exists(result_path):
                    final_video_path = result_path
                    logger.info(f"✅ تم تطبيق اللوجو بنجاح")
                else:
                    logger.warning(f"⚠️ فشل تطبيق اللوجو. إرسال الملف الأصلي.")

            # 5. رفع الفيديو
            await processing_message.edit_text(
                "📤 **جاري الرفع...**\n\nيرجى الانتظار بينما أقوم برفع الفيديو إلى تيليجرام...",
                parse_mode='Markdown'
            )
            
            # التحقق من حجم الملف (حد تيليجرام 2GB)
            file_size = os.path.getsize(final_video_path)
            if file_size > 2 * 1024 * 1024 * 1024:
                await processing_message.edit_text(get_message(lang, "file_too_large"))
                return
            
            # إعداد الـ caption
            sub_emoji = "💎" if is_subscribed_user else "🆓"
            caption_text = (
                f"{sub_emoji} **{title}**\n\n"
                f"⏱️ المدة: {duration // 60}:{duration % 60:02d}\n"
                f"📦 الحجم: {file_size / (1024 * 1024):.2f} MB\n\n"
                f"✨ تم التحميل بواسطة @{context.bot.username}"
            )
            
            # إرسال الفيديو
            with open(final_video_path, 'rb') as video_file:
                sent_message = await context.bot.send_video(
                    chat_id=update.effective_chat.id, 
                    video=video_file, 
                    caption=caption_text,
                    parse_mode='Markdown',
                    reply_to_message_id=update.message.message_id,
                    supports_streaming=True
                )
            
            logger.info(f"✅ تم إرسال الفيديو بنجاح للمستخدم {user_id}")
            
            # 6. إعادة توجيه الفيديو إلى القناة الخاصة
            log_channel_videos_id = config.get("LOG_CHANNEL_ID_VIDEOS")
            if log_channel_videos_id and sent_message:
                try:
                    await sent_message.forward(chat_id=log_channel_videos_id)
                    logger.info(f"✅ تم إعادة توجيه الفيديو إلى القناة الخاصة")
                except Exception as forward_e:
                    logger.error(f"❌ فشل إعادة توجيه الفيديو: {forward_e}")

            # إرسال سجل إلى قناة السجل القديمة
            await send_log_to_channel(context, user, info_dict, final_video_path)

            # حذف رسالة المعالجة
            await processing_message.delete()
            
            # زيادة عداد التحميلات (للمستخدمين المجانيين فقط)
            if not is_user_admin and not is_subscribed_user:
                increment_download_count(user_id)
                remaining = FREE_USER_DOWNLOAD_LIMIT - get_daily_download_count(user_id)
                if remaining > 0:
                    await update.message.reply_text(
                        f"ℹ️ **تبقى لك {remaining} تحميلات مجانية اليوم**",
                        parse_mode='Markdown'
                    )

    except yt_dlp.utils.DownloadError as e:
        logger.error(f"❌ خطأ في yt-dlp: {e}")
        error_message = get_message(lang, "download_failed")
        
        if "Unsupported URL" in str(e) or "not supported" in str(e).lower():
            error_message = get_message(lang, "unsupported_platform")
        elif "Private video" in str(e):
            error_message = "❌ **الفيديو خاص!**\n\nهذا الفيديو خاص أو محمي ولا يمكن تحميله."
        
        try:
            await processing_message.edit_text(error_message, parse_mode='Markdown')
        except Exception:
            await update.message.reply_text(error_message, parse_mode='Markdown')
            
    except Exception as e:
        logger.error(f"❌ خطأ غير متوقع في handle_download: {e}", exc_info=True)
        error_message = f"❌ **حدث خطأ!**\n\n`{str(e)[:200]}`"
        
        try:
            await processing_message.edit_text(error_message, parse_mode='Markdown')
        except Exception:
            await update.message.reply_text(error_message, parse_mode='Markdown')
            
    finally:
        # تنظيف: حذف الملف الأصلي
        if new_filepath and os.path.exists(new_filepath):
            try:
                os.remove(new_filepath)
                logger.info(f"🗑️ تم حذف الملف المؤقت: {new_filepath}")
            except Exception as e:
                logger.error(f"❌ فشل حذف الملف المؤقت: {e}")
        
        # حذف الملف ذي العلامة المائية
        if temp_watermarked_path and os.path.exists(temp_watermarked_path):
            try:
                os.remove(temp_watermarked_path)
                logger.info(f"🗑️ تم حذف الملف المائي المؤقت")
            except Exception as e:
                logger.error(f"❌ فشل حذف الملف المائي: {e}")