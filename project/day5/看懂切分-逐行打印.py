# 看懂切分 —— 为什么 L5 的 mini_rag 看起来和 L3「完全不一样」
"""
    L3（你写通的）              L5（mini_rag.py）
    ─────────────────           ─────────────────
    chunks = [手写3句话]    →   load_docs() 从 docs/ 读 3 个 md     ← 新
                            →   split_text() 把长文切成块           ← 新
    embed(chunks)               embed(chunks)                      ← 一样
    算相似度                     算相似度                          ← 一样
    取第一名                     取第一名 + 阈值拒答                ← 多了个 if
    拼 prompt 调模型             拼 prompt 调模型                   ← 一样

所以不是「换了一套东西」，是**同一个流程换了个更大的语料**。
你 L3 之所以觉得简单，是因为我手写的 3 句话本来就不用切。

这个脚本只干一件事：把 split_text 那 6 行代码每一刀都打印出来，让你看见它到底在切什么。

运行：
    cd D:/agent-learn/project/day5
    python 看懂切分-逐行打印.py
"""

TEXT = "订单满三百元包邮，生鲜类目除外，偏远地区需要额外补差价。"
print("=" * 62)
print("第 0 步：准备一段 28 字的中文（假装它是从 md 读出来的一整篇）")
print("=" * 62)
print(f"    原文：{TEXT}")
print(f"    字数：{len(TEXT)}")
print()

# ---------------------------------------------------------------
# 用「尺子」把每个字的下标标出来，后面看切片就靠它
# ---------------------------------------------------------------
print("=" * 62)
print("第 1 步：给每个字编上座位号（Python 的下标从 0 开始）")
print("=" * 62)
print("    下标：", " ".join(str(i // 10) for i in range(len(TEXT))))
print("          ", " ".join(str(i % 10) for i in range(len(TEXT))))
print("    字：  ", " ".join(TEXT))
print()

# ---------------------------------------------------------------
# 核心：split_text 的写法
# ---------------------------------------------------------------
CHUNK_SIZE = 10
OVERLAP = 3
STEP = CHUNK_SIZE - OVERLAP  # ← 这就是 start += chunk_size - overlap 里那一步


def split_text(text, source, chunk_size=200, overlap=40):
    """和 mini_rag.py 里一字不差，只是把参数改成看得见的大小"""
    chunks = []
    start = 0
    while start < len(text):
        piece = text[start : start + chunk_size]
        if piece.strip():
            chunks.append({"source": source, "text": piece})
        start += chunk_size - overlap  # ← 关键那一行
    return chunks


print("=" * 62)
print(f"第 2 步：chunk_size={CHUNK_SIZE}，overlap={OVERLAP}")
print("=" * 62)
print(f"    一刀切 {CHUNK_SIZE} 个字，但相邻两刀要重叠 {OVERLAP} 个字。")
print(f"    所以每切完一刀，起点只往前挪 {CHUNK_SIZE} - {OVERLAP} = {STEP} 个字。")
print(
    f"    👉 不是挪 {CHUNK_SIZE}，是挪 {STEP}。这就是「减」的原因，减掉的正是重叠部分。"
)
print()

# ---------------------------------------------------------------
# 手工模拟前 4 刀，每刀都打印 start / end / 切到什么
# ---------------------------------------------------------------
print("=" * 62)
print("第 3 步：一刀一刀看（start 怎么涨、每刀切到哪）")
print("=" * 62)
start = 0
round_no = 1
while start < len(TEXT):
    end = min(start + CHUNK_SIZE, len(TEXT))  # 最后一刀会短，所以要 min
    piece = TEXT[start:end]
    print(f"    第{round_no}刀  start={start:<3} end={end:<3}  切到：{piece}")
    print(f"            {' ' * start}{'^' * len(piece)}")
    start += CHUNK_SIZE - OVERLAP
    round_no += 1
print(f"    结束：start 涨到 {start}，已经 >= 总长度 {len(TEXT)}，while 停下")
print()

print("=" * 62)
print("第 4 步：把切出来的块并排摆着，看「重叠」长什么样")
print("=" * 62)
chunks = split_text(TEXT, "demo.md", CHUNK_SIZE, OVERLAP)
for i, c in enumerate(chunks):
    print(f"    chunk{i}：{c['text']}")
print()
print("    仔细看 chunk0 的尾巴和 chunk1 的开头：")
print(f"      chunk0 结尾 3 个字 → 「{chunks[0]['text'][-OVERLAP:]}」")
print(f"      chunk1 开头 3 个字 → 「{chunks[1]['text'][:OVERLAP]}」")
print("      👆 一模一样的 3 个字。这就是 overlap，同一段内容在两块里各出现一次。")
print()

# ---------------------------------------------------------------
# overlap=0 会怎样 —— 这才是理解 overlap 为什么要存在的地方
# ---------------------------------------------------------------
print("=" * 62)
print("第 5 步：如果 overlap=0（不重叠），会发生什么？")
print("=" * 62)
no_overlap = split_text(TEXT, "demo.md", CHUNK_SIZE, 0)
for i, c in enumerate(no_overlap):
    print(f"    chunk{i}：{c['text']}")
print()
print("    看「生鲜」这两个字：")
print(f"      chunk0 里有个「生」：...{no_overlap[0]['text'][-2:]}")
print(f"      chunk1 里有个「鲜」：{no_overlap[1]['text'][:2]}...")
print("      👆「生鲜类目除外」这条规则被硬生生劈成两半，各待在一块里。")
print("      → 如果用户问「生鲜包邮吗」，检索到 chunk1 只看到「鲜类目除外」，")
print("        语义已经残了，模型很可能答错。**这就是切分要留重叠的原因。**")
print()

# ---------------------------------------------------------------
# 回应她「L3 不用切」这个事实
# ---------------------------------------------------------------
print("=" * 62)
print("第 6 步：回头看 L3 —— 为什么你写 L3 时根本没有这一步？")
print("=" * 62)
L3_chunks = [
    "云图库专业版每月赠送 500 次 AI 扩图额度。",
    "免费版单个账号最多存 1000 张图片。",
    "团队协作需要升级到企业版。",
]
print("    L3 的 chunks 是你自己手打的：")
for i, c in enumerate(L3_chunks):
    print(f"      chunks[{i}] = {c}   （{len(c)} 字）")
print()
print("    每句话本来就 20 字上下，比 chunk_size=200 还短，")
print("    根本没东西可切 —— 所以你 L3 跳过了切分，完全正常。")
print("    L5 的 docs/ 里每篇几千字，不切就塞不进 prompt，所以必须补这一步。")
print()
print("=" * 62)
print("一句话记住：L5 = L3 的流程 + 真实文件 + 切分 + 阈值拒答")
print("           后面「向量化 / 算相似度 / 取第一 / 拼 prompt」四步，一行都没变。")
print("=" * 62)
