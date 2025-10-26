import os
import asyncio
import time
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
    """تتبع تقدم التحميل مع تحديثات جميلة ومنتظمة"""
    def __init__(self, message, lang):
        self.message = message
        self.lang = lang
        self.last_update_time = 0
        self.last_percentage = -1
        
    def progress_hook(self, d):
        """يتم استدعاؤه من yt-dlp لتحديث التقدم"""
        if d['status'] == 'downloading':
            try:
                current_time = time.time()
                # تحديث كل 3 ثواني فقط لتجنب rate limit
                if current_time - self.last_update_time < 3:
                    return
                
                # حساب النسبة المئوية
                downloaded = d.get('downloaded_bytes', 0)
                total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
                
                if total > 0:
                    percentage = int((downloaded / total) * 100)
                    
                    # تحديث فقط إذا تغيرت النسبة بـ 5% على الأقل
                    if abs(percentage - self.last_percentage) < 5:
                        return
                    
                    self.last_percentage = percentage
                    self.last_update_time = current_time
                    
                    # تنسيق البيانات
                    speed = d.get('speed', 0)
                    eta = d.get('eta', 0)
                    
                    downloaded_mb = downloaded / (1024 * 1024)
                    total_mb = total / (1024 * 1024)
                    speed_text = f"{speed / 1024 / 1024:.2f} MB/s" if speed else "..."
                    
                    # شريط التقدم الجميل
                    progress_bar = self._create_fancy_progress_bar(percentage)
                    
                    # رموز حالة التحميل
                    status_emoji = "🔄" if percentage < 50 else "⚡" if percentage < 90 else "🎉"
                    
                    update_text = (
                        f"{status_emoji} **جاري التحميل...**\n\n"
                        f"{progress_bar}\n\n"
                        f"📊 **التقدم:** `{percentage}%`\n"
                        f"📦 **المحمّل:** `{downloaded_mb:.1f} MB` / `{total_mb:.1f} MB`\n"
                        f"⚡ **السرعة:** `{speed_text}`\n"
                        f"⏱️ **المتبقي:** `{self._format_eta(eta)}`"
                    )
                    
                    # تحديث الرسالة بشكل آمن
                    try:
                        loop = asyncio.get_event_loop()
                        loop.create_task(self.message.edit_text(update_text, parse_mode='Markdown'))
                    except:
                        pass
                        
            except Exception as e:
                logger.warning(f"خطأ في تحديث التقدم: {e}")
    
    def _create_fancy_progress_bar(self, percentage):
        """إنشاء شريط تقدم مرئي جميل"""
        filled = int(percentage / 5)  # 20 خانة
        empty = 20 - filled
        
        # استخدام رموز جميلة
        bar = f"{'🟩' * filled}{'⬜' * empty}"
        return f"`[{percentage:3d}%]` {bar}"
    
    def _format_eta(self, eta_seconds):
        """تنسيق الوقت المتبقي"""
        if not eta_seconds or eta_seconds <= 0:
            return "حساب..."
        
        if eta_seconds < 60:
            return f"{int(eta_seconds)} ثانية"
        elif eta_seconds < 3600:
            minutes = int(eta_seconds / 60)
            return f"{minutes} دقيقة"
        else:
            hours = int(eta_seconds / 3600)
            minutes = int((eta_seconds % 3600) / 60)
            return f"{hours}:{minutes:02d} ساعة"

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

async def handle_download(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج تحميل الفيديوهات الرئيسي - محسّن بالكامل"""
    user = update.message.from_user
    user_id = user.id
    url = update.message.text.strip()
    lang = get_user_language(user_id)
    user_data = get_user(user_id)
    
    if not user_data:
        await update.message.reply_text(get_message(lang, "error_finding_user"))
        return

    is_user_admin = is_admin(user_id)
    is_subscribed_user = is_subscribed(user_id)
    config = get_config()
    
    # 1. التحقق من حظر المواقع
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
        "🔍 **جاري التحليل والتعرف على الفيديو...**\n\n⏳ يرجى الانتظار...",
        parse_mode='Markdown'
    )
    
    new_filepath = None
    temp_watermarked_path = None
    
    try:
        # إعداد yt-dlp مع خيارات محسّنة
        progress_tracker = DownloadProgressTracker(processing_message, lang)
        
        # خيارات محسّنة لتجنب الأخطاء
        ydl_opts = {
            'format': 'best[ext=mp4][height<=720]/bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'outtmpl': os.path.join(VIDEO_PATH, '%(title)s.%(ext)s'),
            'noplaylist': True,
            'quiet': True,
            'no_warnings': True,
            'merge_output_format': 'mp4',
            'progress_hooks': [progress_tracker.progress_hook],
            'socket_timeout': 30,
            'retries': 3,
            'fragment_retries': 3,
            # خيارات إضافية لحل المشاكل
            'nocheckcertificate': True,
            'prefer_ffmpeg': True,
            'keepvideo': False,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            loop = asyncio.get_event_loop()
            
            # جلب معلومات الفيديو
            logger.info(f"🔍 جلب معلومات من: {url}")
            
            try:
                info_dict = await loop.run_in_executor(
                    None, 
                    lambda: ydl.extract_info(url, download=False)
                )
            except Exception as extract_error:
                logger.error(f"❌ فشل استخراج المعلومات: {extract_error}")
                error_msg = "❌ **فشل التحليل!**\n\n"
                
                if "Unsupported URL" in str(extract_error):
                    error_msg += "هذا الرابط غير مدعوم. يرجى التأكد من أن الرابط من:\n• YouTube\n• Instagram\n• TikTok\n• Facebook"
                elif "Private video" in str(extract_error):
                    error_msg += "الفيديو خاص أو محمي. لا يمكن تحميله."
                elif "Video unavailable" in str(extract_error):
                    error_msg += "الفيديو غير متاح أو تم حذفه."
                else:
                    error_msg += f"خطأ: `{str(extract_error)[:150]}`"
                
                await processing_message.edit_text(error_msg, parse_mode='Markdown')
                return
            
            if not info_dict:
                raise Exception("فشل في جلب معلومات الفيديو")
            
            # استخراج المعلومات
            title = info_dict.get('title', 'video')
            duration = info_dict.get('duration', 0)
            filesize = info_dict.get('filesize', 0) or info_dict.get('filesize_approx', 0)
            uploader = info_dict.get('uploader', 'غير معروف')
            platform = info_dict.get('extractor_key', 'Unknown')
            
            logger.info(f"✅ المعلومات: {title}, المدة: {duration}s, المنصة: {platform}")
            
            # عرض معلومات تفصيلية جميلة
            size_mb = filesize / (1024 * 1024) if filesize else 0
            duration_formatted = f"{duration // 60}:{duration % 60:02d}" if duration else "غير معروف"
            
            platform_emoji = {
                'Youtube': '🎥',
                'Instagram': '📸',
                'TikTok': '🎵',
                'Facebook': '👥',
                'Twitter': '🐦'
            }.get(platform, '📹')
            
            video_info_text = (
                f"{platform_emoji} **تم التعرف على الفيديو!**\n\n"
                f"🎬 **العنوان:** {title[:60]}{'...' if len(title) > 60 else ''}\n"
                f"👤 **القناة/المنشئ:** {uploader[:40]}\n"
                f"⏱️ **المدة:** {duration_formatted}\n"
                f"📦 **الحجم التقريبي:** {size_mb:.1f} MB\n"
                f"📱 **المنصة:** {platform}\n\n"
                f"⏳ **جاري بدء التحميل...**"
            )
            
            await processing_message.edit_text(video_info_text, parse_mode='Markdown')
            await asyncio.sleep(2)
            
            # 3. التحقق من حد المدة
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

            # بدء التحميل
            logger.info(f"📥 بدء التحميل من {platform}...")
            await processing_message.edit_text(
                "📥 **بدء التحميل...**\n\n`[  0%]` ⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜",
                parse_mode='Markdown'
            )
            
            # التحميل الفعلي
            await loop.run_in_executor(None, lambda: ydl.download([url]))
            
            # معالجة الملف
            original_filepath = ydl.prepare_filename(info_dict)
            cleaned_title = clean_filename(title)
            new_filepath = os.path.join(VIDEO_PATH, f"{cleaned_title}.mp4")
            
            if os.path.exists(original_filepath):
                if os.path.exists(new_filepath) and original_filepath != new_filepath:
                    os.remove(new_filepath)
                os.rename(original_filepath, new_filepath)
            
            if not os.path.exists(new_filepath):
                raise FileNotFoundError(f"الفيديو غير موجود: {new_filepath}")

            logger.info(f"✅ تم التحميل: {new_filepath}")
            
            # 4. تطبيق اللوجو (للمجانيين فقط)
            logo_path = config.get("LOGO_PATH")
            final_video_path = new_filepath
            
            if not is_subscribed_user and not is_user_admin and logo_path and os.path.exists(logo_path):
                await processing_message.edit_text(
                    "🎨 **إضافة اللوجو الخاص...**\n\n⏳ لحظات...",
                    parse_mode='Markdown'
                )
                
                temp_watermarked_path = new_filepath.replace(".mp4", "_watermarked.mp4")
                result_path = apply_watermark(new_filepath, temp_watermarked_path, logo_path)
                
                if result_path != new_filepath and os.path.exists(result_path):
                    final_video_path = result_path
                    logger.info(f"✅ تم تطبيق اللوجو")

            # 5. رفع الفيديو
            await processing_message.edit_text(
                "📤 **جاري الرفع إلى تيليجرام...**\n\n🚀 قريباً جداً...",
                parse_mode='Markdown'
            )
            
            file_size = os.path.getsize(final_video_path)
            if file_size > 2 * 1024 * 1024 * 1024:
                await processing_message.edit_text(
                    "❌ **الملف كبير جداً!**\n\nالحجم أكبر من 2GB. تيليجرام لا يسمح بهذا الحجم.",
                    parse_mode='Markdown'
                )
                return
            
            # إعداد caption جميل
            sub_emoji = "💎" if is_subscribed_user else "🆓"
            file_size_mb = file_size / (1024 * 1024)
            
            caption_text = (
                f"{platform_emoji} **{title}**\n\n"
                f"👤 {uploader}\n"
                f"⏱️ {duration_formatted} | 📦 {file_size_mb:.1f} MB\n"
                f"{sub_emoji} تم بواسطة @{context.bot.username}"
            )
            
            # إرسال الفيديو
            with open(final_video_path, 'rb') as video_file:
                sent_message = await context.bot.send_video(
                    chat_id=update.effective_chat.id, 
                    video=video_file, 
                    caption=caption_text,
                    parse_mode='Markdown',
                    reply_to_message_id=update.message.message_id,
                    supports_streaming=True,
                    width=info_dict.get('width'),
                    height=info_dict.get('height'),
                    duration=duration
                )
            
            logger.info(f"✅ تم الإرسال بنجاح للمستخدم {user_id}")
            
            # 6. إعادة توجيه للقناة
            log_channel_videos_id = config.get("LOG_CHANNEL_ID_VIDEOS")
            if log_channel_videos_id and sent_message:
                try:
                    await sent_message.forward(chat_id=log_channel_videos_id)
                except Exception as e:
                    logger.error(f"❌ فشل التوجيه: {e}")

            # إرسال للوج
            await send_log_to_channel(context, user, info_dict, final_video_path)

            # حذف رسالة المعالجة
            try:
                await processing_message.delete()
            except:
                pass
            
            # زيادة العداد
            if not is_user_admin and not is_subscribed_user:
                increment_download_count(user_id)
                remaining = FREE_USER_DOWNLOAD_LIMIT - get_daily_download_count(user_id)
                if remaining > 0:
                    await update.message.reply_text(
                        f"ℹ️ **تبقى لك `{remaining}` تحميلات مجانية اليوم**",
                        parse_mode='Markdown'
                    )
                elif remaining == 0:
                    keyboard = [[InlineKeyboardButton(
                        "🌟 اشترك للتحميل بلا حدود",
                        url=get_message(lang, "subscribe_link")
                    )]]
                    await update.message.reply_text(
                        "⚠️ **انتهت تحميلاتك المجانية اليوم!**\n\nاشترك للحصول على تحميلات غير محدودة.",
                        reply_markup=InlineKeyboardMarkup(keyboard),
                        parse_mode='Markdown'
                    )

    except yt_dlp.utils.DownloadError as e:
        logger.error(f"❌ yt-dlp Error: {e}")
        error_text = "❌ **فشل التحميل!**\n\n"
        
        error_str = str(e).lower()
        if "unsupported url" in error_str:
            error_text += "المنصة غير مدعومة"
        elif "private" in error_str:
            error_text += "الفيديو خاص"
        elif "unavailable" in error_str:
            error_text += "الفيديو غير متاح"
        elif "copyright" in error_str:
            error_text += "الفيديو محمي بحقوق النشر"
        else:
            error_text += f"`{str(e)[:150]}`"
        
        try:
            await processing_message.edit_text(error_text, parse_mode='Markdown')
        except:
            await update.message.reply_text(error_text, parse_mode='Markdown')
            
    except Exception as e:
        logger.error(f"❌ خطأ غير متوقع: {e}", exc_info=True)
        error_text = f"❌ **خطأ غير متوقع!**\n\n`{str(e)[:200]}`"
        
        try:
            await processing_message.edit_text(error_text, parse_mode='Markdown')
        except:
            await update.message.reply_text(error_text, parse_mode='Markdown')
            
    finally:
        # التنظيف
        for filepath in [new_filepath, temp_watermarked_path]:
            if filepath and os.path.exists(filepath):
                try:
                    os.remove(filepath)
                    logger.info(f"🗑️ تم حذف: {filepath}")
                except Exception as e:
                    logger.error(f"❌ فشل الحذف: {e}")