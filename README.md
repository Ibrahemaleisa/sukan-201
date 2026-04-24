# سكان (Sukan)

تطبيق **Full-Stack MVP** لحوكمة وتنظيم السكن المشترك (**Co-living**) في المملكة العربية السعودية.

## ما الذي يعمل الآن؟
- Backend API مبني على **FastAPI**.
- قاعدة بيانات **SQLite** (تشغيل مباشر بدون إعدادات معقدة).
- Frontend Web Dashboard (HTML/CSS/JS) لعمليات:
  - إضافة وحدات سكنية.
  - إضافة عقود.
  - متابعة مؤشرات الإشغال بشكل مباشر.

## تشغيل التطبيق (Backend + Frontend)
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn apps.api.main:app --reload
```

ثم افتح:
- التطبيق: `http://127.0.0.1:8000/`
- Swagger API: `http://127.0.0.1:8000/docs`

> ملاحظة: يتم إنشاء قاعدة البيانات تلقائيًا باسم `sukan.db`.
> لتحديد مسار مختلف: `SUKAN_DB_PATH=/path/to/db.sqlite uvicorn apps.api.main:app --reload`

## المزايا الحالية (MVP)
- `GET /health`
- `GET /properties`
- `POST /properties`
- `GET /contracts`
- `POST /contracts`
- `GET /dashboard`
- `POST /matching/score?interests_overlap=7&schedule_alignment=8&cleanliness_alignment=9`

## اختبارات
```bash
source .venv/bin/activate
pytest -q
```

## هيكل المشروع
```text
apps/
├─ api/
│  └─ main.py
└─ web/
   └─ index.html
tests/
└─ test_api.py
```

## الخطوة التالية المقترحة
1. نقل الواجهة إلى React/Next.js.
2. إضافة نظام تسجيل دخول وصلاحيات (RBAC).
3. إضافة PostgreSQL + Alembic migrations للإنتاج.
4. إضافة إدارة مدفوعات متكاملة (Payment Gateway).
