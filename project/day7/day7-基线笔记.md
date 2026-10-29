# day7 · 工具化 + 20 题评测集（基线）

> 2026-10-29　｜　对应代码：`D:/agent-learn/project/day7/`
> 今天不写 Agent 主循环，只造零件：把 day6 的检索内核包成**能被 import 的 3 个工具**，再建 **20 题评测集**跑出基线。

---

| 名词                                       | 一句话答案                                                           |
| ---------------------------------------- | --------------------------------------------------------------- |
| **模块**（module）                           | 一个 `.py` 文件。文件名叫什么，模块就叫什么                                       |
| **import**                               | ==执行对方文件 + 把里面的名字打包成**一个对象**给你==。等价于前端 `import x from './x.js'` |
| **`if __name__ == "__main__"`**          | 只有「我被直接运行」时才执行下面那段；被 import 时不执行。用来把「自检」和「被别人用」分开               |
| **副作用**（side effect）                     | import 一个模块时，它顶层代码会真的跑一遍。顶层写了联网/建索引，别人一 import 就跟着遭殃            |
| **懒加载**（lazy loading）                    | 先存 `None`，第一次真要用时才建，之后复用。好处：import 变快、不联网、不报错                   |
| **工具描述**（tool description）               | 写在 schema 里给模型看的那段话，==它就是提示词==：说清什么时候用、含什么、失败怎么办                |
| **参数表**（parameters / JSON Schema）        | 告诉模型这个工具要填哪些字段、什么类型、哪些必填                                        |
| **评测集**（eval set）/ **标准答案**（gold answer） | 一批「问题 + 人工核对过的答案 + 答案该来自哪份文件」。没有它，你只能说「感觉变好了」                   |
| **基线**（baseline）                         | 改造之前先跑一遍分数，之后任何改动都跟它比。==没有基线的优化 = 自欺欺人==                        |
| **拒答阈值**（refusal threshold）              | ==一条分数线==。检索结果里最高的相似度低于它，就判「库里没有」，直接回「资料中没有相关信息」，==连模型都不调用==。作用是防编造 + 省一次调用 |
| **跳数**（hop）                              | 要查几次才够。==1 跳 = 一次检索够用；2 跳 = 得换 query 再查==（这是明天「重检」的触发条件）        |

---

## 一、今天为什么非得拆文件

day6 的主产出叫 `D6-混合检索和rerank.py`，检索内核已经跑通，明天 `agent.py` 想直接用它：

```python
from D6-混合检索和rerank import Retriever   # ← 这行代码本身就不合法
```
Python 读到 `-` 会当成减号，整行语法崩掉。

纠正一个容易记错的点：==中文名其实可以 import==（Python 3 支持 Unicode 名字）。真正不合法的是这三种字符：

| 字符 | 会怎样 |
| --- | --- |
| `-` 连字符 | 被当成减号 |
| `.` 点号 | 被当成「子模块」的层级分隔 |
| 空格 | 直接语法错误 |

所以主产出定名 `tools.py`（全英文小写 + 下划线），而不是 `D7-tools.py`。
**规矩**：要给别人 import 的模块，名字必须合法；`D{天数}-xxx` 是给「自己单独跑的脚本」用的。

### 拆完之后：代码写在哪一层

拆成 `tools.py` 只是第一步。**同一行代码写在哪个缩进层级，决定了它什么时候跑**：

| 写在哪 | 什么时候执行 |
| --- | --- |
| **顶层**（缩进 0 格） | 文件被 import 的瞬间，按顺序执行 |
| **函数体内**（缩进 ≥ 4 格） | 只有函数被调用时才执行 |

前端对照：ES module 的顶层代码也是「被 import 时执行一次」——你在 `utils.js` 顶层写 `console.log`，任何页面一 import 它就打印。Python 一模一样，只是不写 `export`。

#### 特例：`def` 写在顶层，为什么函数体不跑

`def build():` 这一行**确实执行了**，但它执行的活是 ==「造一个函数对象、贴上 build 这个标签」==，函数体一行没跑。

```python
print("A 顶层第 1 句")
def build():
    print("B 函数体里")        # ← 缩进：没跑
print("C 顶层第 2 句")
build()                        # ← 顶层：这行执行了，才进去跑 B
print("D 顶层第 3 句")
```

实际输出：

```
A 顶层第 1 句
C 顶层第 2 句          ← B 没出现
B 函数体里（缩进 4 格）
D 顶层第 3 句
```

==B 排在 C 后面==，这就证明 `def` 那行没执行函数体。所以准确的说法是「顶层的**语句**会执行」，**不是**「顶层的**函数**会执行」。

#### D6 为什么 import 不卡

```python
def main():                      # 顶层执行：造出 main，函数体没跑
    r = Retriever(chunks)        # 缩进：没跑
    ...

if __name__ == "__main__":       # 顶层执行：判断真假
    main()                       # 别人 import 时条件为假，不进来
```

别人 `import tools` → `main()` 没被调用 → `Retriever` 从没被 new → ==零网络请求，瞬间返回==。

> `Retriever(chunks)` ≈ 前端的 `new Retriever(chunks)`，Python 只是不写 `new` 这个字。

#### 坑：写 `search_kb` 时你一定会想把 retriever 提到顶层

三种写法对比：

| 写法 | import 时代价 | 第一次检索代价 |
| --- | --- | --- |
| 顶层 `_r = Retriever(chunks)` | ==建索引==（几秒~几十秒，2 次 HTTP） | 0 |
| 每次调用都重新 new | 0 | 每次都重建，最慢 |
| **懒加载** | **0** | 只建一次，之后复用 ✅ |

顶层 new 的三个后果：任何文件 `import tools` 都要等建索引；网络一挂 import 直接报错（`agent.py` 连启动都启动不了）；跑个单元测试也白烧 2 次 API。

![[day7-基线笔记-1793273159743.webp|450]]

懒加载写法（ `tools.py` 照抄这段）：
```python
_RETRIEVER = None                    # 顶层只有这一句，import 时零成本

def get_retriever():
    global _RETRIEVER                # 声明：我要改外面那个全局变量
    if _RETRIEVER is None:           # 第一次进来是 None
        _RETRIEVER = Retriever(_build_chunks())
    return _RETRIEVER
```

**`global _RETRIEVER` 这行不能省**

函数里一旦出现 `_RETRIEVER = ...` 这种赋值，Python 默认把它当成「新建一个局部变量」，模块顶层那个 `None` 纹丝不动。写 `global` 才是「我要改外面那个」。

实测对比：

| 写法 | 函数返回 | 模块里 `_RETRIEVER` |
| --- | --- | --- |
| 没写 `global` | 对象（看起来正常） | 还是 `None` ← ==每次调用都重建，而且不报错== |
| 写了 `global` | 对象 | 变成那个对象 ✅ |

前端对照：`let _retriever = null` 写在模块顶层，函数里直接 `_retriever = x` 就是改外层，**JS 不需要任何声明**。Python 必须专门写一句 `global`。

危害在于**它不报错**：`search_kb` 每问一句都会重建一遍索引（每次等 20 秒），现象只是「有点慢」，很难想到是这行。

`-> "Retriever"` 那个引号：因为 `Retriever` 类定义在这个函数**下面**，写这行时 Python 还不认识这个名字。加引号 = 「先记着这个名字，用到时再解析」。
![[day7-基线笔记-1793283694126.webp|525]]

**数据快照**：

| 时刻 | `_RETRIEVER` | 发生了什么 |
| --- | --- | --- |
| `import tools` 之后 | `None` | 什么都没建，零请求 |
| 第一次 `get_retriever()` | `None` → `<Retriever>` | 读 4 篇 → 切 22 块 → 2 次 embedding → 建 FAISS 索引 |
| 第二次以后 | 还是那个对象，不变 | 直接返回，不再建 |

实测：`import 答案_key_tools` 用了 **0.34 秒**——这是 import faiss / numpy 的钱，不是建索引的钱，此时 `_RETRIEVER` 仍是 `None`。

---

## 二、三个产出

| 文件 | 是什么 | 状态 |
| --- | --- | --- |
| `tools.py` | 检索内核 + 3 个工具 + TOOLS 说明书 + DISPATCH | ✅ 三个工具自检全过 |
| `eval_set.json` | 12 题，5 单跳 / 2 精确型号 / 2 多跳计算 / 3 应拒答 | ✅ |
| `day7-基线笔记.md` | 就是本笔记（放在 Obsidian 的 Agent开发 文件夹） | ✅ |

三个工具：

| 工具 | 干什么 | 返回 |
| --- | --- | --- |
| `search_kb(query, top_k)` | 混合检索 + rerank，返回片段 | `{found, hits:[{doc_id, source, text, score}], message}` |
| `calc(expression)` | 算纯数字表达式 | `{ok, result}` / `{ok, error}` |
| `get_doc_meta(doc_id)` | 查某块来自哪个文件、什么时候更新 | `{ok, source, updated, seq_in_doc, text}` |

**工具设计的四条规矩**（面试问「工具怎么设计」就答这个）：

1. **参数少而明确**，1-2 个 —— 参数越多模型填错越多
2. 返回值是「小 **JSON**」，不是 Python 对象 —— 模型只能读文本
3. 内部异常不往外抛，转成 `{"ok": False, "error": ...}` —— 抛异常会打断整个循环
4. 一定带「来源」—— 不带来源，模型编了你都发现不了

### 2.1 文件开头：路径与环境（先解决「从哪跑都能找到文件」）

```python
import os, re, math, glob, datetime
import httpx
import numpy as np
import faiss
from dotenv import load_dotenv

_HERE = os.path.dirname(os.path.abspath(__file__))
_ENV_LOCAL = os.path.join(_HERE, ".env")
_ENV_FALLBACK = os.path.join(_HERE, "..", "day5", ".env")
load_dotenv(dotenv_path=_ENV_LOCAL if os.path.exists(_ENV_LOCAL) else _ENV_FALLBACK)

API_KEY = os.getenv("API_1")
DOC_DIR = os.path.join(_HERE, "..", "day5", "docs")
```

**这段在干什么**：算出「我这个文件住在哪」，再根据它拼出 `.env` 和 `docs` 的绝对路径。这样不管你在 `day7` 目录敲命令、还是在 `D:\` 敲，都能找对文件。

**Python 难点 / 陌生点**

| 写法 | 什么意思 | JS 对照 |
| --- | --- | --- |
| `__file__` | 当前文件的路径（可能带相对部分） | `__filename` |
| `os.path.abspath()` | 转成绝对路径 | `path.resolve()` |
| `os.path.dirname()` | 取所在**目录** | `path.dirname()` |
| 三个套起来 | 当前文件所在目录 | `__dirname` |
| `os.path.join(a, b)` | 拼路径，自动处理斜杠 | `path.join()` |
| `A if 条件 else B` | 条件表达式 | `条件 ? A : B` ← ==**顺序是反的**== |

⚠️ **最容易写错的一个**：Python 的三元是 `值A if 条件 else 值B`，JS 是 `条件 ? 值A : 值B`。**条件和值的位置调了个头。**

```python
x = "有" if exists else "没有"      # Python
```
```js
let x = exists ? "有" : "没有";     // JS
```

⚠️ **不能写死相对路径**：`open("docs/xx.md")` 里的 `docs` 是相对**你敲命令时所在的目录**，不是相对脚本文件。所以必须用 `_HERE` 拼。

### 2.2 读文档：`load_docs()`

```python
def load_docs(doc_dir: str = DOC_DIR) -> list:
    docs = []
    for path in sorted(glob.glob(os.path.join(doc_dir, "*.md"))):
        with open(path, encoding="utf-8") as f:
            docs.append({"source": os.path.basename(path), "text": f.read()})
    return docs
```

**这段在干什么**：把 4 篇 md 全读进来，变成 `[{"source": 文件名, "text": 全文}, ...]`。

**Python 难点 / 陌生点**

| 写法 | 什么意思 | 备注 |
| --- | --- | --- |
| `doc_dir: str = DOC_DIR` | 参数类型标注 + 默认值 | 只是**提示**，Python **不检查**。传错类型照样跑 |
| `-> list` | 返回值标注 | 同上，不影响运行 |
| `glob.glob("*.md")` | 用通配符找文件，返回路径列表 | ≈ Node 的 `fs.readdirSync` 加过滤 |
| `sorted(...)` | 排序 | **必须有**，见下 |
| `with open(...) as f:` | 离开缩进块自动关文件 | ≈ `try { ... } finally { close() }` |
| `encoding="utf-8"` | 指定编码 | **Windows 默认 GBK**，不写中文会乱码或报错 |
| `os.path.basename()` | 从路径取文件名 | `path.basename()` |

**为什么 `sorted()` 不能省**：`doc_id`（c00、c01…）是按文件顺序编的。不同系统 `glob` 返回的顺序可能不一样，不排序的话同一个 `c03` 在别人机器上可能指向另一篇文档。

### 2.3 切块：`split_text()` + `extend`

```python
def split_text(text, source, chunk_size=200, overlap=40) -> list:
    chunks = []
    start = 0
    while start < len(text):
        piece = text[start : start + chunk_size]
        if piece.strip():
            chunks.append({"source": source, "text": piece})
        start += chunk_size - overlap      # 每次前进 160 字
    return chunks
```

**这段在干什么**：把一篇长文切成 200 字的块，相邻两块重叠 40 字（防止答案正好被切断），每块带上文件名。

**Python 难点 / 陌生点**

- `text[a:b]` 切片：**左闭右开**（含 a 不含 b），和 JS 的 `slice(a, b)` 一样
- `start += chunk_size - overlap` → 每步前进 **160**，所以块与块重叠 40 字
- `if piece.strip():` 空字符串是 **falsy**（JS 也一样），用来跳过纯空白块

⚠️ **`append` 和 `extend` 是今天最容易搞混的一对**：

```python
a = [1, 2]
a.append([3, 4])      # → [1, 2, [3, 4]]     整个列表当一个元素塞进去
b = [1, 2]
b.extend([3, 4])      # → [1, 2, 3, 4]       一个个摊平加进去
```

| Python | JS 对应 | 效果 |
| --- | --- | --- |
| `list.append(x)` | `arr.push(x)` | 塞一个东西 |
| `list.extend(xs)` | `arr.push(...xs)` | 摊平，把里面每个加进来 |

调用处是 `chunks.extend(split_text(...))` —— 因为 `split_text` 返回的是**列表**，要摊平。写成 `append` 就会变成「列表套列表」，后面 `chunks[idx]` 全乱。

### 2.4 调 embedding 接口：`embed()`

```python
def embed(texts: list, type_: str = "db"):
    vectors = []
    BATCH = 20
    for i in range(0, len(texts), BATCH):
        resp = httpx.post(f"{BASE_URL}/embeddings", ...,
                          json={"model": EMBED_MODEL, "texts": texts[i : i + BATCH], "type": type_})
        data = resp.json()
        if data.get("base_resp", {}).get("status_code") != 0:
            raise RuntimeError(data["base_resp"])
        vectors.extend(data["vectors"])
    arr = np.array(vectors, dtype="float32")
    faiss.normalize_L2(arr)
    return arr
```

**这段在干什么**：把一批文本发给 embedding 接口，拿回一堆向量（每段文字一个 1536 维的数组），归一化成单位长度，装进一个二维 numpy 矩阵。

**Python 难点 / 陌生点**

| 写法 | 什么意思 |
| --- | --- |
| `range(0, 22, 20)` | 三参数：起点、终点、**步长** → 得到 `0, 20` 两批 |
| `texts[i : i+BATCH]` | 切片取一批 |
| `data.get("a", {}).get("b")` | **链式 get**：第一个取不到就给 `{}`，第二个才能安全调用 |
| `raise RuntimeError(...)` | 主动抛异常（≈ `throw new Error()`） |
| `np.array(vectors)` | 把 list 转成矩阵，形状 `(块数, 1536)` |
| `faiss.normalize_L2(arr)` | **原地修改**，没有返回值 |

⚠️ **`data["base_resp"]["status_code"]` 会炸**：万一接口没返回 `base_resp` 这个字段，直接取就 `KeyError`。`.get("base_resp", {})` 的意思是「取不到就给个空字典」，这样第二层 `.get` 才不会崩。

⚠️ **`faiss.normalize_L2(arr)` 不返回新数组**，它直接把 `arr` 改了。所以写法是 `faiss.normalize_L2(arr)` 单独一行，**不是** `arr = faiss.normalize_L2(arr)`。

### 2.5 BM25：今天最密集的一节（三个推导式）

```python
def bm25_scores(query, tokens):
    qt = list(set(tokenize(query)))                        # ① 去重
    n = len(tokens)
    lens = {i: len(ts) for i, ts in tokens.items()}         # ② 字典推导式
    avg_len = sum(lens.values()) / n

    idf = {}
    for t in qt:
        df = sum(1 for ts in tokens.values() if t in ts)    # ③ 生成器表达式
        idf[t] = math.log((n - df + 0.5) / (df + 0.5) + 1)
    ...
```

**这段在干什么**：算每个词的稀有度（IDF）。「有几块文档包含这个词」越少，这个词越值钱。

**Python 难点 / 陌生点**（这节四个写法都是新的，一个一个来）

**① `list(set(...))` = 去重**

```python
tokens = ["保", "修", "保"]
set(tokens)        # {'保', '修'}     集合，自动去重
list(set(tokens))  # ['保', '修']     再转回列表
```
同一个词只算一次，否则重复词会被重复加分。

**② 字典推导式 `{k: v for ...}`**

```python
tokens = {0: ["xr", "2000", "保"], 1: ["xr", "三"], 2: ["保"]}

lens = {i: len(ts) for i, ts in tokens.items()}
# → {0: 3, 1: 2, 2: 1}
```

它就是下面这三行的缩写：

```python
lens = {}
for i, ts in tokens.items():
    lens[i] = len(ts)
```

`.items()` 一次给你「键 + 值」两样，相当于 JS 的 `Object.entries()`。

JS 对照：`Object.fromEntries(Object.entries(tokens).map(([i, ts]) => [i, ts.length]))` —— 所以 Python 这个写法其实更省事。

**③ 生成器表达式 `sum(1 for ... if ...)`**

```python
t = "保"
sum(1 for ts in tokens.values() if t in ts)
```
人肉跑一遍（`tokens.values()` 是三个列表）：

| 轮到哪块 | 这个词在里面吗 | 出 1 还是 0 |
| --- | --- | --- |
| `["xr","2000","保"]` | 有 | 1 |
| `["xr","三"]` | 没有 | 0 |
| `["保"]` | 有 | 1 |
| **合计** | | **2** |

所以 `df = 2`：3 块文档里有 2 块包含「保」。

它等价于：

```python
count = 0
for ts in tokens.values():
    if t in ts:
        count += 1
```

JS 对照：`[...tokens.values()].filter(ts => ts.includes(t)).length`

⚠️ 注意是 `sum(1 for ...)` 不是 `sum(...)`。每满足一次就出一个 `1`，最后加起来。**中间没有方括号**，所以它不生成列表，是一边算一边累加（省内存）。

**④ `sum(lens.values()) / n`**

`lens.values()` 给的是 `{0:3,1:2,2:1}` 里的 `3,2,1`，加起来除以块数 = 平均块长。

### 2.6 RRF 融合：集合的 `|` 和 `next()`

```python
def rrf_fuse(vec_rank, bm_rank, k=60):
    vec_pos = {idx: pos for pos, idx in enumerate(vec_rank, start=1)}
    fallback_v = len(vec_rank) + 1
    fused = []
    for idx in set(vec_rank) | set(bm_rank):        # ← 集合并集
        score = 1 / (k + vec_pos.get(idx, fallback_v)) + 1 / (k + bm_pos.get(idx, fallback_b))
        fused.append((idx, score))
    fused.sort(key=lambda x: x[1], reverse=True)    # ← lambda
    return fused
```

**这段在干什么**：把两路检索的「名次」合成一个分。两路的块可能不一样（向量召回 A、BM25 召回 B），所以要取**并集**再各自算分。

**难写点**

**① `set(a) | set(b)` 是并集**

```python
set([1, 2]) | set([2, 3])   # {1, 2, 3}   并集（都要）
set([1, 2]) & set([2, 3])   # {2}         交集（都要有）
set([1, 2]) - set([2, 3])   # {1}         差集（只在左边）
```

这里要并集：只在向量路出现的块、只在 BM25 路出现的块，都要参与算分，不能丢。

**② `lambda x: x[1]` 是「临时小函数」**

```python
pairs = [(5, 0.03), (3, 0.09)]
sorted(pairs, key=lambda x: x[1], reverse=True)
# → [(3, 0.09), (5, 0.03)]     按每个元组的第 2 项从大到小排
```

`lambda x: x[1]` 等价于：

```python
def 取第二项(x):
    return x[1]
```

JS 对照：`pairs.sort((a, b) => b[1] - a[1])`

**③ `enumerate(x, start=1)`**：边遍历边给序号，`start=1` 表示从 1 数（名次不能从 0 开始）。

**④ `next(s for i, s in fused if i == idx)`**：从列表里找**第一个**满足条件的值。

```python
fused = [(5, 0.031), (3, 0.028)]
next(s for i, s in fused if i == 3)   # → 0.028
```
`next()` 是取生成器的第一个结果。这里也可以写成 `dict(fused)[idx]`，那个更好读。

### 2.7 `Retriever` 类：`self` 和字典解包

```python
class Retriever:
    def __init__(self, chunks: list):
        self.chunks = chunks
        self.vectors = embed([c["text"] for c in chunks], type_="db")
        self.index = faiss.IndexFlatIP(self.vectors.shape[1])
        self.index.add(self.vectors)

    def search(self, query, k=3):
        ids, scores = self._search_ids(query, k)
        return [{**self.chunks[i], "score": s} for i, s in zip(ids, scores)]
```

**这段在干什么**：造一个「检索器」对象。`__init__` 时把向量全建好索引；之后每次 `search` 只编一个问题向量去查。

**Python 难点 / 陌生点**

| 写法 | 什么意思 | JS 对照 |
| --- | --- | --- |
| `class X:` + `def __init__(self, ...)` | 构造函数 | `class X { constructor() {} }` |
| `self` | 当前对象 | `this`，但**每个方法都要显式写在第一个参数** |
| `self.chunks = chunks` | 存成对象属性 | `this.chunks = chunks` |
| `{**d, "k": v}` | **字典解包合并** | `{...d, k: v}` |
| `zip(a, b)` | 拉链，两两配对 | 无直接对应，≈ `a.map((x,i) => [x, b[i]])` |

**字典解包数据快照**：

```python
d = {"source": "04-硬件.md", "text": "..."}
{**d, "score": 0.42}
# → {"source": "04-硬件.md", "text": "...", "score": 0.42}
```
**同名键会被后面覆盖**：

```python
{"a": 1, "b": 2}  →  {**那个, "b": 99}  →  {"a": 1, "b": 99}
```

**`zip` 数据快照**：

```python
ids    = [17, 18, 20]
scores = [0.487, 0.414, 0.895]
list(zip(ids, scores))
# → [(17, 0.487), (18, 0.414), (20, 0.895)]
```

`for i, s in zip(ids, scores)` 就是「同时轮着取两个列表的同一位置」。

### 2.8 懒加载 `get_retriever()`

见本章第一节「坑：写 `search_kb` 时你一定会想把 retriever 提到顶层」——那里有完整代码、`global` 的作用、以及三种写法的代价对比。**这节不重复。**

### 2.9 三个工具：只讲前面没讲的三处

**① `search_kb` 里的夹逼**

```python
top_k = max(1, min(int(top_k), 5))
```
从里往外读：`int(top_k)` 先转整数（模型可能传字符串 `"3"`）→ `min(..., 5)` 封顶 5 → `max(1, ...)` 保底 1。**不管模型传 0 还是 100，最后都在 1~5 之间。**

**② `calc` 里的 `eval` 沙箱**

```python
eval(expr, {"__builtins__": {}}, {})
```
`eval` 的第二个参数是「全局命名空间」。塞一个空字典进去，等于**把 `__import__`、`open`、`print` 这些内置函数全禁了** —— 否则别人传一句 `__import__('os').system('...')` 就能执行任意命令。

再配上前面的白名单（只允许数字和 `+-*/(). %`），双保险。

**③ `get_doc_meta` 的「找不到」分支**

```python
for c in chunks:
    if c["doc_id"] == doc_id:
        return {...}          # 找到就立刻返回，后面的循环不再跑
return {"ok": False, "error": ...}   # 循环跑完都没 return，说明没找到
```
`return` 在循环里一旦执行，整个函数就结束了。所以最后那句 `return` 只有「一个都没命中」时才会走到。

### 2.10 `TOOLS` + `DISPATCH`：函数当值存 + `**args`

```python
DISPATCH = {"search_kb": search_kb, "calc": calc, "get_doc_meta": get_doc_meta}

# 模型说「调 search_kb，参数 {"query": "...", "top_k": 5}」之后：
fn = tc["function"]["name"]                      # "search_kb"
args = json.loads(tc["function"]["arguments"])   # {"query": "...", "top_k": 5}
result = DISPATCH[fn](**args)                    # 等于 search_kb(query="...", top_k=5)
```

**两个点**

**① 字典里可以存函数**：Python 里函数是普通对象，能像数字一样被存、被传、被返回。`DISPATCH["calc"]` 拿到的就是那个函数本身。

**② `**args` 把字典摊成关键字参数**

```python
def f(a, b):
    return a + b

args = {"a": 1, "b": 2}
f(**args)    # → 3        等价于 f(a=1, b=2)
f(args)      # → TypeError  把整个字典当成 a 传进去，b 没值
```

JS 对照：`obj.fn(...args)` —— 但 JS 是按位置展开，Python 是**按名字**展开。所以字典的键必须和参数名**一模一样**，否则报错。

### 2.11 自检两个函数

见第六节第 4 条「`_selfcheck_offline()` 在跑什么」——三重验货、`assert` 和 `print` 的区别、为什么分离线/联网。**这节不重复。**

---

## 三、基线（今天最值钱的数字）

> 数字来源：**你自己的 12 题评测集**（`project/day7/eval_set.json`），跑法 `python 跑基线.py`。
> 想拿我给的 20 题参考集做对照，加参数 `--ref`。

| 模式 | HR@3 | MRR | 拒答准确率 | 说明 |
| --- | --- | --- | --- | --- |
| 默认（走 `search_kb`，含阈值 0.6） | ==66.7%==（6/9） | 0.667 | 66.7%（2/3） | 3 道该答被误拒 + 1 道该拒没拒 |
| `--raw`（绕过阈值，只看检索） | ==100%==（9/9） | 1.000 | 不评 | 检索内核其实是满分 |

三个指标是什么：
- **HR@3**（hit rate，命中率）：**top3 里有没有出现**「标准答案所在的那份文件」，有就算命中
- **MRR**（mean reciprocal rank，平均倒数排名）：正确文件排第几名，第 1 名得 1 分、第 2 名 0.5、第 3 名 0.33，再取平均
- **拒答准确率**：该拒的题有没有真的返回 `found=False`

注意一个边界：**这组指标只评「检索有没有==捞到正确文件==」，不评算术和最终答案质量。**
算术靠 `calc` 工具，答案质量要等明天有了 Agent 主循环再评。==这个区分面试会问到==。

---

## 四、两个发现（33.3% 的差距挖出来的）

### 发现① ：拒答阈值 0.6 是拍出来的，它把该答的题也拒了

>**拒答阈值：它是一条分数线**，检索完成后，你手上有若干个片段，每块带有一个相似度分（0~1）。系统只看**最高的那个分数**，并拿它跟这条线比较：

|最高分|系统认为|做什么|
|---|---|---|
|≥ 阈值|库里有内容|把片段交给模型，让它组织答案|
|< 阈值|库里没有|直接回「资料中没有相关信息」，**连模型都不调用**|

你代码里这条线是 `REFUSE_THRESHOLD = 0.6`，day5 定的，一路抄到今天。
![[day7-基线笔记-1793258413326.webp|400]]
它的两个作用：**防止模型编造**（没资料就不让它答）、**节省一次模型调用**。

---

被误拒的 3 题：`Q02`（基础版存储上限）、`Q06`（XR-3000 比 XR-2000 多什么）、`Q08`（专业版年付 8 折）。

看具体分数就明白了：

| 题 | 最高向量分 | 正确文件在 top3 吗 | 结果 |
| --- | --- | --- | --- |
| Q02 基础版存储上限 | 0.3255 | ✅ 在（3 块全是产品手册） | 被 0.6 判成「查不到」 |
| Q06 XR-3000 差异 | 0.3317 | ✅ 在（型号一览块） | 同上 |
| Q08 年付 8 折 | 0.5383 | ✅ 在（价格表块） | 同上 |

**问题不在检索，在阈值。** 0.6 是 D5 拿 3 道题试出来的，题一多就露馅 —— 真实相似度分布是 0.25~0.74，0.6 卡在中间偏上，一刀切掉一堆正确的。

**扫一遍所有候选阈值，长这样**（`看懂拒答阈值.py` 输出的就是这张表）：

| 阈值 | 误杀（该答被拒） | 漏放（该拒被答） | 总错 |
| --- | --- | --- | --- |
| 0.20 | 0 | 3 | 3 |
| **0.25** | **0** | **2** | **2** ← 最不坏 |
| 0.30 | 0 | 2 | 2 |
| 0.35 | 2 | 2 | 4 |
| 0.50 | 2 | 2 | 4 |
| 0.55 | 3 | 2 | 5 |
| **0.60** | **3** | **1** | **4** ← 现在用的这条 |
| 0.75 | 4 | 0 | 4 |
| 0.80 | 6 | 0 | 6 |

两个结论：

1. 0.6 一共判错 **4 题**（3 道该答被误拒 + 1 道该拒没拒住 = Q11）
2. 就算换成最优的 0.25，仍然错 **2 题** —— ==没有一条线能让错变成 0==

第二条就是发现②要讲的事。

### 发现② ：语义相似 ≠ 有答案（阈值调多少都救不了）

`Q11`「云图库 Pro 支持导出 PSD 格式吗」—— 语料里**根本没写导出格式**，正确答案是拒答。
但这题的 `max_vec = 0.7365`，比很多该答的题都高，因为它跟「产品定位」那段谈的都是产品能力，语义上很近。

这种题：阈值往上调就误杀更多正确题，往下调就放过它。==单靠一个分数无解。==

**这就是「为什么必须是 Agent、不是 RAG 管道」的实证理由** —— 得让模型把片段读完再判断「这里面到底有没有回答这个问题」，而不是拿一个相似度数字赌。

---

## 五、面试怎么说（背这一段）

我用 20 题评测集跑基线，`HR@3` 只有 66.7%。我没直接调阈值，而是**先关掉拒答**再看纯检索 —— 是 100%。所以瓶颈不在检索，在拒答策略是拍脑袋定的。之后我把阈值改成由模型判断资料里到底有没有答案，而不是靠一个分数卡。
>**HR@3**（hit rate，命中率）：**top3 里有没有出现**「标准答案所在的那份文件」，有就算命中

顺带发现另一种情况：问「支持导出 PSD 吗」，相似度 0.74 很高，但语料根本没写导出格式。这种题阈值怎么调都解决不了，只能让模型读片段再判断 —— 这也是我把 RAG 管道升级成 Agent 的直接原因。

---

## 六、今天问过的代码问题（答疑存档）

> 按「先理解整体、再抠细节」排的，可以跳着看。

### 6.1 评测集（`eval_set.json`）到底是干什么的

**它就是检索系统的单元测试用例。** 你写组件时的测试长这样：

```js
test('专业版额度', () => {
  expect(search_kb("专业版赠送多少额度")).toBe("500 次");
});
```

`eval_set.json` 里一条，是同一个东西换成数据写法：

```json
{"question": "专业版每月赠送多少次 AI 扩图额度？",
 "gold_answer": "500 次",
 "gold_sources": ["01-云图库Pro产品与定价手册.md"]}
```

**12 条 = 12 个 test case**，`跑基线.py` 是跑测试的 runner，跑完出通过率。

**为什么不用 `toBe()` 比字符串**：`toBe` 要求一字不差，但检索出来的原文是「专业版每月赠送 500 次 AI 扩图额度，次月 1 日清零」，永远不会精确等于「500 次」。所以退一步，**只比「答案来自的那份文件有没有被检索到」**：

```
问 → 检索返回 top3 三块 → 三块里有 01-产品手册吗？有 = 这道题过
```

这就是 **HR@3**（前 3 条里命中了吗）。MRR 是它的精细版：命中排第 1 得 1 分、第 2 得 0.5、第 3 得 0.33，取平均。

### 6.2 `TOOLS` / `tool_calls` / `DISPATCH` 三者是什么关系

| 东西 | 一句话 | 给谁用 |
| --- | --- | --- |
| `TOOLS` | **菜单**：有哪些工具、参数怎么填 | 发给**模型**看 |
| `tool_calls` | **点单**：模型说「我要调 search_kb，参数是…」 | 模型**返回**给你 |
| `DISPATCH` | **后厨**：按名字查表，真正执行函数 | 你的**程序**用 |

`TOOLS` 三个字段各管一件事：

| 字段 | 作用 | 写坏的后果 |
| --- | --- | --- |
| `name` | 模型靠这个名字点菜 | 和 `DISPATCH` 的键对不上就 `KeyError` |
| `description` | 什么时候该用它，==这就是提示词== | 模型不知道何时用，或每题都去查 |
| `parameters` | 要填哪些参数、什么类型、哪些必填 | 模型漏填必填项 |

**实测一次调用**（问「XR-2000 保修期多久」），模型返回了两个 `tool_calls`：

```json
{"function": {"name": "search_kb", "arguments": "{\"query\":\"XR-2000 保修期 时限\",\"top_k\":5}"}},
{"function": {"name": "search_kb", "arguments": "{\"query\":\"XR系列 硬件保修 售后服务\",\"top_k\":5}"}}
```

三件事值得注意：① 它一次要了两个（并行）② query 是它自己改写的 ③ `top_k=5` 也是它自己填的。

**模型从头到尾没有执行任何东西，它只输出了一段 JSON。** 真正跑代码的是 `DISPATCH[fn](**args)` 这一行 —— 面试问「Function Calling 是谁执行的」，答案在这。

### 6.3 为什么 day1 有 `TOOLS`/`DISPATCH`，day3-6 没有，今天又有了

| 天 | 手写 TOOLS | 手写 DISPATCH | 实际怎么写的 |
| --- | --- | --- | --- |
| D1 / D2 | ✅ | ✅ | 全部手写 |
| D3 | ❌ | ❌ | `create_agent(model, tools=[...])` 一行，连循环都没了 |
| D4 | ❌ | ❌ | `@tool` 自动生成 schema + `tools_by_name` 查表 |
| D5 / D6 | ❌ | ❌ | 没有工具，是 RAG 管道 |
| D7 | ✅ | ✅ | 自己做项目，得自己造 |

**它们不是「某天的知识点」，而是有工具调用的 Agent 的三个必需品：**

| 必需品 | 干什么 | 框架里谁负责 |
| --- | --- | --- |
| schema（`TOOLS`） | 告诉模型有哪些工具 | `@tool` 装饰器 |
| 派发表（`DISPATCH`） | 名字 → 函数 | D4 那个 `tools_by_name`，同一个东西 |
| 循环 | 调模型 → 执行 → 回填 → 再调 | `create_agent` 一句全包 |

**框架把它们封装了，不代表它们不存在。** D4 第 68 行 `tools_by_name = {t.name: t for t in tools}` 就是 `DISPATCH` 的另一种写法。

### 6.4 那个 `_selfcheck_offline()` 在跑什么

**三重验货**：结构对不对、功能对不对、安全对不对。

| 代码 | 验的是 | 不过说明什么 |
| --- | --- | --- |
| `assert len(TOOLS) == 3` | 工具数量 | 少抄一个 |
| `set(names) == set(DISPATCH)` | 菜单和后厨对得上吗 | 模型点了做不出来 |
| `assert f["description"].strip()` | 每个都有描述 | 模型不知道何时用 |
| `calc("(399-99)*12/0.08")` 等于 45000 | 工具算得对 | 白名单太严或逻辑错 |
| `calc("__import__('os')")` 必须失败 | 挡得住危险输入 | `eval` 变成任意代码执行 |

`assert` 和 `print` 检查的区别：

| 方式 | 谁判定 | 结果 |
| --- | --- | --- |
| `print` | 你的眼睛 | 看漏了 = 没检查 |
| `assert` | 机器 | 条件不成立 → 当场停在那行 |

```
AssertionError: 应该正好 3 个工具，现在是 2
↑ 脚本停在这里，后面都不跑了
```

**为什么分 offline / online 两段**：离线不联网、不花钱、1 秒出结果，改一点就能跑；联网要调 embedding、20 秒起、还可能被网络搞挂。混在一起的结果是「改个标点都要等 20 秒」，然后你就不想跑了。

### 6.5 `hits` 是什么

**检索命中的片段列表。** `hit` = 命中一次，`hit rate`（命中率 HR@3）同一个来源。

结构是 **list 装 dict**，真实返回：

```python
r["hits"] = [
    {"doc_id": "c18", "source": "04-硬件保修与售后服务手册.md",
     "score": 0.414, "text": "多机位管理。每台设备出厂时贴有唯一序列号..."},
    ...
]
```

它在代码里出现过三代，**含义没变，变的是字段和外壳**：

| 在哪 | 每条有什么 | 外面包什么 |
| --- | --- | --- |
| D5 `search()` | `source, text, score` | 直接返回 list |
| D6 `hybrid_search()` | `+ bm25, rrf, rerank` | `{hits, max_vec, table}` |
| D7 `search_kb()` | `doc_id, source, text, score` | `{found, hits, message}` |

**一个坑**：`hits[0]["score"]` 不一定是最高分。因为 D6 加了 rerank 之后，`hits` 是按**重排分**排的，不是按向量分排的。实测那条 `hits[0]` 的 score 是 0.414，而第 3 条是 0.895。

所以：**拒答判断不能用 `hits[0]["score"]`，要用单独记着的 `max_vec`。**（D5 时代可以，因为那时只有一路分数、列表就是按分排的。）

### 6.6 精简字段到底省了多少 token

同一道题实测：

| 版本 | 每条字段 | JSON 长度 |
| --- | --- | --- |
| D6 | `source, text, doc_id, seq_in_doc, idx, score, bm25, rrf` | 1156 字符 |
| D7 | `doc_id, source, text, score` | 860 字符 |

**省 296 字符，约 25.6%。** 但看清省的是什么：

| 部分 | 占比 |
| --- | --- |
| `text` 原文 | **70%** |
| 字段名 + 分数 + 来源 | 30% |

==大头是原文，字段名只是小头。== 而且工具结果进了 `messages` 之后**每轮都要重发一遍**，所以省一次等于省 N 次（3 轮就是 3 倍）。

真要省 token 得动这三处：`top_k` 调小（省 1/3）、截断 `text`（有截断答案的风险）、同一文件的相邻块合并（能省 2/3）。

### 6.7 `os.stat()` 和那串时间转换

`os.stat(path)` = **向操作系统问一个文件的档案**。和 Node 的 `fs.statSync()` 几乎一模一样：

| Python | Node | 含义 |
| --- | --- | --- |
| `st.st_size` | `stats.size` | 字节数 |
| `st.st_mtime` | `stats.mtime` | 修改时间 |
| `st.st_mode` | `stats.mode` | 权限位 |

**它给的 mtime 是一个人类看不懂的数**（`1793200504.5992644`，距 1970-01-01 的秒数），所以要三步转换：

```python
datetime.datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d")
└───┬───┘ └───┬────┘ └─────┬─────┘            └────┬────┘
   模块      类         类方法                  实例方法
```

| 步骤 | 值 | 类型 |
| --- | --- | --- |
| 起点 | `1793200504.5992644` | `float` |
| 转完 | `datetime.datetime(2026, 10, 28, 23, 15, 4, 599264)` | datetime 对象 |
| 格式化 | `'2026-10-28'` | `str` |

几个小点：

- `datetime` 写两遍，是因为 `import datetime` 导进来的是**模块**，模块里的**类**也叫 `datetime`（模块.类）
- `strftime` = **str**ing **f**ormat **time**（输出）；`strptime` = **str**ing **p**arse **time**（输入），差一个字母
- `%Y%m%d` ↔ dayjs 的 `YYYY-MM-DD`
- **不能直接 `datetime.datetime(ts)`**，那会把时间戳当年份，报 `TypeError`

**为什么不手写日期**：手写成 `"2026-10-28"`，文件改了日期也不变；从文件系统取，文件一变它跟着变。

### 6.8 `replace("×", "*")` 是往哪个方向换

`replace(旧的, 新的)`，**旧在前**。`"399×12".replace("×", "*")` → `"399*12"`。

**但有一个和 JS 的关键差异**：

```python
"aaa".replace("a", "b")     # Python → 'bbb'  全换了
```
```js
"aaa".replace("a", "b")     // JS → 'baa'     只换第一个
```

Python 的 `replace` 天生换全部，所以能连着写两个 `.replace()` 一次换干净。

整串四步：`str()` 先变字符串 → `strip()` 去首尾空白（≈ `trim()`）→ 换全角 `×` → 换全角 `÷`。目的是**输入归一化**：中文输入法打的 `×` `÷`，`eval` 不认识会报 `SyntaxError`。

### 6.9 `spec_from_file_location` / `module_from_spec` 那三行

**不是「导入模块」，是「分三步把任意一个 .py 文件变成能用的对象」。**

| 步 | 代码 | 干什么 | 这时里面有什么 |
| --- | --- | --- | --- |
| ① | `spec_from_file_location("kt", 路径)` | 开一张**取货单**：从哪取、登记成什么名 | 什么都没有，只是一张说明 |
| ② | `module_from_spec(spec)` | 按单子造一个**空壳** | 只有 `__name__`/`__file__` 这些元信息 |
| ③ | `spec.loader.exec_module(mod)` | **真正执行**那个文件，把东西装进去 | 有函数、常量了 |

**日常完全用不上。** 同目录、名字合法的情况下，`import tools` 一行就够（`import` 内部就是帮你做了这三步）。只有「文件不在搜索路径里」或「名字是运行时才知道」（比如扫插件目录）时才需要绕这一圈。

### 6.10 今天踩的 4 个 bug（报错排查）

| # | 写错的地方 | 报的错 | 根因 |
| --- | --- | --- | --- |
| 1 | `docs = load_dotenv()` | `'bool' object is not iterable` | 应该是 `load_docs()`。`load_dotenv()` 存在、能跑，**返回 True**，于是 `for d in True` 崩了 |
| 2 | `os.path.json(...)` | `AttributeError` | 应该是 `os.path.join(...)`，不调用 `get_doc_meta` 不会触发 |
| 3 | `tok_k = max(...)` | **不报错** | 拼错了，`top_k` 上限保护静默失效 |
| 4 | 缺 `import datetime` | `NameError: name 'datetime' is not defined` | 用了却没导入 |

**三个教训：**

1. **错误信息离根因越远越难查。** bug 1 里 `'bool' object is not iterable` 完全不提 `load_dotenv`，因为报错在**下一行**。如果函数名根本不存在，会立刻 `NameError` 反而好查——正因为 `load_dotenv` 真实存在，才静默返回了 True。

2. **`except Exception as e` 会把堆栈吃掉。** 外面只看到「检索出错: 'bool' object is not iterable」，没有行号。调试时临时加一句：
   ```python
   import traceback
   except Exception as e:
       traceback.print_exc()      # 打印完整堆栈
   ```

3. **不报错的 bug 最危险。** bug 3 程序照跑、结果看着正常，只是保护悄悄失效了。这类只能靠逐行读代码，或者写 `assert` 卡住它。

---

## 七、遗留 / 待补

- [x] `eval_set.json` 建好，12 题（5 单跳 / 2 型号 / 2 多跳 / 3 拒答），答案已对照原文核对
- [x] 用自己的题跑完基线，第三、四节的数字已换成自己的
- [x] `tools.py` 三个工具全通（`python tools.py` 离线+联网自检都过）
- [ ] git 提交（`project/day6`、`project/day7` 还没进版本库）
- [ ] ⚠️ 今天（10.29）实际是 D7，比原计划晚一天 → 10.30 合并 D8+D9，10.31 工程化 + 三题验收，吃掉 11.02 缓冲。**10.31 死线不动**
