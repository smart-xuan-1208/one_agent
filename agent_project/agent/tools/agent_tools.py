
import sys
import os

cur_file = os.path.abspath(__file__)
rag_folder1 = os.path.dirname(cur_file)
rag_folder2 = os.path.dirname(rag_folder1)
project_root = os.path.dirname(rag_folder2)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from datetime import datetime
from langchain_core.tools import tool
from rag.rag_service import RagSummarizeService
import requests
from utils.config_handler import agent_conf
from utils.path_tool import get_abs_path
from utils.logger_handler import logger

rag = RagSummarizeService()
external_data = {}

#===============================================================================

from urllib.parse import quote   # 加到文件顶部 import 区

def get_weather_info(city: str) -> str:
    # wttr.in：免费、无需注册、直接支持中文城市名
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    }

    # quote() 对中文城市名做 URL 编码，避免请求路径出问题
    url = f"https://wttr.in/{quote(city)}?format=j1&lang=zh"

    try:
        resp = requests.get(url, headers=headers, timeout=10)

        if resp.status_code != 200:
            return f"天气查询失败，HTTP状态码：{resp.status_code}"

        data = resp.json()
        current = data["current_condition"][0]      # 当前天气
        temp = current["temp_C"]                     # 气温
        desc = current["weatherDesc"][0]["value"]    # 天气描述（中文）
        humidity = current["humidity"]               # 湿度（百分比数字）

        return f"{city} 当前天气：{desc}，气温：{temp}℃，湿度：{humidity}%"

    except requests.exceptions.RequestException as e:
        return f"天气接口网络异常：{str(e)}"
    except (KeyError, IndexError):
        return f"天气数据解析失败，城市：{city}"



#===============================================================================
def generate_external_data() -> str:
    if not external_data:
        external_data_path = get_abs_path(agent_conf["external_data_path"]) #取绝对路径

        if not os.path.exists(external_data_path):
            raise FileNotFoundError(f"[外部数据]目录{external_data_path}不存在")

        with open(external_data_path, "r", encoding="utf-8") as f:
            for line in f.readlines()[1:]:
                arr: list[str] = line.strip().split(",")
                user_id: str = arr[0].replace('"', "")
                feature: str = arr[1].replace('"', "")
                efficiency: str = arr[2].replace('"', "")
                consumables: str = arr[3].replace('"', "")
                comparison: str = arr[4].replace('"', "")
                time: str = arr[5].replace('"', "")
                if user_id not in external_data:
                    external_data[user_id] = {}

                external_data[user_id][time] = {
                    "特征": feature,
                    "效率": efficiency,
                    "耗材": consumables,
                    "对比": comparison,
                }



#===============================================================================
@tool(description="从向量存储中检索信息")
def rag_summarize(query: str) -> str:
    return rag.rag_summarize(query)

@tool(description="获取指定城市天气，以字符串形式返回")
def get_weather(city: str) -> str:
    return get_weather_info(city)

@tool(description="从外部系统中获取指定用户在指定月份的使用记录，以字符串形式返回，未检索到数据时返回空字符串")
def fetch_external_data(user_id: str, month: str) -> str:
    generate_external_data()

    try:
        return external_data[user_id][month]
    except KeyError:
        logger.error(f"[fetch_external_data]未找到用户{user_id}在{month}的记录")
        return ""

@tool(description="无入参，返回值，调用是触发中间件自动为报告生成的场景注入上下文信息，为后续提示词模板提供上下文信息")
def fill_report_context() :
    return "fill_report_context已调用"