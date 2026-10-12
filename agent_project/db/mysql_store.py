# db/mysql_store.py
import pymysql
from pymysql.cursors import DictCursor
from dotenv import load_dotenv
import os

# 加载.env配置
load_dotenv()

def get_mysql_conn():
    """获取mysql数据库连接"""
    conn = pymysql.connect(
        host=os.getenv("MYSQL_HOST"),
        port=int(os.getenv("MYSQL_PORT")),
        user=os.getenv("MYSQL_USER"),
        password=os.getenv("MYSQL_PASSWORD"),
        database=os.getenv("MYSQL_DB"),
        charset=os.getenv("MYSQL_CHARSET")
    )
    return conn


def insert_chat_message(session_id: str, role: str, content: str) -> bool:
    """
    插入一条聊天消息入库
    :param session_id: 会话唯一id
    :param role: user / assistant
    :param content: 消息文本
    :return: 是否写入成功
    """
    conn = get_mysql_conn()
    try:
        with conn.cursor() as cur:
            sql = """
            INSERT INTO agent_chat_history (session_id, role, content)
            VALUES (%s, %s, %s)
            """
            cur.execute(sql, (session_id, role, content))
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        print(f"插入消息异常：{e}")
        return False
    finally:
        conn.close()


def load_chat_history(session_id: str):
    """
    读取某个会话的全部历史消息，按时间升序
    这里用 created_at + id 双字段排序：同一秒内写入的问答，只按 created_at 排会出现顺序错乱
    :return: [{"role", "content"}, ...]，没读到返回空列表
    """
    conn = get_mysql_conn()
    try:
        with conn.cursor(DictCursor) as cur:
            sql = """
            SELECT role, content FROM agent_chat_history
            WHERE session_id = %s ORDER BY created_at ASC, id ASC
            """
            cur.execute(sql, (session_id,))
            # fetchall() 返回的是元组，统一转成列表，和异常分支的返回值保持一致
            rows = list(cur.fetchall())
        return rows
    except Exception as e:
        print(f"读取会话历史异常：{e}")
        return []
    finally:
        conn.close()


def list_chat_sessions():
    """
    查询全部历史会话，按最后更新时间倒序
    :return: [{"session_id", "first_user_message", "first_time", "last_time", "message_count"}]
             first_user_message 是该会话第一条用户提问，交给界面截断成标题；没有用户提问时为 None
    """
    conn = get_mysql_conn()
    try:
        with conn.cursor(DictCursor) as cur:
            # 每个会话的时间范围与消息条数
            cur.execute("""
                SELECT session_id,
                       MIN(created_at) AS first_time,
                       MAX(created_at) AS last_time,
                       COUNT(*)        AS message_count
                FROM agent_chat_history
                GROUP BY session_id
                ORDER BY last_time DESC
            """)
            sessions = list(cur.fetchall())

            # 每个会话的第一条用户提问（role 兼容表注释里的 human 写法）
            cur.execute("""
                SELECT h.session_id, h.content
                FROM agent_chat_history h
                JOIN (
                    SELECT session_id, MIN(id) AS first_user_msg_id
                    FROM agent_chat_history
                    WHERE role IN ('user', 'human')
                    GROUP BY session_id
                ) t ON h.id = t.first_user_msg_id
            """)
            first_messages = {row["session_id"]: row["content"] for row in cur.fetchall()}

        for session in sessions:
            session["first_user_message"] = first_messages.get(session["session_id"])
        return sessions
    except Exception as e:
        print(f"查询会话列表异常：{e}")
        return []
    finally:
        conn.close()

def delete_single_message(msg_id: int):
    """按id删除单条消息"""
    conn = get_mysql_conn()
    try:
        with conn.cursor() as cur:
            sql = "DELETE FROM agent_chat_history WHERE id = %s"
            cur.execute(sql, (msg_id,))
        conn.commit()
        print(f"已删除id={msg_id}的消息")
    except Exception as e:
        conn.rollback()
        print(f"删除单条消息异常:{e}")
    finally:
        conn.close()


if __name__ == "__main__":
    # 测试
    delete_single_message(58)
