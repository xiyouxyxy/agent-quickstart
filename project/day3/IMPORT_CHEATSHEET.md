# LangChain import 速查表（工作中直接抄）

> 原则：不记 import，记分工。日常 90% 的 Agent 代码只需要下面 2 行。

---

## ⭐Day3 ⭐产出只需要 2 行 import

```python
from langchain_openai import ChatOpenAI      # model: 调 LLM
from langchain.agents import create_agent    # agent: 一行创建 Agent
```

就这两行。其它都不用 import——
- 工具函数（get_weather/calculate）就是普通 Python 函数，直接传给 `create_agent(tools=[...])`
- 不需要 `@tool`、不需要手写 schema、不需要 DISPATCH

---

## 完整可抄模板（你下午直接照着改）

```python
import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent

load_dotenv()
llm = ChatOpenAI(
    model=os.getenv("MODEL_NAME"),
    api_key=os.getenv("API_KEY") or os.getenv("API_1"),
    base_url=os.getenv("BASE_URL"),
    temperature=0,
)

def get_weather(city: str) -> str:
    """Get current weather for a given city."""   # docstring = schema
    return f"{city} 今天晴，26℃"

def calculate(expression: str) -> str:
    """Calculate a math expression and return the result."""
    return str(eval(expression))

agent = create_agent(
    model=llm,
    tools=[get_weather, calculate],
    system_prompt="你是一个助手，需要数据时调用工具，不要编造。",
)

result = agent.invoke(
    {"messages": [{"role": "user", "content": "北京今天多少度？温度乘以2再加10是多少？"}]}
)
print(result["messages"][-1].text)
```

---

## 进阶（学到 Day4 LangGraph / RAG 才需要）

| 想做什么 | import 哪行 |
|---|---|
| 自定义消息模板 | `from langchain_core.prompts import ChatPromptTemplate` |
| 解析输出为字符串 | `from langchain_core.output_parsers import StrOutputParser` |
| 手动控制工具 schema | `from langchain_core.tools import tool`（@tool 装饰器） |
| 内存检查点（多轮记忆） | `from langgraph.checkpoint.memory import InMemorySaver` |
| 流式输出 | `for chunk in agent.stream({...}): print(chunk)` |

---

## VS Code 自动 import 建议（开起来，永远不记）

1. 装 Pylance 扩展（VS Code 默认已装）
2. 写完类名后悬停 → 点亮泡 → "Add import" 自动加
3. 或者 `Ctrl+Shift+P` → "Python: Restart Language Server" 触发全文件诊断
4. 设置：`"python.analysis.autoImport": true`（默认开）

效果：你只要打 `ChatOpenAI`，VS Code 自动在你文件顶部加 `from langchain_openai import ChatOpenAI`。**永远不用记 import 路径**。

---

## 面试怎么应对"包生态"问题

面试官**不会问**「`create_agent` 在哪个包」（这是机械记忆，没意义）。
**会问**：「LangChain 包生态怎么分？为什么这样分？」

标准答（你已知）：
> 拆三层——`langchain-core` 是底层抽象（tools/prompts/parsers/message 所有家共用），`langchain-openai` 等是各家模型集成（ChatOpenAI/ChatAnthropic），`langchain` 主包是高级 API（create_agent 等）。拆分的好处是换模型=只换一个集成包，业务代码不动。

---

## 最后：记不住 ≠ 不会

- Day1 你手写了 60 行 agent_loop，**原理你已经懂了**
- Day3 ⭐产出本质是把那 60 行压缩成 30 行（用 LangChain 的抽象替代手写）
- import 路径是机械记忆，**和工作能力无关**
- 你今晚能跑通 ⭐产出 = 你会用 LangChain 了，**就这么简单**

下午 14:00 块②开始，照着上面「完整可抄模板」改你自己的 `agent_loop_langchain.py`，20 分钟跑通。
