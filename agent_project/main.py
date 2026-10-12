import os
import time

from agent.react_agent import ReactAgent
from db.mysql_store import insert_chat_message, list_chat_sessions, load_chat_history
from utils.config_handler import load_rag_config
from utils.logger_handler import logger
from utils.path_tool import get_abs_path
from utils.stream_tool import stream_to_placeholder
from utils.session_tool import (
    build_session_title,
    format_datetime,
    group_sessions_by_time,
    new_session_id,
    normalize_role,
)
import streamlit as st

st.set_page_config(page_title="智能扫地机器人客服")
st.title("智能扫地机器人客服")
st.divider()

GREETING = "你好，我是智能扫地机器人客服，请问有什么可以帮您？"

# 流式显示开关：
# True  = 真流式：模型吐一片界面就更新一次（实测约每秒 10 次，首字约 0.8 秒就能看到）
# False = 等模型整段写完再一次性渲染（界面只更新一次，最稳；前端要是再出问题先关它）
ENABLE_STREAMING = True
# 两次界面更新的最小间隔（秒）：分片密的时候没必要每片都重绘，节流一下更稳
STREAM_MIN_INTERVAL = 0.05


def start_new_session():
    """新建会话：换一个session_id，清空当前消息（消息落库后才会出现在历史列表里）"""
    st.session_state["session_id"] = new_session_id()
    st.session_state["messages"] = [{"role": "assistant", "content": GREETING}]


def switch_session(session_id: str):
    """切换到历史会话：把该会话在数据库里的全部消息读出来"""
    st.session_state["session_id"] = session_id
    st.session_state["messages"] = [
        {"role": normalize_role(row["role"]), "content": row["content"]}
        for row in load_chat_history(session_id)
    ]




AGENT_SOURCE_FILES = (
    "agent/react_agent.py",
    "model/factory.py",
    "config/rag.yml",
    "config/agent.yml",
    "config/prompts.yml",
    "prompts/main_prompt.txt",
    "prompts/report_prompt.txt",
)


def agent_signature() -> str:
    """agent 的版本指纹：模型名 + 相关源文件/提示词的修改时间"""
    parts = [load_rag_config()["chat_model"]]
    for relative_path in AGENT_SOURCE_FILES:
        try:
            parts.append(f"{relative_path}:{os.path.getmtime(get_abs_path(relative_path)):.0f}")
        except OSError:
            parts.append(f"{relative_path}:缺失")
    return "|".join(parts)


live_model_name = load_rag_config()["chat_model"]
live_signature = agent_signature()
if st.session_state.get("agent_signature") != live_signature:
    st.session_state["agent"] = ReactAgent()
    st.session_state["agent_model"] = live_model_name
    st.session_state["agent_signature"] = live_signature

if "session_id" not in st.session_state:
    start_new_session()

# ========== 渲染历史记录 ==========
for message in st.session_state["messages"]:
    with st.chat_message(message["role"]):
        st.write(message["content"])

prompt = st.chat_input("请输入您的问题", submit_mode="disable")

if prompt:
    session_id = st.session_state["session_id"]
    # 本轮提问之前的消息，作为上下文一起传给模型，恢复的历史会话才能接着聊。
    history = [m for m in st.session_state["messages"] if not m.get("error")]

    # 用户消息：存历史 + 入库 + 上屏
    st.session_state["messages"].append({"role": "user", "content": prompt})
    save_ok = insert_chat_message(session_id, "user", prompt)
    with st.chat_message("user"):
        st.write(prompt)

    # 助手消息：流式输出 + 存历史 + 入库
    failed = False
    with st.chat_message("assistant"):
        with st.spinner("正在思考中，请稍等..."):
            placeholder = st.empty()
            stream_stats = {"pieces": 0, "first_at": None}
            started_at = time.monotonic()

            def counted_stream():
                """包一层：顺便统计分片数和首片延迟，日志里就能确认是不是真流式"""
                for piece in st.session_state["agent"].execute_stream(prompt, history):
                    stream_stats["pieces"] += 1
                    if stream_stats["first_at"] is None:
                        stream_stats["first_at"] = time.monotonic() - started_at
                    yield piece

            try:
                # 自己累积渲染
                response = stream_to_placeholder(
                    counted_stream(),
                    placeholder,
                    min_interval=STREAM_MIN_INTERVAL if ENABLE_STREAMING else None,
                )
                first_at = stream_stats["first_at"]
                logger.info(
                    f"[流式]模型={st.session_state.get('agent_model')} 分片数={stream_stats['pieces']} "
                    f"首片={'-' if first_at is None else f'{first_at:.2f}s'} "
                    f"总耗时={time.monotonic() - started_at:.2f}s"
                )
            except Exception as e:
                failed = True
                placeholder.empty()                     # 丢掉半截回答，只留报错
                response = f"抱歉，服务暂时不可用：{e}"
                st.write(response)

    if failed:
        # 报错只上屏：不入库，也不参与下一轮的上下文，
        st.session_state["messages"].append({"role": "assistant", "content": response, "error": True})
    elif response:
        # 关键改动：存完整 response，空响应不存
        st.session_state["messages"].append({"role": "assistant", "content": response})
        save_ok = insert_chat_message(session_id, "assistant", response) and save_ok

    if not save_ok:
        st.warning("这轮对话没能写入数据库，历史会话里可能看不到它。")

# ========== 侧边栏：长期历史会话列表 ==========
# 放在对话处理之后：新会话此时已经落库，这一次渲染就能在列表里看到，
# 不需要在流式输出刚结束时再 st.rerun() 整页重跑（那会拆掉正在收尾的流式 DOM，是前端 removeChild 报错的高危时机）
with st.sidebar:
    st.subheader("历史会话")
    st.button(
        "新建会话",
        icon=":material/add:",
        width="stretch",
        on_click=start_new_session,
    )

    sessions = list_chat_sessions()                       # 按最后更新时间倒序
    if not sessions:
        st.caption("还没有历史会话，聊一句就会自动保存")

    for group_name, group_sessions in group_sessions_by_time(sessions):
        st.caption(group_name)
        for session in group_sessions:
            session_id = session["session_id"]
            st.button(
                build_session_title(session.get("first_user_message")),
                key=f"history_{session_id}",
                type="primary" if session_id == st.session_state["session_id"] else "secondary",
                width="stretch",
                help=f"{session['message_count']} 条消息 · 最后更新 {format_datetime(session['last_time'])}",
                on_click=switch_session,
                args=(session_id,),
            )

    st.divider()
    st.caption(f"当前模型 · {st.session_state.get('agent_model', live_model_name)}")
