# -*- coding: utf-8 -*-
"""
D6-混合检索和rerank.py        ← 今天的主产出（最终版）

在 day5 的 L5-mini_rag.py 上加了两个零件：
  ① BM25 关键词检索 + RRF 融合  → hybrid_search()
  ② rerank 精排（cross_score 先占位，接口能直接换真模型）

跑法：
  cd D:/agent-learn/project/day6
  D:/agent-learn/project/venv/Scripts/python.exe D6-混合检索和rerank.py

跑通后的产出：三条验收全过，且能看到「融合前后名次对比」的证据表。
"""

import os
import re
import math
import glob
import httpx
import numpy as np
import faiss
from dotenv import load_dotenv

# 优先用 day6/.env，没有才回落到 day5/.env
_HERE = os.path.dirname(os.path.abspath(__file__))
_ENV_LOCAL = os.path.join(_HERE, ".env")
_ENV_FALLBACK = os.path.join(_HERE, "..", "day5", ".env")
load_dotenv(dotenv_path=_ENV_LOCAL if os.path.exists(_ENV_LOCAL) else _ENV_FALLBACK)

API_KEY = os.getenv("API_1")
BASE_URL = os.getenv("BASE_URL")
EMBED_MODEL = os.getenv("EMBED_MODEL", "embo-01")
DOC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "day5", "docs")

K1, B = 1.5, 0.75  # BM25 两个行业默认参数
RRF_K = 60  # RRF 的 k，论文经验值
REFUSE_THRESHOLD = 0.6  # 拒答阈值（沿用 day5）


# ==========================================================================
# 一、基础三件套（day5 原样搬过来）
# ==========================================================================
def load_docs(doc_dir: str = DOC_DIR) -> list:
    docs = []
    for path in sorted(glob.glob(os.path.join(doc_dir, "*.md"))):
        with open(path, encoding="utf-8") as f:
            docs.append({"source": os.path.basename(path), "text": f.read()})
    return docs


def split_text(
    text: str, source: str, chunk_size: int = 200, overlap: int = 40
) -> list:
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
    arr = np.array(
        vectors, dtype="float32"
    )  # 把向量转为float32类型的矩阵（n行 x 1536列）
    faiss.normalize_L2(arr)
    return arr


# ==========================================================================
# 二、零件①：BM25（手写，约 25 行）
# ==========================================================================
def tokenize(text: str) -> list:
    """切词：英文/数字整体（xr、2000），中文单字 + 相邻两字（保、修、保修）。"""
    text = text.lower()
    latin = re.findall(r"[a-z0-9]+", text)
    han = re.findall(r"[\u4e00-\u9fff]", text)
    bigram = [han[i] + han[i + 1] for i in range(len(han) - 1)]
    return latin + han + bigram


def bm25_scores(query: str, tokens: dict) -> dict:
    """
    输入：query；tokens = {块下标: [词, 词, ...]}
    输出：{块下标: bm25得分}（没命中任何词的块也会出现在结果里，分数 0）

    三步：① 每个词的 idf（越稀有越值钱）
          ② 每块的 tf 加权（出现越多分越高，但收益递减）
          ③ 长度归一化（长块打折，防止长文档天然占便宜）

    idf: 这个词的稀有度得分，中间表，用来给第二段查询用
    out：这个块的 BM25 总分，最终表，需要return出去
    """
    qt = list(set(tokenize(query)))  # 去重：同一个词只算一次
    n = len(tokens)
    if n == 0:
        return {}
    lens = {
        i: len(ts) for i, ts in tokens.items()
    }  # 生成一张“块下标i → 该块词数len(ts)”的对照表
    avg_len = sum(lens.values()) / n
    # lens.values()拿到len(ts)，lens.keys()拿到i，lens.items()拿到键和值成对
    # sum=所有块的长度之和，然后/n 得到平均每一个块的长度

    # ① idf
    idf = {}
    for t in qt:
        df = sum(1 for ts in tokens.values() if t in ts)
        idf[t] = math.log((n - df + 0.5) / (df + 0.5) + 1)

    # ②③ tf 加权 + 长度归一化
    out = {}
    for i, ts in tokens.items():
        total = 0.0  # 为这一块准备一个分数累加器，初始值设为 0。
        for t in qt:
            tf = ts.count(t)  # 统计这个词在这一块里出现了几次；0 表示没有出现。
            if tf == 0:
                continue  # 如果这个词一次都没有出现，就跳过该词，使它不贡献任何分（idf 再高也用不上）
            total += (
                idf[t] * (tf * (K1 + 1)) / (tf + K1 * (1 - B + B * lens[i] / avg_len))
            )
            # 计算这个词的贡献分——稀有度 × 饱和命中量 ÷ 长度折扣——并累加到 total。
            # 长度折扣：tf + K1 × 长度折扣因子，其中长度折扣因子根据「这块比平均长多少」折算
        out[i] = total  # 存入总表，key:i, value:打分表
    return out


# ==========================================================================
# 三、零件②：RRF 融合（只看名次，不看分数）
# ==========================================================================
def rrf_fuse(vec_rank: list, bm_rank: list, k: int = RRF_K) -> list:
    """
    输入：两路的「块下标」有序列表（各自已按自己的分数降序排好）
    输出：[(块下标, rrf分), ...] 按 rrf分 降序

    只在一路里出现的块：另一路按「最后一名 + 1」计名次（不能丢，否则漏召回）
    """
    vec_pos = {
        idx: pos for pos, idx in enumerate(vec_rank, start=1)
    }  
    # 把「有序下标列表」反查成「块 → 名次」的明细表，enumerate 从 1 开始计名次。
    # pos表示position位置
    bm_pos = {idx: pos for pos, idx in enumerate(bm_rank, start=1)}
    fallback_v = (
        len(vec_rank) + 1
    )  # 兜底名次：向量一路没召回的块，就算它排在第 6 名（5+1）。
    fallback_b = len(bm_rank) + 1

    fused = []
    for idx in set(vec_rank) | set(bm_rank):
        score = (
            1 / (k + vec_pos.get(idx, fallback_v))
            + 1 / (k + bm_pos.get(idx, fallback_b))
        )  # 这个块的融合分 = 向量那一份倒数 + BM25 那一份倒数，.get(键, 默认) 表示查不到就用兜底名次。
        fused.append((idx, score)) # 把「块下标 + 融合分」包成元组，追加进结果列表。
    fused.sort(key=lambda x: x[1], reverse=True) # 按元组第 2 项（分数）从大到小排，lambda x: x[1] 就是「取每对的第二个元素」。
    return fused # 返回排好的榜单，形如 [(20, 0.0323), (18, 0.0318), (17, 0.0318), ...]。


# ==========================================================================
# 四、零件③：rerank 精排（cross_score 是占位，接口留好）
# ==========================================================================
def cross_score(query: str, text: str) -> float:
    """
    交叉编码器占位：真模型是「把问题和文档拼成一条送进模型输出相关分」。
    这里先用词重合率顶替（0~1），**接口不变**，换真模型只改函数体：
        resp = httpx.post(f"{BASE_URL}/rerank", json={"query": query, "doc": text, ...})
        return resp.json()["score"] / 100
    """
    q = set(tokenize(query))
    d = set(tokenize(text))
    if not q:
        return 0.0
    return len(q & d) / len(q)


def rerank(query: str, candidates: list, top_k: int = 3) -> list:
    """对粗排候选逐条重打分，按 cross_score 降序取前 top_k（保留原有字段）。"""
    for c in candidates:
        c["rerank"] = cross_score(query, c["text"])
    return sorted(candidates, key=lambda c: c["rerank"], reverse=True)[:top_k]


# ==========================================================================
# 五、Retriever：向量检索（老朋友）+ 混合检索（今天的核心）
# ==========================================================================
class Retriever:
    def __init__(self, chunks: list):
        self.chunks = chunks
        self.vectors = embed([c["text"] for c in chunks], type_="db")
        self.index = faiss.IndexFlatIP(self.vectors.shape[1])
        self.index.add(self.vectors)

    # ---- 纯向量检索（对照组，day5 原样保留）----
    def search(self, query: str, k: int = 3) -> list:
        ids, scores = self._search_ids(query, k)
        return [{**self.chunks[i], "score": s} for i, s in zip(ids, scores)]

    def _search_ids(self, query: str, k: int):
        """返回 (块下标列表, 分数列表)，按分数从高到低。"""
        q = embed([query], type_="query")
        scores, ids = self.index.search(q, k)
        return [int(i) for i in ids[0]], [float(s) for s in scores[0]]

    # ---- 混合检索 + 精排（今天写的）----
    def hybrid_search(self, query: str, recall_k: int = 5, top_k: int = 3) -> dict:
        """
        返回：
          hits        : top_k 个块（带 score=向量分 / bm25 / rrf / rerank）
          max_vec     : 候选里最高的向量分（用来判拒答）
          table       : 融合前后名次对比（要写进笔记的证据）
        """
        # ① 向量粗排
        vec_ids, vec_scores = self._search_ids(query, recall_k)

        # ② BM25 粗排
        tokens = {i: tokenize(c["text"]) for i, c in enumerate(self.chunks)}
        bm = bm25_scores(query, tokens)
        bm_ranked = sorted(bm.items(), key=lambda kv: kv[1], reverse=True)
        bm_ids = [i for i, _ in bm_ranked[:recall_k]]
        bm_map = dict(bm)

        # ③ RRF 融合
        fused = rrf_fuse(vec_ids, bm_ids)
        pos_v = {idx: p for p, idx in enumerate(vec_ids, start=1)}
        pos_b = {idx: p for p, idx in enumerate(bm_ids, start=1)}

        table = []
        for rank_after, (idx, s) in enumerate(fused, start=1):
            table.append(
                {
                    "idx": idx,
                    "向量名次": pos_v.get(idx, "—"),
                    "BM25名次": pos_b.get(idx, "—"),
                    "bm25分": bm_map.get(idx, 0.0),
                    "rrf": s,
                    "融合名次": rank_after,
                    "source": self.chunks[idx]["source"],
                    "片段": self.chunks[idx]["text"][:36].replace("\n", " "),
                }
            )

        # ④ 取前 recall_k 个当精排候选；向量分查表补上（BM25 独有候选没有向量分）
        vec_score_map = dict(zip(vec_ids, vec_scores))
        cands = []
        for idx, _ in fused[:recall_k]:
            c = dict(self.chunks[idx])
            c["idx"] = idx
            c["score"] = vec_score_map.get(idx, 0.0)  # 0 表示纯向量那一路没召回到它
            c["bm25"] = bm_map.get(idx, 0.0)
            c["rrf"] = next(s for i, s in fused if i == idx)
            cands.append(c)

        # ⑤ 精排
        hits = rerank(query, cands, top_k=top_k)

        return {
            "hits": hits,
            "max_vec": max(vec_scores) if vec_scores else 0.0,
            "table": table,
        }


# ==========================================================================
# 六、验收 runner
# ==========================================================================
def show_preview(t: str, n: int = 44) -> str:
    return t[:n].replace("\n", " ")


def main():
    print("=" * 80)
    print("D6 验收：混合检索（向量 + BM25 + RRF）+ rerank 精排")
    print("=" * 80)

    docs = load_docs()
    if not docs:
        print(f"[错误] 没读到语料，检查 DOC_DIR = {DOC_DIR}")
        return
    chunks = []
    for d in docs:
        chunks.extend(split_text(d["text"], d["source"]))
    print(f"语料：{len(docs)} 个文件 → {len(chunks)} 个块\n")

    r = Retriever(chunks)

    cases = [
        (
            "XR-2000 的保修期是多久？",
            "含 XR-2000 的型号块要进 top3（纯向量里它排不进）",
        ),
        ("专业版每月赠送多少次 AI 扩图额度？", "答案块「500 次」必须还在第 1"),
        ("员工生日有几天假？", "应拒答（纯向量最高分 0.5857 < 0.6）"),
    ]

    for q, expect in cases:
        print("=" * 80)
        print(f"【问题】{q}")
        print(f"【期望】{expect}")
        print("-" * 80)

        print("对照组 · 纯向量检索 top3：")
        for i, h in enumerate(r.search(q, k=3), 1):
            print(
                f"  {i}. score={h['score']:.4f}  {h['source']}  «{show_preview(h['text'])}»"
            )

        res = r.hybrid_search(q, recall_k=5, top_k=3)

        print("\n融合前后名次对比（前 5）：")
        print(
            f"  {'块':<4}{'向量名次':<9}{'BM25名次':<10}{'bm25分':<9}{'rrf':<10}{'融合名次':<9}{'片段'}"
        )
        for row in res["table"][:5]:
            print(
                f"  {row['idx']:<4}{str(row['向量名次']):<9}{str(row['BM25名次']):<10}"
                f"{row['bm25分']:<9.3f}{row['rrf']:<10.6f}{row['融合名次']:<9}{row['片段']}"
            )

        print("\n实验组 · 混合检索 + rerank top3：")
        for i, h in enumerate(res["hits"], 1):
            print(
                f"  {i}. 向量分={h['score']:.4f}  bm25={h['bm25']:.3f}  "
                f"rerank={h['rerank']:.4f}  {h['source']}"
            )
            print(f"     «{show_preview(h['text'], 60)}»")

        print()
        if res["max_vec"] < REFUSE_THRESHOLD:
            print(f"  [拒答] 候选最高向量分 {res['max_vec']:.4f} < {REFUSE_THRESHOLD}")
        else:
            print(
                f"  [正常回答] 候选最高向量分 {res['max_vec']:.4f} ≥ {REFUSE_THRESHOLD}"
            )
        print()

    print("=" * 80)
    print("自检清单（对不上就是没跑对）：")
    print("  □ 第 1 题：融合后的 top3 里出现了含 XR-2000 的型号块")
    print("             （纯向量 top3 里没有它 → 这就是今天要证明的改进）")
    print("  □ 第 2 题：top1 仍是含「500 次」的那块（加了 BM25 不能退步）")
    print("  □ 第 3 题：仍然拒答（阈值 0.6 没弄丢）")
    print("  □ 那张「融合前后名次对比」表能解释清楚：为什么某块升了、某块降了")


if __name__ == "__main__":
    main()
