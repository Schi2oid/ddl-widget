"""数据模型：DDL 条目、紧急度分级、倒计时文案。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

# 紧急度
URGENT_OVERDUE = "overdue"   # 已逾期
URGENT_TODAY = "today"       # 24 小时内 / 今天
URGENT_WEEK = "week"         # 7 天内
URGENT_LATER = "later"       # 7 天以上
URGENT_NONE = "none"         # 无截止时间

GROUP_ORDER = [URGENT_OVERDUE, URGENT_TODAY, URGENT_WEEK, URGENT_LATER, URGENT_NONE]

GROUP_LABEL = {
    "done": "已完成",
    URGENT_OVERDUE: "已逾期",
    URGENT_TODAY: "24 小时内",
    URGENT_WEEK: "7 天内",
    URGENT_LATER: "7 天以后",
    URGENT_NONE: "未定截止",
}

GROUP_COLOR = {
    "done": "#4ADE80",
    URGENT_OVERDUE: "#FF4D5E",
    URGENT_TODAY: "#FF6B78",
    URGENT_WEEK: "#FFB454",
    URGENT_LATER: "#5CACFF",
    URGENT_NONE: "#7C87A8",
}

INTERVAL_TODAY = timedelta(hours=24)
INTERVAL_WEEK = timedelta(days=7)

WEEKDAY_CN = ["一", "二", "三", "四", "五", "六", "日"]


def parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def fmt_iso(dt: datetime | None) -> str | None:
    return dt.replace(microsecond=0).isoformat(sep="T") if dt else None


@dataclass
class DDL:
    id: str
    title: str
    course_name: str = ""
    due_time: datetime | None = None
    source: str = "manual"          # pku3b | manual
    status: str = "pending"         # pending | completed
    ext_id: str = ""
    dedupe_key: str = ""
    status_locked: int = 0
    remote_completed: int = 0   # 上次同步时教学网上是否真的已提交
    user_edited: int = 0
    deleted: int = 0
    stale: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None
    completed_at: datetime | None = None
    notified_date: str = ""

    # ------------------------------------------------------------------
    @property
    def is_completed(self) -> bool:
        return self.status == "completed"

    def urgency(self, now: datetime | None = None) -> str:
        now = now or datetime.now()
        if self.due_time is None:
            return URGENT_NONE
        delta = self.due_time - now
        if delta < timedelta(0):
            return URGENT_OVERDUE
        if delta <= INTERVAL_TODAY:
            return URGENT_TODAY
        if delta <= INTERVAL_WEEK:
            return URGENT_WEEK
        return URGENT_LATER

    # ------------------------------------------------------------------
    def countdown(self, now: datetime | None = None) -> str:
        """倒计时文案，例如「剩 4 小时 20 分」。"""
        now = now or datetime.now()
        if self.due_time is None:
            return "无截止"
        delta = self.due_time - now
        total = int(delta.total_seconds())
        if total < 0:
            return "已逾期 " + _human_span(-total)
        if total == 0:
            return "即将截止"
        if total < 60:
            return "剩不到 1 分钟"
        return "剩 " + _human_span(total)

    def due_label(self, now: datetime | None = None) -> str:
        """截止时间文案，例如「今天 23:59」。"""
        if self.due_time is None:
            return ""
        now = now or datetime.now()
        due = self.due_time
        clock = due.strftime("%H:%M")
        days = (due.date() - now.date()).days
        if days == 0:
            return f"今天 {clock}"
        if days == 1:
            return f"明天 {clock}"
        if days == 2:
            return f"后天 {clock}"
        if days < 0:
            return f"{due.month}月{due.day}日 {clock}"
        if due.year == now.year:
            return f"{due.month}月{due.day}日 周{WEEKDAY_CN[due.weekday()]} {clock}"
        return f"{due.year}年{due.month}月{due.day}日 {clock}"

    def subtitle(self) -> str:
        if self.course_name.strip():
            return self.course_name.strip()
        return "手动添加" if self.source == "manual" else "教学网"


def _human_span(seconds: float) -> str:
    """把秒数转成「4 小时 20 分」这类中文表达。"""
    seconds = int(seconds)
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, _ = divmod(rem, 60)
    chunks: list[str] = []
    if days:
        chunks.append(f"{days} 天")
    if hours:
        chunks.append(f"{hours} 小时")
    if minutes or not chunks:
        if not days:
            chunks.append(f"{minutes} 分")
    return " ".join(chunks).strip() or "1 分钟"


def group_items(items: list[DDL], now: datetime | None = None) -> list[tuple[str, list[DDL]]]:
    """按紧急度分组，返回 [(urgency, items)]，空组不返回。"""
    now = now or datetime.now()
    buckets: dict[str, list[DDL]] = {key: [] for key in GROUP_ORDER}
    for item in items:
        buckets[item.urgency(now)].append(item)
    result: list[tuple[str, list[DDL]]] = []
    for key in GROUP_ORDER:
        rows = buckets[key]
        if not rows:
            continue
        rows.sort(key=lambda d: (d.due_time is None, d.due_time or datetime.max, d.title))
        result.append((key, rows))
    return result


def next_deadline(items: list[DDL], now: datetime | None = None) -> DDL | None:
    now = now or datetime.now()
    future = [i for i in items if i.due_time and i.due_time >= now]
    return min(future, key=lambda d: d.due_time) if future else None
