# سكان (Sukan)

تطبيق **High-End Full-Stack MVP** لإدارة السكن المشترك في السعودية.

## الميزات المتقدمة الحالية
- إدارة العقارات مع تفاصيل إضافية (الحي + الإيجار الأساسي).
- إدارة السكان بملف تفضيلات (اهتمامات، نمط النوم، مستوى النظافة).
- إدارة العقود مع التحقق من السعة والتواريخ.
- إدارة المدفوعات (إصدار فاتورة، تحصيل، تحديث المتأخرات تلقائيًا).
- لوحة تحكم KPI تشمل: الإشغال، عدد السكان، الإيراد المدفوع/المعلّق/المتأخر.
- توصيات توافق السكن بين السكان (`/matching/recommendations/{tenant_id}`).
- واجهة ويب متقدمة RTL موحدة لعمليات التشغيل اليومية.

## التشغيل
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn apps.api.main:app --reload
```

افتح:
- التطبيق: `http://127.0.0.1:8000/`
- Swagger: `http://127.0.0.1:8000/docs`

## API الرئيسية
- `GET /health`
- `GET/POST /properties`
- `GET/POST /tenants`
- `GET/POST /contracts`
- `GET/POST /payments`
- `POST /payments/{payment_id}/mark-paid`
- `POST /payments/refresh-overdue`
- `GET /dashboard`
- `GET /matching/recommendations/{tenant_id}`
- `POST /matching/score`

## اختبارات
```bash
pytest -q
```

## المسار التالي (نسخة Production)
1. إضافة Auth + RBAC + Audit Trail.
2. نقل SQLite إلى PostgreSQL مع migrations.
3. فصل Frontend إلى React/Next.js مع state management.
4. تكامل مع بوابة دفع حقيقية + webhooks.
5. Multi-tenant architecture للمشغّلين الكبار.
