# utils/session_tool.py
"""长期历史会话相关的通用工具：会话ID生成、标题截取、角色统一、按时间分组"""
import uuid
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

# 侧边栏展示的标题最大长度
TITLE_MAX_LEN = 24

# 会话列表的时间分组名
GROUP_TODAY = "今天"
GROUP_RECENT = "近 7 天"
GROUP_EARLIER = "更早"


def new_session_id() -> str:
    """生成一个新的会话唯一ID（32位十六进制，适配表里 session_id varchar(128)）"""
    return uuid.uuid4().hex


def normalize_role(role: Optional[str]) -> str:
    """
    统一数据库里的角色写法
    表注释写的是 human / assistant，Streamlit 渲染和 agent 上下文都用 user / assistant
    """
    value = str(role or "").strip().lower()
    return "user" if value in ("user", "human") else "assistant"


def build_session_title(content: Optional[str], max_len: int = TITLE_MAX_LEN) -> str:
    """用会话的第一条用户提问生成侧边栏标题：去掉换行、压缩空白、超长截断"""
    title = " ".join(str(content or "").split())
    if not title:
        return "新会话"
    if len(title) <= max_len:
        return title
    return title[:max_len] + "…"


def format_datetime(value: Any) -> str:
    """把数据库里的时间格式化成界面展示用的文本"""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M")
    return "未知时间"


def _to_date(value: Any) -> Optional[date]:
    """把 datetime / date 统一转成 date，取不到返回 None"""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return None


def group_sessions_by_time(
    sessions: Optional[List[Dict[str, Any]]],
    now: Optional[datetime] = None,
) -> List[Tuple[str, List[Dict[str, Any]]]]:
    """
    按会话的最后更新时间分组
    :param sessions: list_chat_sessions() 的返回值，需要带 last_time 字段
    :param now: 当前时间，默认取系统当前时间（便于测试）
    :return: [("今天", [会话...]), ("近 7 天", [...]), ("更早", [...])]，空分组不返回
    """
    now = now or datetime.now()
    today = now.date()

    buckets: Dict[str, List[Dict[str, Any]]] = {
        GROUP_TODAY: [],
        GROUP_RECENT: [],
        GROUP_EARLIER: [],
    }

    for session in sessions or []:
        last_date = _to_date(session.get("last_time"))
        if last_date is None:
            buckets[GROUP_EARLIER].append(session)
            continue

        days = (today - last_date).days
        if days <= 0:                      # 今天（含时间异常偏后的情况）
            buckets[GROUP_TODAY].append(session)
        elif days < 7:                     # 最近 7 天内
            buckets[GROUP_RECENT].append(session)
        else:
            buckets[GROUP_EARLIER].append(session)

    return [(name, items) for name, items in buckets.items() if items]
