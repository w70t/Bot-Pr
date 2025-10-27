# 🚀 دليل تشغيل البوت على Ubuntu مع Portainer

## 📋 المتطلبات الأساسية

### 1. تثبيت Docker و Docker Compose
```bash
# تحديث النظام
sudo apt update && sudo apt upgrade -y
#تسغيل البوت 
source venv/bin/activate
python bot.py
# تثبيت Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# إضافة المستخدم لمجموعة Docker
sudo usermod -aG docker $USER

# تفعيل Docker
sudo systemctl enable docker
sudo systemctl start docker

# تثبيت Docker Compose
sudo apt install docker-compose -y
```

### 2. تثبيت Portainer
```bash
# إنشاء volume لـ Portainer
docker volume create portainer_data

# تشغيل Portainer
docker run -d \
  -p 9000:9000 \
  -p 9443:9443 \
  --name=portainer \
  --restart=always \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v portainer_data:/data \
  portainer/portainer-ce:latest
```

الآن يمكنك الوصول لـ Portainer عبر: `http://YOUR_SERVER_IP:9000`

---

## 🔧 إعداد المشروع

### 1. استنساخ المشروع
```bash
cd ~
git clone https://github.com/w70t/Bot-Pr.git
cd Bot-Pr
```

### 2. إنشاء الملفات المطلوبة

**أ. إنشاء Dockerfile:**
```bash
nano Dockerfile
```
انسخ محتوى Dockerfile من الأعلى

**ب. إنشاء docker-compose.yml:**
```bash
nano docker-compose.yml
```
انسخ محتوى docker-compose.yml من الأعلى

**ج. إنشاء ملف .env:**
```bash
nano .env
```
انسخ محتوى .env وعدّل القيم:
- `TELEGRAM_TOKEN`: احصل عليه من [@BotFather](https://t.me/BotFather)
- `ADMIN_ID`: احصل عليه من [@userinfobot](https://t.me/userinfobot)
- `LOG_CHANNEL_ID`: (اختياري) معرف قناة خاصة

### 3. التأكد من هيكل المشروع
```bash
ls -la
```
يجب أن تشاهد:
```
.
├── bot.py
├── Dockerfile
├── docker-compose.yml
├── .env
├── requirements.txt
├── messages.json
├── Procfile
└── README.md
```

---

## 🐳 الطريقة الأولى: التشغيل عبر سطر الأوامر

### 1. بناء الصورة
```bash
docker-compose build
```

### 2. تشغيل البوت
```bash
docker-compose up -d
```

### 3. التحقق من حالة البوت
```bash
# عرض الحاويات
docker-compose ps

# عرض السجلات
docker-compose logs -f

# إيقاف البوت
docker-compose down

# إعادة تشغيل البوت
docker-compose restart
```

---

## 🌐 الطريقة الثانية: التشغيل عبر Portainer (الموصى بها)

### 1. الدخول إلى Portainer
1. افتح المتصفح: `http://YOUR_SERVER_IP:9000`
2. أنشئ حساب مدير
3. اختر "Get Started" ثم "local"

### 2. إضافة Stack جديد
1. من القائمة الجانبية: **Stacks** → **Add stack**
2. اسم الـ Stack: `telegram-video-bot`

### 3. خيارين للإضافة:

#### الخيار أ: رفع docker-compose.yml
1. اختر **Upload**
2. ارفع ملف `docker-compose.yml`
3. في قسم **Environment variables**، أضف:
   ```
   TELEGRAM_TOKEN=YOUR_TOKEN
   ADMIN_ID=YOUR_ID
   LOG_CHANNEL_ID=
   ```

#### الخيار ب: استخدام Git Repository
1. اختر **Repository**
2. Repository URL: `https://github.com/w70t/Bot-Pr`
3. Compose path: `docker-compose.yml`
4. أضف المتغيرات في قسم Environment variables

### 4. نشر البوت
- اضغط **Deploy the stack**
- انتظر حتى يكتمل البناء (قد يستغرق دقائق)

### 5. مراقبة البوت في Portainer
- **Containers** → `video_downloader_bot`
- **Quick actions** → **Logs** لعرض السجلات
- **Quick actions** → **Stats** لعرض الموارد
- **Quick actions** → **Exec Console** للدخول للحاوية

---

## 🔍 التحقق من عمل البوت

### 1. فحص السجلات
```bash
docker logs video_downloader_bot -f
```

يجب أن ترى:
```
Bot started successfully!
Webhook set successfully
```

### 2. اختبار البوت
1. افتح تيليجرام
2. ابحث عن اسم البوت الخاص بك
3. أرسل `/start`
4. جرب إرسال رابط فيديو من يوتيوب

---

## 🛠️ استكشاف الأخطاء

### المشكلة: البوت لا يستجيب
```bash
# فحص السجلات
docker logs video_downloader_bot

# التحقق من الحاوية
docker ps -a

# إعادة تشغيل
docker-compose restart
```

### المشكلة: خطأ في التوكن
- تأكد من صحة `TELEGRAM_TOKEN` من @BotFather
- تأكد من عدم وجود مسافات في الملف `.env`

### المشكلة: خطأ في تحميل الفيديو
```bash
# الدخول للحاوية
docker exec -it video_downloader_bot bash

# فحص yt-dlp
yt-dlp --version

# تحديث yt-dlp
pip install -U yt-dlp
```

### المشكلة: نفاد المساحة
```bash
# حذف الملفات المؤقتة
docker exec video_downloader_bot rm -rf /tmp/downloads/*

# حذف الصور غير المستخدمة
docker system prune -a
```

---

## 📊 أوامر مفيدة

```bash
# عرض استهلاك الموارد
docker stats video_downloader_bot

# نسخ احتياطي للبيانات
docker cp video_downloader_bot:/app/stats.json ./backup/

# تحديث البوت
cd ~/Bot-Pr
git pull
docker-compose up -d --build

# عرض جميع الحاويات
docker ps -a

# حذف الحاوية
docker-compose down -v
```

---

## 🔐 نصائح أمنية

1. **لا تشارك ملف .env أبداً**
2. **استخدم جدار ناري:**
   ```bash
   sudo ufw allow 9000/tcp  # Portainer
   sudo ufw enable
   ```
3. **تحديث النظام دورياً:**
   ```bash
   sudo apt update && sudo apt upgrade -y
   ```
4. **نسخ احتياطي منتظم للبيانات**

---

## 📈 مراقبة الأداء

### في Portainer:
1. **Dashboard** → عرض نظرة عامة
2. **Containers** → **Stats** → مراقبة CPU/RAM
3. **Logs** → متابعة الأحداث في الوقت الفعلي

### من سطر الأوامر:
```bash
# مراقبة مباشرة
docker stats video_downloader_bot

# السجلات الحية
docker logs -f video_downloader_bot --tail 100
```

---

## 🚀 التحديث والصيانة

```bash
# تحديث الكود
cd ~/Bot-Pr
git pull

# إعادة بناء ونشر
docker-compose down
docker-compose up -d --build

# أو في Portainer:
# Stacks → telegram-video-bot → Update
```

---

## 📞 الدعم

إذا واجهت مشاكل:
1. افحص السجلات: `docker logs video_downloader_bot`
2. تأكد من المتغيرات البيئية
3. تحقق من اتصال الإنترنت
4. راجع issues في GitHub

---

## ✅ قائمة التحقق النهائية

- [ ] Docker و Docker Compose مثبتان
- [ ] Portainer يعمل على المنفذ 9000
- [ ] المشروع مستنسخ من GitHub
- [ ] ملف Dockerfile موجود
- [ ] ملف docker-compose.yml موجود
- [ ] ملف .env مُعدّل بالقيم الصحيحة
- [ ] التوكن من @BotFather
- [ ] ADMIN_ID من @userinfobot
- [ ] البوت يعمل: `docker ps`
- [ ] السجلات طبيعية: `docker logs`
- [ ] البوت يستجيب في تيليجرام

---

**تم الإعداد بنجاح! 🎉**
instagram @W70T
