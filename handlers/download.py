import os
import asyncio
import time
import requests
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
from utils import get_message, clean_filename, get_config, format_file_size, format_duration

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

LOG_CHANNEL_ID = os.getenv("LOG_CHANNEL_ID")
FREE_USER_DOWNLOAD_LIMIT = 5
VIDEO_PATH = 'videos'

if not os.path.exists(VIDEO_PATH):
    os.makedirs(VIDEO_PATH)

class DownloadProgressTracker:
    """تتبع تقدم التحميل مع عداد نسبة مئوية"""
    def __init__(self, message, lang):
        self.message = message
        self.lang = lang
        self.last_update_time = 0
        self.last_percentage = -1
        
    def progress_hook(self, d):
        if d['status'] == 'downloading':
            try:
                current_time = time.time()
                if current_time - self.last_update_time < 2:
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
                    downloaded_mb = downloaded / (1024 * 1024)
                    total_mb = total / (1024 * 1024)
                    speed_text = f"{speed / 1024 / 1024:.2f} MB/s" if speed else "..."
                    
                    progress_bar = self._create_progress_bar(percentage)
                    
                    if percentage < 25:
                        status_emoji = "📥"
                    elif percentage < 50:
                        status_emoji = "⬇️"
                    elif percentage < 75:
                        status_emoji = "⚡"
                    elif percentage < 95:
                        status_emoji = "🔄"
                    else:
                        status_emoji = "✨"
                    
                    update_text = (
                        f"{status_emoji} جاري التحميل...\n\n"
                        f"{progress_bar}\n\n"
                        f"📊 {percentage}%\n"
                        f"📦 {downloaded_mb:.1f} / {total_mb:.1f} MB\n"
                        f"⚡ {speed_text}"
                    )
                    
                    try:
                        loop = asyncio.get_event_loop()
                        loop.create_task(self.message.edit_text(update_text))
                    except:
                        pass
                        
            except Exception as e:
                logger.warning(f"خطأ في تحديث التقدم: {e}")
    
    def _create_progress_bar(self, percentage):
        filled = int(percentage / 5)
        empty = 20 - filled
        bar = f"{'🟩' * filled}{'⬜' * empty}"
        return f"{bar} {percentage}%"

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
        f"✅ تحميل جديد\n\n"
        f"👤 بواسطة: {user_name}\n"
        f"🆔 ID: {user_id}\n"
        f"🔗 Username: {username}\n\n"
        f"🎬 العنوان: {video_title}\n"
        f"⏱️ المدة: {duration}s\n"
        f"📦 الحجم: {size_mb:.2f} MB\n"
        f"🌐 الرابط: {video_url}"
    )

    try:
        with open(file_path, 'rb') as video_file:
            await context.bot.send_video(
                chat_id=LOG_CHANNEL_ID,
                video=video_file,
                caption=log_caption[:1024]
            )
    except Exception as e:
        logger.error(f"❌ فشل إرسال الفيديو إلى قناة السجل: {e}")

async def show_quality_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, url: str, info_dict: dict):
    """عرض قائمة اختيار الجودة - مبسطة"""
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
        [InlineKeyboardButton("📱 جودة متوسطة (أسرع)", callback_data="quality_medium")],
        [InlineKeyboardButton("🎵 صوت فقط MP3", callback_data="quality_audio")],
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message_text = (
        f"📺 اختر الجودة:\n\n"
        f"🎬 {title}\n"
        f"⏱️ {duration}"
    )
    
    await update.message.reply_text(
        message_text,
        reply_markup=reply_markup
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
    
    await query.edit_message_text("⏳ جاري التحضير...")
    
    await download_video_with_quality(update, context, url, info_dict, quality_choice)

def get_ydl_opts_for_platform(url: str, quality: str = 'best'):
    """
    إعدادات yt-dlp محسّنة حسب المنصة
    """
    # تحديد المنصة
    is_facebook = 'facebook.com' in url or 'fb.watch' in url or 'fb.com' in url
    is_instagram = 'instagram.com' in url
    is_tiktok = 'tiktok.com' in url or 'vm.tiktok.com' in url or 'vt.tiktok.com' in url
    
    # الجودة
    quality_formats = {
        'best': 'bestvideo[height<=1080]+bestaudio/best[height<=1080]/best',
        'medium': 'bestvideo[height<=720]+bestaudio/best[height<=720]/best',
        'audio': 'bestaudio/best'
    }
    
    format_choice = quality_formats.get(quality, 'best')
    
    # إعدادات أساسية
    ydl_opts = {
        'format': format_choice,
        'outtmpl': os.path.join(VIDEO_PATH, '%(title)s.%(ext)s'),
        'quiet': False,
        'no_warnings': False,
        'extract_flat': False,
        'ignoreerrors': False,
        'nocheckcertificate': True,
        # تحسينات السرعة
        'concurrent_fragment_downloads': 5,
        'retries': 10,
        'fragment_retries': 10,
        'http_chunk_size': 10485760,
        'buffersize': 1024 * 512,
    }
    
    # إعدادات خاصة لـ Facebook
    if is_facebook:
        ydl_opts.update({
            'format': 'best',  # Facebook يحتاج 'best' فقط
            'extractor_args': {
                'facebook': {
                    'timeout': 60
                }
            },
            # User-Agent مهم لـ Facebook
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-us,en;q=0.5',
                'Sec-Fetch-Mode': 'navigate',
            }
        })
    
    # إعدادات خاصة لـ Instagram
    elif is_instagram:
        ydl_opts.update({
            'format': 'best',
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1',
                'Accept': '*/*',
                'Accept-Language': 'en-US,en;q=0.5',
                'X-IG-App-ID': '936619743392459',
            },
            'extractor_args': {
                'instagram': {
                    'timeout': 60
                }
            }
        })
    
    # إعدادات خاصة لـ TikTok - مُحسّنة للصور والفيديوهات
    elif is_tiktok:
        ydl_opts.update({
            'format': 'best',
            # إعدادات مهمة لتيك توك
            'writesubtitles': False,
            'writethumbnail': False,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Referer': 'https://www.tiktok.com/',
            },
            'extractor_args': {
                'tiktok': {
                    'api_hostname': 'api16-normal-c-useast1a.tiktokv.com'
                }
            }
        })
    
    # إعدادات الصوت
    if quality == 'audio':
        ydl_opts['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }]
    
    return ydl_opts

async def download_video_with_quality(update: Update, context: ContextTypes.DEFAULT_TYPE, url: str, info_dict: dict, quality: str):
    """تحميل الفيديو بالجودة المحددة"""
    user = update.effective_user
    user_id = user.id
    lang = get_user_language(user_id)
    
    ydl_opts = get_ydl_opts_for_platform(url, quality)
    
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
        text="📥 بدء التحميل...\n\n⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜ 0%"
    )
    
    new_filepath = None
    temp_watermarked_path = None
    
    # التحقق إذا كان المحتوى صورة وليس فيديو
    is_image_post = False
    
    # طريقة 1: فحص duration - إذا كانت 0 قد يكون صور
    duration = info_dict.get('duration', None)
    
    # طريقة 2: فحص الصيغ المتاحة
    if 'formats' in info_dict and info_dict.get('formats'):
        has_video = any('vcodec' in fmt and fmt.get('vcodec') != 'none' 
                       for fmt in info_dict['formats'])
        has_image = any('ext' in fmt and fmt.get('ext') in ['jpg', 'jpeg', 'png', 'webp'] 
                       for fmt in info_dict['formats'])
        
        # إذا كان فيه صور وما فيه فيديو = منشور صور
        if has_image and not has_video:
            is_image_post = True
            logger.info("✅ تم اكتشاف منشور صور")
    
    # طريقة 3: فحص نوع الملف في thumbnail أو entries
    if not is_image_post and 'entries' in info_dict:
        # بعض المنصات تضع الصور في entries
        entries = info_dict.get('entries', [])
        if entries and all(e.get('ext') in ['jpg', 'jpeg', 'png', 'webp'] for e in entries if e):
            is_image_post = True
            logger.info("✅ تم اكتشاف صور في entries")
    
    # طريقة 4: فحص خاص لتيك توك
    url_lower = url.lower()
    if 'tiktok.com' in url_lower and duration == 0:
        is_image_post = True
        logger.info("✅ تيك توك بدون مدة - احتمال صور")
    
    try:
        # إذا كان منشور صور من تيك توك أو انستقرام
        if is_image_post:
            await processing_message.edit_text("📷 اكتشفت صوراً! جاري التحميل...")
            
            loop = asyncio.get_event_loop()
            
            # إعداد خاص للصور - نضيف write_all_thumbnails لتيك توك
            image_ydl_opts = ydl_opts.copy()
            image_ydl_opts.update({
                'writethumbnail': True,
                'write_all_thumbnails': True,
                'skip_download': False,
            })
            
            # تحميل الصور
            try:
                with yt_dlp.YoutubeDL(image_ydl_opts) as ydl:
                    await loop.run_in_executor(None, lambda: ydl.download([url]))
                logger.info("✅ تم تحميل المحتوى من yt-dlp")
            except Exception as e:
                logger.error(f"❌ خطأ في تحميل الصور: {e}")
                raise
            
            # البحث عن الصور المحملة
            image_files = []
            current_time = time.time()
            
            for file in os.listdir(VIDEO_PATH):
                file_path = os.path.join(VIDEO_PATH, file)
                # التحقق أنها صورة ومحملة حديثاً (آخر دقيقة)
                if (file.endswith(('.jpg', '.jpeg', '.png', '.webp')) and 
                    os.path.isfile(file_path) and 
                    os.path.getmtime(file_path) > (current_time - 60)):
                    image_files.append(file_path)
            
            logger.info(f"📸 تم العثور على {len(image_files)} صورة")
            
            if not image_files:
                # محاولة بديلة: تحميل thumbnail كصورة
                logger.warning("⚠️ لم يتم العثور على صور، محاولة تحميل thumbnail...")
                thumbnail_url = info_dict.get('thumbnail')
                if thumbnail_url:
                    try:
                        import requests
                        response = requests.get(thumbnail_url, timeout=10)
                        if response.status_code == 200:
                            thumb_path = os.path.join(VIDEO_PATH, f"thumbnail_{int(time.time())}.jpg")
                            with open(thumb_path, 'wb') as f:
                                f.write(response.content)
                            image_files.append(thumb_path)
                            logger.info("✅ تم تحميل thumbnail كصورة")
                    except Exception as e:
                        logger.error(f"❌ فشل تحميل thumbnail: {e}")
            
            if not image_files:
                raise FileNotFoundError("لم يتم العثور على صور محملة")
            
            title = info_dict.get('title', 'صور')
            uploader = info_dict.get('uploader', 'Unknown')[:40]
            
            # إرسال الصور للمستخدم
            await processing_message.edit_text(f"📤 جاري رفع {len(image_files)} صورة...")
            
            caption_text = (
                f"📷 {title[:50]}\n\n"
                f"👤 {uploader}\n"
                f"🖼️ عدد الصور: {len(image_files)}\n"
                f"{'💎 VIP' if is_subscribed_user else '🆓 مجاني'}\n\n"
                f"✨ بواسطة @{context.bot.username}"
            )
            
            # إرسال الصور (واحدة تلو الأخرى أو كمجموعة)
            if len(image_files) == 1:
                with open(image_files[0], 'rb') as photo:
                    await context.bot.send_photo(
                        chat_id=update.effective_chat.id,
                        photo=photo,
                        caption=caption_text[:1024],
                        reply_to_message_id=update.effective_message.message_id
                    )
            else:
                # إرسال كمجموعة (MediaGroup)
                from telegram import InputMediaPhoto
                media_group = []
                
                for idx, img_path in enumerate(image_files[:10]):  # تيليجرام يسمح بـ 10 صور كحد أقصى
                    with open(img_path, 'rb') as photo:
                        if idx == 0:
                            media_group.append(InputMediaPhoto(media=photo.read(), caption=caption_text[:1024]))
                        else:
                            media_group.append(InputMediaPhoto(media=photo.read()))
                
                await context.bot.send_media_group(
                    chat_id=update.effective_chat.id,
                    media=media_group,
                    reply_to_message_id=update.effective_message.message_id
                )
            
            logger.info(f"✅ تم إرسال {len(image_files)} صورة")
            
            try:
                await processing_message.delete()
            except:
                pass
            
            # تحديث عداد التحميلات
            if not is_user_admin and not is_subscribed_user:
                increment_download_count(user_id)
                remaining = FREE_USER_DOWNLOAD_LIMIT - get_daily_download_count(user_id)
                if remaining > 0:
                    await context.bot.send_message(
                        chat_id=update.effective_chat.id,
                        text=f"ℹ️ تبقى لك {remaining} تحميلات مجانية اليوم"
                    )
            
            # حذف الصور المؤقتة
            for img_file in image_files:
                try:
                    os.remove(img_file)
                    logger.info(f"🗑️ تم حذف: {img_file}")
                except Exception as e:
                    logger.error(f"❌ فشل حذف الصورة: {e}")
            
            return
        
        # إذا كان فيديو عادي - الكود القديم
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
        
        # التحقق من حالة اللوجو
        from database import is_logo_enabled
        logo_enabled = is_logo_enabled()
        
        logo_path = config.get("LOGO_PATH")
        final_video_path = new_filepath
        
        if not is_audio and logo_enabled and not is_subscribed_user and not is_user_admin and logo_path and os.path.exists(logo_path):
            from utils import apply_animated_watermark
            
            temp_watermarked_path = new_filepath.replace(f".{ext}", f"_watermarked.{ext}")
            result_path = apply_animated_watermark(new_filepath, temp_watermarked_path, logo_path)
            
            if result_path != new_filepath and os.path.exists(result_path):
                final_video_path = result_path
                logger.info(f"✨ تم تطبيق اللوجو المتحرك")
        
        file_size = os.path.getsize(final_video_path)
        total_mb = file_size / (1024 * 1024)
        
        await processing_message.edit_text(
            f"📤 جاري الرفع...\n\n"
            f"⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜ 0%\n\n"
            f"📦 الحجم: {total_mb:.1f} MB"
        )
        
        if file_size > 2 * 1024 * 1024 * 1024:
            await processing_message.edit_text("❌ الملف كبير جداً! (أكثر من 2GB)")
            return
        
        duration = info_dict.get('duration', 0)
        uploader = info_dict.get('uploader', 'Unknown')[:40]
        
        caption_text = (
            f"🎬 {title[:50]}\n\n"
            f"👤 {uploader}\n"
            f"⏱️ {format_duration(duration)} | 📦 {format_file_size(file_size)}\n"
            f"{'🎵' if is_audio else '🎥'} {'💎 VIP' if is_subscribed_user else '🆓 مجاني'}\n\n"
            f"✨ بواسطة @{context.bot.username}"
        )
        
        # محاكاة تقدم الرفع
        for progress in [25, 50, 75]:
            await asyncio.sleep(0.3)
            filled = int(progress / 5)
            empty = 20 - filled
            bar = f"{'🟩' * filled}{'⬜' * empty}"
            
            try:
                await processing_message.edit_text(
                    f"📤 جاري الرفع...\n\n"
                    f"{bar} {progress}%\n\n"
                    f"📦 الحجم: {total_mb:.1f} MB"
                )
            except:
                pass
        
        with open(final_video_path, 'rb') as file:
            if is_audio:
                await context.bot.send_audio(
                    chat_id=update.effective_chat.id,
                    audio=file,
                    caption=caption_text[:1024],
                    reply_to_message_id=update.effective_message.message_id
                )
            else:
                sent_message = await context.bot.send_video(
                    chat_id=update.effective_chat.id,
                    video=file,
                    caption=caption_text[:1024],
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
                    text=f"ℹ️ تبقى لك {remaining} تحميلات مجانية اليوم"
                )
        
        await send_log_to_channel(context, user, info_dict, final_video_path)
        
    except Exception as e:
        logger.error(f"❌ خطأ: {e}", exc_info=True)
        error_text = f"❌ فشل التحميل!\n\nتأكد من أن الرابط صحيح ويمكن الوصول إليه."
        
        try:
            await processing_message.edit_text(error_text)
        except:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=error_text
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
    """معالج تحميل الفيديوهات - يدعم جميع المنصات"""
    user = update.message.from_user
    user_id = user.id
    url = update.message.text.strip()
    lang = get_user_language(user_id)
    user_data = get_user(user_id)
    
    if not user_data:
        await update.message.reply_text("❌ لم يتم العثور على بياناتك. الرجاء إرسال /start")
        return

    is_user_admin = is_admin(user_id)
    is_subscribed_user = is_subscribed(user_id)
    config = get_config()
    
    if is_adult_content(url):
        await update.message.reply_text("🚫 محتوى محظور! هذا الموقع محظور.")
        return
    
    if not is_user_admin and not is_subscribed_user:
        daily_count = get_daily_download_count(user_id)
        if daily_count >= FREE_USER_DOWNLOAD_LIMIT:
            keyboard = [[InlineKeyboardButton(
                "⭐ اشترك الآن",
                url="https://t.me/YourChannelHere"
            )]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                "🚫 وصلت للحد اليومي (5 فيديوهات). اشترك للتحميل بلا حدود!",
                reply_markup=reply_markup
            )
            return
    
    processing_message = await update.message.reply_text("🔍 جاري التحليل...")
    
    try:
        # إعدادات التحليل
        ydl_opts = get_ydl_opts_for_platform(url)
        ydl_opts['skip_download'] = True  # فقط للتحليل
        
        loop = asyncio.get_event_loop()
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = await loop.run_in_executor(None, lambda: ydl.extract_info(url, download=False))
        
        title = info_dict.get('title', 'فيديو')
        duration = info_dict.get('duration', 0)
        
        if is_adult_content(url, title):
            await processing_message.edit_text("🚫 محتوى محظور!")
            return
        
        max_free_duration = config.get("MAX_FREE_DURATION", 600)
        if not is_user_admin and not is_subscribed_user and duration and duration > max_free_duration:
            keyboard = [[InlineKeyboardButton(
                "⭐ اشترك الآن",
                url="https://t.me/YourChannelHere"
            )]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await processing_message.edit_text(
                f"⏰ الفيديو طويل! (أكثر من {max_free_duration // 60} دقائق). اشترك لتحميل فيديوهات طويلة!",
                reply_markup=reply_markup
            )
            return
        
        await processing_message.delete()
        
        await show_quality_menu(update, context, url, info_dict)
        
    except Exception as e:
        logger.error(f"❌ خطأ في التحليل: {e}", exc_info=True)
        error_msg = str(e)
        
        # رسائل خطأ مخصصة
        if 'private' in error_msg.lower() or 'login' in error_msg.lower():
            await processing_message.edit_text(
                "❌ الفيديو خاص أو يحتاج تسجيل دخول!\n\n"
                "💡 تأكد من أن الفيديو عام ويمكن للجميع مشاهدته."
            )
        elif 'unavailable' in error_msg.lower():
            await processing_message.edit_text(
                "❌ الفيديو غير متاح أو تم حذفه!"
            )
        elif 'geo' in error_msg.lower():
            await processing_message.edit_text(
                "❌ الفيديو محظور جغرافياً في هذه المنطقة!"
            )
        else:
            await processing_message.edit_text(
                f"❌ فشل التحليل!\n\n"
                f"تأكد من أن الرابط صحيح ويمكن الوصول إليه.\n\n"
                f"المنصات المدعومة:\n"
                f"✅ YouTube\n"
                f"✅ Facebook\n"
                f"✅ Instagram\n"
                f"✅ TikTok\n"
                f"✅ Twitter/X\n"
                f"✅ +1000 موقع آخر"
            )