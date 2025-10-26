import json
import os
import re
import logging
import subprocess
from telegram import BotCommand, BotCommandScopeDefault, BotCommandScopeChat
# استيراد مكتبة ffmpeg-python
import ffmpeg 

# --- إعدادات التسجيل ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- تحميل الرسائل ---
MESSAGES = {}
CONFIG = {}

def load_config():
    """
    يقوم بتحميل الإعدادات من ملف JSON.
    """
    global CONFIG
    try:
        with open('telegram-downloader-bot/config.json', 'r', encoding='utf-8') as f:
            CONFIG = json.load(f)
        logger.info("✅ تم تحميل ملف الإعدادات بنجاح.")
    except FileNotFoundError:
        logger.error("!!! ملف config.json غير موجود. سيتم استخدام إعدادات افتراضية.")
        CONFIG = {}
    except json.JSONDecodeError:
        logger.error("!!! خطأ في قراءة ملف config.json. تأكد من أن تنسيقه صحيح.")

def load_messages():
    """
    يقوم بتحميل الرسائل من ملف JSON.
    """
    global MESSAGES
    try:
        with open('telegram-downloader-bot/messages.json', 'r', encoding='utf-8') as f:
            MESSAGES = json.load(f)
        logger.info("✅ تم تحميل ملف الرسائل بنجاح.")
    except FileNotFoundError:
        logger.error("!!! ملف messages.json غير موجود. سيتم استخدام رسائل افتراضية.")
    except json.JSONDecodeError:
        logger.error("!!! خطأ في قراءة ملف messages.json. تأكد من أن تنسيقه صحيح.")

def get_message(lang, key, **kwargs):
    """
    يجلب رسالة مترجمة بناءً على اللغة والمفتاح.
    """
    # افتراضي إلى الإنجليزية إذا كانت اللغة غير موجودة
    if lang not in MESSAGES:
        lang = 'en'
    
    message = MESSAGES.get(lang, {}).get(key, f"_{key}_")
    
    # استبدال المتغيرات إذا وجدت
    if kwargs:
        try:
            message = message.format(**kwargs)
        except KeyError as e:
            logger.warning(f"المتغير {e} مفقود في الرسالة '{key}' للغة '{lang}'")

    return message

def get_config():
    """
    يجلب الإعدادات المحملة.
    """
    return CONFIG

def apply_watermark(input_path, output_path, logo_path, position='bottom_right', size=150):
    """
    يطبق علامة مائية (لوجو) على الفيديو باستخدام FFmpeg عبر مكتبة ffmpeg-python.
    """
    if not os.path.exists(logo_path):
        logger.error(f"❌ مسار اللوجو غير صحيح: {logo_path}")
        return input_path

    try:
        logger.info(f"بدء إضافة اللوجو للفيديو: {input_path}")
        
        # تحديد موضع اللوجو
        if position == 'top_left':
            overlay_expr = '10:10'
        elif position == 'top_right':
            overlay_expr = f'W-w-10:10'
        elif position == 'bottom_left':
            overlay_expr = f'10:H-h-10'
        elif position == 'bottom_right':
            overlay_expr = f'W-w-10:H-h-10'
        else:
            # افتراضي إلى أسفل اليمين
            overlay_expr = f'W-w-10:H-h-10'

        # إعداد مدخلات ومخرجات FFmpeg
        input_video = ffmpeg.input(input_path)
        input_logo = ffmpeg.input(logo_path)

        # فلتر معقد: تغيير حجم اللوجو ثم وضعه فوق الفيديو
        # [1:v]scale={size}:-1[logo];[0:v][logo]overlay={overlay_expr}
        # [1:v] هو اللوجو (المدخل الثاني)، [0:v] هو الفيديو (المدخل الأول)
        stream = ffmpeg.filter(
            [input_video.video, input_logo.video],
            'overlay',
            overlay_expr,
            enable=f'between(t,0,999999)' # لتطبيق اللوجو طوال مدة الفيديو
        ).filter('scale', width='if(gt(iw,1920),1920,iw)', height=-2) # لتقليل حجم الفيديو إذا كان كبيراً جداً (اختياري)
        
        # تجميع الأمر النهائي
        final_stream = ffmpeg.output(
            stream, 
            input_video.audio, 
            output_path, 
            vcodec='libx264', # استخدام ترميز H.264
            acodec='copy', # نسخ ترميز الصوت
            pix_fmt='yuv420p', # تنسيق البكسل المتوافق مع معظم المشغلات
            crf=23, # جودة الفيديو (كلما قل الرقم زادت الجودة والحجم)
            preset='veryfast', # سرعة الترميز
            loglevel='error', # تقليل سجلات FFmpeg
            overwrite_output=True
        )

        # تنفيذ الأمر
        final_stream.run(capture_stdout=True, capture_stderr=True)
        
        logger.info(f"✅ تم إضافة اللوجو بنجاح. الملف الجديد: {output_path}")
        return output_path
    except ffmpeg.Error as e:
        logger.error(f"❌ فشل إضافة اللوجو باستخدام FFmpeg: {e.stderr.decode('utf8')}")
        return input_path
    except FileNotFoundError:
        logger.error("❌ لم يتم العثور على أمر FFmpeg. تأكد من تثبيته.")
        return input_path

async def setup_bot_menu(bot):
    """
    يقوم بإعداد قائمة الأوامر (Menu) للبوت للمستخدمين العاديين والمدراء.
    """
    logger.info("إعداد قائمة أوامر البوت...")
    
    # تحميل الرسائل لضمان وجودها
    load_messages() 
    
    # الأوامر العامة (باللغة العربية)
    user_commands_ar = [
        BotCommand("start", get_message('ar', 'start_command_desc')),
        BotCommand("account", get_message('ar', 'account_command_desc')),
    ]
    # الأوامر العامة (باللغة الإنجليزية)
    user_commands_en = [
        BotCommand("start", get_message('en', 'start_command_desc')),
        BotCommand("account", get_message('en', 'account_command_desc')),
    ]
    
    # أوامر المدير (باللغة العربية)
    admin_commands_ar = user_commands_ar + [
        BotCommand("admin", get_message('ar', 'admin_command_desc')),
    ]
    # أوامر المدير (باللغة الإنجليزية)
    admin_commands_en = user_commands_en + [
        BotCommand("admin", get_message('en', 'admin_command_desc')),
    ]

    # تعيين الأوامر الافتراضية (للغة الإنجليزية كقاعدة)
    await bot.set_my_commands(user_commands_en)
    logger.info("✅ تم تعيين قائمة الأوامر العامة.)"
    
    # تعيين الأوامر للمدراء
    admin_ids_str = os.getenv("ADMIN_ID", "") # تم تعديل المتغير ليتوافق مع .env
    admin_ids = [int(admin_id) for admin_id in admin_ids_str.split(',') if admin_id]
    
    for admin_id in admin_ids:
        try:
            # نحاول الحصول على لغة المدير وتعيين القائمة المناسبة
            # (هذه الخطوة تتطلب الوصول إلى قاعدة البيانات، لكن يمكننا افتراض اللغة العربية للمدير)
            commands_to_set = admin_commands_ar # افتراض العربية للمدير
            await bot.set_my_commands(commands_to_set, scope=BotCommandScopeChat(chat_id=admin_id))
            logger.info(f"✅ تم تعيين قائمة أوامر خاصة للمدير ID: {admin_id}")
        except Exception as e:
            logger.error(f"❌ فشل تعيين أوامر للمدير {admin_id}: {e}")

def clean_filename(filename):
    """
    يزيل الأحرف غير الصالحة من أسماء الملفات.
    """
    return re.sub(r'[\\/*?:"<>|]', "", filename)

def escape_markdown(text: str) -> str:
    """
    يقوم بتهريب الأحرف الخاصة في MarkdownV2.
    """
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    return re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', text)

# قم بتحميل الرسائل والإعدادات عند بدء تشغيل الوحدة
load_config()
load_messages()
