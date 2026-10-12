# 智能扫地机器人客服 Agent

基于 **Streamlit + LangChain/LangGraph + RAG** 的扫地机器人客服问答应用。用户用自然语言提问，Agent 自行判断该查知识库、查天气还是调外部记录，然后流式输出回答。

## 功能

- **多轮对话 + 真流式输出** —— 模型吐一片界面更新一片，首字约 0.8 秒可见，不用等整段生成完
- **RAG 知识库问答** —— 扫地机器人的选购指南、故障排除、维护保养、常见问答等资料切分后向量化入库，提问时检索召回再交给模型总结
- **ReAct 工具调用**，目前接了 4 个工具：
  | 工具 | 作用 |
  | --- | --- |
  | `rag_summarize` | 向量库检索并总结 |
  | `get_weather` | 查指定城市天气（wttr.in，免注册） |
  | `fetch_external_data` | 查指定用户在指定月份的使用记录（本地 CSV） |
  | `fill_report_context` | 触发中间件切到「报告生成」提示词 |
- **会话持久化** —— 消息存 MySQL；支持新建会话、历史会话列表（按时间分组、用首条提问作标题）、切换会话后恢复上下文
- **知识库增量加载** —— 按文件 MD5 去重，已入库的文件不会重复灌入
- **中间件** —— 工具调用日志、模型调用前日志、按场景动态切换系统提示词

## 技术栈

```
Streamlit              界面与流式渲染
LangChain / LangGraph  Agent、工具、中间件、提示词链
通义千问（DashScope）    聊天模型 + 文本嵌入模型
Chroma                 本地向量库
MySQL                  会话与消息持久化
```

## 快速开始

### 1. 环境准备

```bash
git clone https://github.com/<你的用户名>/<仓库名>.git
cd <仓库名>
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. 建数据库表

在 MySQL 里建库建表（用户名密码和库名自己定）：

```sql
CREATE TABLE agent_chat_history (
  id         BIGINT AUTO_INCREMENT PRIMARY KEY,
  session_id VARCHAR(64)  NOT NULL,
  role       VARCHAR(16)  NOT NULL COMMENT 'user / assistant',
  content    TEXT         NOT NULL,
  created_at DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_session (session_id),
  INDEX idx_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### 3. 配置环境变量

```bash
cp .env.example .env
```

填好自己的 MySQL 连接信息和 DashScope API Key：

| 变量 | 说明 |
| --- | --- |
| `MYSQL_HOST` / `MYSQL_PORT` / `MYSQL_USER` / `MYSQL_PASSWORD` / `MYSQL_DB` / `MYSQL_CHARSET` | MySQL 连接信息 |
| `DASHSCOPE_API_KEY` | 通义千问 API Key，[在这里申请](https://bailian.console.aliyun.com/) |

> `.env` 已在 `.gitignore` 里，不会被提交。

### 4. 建知识库（首次运行必须先做这一步）

`data/` 目录下的 txt 资料需要先切分、向量化入库：

```bash
python -m rag.vector_store
```

跑完后会生成 `chroma_db/` 目录和记录已处理文件 MD5 的 `md5.txt`。这两个都在 `.gitignore` 里，换台机器重新跑一次即可。

### 5. 启动

```bash
streamlit run main.py
```

浏览器打开终端里提示的地址（默认 http://localhost:8501）。

## 项目结构

```
agent_project/
├── main.py                    # Streamlit 入口：会话状态、流式渲染、侧边栏历史
├── agent/
│   ├── react_agent.py         # ReAct Agent：建图、流式过滤、历史消息转换
│   └── tools/
│       ├── agent_tools.py     # 4 个工具的实现
│       └── middleware.py      # 工具日志 / 模型前日志 / 动态提示词
├── rag/
│   ├── rag_service.py         # 检索 + 提示词 + 模型的总结链
│   └── vector_store.py        # Chroma 建库、切分、MD5 去重增量加载
├── model/factory.py           # 聊天模型 / 嵌入模型工厂，带模型名缓存
├── db/mysql_store.py          # 消息入库、会话历史查询、会话列表
├── utils/
│   ├── config_handler.py      # 读取 config/*.yml
│   ├── prompt_loader.py       # 读取 prompts/*.txt
│   ├── stream_tool.py         # 流式渲染 + 节流（见下方说明）
│   ├── session_tool.py        # session_id、标题截断、按时间分组
│   ├── file_hander.py         # txt/PDF 加载、目录过滤、文件 MD5
│   ├── logger_handler.py      # 日志
│   └── path_tool.py           # 相对路径转绝对路径
├── config/                    # rag / chroma / agent / prompts 配置
├── prompts/                   # 系统提示词、RAG 提示词、报告提示词
└── data/                      # 知识库原始资料 + 外部使用记录 CSV
```

## 几个实现上的取舍

**为什么不用 `st.write_stream`**

Streamlit 的 `st.write_stream` 内部会走 `_markdown(unterminated_parsing=True)`，前端用 `remend` 包自动补齐还没写完的 Markdown 语法来「美化」流式观感。补齐会让解析出的 HTML 结构在流式过程中反复变形，React 丢掉节点引用后浏览器会抛 `Failed to execute 'removeChild' on 'Node'`。

所以这里用普通 `st.markdown` 自己累积重绘同一个占位元素（`utils/stream_tool.py`），并按 50ms 节流——实测模型自然分片约每秒 10 次，节流后既顺滑又离高频重绘很远。

**为什么前面要放一个 `fill_report_context` 空工具**

Agent 需要在「普通问答」和「生成报告」两种提示词之间切换。中间件 `@dynamic_prompt` 只能读到运行时上下文，所以用一个无入参的工具作为信号：模型调用它 → `monitor_tool` 把 `context["report"]` 置为 `True` → 下一轮提示词换成报告模板。

**为什么 agent 实例要带版本指纹**

Agent 对象挂在 `st.session_state` 上活整个浏览器会话，而 Streamlit 只重新导入改动过的模块、不会替换已存在的实例。改了代码或提示词后页面还在用旧 agent，表现就是「流式没了」或「配置不生效」。所以 `main.py` 里用「模型名 + 相关源文件 mtime」算一个指纹，指纹变了就重建 agent。

## 已知限制

- **依赖版本未锁定**：`requirements.txt` 里的版本是按下限写的，没有在干净环境里完整验证过。如果你在别的机器上装出问题，欢迎提 issue 或者 PR 一份实测的 `pip freeze` 结果。
- 知识库资料（`data/*.txt`）是网上整理的扫地机器人常见问题，仅供学习演示，商用请自行确认来源授权。
- `data/external/records.csv` 是构造的示例数据，不对应真实用户。
- 天气走 wttr.in 免费接口，偶尔会超时。

## License

[MIT](LICENSE)
