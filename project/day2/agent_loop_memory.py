import os
import json
import httpx
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("API_KEY") or os.getenv("API_1") or os.getenv("api_key")
BASE_URL = os.getenv("BASE_URL") or os.getenv("base_url")
MODEL_NAME = os.getenv("MODEL_NAME") or os.getenv("model_name")

if not API_KEY:
    raise SystemExit(
        "未读到 API_KEY，请检查 .env（API_KEY / API_1 / api_key 任一即可）"
    )


# ---------- 1. 工具：真实执行逻辑（在应用侧，模型碰不到） ----------
def get_weather(city: str) -> dict:
    """查询指定城市当前天气（这里用假数据演示）"""
    return {"city": city, "weather": "晴", "temp": "26℃"}


# dict 字典 储存键值对


def calculate(expression: str) -> dict:
    """计算一个数学表达式的值
    ⚠️ 仅演示用：eval 有安全风险，生产环境千万别这么写（正好是面试可讲的"护栏"点）。"""
    return {"result": eval(expression)}


DISPATCH = {"get_weather": get_weather, "calculate": calculate}

# ---------- 2. 函数 schema：告诉模型"有哪些工具、怎么调" ----------
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "查询指定城市当前天气",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "城市名，如 北京"}
                },
                "required": ["city"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate",
            "description": "计算一个数学表达式的值",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {"type": "string", "description": "如 3.5*12+7"}
                },
                "required": ["expression"],
            },
        },
    },
]


def chat(messages: list) -> dict:
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
    return resp.json()["choices"][0]["message"]


MEMORY_FILE = os.path.join(os.path.dirname(__file__), "memory.json")


def load_memory() -> list:
    """从本地文件加载历史对话"""
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return [
        {"role": "system", "content": "你是一个助手，需要数据时调用工具，不要编造。"}
    ]


def save_memory(messages: list):
    """保存历史对话到本地文件"""
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(
            messages, f, ensure_ascii=False, indent=2
        )  # dump()写入文件，ensure_ascii=False表示直接写入中文而不是ASCII码，f表示文件对象，indent=2表示缩进2个空格


def run_agent(user_input, messages, max_step=6):
    messages.append({"role": "user", "content": user_input})
    for step in range(max_step):
        msg = chat(messages)
        if msg.get("tool_calls"):
            messages.append(msg)  # 先把模型的回答存下来
            for tc in msg["tool_calls"]:
                fn = tc["function"]["name"]
                args = json.loads(tc["function"]["arguments"])
                result = DISPATCH[fn](**args)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc["id"],  # ★ 必须与上面 assistant 消息的 tool_calls 配对，漏了 API 会报错
                        "name": fn,
                        "content": json.dumps(result, ensure_ascii=False),
                    }
                )
        else:
            messages.append(msg)  # ★ 易漏！day1 没存最终回复，现在必须存
            save_memory(messages)  # ★ 结束写回
            return msg["content"]
    save_memory(messages)  # 强制终止也要存
    return "达到最大步数，强制终止"


if __name__ == "__main__":
    messages = load_memory()  # 启动加载历史
    while True:
        user_input = input("你: ").strip()
        if user_input == "/reset":  # 验收点 4
            save_memory(
                [
                    {
                        "role": "system",
                        "content": "你是一个助手，需要数据时调用工具，不要编造。",
                    }
                ]
            )
            messages = load_memory()
            print("记忆已清空")
            continue
        if user_input == "/quit":
            save_memory(messages)
            break
        reply = run_agent(user_input, messages)
        print("Agent:", reply)
