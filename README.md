# سكان (Sukan) — Final High-End Full-Stack

نسخة نهائية متقدمة لمنصة سكان لإدارة السكن المشترك (Co-living) تشغيليًا وماليًا.

## المزايا النهائية
- **Auth حقيقي**: تسجيل دخول باسم مستخدم/كلمة مرور + جلسات token بوقت انتهاء.
- **RBAC**: أدوار `admin` / `operator` / `viewer`.
- **User Management**: إنشاء مستخدمين جدد بواسطة admin.
- **Core Operations**: إدارة العقارات، السكان، العقود.
- **Finance Ops**: مدفوعات + تحصيل + مصروفات + صافي كاش.
- **Maintenance Ops**: نظام تذاكر صيانة (tickets) مع حالات معالجة.
- **Smart Matching**: توصيات توافق بين السكان.
- **Compliance**: سجل تدقيق Audit Logs.
- **Reporting**: تقرير مالي CSV قابل للتصدير (`/reports/finance.csv`).
- **Full-Stack Console**: واجهة ويب تشغيلية متقدمة متصلة مباشرة بالـ API.

## تشغيل محلي
```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m uvicorn apps.api.main:app --reload
```

- Console: `http://127.0.0.1:8000/`
- API docs: `http://127.0.0.1:8000/docs`

## Render Deployment (fixed)
- **Build Command**
  - `python -m pip install --upgrade pip && python -m pip install -r requirements.txt`
- **Start Command**
  - `python -m uvicorn apps.api.main:app --host 0.0.0.0 --port ${PORT:-10000}`

> تم إضافة `render.yaml` و `nixpacks.toml` لتثبيت إعدادات البناء/التشغيل بشكل صريح ومنع أخطاء `Railpack build plan`.

## بيانات الدخول الافتراضية
- username: `admin`
- password: `admin123`

## اختبارات
```bash
pytest -q
```
