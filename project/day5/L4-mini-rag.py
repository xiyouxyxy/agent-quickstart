import os
import httpx
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("API_1")
BASE_URL = os.getenv("BASE_URL")
EMBED_MODEL = "embo-01"

chunks = [
    "专业版每月赠送 500 次 AI 扩图额度",  # chunk 0
    "一线城市住宿费每晚上限 600 元",  # chunk 1
    "P0 故障要求 15 分钟内响应",  # chunk 2
]


def embedded(texts, type_="db"):
    """通过接口将texts文字转向量"""
    resp = httpx.post(
        f"{BASE_URL}/embeddings",
        headers={"Authorization": f"Bearer {API_KEY}"},
        json={"model": EMBED_MODEL, "texts": texts, "type": type_},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["vectors"]


doc_vecs = embedded(chunks, "db")
question = "专业版每一个月送多少次扩图"
q_vecs = embedded([question], "query")[0]

scores = []
for v in doc_vecs:
    s = sum(a * b for a, b in zip(q_vecs, v))
    scores.append(s)


best = max(range(len(scores)), key=lambda i: scores[i])

prompt = f"只需要根据资料回答问题，资料没有就说不知道。\n资料：{chunks[best]}\n问题：{question}"
resp = httpx.post(
    f"{BASE_URL}/chat/completions",
    headers={"Authorization": f"Bearer {API_KEY}"},
    json={
        "model": os.getenv("MODEL_NAME"),
        "messages": [{"role": "user", "content": prompt}],
    },
    timeout=60,
)
answer = resp.json()["choices"][0]["message"]["content"]
print(f"模型回答：{answer}")
