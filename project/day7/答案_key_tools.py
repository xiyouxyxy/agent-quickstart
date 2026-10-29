# -*- coding: utf-8 -*-
"""
答案_key_tools.py        ← D7 参考实现（先自己写 tools.py，卡住或写完了再看这个）

这个文件要解决的事：
  day6 的检索内核（向量 + BM25 + RRF + rerank）写在一个叫
  「D6-混合检索和rerank.py」的文件里 —— 那个名字**没法 import**
  （有中文、有连字符、有空格），所以明天要写的 agent.py 用不上它。

  今天的活 = 把那套内核搬进一个能 import 的模块 tools.py，
  再把能力包装成 3 个「工具」，给 LLM 看。

跑法（import 不会请求网络，第一次 search_kb 才会）：
  cd D:/agent-learn/project/day7
  D:/agent-learn/project/venv/Scripts/python.exe 答案_key_tools.py
"""

import os
import re
import math
import glob
import json
import datetime

import httpx
import numpy as np
import faiss
from dotenv import load_dotenv

# ==========================================================================
# 〇、路径与环境（这一节的作用：保证“从任何目录运行都能找到文件”）
# ==========================================================================
_HERE = os.path.dirname(os.path.abspath(__file__))          # 本文件所在目录 = day7
_ENV_LOCAL = os.path.join(_HERE, ".env")                    # 优先 day7/.env
_ENV_FALLBACK = os.path.join(_HERE, "..", "day5", ".env")   # 没有就回落 day5/.env
load_dotenv(dotenv_path=_ENV_LOCAL if os.path.exists(_ENV_LOCAL) else _ENV_FALLBACK)

API_KEY = os.getenv("API_1") or os.getenv("API_KEY")
BASE_URL = os.getenv("BASE_URL")
MODEL_NAME = os.getenv("MODEL_NAME")
EMBED_MODEL = os.getenv("EMBED_MODEL", "embo-01")
DOC_DIR = os.path.join(_HERE, "..", "day5", "docs")         # 语料还是 day5 那 4 篇

K1, B = 1.5, 0.75
RRF_K = 60
REFUSE_THRESHOLD = 0.6          # 沿用 day5/D6：最高向量分低于它 = 拒答


# ==========================================================================
# 一、检索内核（day6 原样搬过来，一行没改）
#     搬家的原因只有一个：让它住进一个能被 import 的文件
# ==========================================================================
def load_docs(doc_dir: str = DOC_DIR) -> list:
    docs = []
    for path in sorted(glob.glob(os.path.join(doc_dir, "*.md"))):
        with open(path, encoding="utf-8") as f:
            docs.append({"source": os.path.basename(path), "text": f.read()})
    return docs


def split_text(text: str, source: str, chunk_size: int = 200, overlap: int = 40) -> list:
    chunks = []
    start = 0
    while start < len(text):
        piece = text[start : start + chunk_size]
        if piece.strip():
            chunks.append({"source": source, "text": piece})
        start += chunk_size - overlap
    return chunks


def embed(texts: list, type_: str = "db"):
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


def tokenize(text: str) -> list:
    """切词：英文/数字整体（xr、2000），中文单字 + 相邻两字（保、修、保修）。"""
    text = text.lower()
    latin = re.findall(r"[a-z0-9]+", text)
    han = re.findall(r"[\u4e00-\u9fff]", text)
    bigram = [han[i] + han[i + 1] for i in range(len(han) - 1)]
    return latin + han + bigram


def bm25_scores(query: str, tokens: dict) -> dict:
    qt = list(set(tokenize(query)))
    n = len(tokens)
    if n == 0:
        return {}
    lens = {i: len(ts) for i, ts in tokens.items()}
    avg_len = sum(lens.values()) / n

    idf = {}
    for t in qt:
        df = sum(1 for ts in tokens.values() if t in ts)
        idf[t] = math.log((n - df + 0.5) / (df + 0.5) + 1)

    out = {}
    for i, ts in tokens.items():
        total = 0.0
        for t in qt:
            tf = ts.count(t)
            if tf == 0:
                continue
            total += idf[t] * (tf * (K1 + 1)) / (tf + K1 * (1 - B + B * lens[i] / avg_len))
        out[i] = total
    return out


def rrf_fuse(vec_rank: list, bm_rank: list, k: int = RRF_K) -> list:
    vec_pos = {idx: pos for pos, idx in enumerate(vec_rank, start=1)}
    bm_pos = {idx: pos for pos, idx in enumerate(bm_rank, start=1)}
    fallback_v = len(vec_rank) + 1
    fallback_b = len(bm_rank) + 1

    fused = []
    for idx in set(vec_rank) | set(bm_rank):
        score = 1 / (k + vec_pos.get(idx, fallback_v)) + 1 / (k + bm_pos.get(idx, fallback_b))
        fused.append((idx, score))
    fused.sort(key=lambda x: x[1], reverse=True)
    return fused


def cross_score(query: str, text: str) -> float:
    """rerank 占位：真模型是「问题+文档拼一起送进模型」，这里先用词重合率顶替。"""
    q = set(tokenize(query))
    d = set(tokenize(text))
    if not q:
        return 0.0
    return len(q & d) / len(q)


def rerank(query: str, candidates: list, top_k: int = 3) -> list:
    for c in candidates:
        c["rerank"] = cross_score(query, c["text"])
    return sorted(candidates, key=lambda c: c["rerank"], reverse=True)[:top_k]


class Retriever:
    def __init__(self, chunks: list):
        self.chunks = chunks
        self.vectors = embed([c["text"] for c in chunks], type_="db")
        self.index = faiss.IndexFlatIP(self.vectors.shape[1])
        self.index.add(self.vectors)

    def _search_ids(self, query: str, k: int):
        q = embed([query], type_="query")
        scores, ids = self.index.search(q, k)
        return [int(i) for i in ids[0]], [float(s) for s in scores[0]]

    def hybrid_search(self, query: str, recall_k: int = 5, top_k: int = 3) -> dict:
        vec_ids, vec_scores = self._search_ids(query, recall_k)

        tokens = {i: tokenize(c["text"]) for i, c in enumerate(self.chunks)}
        bm = bm25_scores(query, tokens)
        bm_ranked = sorted(bm.items(), key=lambda kv: kv[1], reverse=True)
        bm_ids = [i for i, _ in bm_ranked[:recall_k]]

        fused = rrf_fuse(vec_ids, bm_ids)
        vec_score_map = dict(zip(vec_ids, vec_scores))

        cands = []
        for idx, rrf_score in fused[:recall_k]:
            c = dict(self.chunks[idx])
            c["idx"] = idx
            c["score"] = vec_score_map.get(idx, 0.0)
            c["bm25"] = bm.get(idx, 0.0)
            c["rrf"] = rrf_score
            cands.append(c)

        hits = rerank(query, cands, top_k=top_k)
        return {"hits": hits, "max_vec": max(vec_scores) if vec_scores else 0.0}


# ==========================================================================
# 二、懒加载：**今天最重要的一个工程细节**
#
#   如果写成 retriever = Retriever(chunks) 放在文件顶层，那么
#   任何人 import 这个文件一次，就会触发一次 embedding 请求（22 个块 → 2 次 HTTP）
#   —— 这叫「import 副作用」，面试里被问到「你的模块为什么这么设计」这就是答案。
#
#   懒加载 = 第一次真正要检索时才建，而且只建一次（存在全局变量里）。
# ==========================================================================
_RETRIEVER = None
_DOC_META = None


def _build_chunks() -> list:
    """读 4 篇文档 → 切块 → 给每块编号（doc_id），并记下它是文件里的第几块。"""
    docs = load_docs()
    chunks = []
    for d in docs:
        chunks.extend(split_text(d["text"], d["source"]))

    counters = {} # counters 记录“每个文件已经数到第几块”
    for i, c in enumerate(chunks):
        c["doc_id"] = f"c{i:02d}"                      # c00 / c01 / ... 全库唯一
        n = counters.get(c["source"], 0)
        c["seq_in_doc"] = n + 1                        # 这块是它所在文件的第几块
        counters[c["source"]] = n + 1
    return chunks


def get_retriever() -> "Retriever":
    # 第一次需要时创建索引，之后一直复用同一个
    global _RETRIEVER
    if _RETRIEVER is None: # 还没有创建过索引
        _RETRIEVER = Retriever(_build_chunks()) # 创建索引：读 4 篇文档 → 切块 → 2 次 embedding → 建 FAISS
    return _RETRIEVER


def _doc_meta() -> dict:
    """{文件名: {source, updated, size}}  —— updated 用文件修改时间，不手写。"""
    global _DOC_META
    if _DOC_META is None:
        _DOC_META = {}
        for path in sorted(glob.glob(os.path.join(DOC_DIR, "*.md"))):
            name = os.path.basename(path)
            st = os.stat(path) # os.stat() 就是向操作系统查询一个文件的档案信息，相当于问操作系统：“这个文件多大、什么时候改的、什么权限”。
            _DOC_META[name] = {
                "source": name,
                "updated": datetime.datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d"),
                "size_bytes": st.st_size,
            }
    return _DOC_META


# ==========================================================================
# 三、三个工具（给 LLM 用的函数）
#
#   规矩（面试会被问「工具怎么设计」）：
#     ① 参数少而明确，最好只有 1-2 个
#     ② 返回值是「字符串 or 小 JSON」，不是 Python 对象（LLM 只能读文本）
#     ③ 内部异常不要往外抛 —— 转成 {"ok": False, "error": "..."} 让模型自己处理
#     ④ 一定要带「来源」，否则模型编了你也看不出来
# ==========================================================================
def search_kb(query: str, top_k: int = 3) -> dict:
    """
    在云图库知识库里检索相关片段（向量 + BM25 混合检索 + rerank 精排）。

    Args:
        query: 检索用的自然语言问题或关键词，越具体越好
        top_k: 返回几块，默认 3，最多 5
    Returns:
        {"found": bool, "hits": [{"doc_id","source","text","score"}], "message": str}
        found=False 表示知识库里没有相关内容，此时不要再用同样的词重复查。
    """
    top_k = max(1, min(int(top_k), 5))
    try:
        res = get_retriever().hybrid_search(query, recall_k=5, top_k=top_k)
    except Exception as e:
        return {"found": False, "hits": [], "message": f"检索出错：{e}"}

    max_vec = res["max_vec"]
    if max_vec < REFUSE_THRESHOLD:
        return {
            "found": False,
            "hits": [],
            "message": (
                f"知识库里没有相关内容（最高相似度 {max_vec:.2f} 低于阈值 "
                f"{REFUSE_THRESHOLD}）。可以换个关键词再试一次，或直接告诉用户查不到。"
            ),
        }

    hits = [] # hits 就是检索命中的片段列表。这个词是搜索领域的标准叫法，hit = 命中一次
    for h in res["hits"]:
        hits.append(
            {
                "doc_id": h["doc_id"],
                "source": h["source"],
                "text": h["text"].strip(),          # 原样给，不截断（200 字的块不长）
                "score": round(h["score"], 3),
            }
        )
    return {
        "found": True,
        "hits": hits,
        "message": f"命中 {len(hits)} 块，最高相似度 {max_vec:.2f}",
    }


_ALLOWED_CALC = set("0123456789+-*/(). %")


def calc(expression: str) -> dict:
    """
    计算一个纯数学表达式（加减乘除、括号、百分号）。

    Args:
        expression: 例如 "399*12*0.8" 或 "(399-99)*12/0.08"
    Returns:
        {"ok": True, "result": 数值} 或 {"ok": False, "error": "原因"}
    """
    expr = str(expression).strip().replace("×", "*").replace("÷", "/") #  replace(旧的, 新的)
    bad = [ch for ch in expr if ch not in _ALLOWED_CALC]
    if bad:
        return {"ok": False, "error": f"表达式里有不允许的字符 {bad}，只能算纯数字式子"}
    try:
        # eval 只喂空内置命名空间，防止被塞进 __import__ 之类的调用
        value = eval(expr, {"__builtins__": {}}, {})
    except Exception as e:
        return {"ok": False, "error": f"算不出来：{e}"}

    if isinstance(value, float):
        value = round(value, 4)
    return {"ok": True, "result": value}


def get_doc_meta(doc_id: str) -> dict:
    """
    查某个片段的出处信息：来自哪个文件、这个文件什么时候更新的、片段原文。

    Args:
        doc_id: search_kb 返回结果里的 doc_id，形如 "c07"
    Returns:
        {"ok": True, "source", "updated", "seq_in_doc", "text"} 或 {"ok": False, "error"}
    """
    chunks = get_retriever().chunks
    for c in chunks:
        if c["doc_id"] == doc_id:
            meta = _doc_meta().get(c["source"], {})
            return {
                "ok": True,
                "doc_id": doc_id,
                "source": c["source"],
                "seq_in_doc": c.get("seq_in_doc"),
                "updated": meta.get("updated", "未知"),
                "text": c["text"].strip(),
            }
    return {"ok": False, "error": f"没有 doc_id={doc_id} 这一块，doc_id 只能从 search_kb 的结果里拿"}


# ==========================================================================
# 四、工具说明书（schema）—— 模型看的就是这一段，写不好它就不会用
# ==========================================================================
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_kb",
            "description": (
                "在云图库公司知识库里检索资料。知识库只包含四类内容："
                "① 云图库 Pro 产品套餐与定价 ② 差旅与费用报销制度 "
                "③ 线上故障应急值班手册 ④ 硬件保修与售后服务（XR 系列）。"
                "凡是问这四类事实（价格、额度、标准、时限、型号、保修、流程）都必须先调它。"
                "它返回若干原文片段和出处，不是完整文档；片段里没有的细节就是没有。"
                "如果返回 found=false，说明知识库里没有，不要用同样的词重复调用。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "检索词。用问题里的关键实体和数字，不要写整句寒暄",
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "返回几块，默认 3，最多 5",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calc",
            "description": (
                "计算纯数学表达式，只支持数字和 + - * / ( ) % 。"
                "凡是需要算差价、总额、折扣、平均值、倍数，都必须调它，不要自己心算。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": '数学表达式，例如 "(399-99)*12/0.08"',
                    }
                },
                "required": ["expression"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_doc_meta",
            "description": (
                "查某一块资料的出处：文件名、更新时间、是该文件第几块、完整原文。"
                "当你要在答案里标注引用来源，或需要确认两块资料是否来自同一份文件时才调它。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "doc_id": {
                        "type": "string",
                        "description": 'search_kb 返回的 doc_id，形如 "c07"',
                    }
                },
                "required": ["doc_id"],
            },
        },
    },
]

# 名字 → 函数。模型只会说「我要调 search_kb」，真正执行靠这张表
DISPATCH = {
    "search_kb": search_kb,
    "calc": calc,
    "get_doc_meta": get_doc_meta,
}


# ==========================================================================
# 五、自检（不需要网络的部分 + 需要网络的部分分开跑）
# ==========================================================================
def _selfcheck_offline():
    print("【离线自检】不需要网络")
    assert len(TOOLS) == 3, f"应该正好 3 个工具，现在是 {len(TOOLS)}"
    names = [t["function"]["name"] for t in TOOLS]
    print(f"  工具名：{names}")
    assert set(names) == set(DISPATCH), "TOOLS 里的名字和 DISPATCH 的键必须一一对应"
    for t in TOOLS:
        f = t["function"]
        assert f["description"].strip(), f"{f['name']} 的描述不能空"
        assert f["parameters"]["required"], f"{f['name']} 必须标出必填参数"
    print("  ✓ 3 个工具、名字对得上、每个都有描述和必填参数")

    r = calc("(399-99)*12/0.08")
    print(f"  calc((399-99)*12/0.08) = {r}")
    assert r["ok"] and abs(r["result"] - 45000) < 1e-6, "算错了，应该是 45000"
    dangerous = calc("__import__('os')")
    print("  calc(\"__import__('os')\") →", dangerous, " ← 被挡掉")
    assert not dangerous["ok"]
    print("  ✓ calc 能算、也能挡住危险输入")


def _selfcheck_online():
    print("\n【联网自检】会调用 embedding 接口（第一次较慢）")
    r = search_kb("XR-2000 的保修期是多久？", top_k=3)
    print(f"  found={r['found']}  message={r['message']}")
    for h in r["hits"]:
        print(f"    {h['doc_id']}  score={h['score']}  {h['source']}  «{h['text'][:34]}»")
    assert r["found"], "XR-2000 这题应该能查到"
    assert any("XR-2000" in h["text"] for h in r["hits"]), "top3 里必须出现含 XR-2000 的块"

    r2 = search_kb("员工生日有几天假？")
    print(f"  拒答题 found={r2['found']}  message={r2['message']}")
    assert not r2["found"], "这题应该 found=False"

    meta = get_doc_meta(r["hits"][0]["doc_id"])
    print(f"  get_doc_meta({r['hits'][0]['doc_id']}) → {meta['source']} / {meta['updated']} / 第{meta['seq_in_doc']}块")
    assert meta["ok"]
    print("  ✓ search_kb / calc / get_doc_meta 三个都能用")


if __name__ == "__main__":
    print("=" * 72)
    print("C 层自检：3 个工具能不能被正确调用")
    print("=" * 72)
    _selfcheck_offline()
    _selfcheck_online()
    print("\n全过 = 今天的主产出可用，可以拿去写 agent.py 了。")
