import json
import os
import re
import logging
import subprocess
from telegram import BotCommand, BotCommandScopeChat

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

MESSAGES = {}
CONFIG = {}

def load_config():
    """يقوم بتحميل الإعدادات من ملف JSON"""
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
    """يقوم بتحميل الرسائل من ملف JSON"""
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
    """يجلب رسالة مترجمة بناءً على اللغة والمفتاح"""
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
    """يجلب الإعدادات المحملة"""
    return CONFIG

def apply_animated_watermark(input_path, output_path, logo_path, size=150):
    """
    يطبق لوجو متحرك على الفيديو - حركة من الزوايا
    استخدام FFmpeg مباشر - أبسط وأسرع
    """
    if not os.path.exists(logo_path):
        logger.error(f"❌ مسار اللوجو غير صحيح: {logo_path}")
        return input_path

    if not os.path.exists(input_path):
        logger.error(f"❌ مسار الفيديو المدخل غير صحيح: {input_path}")
        return input_path

    try:
        logger.info(f"✨ بدء إضافة اللوجو المتحرك: {input_path}")
        
        # حركة من الزوايا الأربع
        # يتحرك من أعلى يمين → أسفل يمين → أسفل يسار → أعلى يسار → يتكرر
        cmd = [
            'ffmpeg',
            '-i', input_path,
            '-i', logo_path,
            '-filter_complex',
            (
                f"[1:v]scale={size}:-1,format=rgba[logo];"
                "[0:v][logo]overlay="
                "x='if(lt(mod(t\\,20)\\,5)\\, W-w-10-(W-w-20)*(mod(t\\,5)/5)\\, "
                "if(lt(mod(t\\,20)\\,10)\\, 10\\, "
                "if(lt(mod(t\\,20)\\,15)\\, 10+(W-w-20)*((mod(t\\,20)-10)/5)\\, W-w-10)))':"
                "y='if(lt(mod(t\\,20)\\,5)\\, 10\\, "
                "if(lt(mod(t\\,20)\\,10)\\, 10+(H-h-20)*((mod(t\\,20)-5)/5)\\, "
                "if(lt(mod(t\\,20)\\,15)\\, H-h-10\\, H-h-10-(H-h-20)*((mod(t\\,20)-15)/5))))'"
            ),
            '-c:a', 'copy',
            '-c:v', 'libx264',
            '-preset', 'veryfast',
            '-crf', '23',
            '-movflags', '+faststart',
            '-y',
            output_path
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300
        )
        
        if result.returncode == 0 and os.path.exists(output_path):
            file_size = os.path.getsize(output_path)
            if file_size > 1000:
                logger.info(f"✨ نجح اللوجو المتحرك! {file_size/1024/1024:.2f}MB")
                return output_path
        
        logger.warning(f"⚠️ فشل اللوجو المتحرك، استخدام الثابت...")
        return apply_watermark(input_path, output_path, logo_path)
            
    except Exception as e:
        logger.error(f"❌ خطأ في اللوجو المتحرك: {e}")
        return apply_watermark(input_path, output_path, logo_path)

def apply_watermark(input_path, output_path, logo_path, position='center_right', size=150):
    """
    يطبق لوجو ثابت على الفيديو (احتياطي)
    """
    if not os.path.exists(logo_path):
        logger.error(f"❌ مسار اللوجو غير صحيح: {logo_path}")
        return input_path

    if not os.path.exists(input_path):
        logger.error(f"❌ مسار الفيديو المدخل غير صحيح: {input_path}")
        return input_path

    try:
        logger.info(f"🎨 إضافة لوجو ثابت: {input_path}")
        
        # مواضع بسيطة
        positions = {
            'top_left': '10:10',
            'top_right': f'W-{size}-10:10',
            'bottom_left': f'10:H-{int(size*0.67)}-10',
            'bottom_right': f'W-{size}-10:H-{int(size*0.67)}-10',
            'center_right': f'W-{size}-10:(H-{int(size*0.67)})/2'
        }
        
        pos = positions.get(position, positions['center_right'])
        
        cmd = [
            'ffmpeg',
            '-i', input_path,
            '-i', logo_path,
            '-filter_complex',
            f'[1:v]scale={size}:-1[logo];[0:v][logo]overlay={pos}',
            '-c:a', 'copy',
            '-c:v', 'libx264',
            '-preset', 'veryfast',
            '-crf', '23',
            '-y',
            output_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        
        if result.returncode == 0 and os.path.exists(output_path):
            logger.info(f"✅ نجح اللوجو الثابت")
            return output_path
        else:
            logger.error(f"❌ فشل اللوجو الثابت")
            return input_path
        
    except Exception as e:
        logger.error(f"❌ خطأ: {e}")
        return input_path

async def setup_bot_menu(bot):
    """يقوم بإعداد قائمة الأوامر (Menu) للبوت"""
    logger.info("📋 إعداد قائمة أوامر البوت...")
    
    if not MESSAGES:
        load_messages()
    
    user_commands_ar = [
        BotCommand("start", get_message('ar', 'start_command_desc')),
        BotCommand("account", get_message('ar', 'account_command_desc')),
        BotCommand("help", get_message('ar', 'help_command_desc')),
    ]
    
    user_commands_en = [
        BotCommand("start", get_message('en', 'start_command_desc')),
        BotCommand("account", get_message('en', 'account_command_desc')),
        BotCommand("help", get_message('en', 'help_command_desc')),
    ]
    
    admin_commands_ar = user_commands_ar + [
        BotCommand("admin", get_message('ar', 'admin_command_desc')),
    ]
    
    admin_commands_en = user_commands_en + [
        BotCommand("admin", get_message('en', 'admin_command_desc')),
    ]

    await bot.set_my_commands(user_commands_ar)
    logger.info("✅ تم تعيين قائمة الأوامر العامة.")
    
    admin_ids_str = os.getenv("ADMIN_ID", "")
    admin_ids = [int(admin_id) for admin_id in admin_ids_str.split(',') if admin_id.strip()]
    
    for admin_id in admin_ids:
        try:
            await bot.set_my_commands(admin_commands_ar, scope=BotCommandScopeChat(chat_id=admin_id))
            logger.info(f"✅ تم تعيين قائمة أوامر خاصة للمدير ID: {admin_id}")
        except Exception as e:
            logger.error(f"❌ فشل تعيين أوامر للمدير {admin_id}: {e}")

def clean_filename(filename):
    """يزيل الأحرف غير الصالحة من أسماء الملفات"""
    cleaned = re.sub(r'[\\/*?:"<>|]', "", filename)
    if len(cleaned) > 200:
        cleaned = cleaned[:200]
    return cleaned

def escape_markdown(text: str) -> str:
    """يقوم بتهريب الأحرف الخاصة في MarkdownV2"""
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    return re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', text)

def format_file_size(size_bytes):
    """تحويل حجم الملف من bytes إلى صيغة قابلة للقراءة"""
    if not size_bytes:
        return "غير معروف"
    
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} TB"

def format_duration(seconds):
    """تحويل المدة من ثواني إلى صيغة قابلة للقراءة (HH:MM:SS)"""
    if not seconds:
        return "00:00"
    
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    else:
        return f"{minutes:02d}:{secs:02d}"

def validate_url(url: str) -> bool:
    """التحقق من صحة الرابط"""
    url_pattern = re.compile(
        r'^https?://'
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'
        r'localhost|'
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'
        r'(?::\d+)?'
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    return url_pattern.match(url) is not None

load_config()
load_messages()