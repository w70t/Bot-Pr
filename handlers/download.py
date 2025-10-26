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

async def send_log_to_channel(context: ContextTypes.DEFAULT_TYPE, user, video_info: dict, file_path: str):
    """
    إرسال سجل التحميل إلى قناة اللوج
    """
    if not LOG_CHANNEL_ID:
        return

    user_id = user.id
    user_name = user.full_name
    username = f"@{user.username}" if user.username else "لا يوجد"
    
    video_title = video_info.get('title', 'N/A')
    video_url = video_info.get('webpage_url', 'N/A')

    log_caption = (
        f"✅ تحميل جديد\n\n"
        f"👤 بواسطة: {user_name}\n"
        f"🆔 ID: {user_id}\n"
        f"🔗 Username: {username}\n\n"
        f"🎬 العنوان: {video_title}\n"
        f"🌐 الرابط: {video_url}"
    )

    try:
        with open(file_path, 'rb') as video_file:
            await context.bot.send_video(
                chat_id=LOG_CHANNEL_ID,
                video=video_file,
                caption=log_caption
            )
    except Exception as e:
        logger.error(f"❌ فشل إرسال الفيديو إلى قناة السجل: {e}")
        try:
            await context.bot.send_message(
                chat_id=LOG_CHANNEL_ID,
                text=log_caption,
                disable_web_page_preview=True
            )
        except Exception as text_e:
            logger.error(f"❌ فشل إرسال السجل النصي أيضاً: {text_e}")

async def handle_download(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    معالج تحميل الفيديوهات الرئيسي
    """
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

    # 2. التحقق من حد التحميل اليومي للمستخدمين غير المشتركين
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

    processing_message = await update.message.reply_text(get_message(lang, "processing"))
    
    new_filepath = None
    temp_watermarked_path = None
    
    try:
        # إعدادات yt-dlp
        ydl_opts = {
            'format': 'best[ext=mp4][height<=720]/best[ext=mp4]/best',
            'outtmpl': os.path.join(VIDEO_PATH, '%(title)s.%(ext)s'),
            'noplaylist': True,
            'quiet': True,
            'no_warnings': True,
            'merge_output_format': 'mp4',
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            loop = asyncio.get_event_loop()
            
            # جلب معلومات الفيديو بدون تحميل
            info_dict = await loop.run_in_executor(
                None, 
                lambda: ydl.extract_info(url, download=False)
            )
            
            duration = info_dict.get('duration', 0)
            
            # 3. التحقق من حد المدة للمستخدمين غير المشتركين
            max_free_duration = config.get("MAX_FREE_DURATION", 300)  # 5 دقائق افتراضياً
            
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
            await processing_message.edit_text(get_message(lang, "downloading"))
            await loop.run_in_executor(None, lambda: ydl.download([url]))
            
            # إعداد مسارات الملفات
            original_filepath = ydl.prepare_filename(info_dict)
            title = info_dict.get('title', 'video')
            cleaned_title = clean_filename(title)
            new_filepath = os.path.join(VIDEO_PATH, f"{cleaned_title}.mp4")
            
            # إعادة تسمية الملف
            if os.path.exists(original_filepath):
                if os.path.exists(new_filepath) and original_filepath != new_filepath:
                    os.remove(new_filepath)
                os.rename(original_filepath, new_filepath)
            
            if not os.path.exists(new_filepath):
                raise FileNotFoundError(f"الفيديو المحمل غير موجود في: {new_filepath}")

            await processing_message.edit_text(get_message(lang, "uploading"))
            
            # 4. تطبيق اللوجو (Watermark)
            # المنطق الصحيح: اللوجو للمستخدمين المجانيين فقط!
            logo_path = config.get("LOGO_PATH")
            final_video_path = new_filepath  # افتراضياً بدون لوجو
            
            # إضافة اللوجو للمستخدمين المجانيين (غير المشتركين)
            if not is_subscribed_user and not is_user_admin and logo_path and os.path.exists(logo_path):
                await processing_message.edit_text(get_message(lang, "applying_watermark"))
                temp_watermarked_path = new_filepath.replace(".mp4", "_watermarked.mp4")
                
                result_path = apply_watermark(new_filepath, temp_watermarked_path, logo_path)
                
                if result_path != new_filepath and os.path.exists(result_path):
                    final_video_path = result_path
                    logger.info(f"✅ تم تطبيق اللوجو بنجاح للمستخدم المجاني {user_id}")
                else:
                    logger.warning(f"⚠️ فشل تطبيق اللوجو للمستخدم {user_id}. إرسال الملف الأصلي.")
                    final_video_path = new_filepath
            else:
                if is_subscribed_user:
                    logger.info(f"✨ المستخدم {user_id} مشترك - فيديو نظيف بدون لوجو")

            # 5. إرسال الفيديو للمستخدم
            caption_text = f"🎬 {title}\n\n✨ تم التحميل بواسطة @{context.bot.username}"
            
            # التحقق من حجم الملف (حد تيليجرام 2GB)
            file_size = os.path.getsize(final_video_path)
            if file_size > 2 * 1024 * 1024 * 1024:  # 2GB
                await processing_message.edit_text(get_message(lang, "file_too_large"))
                return
            
            with open(final_video_path, 'rb') as video_file:
                sent_message = await context.bot.send_video(
                    chat_id=update.effective_chat.id, 
                    video=video_file, 
                    caption=caption_text,
                    reply_to_message_id=update.message.message_id
                )
            
            # 6. إعادة توجيه الفيديو إلى القناة الخاصة (إذا وُجدت)
            log_channel_videos_id = config.get("LOG_CHANNEL_ID_VIDEOS")
            if log_channel_videos_id and sent_message:
                try:
                    await sent_message.forward(chat_id=log_channel_videos_id)
                    logger.info(f"✅ تم إعادة توجيه الفيديو إلى القناة الخاصة: {log_channel_videos_id}")
                except Exception as forward_e:
                    logger.error(f"❌ فشل إعادة توجيه الفيديو: {forward_e}")

            # إرسال سجل إلى قناة السجل القديمة (إذا كانت موجودة)
            await send_log_to_channel(context, user, info_dict, final_video_path)

            # حذف الملف المؤقت ذي العلامة المائية إذا تم إنشاؤه
            if temp_watermarked_path and os.path.exists(temp_watermarked_path):
                os.remove(temp_watermarked_path)
            
            await processing_message.delete()
            
            # زيادة عداد التحميلات (إلا للمدراء والمشتركين)
            if not is_user_admin and not is_subscribed_user:
                increment_download_count(user_id)

    except yt_dlp.utils.DownloadError as e:
        logger.error(f"خطأ في yt-dlp: {e}")
        error_message = get_message(lang, "download_failed")
        
        if "Unsupported URL" in str(e) or "not supported" in str(e).lower():
            error_message = get_message(lang, "unsupported_platform")
        
        try:
            await processing_message.edit_text(error_message)
        except Exception:
            await update.message.reply_text(error_message)
            
    except Exception as e:
        logger.error(f"خطأ غير متوقع في handle_download: {e}", exc_info=True)
        error_message = get_message(lang, "download_failed")
        
        try:
            await processing_message.edit_text(error_message)
        except Exception:
            await update.message.reply_text(error_message)
            
    finally:
        # تنظيف: حذف الملف الأصلي الذي تم تنزيله
        if new_filepath and os.path.exists(new_filepath):
            try:
                os.remove(new_filepath)
                logger.info(f"🗑️ تم حذف الملف المؤقت: {new_filepath}")
            except Exception as e:
                logger.error(f"❌ فشل حذف الملف المؤقت: {e}")
        
        # حذف الملف ذي العلامة المائية إذا كان موجوداً
        if temp_watermarked_path and os.path.exists(temp_watermarked_path):
            try:
                os.remove(temp_watermarked_path)
                logger.info(f"🗑️ تم حذف الملف المائي المؤقت: {temp_watermarked_path}")
            except Exception as e:
                logger.error(f"❌ فشل حذف الملف المائي المؤقت: {e}")