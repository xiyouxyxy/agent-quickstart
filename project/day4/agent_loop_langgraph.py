# ===== import 区：每个包干什么用 =====
# os: Python 标准库，读环境变量
import os  # noqa: I001

# Annotated: Python 类型注解扩展，给字段加额外元数据（给框架读的）
from typing import Annotated

# TypedDict: 声明一个"字典的形状"，比普通 dict 强约束（哪些字段、什么类型）
# typing_extensions 是 typing 的 backport，3.11 以下需要它
from typing_extensions import TypedDict

# @tool: 装饰器。把下面的普通函数变成 Tool 对象——自动从函数签名+docstring
#        生成给模型看的 JSON schema（D1 手写 TOOLS = [{...schema...}] 那段）
from langchain.tools import tool

# init_chat_model: 工厂函数，按 model_provider 创建不同厂商的 ChatModel 对象
# model_provider="openai" 表示用 OpenAI 兼容协议（MiniMax 走这个）
from langchain.chat_models import init_chat_model

# HumanMessage / ToolMessage: LangChain 的消息类型
#   HumanMessage = 用户说的话（role: "user"）
#   ToolMessage  = 工具执行返回的结果（role: "tool"，必须带 tool_call_id）
from langchain_core.messages import HumanMessage, ToolMessage

# StateGraph: 图的构造器
# START/END: 特殊锚点节点（不是你写的函数，只是入口/出口标记）
from langgraph.graph import StateGraph, START, END

# add_messages: 消息列表的合并函数（reducer）——追加而非覆盖
from langgraph.graph.message import add_messages

# load_dotenv: 把 .env 文件里的 KEY=VALUE 注入 os.environ
from dotenv import load_dotenv

load_dotenv()


@tool
def get_weather(city: str) -> dict:
    """获取天气
    :param city: 城市名
    :return: 天气信息
    """
    return {"city": city, "weather": "晴", "temp": 26}  # 假数据 26℃


@tool
def calculator(expression: str) -> str:
    """计算器
    :param expression: 表达式
    :return: 计算结果
    """
    return {
        "expression": expression,
        "result": eval(expression),
    }  # eval 仅示例，生产慎用


model = init_chat_model(
    model=os.getenv("MODEL_NAME"),  # 模型名，如 "MiniMax-M3.1-Flash-Preview"
    model_provider="openai",  # 走 OpenAI 兼容协议
    base_url=os.getenv("BASE_URL"),  # MiniMax 接口地址
    api_key=os.getenv("API_1") or os.getenv("API_KEY"),  # API key
    temperature=0.7,  # 温度：低=稳定JSON，高=创
)

tools = [get_weather, calculator]  # 工具列表，给模型看的 JSON schema
tools_by_name = {t.name: t for t in tools}  # 工具名->工具对象的映射，方便调用
model_with_tools = model.bind_tools(tools)  # 把工具列表传给模型，模型就能调用工具了


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]  # 消息列表，reducer=add_messages


def call_model(state: AgentState):
    msg = model_with_tools.invoke(
        state["messages"]
    )  # 调用模型，返回 ToolMessage 或 HumanMessage

    return {
        "messages": [msg]
    }  # 返回字典，reducer 会把 messages 追加到 state["messages"]


def call_tools(state: AgentState):
    last = state["messages"][-1]
    results = []
    for tc in last.tool_calls:
        fn = tools_by_name[tc["name"]]
        result = fn.invoke(tc["args"])
        results.append(ToolMessage(content=str(result), tool_call_id=tc["id"]))
    return {"messages": results}


def should_continue(state: AgentState):
    last = state["messages"][-1]
    # 如果模型说"我要调工具"，返回字符串 "tools" → 跳到 tools 节点
    if last.tool_calls:
        return "tools"
    # 否则返回 END → 流程结束
    return END


# 创建一个图构造器，告诉它这张图用哪个 State
g = StateGraph(AgentState)

# 注册节点：给函数起个名字挂进图
# 等价 react-router 的 <Route path="agent" element={<Agent/>}/>
g.add_node("agent", call_model)
g.add_node("tools", call_tools)

# 加边：
# add_edge(A, B) = A 跑完必到 B（无条件直达）
g.add_edge(START, "agent")  # 入口直接进 agent 节点

# add_conditional_edges(source, path_func) = source 跑完调 path_func
# path_func 返回字符串决定下一步去哪
g.add_conditional_edges("agent", should_continue)

# ★ 这条回头边 = D1 的 for 循环
# tools 跑完回 agent，让模型再决定下一步
# 没有它，调一次工具就结束了；有它，才能链式调用 add → multiply
g.add_edge("tools", "agent")

# 编译：校验图结构 + 转成可调用对象
# 编译时框架会检查：节点都注册了吗？边引用的节点名都对吗？
# 编译后才能 .invoke / .stream / .batch
app = g.compile()


# ===== 跑一次 =====
if __name__ == "__main__":
    # === Demo 1: invoke 模式（一次跑完拿最终 state） ===
    print("=" * 60)
    print("Demo 1: invoke 模式")
    print("=" * 60)
    result = app.invoke(
        {"messages": [HumanMessage(content="3 加 4 再乘以 2 是多少？")]}
    )
    for m in result["messages"]:
        m.pretty_print()

    # === Demo 2: stream 模式（每个节点跑完吐一次 chunk） ===
    print()
    print("=" * 60)
    print("Demo 2: stream 模式（每步可见）")
    print("=" * 60)
    for chunk in app.stream(
        {"messages": [HumanMessage(content="2 乘以 5 再加 1")]},
        stream_mode="updates",
    ):
        print("---")
        print(chunk)

    # === Demo 3: 画架构图（保存 png） ===
    print()
    print("=" * 60)
    print("Demo 3: 画架构图")
    print("=" * 60)
    # draw_mermaid_png 要联网访问 mermaid.ink 渲染，国内网络经常 SSL 失败
    # 失败就降级用 print_ascii（纯终端字符图，不联网）
    try:
        png_bytes = app.get_graph(xray=True).draw_mermaid_png()
        with open("agent_graph.png", "wb") as f:
            f.write(png_bytes)
        print("图已保存到 day4/agent_graph.png，双击查看")
    except Exception as e:
        print(f"在线渲染失败（{e.__class__.__name__}），改用终端 ASCII 图：")
        app.get_graph().print_ascii()
