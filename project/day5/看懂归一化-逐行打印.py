# 看懂归一化 —— 把一个箭头缩成「长度刚好等于 1」是什么意思
"""
你问的「归一化」（中文叫归一化，英文 normalization），碰到它的地方是这行：

    faiss.normalize_L2(doc_vecs)      # 查表：把每条向量的长度缩成 1

这个脚本不调 API，纯算术，一秒跑完。跑完你会知道三件事：
    ① 归一化到底做了什么（手算一遍）
    ② 为什么做完它，「内积」就等于「余弦相似度」
    ③ 为什么不做会出事（不相关的长文本会被排到第一）

运行：
    cd D:/agent-learn/project/day5
    python 看懂归一化-逐行打印.py
"""

import math

def norm(v):
    """求一个向量的长度（模长）。二维就是勾股定理，N 维就多开几项。"""
    return math.sqrt(sum(x * x for x in v))

def dot(a, b):
    """内积：同位相乘再相加（你 L3 写的那行）"""
    return sum(x * y for x, y in zip(a, b))

# =============================================================
print("=" * 66)
print("第 1 步：先说「长度」（学术名叫模长 / norm）是什么")
print("=" * 66)
V = [3, 4]
print(f"    有个向量 [3, 4]，意思是：往右走 3 步，往上走 4 步。")
print(f"    那它这条斜边有多长？勾股定理：√(3² + 4²) = √(9+16) = √25 = {norm(V)}")
print(f"    👉 这个 {norm(V)} 就是它的「长度」。")
print()
print("    ⚠️ 注意：向量有 1536 维，但算法完全一样，")
print("       只是从「√(a²+b²)」变成「√(a²+b²+c²+...+1536 个)」。")
print()

# =============================================================
print("=" * 66)
print("第 2 步：归一化 = 每个分量 ÷ 长度")
print("=" * 66)
length = norm(V)
normalized = [x / length for x in V]
print(f"    原向量：      {V}        长度 = {length}")
print(f"    除以长度 {length} 后：{normalized}")
print(f"    新向量长度 =  {norm(normalized)}   ← 就是 1（浮点误差忽略）")
print()
print("    👉 归一化就一句话：把这条箭头的长度硬缩成 1，方向一点都不动。")
print()

# =============================================================
print("=" * 66)
print("第 3 步：方向真的没动吗？看比例")
print("=" * 66)
print(f"    原向量 3 : 4        = {3/4}")
print(f"    新向量 0.6 : 0.8    = {0.6/0.8}")
print(f"    {'✅ 比例一样，指向同一个方向' if abs(3/4 - 0.6/0.8) < 1e-9 else '❌'}")
print()
print("    👉 长度变了，方向没变。所以「归一化」不改变语义，只改变长度。")
print()

# =============================================================
print("=" * 66)
print("第 4 步：为什么要这么做？因为归一化后「内积」== 「余弦」")
print("=" * 66)
A = [3, 4]        # 短的
B = [30, 40]      # 同方向，但长度是 A 的 10 倍（假装它是一段很长的文本）

print(f"    两个向量：A={A}（长 {norm(A)}）   B={B}（长 {norm(B)}）")
print(f"    它们指向同一个方向。")
print()
print(f"    ① 直接算内积：{dot(A, B)}   ← 差了 10 倍距离吧？")
print(f"       这叫「内积」，它同时含了「方向」和「长度」两个信息，糊在一起了。")
print()
cos = dot(A, B) / (norm(A) * norm(B))
print(f"    ② 余弦相似度 = 内积 ÷ (|A| × |B|) = {dot(A,B)} ÷ ({norm(A)}×{norm(B)}) = {cos}")
print(f"       余弦只留「方向」，把长度除掉了 → 所以同方向答案是 1.0（完全相似）。")
print()
A_n = [x / norm(A) for x in A]
B_n = [x / norm(B) for x in B]
print(f"    ③ 先把两个都归一化：A→{A_n}   B→{B_n}")
print(f"       再算内积 = {dot(A_n, B_n)}")
print()
print("    ╔══════════════════════════════════════════════════════════╗")
print("    ║  归一化之后，内积 = 1.0 = 余弦。两个结果一模一样了。       ║")
print("    ║  这就是为什么用 FAISS 的 IndexFlatIP（内积版）之前，      ║")
print("    ║  必须先 normalize：让「内积」替「余弦」干活，省一次除法。  ║")
print("    ╚══════════════════════════════════════════════════════════╝")
print()

# =============================================================
print("=" * 66)
print("第 5 步：不做归一化会出什么事？（这才是关键）")
print("=" * 66)
q = [1.0, 0.0]          # 用户的问题方向：正右
doc_short = [0.99, 0.10]  # 相关，但向量短
doc_long  = [5.0, 5.0]    # 不相关（偏了 45 度），但向量长

print(f"    用户问题 q = {q}   （方向：正右）")
print(f"    资料 A（相关）= {doc_short}")
print(f"    资料 B（不相关，但向量很长）= {doc_long}")
print()
print("    --- 不归一化，直接算内积 ---")
sA, sB = dot(q, doc_short), dot(q, doc_long)
print(f"      A 的内积 = {sA:.4f}")
print(f"      B 的内积 = {sB:.4f}")
print(f"      {'❌ B 赢了！明明不相关却排第一 —— 就因为它向量长' if sB > sA else 'A 赢'}")
print()
print("    --- 归一化之后再算内积（= 余弦）---")
q_n  = [x / norm(q) for x in q]
dA_n = [x / norm(doc_short) for x in doc_short]
dB_n = [x / norm(doc_long)  for x in doc_long]
cA, cB = dot(q_n, dA_n), dot(q_n, dB_n)
print(f"      A 的余弦 = {cA:.4f}")
print(f"      B 的余弦 = {cB:.4f}")
print(f"      {'✅ A 赢了，相关的排第一' if cA > cB else '❌'}")
print()
print("    为什么？因为「长向量」在不同尺度下天然吃亏/占便宜：")
print("    一段很长的文本，累加出来的向量长度会更大，内积也被放大，")
print("    于是一堆长文档永远压着短文档 —— 这叫「长度偏置」，纯属噪声。")
print("    归一化把所有人的长度拉平成 1，只比方向，才公平。")
print()

# =============================================================
print("=" * 66)
print("第 6 步：那你的项目到底要不要写 normalize？")
print("=" * 66)
print("    你之前跑 embed_demo.py 时打印过一行：模长 = 1.0")
print("    👉 说明 MiniMax 的 embo-01 在接口内部已经帮你归一化过了。")
print()
print("    所以：")
print("      • 用 MiniMax embo-01 → 不用再写，本来就都是 1")
print("      • 换 OpenAI text-embedding-3 → 默认不归一化，必须自己写")
print("      • 换 BGE / m3e 等开源模型 → 看它文档，多数也要自己写")
print()
print("    面试怎么答：")
print("      「我把 FAISS 的索引换成内积版 IndexFlatIP 来算相似度；")
print("        内积要等价于余弦，前提是向量长度都为 1，")
print("        所以存入前统一做 L2 归一化。我用的 embedding 接口返回的")
print("        向量本身已经归一化过，代码里也保留了这步，防止换模型时踩坑。」")
print()
print("=" * 66)
print("一句话记住：归一化 = 把箭头长度压成 1，方向不动；")
print("           目的是让「内积」直接等于「余弦」，避免长度干扰排序。")
print("=" * 66)
