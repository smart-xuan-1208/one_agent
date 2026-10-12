import sys
import os

# ========== 模块路径处理 ==========
# 获取当前文件的绝对路径
cur_file = os.path.abspath(__file__)
rag_folder = os.path.dirname(cur_file)
project_root = os.path.dirname(rag_folder)
if project_root not in sys.path:
    sys.path.insert(0, project_root)


from langchain.agents import create_agent
from model.factory import get_chat_model
from utils.config_handler import agent_conf, load_rag_config
from utils.logger_handler import logger
from utils.prompt_loader import load_system_prompts
from agent.tools.agent_tools import (rag_summarize, get_weather, fetch_external_data, fill_report_context)
from agent.tools.middleware import monitor_tool, log_before_model, report_prompt_switch
from langchain_core.messages import HumanMessage, AIMessage, AIMessageChunk


# create_agent 内部主模型节点在图里的名字，流式过滤只认这个节点的输出
MODEL_NODE = "model"

# 恢复历史会话时，最多把最近多少条历史消息作为上下文传给模型，可在 config/agent.yml 里调整
MAX_HISTORY_MESSAGES = int(agent_conf.get("max_history_messages", 20))

# 数据库 role 字段的取值，兼容早期写的 human / ai
_USER_ROLES = ("user", "human")
_ASSISTANT_ROLES = ("assistant", "ai")


def build_history_messages(history):
    """
    把数据库里读出来的历史消息转成LangChain消息对象
    :param history: [{"role": "user"/"assistant", "content": "..."}, ...]，可以为None
    :return: [HumanMessage | AIMessage, ...]，只保留最近 MAX_HISTORY_MESSAGES 条
    """
    if not history:
        return []

    messages = []
    for item in history:
        if not isinstance(item, dict):
            continue

        role = str(item.get("role", "")).strip().lower()
        content = str(item.get("content", "")).strip()
        if not content:
            continue

        if role in _USER_ROLES:
            messages.append(HumanMessage(content=content))
        elif role in _ASSISTANT_ROLES:
            messages.append(AIMessage(content=content))

    # 只保留最近若干条，避免会话越聊越长把上下文撑爆
    if MAX_HISTORY_MESSAGES > 0:
        messages = messages[-MAX_HISTORY_MESSAGES:]

    # 截断后开头可能是AI消息，去掉它，保证历史从用户提问开始
    while messages and isinstance(messages[0], AIMessage):
        messages.pop(0)

    return messages


class ReactAgent:
    """
    ReAct智能Agent主类
    封装agent实例，提供流式对话执行入口
    """
    def __init__(self):
        """
        构造函数：实例化的时候自动执行
        创建agent对象，配置模型、系统提示词、工具列表、中间件
        """
        # 每次创建agent都实时读一遍配置里的模型名，并把名字写进日志：
        # 以后接口报错时，翻日志就能确认"到底用的哪个模型"，不用再猜
        self.model_name = load_rag_config()["chat_model"]
        logger.info(f"[ReactAgent]使用聊天模型：{self.model_name}")

        self.agent = create_agent(
            model=get_chat_model(self.model_name),              # 使用的大模型实例
            system_prompt=load_system_prompts(),               # 系统角色提示词
            tools=[                                            # agent可以调用的全部工具
                rag_summarize,        # RAG知识库检索总结
                get_weather,          # 获取城市天气
                fetch_external_data,  # 读取扫地机器人csv外部使用记录
                fill_report_context   # 切换报告生成模式
            ],
            middleware=[                                       # 中间件
                monitor_tool,         # 工具调用监控：打印工具名称、参数、执行结果日志
                log_before_model,     # 模型调用前日志：打印消息数量与最后一条消息
                report_prompt_switch  # 动态提示词切换：普通对话 / 报告模式切换prompt
            ],
        )

    def execute_stream(self, query: str, history=None):
        """
        执行agent对话，生成器，流式返回AI最终回答
        :param query: 用户输入的提问字符串
        :param history: 该会话之前的消息（[{"role","content"}]），用于恢复长期历史会话的上下文
        :yield: 产出AI最终回答的文本分片（模型吐一片就产出一片）
        """
        # 组装agent输入状态：历史消息 + 本轮用户提问
        input_dict = {
            "messages": build_history_messages(history) + [HumanMessage(content=query)]
        }

        # stream_mode="messages"：模型边生成边产出分片（配合 model/factory.py 里的 streaming=True），
        # 界面才能真流式显示；旧的 "values" 模式要等整段生成完才拿到，只能靠假打字机演
        # context 运行时上下文，可以在中间件之间共享数据
        for chunk, metadata in self.agent.stream(input_dict, stream_mode="messages", context={"report": False}):
            # 只要主模型节点产出的正文：
            # 过滤工具节点（ToolMessage）、工具调用参数分片（tool_call_chunks）和空分片
            if metadata.get("langgraph_node") != MODEL_NODE:
                continue
            if not isinstance(chunk, AIMessageChunk):
                continue
            if getattr(chunk, "tool_call_chunks", None):
                continue
            if isinstance(chunk.content, str) and chunk.content:
                yield chunk.content


if __name__ == '__main__':
    agent = ReactAgent()
    for a in agent.execute_stream("扫地机器人在当前福建三明的气温下如何保养"):
        print(a, end="", flush=True)
