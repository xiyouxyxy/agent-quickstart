"""
Day3 ⭐产出: 用 LangChain 重写 Day1 的 agent_loop
对照 Day1: 同样的天气+计算器双工具 + 同样的连续两步调用验收题
"""

import os
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
from langchain.agents import create_agent

load_dotenv()

API_KEY = os.getenv("API_KEY") or os.getenv("API_1")
BASE_URL = os.getenv("BASE_URL")
MODEL_NAME = os.getenv("MODEL_NAME")


if not API_KEY:
    raise SystemExit(
        "未读到 API_KEY，请检查 .env（API_KEY / API_1 / api_key 任一即可）"
    )

llm = ChatOpenAI(
    model_name=MODEL_NAME, api_key=API_KEY, base_url=BASE_URL, temperature=0
)


def get_weather(city: str) -> str:
    """获取天气
    :param city: 城市名
    :return: 天气信息
    """
    return f"{city}的天气是：晴天，温度25℃"


def calculator(expression: str) -> str:
    """计算器
    :param expression: 表达式
    :return: 计算结果
    """
    return str(eval(expression))


agent = create_agent(
    model=llm,
    tools=[get_weather, calculator],
    system_prompt="你是一个智能助理，可以调用天气和计算器工具来回答用户的问题，需要数据时调用工具，不要编造。",
)

result = agent.invoke(
    {
        "messages": [
            {"role": "user", "content": "北京今天多少度？温度乘以2再加10是多少？"},
            {"role": "user", "content": "请帮我算一下 1+2*3"},
        ]
    }
)

print(result["messages"][-1].text)
