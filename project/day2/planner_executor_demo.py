# planner_executor_demo.py —— Planner-Executor 最小 demo（Day2 概念块素材）
# 与 day1 的 ReAct 循环对照：
#   ReAct        = 模型每轮动态决定下一步（走一步看一步）
#   Planner-Exec = 两阶段分离：先一次调用拿到完整计划，再按计划逐步执行
# 关键认知：Executor 的循环结构和 day1 的 agent_loop 一模一样——
#          P-E 不是替代 ReAct 循环，而是在循环外面套了一层"计划"。
import os, json, re, httpx
from dotenv import load_dotenv

load_dotenv()
API_KEY, BASE_URL, MODEL_NAME = os.getenv("API_KEY"), os.getenv("BASE_URL"), os.getenv("MODEL_NAME")


# ---- 工具定义（与 day1 完全相同，真实执行在应用侧）----
def get_weather(city: str):
    return {"city": city, "weather": "晴", "temp": "26℃"}


def calculate(expression: str):
    return {"result": eval(expression)}  # 仅演示用


TOOLS = [
    {"type": "function", "function": {
        "name": "get_weather",
        "description": "查询指定城市当前天气",
        "parameters": {"type": "object", "properties": {
            "city": {"type": "string", "description": "城市名，如 北京"}},
            "required": ["city"]}}},
    {"type": "function", "function": {
        "name": "calculate",
        "description": "计算一个数学表达式的值",
        "parameters": {"type": "object", "properties": {
            "expression": {"type": "string", "description": "如 3.5*12+7"}},
            "required": ["expression"]}}},
]
DISPATCH = {"get_weather": get_weather, "calculate": calculate}


def chat(messages, tools=None):
    body = {"model": MODEL_NAME, "messages": messages, "temperature": 0}
    if tools:
        body["tools"] = tools
    resp = httpx.post(
        f"{BASE_URL}/chat/completions",
        headers={"Authorization": f"Bearer {API_KEY}"},
        json=body,
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]


# ---- 阶段 1：Planner —— 只拆解，不执行 ----
def plan(user_input: str) -> list:
    messages = [
        {"role": "system", "content":
            "你是规划器。把任务拆解成有序步骤，只输出 JSON 字符串数组，"
            "不要执行任何步骤。示例：[\"查询北京天气\", \"把温度乘以2再加10\", \"汇总回答\"]"},
        {"role": "user", "content": user_input},
    ]
    # ★ 和 ReAct 的本质区别之一：规划阶段【不发 tools】——
    #   不给模型调工具的能力，强制它只能输出计划文本
    msg = chat(messages)
    content = msg["content"].strip()
    # 容错：剥掉模型可能包的 ```json ... ``` 围栏（生产级解析失败重试是 D8 工程化点）
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", content, re.S)
    if fence:
        content = fence.group(1)
    steps = json.loads(content)
    print("=== Planner 拆解的计划 ===")
    for i, s in enumerate(steps, 1):
        print(f"  {i}. {s}")
    return steps


# ---- 阶段 2：Executor —— 按计划逐步执行（这步可以调工具）----
def execute(steps: list, user_input: str) -> str:
    messages = [
        {"role": "system", "content":
            "你是执行器。严格按给定计划逐步完成，需要数据时调用工具，不要编造。"},
        {"role": "user", "content":
            f"原始任务：{user_input}\n计划步骤：{json.dumps(steps, ensure_ascii=False)}"},
    ]
    for step in range(8):  # ★ 这个循环和 day1 的 agent_loop 结构一模一样
        msg = chat(messages, tools=TOOLS)
        if msg.get("tool_calls"):
            messages.append(msg)  # 第1条：assistant + tool_calls
            for tc in msg["tool_calls"]:
                fn = tc["function"]["name"]
                args = json.loads(tc["function"]["arguments"])
                print(f"[执行 step {step}] 调用工具 {fn}({args})")
                result = DISPATCH[fn](**args)
                # 第2条：role:"tool" + 执行结果（tool_call_id 配对，和 day1 相同）
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": json.dumps(result, ensure_ascii=False),
                })
        else:
            return msg["content"]
    return "达到最大步数，强制终止"


if __name__ == "__main__":
    task = "北京今天多少度？温度乘以2再加10是多少？"
    print("=== 阶段 1：Planner（只拆解不执行）===")
    steps = plan(task)
    print("\n=== 阶段 2：Executor（按计划执行）===")
    print(execute(steps, task))
