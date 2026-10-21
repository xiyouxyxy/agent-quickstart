---
aliases:
  - |-
    day4-

    LangGraph
---

### 主题：LangGraph — 状态机、节点/边、循环、条件路由

**今天结束时的标准**：有一个 `agent_loop_langgraph.py`，把 D1 手写的 `agent_loop.py` 用 LangGraph 重写一遍；能脱稿说清「LangGraph 和 LangChain LCEL 的本质区别 = 显式状态机 + 循环 + 条件路由」。

⭐ **最低保留项**：跑通 single-agent graph（一个 LLM 节点 + 一个工具节点 + 一条条件边 + 循环回 LLM）。

---

### 上午 2.5h · 概念扫盲 + Quickstart

#### 1️⃣ LangGraph 六个核心名词（1h）⭐

照 D3 的对比表风格，自己先填再对答案：

| 名词               | 一句话                                                | 对应 D1 手写的什么                                       |
| ---------------- | -------------------------------------------------- | ------------------------------------------------- |
| State            | 跨节点共享的「全局上下文」，用 `TypedDict` 声明（如 `messages: list`） | `messages = [...]` 那个变量                           |
| Node             | 接收 state、返回 dict（会被 merge 回 state）的函数              | `call_llm()` / 工具 dispatch 两段                     |
| Edge             | 节点之间的固定流转                                          | for 循环里"调完工具再回 LLM"的隐式顺序                          |
| Conditional Edge | 根据当前 state 决定下一个节点（函数返回节点名字符串）                     | `if msg.get("tool_calls"): ... else: return` 那个分支 |
| START / END      | 唯一入口 / 唯一出口特殊节点                                    | `run_agent()` 的入参和 `return msg["content"]`        |
| Compiled Graph   | `graph.compile()` 后的可调用对象，`.invoke()`/.stream()    | `run_agent(user_input)` 整个函数                      |

##### 六名词展开（对答案用）

![[day4-langgraph-名词关系图.svg]]

###### **State —— 全局共享上下文**

一个用 `TypedDict` 声明的数据结构，**所有节点读写的是同一份**，这是 LangGraph 和手写版最本质的差异。

```python
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
#                ↑           ↑
#        真实类型还是 list   附加信息：合并策略 = add_messages 函数
```

- 关键细节是 `Annotated[list, add_messages]`：节点返回 dict 后，LangGraph 要决定「==返回值怎么合并进 state==」——默认行为是**整个 key 覆盖**，而 `add_messages` 这个 reducer 把覆盖改成**追加**。
	- **LangGraph**是唯一会去读这个标签的读者。LangGraph 编译图时扫描 State 的每个字段，发现 `messages` 挂了 `add_messages`，就把它当作 **reducer**​（合并函数）使用——节点返回 `{"messages": [新消息]}` 时，LangGraph ==不再直接覆盖==，而是调 `add_messages(旧列表, 新消息)`，结果就是追加
	- 也有别的属性比如：
		- 不写：默认覆盖
		- `operator.add`通用追加，纯拼接。而`add_messages`会按照`id`去重
		- 自定义函数 √![[day4-LangGraph-1792519808730.webp]]
- D1 手写版里 `messages.append(...)` 干的事，在这里就是它的职责。
- 不写会怎样：没有 reducer 的字段默认合并策略 = 整个覆盖。节点返回 `[新消息]`，旧的对话历史直接被冲掉，模型第二轮==失忆==。
- D1 对照：`messages = [...]` 是 `run_agent()` 里的局部变量，靠函数参数和闭包传递；LangGraph 把它提升成图级别的显式状态。
- **面试追问**：「为什么节点只返回 dict 不返回整个 state？」→ 局部更新让多个节点可以并行写不同字段互不干扰，也让每一步的 state 变化可追踪可重放。

###### **Node —— 节点 = 函数**

一个节点就是一个普通 Python 函数：入参是当前 state，返回一个 dict。返回的 dict **不是替换 state，而是 merge 进去**（按上面说的 reducer 规则）。

```python
def call_model(state: AgentState):
    resp = llm.invoke(state["messages"])
    return {"messages": [resp]}   # 只声明"我改了 messages"，其他字段不动
```

- D1 对照：`call_llm()` + 工具 dispatch 那两段代码，拆成两个函数就是两个节点。
- 心智转变：**节点不做流程控制**——「接下来干什么」不归节点管，归边管。

###### **Edge —— 固定流转**

`g.add_edge("tools", "agent")`：A 节点跑完必到 B 节点，没有条件。

- D1 对照：for 循环里「执行完工具再回 LLM」这个隐式顺序。手写版的流程顺序**藏在代码控制流里**（for、缩进、break），LangGraph 把它变成**图的数据结构**——所以能画出来、能静态检查、能在 LangSmith 里追踪。
- 面试好表达：「**从控制流变成数据**」。

###### **Conditional Edge —— 条件路由**
>路由就是和React-Router一样的路由，`add_conditional_edges` 干的事，本质就是给图装了一个 `navigate()`。

`add_conditional_edges("agent", should_continue)`：从某节点出发，**路由函数读当前 state，返回下一个节点的名字符串**（或 `END`）。
```python
def should_continue(state: AgentState):
    if state["messages"][-1].tool_calls:
        return "tools"    # 字符串节点名，不是节点对象
    return END
```
- D1 对照：`if msg.get("tool_calls"): ... else: return msg["content"]` 那个分支。
- **面试追问**「和普通 if/else 区别？」→ 路由逻辑成了图结构的一部分：可视化时能看到分叉、LangSmith 追踪时能看到每次路由走了哪条、多 Agent 时路由就是 supervisor 的调度逻辑。
- ⚠️ 坑：路由函数返回不存在的节点名，编译时不报错，**运行时**才报 `ValueError`——跑之前核对名字。

==路由怎么查 / 字符串是怎么变成 跳转 的==：关键机制就一句：**路由函数返回的字符串是节点名，LangGraph 拿它去节点表里查，查到哪个就跳哪个**。
```python
g.add_node("tools", call_tools) # ≈ 注册路由表：<Route path="tools" .../>
g.add_conditional_edges("agent", should_continue) # ≈ agent 页面里挂了个 navigate 逻辑
```
用react-router来理解就是
```jsx
// react-router 世界                          // LangGraph 世界
<Route path="tools" element={<Tools/>} />     g.add_node("tools", call_tools)
navigate(isLogin ? "/tools" : "/home")        return "tools" if ... else END
```

==和day1的对比==：
```text
第1轮  agent 返回：我要调 get_weather(北京)
    → should_continue 读 state，发现 tool_calls 有货 → 返回 "tools" → 跳 tools 节点
第2轮  agent 拿到 25℃，返回：我要调 calculate("25*2+10")
    → 又有 tool_calls → "tools" → 再跳
第3轮  agent 拿到 60，直接写答案
    → 没有 tool_calls → 返回 END → 流程结束
```
同一个函数被调三次、三次返回不同字符串、走三条不同的路——**判断发生在每次运行时现场，不是写死的**。这就是「条件」二字的含义，普通边（`add_edge`）则是无条件直达，没有判断环节。

==和 D1 的 if/else 区别==（面试追问的完整版）：D1 的 `if msg.get("tool_calls")` 写在 for 循环体内：**判断和「接下来干什么」耦合在一起**，跳走就回不来，外面的人看不见你走了哪个分支。条件边把这件事拆开：判断逻辑独立成 `should_continue` 函数，跳转由框架执行——代价是多写几行，换来的是：每次路由决策被记录（LangSmith 里能看到每轮走了哪条边）、整张图能画出来给面试官看、`should_continue` 可以单独写单测。

###### **START / END —— 特殊锚点**

图必须有唯一入口和出口，这两个是 LangGraph 内置的特殊节点：`add_edge(START, "agent")` 声明从哪进；路由函数返回 `END` 表示流程结束。它们不是你写的函数，只是锚点。

- D1 对照：`run_agent(user_input)` 的入参 = START；`return msg["content"]` = END。手写版里「结束」靠 return 语句，图里「结束」是一条显式的边。

###### **Compiled Graph —— 编译后的可执行对象**

`g.compile()` 把你声明的 State + Node + Edge 校验并编译成一个 Runnable，之后 `.invoke(input)` 一次跑完、`.stream()` 逐步吐出每步的 state 快照。

- D1 对照：`run_agent()` 整个函数。
- **多出来的能力**：stream 的每步快照是白送的观测性（手写版要自己 print）；`app.get_graph().draw_mermaid()` 能直接导出架构图——⭐产出要画的图，一行代码就有了。

> **串起来的一句话**（面试可用）：手写版里「状态、顺序、分支、循环」散在函数体里；LangGraph 把它们分别抽成 State、Edge、Conditional Edge、回头边，节点只管计算——所以循环驱动从 for 变成了图，观测和扩展（多 Agent）才有抓手。D7 的 supervisor 模式，无非就是把「条件边」换成「路由到不同 agent 节点」。

#### 2️⃣ 跑官方 Quickstart（1.5h）⭐

- 装包：`pip install langgraph`（注意包名是 `langgraph`，不是 `langchain`）
- 跑通 [LangGraph Quickstart](https://docs.langchain.com/oss/python/langgraph/quickstart)（⚠️ 官方文档已迁移到 docs.langchain.com，旧版 "Part 1~Part 3" 教程已删除；新 Quickstart = 6 步搭计算器 Agent，正好覆盖本清单骨架：定义工具和模型 → 定义状态 → 模型节点 → 工具节点 → 条件路由 → StateGraph 编译），**手抄一遍**别只看
- 教程示例用 Claude/Anthropic，换 MiniMax：`ChatOpenAI(model=..., api_key=..., base_url=...)`（D3 那套直接搬）
- ⚠️ **三个坑**（D3 已踩过类似）：
  1. `from langgraph.graph import StateGraph, START, END` — 不是 `from langchain...`
  2. 节点函数返回 `{"messages": [...]}`，**返回的 key 必须在 State TypedDict 里声明过**，否则被默认丢弃（默认 reducer 是覆盖，消息列表要用 `Annotated[list, add_messages]` 做 append）
  3. 条件边的路由函数返回的是**字符串节点名**，不是节点对象

##### quickstart里面在做什么

把 D1 的 `run_agent()` 那个 for 循环，拆成 6 个零件组装成图。每个零件都是你 D1 已经写过的东西，只是换了件衣服。
```text
D1 run_agent():                    quickstart:
─────────────────                  ─────────────────
messages = [...]          step2 →  State(TypedDict)
call_llm()                step3 →  def call_model(state)
DISPATCH[fn](**args)      step4 →  def call_tools(state)
if tool_calls: ...        step5 →  def should_continue(state)
for step in range(6):     step6 →  图的循环边
```
###### 1. 定义工具和模型
```python
from langchain.tools import tool
from langchain.chat_models import init_chat_model
model = init_chat_model(
    "claude-sonnet-4-6",
    temperature=0
)
@tool
def add(a: int, b: int) -> int:
    """Adds `a` and `b`.     # ← docstring 会变成给模型看到描述

    Args:
        a: First int
        b: Second int
    """
    return a + b

tools = [add, multiply, divide] 
tools_by_name = {tool.name: tool for tool in tools}  # = DISPATCH
model_with_tools = model.bind_tools(tools)           # = 'tools' = TOOLS
```
###### 2. 定义状态
```python
from langchain.messages import AnyMessage
from typing_extensions import TypedDict, Annotated
import operator
class MessagesState(TypedDict):
    messages: Annotated[list[AnyMessage], operator.add]
    llm_calls: int
```
- `messages: list` ← 这是「真实类型」
- `Annotated[..., add_messages]` ← 这是「合并策略」（追加而非覆盖）
- 整个 State 等价于 D1 里的「`messages` 这个会被各节点往里 append 的列表」，区别只是从函数局部变量提升成==图级共享==
###### 3. 定义模型节点
D1 的 `call_llm()` —— 调 LLM
>节点=函数（见node那一节）
```python
from langchain.messages import SystemMessage
def llm_call(state: dict):    # 入参 = 当前的state
    """LLM decides whether to call a tool or not"""   # day1 call_llm
    return {                  # 返回dict，不直接改state
        "messages": [
            model_with_tools.invoke(
                [
                    SystemMessage(
                        content="You are a helpful assistant tasked with performing arithmetic on a set of inputs."
                    )
                ]
                + state["messages"]
            )
        ],
        "llm_calls": state.get('llm_calls', 0) + 1
    }
```
三个关键：
1. **节点不读外部变量，只读 state**——这是和 D1 `call_llm(messages)` 的本质区别，D1 靠参数传递，这里靠 state 共享
2. **返回 dict 不是修改 state**——你在函数里写 `state["messages"].append(msg)` 是错的，必须 `return {"messages": [msg]}`，框架拿返回值调 reducer 合并
3. **`[msg]` 两边都有方括号**——必须返回列表，因为 `add_messages(旧列表, 新列表)`
###### 4. 定义工具节点
D1 的 `for tc in tool_calls: DISPATCH[...]`
```python
from langchain.messages import ToolMessage
def tool_node(state: dict):
    """Performs the tool call"""
    result = []
    for tool_call in state["messages"][-1].tool_calls:
        tool = tools_by_name[tool_call["name"]]       # DISPATCH
        observation = tool.invoke(tool_call["args"])  # DISPATCH[fn](**args)
        result.append(ToolMessage(content=observation, tool_call_id=tool_call["id"]))
    return {"messages": result}
```
和 D1 的差异：D1 是「每个 tool 结果立刻塞回 messages」，这里是「全部执行完一次性返回」。为什么？多次工具调用时框架可以**并行**执行，结果统一合入——这就是 day1 手写版做不到的事。
###### 5. 定义终端逻辑
```python
from typing import Literal
from langgraph.graph import StateGraph, START, END
def should_continue(state: MessagesState) -> Literal["tool_node", END]:
    """Decide if we should continue the loop or stop based upon whether the LLM made a tool call"""
    messages = state["messages"]
    last_message = messages[-1]
    if last_message.tool_calls:
        return "tool_node"   # 有工具调用 → 跳tools节点
    return END               # 没工具调用 → 结束（END是特殊字符）
```
注意它**不执行任何东西，只返回字符串**——框架拿字符串去节点表查。
###### 6. 构建并编译代理
```python
# Build workflow
agent_builder = StateGraph(MessagesState)  # 这张图就用上面配置好的MessagesState

# Add nodes
agent_builder.add_node("llm_call", llm_call)
agent_builder.add_node("tool_node", tool_node)

# Add edges to connect nodes
agent_builder.add_edge(START, "llm_call")
agent_builder.add_conditional_edges(
    "llm_call",
    should_continue,   # 返回出 运行时跳哪
    ["tool_node", END] # 可选的目的地声明
)
agent_builder.add_edge("tool_node", "llm_call")

# Compile the agent
agent = agent_builder.compile()

# Show the agent
from IPython.display import Image, display
# display(Image(agent.get_graph(xray=True).draw_mermaid_png()))这一行说需要有别的依赖环境，此时跑不通
png_bytes = agent.get_graph(xray=True).draw_mermaid_png()
with open("agent_graph.png", "wb") as f:
    f.write(png_bytes)
print("图已保存到 agent_graph.png")


# Invoke
from langchain.messages import HumanMessage
messages = [HumanMessage(content="Add 3 and 4.")]
messages = agent.invoke({"messages": messages})
for m in messages["messages"]:
    m.pretty_print()
```

---

### 下午 3h · 手写 Graph 版 Agent ⭐（今天最核心产出）

在 `D:/agent-learn/project/day4/` 下新建 `agent_loop_langgraph.py`，目标：**复刻 D1 的 `run_agent("北京今天多少度？温度乘以2再加10")` 行为**，但全程不写 for 循环——让循环由图的边来驱动。

骨架（自己补全）：

```python
from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_openai import ChatOpenAI
# 复用 D1 的 TOOLS / DISPATCH，或用 langchain @tool 装饰器

class AgentState(TypedDict):
    messages: Annotated[list, add_messages]

def call_model(state: AgentState):
    resp = llm.invoke(state["messages"])      # 1 个节点 = 1 个函数
    return {"messages": [resp]}                 # 返回会被 reducer append

def call_tools(state: AgentState):
    last = state["messages"][-1]
    # 执行 last.tool_calls，每个 tool_call_id 对应一条 ToolMessage
    return {"messages": tool_messages}

def should_continue(state: AgentState):         # ★ 条件边路由函数
    last = state["messages"][-1]
    if last.tool_calls:
        return "tools"                          # 字符串节点名
    return END

# 组装图
g = StateGraph(AgentState)
g.add_node("agent", call_model)
g.add_node("tools", call_tools)
g.add_edge(START, "agent")
g.add_conditional_edges("agent", should_continue)  # ★ D1 的 if/else 变成图里一条边
g.add_edge("tools", "agent")                       # ★ D1 的 for 循环 = 这条回头边

app = g.compile()                                  # 编译后 .invoke 即可
result = app.invoke({"messages": [HumanMessage("北京今天多少度？×2+10=?")]})
```

**验收**：和 D1 一样能连续调用两个工具（先 weather 后 calculate）后给出正确答案；用 `app.stream(...)` 看每步 state 快照——这是面试时讲「LangGraph 可观测性比手写 loop 强在哪」的素材。

**画图存档**：在 `day4-langgraph.md` 里画一张 ASCII 流程图（START → agent → (条件边) → tools → agent → ... → END），面试时「能画图讲架构」就是这条⭐ 的兑现。

---

### 晚上 1h · 自测 + git commit

口答下面 6 题（不看笔记），答不上的回上午表补：

1. LangGraph 和 LangChain LCEL 的本质区别？（关键词：显式状态机 / 循环 / 条件路由 / 多 Agent）
2. 为什么 LangGraph 适合做多 Agent，而 LCEL 不太适合？（state 共享 + supervisor 路由 + 循环）
3. State 用 TypedDict 声明，节点函数为什么只返回 dict 而不是整个 state？（reducer 机制，便于并行与可观测）
4. `Annotated[list, add_messages]` 这个 Annotated 是干嘛的？不写会怎样？
5. 条件边路由函数返回什么类型？写错会报什么错？
6. 你的 D1 手写循环和 LangGraph 版相比，工程化上多了什么？（可观测 stream / 可重放 / 状态显式 / 多 Agent 扩展）

**收尾动作**（固定三件套）：
- `agent_loop_langgraph.py` + `day4-langgraph.md` push 到 GitHub
- 名词表追加 LangGraph 六词
- 带着问题睡：明天 D5 进 RAG，LangGraph 在 RAG 里能干嘛？（→ D9 Agentic RAG 要用到）

---

### 资源（只认三个里的第二个）

- `adongwanai/AgentGuide` 的 LangGraph 章节（D4-D8 主线）
- LangGraph 官方 quickstart：https://docs.langchain.com/oss/python/langgraph/quickstart （旧地址 langchain-ai.github.io 已迁移废弃）
- D3 你自己的 `day3-langchain入门.md`——D4 的对照物

---

**进度提醒**：D4 + D5 都欠了，今天若只补完 D4，D5（RAG 主线：切分/Embedding/FAISS）明天必须起，否则 D9 Agentic RAG 会断档。需要的话直接说「列 D5 清单」，我按同款格式出。