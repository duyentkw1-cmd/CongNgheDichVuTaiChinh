"""Shared financial rules. Reports and exports always select the same confirmed rows."""
import calendar
import re
import unicodedata
from datetime import date, timedelta
from typing import Literal

from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select

from .db import Budget, Transaction, today, TZ

CATEGORIES = {
    'sales': ('Tiền bán hàng', 'income'), 'service': ('Dịch vụ', 'income'),
    'capital': ('Vốn bổ sung / tiền vay', 'income'), 'other_income': ('Thu khác', 'income'),
    'materials': ('Nguyên liệu / nhập hàng', 'expense'), 'rent': ('Thuê mặt bằng', 'expense'),
    'utilities': ('Điện, nước, Internet', 'expense'), 'shipping': ('Vận chuyển', 'expense'),
    'salary': ('Lương nhân viên', 'expense'), 'other_expense': ('Chi khác', 'expense')
}
REVENUE_CATEGORIES = {'sales', 'service'}

class TransactionInput(BaseModel):
    kind: Literal['income', 'expense']
    amount: int = Field(gt=0, le=1000000000000, strict=True)
    description: str = Field(min_length=1, max_length=300)
    category: str
    date: date
    payment: Literal['cash', 'transfer'] = 'cash'
    scope: Literal['business', 'personal'] = 'business'
    source: Literal['manual', 'text', 'voice', 'image'] = 'manual'
    raw_text: str = Field(default='', max_length=10000)
    attachment_id: str | None = None
    request_id: str = Field(min_length=8, max_length=80)
    allow_duplicate: bool = False

    @model_validator(mode='after')
    def check_fields(self):
        self.description = self.description.strip()
        if not self.description:
            raise ValueError('Vui lòng nhập nội dung giao dịch.')
        if self.category not in CATEGORIES or CATEGORIES[self.category][1] != self.kind:
            raise ValueError('Nhóm giao dịch không khớp với khoản thu / chi.')
        if self.date > today():
            raise ValueError('Ngày giao dịch không được nằm trong tương lai.')
        return self

def period_range(period='month', anchor=None):
    d = anchor or today()
    if period == 'day':
        return d, d
    if period == 'week':
        start = d - timedelta(days=d.weekday())
        return start, start + timedelta(days=6)
    return d.replace(day=1), d.replace(day=calendar.monthrange(d.year, d.month)[1])

def select_transactions(db, household_id, start, end, scope='business'):
    q = select(Transaction).where(Transaction.household_id == household_id,
        Transaction.deleted.is_(False), Transaction.date >= start, Transaction.date <= end)
    if scope != 'all':
        q = q.where(Transaction.scope == scope)
    return db.scalars(q.order_by(Transaction.date.desc(), Transaction.created_at.desc())).all()

def serialize(t):
    return {k: (int(getattr(t, k)) if k == 'amount' else (getattr(t, k).replace(tzinfo=TZ).isoformat() if k != 'date' else getattr(t, k).isoformat())
                if k in ('date', 'created_at', 'updated_at') else getattr(t, k))
            for k in ('id', 'kind', 'amount', 'description', 'category', 'date', 'payment',
                      'scope', 'source', 'raw_text', 'attachment_id', 'created_at', 'updated_at')}

def summarize(rows, start, end):
    income = sum(int(t.amount) for t in rows if t.kind == 'income')
    expense = sum(int(t.amount) for t in rows if t.kind == 'expense')
    revenue = sum(int(t.amount) for t in rows if t.kind == 'income' and t.category in REVENUE_CATEGORIES and t.scope == 'business')
    groups = {}
    series = {}
    d = start
    while d <= end:
        series[d.isoformat()] = {'date': d.isoformat(), 'income': 0, 'expense': 0}
        d += timedelta(days=1)
    for t in rows:
        series[t.date.isoformat()][t.kind] += int(t.amount)
        if t.kind == 'expense':
            groups[t.category] = groups.get(t.category, 0) + int(t.amount)
    return {'income': income, 'expense': expense, 'balance': income - expense, 'revenue': revenue,
            'count': len(rows), 'series': list(series.values()),
            'categories': [{'category': c, 'amount': a, 'label': CATEGORIES[c][0]}
                           for c, a in sorted(groups.items(), key=lambda x: -x[1])]}

def budget_status(db, household_id):
    result = []
    for b in db.scalars(select(Budget).where(Budget.household_id == household_id)).all():
        start, end = period_range(b.period)
        rows = select_transactions(db, household_id, start, end)
        actual = sum(int(t.amount) for t in rows if t.kind == 'expense' and t.category == b.category)
        limit = int(b.amount)
        result.append({'id': b.id, 'category': b.category, 'label': CATEGORIES[b.category][0],
                       'period': b.period, 'limit': limit, 'actual': actual,
                       'exceeded': actual > limit, 'over': max(0, actual - limit),
                       'start': start.isoformat(), 'end': end.isoformat()})
    return result

def fold(text):
    return ''.join(c for c in unicodedata.normalize('NFD', text.lower().replace('đ', 'd'))
                   if unicodedata.category(c) != 'Mn')

