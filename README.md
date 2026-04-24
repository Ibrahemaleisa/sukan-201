# سكان (Sukan)

منصة **PropTech** لحوكمة وتنظيم السكن المشترك (**Co-living**) في المملكة العربية السعودية.

## ماذا يوجد الآن في المستودع؟
- وثائق تأسيس المشروع (الرؤية، PRD، المعمارية).
- **MVP API أولي** باستخدام FastAPI لإدارة:
  - الوحدات السكنية المشتركة.
  - العقود الأساسية.
  - درجة توافق مبدئية بين المستأجرين.

## تشغيل الـ API محليًا
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn apps.api.main:app --reload
```

بعد التشغيل:
- Swagger UI: `http://127.0.0.1:8000/docs`
- Health check: `http://127.0.0.1:8000/health`

## الاختبارات
```bash
source .venv/bin/activate
pytest -q
```

## endpoints الحالية (MVP)
- `GET /health`
- `GET /properties`
- `POST /properties`
- `GET /contracts`
- `POST /contracts`
- `POST /matching/score?interests_overlap=7&schedule_alignment=8`

## خارطة الخطوة التالية
1. إضافة قاعدة بيانات PostgreSQL بدل التخزين المؤقت داخل الذاكرة.
2. إضافة مصادقة وصلاحيات (RBAC).
3. بناء واجهة ويب أولية للملاك والمشغلين.

للتفاصيل المنتجية والمعمارية:
- `docs/PRD.md`
- `docs/ARCHITECTURE.md`
