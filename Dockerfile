# استخدام Python 3.11 كصورة أساسية
FROM python:3.11-slim

# تعيين مجلد العمل
WORKDIR /app

# تثبيت ffmpeg وأدوات النظام المطلوبة
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# نسخ ملف المتطلبات وتثبيت المكتبات
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# نسخ جميع ملفات المشروع
COPY . .

# إنشاء مجلد للملفات المؤقتة
RUN mkdir -p /tmp/downloads

# تعيين المنفذ الافتراضي
ENV PORT=8080

# تشغيل البوت
CMD ["python", "bot.py"]
