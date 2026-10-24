# Day 5 · RAG 主线：文档加载 / 切分 / Embedding / 向量检索（FAISS）

> 日期：2026-10-22（周四）｜前置：D3 LangChain、D4 LangGraph 已跑通
> **明天结束时的标准**：能脱稿说清 RAG 五步流水线，并且有一个自己写的 `mini_rag.py`——问一句话，能从 `docs/` 里召回正确段落、基于它回答；问资料里没有的，会老实说"没有"。
> ⭐ **最低保留项**：切分 + 检索跑通（第 2 块的 Step 2 + Step 5）。哪怕只有 3 小时，做完这两步今天就不算掉队。
> 为什么今天重要：这段代码就是 **D9 简历项目 1（Agentic RAG）** 的地基。今天的 `split_text` + `Retriever` 明天会被包进 Agent 的节点里，一行都不白写。

---

## 生词表（先扫一眼，全部英文名词的中文解释）

> 2026-10-24 补：之前这份清单直接甩了没解释的英文名词，是我的错。**这张表里"今天要不要懂"一栏写"跳过"的，可以直接不看。**

| 英文 | 中文 | 一句人话 | 今天要不要懂 |
| --- | --- | --- | --- |
| RAG | 检索增强生成 | 先从资料里搜出相关段落，再让模型照着这些段落回答 | 要 |
| Embedding | 向量化 / 嵌入 | 把一段文字变成一串数字（1536 个小），意思像的，数字也像 | 要 |
| chunk | 切片 / 片段 | 从长文档里切出来的一小段文字，是检索的最小单位 | 要 |
| overlap | 重叠 | 相邻两片故意重复一点尾巴，防止关键句正好被切成两半 | 要 |
| metadata | 元数据 / 附加信息 | 跟正文一起存的信息，比如"来自哪个文件第几页" | 要 |
| top-k | 取前 k 个 | 按分数排完序，拿最像的 k 条（k 一般取 3~5） | 要 |
| FAISS | （一个工具库的名字，读作"费斯"） | 专门干"给一个向量，快速找出最像的几个"这件事的库 | 要（会用就行，不用懂内部） |
| IndexFlatIP | 内积索引（Flat = 平铺，IP = 内积） | 最笨最实在的写法：拿问题跟每一条逐一算相似度，然后排序 | 要（今天就用它，代码是我给你写好的） |
| IndexFlatL2 | 欧氏距离索引 | 同上，只是改用"直线距离"衡量远近 | 知道名字即可，**今天不用** |
| IndexIVF / HNSW | 近似索引（两种加速结构） | 数据上百万条时才需要：先分桶、只搜几个桶，用一点点准确率换速度 | **今天完全跳过** |
| MMR | 最大边际相关 | 一种挑结果的策略，避免 top-3 全是同一段重复内容 | 知道有这东西即可 |
| BM25 | 关键词检索算法 | 老式搜索引擎打分法，只数"词出现了几次"，不懂语义 | **D6 才讲**，今天跳过 |
| RRF | 倒数排名融合 | 把两路检索结果合并成一个排名的方法 | **D6 才讲**，今天跳过 |
| cross-encoder | 交叉编码器 / 精排模型 | 把"问题"和"文档"拼在一起过一遍模型，所以能看懂"不"字 | **D6 才讲**，今天跳过 |
| RAGAS | （一个评测工具的名字） | 给 RAG 效果打分的工具 | **D6 才讲**，今天跳过 |

### 这些词在代码里到底落在哪一行

别只看定义。打开 `project/day5/先跑这个-五步看得见.py`，每个名词都对应一段看得见的代码：

| 名词 | 在那份脚本里的位置 |
| --- | --- |
| chunk | 第 ① 步的 `chunks` 列表（就 3 句话） |
| Embedding | `embed()` 函数 —— 一个 `httpx.post` 请求，返回一串数组 |
| 余弦相似度 | 第 ④ 步的 `sum(a * b for a, b in zip(q_vec, v))`，**就这一行** |
| top-k / Retriever | 第 ⑤ 步的 `max(range(...), key=lambda i: scores[i])` |
| Vector Store（FAISS） | **本脚本没有用 FAISS**，第 ④⑤ 步那个 for 循环就是它在干的事 |
| prompt 拼装 + 生成 | 第 ⑥ 步：把 `chunks[best]` 拼进字符串，发给 chat 接口 |

---

## 0. 今天的日程（一日模板 v2）

| 时间 | 内容 | 备注 |
| --- | --- | --- |
| 09:30-12:00 | 块① 概念 + `embed_demo.py` 跑通 | 手机放另一个房间 |
| 12:00-14:00 | 午饭 + 摆烂（奖励，别愧疚） | |
| 14:00-17:00 | 块② 切分 → 检索 → ⭐`mini_rag.py` | 今天的主战场 |
| 17:00-19:00 | 晚饭 + 自由 | |
| 19:00-20:00 | 芭杆 | 保留，别砍 |
| 20:00-20:30 | 投递 3-5 家 | |
| 21:50-22:30 | 模拟面试（定时任务自动开考） | |
| 22:30-23:00 | `git commit` + 写 1 个明天的问题 + 关机 | |

**已经装好、不用你再折腾的**：`faiss-cpu 1.15.1`、`numpy 2.5.4`、`langchain-text-splitters`（都装进了 `project/venv`）；`day5/.env` 已从 day4 复制；`docs/` 里放了 3 篇练习文档（产品手册 / 报销制度 / 值班手册）。

---

## 1. 上午块①（2.5h）：概念

### 1️⃣ 为什么需要 RAG（30 min）

LLM 有三个死穴：**知识有截止日期**、**不知道你的私有数据**、**不懂的时候会一本正经编（幻觉）**。三种补法：

| 方案 | 做法 | 代价 | 什么时候用 |
| --- | --- | --- | --- |
| 塞进 prompt（长上下文） | 把资料全文拼进 prompt | 每次请求都烧 token；几十万字塞不下；改了资料要重拼 | 资料少（几页）、一次问答 |
| 微调 Fine-tune | 用私有数据继续训练 | 贵、慢、资料一更新就得重训、还可能"背错" | 固化说话风格 / 输出格式 |
| **RAG** | 先检索相关片段，再让模型基于片段回答 | 要建索引、要工程化（切分/召回/重排/评测） | **知识型问答、企业知识库、客服** ← 你的场景 |

> **一句话面试答法**：RAG = 检索增强生成。把外部知识先向量化存进索引，用户提问时先检索出最相关的几个片段，再把「片段 + 问题」一起交给模型生成。它解决的是模型「不知道你的数据」和「知识过期」，而且**资料更新只重建索引，不用重训模型**——这是它比微调便宜的根本原因。

### 2️⃣ 五步流水线（30 min）

```text
【离线建库，一次】                          【在线查询，每次提问】
① Load   读文件 → Document(文本+来源)       ⑤ Retrieve  query → 向量 → top-k 片段（最像的前 k 条）
② Split  长文 → chunk（200~800 字，带 overlap）
③ Embed  chunk → 向量（1536 维）      ──→   ⑥ Generate  片段+问题 → prompt → 模型 → 答案
④ Store  向量塞进 FAISS 索引                   （再加一步 Rerank 就是明天的 D6）
```

**关键认知**：②③④ 是**离线**做的（慢一点没关系，一次就好）；⑤⑥ 是**在线**的（决定用户等多久）。面试问"RAG 慢在哪"，答案永远在**在线这一段**：一次 query embedding + 一次向量检索 + 一次 LLM 生成。

### 3️⃣ 六个核心名词（先自己填，再看答案）⭐

| 名词 | 一句话 | 对应你已经会的 | 面试追问 |
| --- | --- | --- | --- |
| Document / Loader | | 相当于 D1 的 user 输入，只是来源从"用户打字"换成"文件/网页" | 为什么 metadata 重要？ |
| Chunk | | 相当于 D1 `messages` 里的一条消息，只是内容是知识片段 | chunk 太大 / 太小各有什么代价？ |
| TextSplitter | | 新东西，没有对应 | 为什么要 overlap？ |
| Embedding | | 相当于 D3 的 model 对象——同样吃文本，但吐的不是文字是数组 | 怎么选 embedding 模型？ |
| Vector Store（FAISS） | | 相当于 D1 的 `DISPATCH` 字典，只是 key 从函数名变成了向量 | FAISS 和向量数据库有什么区别？ |
| Retriever | | 相当于 D4 的条件边——它决定"接下来给模型看什么" | top-k 怎么定？ |

#### 对答案（每题都是面试可用的说法）

**Document / Loader**：Document = `{page_content, metadata}`。metadata 是**答案可信度的来源**——用户问"报销标准"，你要能说"出自《差旅与费用报销制度》第三节"，也要能按来源过滤（只查某个部门的文档）。没有 metadata 的 RAG，答对了也没人敢信。

**Chunk**：检索的**最小单位**。不是越小越好：太小 → 一句话被切碎，缺上下文，"600 元"脱离了"一线城市住宿上限"就是废信息；太大 → 一段里混了 5 个主题，向量被平均掉，语义被稀释，召回反而不准，还白占 prompt token。**200~800 字是常见甜点**，中文按**字符**算（不是英文的 token 经验，一个字差不多 1~1.5 token）。

**TextSplitter**：按**分隔符优先级递归**切——先按 `\n\n`（段落），段落还太长再按 `\n`、再按句号/问号，最后才硬切。相邻块保留 **overlap**（10%~20%），为的是**防止关键句正好跨在切割边界上、两半都不完整**。代价是同一段内容被 embedding 多次，白烧 token 和存储。

**Embedding**：把文本映射成向量，**语义相近 → 向量夹角小**。三个必须知道的点：
- **同一个知识库的文档和查询必须用同一个模型**，混用两个模型 = 向量空间对不上，检索直接失效（这是新人最常踩的坑）。
- 很多模型要区分 `type=query` / `type=db`（**你这个 MiniMax `embo-01` 就是**）——短查询和长文档的编码方式不同，混用会掉召回。
- 中文场景别用 `text-embedding-ada-002` 这种英文优化的模型；中文优先用国产的中文向量模型（`bge-m3`、`bge-large-zh` 都是常见选择），或者你现在这条 `embo-01`（MiniMax 提供的，已经验证可用）。

**Vector Store（FAISS）**：存向量 + 做近邻检索的索引结构（"索引"= 帮你快速找到最像的那几条的东西）。两种检索模式要分清：

- `IndexFlatIP`（内积索引，Flat = 平铺）：**暴力精确搜索**，拿问题和每一条逐一算相似度，100% 准，数据量到百万级才开始慢。**你今天用的就是它。** 名字里的 IP 是 Inner Product（内积）的缩写——因为向量已经归一化，内积就等于余弦相似度。
- `IndexFlatL2`（欧氏距离索引）：同上，只是改用"直线距离"衡量远近。今天不用它，知道有这个兄弟就行。
- `IndexIVFFlat` / HNSW（两种近似索引）：数据上百万条才用的加速结构，先聚类分桶、只搜几个桶，**快很多但可能漏**。这是"召回率 vs 延迟"的权衡。**今天完全不用看这两个词。**
- **``FAISS 是库不是数据库``**：它没有持久化服务、没有 metadata 过滤、没有分布式、没有增删改的事务。Milvus / Qdrant / pgvector 才是"向量数据库"。这句话答出来，面试官会认为你真的用过。

**Retriever**：把 query 变成 top-k 片段的策略（top-k = 排序后取前 k 个）。三个旋钮：`k`（给几块）、`score_threshold`（相似度阈值：低于多少就直接丢掉，宁可不答）、`MMR`（最大边际相关：一种挑法，防止 top-3 全是同一段的重复内容，**今天不用碰**）。**k 不是越大越好**——k 增大召回率上升，但噪声也进 prompt，模型容易被无关片段带跑（这就是"幻觉放大器"）。

### 4️⃣ 五个坑（今天一定会撞上的）

1. **照抄 OpenAI 的 embedding 示例**：你这条接口字段是 `{"model","texts","type"}`，不是 `{"model","input"}`；而且业务错误码在返回体的 `base_resp` 里，HTTP 状态还是 200 —— 不查 `base_resp` 你会以为调用成功了。`embed_demo.py` 里已经处理好。
2. **切分按英文经验给 500 token**：中文得按字符估，先 `chunk_size=200` 起步，跑完看命中效果再调。
3. **overlap 设为 0 图省钱**：关键句被切断，召回直接掉。10%~20% 是工程默认值。
4. **检索到无关内容还硬答**：这才是 RAG 幻觉的真正来源——不是模型坏，是你硬塞了不相干的上下文。**要么加阈值拒答，要么在 system prompt 里明确"资料里没有就说没有"**（今天两样都要做）。
5. **只存文本不存来源**：答对了没法溯源。`chunk` 一定要带 `source`。

### 5️⃣ 手算一遍余弦相似度（20 min，前端类比）

```text
向量 A = [1, 2, 2]   向量 B = [2, 4, 4]   向量 C = [2, 0, 1]

A·B = 1*2 + 2*4 + 2*4 = 18      |A| = 3,  |B| = 6      cos = 18/(3*6) = 1.0   → 完全同向（B 就是 A 放大 2 倍）
A·C = 1*2 + 2*0 + 2*1 = 4       |A| = 3,  |C| = √5≈2.24 cos = 4/(3*2.24) ≈ 0.60
```

**为什么用余弦而不是欧氏距离**：余弦只看**方向**不看**长度**，而"长度"在文本里常常是"这句话有多长"这种无关信息。你已经有 1536 维的向量，本质和 3 维完全一样，只是没法手算了。

> 前端类比：向量 = 一个 1536 长度的 `number[]`，余弦相似度 = 先各自归一化再点乘。**归一化之后，余弦 == 内积** —— 这就是 FAISS 用 `IndexFlatIP`（IP = Inner Product）的原因，也是今天代码里那行 `faiss.normalize_L2` 的意义。

---

## 2. 下午块②（3h）：⭐ 产出 `mini_rag.py`

### Step 0（2 min）装包 —— 已经装好了，跳过

```bash
# 已装进 project/venv，不用再跑；记录下来面试时知道依赖了啥
# pip install faiss-cpu numpy langchain-text-splitters
```

### Step 1（15 min）先跑 `embed_demo.py`，确认通路

```bash
cd D:/agent-learn/project/day5
python embed_demo.py
```

**已实测的预期输出**：维度 1536、模长 1.0，三句相似度大约是

```text
cos(0,1) = 0.8283   「北京的天气怎么样」 vs 「今天北京是晴天，气温 26 度」
cos(0,2) = 0.0652   「北京的天气怎么样」 vs 「差旅住宿费一线城市每晚上限 600 元」
cos(1,2) = 0.0018
```

**看到这组数字你要能说出**：语义相近的 0.83、无关的 0.06 —— 差了一个数量级，**这就是"向量能检索"的物理基础**。顺便记住：真实系统里"相关"和"不相关"的界线通常落在 **0.5~0.7**，不是 0.9。

### Step 2（40 min）手写切分 ⭐

在 `day5/split_test.py` 里自己写（别抄附录，附录是卡住才看的）：

```python
def split_text(text, source, chunk_size=200, overlap=40):
    """按 chunk_size 字切，相邻块重叠 overlap 字，每块带上 source"""
    ...
```

**必须做的实验**（这一步比写对代码更值钱）：`chunk_size` 分别取 `80 / 200 / 600`，各跑一次，把每次切出来的块数和第一块内容打出来，观察：

- `80`：一句话被切断，"专业版每月赠送 500 次"和"AI 扩图额度"分家了 → 检索到了也答不出
- `600`：一块里塞了套餐表 + 超限规则 + 扩图配额三件事，向量被平均 → 问到"扩图配额"可能召回一块大杂烩
- `200`：**刚刚好，一块 ≈ 一节小标题下的内容**

> 这个实验就是面试时回答"chunk_size 怎么定"的底气：**不是拍脑袋，是拿真实语料跑不同参数、看召回质量。** 这句话比背"200-800 字"值钱十倍。

### Step 3（20 min）对照 LangChain 的 `RecursiveCharacterTextSplitter`

```python
from langchain_text_splitters import RecursiveCharacterTextSplitter

splitter = RecursiveCharacterTextSplitter(
    chunk_size=200, chunk_overlap=40,
    separators=["\n\n", "\n", "。", "！", "？", " ", ""],   # 中文标点一定要加
)
chunks = splitter.split_text(text)
```

**和 Step 2 的差别（要能说出来）**：你手写的是**硬切**（不管语义，到 200 就断）；`Recursive` 是**按分隔符优先级递归切**——优先在段落边界断，宁可这块小一点。代价是你没法精确控制长度（块会在 100~200 之间浮动）。**生产中用它，理解用你自己的版本。**

### Step 4（20 min）用 numpy 手算 top-k（不用 FAISS，看原理）

```python
import numpy as np
# 假设已拿到 doc_vecs: (n, 1536)、q_vec: (1536,)
scores = doc_vecs @ q_vec          # 矩阵乘 → 一次算完所有相似度
top_k_ids = np.argsort(-scores)[:3]  # 取最大的 3 个（负号 = 从大到小）
```

**这一步的意义**：RAG 的"检索"在数学上就这么简单——**一次矩阵乘 + 一次排序**。FAISS 只是把这两步做到了极致（SIMD、分桶、量化）。**能说出这句话，比背十个框架名都管用。**

### Step 5（25 min）FAISS 版 ⭐

```python
import faiss
faiss.normalize_L2(vecs)                        # 归一化 → 内积 == 余弦
index = faiss.IndexFlatIP(vecs.shape[1])        # 内积索引（Flat=平铺、IP=内积）；归一化后等于余弦
index.add(vecs)
scores, ids = index.search(q_vec, k=3)          # 一次查 3 个
```

⚠️ 两个坑：
- **`IndexFlatIP` 必须配归一化**，否则内积会被"长向量"刷分（长得像没用，长就赢）。
- **`search` 返回的是 `(相似度数组, 下标数组)`**，`ids` 要拿去查你保存的 `chunks` 列表——FAISS 只存向量，**不存文本**。这句是面试高频："FAISS 里存的是原文吗？"→ 不是，存的是向量和自增 id，原文和 metadata 要你自己用 dict/列表/数据库映射回去。

### Step 6（60 min）⭐ 拼成 `mini_rag.py`

六个函数对应五步，一个不多：`load_docs` → `split_text` → `embed` → `Retriever(建索引+search)` → `answer`。

**验收（三条命令，我已实测过预期结果）**：

```bash
cd D:/agent-learn/project/day5

# ① 正例：答案只在《产品手册》里
python mini_rag.py "专业版每月赠送多少次 AI 扩图额度？"
#   期望：top1 命中 01-云图库Pro产品与定价手册.md（score ≈ 0.80），回答「500 次」

# ② 负例：资料里根本没有
python mini_rag.py "员工生日有几天假？"
#   期望：top1 score 只有 ≈ 0.59，回答「资料中没有相关信息」

# ③ 跨段落：同一份文档里两个地方的信息
python mini_rag.py "P0 故障要求多久内响应，复盘报告几天内交？"
#   期望：top1 score ≈ 0.90，回答「15 分钟响应、72 小时内复盘」
```

**加分（10 min，面试直接能用）**：在 `search` 后面加一个阈值——`if hits[0]["score"] < 0.6: return "资料中没有相关信息"`。对比一下"靠 prompt 兜底"和"靠阈值兜底"的区别：**prompt 是软约束（模型可能不听），阈值是硬约束（代码里就拦住了）**。这一个细节，能撑起"你怎么防 RAG 幻觉"整道题。

---

## 3. 晚上（1h）：自测 + 收尾

### 不看笔记口答（答不上的，回第 1 节补）

1. RAG 五步流水线，哪几步是离线、哪几步是在线？慢在哪一段？
2. 为什么 RAG 比微调便宜？什么场景反而该微调？
3. chunk 太大和太小各有什么代价？overlap 解决什么问题？
4. 同一个知识库的文档和查询，能用两个不同的 embedding 模型吗？为什么？
5. `FAISS 是库不是数据库` —— 说出三个它没有的能力。
6. `IndexFlatIP` 为什么必须归一化？`IndexFlatL2` 需要吗？
7. `FAISS 的 search 返回什么？原文存在哪？`
8. RAG 的幻觉主要来自哪一环？（提示：不是模型坏）你怎么防？

### 收尾三件套

- [ ] `git add day5 && git commit -m "Day5: mini RAG pipeline (split + embed + faiss retrieve)"`
- [ ] 笔记：把今天六个名词的答案 + chunk_size 实验结论写进 Obsidian `Agent开发/day5-RAG.md`
- [ ] 带着问题睡：**D6 要讲 Rerank 和混合检索——现在这套纯向量检索，最可能在什么查询上翻车？**（提示：精确关键词、型号、人名、缩写）

---

## 附录 A · 自测答案要点

1. ①Load ②Split ③Embed ④Store 离线；⑤Retrieve ⑥Generate 在线。慢在在线段：query embedding + 检索 + LLM 生成（生成最慢）。
2. RAG 资料更新只重建索引（分钟级、几乎不要钱）；微调要重训（小时级、要 GPU、要标注数据）。反过来，**风格/格式/语气固化**、以及**极短输出要求低延迟**时，微调更合适；两者可以叠加（先微调风格，再 RAG 补知识）。
3. 太小：语义碎片化、缺上下文、召回命中但答不出；太大：语义被平均、召回不准、白占 token。overlap：防止关键句跨边界被切断，代价是重复 embedding。
4. 不能。不同模型的向量空间维度、坐标系都不同，混用等于拿两把不同刻度的尺子量同一根棍子。换模型 = 全库重建索引。
5. FAISS 没有：持久化服务（要自己 save/load index）、metadata 过滤（要自己按 id 回查再筛）、分布式与副本、事务与增删改一致性。它是"算法库"。
6. `IndexFlatIP` 算内积，向量越长内积越大，不归一化就是"谁长谁赢"；归一化后内积 == 余弦，才只比方向。`IndexFlatL2` 算欧氏距离，对长度差异本身就在意，不需要额外归一化（但归一化后往往更稳）。
7. 返回 `(similarities: (n,k) float, indices: (n,k) int64)`——只有分数和**自增下标**，没有原文。原文/来源要你自己用 `id → chunk` 的映射表（或向量数据库的 payload）存回来。
8. 来自**检索环节**：塞进了不相关或误导性片段，模型只能硬着头皮根据它编。防法三层：① 阈值拒答（硬约束）② prompt 明确"资料没有就说没有"（软约束）③ D6 的 Rerank 提高 top-k 精度。

---

## 附录 B · 参考实现（**先自己写，卡住再看**，已实测全通）

```python
# mini_rag.py
import os, sys, glob
import httpx, numpy as np, faiss
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

load_dotenv()
API_KEY, BASE_URL, MODEL_NAME = os.getenv("API_1"), os.getenv("BASE_URL"), os.getenv("MODEL_NAME")
EMBED_MODEL = os.getenv("EMBED_MODEL", "embo-01")
DOC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs")

def load_docs(doc_dir=DOC_DIR):
    docs = []
    for path in sorted(glob.glob(os.path.join(doc_dir, "*.md"))):
        with open(path, encoding="utf-8") as f:
            docs.append({"source": os.path.basename(path), "text": f.read()})
    return docs

def split_text(text, source, chunk_size=200, overlap=40):
    chunks, start = [], 0
    while start < len(text):
        piece = text[start:start + chunk_size]
        if piece.strip():
            chunks.append({"source": source, "text": piece})
        start += chunk_size - overlap
    return chunks

def embed(texts, type_="db"):
    vectors, BATCH = [], 20
    for i in range(0, len(texts), BATCH):
        resp = httpx.post(f"{BASE_URL}/embeddings",
            headers={"Authorization": f"Bearer {API_KEY}"},
            json={"model": EMBED_MODEL, "texts": texts[i:i+BATCH], "type": type_}, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        if data.get("base_resp", {}).get("status_code") != 0:
            raise RuntimeError(data["base_resp"])
        vectors.extend(data["vectors"])
    arr = np.array(vectors, dtype="float32")
    faiss.normalize_L2(arr)
    return arr

class Retriever:
    def __init__(self, chunks):
        self.chunks = chunks
        self.vectors = embed([c["text"] for c in chunks], type_="db")
        self.index = faiss.IndexFlatIP(self.vectors.shape[1])
        self.index.add(self.vectors)
    def search(self, query, k=3):
        q = embed([query], type_="query")
        scores, ids = self.index.search(q, k)
        return [{**self.chunks[i], "score": float(s)} for s, i in zip(scores[0], ids[0])]

def answer(question, hits):
    context = "\n\n".join(f"[来源：{h['source']}]\n{h['text']}" for h in hits)
    llm = ChatOpenAI(model=MODEL_NAME, api_key=API_KEY, base_url=BASE_URL, temperature=0)
    return llm.invoke([
        SystemMessage(content="你是一个只基于给定资料回答问题的助手。如果资料里没有答案，直接回答「资料中没有相关信息」，绝对不要编造。"),
        HumanMessage(content=f"资料：\n{context}\n\n问题：{question}"),
    ]).content

if __name__ == "__main__":
    question = sys.argv[1] if len(sys.argv) > 1 else "专业版每月赠送多少次 AI 扩图额度？"
    chunks = []
    for d in load_docs():
        chunks.extend(split_text(d["text"], d["source"]))
    print(f"[load] {len(load_docs())} 篇 → [split] {len(chunks)} chunk")
    r = Retriever(chunks)
    hits = r.search(question, k=3)
    for i, h in enumerate(hits, 1):
        print(f"  top{i} score={h['score']:.4f} {h['source']} «{h['text'][:50]}...»")
    print("\n回答：", answer(question, hits))
```

---

## 资源（只看这个，别扩散）

- **`datawhalechina/all-in-rag`** 的第 1~2 章（RAG 基础 + 数据处理与切分）—— 只看到"向量检索"为止，别翻后面
- FAISS 官方 wiki 的 `Getting started`（只看 `IndexFlat` 那一段，别管 `IndexIVF`，今天用不上）
- 你 D3 的 `day3-langchain入门.md`：`model` 那节讲的"适配器模式"，和 embedding 模型是同一套设计思路

## 明天的伏笔（D6）

今天这套纯向量检索有四个必翻车的场景，明天逐个补：

| 翻车场景 | 为什么会翻 | 明天补什么 |
| --- | --- | --- |
| 查"P0"、"AES-256"这种精确串 | 向量擅长语义，不擅长字面精确匹配 | **混合检索**：关键词检索（BM25，只数词出现几次，不懂语义）+ 向量检索，两路结果用倒数排名融合（RRF）合并 |
| 问题很刁钻，top-10 里只有 1 条有用 | 向量检索只有粗排，精度不够 | **重排（Rerank）**：用交叉编码器（cross-encoder，把问题和文档拼一起过一遍模型）再排一次 |
| "效果到底好不好"说不清 | 没有量化指标 | **评测（RAGAS 工具）**：算四个分——答案有没有资料支撑、答案切不切题、检索准不准、该检索的有没有漏 |
| 多跳问题（"P0 的响应时限和复盘时限"要跨两段） | 一次检索只拿一次上下文 | **Agentic RAG**（让 Agent 自己决定检索几次）：改写问题 → 检索 → 判断资料够不够 → 不够再检索 |

**这四个词就是 D9 项目 1 的骨架。今天写的 `Retriever` 类，明天会被塞进 LangGraph 的节点里。**
