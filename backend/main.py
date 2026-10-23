import hashlib
import json
import os
import secrets
import time
import uuid
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import date, timedelta
from typing import Literal

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import ai
from .db import (ROOT, DATA, DATABASE_URL, TZ, Attachment, Audit, Budget, Household,
                 LoginSession, SessionLocal, Transaction, User, hash_password, init_db, now, today, verify_password)
from .domain import (CATEGORIES, TransactionInput, budget_status, period_range,
                     select_transactions, serialize, summarize)
from .exports import export_file

@asynccontextmanager
async def lifespan(app):
    init_db()
    yield

app = FastAPI(title='Sổ Thu Chi AI · Local', version='2.0.0', lifespan=lifespan)
login_attempts = defaultdict(list)
ai_attempts = defaultdict(list)

@app.middleware('http')
async def security(request, call_next):
    if request.method in ('POST', 'PATCH', 'PUT', 'DELETE') and request.url.path.startswith('/api/'):
        if request.headers.get('x-requested-with') != 'so-thu-chi':
            return JSONResponse({'detail': 'Yêu cầu không hợp lệ.'}, status_code=403)
        try:
            if int(request.headers.get('content-length', '0')) > 6 * 1024 * 1024:
                return JSONResponse({'detail': 'Tệp vượt quá dung lượng cho phép.'}, status_code=413)
        except ValueError:
            return JSONResponse({'detail': 'Kích thước yêu cầu không hợp lệ.'}, status_code=400)
    response = await call_next(request)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'same-origin'
    if request.url.path.startswith('/api/'):
        response.headers['Cache-Control'] = 'no-store'
    return response

def db_session():
    with SessionLocal() as db:
        yield db

def current_user(request: Request, db: Session = Depends(db_session)):
    token = request.cookies.get('sothuchi_session', '')
    session = db.get(LoginSession, hashlib.sha256(token.encode()).hexdigest())
    if not session or session.expires_at <= now():
        raise HTTPException(401, 'Phiên đăng nhập đã hết. Vui lòng đăng nhập lại.')
    user = db.get(User, session.user_id)
    if user is None:
        raise HTTPException(401, 'Tài khoản không tồn tại.')
    return user

def audit(db, user, action, transaction_id=None, detail=''):
    db.add(Audit(id=str(uuid.uuid4()), household_id=user.household_id,
                 transaction_id=transaction_id, action=action, detail=detail))

def user_info(user, db):
    return {'name': user.name, 'email': user.email, 'phone': user.phone,
            'household': db.get(Household, user.household_id).name}

class LoginInput(BaseModel):
    email: str = Field(max_length=160)
    password: str = Field(max_length=200)

class RegisterInput(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: str | None = Field(default=None, max_length=160)
    phone: str | None = Field(default=None, max_length=20)
    password: str = Field(min_length=6, max_length=200)
    shop_name: str | None = Field(default=None, max_length=100)

@app.post('/api/auth/register')
def register(body: RegisterInput, request: Request, response: Response, db: Session = Depends(db_session)):
    import re as _re
    name = body.name.strip()
    raw_email = body.email.strip().lower() if body.email and body.email.strip() else None
    raw_phone = body.phone.strip() if body.phone and body.phone.strip() else None
    phone = _re.sub(r'[^\d+]', '', raw_phone) if raw_phone else None

    if not name:
        raise HTTPException(422, 'Họ và tên không được để trống.')
    if len(body.password) < 6:
        raise HTTPException(422, 'Mật khẩu phải có ít nhất 6 ký tự.')
    if not raw_email and not phone:
        raise HTTPException(422, 'Vui lòng nhập email hoặc số điện thoại để đăng ký.')
    if raw_email and not _re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', raw_email):
        raise HTTPException(422, 'Email không đúng định dạng.')
    if phone and not _re.fullmatch(r'[+]?\d{9,15}', phone):
        raise HTTPException(422, 'Số điện thoại không hợp lệ (từ 9 đến 15 chữ số).')

    # Guaranteed unique email for DB record: use user email or phone-derived address
    clean_phone_digits = phone.replace('+', '') if phone else ''
    email = raw_email or f'phone_{clean_phone_digits}@sothuchi.local'

    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, 'Email này đã được đăng ký. Hãy đăng nhập hoặc dùng email khác.')
    if phone and db.scalar(select(User).where(User.phone == phone)):
        raise HTTPException(409, 'Số điện thoại này đã được đăng ký. Hãy đăng nhập hoặc dùng số khác.')

    hid = str(uuid.uuid4())
    uid = str(uuid.uuid4())
    shop_name = body.shop_name.strip() if body.shop_name and body.shop_name.strip() else f'Tiệm của {name}'
    db.add(Household(id=hid, name=shop_name[:100]))
    db.flush()
    user = User(id=uid, household_id=hid, email=email, phone=phone, name=name[:100],
                password_hash=hash_password(body.password))
    db.add(user)
    # Starter budgets for the new household so budget alerts work smoothly
    for c, a in [('materials', 5000000), ('utilities', 1000000), ('shipping', 500000)]:
        db.add(Budget(id=str(uuid.uuid4()), household_id=hid, category=c, period='month', amount=a))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'Email hoặc số điện thoại đã tồn tại. Hãy thử lại.') from None

    token = secrets.token_urlsafe(32)
    db.add(LoginSession(token_hash=hashlib.sha256(token.encode()).hexdigest(), user_id=uid,
                        expires_at=now() + timedelta(hours=8)))
    db.commit()
    response.set_cookie('sothuchi_session', token, httponly=True, samesite='strict',
                        secure=os.getenv('COOKIE_SECURE', 'false').lower() == 'true', max_age=28800)
    return user_info(user, db)

@app.post('/api/auth/login')
def login(body: LoginInput, request: Request, response: Response, db: Session = Depends(db_session)):
    import re as _re
    from sqlalchemy import or_
    key = request.client.host if request.client else 'local'
    login_attempts[key] = [t for t in login_attempts[key] if t > time.time() - 300]
    if len(login_attempts[key]) >= 10:
        raise HTTPException(429, 'Bạn đã thử quá nhiều lần. Vui lòng thử lại sau 5 phút.')
    
    raw_identifier = body.email.strip().lower()
    # Digits inside an email must not be treated as a phone number. Otherwise
    # `shop0912345678@example.com` can match a different user whose phone is
    # 0912345678, so the real email login fails (or hits the wrong account).
    if '@' in raw_identifier:
        user = db.scalar(select(User).where(User.email == raw_identifier))
    else:
        clean_phone = _re.sub(r'[^\d+]', '', raw_identifier)
        digits = clean_phone.replace('+', '')
        conditions = [User.email == raw_identifier]
        if digits:
            conditions.extend([
                User.phone == clean_phone,
                User.phone == raw_identifier,
                User.phone == digits,
                User.email == f'phone_{digits}@sothuchi.local',
            ])
        user = db.scalar(select(User).where(or_(*conditions)))
    if not user or not verify_password(body.password, user.password_hash):
        login_attempts[key].append(time.time())
        raise HTTPException(401, 'Email, số điện thoại hoặc mật khẩu chưa đúng.')
    login_attempts[key] = []
    old = request.cookies.get('sothuchi_session')
    if old:
        previous = db.get(LoginSession, hashlib.sha256(old.encode()).hexdigest())
        if previous:
            db.delete(previous)
    token = secrets.token_urlsafe(32)
    db.add(LoginSession(token_hash=hashlib.sha256(token.encode()).hexdigest(), user_id=user.id,
                        expires_at=now() + timedelta(hours=8)))
    audit(db, user, 'login')
    db.commit()
    response.set_cookie('sothuchi_session', token, httponly=True, samesite='strict',
                        secure=os.getenv('COOKIE_SECURE', 'false').lower() == 'true', max_age=28800)
    return user_info(user, db)

@app.post('/api/auth/logout')
def logout(request: Request, response: Response, db: Session = Depends(db_session)):
    token = request.cookies.get('sothuchi_session', '')
    session = db.get(LoginSession, hashlib.sha256(token.encode()).hexdigest())
    if session:
        db.delete(session)
        db.commit()
    response.delete_cookie('sothuchi_session')
    return {'ok': True}

@app.get('/api/auth/me')
def me(user: User = Depends(current_user), db: Session = Depends(db_session)):
    return user_info(user, db)

@app.get('/api/meta')
def meta():
    return {'today': today().isoformat(), 'timezone': 'Asia/Ho_Chi_Minh', 'ai': ai.capabilities(),
        'database': 'PostgreSQL' if DATABASE_URL.startswith('postgresql') else 'SQLite · demo local',
        'categories': [{'id': k, 'label': v[0], 'kind': v[1]} for k, v in CATEGORIES.items()]}

def query_range(start, end, period):
    a, b = period_range(period)
    a, b = start or a, end or b
    if a > b or (b - a).days > 366:
        raise HTTPException(422, 'Kỳ báo cáo cần hợp lệ và không dài quá 366 ngày.')
    return a, b

@app.get('/api/report')
def report(start: date | None = None, end: date | None = None,
           period: Literal['day', 'week', 'month'] = 'month',
           scope: Literal['business', 'personal', 'all'] = 'business',
           user: User = Depends(current_user), db: Session = Depends(db_session)):
    start, end = query_range(start, end, period)
    rows = select_transactions(db, user.household_id, start, end, scope)
    return {**summarize(rows, start, end), 'transactions': [serialize(t) for t in rows],
            'start': start.isoformat(), 'end': end.isoformat(), 'scope': scope,
            'budgets': budget_status(db, user.household_id)}

def find_transaction(db, user, tid):
    row = db.scalar(select(Transaction).where(Transaction.id == tid,
        Transaction.household_id == user.household_id, Transaction.deleted.is_(False)))
    if row is None:
        raise HTTPException(404, 'Không tìm thấy giao dịch.')
    return row

def check_attachment(db, user, attachment_id):
    if attachment_id:
        a = db.get(Attachment, attachment_id)
        if not a or a.household_id != user.household_id:
            raise HTTPException(404, 'Không tìm thấy ảnh đính kèm.')

@app.post('/api/transactions')
def create_transaction(body: TransactionInput, user: User = Depends(current_user), db: Session = Depends(db_session)):
    existing = db.scalar(select(Transaction).where(Transaction.household_id == user.household_id,
        Transaction.request_id == body.request_id))
    if existing:
        return serialize(existing)
    check_attachment(db, user, body.attachment_id)
    duplicate = db.scalar(select(Transaction).where(Transaction.household_id == user.household_id,
        Transaction.date == body.date, Transaction.amount == body.amount, Transaction.kind == body.kind,
        Transaction.description == body.description, Transaction.scope == body.scope, Transaction.deleted.is_(False)))
    if duplicate and not body.allow_duplicate:
        raise HTTPException(409, 'Đã có giao dịch cùng nội dung, số tiền và ngày. Kiểm tra trước khi lưu thêm.')
    row = Transaction(id=str(uuid.uuid4()), household_id=user.household_id,
                      **body.model_dump(exclude={'allow_duplicate'}))
    db.add(row)
    audit(db, user, 'create', row.id)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(select(Transaction).where(Transaction.household_id == user.household_id,
            Transaction.request_id == body.request_id))
        if existing:
            return serialize(existing)
        raise HTTPException(409, 'Giao dịch vừa thay đổi. Vui lòng tải lại.')
    return serialize(row)

@app.put('/api/transactions/{tid}')
def edit_transaction(tid: str, body: TransactionInput, user: User = Depends(current_user), db: Session = Depends(db_session)):
    row = find_transaction(db, user, tid)
    check_attachment(db, user, body.attachment_id)
    before = serialize(row)
    for k, v in body.model_dump(exclude={'allow_duplicate', 'request_id'}).items():
        setattr(row, k, v)
    row.updated_at = now()
    audit(db, user, 'edit', tid, json.dumps({'before': before, 'after': serialize(row)}, ensure_ascii=False))
    db.commit()
    return serialize(row)

@app.delete('/api/transactions/{tid}')
def delete_transaction(tid: str, user: User = Depends(current_user), db: Session = Depends(db_session)):
    row = find_transaction(db, user, tid)
    row.deleted = True
    row.updated_at = now()
    audit(db, user, 'delete', tid)
    db.commit()
    return {'ok': True}

@app.get('/api/transactions/{tid}/history')
def history(tid: str, user: User = Depends(current_user), db: Session = Depends(db_session)):
    find_transaction(db, user, tid)
    rows = db.scalars(select(Audit).where(Audit.transaction_id == tid,
        Audit.household_id == user.household_id).order_by(Audit.created_at.desc())).all()
    return [{'action': x.action, 'at': x.created_at.replace(tzinfo=TZ).isoformat(), 'detail': x.detail} for x in rows]

class SettingsInput(BaseModel):
    household: str = Field(min_length=1, max_length=100)

@app.put('/api/settings')
def settings(body: SettingsInput, user: User = Depends(current_user), db: Session = Depends(db_session)):
    name = body.household.strip()
    if not name:
        raise HTTPException(422, 'Tên cửa hàng không được để trống.')
    db.get(Household, user.household_id).name = name
    db.commit()
    return user_info(user, db)

class BudgetInput(BaseModel):
    category: str
    period: Literal['day', 'week', 'month']
    amount: int = Field(gt=0, le=1000000000000, strict=True)

@app.post('/api/budgets')
def save_budget(body: BudgetInput, user: User = Depends(current_user), db: Session = Depends(db_session)):
    if body.category not in CATEGORIES or CATEGORIES[body.category][1] != 'expense':
        raise HTTPException(422, 'Hãy chọn một nhóm chi kinh doanh.')
    row = db.scalar(select(Budget).where(Budget.household_id == user.household_id,
        Budget.category == body.category, Budget.period == body.period))
    if row:
        row.amount = body.amount
    else:
        db.add(Budget(id=str(uuid.uuid4()), household_id=user.household_id, **body.model_dump()))
    db.commit()
    return budget_status(db, user.household_id)

@app.delete('/api/budgets/{bid}')
def delete_budget(bid: str, user: User = Depends(current_user), db: Session = Depends(db_session)):
    row = db.get(Budget, bid)
    if not row or row.household_id != user.household_id:
        raise HTTPException(404, 'Không tìm thấy ngưỡng.')
    db.delete(row)
    db.commit()
    return {'ok': True}

@app.get('/api/exports')
def export(start: date, end: date, format: Literal['csv', 'xlsx', 'pdf'] = 'xlsx',
           kind: Literal['all', 'revenue'] = 'all', scope: Literal['business', 'personal', 'all'] = 'business',
           user: User = Depends(current_user), db: Session = Depends(db_session)):
    start, end = query_range(start, end, 'month')
    rows = select_transactions(db, user.household_id, start, end, scope)
    content, content_type = export_file(rows, start, end, db.get(Household, user.household_id).name, kind, format, scope)
    audit(db, user, 'export', detail=f'{kind}/{format}/{start}/{end}/{scope}')
    db.commit()
    return Response(content, media_type=content_type,
        headers={'Content-Disposition': f'attachment; filename="so-{kind}-{start}-{end}.{format}"'})

def ai_quota(user):
    key = user.id
    ai_attempts[key] = [t for t in ai_attempts[key] if t > time.time() - 60]
    if len(ai_attempts[key]) >= 20:
        raise HTTPException(429, 'Vui lòng đợi một phút trước khi phân tích tiếp.')
    ai_attempts[key].append(time.time())

class TextInput(BaseModel):
    text: str = Field(min_length=1, max_length=10000)
    consent: bool = False
    sample: bool = False

@app.get('/api/ai/status')
def ai_status(user: User = Depends(current_user)):
    return ai.connection_status()

@app.get('/api/ai/dataset/{split}')
def download_dataset(split: Literal['train','validation','test'], user: User = Depends(current_user)):
    return FileResponse(ROOT / 'datasets' / f'{split}.csv', media_type='text/csv', filename=f'{split}.csv')

@app.post('/api/ai/text')
async def ai_text(body: TextInput, user: User = Depends(current_user)):
    ai_quota(user)
    return await ai.extract(body.text, body.consent, body.sample)

@app.post('/api/ai/image')
async def ai_image(file: UploadFile = File(...), consent: bool = Form(False), user: User = Depends(current_user)):
    ai_quota(user)
    return await ai.read_image(await file.read(5 * 1024 * 1024 + 1), consent)

@app.post('/api/ai/voice')
async def ai_voice(file: UploadFile = File(...), consent: bool = Form(False), user: User = Depends(current_user)):
    ai_quota(user)
    return await ai.transcribe(await file.read(5 * 1024 * 1024 + 1), file.content_type, consent)

@app.post('/api/attachments')
async def attachment(file: UploadFile = File(...), user: User = Depends(current_user), db: Session = Depends(db_session)):
    content = ai.clean_image(await file.read(5 * 1024 * 1024 + 1))
    uid = str(uuid.uuid4())
    path = DATA / 'attachments'
    path.mkdir(exist_ok=True)
    (path / f'{uid}.jpg').write_bytes(content)
    db.add(Attachment(id=uid, household_id=user.household_id, filename=f'{uid}.jpg'))
    db.commit()
    return {'id': uid}

@app.get('/api/attachments/{aid}')
def get_attachment(aid: str, user: User = Depends(current_user), db: Session = Depends(db_session)):
    check_attachment(db, user, aid)
    row = db.get(Attachment, aid)
    path = DATA / 'attachments' / row.filename
    if not path.exists():
        raise HTTPException(404, 'Ảnh không còn trên máy chủ.')
    return FileResponse(path, media_type='image/jpeg')

@app.get('/api/health')
def health():
    return {'ok': True}

@app.get('/sample-receipt.png')
def sample_receipt():
    return FileResponse(ROOT / 'backend' / 'assets' / 'sample-receipt.png')

dist = ROOT / 'frontend' / 'dist'
if dist.exists():
    app.mount('/', StaticFiles(directory=dist, html=True), name='frontend')
