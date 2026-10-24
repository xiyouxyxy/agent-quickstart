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
DOC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs")


# ---------- 1. Load：把文档读成 {source, text} ----------
def load_docs(doc_dir: str = DOC_DIR) -> list[dict]:
    docs = []
    for path in sorted(glob.glob(os.path.join(doc_dir, "*.md"))):
        with open(path, encoding="utf-8") as f:
            docs.append({"source": os.path.basename(path), "text": f.read()})
    return docs


# ---------- 2. Split：切分（这里手写，为的是看清每个参数在干什么）----------
def split_text(text: str, source: str, chunk_size: int = 200, overlap: int = 40) -> list[dict]:
    """
    切成 chunk_size 字左右的小块，相邻块重叠 overlap 字。
    overlap 的作用：防止关键句正好被切在边界上，两半都不完整。
    """
    chunks = []
    start = 0
    while start < len(text):
        piece = text[start:start + chunk_size]
        if piece.strip():
            chunks.append({"source": source, "text": piece})
        start += chunk_size - overlap
    return chunks


# ---------- 3. Embed：批量把文本变向量 ----------
def embed(texts: list[str], type_: str = "db") -> np.ndarray:
    vectors = []
    BATCH = 20                      # 一次别发太多，接口对批量有上限
    for i in range(0, len(texts), BATCH):
        resp = httpx.post(
            f"{BASE_URL}/embeddings",
            headers={"Authorization": f"Bearer {API_KEY}"},
            json={"model": EMBED_MODEL, "texts": texts[i:i + BATCH], "type": type_},
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("base_resp", {}).get("status_code") != 0:
            raise RuntimeError(data["base_resp"])
        vectors.extend(data["vectors"])
    arr = np.array(vectors, dtype="float32")
    # 归一化后，内积 == 余弦相似度（MiniMax 已经归一化了，这行是保险）
    faiss.normalize_L2(arr)
    return arr


# ---------- 4+5. Store + Retrieve：FAISS 索引 + top-k 检索 ----------
class Retriever:
    def __init__(self, chunks: list[dict]):
        self.chunks = chunks
        self.vectors = embed([c["text"] for c in chunks], type_="db")
        self.index = faiss.IndexFlatIP(self.vectors.shape[1])   # IP = 内积
        self.index.add(self.vectors)

    def search(self, query: str, k: int = 3) -> list[dict]:
        q = embed([query], type_="query")                      # 查询要用 type="query"
        scores, ids = self.index.search(q, k)                   # 返回相似度和下标
        return [{**self.chunks[i], "score": float(s)} for s, i in zip(scores[0], ids[0])]


# ---------- 6. Generate：把检索结果塞进 prompt 让模型回答 ----------
def answer(question: str, hits: list[dict]) -> str:
    context = "\n\n".join(f"[来源：{h['source']}]\n{h['text']}" for h in hits)
    llm = ChatOpenAI(model=MODEL_NAME, api_key=API_KEY, base_url=BASE_URL, temperature=0)
    messages = [
        SystemMessage(content=(
            "你是一个只基于给定资料回答问题的助手。"
            "如果资料里没有答案，直接回答「资料中没有相关信息」，绝对不要编造。"
        )),
        HumanMessage(content=f"资料：\n{context}\n\n问题：{question}"),
    ]
    return llm.invoke(messages).content


if __name__ == "__main__":
    question = sys.argv[1] if len(sys.argv) > 1 else "专业版每月赠送多少次 AI 扩图额度？"

    docs = load_docs()
    chunks = []
    for d in docs:
        chunks.extend(split_text(d["text"], d["source"]))
    print(f"[load] {len(docs)} 篇文档 → [split] {len(chunks)} 个 chunk")

    retriever = Retriever(chunks)
    hits = retriever.search(question, k=3)

    print(f"\n[retrieve] 问题：{question}")
    for i, h in enumerate(hits, 1):
        head = h["text"][:60].replace("\n", " ")
        print(f"  top{i}  score={h['score']:.4f}  {h['source']}  «{head}...»")

    print("\n[generate] 回答：")
    print(answer(question, hits))
