### RAG的逻辑
RAG 分两段。**离线**：文档先切分成 chunk，用同一个 embedding 模型把每个 chunk 编码成向量，存进向量索引；**原文和来源单独存一份**，索引里只有向量和 id。

**在线**：用户提问，<u>用同一个模型把 query 编码成向量</u>，在索引里做 top-k <u>近邻检索</u>拿回 k 条 id，**用 id 回表取出原文**，按模板把原文和问题<u>拼成 prompt 交给 LLM 生成</u>。

两个关键点：**向量只用来找，生成用的是原文**；**建库是一次性的，查询每次都跑**。
#### 1. 离线

0. 其实还有一个步骤是 [[day5-RAG#^ab97bd|Document / Loader]]，但是因为理解的一直是写死的chunk版本所以没研究这个。
   >最底下说loader就是把chunks换成真实文本。在[[day5-RAG#^219602|附录]]里面有。[[完整mini-RAG补充]]
   ```python
   
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
   ```
   
   
1. 先切chunks：把文本拆分成合适的块
   这里有两个问题：[[day5-RAG#^ed5bca]] + [[day5-RAG#^b22acc]]
     ①太大or太小
     ②overlap：[[day5-RAG#^1d2256]]
    ```python
    # ============ ① 准备语料 ============
    # 假装这 3 句就是从 3 个文档里切出来的 chunk（真实项目里是 glob 读文件 + 切分）
	chunks = [
	    "专业版每月赠送 500 次 AI 扩图额度",  # chunk 0
	    "一线城市住宿费每晚上限 600 元",  # chunk 1
	    "P0 故障要求 15 分钟内响应",  # chunk 2
	]
    ```
    
2. 用embedd函数将chunks转为向量
   把文本映射成向量，**语义相近代表向量的夹角小**
     ①不能混用模型：[[day5-RAG#^f5a263]] + [[day5-RAG#^e4439d]]
     ②换模型=重建索引
     ```python
     def embed(texts, type_="db"):
	    """文字 → 数组。就这么个事，别被 'embedding' 这个词吓到。
	    是通过大模型的/embedding接口，传入text返回数组， 函数本身并不能实现这个功能
	    """
	    resp = httpx.post(
	        f"{BASE_URL}/embeddings",
	        headers={"Authorization": f"Bearer {API_KEY}"},
	        json={"model": EMBED_MODEL, "texts": texts, "type": type_},
	        timeout=60,
	    )
	    resp.raise_for_status()
	    return resp.json()["vectors"]
	 # ============ 2. 建库：每个 chunk 变成一串数字 ======
	 doc_vecs = embed(chunks, "db") # 把每个 chunk 变成一串数字
	 # ============ 3. 提问：问题也变成数组 ============ 
	 question = "专业版每个月送多少次扩图？"  # 把问题也变成数字
	 q_vec = embed([question], "query")[0]
     ```

一直在bug：
- `/embedding`和`BEARER {key}`都是错的！
![[day5代码补充-1792917050903.webp|450]]

- 入库的材料用 `db`，用户的提问用 `query`
![[day5代码补充-1792917157639.webp|450]]

- `q_vec = embed([question], "query")[0]`拿到的是`[0]`，我写成`q_vec = embed([question], "query")`
	- 在`embedded()`中，接口返回的永远是**一批向量**，哪怕你只传了一条：
	  ```python
		  embedded(["专业版每一个月送多少次扩图"], "query")
		  # 返回 → [[0.012, -0.03, 0.88, ... 1536 个数 ...]]
		  #          ↑ 外面这一层是「批次」
	  ```
	- 所以 `q_vecs` 拿到的是**两层**。下面这行：`s = sum(a * b for a, b in zip(q_vecs, v))`，`zip` 会把「里面那一整个 1536 的列表」和「v 里的第一个数字」配成一对，然后 `a * b` 变成 `list * float` → `TypeError`。
	- 还有一点：是`[question]`。`question` 是字符串，外面套 `[]` 才是列表 → `embedder(texts:string[], type:"db"|"query"):[]`
![[day5代码补充-1792917305712.webp|450]]

补充一个小点：
```ts
interface EmbedResponse {
  vectors: number[][];           // 一批向量，跟传入顺序一一对应
  base_resp: {                   // ← MiniMax 的业务状态在业务状态里，不在 HTTP 里
    status_code: number;         // 0 = 成功，1004 = 登录失败，2013 = 参数错
    status_msg: string;          // "success"
  };
}

/** 一条向量：1536 个数字 */
export type Vector = number[];

/** 向量用途：入库用 db，提问用 query */
export type EmbedType = "db" | "query";

/** embed() 的入参 */
export interface EmbedProps {
  /** 要转向量的文本。是数组，即使只有一条也要包起来 */
  texts: string[];
  /** 不传默认 "db"（入库）；提问时传 "query" */
  type?: EmbedType;
  /** 单批发多少条，默认 20 */
  batchSize?: number;
}

/** embed() 的出参 */
export interface EmbedResult {
  /** 一批向量，与 texts 顺序严格一一对应 */
  vectors: Vector[];
  /** 回显输入，方便做 chunks[i] ↔ vectors[i] 对照 */
  texts: string[];
}

```
#### 2. 在线
>**在线**：用户提问，用同一个模型把 query 编码成向量，在索引里做 top-k 近邻检索拿回 k 条 id，**用 id 回表取出原文**，按模板把原文和问题拼成 prompt 交给 LLM 生成。

```python
# ============ 4. 算相似度：一个问题 vs 3 个 chunk ============
print("因为向量已经归一化，余弦 = 点积 = 对应位相乘再相加")
scores = []
for v in doc_vecs:
    s = sum(a * b for a, b in zip(q_vec, v))  # ← 就这一行
    scores.append(s)
for i, (c, s) in enumerate(zip(chunks, scores))
    print(f"  chunk{i}  score={s:.4f}  {c}")
print("↑ 注意 chunk0 的分数明显高，另外两个趴在地上")

# ============ 5. 排序取 top-candidate：前端一句话 ============
print("\n===== ⑤ 排序取第一名 =====")
best = max(range(len(scores)), key=lambda i: scores[i])
print(f"scores.sort 之后第一名是 chunk{best} → {chunks[best]}")
print("FAISS 干的全部事情，就是把上面 45 步换成一句 index.search(q, k)。没别的魔法。")
```
>`Retriever`就是把以上包装成函数[[day5-RAG#^f4a3bf]]

1. 比较相似度
```python
scores = []
for v in doc_vecs:
    s = sum(a * b for a, b in zip(q_vec, v))  # ← 就这一行
    scores.append(s)
for i, (c, s) in enumerate(zip(chunks, scores)):
    print(f"  chunk{i}  score={s:.4f}  {c}")
```

==第一个for==：算分，**职责：执行数学计算**。它挨个拿用户的==问题向量==，去跟每一个==文档向量==算点积（余弦相似度），算出一个分数塞进 `scores` 列表里。**这是 RAG 的核心步骤。**
`sum(a * b for a, b in zip(q_vec, v))`：
- `zip(q_vec, v)` 按位置配对 → `(q_vec[0], v[0])`、`(q_vec[1], v[1])`…… 一共 1536 个元组。
	- zip表示**像拉链一样一个一个对着配对**，但是如果两个长度不一样，就会丢掉后面超出的部分（zi**p不检查长度**）
	- **这就是“同一个知识库必须用同一个 embedding 模型”背后的原因**。原因在于 `zip` 在不知不觉中截断了数据，并非模型本身有问题。面试时这么答，比背“向量空间不一致”具体得多。 ^7fbf47
	- **点积的定义就是「同一个位置上的数相乘，然后全部加起来」**。`zip` 实现的就是“按位置配对”这个动作。
- `for a, b in ...` 把每个元组**解包**成两个数字：`a = q_vec[i]`、`b = v[i]`
- `a * b` 是**两个数字相乘**，`sum(...)` 把 1536 个乘积全部加起来。

==第二个for==：看分，**职责：相当于前端的 `console.log()`**。它把刚才算出来的分数，和原文对应起来打印到屏幕上。真实项目内不写也不会bug。
`for i, (c, s) in enumerate(zip(chunks, scores))`：
- zip拉链配对
  ```python
    ('专业版每月赠送 500 次 AI 扩图额度', 0.5911)
	('一线城市住宿费每晚上限 600 元', 0.0201)
	('P0 故障要求 15 分钟内响应', 0.0352)
  ```
- enumerate给每一对前面加上序号
  ```python
    0 | ('专业版每月赠送 500 次 AI 扩图额度', 0.5911)
	1 | ('一线城市住宿费每晚上限 600 元', 0.0201)
	2 | ('P0 故障要求 15 分钟内响应', 0.0352)
  ```
  `enumerate` **不会拆开**元组，它只是给每个元素前面加一个序号。
- `for i, (c,s) in ...`：
  ```python
  i  ← 序号（enumerate 给的）
  (c, s) ← 里面的元组再拆成 c=文案、s=分数   ← 括号必须有，这就是"双重解包"
  ```
  写成 `for i, c, s in ...`，会报 `ValueError: not enough values to unpack`。
- `score={s:.4f}中的{s:.4f}`：f-string 的**格式说明符**。`:` 后面是格式，`.4f` 表示“浮点数保留 4 位小数”。


2. 取到`top-k`。拿到问题向量和文本向量的相似度后，取出最高的k位，用来拼接给prompt
```python
print("\n===== ⑤ 排序取第一名 =====")
best = max(range(len(scores)), key=lambda i: scores[i])
print(f"scores.sort 之后第一名是 chunk{best} → {chunks[best]}")
print("FAISS 干的全部事情，就是把上面 45 步换成一句 index.search(q, k)。没别的魔法。")
```

==FAISS==：[[day5-RAG#^e55718|Vector Store索引卡柜]]  用来存向量和做近邻检索的索引结构。[[day5-RAG#^f430bf|FAISS版]]
有两种检索模式：
- `IndexFlatIP`（内积索引，Flat = 平铺）：先[[Agent开发/归一化.md|归一化]]，然后进行余弦比较
- `IndexFlatL2`：欧式检索，不用归一化，改用直线距离量远近
- `IndexIVFFlat` / HNSW（两种近似索引） ps：暂时没用到

==取best==：`best = max(range(len(scores)), key=lambda i: scores[i])`
- 取最大值的压缩版
  ```js
    const scores = [0.5911, 0.0201, 0.0352];
	let best = 0;   // 先假设第 0 个最大
	for (let i = 1; i < scores.length; i++) {
	  if (scores[i] > scores[best]) best = i;  // 谁大就把下标换成谁
	}
	// best = 0
  ```
- `len(scores)`
	- `scores` 通常是一个列表（或者数组），里面存着各个候选结果的得分，比如 `[0.8, 0.9, 0.7]`。
	- `len(scores)` 的作用是**获取这个列表的长度**（元素个数）。如果 `scores` 里有 3 个元素，`len(scores)` 就是 `3`。
- ### `range(...)`
	- `range(n)` 是 Python 中用来生成一个整数序列的函数。
	- `range(3)` 会生成一个从 0 开始，到 2 结束的序列：`0, 1, 2`（注意：**包含 0，不包含 n**）。
- ### `range(len(scores))`
	- 它的意思是：**生成一个从 `0` 到 `len(scores)-1` 的整数序列**。
	- **本质：** 这个序列刚好就是 `scores` 列表里每一个元素的**索引（下标）**。
	- **例子：** 如果 `scores = [0.8, 0.9, 0.7]`，那么 `range(len(scores))` 生成的就是 `0, 1, 2`。
	- 合起来看，就是**找出 `scores` 列表中最大值所在的“索引（下标）**
- `lambda` 是 **Python 里的匿名函数**，相当于**箭头函数**。
```python
lambda i: scores[i]        # Python
```
对应js：
```js
i => scores[i]             // JavaScript，一模一样
```
完整的写法就是：
```python
def 按分数取(i):        # 4 行，还起了个名字
    return scores[i]

按分数取 = lambda i: scores[i]    # 1 行，没名字
```
因为 `key=` 只需要一个“把 i 翻成分数”的小函数，**用完就扔，起名字是浪费**
```python
lambda x: x * x                    # ✅
lambda a, b: a + b                 # ✅ 多参数
lambda x: '高' if x > 0.5 else '低'  # ✅ 三元可以
lambda x:                          # ❌ 不能多行、不能写 return、不能写 for
    return x * x
```
总结版：
```python
best = max(range(len(scores)), key=lambda i: scores[i])
```
就是先**找出 `scores` 列表中最大值所在的==索引==（下标）**。拿到了索引i值，通过箭头函数`lambda i:scores[i]`  传参`i`值，返回`scores[i]`

3. **拼接prompt并发给llm**
```python
print("\n===== 6. 生成：把 top1 塞给模型 =====")
prompt = (
    f"只根据资料回答，资料里没有就说不知道。\n资料：{chunks[best]}\n问题：{question}"
)

resp = httpx.post(
    f"{BASE_URL}/chat/completions",
    headers={"Authorization": f"Bearer {API_KEY}"},
    json={
        "model": os.getenv("MODEL_NAME"),
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
    },
    timeout=60,
)
answer = resp.json()["choices"][0]["message"]["content"]
print(f"模型回答：{answer}")
```

4. 这就是RAG简单版逻辑
```python
print("RAG = 上面这 6 步。你刚才看到的就是全部。")

print("剩下的名词：Loader = 第1步换个来源、FAISS = 第45步换个写法、")

print("Retriever = 把 45 包成函数、Rerank = 第5步之后再找模型排一次。")
```
