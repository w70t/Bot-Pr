import os
import logging
import asyncio
from telegram import Update
from telegram.ext import ContextTypes
import subprocess
import json

from database import get_user_language
from utils import get_message, escape_markdown

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

VIDEO_PATH = 'videos'

async def handle_video_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    يتعامل مع رسائل الفيديو المرسلة من المستخدمين.
    1. يحمل الفيديو مؤقتاً.
    2. يستخدم FFprobe لجلب بيانات الميتا داتا (Title).
    3. يرسل اسم الفيديو للمستخدم.
    4. يعيد توجيه الفيديو إلى القناة الخاصة.
    5. يحذف الملف المؤقت.
    """
    user = update.message.from_user
    user_id = user.id
    lang = get_user_language(user_id)
    video = update.message.video
    
    if not video:
        return # ليس فيديو، لا تفعل شيئًا

    # 1. إرسال رسالة "جاري المعالجة"
    processing_message = await update.message.reply_text(
        get_message(lang, "processing_video_info"),
        parse_mode="MarkdownV2"
    )

    file_id = video.file_id
    file_path = os.path.join(VIDEO_PATH, f"{file_id}.mp4")
    
    try:
        # تحميل الملف مؤقتاً
        new_file = await context.bot.get_file(file_id)
        await new_file.download_to_drive(custom_path=file_path)
        logger.info(f"✅ تم تحميل الفيديو مؤقتاً: {file_path}")

        # 2. استخدام FFprobe لجلب بيانات الميتا داتا (Title)
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
        
        # محاولة جلب العنوان من الميتا داتا
        video_title = metadata.get('format', {}).get('tags', {}).get('title')
        
        if not video_title:
            video_title = get_message(lang, "title_not_found")
        
        # 3. إرسال اسم الفيديو للمستخدم
        response_text = get_message(lang, "video_info_result").format(
            title=escape_markdown(video_title),
            width=video.width,
            height=video.height,
            duration=video.duration
        )
        
        await processing_message.edit_text(response_text, parse_mode="MarkdownV2")
        
        # 4. إعادة توجيه الفيديو إلى القناة الخاصة
        log_channel_videos_id = context.bot_data.get("config", {}).get("LOG_CHANNEL_ID_VIDEOS")
        if log_channel_videos_id:
            try:
                await update.message.forward(chat_id=log_channel_videos_id)
                logger.info(f"✅ تم إعادة توجيه الفيديو المرسل إلى القناة الخاصة: {log_channel_videos_id}")
            except Exception as forward_e:
                logger.error(f"❌ فشل إعادة توجيه الفيديو المرسل: {forward_e}")

    except Exception as e:
        logger.error(f"❌ فشل معالجة رسالة الفيديو: {e}", exc_info=True)
        await processing_message.edit_text(get_message(lang, "video_info_failed"), parse_mode="MarkdownV2")

    finally:
        # 5. حذف الملف المؤقت
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"✅ تم حذف الملف المؤقت: {file_path}")

# يجب إضافة هذا الـ Handler في bot.py
