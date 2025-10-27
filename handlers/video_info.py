import os
import logging
import asyncio
from telegram import Update
from telegram.ext import ContextTypes
import subprocess
import json

from database import get_user_language
from utils import get_message, escape_markdown, get_config, format_file_size, format_duration

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

VIDEO_PATH = 'videos'

if not os.path.exists(VIDEO_PATH):
    os.makedirs(VIDEO_PATH)

async def handle_video_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    يتعامل مع رسائل الفيديو المرسلة من المستخدمين
    1. يحمل الفيديو مؤقتاً
    2. يستخدم FFprobe لجلب معلومات الفيديو
    3. يرسل المعلومات للمستخدم
    4. يعيد توجيه الفيديو إلى القناة الخاصة
    5. يحذف الملف المؤقت
    """
    user = update.message.from_user
    user_id = user.id
    lang = get_user_language(user_id)
    video = update.message.video
    
    if not video:
        return

    # رسالة المعالجة
    processing_message = await update.message.reply_text(
        get_message(lang, "processing_video_info"),
        parse_mode="Markdown"
    )

    file_id = video.file_id
    file_path = os.path.join(VIDEO_PATH, f"{file_id}.mp4")
    
    try:
        # تحميل الملف مؤقتاً
        new_file = await context.bot.get_file(file_id)
        await new_file.download_to_drive(custom_path=file_path)
        logger.info(f"✅ تم تحميل الفيديو مؤقتاً: {file_path}")

        # استخدام FFprobe لجلب المعلومات
        ffprobe_command = [
            'ffprobe',
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            '-show_streams',
            file_path
        ]

        loop = asyncio.get_event_loop()
        process = await loop.run_in_executor(None, lambda: subprocess.run(
            ffprobe_command,
            capture_output=True,
            text=True,
            check=True
        ))
        
        metadata = json.loads(process.stdout)
        
        # جلب المعلومات
        video_title = metadata.get('format', {}).get('tags', {}).get('title')
        
        if not video_title:
            video_title = get_message(lang, "title_not_found")
        
        # حساب الجودة
        quality = "SD"
        if video.height >= 1080:
            quality = "Full HD"
        elif video.height >= 720:
            quality = "HD"
        elif video.height >= 480:
            quality = "SD"
        
        file_size = video.file_size if video.file_size else 0
        duration = video.duration if video.duration else 0
        
        # إرسال المعلومات للمستخدم
        response_text = get_message(lang, "video_info_result").format(
            title=escape_markdown(video_title),
            width=video.width,
            height=video.height,
            duration=format_duration(duration),
            size=format_file_size(file_size),
            quality=quality
        )
        
        await processing_message.edit_text(response_text, parse_mode="Markdown")
        
        # إعادة توجيه الفيديو إلى القناة الخاصة
        config = get_config()
        log_channel_videos_id = config.get("LOG_CHANNEL_ID_VIDEOS")
        
        if log_channel_videos_id:
            try:
                # إعداد caption للقناة
                channel_caption = (
                    f"📺 **فيديو مرسل من مستخدم**\n\n"
                    f"👤 **المستخدم:** {escape_markdown(user.full_name)}\n"
                    f"🆔 **ID:** `{user_id}`\n"
                    f"👁️ **Username:** @{user.username if user.username else 'لا يوجد'}\n\n"
                    f"🎬 **العنوان:** {escape_markdown(video_title)}\n"
                    f"📐 **الأبعاد:** {video.width}x{video.height}\n"
                    f"⏱️ **المدة:** {format_duration(duration)}\n"
                    f"📦 **الحجم:** {format_file_size(file_size)}\n"
                    f"🎨 **الجودة:** {quality}"
                )
                
                await update.message.copy(
                    chat_id=log_channel_videos_id,
                    caption=channel_caption,
                    parse_mode="Markdown"
                )
                logger.info(f"✅ تم إرسال الفيديو إلى القناة: {log_channel_videos_id}")
            except Exception as forward_e:
                logger.error(f"❌ فشل إرسال الفيديو للقناة: {forward_e}")

    except Exception as e:
        logger.error(f"❌ فشل معالجة الفيديو: {e}", exc_info=True)
        await processing_message.edit_text(
            get_message(lang, "video_info_failed"), 
            parse_mode="Markdown"
        )

    finally:
        # حذف الملف المؤقت
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                logger.info(f"✅ تم حذف الملف المؤقت: {file_path}")
            except Exception as delete_e:
                logger.error(f"❌ فشل حذف الملف: {delete_e}")