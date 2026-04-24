# سكان (Sukan)

**Sukan v2.0** — منصة تشغيل متقدمة جدًا (Too Advanced MVP) لقطاع السكن المشترك.

## ما الجديد في النسخة المتقدمة
- **Role-based access** عبر token-based login (`admin`, `operator`, `viewer`).
- **Audit Trail** لكل العمليات الحساسة (إنشاء وحدات/سكان/عقود/مدفوعات/مصروفات).
- **إدارة تشغيل مالية كاملة**: فواتير، تحصيل، متأخرات، مصروفات، وصافي كاش.
- **تنبيهات انتهاء العقود** عبر `/alerts/expiring-contracts`.
- **بحث + Pagination** في قوائم العقارات/السكان/المدفوعات.
- **واجهة تشغيل موحدة** تدعم تسجيل الدخول، إدارة الكيانات، وإظهار Audit Logs.

## تشغيل التطبيق
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn apps.api.main:app --reload
```

- UI: `http://127.0.0.1:8000/`
- API Docs: `http://127.0.0.1:8000/docs`

## أهم الـ Endpoints
- Auth: `POST /auth/login`
- Core: `GET/POST /properties`, `GET/POST /tenants`, `GET/POST /contracts`
- Finance: `GET/POST /payments`, `POST /payments/{id}/mark-paid`, `POST /payments/refresh-overdue`, `GET/POST /expenses`
- Intelligence: `GET /dashboard`, `GET /alerts/expiring-contracts`, `GET /matching/recommendations/{tenant_id}`
- Compliance: `GET /audit/logs` (admin only)

## اختبارات
```bash
pytest -q
```
