<div align="center">
  <h1>📦 TIF App</h1>
  <p><strong>تطبيق إدارة المخزون والتنبؤ بالمبيعات</strong></p>
  <p><strong>Inventory Forecasting & Transfers</strong></p>
  <p>
    <img src="https://img.shields.io/badge/Python-3.11-blue?logo=python" alt="Python">
    <img src="https://img.shields.io/badge/Flask-3.1-black?logo=flask" alt="Flask">
    <img src="https://img.shields.io/badge/MongoDB-8.0-green?logo=mongodb" alt="MongoDB">
    <img src="https://img.shields.io/badge/AI-OpenRouter-orange?logo=openai" alt="AI">
  </p>
</div>

---

## 📋 نظرة عامة / Overview

**TIF App** هو نظام متكامل لإدارة المخزون والمبيعات، يجمع بين:

- **التنبؤ بالمبيعات** باستخدام نماذج XGBoost مع مراعاة العوامل الموسمية
- **تحليل وتوازن المخزون** بين الفروع
- **لوحة تحكم تفاعلية** مع تقارير Excel قابلة للتصدير
- **نظام ذكاء اصطناعي** عبر OpenRouter (GPT-4o-mini) لتوليد الرؤى والتقارير الذكية

---

## ✨ المميزات / Features

### 📈 التنبؤ بالمبيعات / Sales Forecasting
- تحليل البيانات التاريخية للمبيعات
- توليد تنبؤات دقيقة باستخدام XGBoost
- دمج العوامل الموسمية (رمضان، عيد الأضحى، إلخ)
- تقديم توصيات لإدارة المخزون
- تصدير النتائج إلى Excel

### 🏭 توازن المخزون بين الفروع / Branch Transfers
- تحليل حالة المخزون لكل فرع
- حساب أيام التغطية (Coverage Days)
- اقتراح نقل الأصناف تلقائيًا بين الفروع
- تقرير شامل بصيغة Excel

### 📊 لوحة تحكم تحليل المخزون / Inventory Dashboard
- تحليل بيانات المبيعات والمخزون
- تصنيف ABC للأصناف
- تحديد الأصناف الحرجية (Low Stock) والراكدة (Stagnant)
- تصدير تقرير تحليلي كامل

### 🤖 الذكاء الاصطناعي / AI Features
- رؤى ذكية للمخزون عبر OpenRouter
- معالجة اللغة الطبيعية للاستعلامات
- تقارير ذكية قابلة للتخصيص
- تنبؤات معززة بالذكاء الاصطناعي

### 🔐 نظام المصادقة / Authentication
- تسجيل دخول آمن للمستخدمين
- صلاحيات المشرف والعرض
- إدارة المستخدمين وتغيير كلمات المرور

---

## 🛠 التقنيات المستخدمة / Tech Stack

| التقنية | الإصدار |
|---|---|
| **Python** | 3.11+ |
| **Flask** | 3.1.x |
| **MongoDB** | 8.0+ |
| **OpenRouter AI** | GPT-4o-mini |
| **XGBoost** | 3.x |
| **Pandas** | 2.x |
| **Bootstrap** | 5.x |

---

## 🚀 دليل التثبيت الكامل / Installation Guide

### ♦️ المتطلبات الأساسية / Prerequisites

| المتطلب | ملاحظات |
|---|---|
| **Python 3.11+** | [تحميل Python](https://www.python.org/downloads/) |
| **MongoDB 8.0+** | [تحميل MongoDB Community](https://www.mongodb.com/try/download/community) |
| **Git** | [تحميل Git](https://git-scm.com/downloads) |

> **⚠️ تنبيه هام / Important Notice:**
> - **MongoDB إجباري** — هذا التطبيق لا يعمل بدون MongoDB. لا يمكن استخدام SQLite أو أي قاعدة SQL أخرى.
> - **MongoDB is required** — this application does NOT work without MongoDB. No SQLite or other SQL database is supported.
> - تمت إزالة DuckDB و SQLite بالكامل من المشروع. MongoDB هو المحرك الوحيد.
> - DuckDB and SQLite have been fully removed. MongoDB is the only supported database engine.

### 1️⃣ تحميل المشروع / Clone Repository

```bash
git clone https://github.com/<your-username>/TIF.git
cd TIF
```

### 2️⃣ إنشاء بيئة افتراضية / Create Virtual Environment

> **ملاحظة:** مجلد `.venv/` غير مضمن في المستودع. يجب إنشاؤه محليًا.
> **Note:** The `.venv/` folder is NOT included in the repository. You must create it locally.

```bash
# Windows
python -m venv .venv
.venv\Scripts\activate

# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate
```

### 3️⃣ تثبيت التبعيات / Install Dependencies

```bash
# تأكد أولاً من تفعيل البيئة الافتراضية (الخطوة 2)
# Make sure the virtual environment is activated first (step 2)
pip install -r requirements.txt
```

> 📦 `requirements.txt` يحتوي على جميع المكتبات المطلوبة (77 حزمة) بنسخ محددة.
> `requirements.txt` contains all required packages (77 packages) with pinned versions.

### 4️⃣ تشغيل MongoDB / Start MongoDB

```bash
# Windows (افتراضيًا يعمل كخدمة)
# أو شغّل يدويًا:
"C:\Program Files\MongoDB\Server\8.0\bin\mongod.exe" --dbpath=C:\data\db

# Linux / macOS
sudo systemctl start mongod
```

### 5️⃣ تثبيت واجهة الأوامر (اختياري) / Install CLI (Optional)

```bash
# هذا يتيح لك استخدام الأمر tif مباشرة
pip install -e .
```

### 6️⃣ إعداد ملف البيئة / Configure Environment

```bash
# انسخ ملف الإعدادات
copy .env.example .env

# أو على Linux/macOS
cp .env.example .env
```

ثم **قم بتحرير ملف `.env`** واستبدل القيم التالية:

| المتغير | الشرح | مثال |
|---|---|---|
| `SECRET_KEY` | مفتاح تشفير الجلسات (إجباري) | `python -c "import secrets; print(secrets.token_hex(32))"` |
| `OPENROUTER_API_KEY` | مفتاح API لـ OpenRouter [📌](#-api-keys) | `sk-or-v1-...` |
| `MONGO_URI` | رابط MongoDB | `mongodb://localhost:27017` |

### 7️⃣ الإعداد الأولي للتطبيق / First-Run Setup

**الخطوة 1 — تشغيل التطبيق:**
```bash
# الطريقة الموصى بها (CLI)
python -m tif_ai.cli run

# أو مباشرة
python flask_app.py
```

**الخطوة 2 — فتح المتصفح على:**
```
http://localhost:5000
```

**الخطوة 3 — إنشاء حساب المشرف:**
- ابحث في سجل التطبيق عن رمز الإعداد (setup token)
- افتح الرابط: `http://localhost:5000/setup?token=<TOKEN>`
- أدخل اسم المستخدم وكلمة المرور (8 أحرف على الأقل)
- سجل الدخول باستخدام البيانات التي أدخلتها

---

## 🔑 مفاتيح API

يتطلب التطبيق مفتاح API واحد على الأقل لتفعيل ميزات الذكاء الاصطناعي:

### OpenRouter (موصى به / Recommended)

1. سجل في [OpenRouter.ai](https://openrouter.ai/)
2. اذهب إلى [Keys](https://openrouter.ai/keys)
3. أنشئ مفتاح جديد
4. ضع المفتاح في `.env`:
   ```
   OPENROUTER_API_KEY=sk-or-v1-<مفتاحك>
   AI_PROVIDER=openrouter
   AI_ENABLED=true
   ```

### Google Gemini (بديل / Alternative)

1. سجل في [Google AI Studio](https://aistudio.google.com/)
2. اذهب إلى [API Keys](https://aistudio.google.com/app/apikey)
3. أنشئ مفتاح جديد
4. ضع المفتاح في `.env`:
   ```
   GEMINI_API_KEY=AIzaSy...
   AI_PROVIDER=gemini
   AI_ENABLED=true
   ```

> 💡 **نصيحة:** ابدأ بـ OpenRouter — يعطي 1$ مجاني للاختبار ولا يحتاج بطاقة ائتمان.

---

## 🏭 نشر الإنتاج / Production Deployment

### باستخدام Waitress (Windows موصى به)
```bash
pip install waitress
waitress-serve --port=5000 wsgi:app
```

### باستخدام Gunicorn (Linux/macOS)
```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 wsgi:app
```

### مع PM2 (إدارة العمليات)
```bash
npm install -g pm2
pm2 start "waitress-serve --port=5000 wsgi:app" --name tif-app
pm2 save
pm2 startup
```

### إعدادات الإنتاج الإضافية
```bash
# ملف .env للإنتاج
FLASK_ENV=production
SECRET_KEY=<مفتاح قوي عشوائي 64 حرف>
SESSION_COOKIE_SECURE=true
FLASK_HOST=127.0.0.1     # أو 0.0.0.0 للشبكة
FLASK_PORT=5000
```

> ⚠️ **هام:** استخدم反向 proxy مثل Nginx أمام التطبيق في الإنتاج.

---

## 📁 هيكل المشروع / Project Structure

```
TIF/
├── ai_providers/           # مزودات AI (OpenRouter, Gemini, إلخ)
├── db/                     # طبقة MongoDB
├── docs/                   # الوثائق
├── forecast_modules/       # نماذج التنبؤ
├── modules/                # وحدات التطبيق الأساسية
├── static/                 # ملفات ثابتة (CSS, JS, images)
├── templates/              # قوالب HTML (Jinja2)
├── tests/                  # 73 ملف اختبار
├── tif_ai/                 # واجهة الأوامر (CLI)
├── utils/                  # أدوات مساعدة
├── flask_app.py            # مدخل Flask الرئيسي
├── wsgi.py                 # WSGI للإنتاج
├── launcher.py             # مشغل التطبيق
├── auth_flask.py           # واجهة المصادقة
├── auth_mongo.py           # تطبيق MongoDB للمصادقة
├── data_store.py           # واجهة البيانات
├── data_store_mongo.py     # تطبيق MongoDB للبيانات
├── config.py               # إعدادات التطبيق
├── requirements.txt        # قائمة التبعيات
├── pyproject.toml          # بيانات المشروع
└── README.md               # هذا الملف
```

---

## 🧪 تشغيل الاختبارات / Running Tests

```bash
# فحص صحة النظام
tif doctor

# تشغيل جميع الاختبارات
pytest tests/ -v

# تشغيل اختبار محدد
pytest tests/test_authentication.py -v
```

---

## ❓ استكشاف الأخطاء / Troubleshooting

| المشكلة | الحل |
|---|---|
| `SECRET_KEY not set` | شغّل `python -c "import secrets; print(secrets.token_hex(32))"` وضع الناتج في `.env` |
| MongoDB Connection Refused | تأكد من تشغيل MongoDB: `mongod --dbpath=C:\data\db` |
| OpenRouter 401 | تحقق من صحة مفتاح API في `.env` |
| Flask port busy | غير المنفذ: `$env:FLASK_PORT=5001` |
| `.venv` غير موجود / not found | أنشئ البيئة الافتراضية: `python -m venv .venv` ثم `pip install -r requirements.txt` |
| `ModuleNotFoundError` | شغّل `pip install -r requirements.txt` في البيئة الافتراضية |

---

## 📜 الترخيص / License

المشروع مرخص تحت **MIT License**.

```
MIT License

Copyright (c) 2024

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions...
```

---

<div align="center">
  <p>🛠 تم التطوير باستخدام Flask + MongoDB + OpenRouter</p>
  <p>Built with ❤️</p>
</div>
#   T I F - A P P  
 #   T I F - A P P  
 