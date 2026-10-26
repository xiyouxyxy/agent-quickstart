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


def load_docs(doc_dir: str = DOC_DIR) -> list[dict]:
    docs = []
    for path in sorted(glob.glob(os.path.join(doc_dir, "*.md"))):
        with open(path, encoding="utf-8") as f:
            docs.append({"source": os.path.basename(path), "text": f.read()})
    return docs


def split_text(text: str, source: str, chunk_size: int = 200, overlap: int = 40) -> str:
    chunks = []
    start = 0
    while start < len(text):
        piece = text[start : start + chunk_size]
        if piece.strip():
            chunks.append({"source": source, "text": piece})
        start += chunk_size - overlap
    return chunks


def embed(texts: list[str], type_: str = "db"):
    vectors = []
    BATCH = 20
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
    arr = np.array(vectors, dtype="float32")
    faiss.normalize_L2(arr)
    return arr


class Retriever:
    def __init__(self, chunks=list[dict]):
        self.chunks = chunks
        self.vectors = embed([c["text"] for c in chunks], type_="db")
        self.index = faiss.IndexFlatIP(self.vectors.shape[1])
        self.index.add(self.vectors)

    def search(self, query: str, k: int = 3) -> list[dict]:
        q = embed([query], type_="query")
        scores, ids = self.index.search(q, k)
        return [
            {**self.chunks[i], "score": float(s)} for s, i in zip(scores[0], ids[0])
        ]


def answer(question: str, hits: list[dict]) -> str:
    context = "\n\n".join(f"[来源:{h['source']}\n{h['text']}]" for h in hits)
    llm = ChatOpenAI(
        model=MODEL_NAME, api_key=API_KEY, base_url=BASE_URL, temperature=0
    )
    messages = [
        SystemMessage(
            content=(
                "你是一个只基于给定资料回答问题的助手。"
                "如果资料里没有答案，直接回答「资料中没有相关信息」，绝对不要编造。"
            )
        ),
        HumanMessage(content=f"资料：\n{context}\n\n问题：{question}"),
    ]
    return llm.invoke(messages).content


if __name__ == "__main__":
    question = (
        sys.argv[1] if len(sys.argv) > 1 else "专业版每月赠送多少次 AI 扩图额度？"
    )
    docs = load_docs()
    chunks = []
    for d in docs:
        chunks.extend(split_text(d["text"], d["source"]))

    retriever = Retriever(chunks)
    hits = retriever.search(question, k=3)

    for i, h in enumerate(hits, 1):
        head = h["text"][:60].replace("\n", "")
        print(f"top{i}  score={h['score']:.4f}  {h['source']}  «{head}...»")

    if hits[0]["score"] < 0.6:
        print("\n[generate] 拒答：")
        print("资料中没有相关信息")
    else:
        print("\n[generate] 回答：")
        print(answer(question, hits))
