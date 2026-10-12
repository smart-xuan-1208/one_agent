from langchain.agents import AgentState
from langchain.agents.middleware import wrap_tool_call
from langchain.tools.tool_node import ToolCallRequest
from typing import Callable
from langchain_core.messages import ToolMessage
from langgraph.types import Command
from utils.logger_handler import logger
from langgraph.runtime import Runtime
from langchain.agents.middleware import before_model, dynamic_prompt, ModelRequest
from utils.prompt_loader import load_report_prompts, load_system_prompts


@wrap_tool_call
def monitor_tool(
    request: ToolCallRequest,
    handler: Callable[[ToolCallRequest], ToolMessage | Command],
) -> ToolMessage | Command:
    # 安全取出工具名，取不到就显示unknown
    tool_name = request.tool_call.get("name", "unknown") if request.tool_call else "unknown"
    
    logger.info(f"[monitor_tool]执行工具: {tool_name}")
    logger.info(f"[monitor_tool]工具参数: {request.tool_call.get('args', {}) if request.tool_call else {}}")
    
    try:
        result = handler(request)
        # ToolMessage 对象用 .name 获取工具名，不是 .tool_call['name']
        logger.info(f"[monitor_tool]工具{result.name}调用成功")
        
        if tool_name == "fill_report_context":
            request.runtime.context["report"] = True
        return result
    
    except Exception as e:
        logger.error(f"工具{tool_name}调用失败: {str(e)}")
        raise e


@before_model
def log_before_model(
    state: AgentState,
    runtime: Runtime,
):
    messages = state.get("messages", [])
    msg_count = len(messages)
    logger.info(f"[log_before_model]即将调用模型，带有{msg_count}条消息")
    
    # 只有消息列表不为空，才打印最后一条详情
    if messages:
        last_msg = messages[-1]
        logger.debug(f"[log_before_model]{type(last_msg).__name__} | {last_msg.content.strip()}")
    
    return None


@dynamic_prompt
def report_prompt_switch(request: ModelRequest):
    is_report = request.runtime.context.get("report", False)
    if is_report:
        return load_report_prompts()
    return load_system_prompts()
