"""
Day4 ⭐ LangGraph quickstart —— 逐行解析版（MiniMax 适配）

读法：从上到下，每读一行代码先看上面的注释——注释解释这行做什么、
对应 D1 手写版哪段、为什么这么写。读完这个文件，你应该能脱稿
解释"LangGraph 在做什么"。
"""

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


# ===== Step 0: 加载环境变量 =====
# 读 .env 文件里的 API_1 / BASE_URL / MODEL_NAME，注入 os.environ
# 之后 os.getenv 就能拿到值（不写这行 .env 里的 key 拿不到）
load_dotenv()


# ===== Step 1: 模型 + 工具（D1 的 call_llm + TOOLS + DISPATCH 三件套）=====

# init_chat_model 创建一个"调用 MiniMax 大模型的句柄"
# 等价于 D1 里你写的 call_llm 函数，但封装成可 .invoke 的对象
model = init_chat_model(
    model=os.getenv("MODEL_NAME"),  # 模型名，如 "MiniMax-M3.1-Flash-Preview"
    model_provider="openai",  # 走 OpenAI 兼容协议
    api_key=os.getenv("API_1") or os.getenv("API_KEY"),  # API key
    base_url=os.getenv("BASE_URL"),  # MiniMax 接口地址
    temperature=0.7,  # 温度：低=稳定JSON，高=创意
)


# @tool 装饰器的作用：
#   1. 把下面的函数包成 Tool 对象
#   2. 从函数签名 (a: int, b: int) -> int 自动生成参数 schema
#   3. 从 docstring "Adds a and b." 自动生成工具描述
# 模型看到的就是这个 schema + 描述，然后决定要不要调它
@tool
def add(a: int, b: int) -> int:
    """Adds a and b."""
    return a + b


@tool
def multiply(a: int, b: int) -> int:
    """Multiplies a and b."""
    return a * b


# tools 列表 = D1 的 TOOLS（给模型看的工具清单）
tools = [add, multiply]
# tools_by_name 字典 = D1 的 DISPATCH（名字 → 函数 的查表，执行用）
# 字典推导式语法：{key_expr: val_expr for item in iterable}
# 注意循环变量用 t，不用 tool（tool 是上面 @tool 装饰器，会被覆盖）
tools_by_name = {t.name: t for t in tools}
# 把工具清单绑到模型上 = D1 请求体里的 "tools": TOOLS 参数
# 绑定后返回新对象 model_with_tools，原 model 不变
# 之后每次 invoke，LangChain 自动把工具 schema 塞进请求
model_with_tools = model.bind_tools(tools)


# ===== Step 2: State（D1 的 messages 局部变量提升为图级共享）=====


# TypedDict 声明 State 的"形状"——所有节点共享这一份数据
# 入口 invoke({"messages": [...]}) 时初始化它
class AgentState(TypedDict):
    # messages 字段：类型是 list（消息列表）
    # Annotated[list, add_messages] 的 add_messages 是 reducer（合并函数）
    # 节点返回 {"messages": [新消息]} 时：
    #   - 不写 Annotated → 整个 key 被覆盖（旧消息全丢）
    #   - 写了 add_messages → 调 add_messages(旧列表, 新列表) → 追加
    # 这就是 D1 里 messages.append(...) 在 LangGraph 里的等价物
    messages: Annotated[list, add_messages]


# ===== Step 3: 模型节点（D1 的 call_llm）=====


# 节点 = 函数。入参是当前 state，返回一个 dict（会被 reducer 合并进 state）
# 关键规则：不能直接修改 state，必须 return dict
def call_model(state: AgentState):
    # state["messages"] 是当前所有消息（含历史）
    # model_with_tools.invoke(...) = D1 的 httpx.post(...) 调一次模型
    # 模型看到工具清单后会决定：要么回答，要么返回 tool_calls
    msg = model_with_tools.invoke(state["messages"])
    # 返回 dict，key 必须在 AgentState 里声明过
    # [msg] 包成列表，因为 add_messages 期望"新值是列表"做追加
    # 框架会调 add_messages(旧 messages, [msg]) → 把 msg append 进去
    return {"messages": [msg]}


# ===== Step 4: 工具节点（D1 的 for tc in tool_calls: DISPATCH[fn](**args)）=====


def call_tools(state: AgentState):
    # state["messages"][-1] 拿最后一条消息（一定是上一步 agent 返回的 AIMessage）
    # 这条消息可能带 tool_calls：模型说"我要调 add(3,4) 和 multiply(7,2)"
    last = state["messages"][-1]
    results = []
    # 遍历模型要求调的所有工具（一次可能调多个）
    for tc in last.tool_calls:
        # tc 长这样: {"name": "add", "args": {"a": 3, "b": 4}, "id": "call_xxx"}
        # 按名字查表拿真函数 = D1 的 DISPATCH[fn]
        fn = tools_by_name[tc["name"]]
        # 执行真函数 = D1 的 DISPATCH[fn](**args)
        # tc["args"] 已经是 dict，直接传
        result = fn.invoke(tc["args"])
        # 工具结果必须包成 ToolMessage，并且 tool_call_id 必须对得上
        # 模型靠 tool_call_id 把"我要求的调用"和"返回的结果"配对
        results.append(ToolMessage(content=str(result), tool_call_id=tc["id"]))
    # 一次性返回所有工具结果（多个 ToolMessage 一起 merge 进 state）
    return {"messages": results}


# ===== Step 5: 条件路由（D1 的 if tool_calls: ... else: return）=====


# 路由函数：不执行任何东西，只返回"下一步去哪"的字符串
# 框架拿这个字符串去节点表查表跳转（类似 react-router 的 navigate("/path")）
def should_continue(state: AgentState):
    last = state["messages"][-1]
    # 如果模型说"我要调工具"，返回字符串 "tools" → 跳到 tools 节点
    if last.tool_calls:
        return "tools"
    # 否则返回 END → 流程结束
    return END


# ===== Step 6: 组装图（D1 的 run_agent for 循环）=====

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
    # invoke 入参 = 初始 state 的部分字段（只给 messages）
    # 返回值 = 跑完后的完整 state（dict）
    result = app.invoke(
        {"messages": [HumanMessage(content="3 加 4 再乘以 2 是多少？")]}
    )
    # result["messages"] 是完整历史（追加式 reducer 留住了每步）
    # pretty_print() 带角色标签的美化打印
    # 输出会看到 4-6 条消息：human → ai(tool_calls) → tool → ai(tool_calls) → tool → ai(final)
    for m in result["messages"]:
        m.pretty_print()

    # === Demo 2: stream 模式（每个节点跑完吐一次 chunk） ===
    print()
    print("=" * 60)
    print("Demo 2: stream 模式（每步可见）")
    print("=" * 60)
    # stream_mode="updates" = 吐"节点返回值"（增量，轻量）
    # 每个 chunk 是 {节点名: 该节点返回的 dict}
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
    # get_graph() 拿图对象，draw_mermaid_png() 导出 mermaid 流程图 PNG
    # xray=True = 把节点内部也透视出来（能看到 tools 里有哪些工具）
    png_bytes = app.get_graph(xray=True).draw_mermaid_png()
    with open("agent_graph.png", "wb") as f:
        f.write(png_bytes)
    print("图已保存到 day4/agent_graph.png，双击查看")


# ===== 读完后自测（脱稿回答，答不上就回查对应 Step） =====
# 1. add_messages 这个 reducer 如果不写，会发生什么？(回 Step 2)
# 2. call_model 里为什么必须 return dict，不能直接 state["messages"].append？(回 Step 3)
# 3. ToolMessage 为什么必须带 tool_call_id？(回 Step 4)
# 4. should_continue 返回 "tools" 这字符串去哪了？(回 Step 5)
# 5. 那条 add_edge("tools", "agent") 如果删掉，会发生什么？(回 Step 6)
# 6. invoke 和 stream 输出的区别是什么？(回 Demo 1 / Demo 2)
