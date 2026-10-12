# utils/stream_tool.py
"""流式渲染工具：把模型分片稳定地画到 Streamlit 占位元素上"""
import time

# 两次界面更新的最小间隔（秒），默认值；调用方可以覆盖，传 None 表示只在最后渲染一次
DEFAULT_MIN_INTERVAL = 0.05


def stream_to_placeholder(stream, placeholder, min_interval=DEFAULT_MIN_INTERVAL):
    """
    边收边渲染：自己累积文本，用普通的 st.markdown 重绘同一个占位元素

    为什么不用 st.write_stream：
    它内部走的是 _markdown(unterminated_parsing=True)（见 streamlit issue #14524 对内部实现的说明），
    前端会调用 remend 包自动补齐还没写完的 markdown 语法（**、`、``` 等）来"美化"流式观感
    （streamlit PR #13939）。补齐会让解析出的 HTML 结构在流式过程中反复变形，
    React 丢掉节点引用后浏览器就抛 "Failed to execute 'removeChild' on 'Node'"
    —— 也就是聊天页面上那个红框里的 react-dom 报错。
    普通 st.markdown 不带补齐逻辑（unterminatedParsing 未设置时前端跳过处理），绕开这条路径。

    为什么要节流：每次重绘前端都要重新解析整段 markdown，更新越密越容易踩到那条竞态。
    实测模型自然分片约每秒 10 次，按 min_interval 节流后既够顺滑，又离高频重绘很远。

    :param stream: 产出文本分片的生成器
    :param placeholder: st.empty() 得到的占位元素（只要有 markdown(str) 方法即可，便于单测）
    :param min_interval: 两次重绘的最小间隔（秒）；传 None 表示中间不重绘，只在最后渲染一次
    :return: 累积出来的完整文本
    """
    buffer = ""
    last_draw = 0.0
    for piece in stream:
        if not piece:
            continue
        buffer += piece
        if min_interval is None:
            continue
        now = time.monotonic()
        if now - last_draw >= min_interval:
            placeholder.markdown(buffer)
            last_draw = now
    if buffer:
        placeholder.markdown(buffer)        # 收尾补一次，保证显示的是完整文本
    return buffer
