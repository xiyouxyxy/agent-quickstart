### 1️⃣ 四块概念⭐

| 概念     | 一句话                                             | 对应你 day1 手写的什么                 |
| ------ | ----------------------------------------------- | ------------------------------ |
| model  | LLM 调用的统一封装（ChatOpenAI 等）                       | `call_llm()` 函数                |
| tool   | 工具定义+执行的统一协议（`@tool` 装饰器）                       | TOOLS 列表 + DISPATCH 字典         |
| prompt | 消息模板（ChatPromptTemplate）                        | `messages = [{"role":...}]` 手拼 |
| LCEL   | LangChain Expression Language，用 `\|` 管道组合 chain | `run_agent()` 里的 for 循环        |
**坑预警**（别被旧教程带歪）：
- 包已分裂：`langchain` / `langchain-core` / `langchain-community` / `langchain-openai`。老 `from langchain.chat_models import ChatOpenAI` 废弃，新写法 `from langchain_openai import ChatOpenAI`。
- LCEL（`chain = prompt | model`）是主推，老 `LLMChain(...)` 已 deprecated。教程看 2024 后的。
- MiniMax 兼容 OpenAI API → `ChatOpenAI(base_url=..., api_key=...)` 直接接，不需要专门包。
#### 1️⃣ Model 

![[day3-langchain入门-1792398973789.webp]]

`call_llm`函数 = LangChain 里的 ChatModel 调用，更准确地说是两件事的合体:
1. `httpx.post(...)` 那段 = `ChatOpenAI(model=..base_url=...,api_key=...)`本身：封装"把`messages`发给模型、拿回回复"的 HTTP细节
2. `"tools":TOOLS` 参数 = `llm.bind_tools (TooLS)`：把工具清单绑到模型上
所以等价写法是：`llm = ChatOpenAi(...).bing_tools(TOOLS)`，然后`msg=llm.invoke(messages)`。其中 `msg`就是`resp.json()["choices"][0]["message"]`，（Langchain里是`AIMessage`对象，`.tools_calls`属性对应手动解析的部分）

**LangChain 的 model 对象 = 模型调用适配器 + 统一接口 + 参数配置。**
主要分两类语言模型：
1. **LLM / Text Completion Model**
	- 输入：字符串
    - 输出：字符串
    - 老式 completion 接口，如 `OpenAI` 的 completion、部分本地模型
3. **Chat Model**
    - 输入：消息列表，如 `SystemMessage`、`HumanMessage`、`AIMessage`
    - 输出：`AIMessage`
    - 现在主流，如 `ChatOpenAI`、`ChatAnthropic`、`ChatOllama
LangChain 里更常用的是 **Chat Model**。

| 维度               | 内容                                                                                                                                              |
| ---------------- | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| **一句话**          | LangChain 把所有 LLM 调用包成 `ChatModel` 类，换模型=换一个类，业务代码不动                                                                                            |
| **对应你 day1 的什么** | 你的 `call_llm()` 函数——只不过它现在是个对象，能 `.invoke()`，`.stream()`                                                                                        |
| **最简代码**         | `from langchain_openai import ChatOpenAI`  <br>`llm = ChatOpenAI(model=MODEL_NAME, api_key=API_KEY, base_url=BASE_URL)`  <br>`llm.invoke("你好")` |
| **必考追问**         | "为什么不让模型直接调？" → 因为生产要切换 OpenAI/Anthropic/MiniMax，统一封装让业务代码零改动                                                                                   |
##### model 对象负责什么

比如：
```python
from langchain_openai import ChatOpenAI
model = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0,
    api_key="..."
)
```

这个 `model` 对象：
- 保存模型名、温度、最大 token、API key 等配置
- 提供统一调用方式：`invoke`、`stream`、`batch`、`ainvoke`
- 把 LangChain 消息格式转成 OpenAI API 格式
- 把 OpenAI 响应转成 LangChain 的 `AIMessage`
- 支持回调、追踪、重试、限流等横切能力
调用：
```python
resp = model.invoke("你好")
print(resp.content)
```
或 Chat 风格：
```python
from langchain_core.messages import HumanMessage
resp = model.invoke([HumanMessage(content="你好")])
```
##### 关键点
- **model 是“调用模型的句柄”**，不是训练模型。把它理解为：帮助调用大模型服务的遥控器 / 客户端对象，它本身不是模型，也不是权重文件。代码里创建它，是为了**不用自己写 HTTP 请求、拼 JSON、解析响应**，而是用统一方式调用模型。
- LangChain **不训练模型**，只负责调用、编排、组合
- 同一个接口可以切换不同厂商模型
- `Embeddings` 也是 LangChain 里的 model 概念，但它是**文本转向量**的模型，不是聊天语言模型
- `model` 通常和 `PromptTemplate`、`OutputParser`、`Retriever`、`Tool` 组合成 Chain/Agent
###### 不用换langchain时
要自己写：
```python
requests.post(
    "https://api.openai.com/v1/chat/completions",
    headers={"Authorization": "Bearer xxx"},
    json={
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": "你好"}],
        "temperature": 0
    }
)
```
还要自己处理返回 JSON、错误、流式输出等。
###### 用 LangChain 的 model
首先创建：
```python
model = ChatOpenAI(model="gpt-4o-mini", temperature=0)
```
然后调用：
```python
resp = model.invoke("你好")
print(resp.content)
```
它帮你做了这些事：
1. **保存配置**：模型名、温度、API key、超时等
2. **发请求**：把你的输入转成对应厂商 API 格式
3. **收响应**：把返回结果转成 LangChain 统一格式 `AIMessage`
4. **统一接口**：换 Anthropic、Ollama、本地模型时，调用方式基本不变
5. **支持流式/异步/批量**：`stream`、`ainvoke`、`batch`
6. **支持回调追踪**：记录调用开始、结束、错误、token 等
7. **方便组合**：和 Prompt、Parser、Retriever、Tool 拼成 Chain/Agent
它在整个流程里的位置：
```text
用户输入 -> Prompt模板 -> model 调用大模型 -> 输出解析 -> 结果
```
##### 为什么model可以统一接口

核心原因：**LangChain 用“抽象基类 + 适配器模式 + 统一数据格式”把不同厂商的差异收敛到同一个接口上。**

拆开看是四层机制：
###### 1. 定义抽象接口：BaseChatModel
LangChain 先规定“一个聊天模型必须长什么样”：
```python
class BaseChatModel(BaseLanguageModel, Runnable):
    def invoke(self, input, config=None): ...
    def stream(self, input, config=None): ...
    def batch(self, inputs, config=None): ...
    def _generate(self, messages, stop=None, **kwargs): ...  # 子类必须实现
```
- `invoke/stream/batch` 是**对外的统一接口**，由基类实现通用逻辑
- `_generate` 是**子类必须实现的私有方法**，厂商适配器只写这一块
- 所以用户永远调 `invoke`，而 OpenAI/Anthropic/Ollama 各自实现 `_generate`
这就是**模板方法模式**：父类定流程，子类填差异。
###### 2. 统一输入格式：消息体系
LangChain 定义了一套标准消息类：
```text
BaseMessage
├── SystemMessage
├── HumanMessage
├── AIMessage
└── ToolMessage
```
所有模型的输入都统一成 `list[BaseMessage]`。
适配器负责翻译：
```text
LangChain HumanMessage  ->  OpenAI {"role":"user","content":...}
                        ->  Anthropic {"role":"user","content":[...]}
                        ->  Ollama    {"role":"user","content":...}
```
用户只写一次 `HumanMessage`，各家适配器自己转。
###### 3. 统一输出格式：AIMessage / ChatResult
不管厂商返回什么 JSON，适配器都转成：
```python
AIMessage(
    content="回答文本",
    tool_calls=[...],
    usage_metadata={...},
    response_metadata={...}
)
```
所以 `resp.content` 对所有模型都成立。
###### 4. 统一标准参数 + 差异透传
标准参数（`temperature`、`max_tokens`、`stop`、`timeout`）由基类/适配器映射到厂商字段。
厂商特有参数不强行统一，通过 `model_kwargs` / `extra_body` 透传：

```python
ChatOpenAI(model="...", model_kwargs={"top_p": 0.9})
```

这样既统一了常用面，又不牺牲厂商能力。

###### 5. 横切能力由基类统一提供
`invoke/stream/batch` 这些方法在基类里统一处理：
- 回调（Callbacks）
- 追踪（Tracing）
- 重试、限流、缓存
- 异步封装
- 流式聚合

子类只关心“怎么把消息发给这个厂商、怎么把响应读回来”，不用重复实现这些。

###### 一张图总结
```text
用户代码
   │  统一调用 model.invoke(messages)
   ▼
BaseChatModel（统一接口 + 通用逻辑：回调/重试/流式/批处理）
   │  调用子类 _generate()
   ▼
适配器子类（ChatOpenAI / ChatAnthropic / ChatOllama）
   │  翻译输入 -> 厂商API -> 翻译输出
   ▼
厂商模型服务
```

###### 关键结论
- **“同一接口”不是魔法，是适配器模式**：每个厂商写一个适配器类，把差异封装在内部
- **统一的是“常用面”**：消息、标准参数、输出结构、调用方法
- **差异仍然存在**：厂商特有参数、特殊能力、错误码，需要透传或特殊处理
- 这就是为什么 LangChain 有大量 `langchain-openai`、`langchain-anthropic` 这类**集成包**——每个包就是一个适配器

类比：就像 JDBC。Java 代码永远调 `Connection.prepareStatement()`，但底下 MySQL、PostgreSQL、Oracle 各有一个 Driver 实现。LangChain 的 model 就是这个思路在 LLM 上的翻版。
#### 2️⃣ Tool —— 工具定义+执行的统一协议

| 维度               | 内容                                                                                                                                                                                 |
| ---------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **一句话**          | `@tool` 装饰器从函数签名+docstring 自动生成 JSON schema，省掉你 day1 手写的 TOOLS 列表                                                                                                                  |
| **对应你 day1 的什么** | `TOOLS` 列表 + `DISPATCH` 字典 → **合二为一**，装饰器搞定                                                                                                                                        |
| **最简代码**         | `from langchain_core.tools import tool`  <br>`@tool`  <br>`def get_weather(city: str) -> str:`  <br>"""查询指定城市当前天气""" # ← 这行 docstring 就是 schema 的 description  <br>return "晴 26℃"` |
| **必考追问**         | "schema 哪来的？" → 类型注解（city: str）+ docstring 第一行，LangChain 自动反射生成                                                                                                                    |
##### @tool装饰器

`@tool`：**这个装饰器的作用，就是把一个普通的 Python 函数，一键“包装”成大模型能看懂、能调用的“工具”。**
它主要帮你干了两件事：**自动写说明书** 和 **统一执行入口**。

==调用原因==；省略掉`TOOL`和`DISPATCH`的编写

==如何帮助偷懒==：你只要在函数头上加个 `@tool`，LangChain 就会在幕后利用 Python 的**反射机制（Inspect）**，自动扒你的代码：
- **扒函数名**：把 `get_weather` 变成工具的名字。
- **扒类型注解**：看到 `city: str`，自动生成参数要求（必填、字符串类型）。
- **扒 Docstring（文档字符串）**：看到 `"""查询指定城市当前天气"""`，自动把它变成工具的“功能描述”（description）。
也就是说本来的`get_weather`函数，
```python
def get_weather(city: str) -> str:
    """查询指定城市当前天气"""
```
在装饰器包装后，就会自动变成llm能看懂的JSON（schema）：
```json
{
  "name": "get_weather",
  "description": "查询指定城市当前天气",
  "parameters": {
    "type": "object",
    "properties": {
      "city": {"type": "string"}
    },
    "required": ["city"]
  }
}
```
这样包装后，不仅llm能直接读懂，自己也可以直接调用`.invoke()`
```python
# 包装后，你可以直接调用它的 invoke 方法
result = get_weather.invoke({"city": "北京"}) 
print(result) # 输出: 晴 26℃
```
##### docstring
![[day3-langchain入门-1792422607148.webp]]

选中的内容就是`docstring`
如果加上@tool装饰器
```python
from langchain_core.tools import tool

@tool
def get_weather(city: str) -> dict:
    """
    获取天气信息
    :param city: 城市名称
    :return: 天气信息字典
    """
    return {"city": city, "weather": "晴朗", "temp": "26℃"}
```
LangChain 会在后台自动做这些事：
- 看到函数名叫 `get_weather`，工具名就是 `get_weather`。
- 看到 `city: str`，知道必须传入一个字符串类型的 `city` 参数。
- 读取你的 docstring，把整个文本拿去作为工具的**描述（Description）**。
>在 docstring 里用的 `:param` 和 `:return` 是 **reStructuredText（reST）** 风格的写法（Sphinx 文档生成器最常用这种）。
>
   在 LangChain 中，如果你只写一段简短的话（比如只写“获取天气信息”），其实也完全够用。如果你用了 `:param` 这种详细格式，LangChain 的某些底层解析器（或者对应的大模型）也会尽量去解析它，并在需要时提取参数级别的说明。
#### 3️⃣ Prompt —— 消息模板（ChatPromptTemplate）

|维度|内容|
|---|---|
|**一句话**|把 `messages = [{"role":...}]` 手拼字符串，变成可复用、可参数化的模板对象|
|**对应你 day1 的什么**|`messages = [{"role":"system",...}, {"role":"user",...}]` 那两行手拼|
|**最简代码**|`from langchain_core.prompts import ChatPromptTemplate`  <br>`prompt = ChatPromptTemplate.from_messages([`  <br>("system", "你是一个助手，需要数据时调用工具。"),`<br> ("user", "{input}")`  <br>`])`|
|**必考追问**|"和 f-string 有什么区别？" → ChatPromptTemplate 输出的是 Message 对象列表，能直接喂 model；f-string 出来是纯字符串|

**Prompt 的本质确实就是“提示词”**。但在 LangChain（以及现代大模型开发）的语境下，Prompt 的形态从“**一段手写的纯文**本”升级成了“一个**可复用、带结构的模板对象**”。
##### 1. 早期（或你自己写脚本时）：手写长文本
以前调 API，可能会手动拼一个列表：
```python
messages = [
    {"role": "system", "content": "你是一个助手，需要数据时调用工具。"},
    {"role": "user", "content": "今天北京天气怎么样？"}
]
```
这种写法有两个痛点：
*   **死板**：每次换一个问题（比如问上海），你都要重新手写一遍列表。
*   **容易错**：`role` 和 `content` 拼错一个字母，API 就会报错。
##### 2. 现在（LangChain）：使用 `ChatPromptTemplate`
LangChain 把它封装成了一个“填空题模板”。
图片里的代码：
```python
prompt = ChatPromptTemplate.from_messages([
    ("system", "你是一个助手，需要数据时调用工具。"),
    ("user", "{input}")  # 注意这个 {input}
])
```
这里面的 `{input}` 就是**变量**。这个 `prompt` 现在是一个**对象**，它的作用相当于一个“模具”：
*   你的人设（`system`）是固定的。
*   用户的问题（`user`）是动态的。

当你真正要提问时，你只要把变量填进去：
```python
# 填入变量，生成最终要发给大模型的数据
final_messages = prompt.invoke({"input": "今天北京天气怎么样？"})
```
然后你直接把 `final_messages` 扔给模型：
```python
model.invoke(final_messages)
```
##### 追问

###### 和 f-string 有什么区别？
- ChatPromptTemplate 输出的是 **Message 对象列表**，能直接喂 model；f-string 出来是**纯字符串**

如果你用 f-string 拼字符串：
```python
user_input = "今天北京天气怎么样？"
text = f"你是一个助手。用户的问题是：{user_input}"
```
注意，`text` 只是一个**普通的纯字符串 (String)**。但是现在的 Chat 模型（比如 GPT-4、Claude）不仅需要文字，还需要知道**角色（Role）**。如果你直接把纯字符串发给 Chat 模型，它可能会报错，或者把它全当成 user 的话。
###### `ChatPromptTemplate` 的神奇之处在于
当它调用 `.invoke()` 之后，它不仅帮你填好了空，还会**自动打包成大模型需要的格式（Message 列表）**。
它输出的不是一段文字，而是类似这样的结构：
```python
[
    SystemMessage(content="你是一个助手..."),
    HumanMessage(content="今天北京天气怎么样？")
]
```
这个结构是**带有角色标签**的，可以直接无缝喂给模型。
**总结**：
*   **传统的 Prompt**：就像你每次去餐馆点菜，都要跟厨师口述一遍（纯字符串）。
*   **ChatPromptTemplate**：就像一张点菜单。上面印刷好的字（`system` 人设）是固定的，空出来的白条（`{input}`）是你自己填的。填完之后，服务员（LangChain）会把单子标准化，直接送进厨房（模型）。

所以，Prompt 不仅是提示词，在代码里它变成了一个**管理提示词、支持参数替换、并且能自动转换成模型标准输入格式的“工具/对象”**。
#### 4️⃣ LCEL —— LangChain Expression Language（管道 |）
>LangChain 里最核心、最优雅的语法：**LCEL（LangChain Expression Language，LangChain 表达式语言）**。![[day3-langchain入门-1792426466504.webp]]

| 维度               | 内容                                                                                                                                                   |
| ---------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| **一句话**          | 用 `\|` 把组件串成管道：`chain = prompt \| model`，类似 Unix 管道，前一个的输出喂给后一个                                                                                      |
| **对应你 day1 的什么** | 你的 `run_agent()` for 循环——但 LCEL 只解决"无工具的单轮问答"，**带工具的循环仍要自己写**                                                                                        |
| **最简代码**         | `chain = prompt \| model` ← 这就是一个最小 chain  <br>`chain.invoke({"input": "你好"})`                                                                       |
| **必考追问**         | "LCEL 等价于什么？" → `model.invoke(prompt.invoke({"input":"你好"}))`，`\|` 是语法糖  <br>"LCEL 能跑 Agent 循环吗？" → **不能直接跑**，工具循环仍要自己写 for（这是 LangChain 的一个反直觉点，必考） |
##### 用法
之前你学了：
*   `prompt` 负责把变量变成大模型能看懂的 `Message` 列表。
*   `model` 负责接收列表，调用大模型，返回结果。
如果没有管道，你每次都要这样嵌套着写（也就是图片里“必考追问”的第一点）：
```python
# 就像套娃一样，看着就很累
response = model.invoke(prompt.invoke({"input": "你好"}))
```

有了 LCEL 管道，你只需要这样写：
```python
# 把 prompt 的输出，直接塞进 model 的嘴里
chain = prompt | model

# 调用这个链
response = chain.invoke({"input": "你好"})
```
**那个 `|` 符号，纯粹就是上面那种“套娃代码”的“语法糖”**。它长得和 Linux 命令行里的 `|`（比如 `cat log.txt | grep "error"`）一模一样，意思也是：前一个程序的输出，作为后一个程序的输入。

>把 `|` 想象成一根水管，**数据只能==从左往右流**==。前一个组件的“输出结果”，必须是后一个组件的“输入参数”。

##### LCEL 到底强在哪？（为什么不用普通函数调用）
你可能会想：“我自己写个函数 `def my_chain(x): return model.invoke(prompt.invoke(x))` 不行吗？为什么要用 `|`？”

因为一旦你用了 `|`，把组件拼装成了 `chain` 对象，LangChain 就会自动赋予它**超能力**：
*   **流式输出**：你直接调用 `chain.stream(...)`，文字就会像打字机一样一点点吐出来。
*   **异步调用**：直接 `await chain.ainvoke(...)`。
*   **批量处理**：直接 `chain.batch([...])` 同时问好几个问题。
*   **自动追踪**：中间哪一步花了多少时间，出没出错，LangChain 框架自动帮你记录。

**这就是 LCEL 的价值：声明式编程。** 你只负责声明“谁连着谁”，底层怎么跑、怎么优化，框架帮你搞定。

##### LCEL为什么跑不了 Agent 循环？
这是图片里标红的“必考追问”，也是很多人学 LangChain 最容易踩坑的地方。

**LCEL 是一条==单行道==（DAG，==有向无环==图），数据只能从前往后流。**`prompt -> model -> parser`，流完就结束了。

但 **Agent（智能体）是什么？** 
Agent 是一个“**循环**”。它问模型 -> 模型说要调工具 -> 执行工具 -> **把工具结果再喂给模型** -> 模型再思考 -> 可能又要调工具... 

这个 `while` 循环，LCEL 的 `|` 管道是做不到的（管道不能倒流）。
所以图片里说：**“带工具的循环仍要自己写”**（或者用后来 LangChain 推出的 `LangGraph` 专门画图做循环）。

##### 对应day1代码
图片里说“对应你day1的 `run_agent()` for 循环”。
如果你第一天自己手写过，你的代码大概是这样的（伪代码）：
```python
# 你自己手写的流水线和循环
messages = build_prompt(user_input)
while True:
    response = call_llm(messages)
    if response.has_tool_calls:
        result = run_tool(response.tool_calls)
        messages.append(result)
    else:
        break
return response
```
*   其中的 `build_prompt` 到 `call_llm` 这一段**单次调用**，现在被 LCEL 简化成了 `prompt | model`。
*   而外面的 `while` 循环，LCEL 管不了，你还是得用代码老老实实写循环（除非进阶去学 LangGraph）。

**一句话总结**：**`prompt | model` 就是一条单次问答的流水线。** 把前面的组件串起来，代码清爽，还自带流式、异步功能。但别指望它帮你做带工具的复杂思考和循环。
#### 名词复盘

 一句话回答（你自己写，写不出=没懂）
不看上面表格，闭眼回答这 4 题：

1. Model 解决了什么痛点？换模型要改哪行代码？
2. `@tool` 装饰器靠什么生成 schema？
3. ChatPromptTemplate 和 f-string 的区别？
4. **LCEL 能跑带工具的 Agent 循环吗？为什么？**（第 4 题是面试最大坑）

### 2️⃣ 跑通官方 quickstart（1h）⭐⭐ 今天最高优先

#### ① 装包（沙箱 venv，别全局）
在 VS Code 终端跑：
```bash
pip install langchain langchain-openai
```
（`langchain` 主包 + `langchain-openai` 的 ChatOpenAI 类，两个都装）
#### ② 跑官方 quickstart ⭐⭐

地址：`https://python.langchain.com/docs/tutorials/llm_chain/`

目标：跑通「prompt + model + parser」管道最小例子，能输出一句话。**装完包就跑，别先看长篇文档**——quickstart 本身就是文档。

验收点：你能说出 `chain = prompt | model | output_parser` 这一行每个组件是什么、为什么用 `|`。

---

## 下午块② 14:00-17:00（3h）：⭐产出=LangChain 重写 agent_loop

`project/day3/agent_loop_langchain.py`，复用 day1 的工具函数和 system prompt，目标：实现 Day1 同款「天气+计算器」双工具 Agent，验收=「北京今天多少度？温度乘2再加10」连续调两工具答对。

**3 处改动指引**：

1. `ChatOpenAI` 替代 `call_llm()`：`llm = ChatOpenAI(model=..., api_key=..., base_url=...)`
2. `@tool` 装饰器替代 TOOLS+DISPATCH：`@tool\ndef get_weather(city: str): ...`，自动从 docstring+类型注解生成 schema
3. `llm.bind_tools([get_weather, calculate])` 让模型知道工具；输出有 `tool_calls` 仍要自己 dispatch——**LangChain 不自动执行工具**，这正好对照 Day1，是面试加分点

**进阶**（富余再做）：用 LCEL 写 `prompt | llm.bind_tools([...])` 最小管道对比可读性。别陷进深水区。

```python
```

---

## 对照表（下午写完代码后填，面试素材）

|维度|手写 agent_loop|LangChain 版|谁赢|
|---|---|---|---|
|代码量|~60 行|~30 行|LC|
|工具 schema|手写 JSON|@tool 自动生成|LC|
|模型切换|改 BASE_URL/MODEL|换一个类|LC|
|执行循环|自己 for+dispatch|仍自己写|平|
|学习成本|0|多一层抽象|手写|
|生产可控性|全代码可见|黑盒多|手写|

**面试话术**：「手写是底座、LangChain 是工程提速——小项目手写更清楚，大项目 LangChain 省 schema/模型切换的重复活，但循环逻辑仍要自己写，LC 不是魔法。」

## 睡前面试自测（不查笔记）

1. LangChain 解决了手写 Agent 的什么痛点？（schema 自动生成 / 模型切换 / prompt 模板）
2. `@tool` 装饰器做了什么？（从函数签名+docstring 生成 schema）
3. LCEL 是什么？`prompt | model` 等价于什么？
4. **LangChain 会自动执行工具吗？**（不会，只生成 tool_calls——和 Function Calling 一致，必考）
5. 为什么不用 LangChain 的 AgentExecutor？（封装太重黑盒；自写循环可控且能讲清原理）