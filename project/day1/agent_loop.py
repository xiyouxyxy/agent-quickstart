import os
import json
import httpx
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("API_KEY") or os.getenv("API_1")
BASE_URL = os.getenv("BASE_URL")
MODEL_NAME = os.getenv("MODEL_NAME")


if not API_KEY:
    raise SystemExit(
        "未读到 API_KEY，请检查 .env（API_KEY / API_1 / api_key 任一即可）"
    )


def get_weather(city: str) -> dict:
    """
    获取天气信息
    :param city: 城市名称
    :return: 天气信息字典
    """
    return {"city": city, "weather": "晴朗", "temp": "26℃"}


def calculate(expression: str) -> dict:
    """
    计算数学表达式
    :param expression: 数学表达式
    :return: 计算结果字典
    """
    return {"result": eval(expression)}


DISPATCH = {"get_weather": get_weather, "calculate": calculate}

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "获取天气信息",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "城市名称，如北京"}
                },
                "required": ["city"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate",
            "description": "计算数学表达式",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "数学表达式，如 2+3*4",
                    }
                },
                "required": ["expression"],
            },
        },
    },
]


def call_llm(messages: list) -> dict:
    """把 messages + tools 发给模型，返回 assistant message（可能含 tool_calls）"""
    resp = httpx.post(
        f"{BASE_URL}/chat/completions",
        headers={"Authorization": f"Bearer {API_KEY}"},
        json={
            "model": MODEL_NAME,
            "messages": messages,
            "tools": TOOLS,
        },
        timeout=60,
    )
    resp.raise_for_status()
    print(resp.json(), "resp.json")
    return resp.json()["choices"][0]["message"]


def run_agent_loop(user_input: str, max_steps: int = 6) -> str:
    messages = [
        {"role": "system", "content": "你是一个助手，需要数据时调用工具，不要编造"},
        {"role": "user", "content": user_input},
    ]

    for step in range(max_steps):
        msg = call_llm(messages)
        if msg.get("tool_calls"):
            messages.append(
                {
                    "role": "assistant",
                    "content": msg.get("content") or "",
                    "tool_calls": msg["tool_calls"],
                }
            )
            for tc in msg["tool_calls"]:
                fn = tc["function"]["name"]
                args = json.loads(tc["function"]["arguments"])
                print(f"[step {step}] 调用工具 {fn}({args})")
                result = DISPATCH[fn](**args)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": json.dumps(result, ensure_ascii=False),
                    }
                )
        else:
            return msg["content"]
    return "达到最大步数，强制终止"


if __name__ == "__main__":
    question = "北京今天多少度？温度乘以2再加10是多少？"
    print(f"[user] {question}")
    print(f"[agent] {run_agent_loop(question)}")
