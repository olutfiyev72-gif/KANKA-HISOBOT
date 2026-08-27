# 📊 Biznes Hisob Bot (E-Commerce Finance & Accounting Bot)

Production-ready Telegram finance and accounting bot for small e-commerce businesses and shops.

## 🏗️ Texnologik Stack va Arxitektura

- **Python 3.12+**
- **aiogram 3.x** (Telegram Bot Framework)
- **SQLAlchemy 2.0 (Async)** + **asyncpg** (PostgreSQL / Supabase)
- **Pydantic Settings v2** (Tip xavfsiz konfiguratsiya boshqaruvi)
- **Alembic** (Async migratsiyalar)
- **Loguru** (Strukturalangan asinxron loglar)
- **Decimal / Numeric(18, 2)** (Moliyaviy hisob-kitoblarda aniqlik, 0% float xatolik)
- **pytest & pytest-asyncio** (Asinxron test qoplamasi)
- **Docker & Docker Compose** (Konteynerlashtirish)

---

## 📁 Loyiha Strukturasi

```
biznes_bot/
├── alembic/                 # Alembic migratsiya skriptlari va muhiti
│   ├── env.py               # Async migratsiya drayveri
│   ├── script.py.mako       # Migratsiya shabloni
│   └── versions/            # Versiyalar tarixi
├── app/
│   ├── bot/                 # Telegram bot qatlami
│   │   ├── filters/         # Maxsus filtrlar (Admin, Role)
│   │   ├── handlers/        # Message va Callback handlerlar
│   │   ├── keyboards/       # Inline & Reply klaviaturalar
│   │   ├── middlewares/     # Database, Auth, Logging, Throttling
│   │   └── states/          # aiogram FSM holatlari
│   ├── config/              # Konfiguratsiya va doimiylar
│   │   ├── constants.py     # Tizim enumlari (TransactionType, DebtType, etc.)
│   │   └── settings.py      # Pydantic v2 Settings
│   ├── database/            # Ma'lumotlar bazasi qatlami
│   │   ├── base.py          # AsyncEngine, SessionMaker va Base model
│   │   ├── models/          # SQLAlchemy deklarativ modellari
│   │   ├── repositories/    # Repositoriy qatlami (CRUD & Data Access)
│   │   └── seeder.py        # Dastlabki ma'lumotlar (Kategoriyalar)
│   ├── schemas/             # Pydantic DTO va validatsiya sxemalari
│   │   ├── user.py
│   │   ├── category.py
│   │   ├── transaction.py
│   │   ├── product.py
│   │   ├── debt.py
│   │   ├── report.py
│   │   └── export.py
│   ├── services/            # Biznes mantiq qatlami (Domain Services)
│   │   ├── base.py
│   │   ├── finance_service.py
│   │   ├── product_service.py
│   │   ├── debt_service.py
│   │   ├── report_service.py
│   │   ├── export_service.py
│   │   ├── marketplace_service.py
│   │   └── ai_service.py
│   └── utils/               # Yordamchi modullar
│       ├── formatters.py    # Pul va sana formatlash
│       ├── logger.py        # Loguru sozlamalari
│       ├── quick_parser.py  # +/- tezkor kiritish tahlili
│       └── validators.py    # Kiritilgan ma'lumotlarni tekshirish
├── tests/                   # Pytest test to'plami
│   ├── conftest.py
│   ├── test_balance.py
│   ├── test_debts.py
│   ├── test_income.py
│   └── test_products.py
├── .env.example             # Namunaviy muhit o'zgaruvchilari
├── alembic.ini              # Alembic konfiguratsiyasi
├── Dockerfile               # Production Dockerfile
├── docker-compose.yml       # Docker Compose konfiguratsiyasi
├── main.py                  # Ilova kirish nuqtasi
├── pytest.ini               # Pytest konfiguratsiyasi
├── requirements.txt         # Python kutubxonalari
└── README.md                # Qo'llanma
```

---

## 🚀 O'rnatish va Ishga Tushirish

### 1. Muhitni tayyorlash

```bash
# Loyihaga kirish
cd biznes_bot

# Virtual muhit yaratish
python3 -m venv .venv
source .venv/bin/activate  # Mac / Linux
# yoki Windows uchun: .venv\Scripts\activate

# Kutubxonalarni o'rnatish
pip install -r requirements.txt
```

### 2. `.env` faylini sozlash

```bash
cp .env.example .env
```

`.env` faylini ochib, kerakli o'zgaruvchilarni kiriting:

```env
BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrSTUvwxYZ
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/biznes_bot
ADMIN_IDS=123456789
ENVIRONMENT=development
DEFAULT_TIMEZONE=Asia/Tashkent
```

> **Supabase ishlatilganda:**
> `DATABASE_URL=postgresql+asyncpg://postgres:[PASSWORD]@db.[PROJECT_REF].supabase.co:5432/postgres`

### 3. Migratsiyalar va Ma'lumotlar Bazasini sozlash

```bash
# Yangi migratsiya yaratish (model o'zgarganda)
alembic revision --autogenerate -m "Initial tables"

# Migratsiyani bazaga qo'llash
alembic upgrade head
```

### 4. Botni ishga tushirish

```bash
python main.py
```

---

## 🐳 Docker bilan ishga tushirish

```bash
# Docker Compose orqali PostgreSQL va Botni fonda ishga tushirish:
docker compose up -d

# Loglarni kuzatish:
docker compose logs -f bot
```

---

## 🧪 Testlarni ishga tushirish

```bash
# Barcha asinxron testlarni bajarish:
pytest -v
```

---

## 🔒 Xavfsizlik va Moliya Qoidalari

1. **Float ishlatilmaydi**: Barcha pul va miqdor qiymatlari uchun `Decimal` va PostgreSQL `Numeric(18, 2)` qo'llaniladi.
2. **Multi-tenant izolyatsiya**: Har bir so'rov foydalanuvchi `user_id` filtri orqali himoyalangan.
3. **Avtomatik Rollback**: Xatolik yuz berganda tranzaksiya middleware orqali avtomatik bekor qilinadi (rollback).
