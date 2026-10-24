# embed_demo.py —— D5 第 1 步：先确认「文本 → 向量」这条路是通的
"""
这个脚本只干一件事：验证 embedding 通路。
跑完之后你应该能当场回答三个问题：
  1. 一句话被变成多少个数字？（维度）
  2. 语义相近的两句话，向量「像不像」？用什么衡量？（余弦相似度）
  3. 为什么不能照抄网上的 OpenAI 写法？（参数名是 texts + type，不是 input）

运行：cd project/day5 && python embed_demo.py
（venv 用 project/venv，已装 httpx / python-dotenv）
"""

import os
import math
import httpx
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("API_1")                     # ⚠️ 你的 .env 里 key 的变量名就是 API_1
BASE_URL = os.getenv("BASE_URL")                 # https://api.minimaxi.com/v1
EMBED_MODEL = os.getenv("EMBED_MODEL", "embo-01")  # MiniMax 的 embedding 模型


def embed(texts: list[str], type_: str = "db") -> list[list[float]]:
    """把一批文本变成向量。返回 list[list[float]]，长度和传入的 texts 一一对应。

    和网上 OpenAI 例子有两处不同（实测出来的，别照抄）：
      · 请求体字段叫 texts（复数数组），不是 input
      · 必须带 type：入库的文档切片用 "db"，用户提问用 "query"
        —— 很多检索模型对「短查询」和「长文档」用不同的编码方式，混用会掉召回。
    """
    resp = httpx.post(
        f"{BASE_URL}/embeddings",
        headers={"Authorization": f"Bearer {API_KEY}"},
        json={"model": EMBED_MODEL, "texts": texts, "type": type_},
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()
    # MiniMax 的业务错误码放在 body 里，HTTP 状态码仍然是 200 —— 所以必须自己查 base_resp
    if data.get("base_resp", {}).get("status_code") != 0:
        raise RuntimeError(data["base_resp"])
    return data["vectors"]


def cosine(a: list[float], b: list[float]) -> float:
    """余弦相似度 = 点积 / (模长×模长)。范围 -1~1，越接近 1 越像。"""
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb)


if __name__ == "__main__":
    sentences = [
        "北京的天气怎么样",          # 查询句
        "今天北京是晴天，气温 26 度",  # 和上面语义接近
        "差旅住宿费一线城市每晚上限 600 元",  # 无关
    ]
    vecs = embed(sentences, type_="query")   # 这里当查询用，所以 type=query

    print("条数 =", len(vecs))
    print("维度 =", len(vecs[0]))                       # 期望 1536
    print("第一句的向量模长 =", round(math.sqrt(sum(x * x for x in vecs[0])), 4))  # 期望 1.0（已归一化）
    print()

    for i in range(len(sentences)):
        for j in range(i + 1, len(sentences)):
            print(f"cos({i},{j}) = {cosine(vecs[i], vecs[j]):.4f}   「{sentences[i]}」 vs 「{sentences[j]}」")

    print()
    print("→ 你应该看到：0/1 明显高于 0/2 和 1/2，说明向量真的捕捉到了语义，而不是字面重合度。")
    print("→ 顺带一个面试点：因为向量已归一化（模长 1），此时「余弦相似度」=「点积」，")
    print("  所以 FAISS 用 IndexFlatIP（内积）就够了，不需要专门写余弦函数。")
