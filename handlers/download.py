import os
import asyncio
import time
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler
from telegram.constants import ParseMode
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
from utils import get_message, clean_filename, get_config, apply_watermark, format_file_size, format_duration

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

LOG_CHANNEL_ID = os.getenv("LOG_CHANNEL_ID")
FREE_USER_DOWNLOAD_LIMIT = 5
VIDEO_PATH = 'videos'

if not os.path.exists(VIDEO_PATH):
    os.makedirs(VIDEO_PATH)

class DownloadProgressTracker:
    """تتبع تقدم التحميل"""
    def __init__(self, message, lang):
        self.message = message
        self.lang = lang
        self.last_update_time = 0
        self.last_percentage = -1
        
    def progress_hook(self, d):
        if d['status'] == 'downloading':
            try:
                current_time = time.time()
                if current_time - self.last_update_time < 3:
                    return
                
                downloaded = d.get('downloaded_bytes', 0)
                total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
                
                if total > 0:
                    percentage = int((downloaded / total) * 100)
                    
                    if abs(percentage - self.last_percentage) < 5:
                        return
                    
                    self.last_percentage = percentage
                    self.last_update_time = current_time
                    
                    speed = d.get('speed', 0)
                    eta = d.get('eta', 0)
                    
                    downloaded_mb = downloaded / (1024 * 1024)
                    total_mb = total / (1024 * 1024)
                    speed_text = f"{speed / 1024 / 1024:.2f} MB/s" if speed else "..."
                    
                    progress_bar = self._create_progress_bar(percentage)
                    status_emoji = "🔄" if percentage < 50 else "⚡" if percentage < 90 else "🎉"
                    
                    update_text = (
                        f"{status_emoji} **جاري التحميل...**\n\n"
                        f"{progress_bar}\n\n"
                        f"📊 **التقدم:** `{percentage}%`\n"
                        f"📦 **المحمّل:** `{downloaded_mb:.1f} MB` / `{total_mb:.1f} MB`\n"
                        f"⚡ **السرعة:** `{speed_text}`\n"
                        f"⏱️ **المتبقي:** `{self._format_eta(eta)}`"
                    )
                    
                    try:
                        loop = asyncio.get_event_loop()
                        loop.create_task(self.message.edit_text(update_text, parse_mode='Markdown'))
                    except:
                        pass
                        
            except Exception as e:
                logger.warning(f"خطأ في تحديث التقدم: {e}")
    
    def _create_progress_bar(self, percentage):
        filled = int(percentage / 5)
        empty = 20 - filled
        bar = f"{'🟩' * filled}{'⬜' * empty}"
        return f"`[{percentage:3d}%]` {bar}"
    
    def _format_eta(self, eta_seconds):
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

def is_adult_content(url: str, title: str = "") -> bool:
    """التحقق من المحتوى الإباحي"""
    config = get_config()
    
    blocked_domains = config.get("BLOCKED_DOMAINS", [])
    for domain in blocked_domains:
        if domain.lower() in url.lower():
            return True
    
    adult_keywords = config.get("ADULT_CONTENT_KEYWORDS", [])
    text_to_check = (url + " " + title).lower()
    
    for keyword in adult_keywords:
        if keyword.lower() in text_to_check:
            return True
    
    return False

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

async def show_quality_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, url: str, info_dict: dict):
    """عرض قائمة اختيار الجودة"""
    user_id = update.effective_user.id
    lang = get_user_language(user_id)
    
    title = info_dict.get('title', 'فيديو')[:50]
    duration = format_duration(info_dict.get('duration', 0))
    
    context.user_data['pending_download'] = {
        'url': url,
        'info': info_dict
    }
    
    keyboard = [
        [InlineKeyboardButton("🌟 أفضل جودة", callback_data="quality_best")],
        [InlineKeyboardButton("📺 جودة عالية HD", callback_data="quality_high")],
        [InlineKeyboardButton("📱 جودة متوسطة", callback_data="quality_medium")],
        [InlineKeyboardButton("⚡ جودة منخفضة (سريع)", callback_data="quality_low")],
        [InlineKeyboardButton("🎵 صوت فقط MP3", callback_data="quality_audio")],
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message_text = get_message(lang, "quality_selection").format(
        title=title,
        duration=duration
    )
    
    await update.message.reply_text(
        message_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def handle_quality_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة اختيار الجودة"""
    query = update.callback_query
    await query.answer()
    
    quality_choice = query.data.replace("quality_", "")
    
    pending_data = context.user_data.get('pending_download')
    if not pending_data:
        await query.edit_message_text("❌ انتهت صلاحية الطلب. أرسل الرابط مرة أخرى.")
        return
    
    url = pending_data['url']
    info_dict = pending_data['info']
    
    del context.user_data['pending_download']
    
    await query.edit_message_text("⏳ **جاري التحميل بالجودة المختارة...**")
    
    await download_video_with_quality(update, context, url, info_dict, quality_choice)

async def download_video_with_quality(update: Update, context: ContextTypes.DEFAULT_TYPE, url: str, info_dict: dict, quality: str):
    """تحميل الفيديو بالجودة المحددة"""
    user = update.effective_user
    user_id = user.id
    lang = get_user_language(user_id)
    
    quality_formats = {
        'best': 'bestvideo+bestaudio/best',
        'high': 'bestvideo[height<=1080]+bestaudio/best[height<=1080]',
        'medium': 'bestvideo[height<=720]+bestaudio/best[height<=720]',
        'low': 'bestvideo[height<=480]+bestaudio/best[height<=480]',
        'audio': 'bestaudio/best'
    }
    
    format_choice = quality_formats.get(quality, 'best')
    
    ydl_opts = {
        'format': format_choice,
        'outtmpl': os.path.join(VIDEO_PATH, '%(title)s.%(ext)s'),
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
    }
    
    if quality == 'audio':
        ydl_opts['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }]
    
    await perform_download(update, context, url, info_dict, ydl_opts, is_audio=(quality=='audio'))

async def perform_download(update: Update, context: ContextTypes.DEFAULT_TYPE, url: str, info_dict: dict, ydl_opts: dict, is_audio: bool = False):
    """تنفيذ عملية التحميل"""
    user = update.effective_user
    user_id = user.id
    lang = get_user_language(user_id)
    
    is_user_admin = is_admin(user_id)
    is_subscribed_user = is_subscribed(user_id)
    config = get_config()
    
    processing_message = await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="📥 **بدء التحميل...**",
        parse_mode='Markdown'
    )
    
    new_filepath = None
    temp_watermarked_path = None
    
    try:
        loop = asyncio.get_event_loop()
        
        progress_tracker = DownloadProgressTracker(processing_message, lang)
        ydl_opts['progress_hooks'] = [progress_tracker.progress_hook]
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            await loop.run_in_executor(None, lambda: ydl.download([url]))
            
            original_filepath = ydl.prepare_filename(info_dict)
            title = info_dict.get('title', 'video')
            cleaned_title = clean_filename(title)
            
            ext = 'mp3' if is_audio else 'mp4'
            new_filepath = os.path.join(VIDEO_PATH, f"{cleaned_title}.{ext}")
            
            if os.path.exists(original_filepath):
                if os.path.exists(new_filepath) and original_filepath != new_filepath:
                    os.remove(new_filepath)
                os.rename(original_filepath, new_filepath)
            
            if not os.path.exists(new_filepath):
                raise FileNotFoundError(f"الملف غير موجود: {new_filepath}")
        
        logger.info(f"✅ تم التحميل: {new_filepath}")
        
        logo_path = config.get("LOGO_PATH")
        final_video_path = new_filepath
        
        if not is_audio and not is_subscribed_user and not is_user_admin and logo_path and os.path.exists(logo_path):
            await processing_message.edit_text(
                "🎨 **إضافة اللوجو...**",
                parse_mode='Markdown'
            )
            
            temp_watermarked_path = new_filepath.replace(f".{ext}", f"_watermarked.{ext}")
            result_path = apply_watermark(new_filepath, temp_watermarked_path, logo_path)
            
            if result_path != new_filepath and os.path.exists(result_path):
                final_video_path = result_path
                logger.info(f"✅ تم تطبيق اللوجو")
        
        await processing_message.edit_text(
            "📤 **جاري الرفع...**",
            parse_mode='Markdown'
        )
        
        file_size = os.path.getsize(final_video_path)
        if file_size > 2 * 1024 * 1024 * 1024:
            await processing_message.edit_text(
                "❌ **الملف كبير جداً!** (أكثر من 2GB)",
                parse_mode='Markdown'
            )
            return
        
        duration = info_dict.get('duration', 0)
        uploader = info_dict.get('uploader', 'Unknown')
        
        caption_text = (
            f"🎬 **{title[:50]}**\n\n"
            f"👤 {uploader[:40]}\n"
            f"⏱️ {format_duration(duration)} | 📦 {format_file_size(file_size)}\n"
            f"{'🎵' if is_audio else '🎥'} {'💎 VIP' if is_subscribed_user else '🆓 مجاني'}\n\n"
            f"✨ بواسطة @{context.bot.username}"
        )
        
        with open(final_video_path, 'rb') as file:
            if is_audio:
                await context.bot.send_audio(
                    chat_id=update.effective_chat.id,
                    audio=file,
                    caption=caption_text,
                    parse_mode='Markdown',
                    reply_to_message_id=update.effective_message.message_id
                )
            else:
                sent_message = await context.bot.send_video(
                    chat_id=update.effective_chat.id,
                    video=file,
                    caption=caption_text,
                    parse_mode='Markdown',
                    reply_to_message_id=update.effective_message.message_id,
                    supports_streaming=True,
                    width=info_dict.get('width'),
                    height=info_dict.get('height'),
                    duration=duration
                )
                
                log_channel_videos_id = config.get("LOG_CHANNEL_ID_VIDEOS")
                if log_channel_videos_id and sent_message:
                    try:
                        await sent_message.forward(chat_id=log_channel_videos_id)
                    except Exception as e:
                        logger.error(f"❌ فشل التوجيه: {e}")
        
        logger.info(f"✅ تم الإرسال بنجاح")
        
        try:
            await processing_message.delete()
        except:
            pass
        
        if not is_user_admin and not is_subscribed_user:
            increment_download_count(user_id)
            remaining = FREE_USER_DOWNLOAD_LIMIT - get_daily_download_count(user_id)
            if remaining > 0:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=f"ℹ️ **تبقى لك `{remaining}` تحميلات مجانية اليوم**",
                    parse_mode='Markdown'
                )
        
        await send_log_to_channel(context, user, info_dict, final_video_path)
        
    except Exception as e:
        logger.error(f"❌ خطأ: {e}", exc_info=True)
        error_text = f"❌ **فشل التحميل!**\n\n`{str(e)[:200]}`"
        
        try:
            await processing_message.edit_text(error_text, parse_mode='Markdown')
        except:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=error_text,
                parse_mode='Markdown'
            )
    
    finally:
        for filepath in [new_filepath, temp_watermarked_path]:
            if filepath and os.path.exists(filepath):
                try:
                    os.remove(filepath)
                    logger.info(f"🗑️ تم حذف: {filepath}")
                except Exception as e:
                    logger.error(f"❌ فشل الحذف: {e}")

async def handle_download(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج تحميل الفيديوهات الرئيسي"""
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
    
    if is_adult_content(url):
        await update.message.reply_text(get_message(lang, "adult_content_detected"))
        return
    
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
    
    processing_message = await update.message.reply_text(
        get_message(lang, "processing"),
        parse_mode='Markdown'
    )
    
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
        }
        
        loop = asyncio.get_event_loop()
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = await loop.run_in_executor(None, lambda: ydl.extract_info(url, download=False))
        
        title = info_dict.get('title', 'فيديو')
        duration = info_dict.get('duration', 0)
        
        if is_adult_content(url, title):
            await processing_message.edit_text(get_message(lang, "adult_content_detected"))
            return
        
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
        
        await processing_message.delete()
        
        await show_quality_menu(update, context, url, info_dict)
        
    except Exception as e:
        logger.error(f"❌ خطأ: {e}")
        await processing_message.edit_text(
            f"❌ **فشل التحليل!**\n\n`{str(e)[:200]}`",
            parse_mode='Markdown'
        )