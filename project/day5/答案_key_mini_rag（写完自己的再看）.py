# ⚠️ 答案 key：先自己写 mini_rag.py，卡住了再打开这个对答案（已实测三条验收命令全通）
# mini_rag.py —— D5 ⭐产出：最小可用 RAG（load → split → embed → faiss → retrieve → answer）
"""
运行：
    cd project/day5
    python mini_rag.py "专业版每月赠送多少次 AI 扩图额度？"
    python mini_rag.py "员工生日有几天假？"        # 资料里没有 → 应该回答不知道

依赖（已装好）：httpx / python-dotenv / numpy / faiss-cpu / langchain-openai
"""

import os
import sys
import glob
import json
import httpx
import numpy as np
import faiss
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

load_dotenv()
API_KEY = os.getenv("API_1")
BASE_URL = os.getenv("BASE_URL")
MODEL_NAME = os.getenv("MODEL_NAME")
EMBED_MODEL = os.getenv("EMBED_MODEL", "embo-01")

DOC_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "docs"
)  # 拿到当前文件的绝对路径，并拿出__dirname，然后和docs拼接。得到的就是同文件夹下的/docs文件夹


# ---------- 1. Load：把文档读成 {source, text} ----------
# 本质就是把目录内的.md文件全读进内存并带上来源名。只是读，没有向量化
def load_docs(doc_dir: str = DOC_DIR) -> list[dict]:
    docs = []
    for path in sorted(glob.glob(os.path.join(doc_dir, "*.md"))):
        # glob.glob(.../*.md)找出所有md文件，sorted保证每次加载顺序一致
        with open(path, encoding="utf-8") as f:
            # 用utf-8读全文，追加成 {"source": 文件名, "text": 全文}的dict列表
            docs.append({"source": os.path.basename(path), "text": f.read()})
    return docs  # 返回list[dict]，供下一步split-text按来源切块


# ---------- 2. Split：切分（这里手写，为的是看清每个参数在干什么）----------
def split_text(
    text: str, source: str, chunk_size: int = 200, overlap: int = 40
) -> list[dict]:
    """
    切成 chunk_size 字左右的小块，相邻块重叠 overlap 字。
    overlap 的作用：防止关键句正好被切在边界上，两半都不完整。
    @params:text 原文， source 来源名，原样带给每个chunk， chunk_size 块大小， overlap 相邻块重叠字数
    """
    chunks = []
    start = 0
    while start < len(text):
        piece = text[
            start : start + chunk_size
        ]  # 从start=0开始，每次取text[start:start + chunk_size]
        if piece.strip():  # 过滤空白块后
            chunks.append({"source": source, "text": piece})  # 追加进chunks
        start += chunk_size - overlap
    return chunks


# ---------- 3. Embed：批量把文本变向量 ----------
def embed(texts: list[str], type_: str = "db") -> np.ndarray:
    vectors = []
    BATCH = 20  # 一次别发太多，接口对批量有上限
    for i in range(0, len(texts), BATCH):
        resp = httpx.post(
            f"{BASE_URL}/embeddings",
            headers={"Authorization": f"Bearer {API_KEY}"},
            json={"model": EMBED_MODEL, "texts": texts[i : i + BATCH], "type": type_},
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("base_resp", {}).get("status_code") != 0:
            raise RuntimeError(data["base_resp"])
        vectors.extend(data["vectors"])
        # extend只展开向量组这一层
        # 比如原本的vetors=[v1,v2]，data["vectors"]=[v3,v4,v5]，extend后变成[v1,v2,v3,v4,v5]。在js内相当于vectors.push(...data["vectors"])

    arr = np.array(vectors, dtype="float32")
    # np是上面引入的库 import numpy as np; Numpy是数值计算库，提供多维数组和向量画计算，之类用来吧向量列表转为矩阵

    # FAISS：给一个向量，快速找出最像的几个
    # 要存进FAISS，使用index.add()\index.search()，这两的接口签名要求inumpy.float32的二维数组，传py列表会报错
    # faiss.normalize_L2(arr)这一行就把所有行归一化

    # 归一化后，内积 == 余弦相似度（MiniMax 已经归一化了，这行是保险）
    faiss.normalize_L2(arr)
    return arr  # 拿到 每个向量除以自身长度后的结果，形状(文本数, 维度)，里面只有向量


# ---------- 4+5. Store + Retrieve：FAISS 索引 + top-k 检索 ----------
class Retriever:
    # 建索引+检索
    def __init__(self, chunks: list[dict]):
        # 建库
        self.chunks = chunks  # 存chunks，保存原文
        self.vectors = embed([c["text"] for c in chunks], type_="db")  # 转向量
        self.index = faiss.IndexFlatIP(self.vectors.shape[1])  # IP = 内积
        # self.vectors.shape 返回元组(文本数, 维度)，就是上面的arr。shape[1]就是第二条
        # 例如 (25, 1536)：shape[0] 是 25（25 个 chunk 向量），shape[1] 是 1536（每条向量 1536 维）。传给 IndexFlatIP 就是告诉 FAISS"库里的每个向量都是 1536 维"，建索引和后续 add/search 都按这个维度校验

        self.index.add(self.vectors)
        # add 完成"向量入库 + 编号"，编号顺序对齐 chunk 顺序
        # self.vectors 形状 (n, 1536)，FAISS 按行处理，把每一行当成一条独立向量存进索引

    def search(self, query: str, k: int = 3) -> list[dict]:
        # 检索
        q = embed([query], type_="query")  # 查询要用 type="query"
        scores, ids = self.index.search(q, k)  # 返回相似度和下标
        # index.search(q, k)：返回 (scores, ids)，各是 (1, k) 的矩阵；[0] 取第一行，得到 top-k 的分数和下标
        return [
            {**self.chunks[i], "score": float(s)}
            for s, i in zip(
                scores[0], ids[0]
            )  # 用下标取回 chunk 的 source/text，合并成新 dict 并附上相似度分数
        ]


# ---------- 6. Generate：把检索结果塞进 prompt 让模型回答 ----------
def answer(question: str, hits: list[dict]) -> str:
    context = "\n\n".join(f"[来源：{h['source']}]\n{h['text']}" for h in hits)
    # 传入的是search()返回的dict，遍历，每块格式化成"来源标注 + 换行 + 原文"，让模型能区分内容出处
    llm = ChatOpenAI(
        model=MODEL_NAME, api_key=API_KEY, base_url=BASE_URL, temperature=0
    )
    messages = [
        SystemMessage(
            # SystemMessage是 LangChain 里对应 OpenAI role: "system" 的消息类型，即系统提示词——用来设定模型的角色、行为规则和约束，优先级高于用户消息，模型会把它当作"指令"而不是"对话内容"
            content=(
                "你是一个只基于给定资料回答问题的助手。"
                "如果资料里没有答案，直接回答「资料中没有相关信息」，绝对不要编造。"
            )
        ),
        HumanMessage(
            content=f"资料：\n{context}\n\n问题：{question}"
        ),  # HumanMessage 承载具体的资料和问题，是"用户侧输入"
    ]
    return llm.invoke(
        messages
    ).content  # 阻塞任务等模型全部生成玩，返回一条完整的 AIMessage 对象，`.content` 里就是完整文本。


# 对比 LangChain 里其他调用方式：
# - llm.invoke(messages)：一次给完、一次拿完（本项目用的）
# - llm.stream(messages)：流式返回，边生成边吐 token，适合打字机效果
# - llm.batch([msgs1, msgs2])：批量并发处理多组输入
# 所以这里的 return llm.invoke(messages).content 意思是：等模型答完，取出完整回答字符串返回给调用方。

if __name__ == "__main__":
    question = (
        sys.argv[1] if len(sys.argv) > 1 else "专业版每月赠送多少次 AI 扩图额度？"
        # Python 的三元表达式 A if 条件 else B
        # sys 是 Python 内置模块
        # sys.argv[0]：脚本自己（文件名）；sys.argv[1]：你运行时跟在后面的第一个参数
        # 所以这行的意思是：如果运行时传了问题（如 python mini_rag.py "员工生日有几天假？"），就把 sys.argv[1] 当问题；没传就直接取 argv[1] 会报 IndexError，所以先用 len(sys.argv) > 1 判断，否则用默认问题兜底
    )

    docs = load_docs()
    chunks = []
    for d in docs:
        chunks.extend(split_text(d["text"], d["source"]))
    print(f"[load] {len(docs)} 篇文档 → [split] {len(chunks)} 个 chunk")

    retriever = Retriever(chunks)
    hits = retriever.search(question, k=3)

    print(f"\n[retrieve] 问题：{question}")

    for i, h in enumerate(hits, 1):
        head = h["text"][:60].replace(
            "\n", " "
        )  # hits内的每一个数据，取前60个字符做head预览，并且有换行的替换成空格
        print(f"  top{i}  score={h['score']:.4f}  {h['source']}  «{head}...»")
        # 打印前i条相似的，相似度score保留4位小数，h['source']打印出资源文件名，«{head}...»打印出用书名号包裹的预览文字

    print("\n[generate] 回答：")
    print(answer(question, hits))
