import os
import logging
import asyncio
from telegram import Update
from telegram.ext import ContextTypes
import subprocess
import json

from database import get_user_language
from utils import format_file_size, format_duration

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

VIDEO_PATH = 'videos'

if not os.path.exists(VIDEO_PATH):
    os.makedirs(VIDEO_PATH)

async def handle_video_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    التعرف على الفيديو المرسل - للبحث عن اسم الفلم
    """
    user = update.message.from_user
    user_id = user.id
    lang = get_user_language(user_id)
    video = update.message.video
    
    if not video:
        return

    processing_message = await update.message.reply_text(
        "🎬 جاري تحليل الفيديو للتعرف عليه..."
    )

    file_id = video.file_id
    file_path = os.path.join(VIDEO_PATH, f"{file_id}.mp4")
    
    try:
        # تحميل الفيديو مؤقتاً
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
        video_title = metadata.get('format', {}).get('tags', {}).get('title', 'غير متوفر')
        
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
        
        # إرسال معلومات الفيديو للمستخدم
        response_text = (
            f"🎬 معلومات الفيديو:\n\n"
            f"📝 العنوان: {video_title}\n"
            f"📐 الأبعاد: {video.width}x{video.height}\n"
            f"⏱️ المدة: {format_duration(duration)}\n"
            f"📦 الحجم: {format_file_size(file_size)}\n"
            f"🎨 الجودة: {quality}\n\n"
            f"💡 نصيحة: ابحث عن اسم الفيديو في Google أو استخدم تطبيقات التعرف على الأفلام!"
        )
        
        await processing_message.edit_text(response_text)
        
        # لا نرسل للقناة - فقط معلومات للمستخدم

    except Exception as e:
        logger.error(f"❌ فشل معالجة الفيديو: {e}", exc_info=True)
        await processing_message.edit_text(
            "❌ فشل التحليل! عذراً، لم أتمكن من تحليل هذا الفيديو."
        )

    finally:
        # حذف الملف المؤقت
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                logger.info(f"✅ تم حذف الملف المؤقت: {file_path}")
            except Exception as delete_e:
                logger.error(f"❌ فشل حذف الملف: {delete_e}")