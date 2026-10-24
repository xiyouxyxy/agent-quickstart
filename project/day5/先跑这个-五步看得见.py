# 先跑这个 —— RAG 五步，每一步都打印出来
"""
别读清单，先跑这个。60 行，全部 print 出来给你看。
语料只有 3 句话，为的是让你一眼看到：文字 → 数组 → 分数 → 排序 → 答案。

运行：
    cd D:/agent-learn/project/day5
    python 先跑这个-五步看得见.py
"""

import os
import httpx
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("API_1")
BASE_URL = os.getenv("BASE_URL")
EMBED_MODEL = "embo-01"

# ============ ① 准备语料 ============
# 假装这 3 句就是从 3 个文档里切出来的 chunk（真实项目里是 glob 读文件 + 切分）
chunks = [
    "专业版每月赠送 500 次 AI 扩图额度",  # chunk 0
    "一线城市住宿费每晚上限 600 元",  # chunk 1
    "P0 故障要求 15 分钟内响应",  # chunk 2
]


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


# ============ ② 建库：每个 chunk 变成一串数字 ============
print("===== ② 建库：把 3 个 chunk 变成数组 =====")
doc_vecs = embed(chunks, "db")
print(f"每个 chunk 变成多长的数组：{len(doc_vecs[0])}")
print(f"chunk 0 的前 5 个数：{[round(x, 4) for x in doc_vecs[0][:5]]}")
print("（这 5 个数没有任何人类意义，别试图读懂它，它只是'意思的坐标'的一部分）")

# ============ ③ 提问：问题也变成数组 ============
print("\n===== ③ 提问：问题也走同一个函数 =====")
question = "专业版每个月送多少次扩图？"
q_vec = embed([question], "query")[0]
print(f"问题：{question}")
print(
    f"问题也变成 {len(q_vec)} 个数，chunk 是 {len(doc_vecs[0])} 个数 → 长度一样才能比"
)

# ============ ④ 算相似度：一个问题 vs 3 个 chunk ============
print("\n===== ④ 算相似度（这一步就是全部的秘密）=====")
print("因为向量已经归一化，余弦 = 点积 = 对应位相乘再相加")
scores = []
for v in doc_vecs:
    s = sum(a * b for a, b in zip(q_vec, v))  # ← 就这一行
    scores.append(s)

for i, (c, s) in enumerate(zip(chunks, scores)):
    print(f"  chunk{i}  score={s:.4f}  {c}")
print("↑ 注意 chunk0 的分数明显高，另外两个趴在地上")

# ============ ⑤ 排序取 top-candidate：前端一句话 ============
print("\n===== ⑤ 排序取第一名 =====")
best = max(range(len(scores)), key=lambda i: scores[i])
print(f"scores.sort 之后第一名是 chunk{best} → {chunks[best]}")
print("FAISS 干的全部事情，就是把上面 ④⑤ 步换成一句 index.search(q, k)。没别的魔法。")

# ============ ⑥ 生成：把搜到的塞进 prompt ============
print("\n===== ⑥ 生成：把 top1 塞给模型 =====")
prompt = (
    f"只根据资料回答，资料里没有就说不知道。\n资料：{chunks[best]}\n问题：{question}"
)
print("发给模型的东西长这样：")
print("---")
print(prompt)
print("---")

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

print("\n===== 这就完了 =====")
print("RAG = 上面这 6 步。你刚才看到的就是全部。")
print("剩下的名词：Loader = 第①步换个来源、FAISS = 第④⑤步换个写法、")
print("Retriever = 把 ④⑤ 包成函数、Rerank = 第⑤步之后再找模型排一次。")
