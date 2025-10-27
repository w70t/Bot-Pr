import json
import os
import re
import logging
import subprocess
from telegram import BotCommand, BotCommandScopeChat
import ffmpeg

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

MESSAGES = {}
CONFIG = {}

def load_config():
    """
    يقوم بتحميل الإعدادات من ملف JSON
    """
    global CONFIG
    try:
        with open('config.json', 'r', encoding='utf-8') as f:
            CONFIG = json.load(f)
        logger.info("✅ تم تحميل ملف الإعدادات بنجاح.")
    except FileNotFoundError:
        logger.error("!!! ملف config.json غير موجود. سيتم استخدام إعدادات افتراضية.")
        CONFIG = {}
    except json.JSONDecodeError:
        logger.error("!!! خطأ في قراءة ملف config.json. تأكد من أن تنسيقه صحيح.")
        CONFIG = {}

def load_messages():
    """
    يقوم بتحميل الرسائل من ملف JSON
    """
    global MESSAGES
    try:
        with open('messages.json', 'r', encoding='utf-8') as f:
            MESSAGES = json.load(f)
        logger.info("✅ تم تحميل ملف الرسائل بنجاح.")
    except FileNotFoundError:
        logger.error("!!! ملف messages.json غير موجود. سيتم استخدام رسائل افتراضية.")
        MESSAGES = {}
    except json.JSONDecodeError:
        logger.error("!!! خطأ في قراءة ملف messages.json. تأكد من أن تنسيقه صحيح.")
        MESSAGES = {}

def get_message(lang, key, **kwargs):
    """
    يجلب رسالة مترجمة بناءً على اللغة والمفتاح
    """
    if lang not in MESSAGES:
        lang = 'ar'
    
    message = MESSAGES.get(lang, {}).get(key, f"_{key}_")
    
    if kwargs:
        try:
            message = message.format(**kwargs)
        except KeyError as e:
            logger.warning(f"المتغير {e} مفقود في الرسالة '{key}' للغة '{lang}'")

    return message

def get_config():
    """
    يجلب الإعدادات المحملة
    """
    return CONFIG

def apply_watermark(input_path, output_path, logo_path, position='center_right', size=150):
    """
    يطبق علامة مائية (لوجو) على الفيديو باستخدام FFmpeg
    
    Args:
        input_path: مسار الفيديو المدخل
        output_path: مسار الفيديو الناتج
        logo_path: مسار ملف اللوجو
        position: موقع اللوجو (center_right = الوسط على اليمين)
        size: عرض اللوجو بالبكسل
    
    Returns:
        str: مسار الفيديو الناتج إذا نجحت العملية، وإلا input_path
    """
    if not os.path.exists(logo_path):
        logger.error(f"❌ مسار اللوجو غير صحيح: {logo_path}")
        return input_path

    if not os.path.exists(input_path):
        logger.error(f"❌ مسار الفيديو المدخل غير صحيح: {input_path}")
        return input_path

    try:
        logger.info(f"🎨 بدء إضافة اللوجو للفيديو: {input_path}")
        
        # تحديد موضع اللوجو - الوسط على اليمين
        overlay_positions = {
            'top_left': '10:10',
            'top_right': 'W-w-10:10',
            'bottom_left': '10:H-h-10',
            'bottom_right': 'W-w-10:H-h-10',
            'center_right': 'W-w-10:(H-h)/2'  # الوسط على اليمين
        }
        overlay_expr = overlay_positions.get(position, 'W-w-10:(H-h)/2')

        # إعداد مدخلات FFmpeg
        input_video = ffmpeg.input(input_path)
        input_logo = ffmpeg.input(logo_path)

        # تطبيق الفلتر: تغيير حجم اللوجو ثم وضعه فوق الفيديو
        logo_scaled = input_logo.filter('scale', size, -1)
        
        # دمج اللوجو مع الفيديو
        stream = ffmpeg.overlay(input_video, logo_scaled, x=overlay_expr.split(':')[0], y=overlay_expr.split(':')[1])
        
        # إنشاء الفيديو النهائي
        stream = ffmpeg.output(
            stream,
            input_video.audio,
            output_path,
            vcodec='libx264',
            acodec='aac',
            audio_bitrate='128k',
            **{'b:v': '1000k'},
            preset='veryfast',
            movflags='faststart',
            loglevel='error'
        )
        
        # تنفيذ الأمر
        ffmpeg.run(stream, overwrite_output=True, capture_stdout=True, capture_stderr=True)
        
        logger.info(f"✅ تم إضافة اللوجو بنجاح. الملف الجديد: {output_path}")
        return output_path
        
    except ffmpeg.Error as e:
        error_message = e.stderr.decode('utf8') if e.stderr else str(e)
        logger.error(f"❌ فشل إضافة اللوجو باستخدام FFmpeg: {error_message}")
        return input_path
    except Exception as e:
        logger.error(f"❌ خطأ غير متوقع في apply_watermark: {e}")
        return input_path

def apply_animated_watermark(input_path, output_path, logo_path, size=150):
    """
    يطبق لوجو متحرك متقدم على الفيديو
    - حركة دائرية حول الفيديو
    - تأثير fade in/out
    - تأثير zoom
    
    Args:
        input_path: مسار الفيديو المدخل
        output_path: مسار الفيديو الناتج
        logo_path: مسار ملف اللوجو
        size: عرض اللوجو بالبكسل
    
    Returns:
        str: مسار الفيديو الناتج إذا نجحت العملية، وإلا input_path
    """
    if not os.path.exists(logo_path):
        logger.error(f"❌ مسار اللوجو غير صحيح: {logo_path}")
        return input_path

    if not os.path.exists(input_path):
        logger.error(f"❌ مسار الفيديو المدخل غير صحيح: {input_path}")
        return input_path

    try:
        logger.info(f"✨ بدء إضافة اللوجو المتحرك للفيديو: {input_path}")
        
        # الحصول على معلومات الفيديو
        probe = ffmpeg.probe(input_path)
        video_info = next(s for s in probe['streams'] if s['codec_type'] == 'video')
        duration = float(probe['format']['duration'])
        width = int(video_info['width'])
        height = int(video_info['height'])
        
        # مدة الدورة الكاملة (10 ثواني)
        cycle_duration = 10
        
        # معادلات الحركة الدائرية مع zoom و fade
        # الحركة: دائرة حول حواف الفيديو
        # t = الوقت الحالي
        # المركز: (width/2, height/2)
        # نصف القطر: min(width, height) * 0.4
        
        radius_x = width * 0.35
        radius_y = height * 0.35
        center_x = width / 2
        center_y = height / 2
        
        # معادلات الحركة
        # x = center_x + radius_x * cos(2*PI*t/cycle_duration) - logo_width/2
        # y = center_y + radius_y * sin(2*PI*t/cycle_duration) - logo_height/2
        
        x_expr = f"{center_x}+{radius_x}*cos(2*PI*t/{cycle_duration})-w/2"
        y_expr = f"{center_y}+{radius_y}*sin(2*PI*t/{cycle_duration})-h/2"
        
        # تأثير zoom (التكبير والتصغير)
        # يتراوح بين 0.8 و 1.2 من الحجم الأصلي
        scale_expr = f"{size}*(1+0.2*sin(4*PI*t/{cycle_duration}))"
        
        # تأثير fade (الشفافية)
        # يتراوح بين 0.7 و 1.0
        alpha_expr = f"0.85+0.15*sin(2*PI*t/{cycle_duration})"
        
        # إعداد FFmpeg
        input_video = ffmpeg.input(input_path)
        input_logo = ffmpeg.input(logo_path, loop=1, t=duration)
        
        # تطبيق المقياس الديناميكي
        logo_scaled = input_logo.filter('scale', scale_expr, -1)
        
        # تطبيق الشفافية
        logo_alpha = logo_scaled.filter('format', 'rgba').filter('colorchannelmixer', aa=alpha_expr)
        
        # تطبيق الحركة
        stream = ffmpeg.overlay(
            input_video, 
            logo_alpha,
            x=x_expr,
            y=y_expr,
            format='auto',
            shortest=1
        )
        
        # الإخراج
        stream = ffmpeg.output(
            stream,
            input_video.audio,
            output_path,
            vcodec='libx264',
            acodec='aac',
            audio_bitrate='128k',
            **{'b:v': '1200k'},
            preset='medium',
            movflags='faststart',
            loglevel='error'
        )
        
        # تنفيذ
        ffmpeg.run(stream, overwrite_output=True, capture_stdout=True, capture_stderr=True)
        
        logger.info(f"✨ تم إضافة اللوجو المتحرك بنجاح!")
        return output_path
        
    except ffmpeg.Error as e:
        error_message = e.stderr.decode('utf8') if e.stderr else str(e)
        logger.error(f"❌ فشل إضافة اللوجو المتحرك: {error_message}")
        # إذا فشل المتحرك، نرجع للثابت
        return apply_watermark(input_path, output_path, logo_path)
    except Exception as e:
        logger.error(f"❌ خطأ غير متوقع في apply_animated_watermark: {e}")
        return apply_watermark(input_path, output_path, logo_path)

async def setup_bot_menu(bot):
    """
    يقوم بإعداد قائمة الأوامر (Menu) للبوت
    """
    logger.info("📋 إعداد قائمة أوامر البوت...")
    
    if not MESSAGES:
        load_messages()
    
    # الأوامر العامة (باللغة العربية)
    user_commands_ar = [
        BotCommand("start", get_message('ar', 'start_command_desc')),
        BotCommand("account", get_message('ar', 'account_command_desc')),
        BotCommand("help", get_message('ar', 'help_command_desc')),
    ]
    
    # الأوامر العامة (باللغة الإنجليزية)
    user_commands_en = [
        BotCommand("start", get_message('en', 'start_command_desc')),
        BotCommand("account", get_message('en', 'account_command_desc')),
        BotCommand("help", get_message('en', 'help_command_desc')),
    ]
    
    # أوامر المدير (باللغة العربية)
    admin_commands_ar = user_commands_ar + [
        BotCommand("admin", get_message('ar', 'admin_command_desc')),
    ]
    
    # أوامر المدير (باللغة الإنجليزية)
    admin_commands_en = user_commands_en + [
        BotCommand("admin", get_message('en', 'admin_command_desc')),
    ]

    # تعيين الأوامر الافتراضية
    await bot.set_my_commands(user_commands_ar)
    logger.info("✅ تم تعيين قائمة الأوامر العامة.")
    
    # تعيين الأوامر للمدراء
    admin_ids_str = os.getenv("ADMIN_ID", "")
    admin_ids = [int(admin_id) for admin_id in admin_ids_str.split(',') if admin_id.strip()]
    
    for admin_id in admin_ids:
        try:
            await bot.set_my_commands(admin_commands_ar, scope=BotCommandScopeChat(chat_id=admin_id))
            logger.info(f"✅ تم تعيين قائمة أوامر خاصة للمدير ID: {admin_id}")
        except Exception as e:
            logger.error(f"❌ فشل تعيين أوامر للمدير {admin_id}: {e}")

def clean_filename(filename):
    """
    يزيل الأحرف غير الصالحة من أسماء الملفات
    """
    cleaned = re.sub(r'[\\/*?:"<>|]', "", filename)
    if len(cleaned) > 200:
        cleaned = cleaned[:200]
    return cleaned

def escape_markdown(text: str) -> str:
    """
    يقوم بتهريب الأحرف الخاصة في MarkdownV2
    """
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    return re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', text)

def format_file_size(size_bytes):
    """
    تحويل حجم الملف من bytes إلى صيغة قابلة للقراءة
    """
    if not size_bytes:
        return "غير معروف"
    
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} TB"

def format_duration(seconds):
    """
    تحويل المدة من ثواني إلى صيغة قابلة للقراءة (HH:MM:SS)
    """
    if not seconds:
        return "00:00"
    
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    else:
        return f"{minutes:02d}:{secs:02d}"

def get_video_info(file_path):
    """
    جلب معلومات الفيديو باستخدام FFprobe
    
    Returns:
        dict: معلومات الفيديو (width, height, duration, codec, etc.)
    """
    try:
        probe = ffmpeg.probe(file_path)
        video_info = next(s for s in probe['streams'] if s['codec_type'] == 'video')
        
        return {
            'width': int(video_info.get('width', 0)),
            'height': int(video_info.get('height', 0)),
            'duration': float(probe['format'].get('duration', 0)),
            'size': int(probe['format'].get('size', 0)),
            'codec': video_info.get('codec_name', 'unknown'),
            'bitrate': int(probe['format'].get('bit_rate', 0))
        }
    except Exception as e:
        logger.error(f"❌ فشل جلب معلومات الفيديو: {e}")
        return None

def validate_url(url: str) -> bool:
    """
    التحقق من صحة الرابط
    """
    url_pattern = re.compile(
        r'^https?://'
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'
        r'localhost|'
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'
        r'(?::\d+)?'
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    return url_pattern.match(url) is not None

# قم بتحميل الرسائل والإعدادات عند بدء تشغيل الوحدة
load_config()
load_messages()