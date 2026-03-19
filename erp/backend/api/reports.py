from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, extract
from typing import Optional
from datetime import date, timedelta
from erp.backend.db.session import get_db
from erp.backend.db.models import PettyCashRecord, AccountsPayable

router = APIRouter(prefix="/reports", tags=["reports"])


def _period_dates(period: str):
    """Return (start, end, prev_start, prev_end) for period label."""
    today = date.today()
    if period == "month":
        start = today.replace(day=1)
        # last day of month
        if today.month == 12:
            end = today.replace(month=12, day=31)
        else:
            end = today.replace(month=today.month + 1, day=1) - timedelta(days=1)
        prev_start = (start - timedelta(days=1)).replace(day=1)
        prev_end = start - timedelta(days=1)
    elif period == "quarter":
        q = (today.month - 1) // 3
        start = today.replace(month=q * 3 + 1, day=1)
        prev_q_start_month = (q - 1) * 3 + 1
        if prev_q_start_month <= 0:
            prev_q_start_month += 12
            prev_year = today.year - 1
        else:
            prev_year = today.year
        prev_start = date(prev_year, prev_q_start_month, 1)
        prev_end = start - timedelta(days=1)
        end = today
    else:  # year
        start = today.replace(month=1, day=1)
        end = today
        prev_start = date(today.year - 1, 1, 1)
        prev_end = date(today.year - 1, 12, 31)
    return start, end, prev_start, prev_end


def _sum_petty(db, type_list, start, end):
    return float(db.query(func.sum(PettyCashRecord.amount)).filter(
        PettyCashRecord.type.in_(type_list),
        PettyCashRecord.created_at >= start,
        PettyCashRecord.created_at <= end,
    ).scalar() or 0)


@router.get("/pl")
def get_pl(period: str = "month", db: Session = Depends(get_db)):
    start, end, prev_start, prev_end = _period_dates(period)

    inc = _sum_petty(db, ["income"], start, end)
    prev_inc = _sum_petty(db, ["income"], prev_start, prev_end)
    exp = _sum_petty(db, ["expense", "withdrawal"], start, end)
    prev_exp = _sum_petty(db, ["expense", "withdrawal"], prev_start, prev_end)

    def pct(cur, prev):
        if prev == 0: return None
        return round((cur - prev) / prev * 100, 1)

    return {
        "period": period,
        "period_label": f"{start.strftime('%Y年%m月')} ~ {end.strftime('%m月')}",
        "kpis": {
            "revenue": {"current": inc, "previous": prev_inc, "change_percent": pct(inc, prev_inc)},
            "cogs": {"current": 0, "previous": 0, "change_percent": None},
            "gross_profit": {"current": inc, "previous": prev_inc, "change_percent": pct(inc, prev_inc)},
            "expenses": {"current": exp, "previous": prev_exp, "change_percent": pct(exp, prev_exp)},
            "net_profit": {"current": inc - exp, "previous": prev_inc - prev_exp, "change_percent": pct(inc - exp, prev_inc - prev_exp)},
        },
        "revenue_lines": [
            {"account": "銷售收入", "current": inc, "previous": prev_inc, "variance": inc - prev_inc, "change_percent": pct(inc, prev_inc)},
        ],
        "expense_lines": [
            {"account": "零用金支出", "current": exp, "previous": prev_exp, "variance": exp - prev_exp, "change_percent": pct(exp, prev_exp)},
        ],
    }


@router.get("/pl/trend")
def get_pl_trend(months: int = 6, db: Session = Depends(get_db)):
    today = date.today()
    result = []
    for i in range(months - 1, -1, -1):
        y = today.year
        m = today.month - i
        while m <= 0:
            m += 12
            y -= 1
        month_start = date(y, m, 1)
        if m == 12:
            month_end = date(y, 12, 31)
        else:
            month_end = date(y, m + 1, 1) - timedelta(days=1)

        inc = _sum_petty(db, ["income"], month_start, month_end)
        exp = _sum_petty(db, ["expense", "withdrawal"], month_start, month_end)
        result.append({
            "label": f"{m}月",
            "revenue": inc,
            "expenses": exp,
            "net": inc - exp,
        })
    return result
