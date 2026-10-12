"""
总结服务，用户提问，搜索参考资料，将提问和参考资料提问给模型，模型总结
"""
import sys
import os

# 获取当前 rag_service.py 的上级（项目根目录 agent_project）
cur_file = os.path.abspath(__file__)
rag_folder = os.path.dirname(cur_file)
project_root = os.path.dirname(rag_folder)
if project_root not in sys.path:
    sys.path.insert(0, project_root)


from rag.vector_store import VectorStoreService
from utils.prompt_loader import load_rag_prompts
from langchain_core.prompts import PromptTemplate
from model.factory import chat_model
from langchain_core.output_parsers import StrOutputParser
from langchain_core.documents import Document

def get_prompt(prompt):
    print("="*20)
    print(prompt)
    print("="*20)
    return prompt


class RagSummarizeService(object):
    def __init__(self):
        self.vector_store = VectorStoreService()   #向量存储
        self.retriever = self.vector_store.get_retriever()  #检索器
        self.prompt_text = load_rag_prompts()  #提示词
        self.prompt_template = PromptTemplate.from_template(self.prompt_text) #提示词模板
        self.model = chat_model
        self.chain = self._init_chain()

    def _init_chain(self):
        chain = self.prompt_template | self.model | StrOutputParser()
        return chain

    def retriever_docs(self, query: str) -> list[Document]:
        return self.retriever.invoke(query)

    def rag_summarize(self, query: str) -> str:

        context_docs = self.retriever_docs(query)

        context = ""
        counter = 0
        for a in context_docs:
            counter += 1
            context += f"【参考资料{counter}】: {a.page_content} | 参考元数据: {a.metadata}\n"

        return self.chain.invoke(
            {
                "input": query,
                "context": context,
            }
        )


if __name__ == '__main__':
    rag = RagSummarizeService()

    print(rag.rag_summarize("小户型适合哪种扫地机器人"))