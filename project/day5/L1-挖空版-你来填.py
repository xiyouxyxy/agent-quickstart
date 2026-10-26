# 挖空版 —— 手写能力第 1 级：填空
"""
规则（严格执行，否则等于白练）：
  1. 只填 6 处 ______，其他代码一个字都不要改
  2. 填完立刻跑：python 挖空版-你来填.py
  3. 看到最后一行「✅ 通关」才算过；报错就看最底下那一行（不是中间那堆栈）
  4. 卡住时可以翻「先跑这个-五步看得见.py」对照，但对照完要关掉、清空、重写一遍
  5. 6 处全填对之后，进入第 2 级：把 TODO 注释也删掉，只看代码结构再写一遍

目标不是"填对"，而是让手指记住这 6 个位置：库用 db、问用 query、相似度是点积、
top1 是排序取值、prompt 是拼字符串、调用是 messages 数组。
"""

import os
import httpx
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("API_1")
BASE_URL = os.getenv("BASE_URL")
EMBED_MODEL = "embo-01"

chunks = [
    "专业版每月赠送 500 次 AI 扩图额度",
    "一线城市住宿费每晚上限 600 元",
    "P0 故障要求 15 分钟内响应",
]


def embed(texts, type_="db"):
    resp = httpx.post(
        f"{BASE_URL}/embeddings",
        headers={"Authorization": f"Bearer {API_KEY}"},
        json={"model": EMBED_MODEL, "texts": texts, "type": type_},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["vectors"]


# ===== ② 建库：把 3 个 chunk 变成数组 =====
# TODO 1：这些是要存进库的"文档"，type_ 该是 "db" 还是 "query"？
doc_vecs = embed(chunks, type_="db")


# ===== ③ 提问：问题也变成数组 =====
question = "专业版每个月送多少次扩图？"
# TODO 2：现在编码的是用户的"查询"，type_ 该是哪个？
q_vec = embed([question], type_="query")[0]


# ===== ④ 算相似度 =====
print("===== ④ 相似度 =====")
scores = []
for v in doc_vecs:
    # TODO 3：算一个分数。提示：向量已归一化，所以余弦 == 点积 == 对应位相乘再求和
    #         用 sum(...) 和 zip(...)，一行搞定
    s = sum(a * b for a, b in zip(q_vec, v))
    scores.append(s)

for i, (c, s) in enumerate(zip(chunks, scores)):
    print(f"  chunk{i}  score={s:.4f}  {c}")


# ===== ⑤ 取第一名 =====
# TODO 4：从 scores 里找出分数最高的那个 chunk 的下标 i（0/1/2）
#         提示：max(range(len(scores)), key=lambda i: ...)
best = max(range(len(scores)), key=lambda i: scores[i])
print(f"\n第一名：chunk{best} → {chunks[best]}")


# ===== ⑥ 生成 =====
# TODO 5：拼 prompt，必须包含三样：① 只根据资料回答、没有就说不知道 ② 资料：chunks[best] ③ 问题：question
prompt = (
    f"只根据资料回答，资料里没有就说不知道。\n 资料:{chunks[best]}\n问题：{question}"
)
print("\n发给模型的 prompt：\n---")
print(prompt)
print("---")

resp = httpx.post(
    f"{BASE_URL}/chat/completions",
    headers={"Authorization": f"Bearer {API_KEY}"},
    json={
        "model": os.getenv("MODEL_NAME"),
        # TODO 6：填成大模型要的 messages 格式 —— 一个列表，里面一个 dict，role 是 "user"，content 是 prompt
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
    },
    timeout=60,
)
answer = resp.json()["choices"][0]["message"]["content"]
print(f"模型回答：{answer}")

# 通关判定（这个别改）
assert best == 0, f"top1 应该命中 chunk0，你命中的是 chunk{best}"
assert "500" in answer, f"回答里应该包含 500，实际是：{answer}"
print("\n✅ 通关：6 处全对，且检索命中 + 答案正确")
print("下一步：删掉 TODO 注释，只看变量名再写一遍（第 2 级）")
