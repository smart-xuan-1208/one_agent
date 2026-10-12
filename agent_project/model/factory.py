from abc import ABC, abstractmethod
from typing import Optional
from langchain_community.embeddings import DashScopeEmbeddings
from langchain_community.chat_models.tongyi import ChatTongyi
from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel
from utils.config_handler import rag_conf, load_rag_config


class BaseModelFactory(ABC):
    @abstractmethod
    def generate(self) -> Optional[Embeddings | BaseChatModel]:
        """工厂方法：生成并返回模型实例"""
        pass


class ChatModelFactory(BaseModelFactory):
    """聊天模型工厂：生成通义千问聊天模型实例"""
    def generate(self) -> BaseChatModel:
        return ChatTongyi(model=rag_conf["chat_model"])


class EmbeddingsFactory(BaseModelFactory):
    """嵌入模型工厂：生成通义百炼嵌入模型实例"""
    def generate(self) -> Embeddings:
        return DashScopeEmbeddings(
            model=rag_conf["embedding_model"])


# 聊天模型按“模型名”缓存
_chat_model_cache: dict = {}


def get_chat_model(model_name: Optional[str] = None) -> BaseChatModel:
    """
    获取聊天模型，模型名变了就重新创建
    :param model_name: 指定模型名；不传则每次实时读取 config/rag.yml 里的 chat_model
    实时读取的意义：改完配置不用重启整个进程，下一次对话就用新模型。
    否则旧模型对象一直留在内存里，接口只返回"Model not exist"，根本看不出是配置没生效
    """
    name = model_name or load_rag_config()["chat_model"]
    if _chat_model_cache.get("name") != name:
        _chat_model_cache["name"] = name
        # streaming=True：ChatTongyi 默认是 False，那样模型会憋完整段再返回，
        # agent 侧就只能拿到一个大块，界面做不出真流式；开了之后是按分片返回的
        _chat_model_cache["model"] = ChatTongyi(model=name, streaming=True)
    return _chat_model_cache["model"]


# 对外暴露的模型实例（和你 vector_store 里的导入名保持一致）
chat_model = get_chat_model()
Embedding_model = EmbeddingsFactory().generate()
