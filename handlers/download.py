import os
import asyncio
import telegram
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
import yt_dlp
import logging

from database import (
    is_subscribed,
    get_user,
    increment_download_count,
    get_user_language,
    is_admin
)
from utils import get_message, clean_filename, get_config, apply_watermark

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

LOG_CHANNEL_ID = os.getenv("LOG_CHANNEL_ID")
# تم نقل هذه المتغيرات إلى config.json
# MAX_VIDEO_DURATION = 300
FREE_USER_DOWNLOAD_LIMIT = 5
VIDEO_PATH = 'videos'

if not os.path.exists(VIDEO_PATH):
    os.makedirs(VIDEO_PATH)

async def send_log_to_channel(context: ContextTypes.DEFAULT_TYPE, user: dict, video_info: dict, file_path: str):
    if not LOG_CHANNEL_ID:
        return

    user_id = user.id
    user_name = user.full_name
    username = f"@{user.username}" if user.username else "لا يوجد"
    
    video_title = video_info.get('title', 'N/A')
    video_url = video_info.get('webpage_url', 'N/A')

    # --- ✨ التعديل هنا: استخدام نص عادي بدلاً من الماركدوان ✨ ---
    log_caption = (
        f"✅ تحميل جديد\n\n"
        f"👤 بواسطة: {user_name}\n"
        f"🆔: {user_id}\n"
        f"🔗: {username}\n\n"
        f"🎬: {video_title}\n"
        f"🌐: {video_url}"
    )

    try:
        with open(file_path, 'rb') as video_file:
            await context.bot.send_video(
                chat_id=LOG_CHANNEL_ID,
                video=video_file,
                caption=log_caption
                # لا نستخدم parse_mode هنا
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
            logger.error(f"❌ فشل إرسال السجل النصي أيضًا: {text_e}")

async def handle_download(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    
    # 1. التحقق من حظر المواقع الإباحية
    config = get_config()
    blocked_domains = config.get("BLOCKED_DOMAINS", [])
    for domain in blocked_domains:
        if domain in url:
            await update.message.reply_text(get_message(lang, "blocked_domain_message"))
            return

    # 2. التحقق من حد التحميل اليومي للمستخدمين غير المشتركين
    if not is_user_admin and not is_subscribed_user and user_data.get('download_count', 0) >= FREE_USER_DOWNLOAD_LIMIT:
        keyboard = [[InlineKeyboardButton(get_message(lang, "subscribe_button_text"), url=get_message(lang, "subscribe_link"))]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(get_message(lang, "limit_reached"), reply_markup=reply_markup)
        return

    processing_message = await update.message.reply_text(get_message(lang, "processing"))
    
    new_filepath = None
    try:
        ydl_opts = {
            'format': 'best[ext=mp4][height<=720]/best[ext=mp4]/best',
            'outtmpl': os.path.join(VIDEO_PATH, '%(title)s.%(ext)s'),
            'noplaylist': True, 'quiet': True, 'merge_output_format': 'mp4',
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            loop = asyncio.get_event_loop()
            info_dict = await loop.run_in_executor(None, lambda: ydl.extract_info(url, download=False))
            
            duration = info_dict.get('duration', 0)
            
            # 3. التحقق من حد المدة للمستخدمين غير المشتركين
            max_free_duration = config.get("MAX_FREE_DURATION", 300) # 5 minutes default
            if not is_user_admin and not is_subscribed_user and duration > max_free_duration:
                keyboard = [[InlineKeyboardButton(get_message(lang, "subscribe_button_text"), url=get_message(lang, "subscribe_link"))]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await processing_message.edit_text(
                    get_message(lang, "duration_limit_exceeded").format(limit=max_free_duration // 60),
                    reply_markup=reply_markup
                )
                return

            await processing_message.edit_text(get_message(lang, "downloading"))
            await loop.run_in_executor(None, lambda: ydl.download([url]))
            
            original_filepath = ydl.prepare_filename(info_dict)
            title = info_dict.get('title', 'video')
            cleaned_title = clean_filename(title)
            new_filepath = os.path.join(VIDEO_PATH, f"{cleaned_title}.mp4")
            
            if os.path.exists(original_filepath):
                if os.path.exists(new_filepath) and original_filepath != new_filepath:
                    os.remove(new_filepath)
                os.rename(original_filepath, new_filepath)
            
            if not os.path.exists(new_filepath):
                raise FileNotFoundError(f"Downloaded video not found at {new_filepath}")

            await processing_message.edit_text(get_message(lang, "uploading"))
            
            # 4. تطبيق اللوجو (Watermark)
            # يتم تطبيق اللوجو فقط إذا كان المستخدم مشتركًا
            config = get_config() # إعادة تحميل الإعدادات لضمان الحصول على LOGO_PATH
            logo_path = config.get("LOGO_PATH")
            temp_watermarked_path = new_filepath # الافتراضي هو الملف بدون لوجو
            
            # التحقق من حالة الاشتراك لتطبيق اللوجو
            if is_subscribed_user and logo_path and os.path.exists(logo_path):
                await processing_message.edit_text(get_message(lang, "applying_watermark"))
                temp_watermarked_path = new_filepath.replace(".mp4", "_watermarked.mp4")
                # يمكن إضافة خيارات لتخصيص اللوجو هنا (الموقع، الحجم) إذا لزم الأمر
                temp_watermarked_path = apply_watermark(new_filepath, temp_watermarked_path, logo_path)
                # إذا فشل تطبيق اللوجو، نعود إلى الملف الأصلي
                if temp_watermarked_path == new_filepath:
                    logger.warning(f"فشل تطبيق اللوجو للمستخدم {user_id}. إرسال الملف الأصلي.")
                else:
                    logger.info(f"تم تطبيق اللوجو بنجاح للمستخدم {user_id}.")

            # 5. إرسال الفيديو للمستخدم
            # --- ✨ التصحيح النهائي هنا: استخدام نص عادي ✨ ---
            caption_text = f"{title}\n\nتم التحميل بواسطة @{context.bot.username}"
            
            with open(temp_watermarked_path, 'rb') as video_file:
                sent_message = await context.bot.send_video(
                    chat_id=update.effective_chat.id, 
                    video=video_file, 
                    caption=caption_text, # لا نستخدم parse_mode
                    reply_to_message_id=update.message.message_id
                )
            
            # 6. إعادة توجيه الفيديو إلى القناة الخاصة
            log_channel_videos_id = config.get("LOG_CHANNEL_ID_VIDEOS")
            if log_channel_videos_id and sent_message:
                try:
                    await sent_message.forward(chat_id=log_channel_videos_id)
                    logger.info(f"✅ تم إعادة توجيه الفيديو إلى القناة الخاصة: {log_channel_videos_id}")
                except Exception as forward_e:
                    logger.error(f"❌ فشل إعادة توجيه الفيديو: {forward_e}")

            # إرسال سجل إلى قناة السجل القديمة (إذا كانت موجودة)
            await send_log_to_channel(context, user, info_dict, temp_watermarked_path)

            # حذف الملف المؤقت ذي العلامة المائية إذا تم إنشاؤه
            if temp_watermarked_path != new_filepath and os.path.exists(temp_watermarked_path):
                os.remove(temp_watermarked_path)
            
            await processing_message.delete()
            
            if not is_user_admin and not is_subscribed_user:
                increment_download_count(user_id)

    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}", exc_info=True)
        error_message = get_message(lang, "download_failed")
        if isinstance(e, yt_dlp.utils.DownloadError) and "Unsupported URL" in str(e):
            error_message = get_message(lang, "unsupported_platform")
        
        try:
            await processing_message.edit_text(error_message)
        except Exception as edit_error:
            logger.error(f"Failed to edit error message: {edit_error}")
            await update.message.reply_text(error_message)
            
    finally:
        # حذف الملف الأصلي الذي تم تنزيله
        if new_filepath and os.path.exists(new_filepath):
            os.remove(new_filepath)

