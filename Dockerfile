# استخدام Python 3.11 slim
FROM python:3.11-slim

# تثبيت الأدوات الضرورية
RUN apt-get update && apt-get install -y \
    ffmpeg \
    wget \
    curl \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# إنشاء مستخدم غير root للأمان
RUN useradd -m -u 1000 botuser

# تعيين مجلد العمل
WORKDIR /app

# نسخ requirements.txt وتثبيت المكتبات
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# نسخ جميع ملفات المشروع
COPY . .

# إنشاء المجلدات المطلوبة
RUN mkdir -p /app/videos /app/data /app/logs /app/handlers \
    && chown -R botuser:botuser /app

# التبديل للمستخدم غير root
USER botuser

# المتغيرات البيئية الافتراضية
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

# فتح المنفذ
EXPOSE 8080

# تشغيل البوت
CMD ["python", "bot.py"]