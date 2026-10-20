"""
Day3 官方 quickstart（MiniMax 适配版）

官方原版: https://docs.langchain.com/oss/python/langchain/quickstart
官方用 model="openai:gpt-5.5" 字符串; MiniMax 兼容 OpenAI 协议,
所以用 langchain_openai.ChatOpenAI 显式传 base_url。

Demo 1 = LCEL 管道 (prompt | model | parser)  —— 四块概念里的 LCEL
Demo 2 = create_agent + tool                  —— 官方 quickstart 主推写法
"""
import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("API_KEY") or os.getenv("API_1")
BASE_URL = os.getenv("BASE_URL")
MODEL_NAME = os.getenv("MODEL_NAME")

# ---------- 公共: model ----------
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(
    model=MODEL_NAME,
    api_key=API_KEY,
    base_url=BASE_URL,
    temperature=0,
)

# ---------- Demo 1: LCEL 管道 prompt | model | parser ----------
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

prompt = ChatPromptTemplate.from_messages([
    ("system", "你是一个简洁的助手，用一句话回答。"),
    ("user", "{question}"),
])

chain = prompt | llm | StrOutputParser()   # <- LCEL: 管道组合

print("=== Demo 1: LCEL 管道 ===")
print(chain.invoke({"question": "用一句话说明什么是 Agent"}))

# ---------- Demo 2: create_agent + tool（官方 quickstart 主推） ----------
from langchain.agents import create_agent

def get_weather(city: str) -> str:
    """Get weather for a given city."""
    return f"{city} 今天晴，26℃"

agent = create_agent(
    model=llm,
    tools=[get_weather],
    system_prompt="你是一个助手，需要数据时调用工具，不要编造",
)

print("\n=== Demo 2: create_agent ===")
result = agent.invoke(
    {"messages": [{"role": "user", "content": "北京今天天气怎么样？"}]}
)
print(result["messages"][-1].text)
