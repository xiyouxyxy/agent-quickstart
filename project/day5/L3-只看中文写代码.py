# L3 —— 只有中文提纲，一行现成代码都没有
"""
规则（照做，别走捷径）：
  1. 这个文件里没有任何 Python 代码，只有中文提纲。你要把每一段翻译成代码。
  2. 某一步写不出来时，先在那一步下面用【中文】写一句"我要做什么"，再翻成代码。
  3. 允许翻 L1 的答案（`挖空版-你来填.py`），但一次只看一行，看完立刻滚回去写。
  4. 跑通、看到最后一行 ✅ 才算过。跑不通就只看最底下那行报错。
  5. 第一次大概率要 30~50 分钟，写不出来是正常的 —— 卡在哪一步，就说明那一步还没内化，
     不是"我太笨"。同一套结构写 3 遍才能脱稿，这是规律不是天赋。

运行：
    cd D:/agent-learn/project/day5
    python "L3-只看中文写代码.py"
"""

# ============ 依赖和配置：这部分是环境，不是你今天要练的，我留着 ============
import os
import httpx
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("API_1")
BASE_URL = os.getenv("BASE_URL")
EMBED_MODEL = "embo-01"
MODEL_NAME = os.getenv("MODEL_NAME")


# ============ 第 ① 步：准备语料 ============
# 写一个列表，装 3 条字符串，变量名叫 chunks。内容就用这三句：
#   "专业版每月赠送 500 次 AI 扩图额度"
#   "一线城市住宿费每晚上限 600 元"
#   "P0 故障要求 15 分钟内响应"
chunks = [
    "专业版每月赠送 500 次 AI 扩图额度",
    "一线城市住宿费每晚上限 600 元",
    "P0 故障要求 15 分钟内响应",
]


# ============ 第 ② 步：写 embed 函数 ============
# 目标：吃一批文本，吐一批向量（list[list[float]]）
# 要做的事：向 {BASE_URL}/embeddings 发 POST 请求
#   - headers 里带 Authorization: Bearer {API_KEY}
#   - body 里三个字段：model 用 EMBED_MODEL、texts 收进来的那批文本、type_ 默认 "db"
#   - 最后把 resp.json()["vectors"] 返回
# 提示：用 httpx.post，timeout 给 60；resp.raise_for_status() 加一句没坏处
def embed(texts, type_="db"):
    resp = httpx.post(
        f"{BASE_URL}/embeddings",
        headers={"Authorization": f"Bearer {API_KEY}"},  # Bearer {API_KEY}这里有个空格
        json={"model": EMBED_MODEL, "texts": texts, "type": type_},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["vectors"]


# ============ 第 ③ 步：建库 ============
# 把 chunks 全部转成向量，变量名叫 doc_vecs。注意这里传 type_="db"
print("===== ② 建库：把 3 个 chunk 变成数组 =====")
doc_vecs = embed(chunks, "db")
print(doc_vecs, "doc_vecs")

# ============ 第 ④ 步：提问 ============
# 问题字符串是："专业版每个月送多少次扩图？"
# 把它也转成向量，变量名叫 q_vec
# 两个坑：① 这里的 type_ 该用哪个？ ② embed 返回的是一批，只有一个问题，要取第 0 个
print("\n===== ③ 提问：问题也走同一个函数 =====")
question = "专业版每个月送多少次扩图？"
q_vec = embed([question], "query")[0]


# ============ 第 ⑤ 步：算相似度 ============
# 对 doc_vecs 里的每一个向量，算它和 q_vec 的点积（对应位相乘再求和），存进 scores 列表
# 然后打印出每个 chunk 的分数（格式随意，能看清就行）
print("\n===== ④ 算相似度（这一步就是全部的秘密）=====")
scores = []
for v in doc_vecs:
    s = sum(a * b for a, b in zip(q_vec, v))
    scores.append(s)

# ============ 第 ⑥ 步：取第一名 ============
# 从 scores 里找出分数最高的那个的【下标】，变量名叫 best
# 打印 chunks[best]，看看是不是"专业版每月赠送 500 次 AI 扩图额度"
for i, (c, s) in enumerate(zip(chunks, scores)):
    print(f" chunk{i} score={s:.4f} {c}")

best = max(range(len(scores)), key=lambda i: scores[i])


# ============ 第 ⑦ 步：拼 prompt 并调用模型 ============
# prompt 必须包含三样：
#   1. 约束："只根据资料回答，资料里没有就说不知道"
#   2. 资料：chunks[best]
#   3. 问题：那个问题字符串
# 然后向 {BASE_URL}/chat/completions 发 POST：
#   - headers 同上
#   - body 三个字段：model 用 MODEL_NAME、messages（一批消息，里面一条 role 是 user、
#     content 是 prompt 的消息）、temperature 给 0
# 最后把回答文本取出来，变量名叫 answer
#   提示：回答藏在 resp.json() 里，路径是 choices → [0] → message → content
print("\n===== ⑥ 生成：把 top1 塞给模型 =====")
prompt = (
    f"只根据资料回答，资料里没有就说不知道。\n资料：{chunks[best]}\n问题:{question}"
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

print(f"模型回答:{answer}")

# ============ 通关判定：别改这一段 ============
assert len(chunks) == 3
assert len(doc_vecs) == 3 and len(doc_vecs[0]) == 1536
assert len(q_vec) == 1536
assert len(scores) == 3
assert best == 0, f"top1 应该命中 chunk0，你命中的是 chunk{best}"
assert "500" in answer, f"回答里应该包含 500，实际是：{answer}"
print("\n✅ 通关：全程没有一个空，这 7 步是你自己写出来的")
# print("下一步：关掉这个文件，新建一个空文件，凭记忆再写一遍（这次连中文提纲都不看）")
