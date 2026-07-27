<div align="center">
  <h1>📦 TIF App — نظام إدارة المخزون والتنبؤ بالمبيعات</h1>
  <p><strong>نظام متكامل لإدارة المخزون والتنبؤ الذكي بالمبيعات • Inventory Forecasting & Transfers</strong></p>
  <p>
    <img src="https://img.shields.io/badge/Python-3.11-blue?logo=python" alt="Python">
    <img src="https://img.shields.io/badge/Flask-3.1-black?logo=flask" alt="Flask">
    <img src="https://img.shields.io/badge/MongoDB-8.0-green?logo=mongodb" alt="MongoDB">
    <img src="https://img.shields.io/badge/AI-OpenRouter-orange?logo=openai" alt="AI">
    <img src="https://img.shields.io/badge/License-MIT-brightgreen" alt="MIT License">
  </p>
</div>

---

## ⚡ نبذة سريعة — Quick Overview

TIF App هو حل متكامل لإدارة المخزون وتحسين عمليات النقل بين الفروع مع دعم تنبؤات مبيعات دقيقة مدعومة بتقنيات تعلم الآلة والذكاء الاصطناعي. تم تصميمه ليخدم منشآت التجزئة والشركات متعددة الفروع التي تحتاج إلى:

- تقليل نفاد المخزون وتخفيض الفائض
- تحسين قرارات النقل بين الفروع
- الحصول على تقارير قابلة للتنفيذ بصيغة Excel
- الاستفادة من رؤى ذكية تولدها نماذج الـ AI

---

## ✨ أهم المزايا — Key Features

- التنبؤ بالمبيعات باستخدام XGBoost مع دعم العوامل الموسمية والمناسبات المحلية
- اقتراحات آلية للنقل بين الفروع وتوازن المخزون
- لوحة تحكم تحليلية مع تصنيف ABC، تنبيهات المخزون المنخفض والراكد
- تكامل مع OpenRouter (GPT-4o-mini) لتوليد رؤى وتقارير طبيعية اللغة
- إمكانية تصدير البيانات والتقارير إلى Excel
- نظام مصادقة وصلاحيات مرن للمستخدمين والمشرفين

---

## 🧰 التقنيات المستخدمة — Tech Stack

- Python 3.11+
- Flask 3.1.x
- MongoDB 8.0+
- XGBoost
- Pandas
- Bootstrap 5
- OpenRouter (GPT-4o-mini) — مزود AI

> ملاحظة مهمة: التطبيق يعتمد على MongoDB فقط — تم إزالة DuckDB و SQLite ولا يدعم قواعد SQL الأخرى.

---

## 🚀 سريع: بدء التشغيل — Quickstart

1. استنساخ المستودع

```bash
git clone https://github.com/Ramisharafaldin/TIF-APP.git
cd TIF-APP
```

2. إنشاء وتفعيل بيئة افتراضية

```bash
# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate

# Windows (PowerShell)
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

3. تثبيت التبعيات

```bash
pip install -r requirements.txt
```

4. إعداد ملف البيئة

```bash
cp .env.example .env    # أو: copy .env.example .env على Windows
```

حرّر `.env` وأضف المتغيرات الأساسية:

- SECRET_KEY — مفتاح سري لتوقيع الجلسات
- MONGO_URI — رابط اتصال MongoDB (مثال: mongodb://localhost:27017)
- OPENROUTER_API_KEY — مفتاح OpenRouter (لميزات AI)

5. تشغيل التطبيق (وضع التطوير)

```bash
# عبر CLI المرفق
python -m tif_ai.cli run

# أو مباشرة
python flask_app.py
```

ثم افتح: http://localhost:5000

---

## 🔧 إعداد الإنتاج — Production

- استخدم Waitress أو Gunicorn كخادم WSGI
- ضع Nginx كـ reverse proxy مع TLS
- اضبط متغيرات البيئة (`FLASK_ENV=production`, `SESSION_COOKIE_SECURE=true`, `SECRET_KEY` قوي)

أمثلة تشغيل:

```bash
# Waitress (Windows)
waitress-serve --port=5000 wsgi:app

# Gunicorn (Linux/macOS)
gunicorn -w 4 -b 0.0.0.0:5000 wsgi:app
```

---

## ⚙️ إعدادات وملفات مهمة — Configuration

- `.env` — إعدادات البيئة (غير مضمن في المستودع)
- `requirements.txt` — تبعيات Python
- `wsgi.py` — نقطة الإدخال للإنتاج

أمثلة متغيرات وبيئة إنتاج في `.env`:

```
FLASK_ENV=production
SECRET_KEY=<قيمة_عشوائية_قوية>
MONGO_URI=mongodb://username:password@host:27017/dbname
AI_ENABLED=true
AI_PROVIDER=openrouter
OPENROUTER_API_KEY=sk-or-v1-...
```

---

## 🧩 هيكل المشروع — Project Structure

```
TIF/
├── ai_providers/           # مزودات AI (OpenRouter, Gemini, ...)
├── db/                     # طبقة MongoDB
├── forecast_modules/       # نماذج التنبؤ
├── modules/                # وحدات التطبيق
├── static/                 # ملفات ثابتة (CSS, JS, images)
├── templates/              # قوالب HTML (Jinja2)
├── tests/                  # اختبارات الوحدة
├── tif_ai/                 # واجهة الأوامر (CLI)
├── flask_app.py            # مدخل Flask
├── wsgi.py                 # WSGI للإنتاج
├── requirements.txt
└── README.md
```

---

## ✅ تشغيل الاختبارات — Tests

```bash
# التحقق العام
tif doctor

# تشغيل جميع الاختبارات
pytest tests/ -v
```

---

## 🛠️ استكشاف الأخطاء — Troubleshooting

- SECRET_KEY not set: شغّل `python -c "import secrets; print(secrets.token_hex(32))"` وضع الناتج في `.env`
- MongoDB Connection Refused: تأكد من تشغيل MongoDB (`mongod --dbpath /data/db`)
- OpenRouter 401: تحقق من صحة مفتاح API في `.env`

---

## 📄 الترخيص — License

مشروع مفتوح المصدر مرخص بترخيص MIT.

---

<div align="center">
  <p>تم التطوير بواسطة فريق TIF • Built with ❤️ using Flask, MongoDB & AI</p>
  <p>لمزيد من المعلومات أو الحصول على دعم: افتح Issue أو اتصل عبر GitHub</p>
</div>
