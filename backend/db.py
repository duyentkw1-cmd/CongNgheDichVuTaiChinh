"""SQLAlchemy models shared by SQLite quick demo and PostgreSQL."""
import hashlib
import os
import secrets
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from sqlalchemy import (Boolean, Date, DateTime, ForeignKey, Integer, Numeric,
                        String, Text, UniqueConstraint, create_engine, select)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / '.env')
DATA = ROOT / 'data'
DATA.mkdir(exist_ok=True)
TZ = ZoneInfo('Asia/Ho_Chi_Minh')

def today():
    return datetime.now(TZ).date()

def now():
    return datetime.now(TZ).replace(tzinfo=None)

DATABASE_URL = os.getenv('DATABASE_URL', f'sqlite:///{DATA / "demo.sqlite3"}')
engine = create_engine(DATABASE_URL, pool_pre_ping=True,
    connect_args={'check_same_thread': False} if DATABASE_URL.startswith('sqlite') else {})
SessionLocal = sessionmaker(engine, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

class Household(Base):
    __tablename__ = 'households'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))

class User(Base):
    __tablename__ = 'users'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    household_id: Mapped[str] = mapped_column(ForeignKey('households.id'), index=True)
    email: Mapped[str] = mapped_column(String(160), unique=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True, default=None)
    name: Mapped[str] = mapped_column(String(100))
    password_hash: Mapped[str] = mapped_column(Text)

def hash_password(value, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.scrypt(value.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()
    return f'{salt}:{digest}'

def verify_password(value, encoded):
    return secrets.compare_digest(hash_password(value, encoded.split(':')[0]), encoded)

class LoginSession(Base):
    __tablename__ = 'sessions'
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    expires_at: Mapped[datetime] = mapped_column(DateTime)

class Transaction(Base):
    __tablename__ = 'transactions'
    __table_args__ = (UniqueConstraint('household_id', 'request_id'),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    household_id: Mapped[str] = mapped_column(ForeignKey('households.id'), index=True)
    request_id: Mapped[str] = mapped_column(String(80))
    kind: Mapped[str] = mapped_column(String(10))
    amount: Mapped[int] = mapped_column(Numeric(16, 0))
    description: Mapped[str] = mapped_column(String(300))
    category: Mapped[str] = mapped_column(String(40))
    date: Mapped[datetime] = mapped_column(Date, index=True)
    payment: Mapped[str] = mapped_column(String(20), default='cash')
    scope: Mapped[str] = mapped_column(String(20), default='business')
    source: Mapped[str] = mapped_column(String(20), default='manual')
    raw_text: Mapped[str] = mapped_column(Text, default='')
    attachment_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    deleted: Mapped[bool] = mapped_column(Boolean, default=False)

class Budget(Base):
    __tablename__ = 'budgets'
    __table_args__ = (UniqueConstraint('household_id', 'category', 'period'),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    household_id: Mapped[str] = mapped_column(ForeignKey('households.id'))
    category: Mapped[str] = mapped_column(String(40))
    period: Mapped[str] = mapped_column(String(10), default='month')
    amount: Mapped[int] = mapped_column(Numeric(16, 0))

class Attachment(Base):
    __tablename__ = 'attachments'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    household_id: Mapped[str] = mapped_column(ForeignKey('households.id'))
    filename: Mapped[str] = mapped_column(String(80))

class Audit(Base):
    __tablename__ = 'audit_events'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    household_id: Mapped[str] = mapped_column(String(36), index=True)
    transaction_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    action: Mapped[str] = mapped_column(String(40))
    detail: Mapped[str] = mapped_column(Text, default='')
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

def init_db():
    import uuid
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        try:
            if DATABASE_URL.startswith('sqlite'):
                cols = [r[1] for r in conn.exec_driver_sql("PRAGMA table_info(users)").fetchall()]
                if cols and 'phone' not in cols:
                    conn.exec_driver_sql("ALTER TABLE users ADD COLUMN phone VARCHAR(20)")
            else:
                conn.exec_driver_sql("ALTER TABLE users ADD COLUMN IF NOT EXISTS phone VARCHAR(20)")
        except Exception:
            pass
    with SessionLocal() as db:
        if db.scalar(select(User).where(User.email == 'demo@sothuchi.vn')):
            return
        db.add(Household(id='demo-household', name='Tiệm nhỏ An Nhiên'))
        db.flush()
        db.add(User(id='demo-user', household_id='demo-household', email='demo@sothuchi.vn',
                    name='An Nhiên', password_hash=hash_password(os.getenv('DEMO_PASSWORD', 'Demo123!'))))
        for c, a in [('materials', 6000000), ('utilities', 1200000), ('shipping', 500000)]:
            db.add(Budget(id=str(uuid.uuid4()), household_id='demo-household', category=c, period='month', amount=a))
        # Dates are anchored at the first start in Vietnam time. No invented past performance.
        for offset in range(min(today().day, 21)):
            d = today() - timedelta(days=offset)
            rows = [('income', 2450000 if offset == 0 else 1700000 + offset % 5 * 180000,
                     'Tiền bán hàng hôm nay' if offset == 0 else 'Tiền bán hàng tại tiệm', 'sales', 'transfer'),
                    ('expense', 650000 if offset == 0 else 310000 + offset % 4 * 55000,
                     'Mua nguyên liệu', 'materials', 'cash')]
            if offset == 0:
                rows += [('expense', 320000, 'Thanh toán tiền điện', 'utilities', 'transfer')]
            if offset % 3 == 1:
                rows += [('expense', 45000, 'Phí giao hàng', 'shipping', 'cash')]
            for k, a, desc, cat, pay in rows:
                uid = str(uuid.uuid4())
                db.add(Transaction(id=uid, request_id=uid, household_id='demo-household', kind=k,
                    amount=a, description=desc, category=cat, date=d, payment=pay,
                    source=['manual', 'voice', 'image'][offset % 3], scope='business', raw_text='Dữ liệu mẫu minh họa.'))
        db.commit()
