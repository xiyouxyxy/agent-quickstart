# -*- coding: utf-8 -*-
"""
看懂评测指标.py      ← 只读脚本，跑就行，不要改

它回答五个问题：
  1. 改了切分参数 / 换了 embedding，我怎么知道到底是变好还是变坏？
  2. 命中率（Hit Rate）和 MRR 到底怎么算？
  3. 答案「看着对」和「忠实于资料」有什么区别？—— 忠实度（Faithfulness）
  4. RAGAS 是什么？它凭什么能自动打分？
  5. 面试里说「我做了评测」要能报出哪几个数？

不联网、不花钱、纯算术，秒出结果。

跑法：
  cd D:/agent-learn/project/day6
  D:/agent-learn/project/venv/Scripts/python.exe 看懂评测指标.py
"""

print("=" * 76)
print("第 0 步：为什么非得有指标？")
print("=" * 76)
print("  你的 mini_rag 现在切分是 chunk_size=200、overlap=40，切出 17 块。")
print("  某天你把 chunk_size 改成 120，切成 29 块。")
print("  然后你问「专业版送多少 AI 扩图额度」，答对了。")
print()
print("  问题来了：这是变好了，还是运气好？")
print("  只测一个问题，你永远不知道 —— 因为 RAG 是个概率系统，")
print("  单个问题答对答错，可能只是噪声。")
print()
print("  所以要有「评测集」：一批固定的问题 + 每题的正确答案（人工标好），")
print("  每次改动跑一遍，比数字。数字涨了是改对了，跌了是改砸了。")
print("  这就是「评测」（evaluation）存在的全部意义。\n")


# ==========================================================================
# 第 1 步：造一个小测试集
# ==========================================================================
print("=" * 76)
print("第 1 步：一个最小的评测集长什么样")
print("=" * 76)
print("  每道题只需要两个字段：")
print("    · question    ：用户会怎么问")
print("    · gold_chunk  ：答案在那一块文档里（**人工标的**，这是关键）")
print()
print("  真实项目一般标 30~100 题就够起步了。这里用 5 题演示算法：\n")

TEST_SET = [
    {"q": "专业版每月赠送多少次 AI 扩图额度", "gold": 3},
    {"q": "线上故障多长时间内要上报", "gold": 8},
    {"q": "员工生日有几天假", "gold": 5},
    {"q": "差旅住宿标准是多少", "gold": 1},
    {"q": "值班补贴怎么算", "gold": 7},
]
for i, item in enumerate(TEST_SET, start=1):
    print(f"    Q{i}  {item['q']}")
    print(f"         正确答案在第 {item['gold']} 块（gold_chunk）")
print()

# 两次实验的检索结果，每个列表是「系统返回的 top-3 块编号」，按相关度从高到低
RUN_A = [[3, 7, 1], [2, 8, 5], [9, 4, 6], [1, 2, 3], [4, 7, 6]]   # chunk_size=200
RUN_B = [[3, 2, 1], [8, 1, 5], [6, 5, 9], [1, 2, 3], [7, 6, 4]]   # chunk_size=120
print("  两次实验的检索结果（top-3，按系统认为的相关度排序）：")
print(f"    {'':<6}{'A 组（chunk=200）':<24}{'B 组（chunk=120）'}")
for i, (ra, rb) in enumerate(zip(RUN_A, RUN_B), start=1):
    print(f"    Q{i}   {str(ra):<26}{str(rb)}")
print()


# ==========================================================================
# 第 2 步：命中率 Hit Rate@k
# ==========================================================================
print("=" * 76)
print("第 2 步：命中率 Hit Rate@k（简称 HR@k）")
print("=" * 76)
print("  人话：只看前 k 个里有没有正确答案，有就算 1 分，没有算 0 分。")
print("        它不关心正确答案排第几，只关心「在不在里面」。\n")


def hit_rate(runs, k=3):
    rows = []
    for item, got in zip(TEST_SET, runs):
        hit = item["gold"] in got[:k]
        rows.append((item, got, hit))
    return rows, sum(r[2] for r in rows) / len(rows)


for name, runs in [("A 组（chunk=200）", RUN_A), ("B 组（chunk=120）", RUN_B)]:
    rows, score = hit_rate(runs)
    print(f"  {name}")
    print(f"    {'':<6}{'top-3':<16}{'正确答案':<10}{'命中？'}")
    for i, (item, got, hit) in enumerate(rows, start=1):
        print(f"    Q{i}   {str(got):<18}{item['gold']:<12}{'✅' if hit else '❌'}")
    print(f"    → HR@3 = {sum(r[2] for r in rows)} / {len(rows)} = {score:.2f}\n")

print("  HR@3 的缺点：它很粗。正确答案排第 1 和排第 3，都是 1 分。")
print("  但实际用起来差别很大 —— 排第 1 会被 LLM 优先看到，排第 3 容易被忽略。")
print("  所以还要一个「看名次」的指标。\n")


# ==========================================================================
# 第 3 步：MRR 平均倒数排名
# ==========================================================================
print("=" * 76)
print("第 3 步：MRR（Mean Reciprocal Rank，中文：平均倒数排名）")
print("=" * 76)
print("  人话：每题的得分 = 1 / 正确答案排第几。")
print("        排第 1 → 1 分；排第 2 → 0.5 分；排第 3 → 0.33 分；没进前 k → 0 分。")
print("        最后把所有题的平均一下。\n")


def mrr(runs, k=3):
    rows = []
    for item, got in zip(TEST_SET, runs):
        rank = None
        for pos, chunk_id in enumerate(got[:k], start=1):
            if chunk_id == item["gold"]:
                rank = pos
                break
        rows.append((item, got, rank, 0.0 if rank is None else 1.0 / rank))
    return rows, sum(r[3] for r in rows) / len(rows)


for name, runs in [("A 组（chunk=200）", RUN_A), ("B 组（chunk=120）", RUN_B)]:
    rows, score = mrr(runs)
    print(f"  {name}")
    print(f"    {'':<6}{'top-3':<16}{'正确答案排第几':<16}{'这道题得分'}")
    for i, (item, got, rank, s) in enumerate(rows, start=1):
        rank_txt = "没进前3" if rank is None else f"第 {rank} 名"
        print(f"    Q{i}   {str(got):<18}{rank_txt:<18}{s:.3f}")
    print(f"    → MRR = {score:.3f}\n")


# ==========================================================================
# 第 4 步：把两组摆一起，看指标到底有什么用
# ==========================================================================
print("=" * 76)
print("第 4 步：两组的成绩单")
print("=" * 76)
_, hr_a = hit_rate(RUN_A)
_, hr_b = hit_rate(RUN_B)
_, mrr_a = mrr(RUN_A)
_, mrr_b = mrr(RUN_B)
print(f"    {'':<14}{'chunk=200':<14}{'chunk=120':<14}{'变化'}")
print(f"    {'HR@3':<14}{hr_a:<14.2f}{hr_b:<14.2f}{hr_b - hr_a:+.2f}")
print(f"    {'MRR':<14}{mrr_a:<14.3f}{mrr_b:<14.3f}{mrr_b - mrr_a:+.3f}")
print()
print("  → 只改了一个切分参数，HR@3 从 0.80 涨到 1.00，MRR 从 0.600 涨到 0.900。")
print("    没有这张表，你只会说「我感觉改完好像好了一点」。")
print("    有了这张表，你可以说「我把 chunk_size 从 200 调到 120，")
print("    HR@3 +0.20、MRR +0.30，因为更小的块减少了无关内容的稀释」。")
print("    —— 这句话就是面试里「你做过什么优化、怎么验证的」的标准答案结构。\n")
print("  ⚠️ 但注意：块变多 = 索引更大、召回更慢、塞进 prompt 的碎片更多。")
print("     指标涨了不代表该上线，还要看延迟和成本。这句要主动提，是加分项。\n")


# ==========================================================================
# 第 5 步：检索指标之外，还要看「答案」
# ==========================================================================
print("=" * 76)
print("第 5 步：检索对了，答案就对了？不一定")
print("=" * 76)
print("  上面 HR / MRR 只评「有没有找到正确的资料」。")
print("  但用户看到的是一句话，不是一堆文档块。所以还要评生成出来的答案。")
print()
print("  两个最重要的生成指标：")
print("    ① 忠实度 Faithfulness（中文：忠实度。人话：答案里说的每一句，")
print("       在检索到的资料里都能找到依据吗？找不到 = 编的 = 幻觉）")
print("    ② 答案相关性 Answer Relevancy（中文：答案相关性。人话：")
print("       答案有没有正面回答用户问的那件事？对的但答偏了，这分很低）\n")


# ==========================================================================
# 第 6 步：手算一次 Faithfulness
# ==========================================================================
print("=" * 76)
print("第 6 步：手算 Faithfulness")
print("=" * 76)
ANSWER = "XR-2000 保修 12 个月，从签收日算起，而且可以付费延长到 24 个月。"
CONTEXT = "所有硬件设备（含 XR-2000 型号）自签收之日起享受 12 个月免费保修。"
print(f"  用户问：XR-2000 保修多久？")
print(f"  检索到的资料：{CONTEXT}")
print(f"  模型给的答案：{ANSWER}\n")
print("  做法（人肉版，机器版也是同一套思路）：把答案拆成一句一个断言，逐个查证：\n")
CLAIMS = [
    ("XR-2000 保修 12 个月", "自签收之日起享受 12 个月免费保修", True),
    ("从签收日算起", "自签收之日起", True),
    ("可以付费延长到 24 个月", "（资料里完全没有这句）", False),
]
print(f"    {'断言':<26}{'资料里的依据':<34}{'有据？'}")
for claim, evidence, ok in CLAIMS:
    print(f"    {claim:<26}{evidence:<36}{'✅' if ok else '❌ 编的'}")
supported = sum(1 for c in CLAIMS if c[2])
print(f"\n    → Faithfulness = 有依据的断言 {supported} / 总断言 {len(CLAIMS)} = "
      f"{supported / len(CLAIMS):.2f}\n")
print("  ❌ 这条答案「听起来完全合理」，但三分之一是编的。")
print("     一个只看「答案像不像对的」的评测，是抓不出这种问题的 ——")
print("     这正是忠实度存在的理由，也是 RAG 相对纯 LLM 的核心卖点：")
print("     「我说的每句话都来自你的资料，可以查」。\n")


# ==========================================================================
# 第 7 步：RAGAS 是什么
# ==========================================================================
print("=" * 76)
print("第 7 步：RAGAS（自动评测框架）")
print("=" * 76)
print("  RAGAS（英文全称 Retrieval Augmented Generation Assessment，")
print("        中文：RAG 评测框架。人话：一个开源的 Python 库，")
print("        你给它「问题 + 检索到的资料 + 模型答案」，它自动吐出上面那几个分。）\n")
print("  它凭什么自动打分？—— 用 LLM 当裁判（这个做法叫 LLM-as-a-judge，")
print("                                 中文：让大模型当评委）。")
print()
print("  以忠实度为例，它在背后干的事就是刚才第 6 步那三步：")
print("    1) 叫一个 LLM 把答案拆成若干条断言")
print("    2) 再叫一个 LLM 逐条判断「这条能否从资料里推出」（输出是/否）")
print("    3) 用「是」的条数除以总条数")
print()
print("  优点：不用人工标答案，几百条测试集几分钟跑完。")
print("  缺点：裁判也是模型，会有偏差（比如偏爱长答案、偏爱自己家族的模型），")
print("        所以关键指标要人工抽查一小部分校准。这句能说出来显得很实在。\n")
print("  ⚠️ 你的项目要不要上 RAGAS？现阶段不必。")
print("     先有「能算 HR@3 / MRR 的 20 题测试集」就够了 —— 那是你手写的、")
print("     完全说得清原理的评测；RAGAS 留到后面几天接，作为加分项。\n")


# ==========================================================================
# 第 8 步：面试话术
# ==========================================================================
print("=" * 76)
print("第 8 步：面试怎么说「我的 RAG 做过评测」")
print("=" * 76)
print("""
  问：你怎么知道你的 RAG 好不好？

  答（按这个顺序说，四句）：
    1）我建了一个 20 题的评测集，每题人工标注了「答案在哪个块」。
    2）检索侧看两个指标：HR@3（前 3 个里有没有正确答案）和 MRR（正确答案平均排第几）。
       只看 HR 会漏掉「找到了但排得很后」这种情况，所以两个一起看。
    3）生成侧看忠实度：把答案拆成断言，逐条查能不能从检索到的资料里推出来，
       算有依据的比例。这个数低说明在编，得回去看 prompt 和召回质量。
    4）每次调参（chunk_size、embedding 模型、要不要 rerank）都跑一遍这套，
       记录变化。比如我把 chunk_size 从 200 降到 120，HR@3 涨了 0.2、MRR 涨了 0.3，
       但块数从 17 涨到 29，延迟也涨了，所以最后取了个折中值。

  追问：HR 和 Recall 有什么区别？
    答：HR@k 只问「前 k 个里有没有」，Recall@k 问「所有该找的块找回来几成」。
        如果一道题有 3 个相关块，HR 只要求命中 1 个就算满分，Recall 要求 3 个都找到。
        我们的语料一个问题通常只对应 1 块，所以用 HR 就够；多跳问题必须用 Recall。
""")
print("=" * 76)
print("一句话记住：")
print("  没有评测集的优化 = 靠感觉调参数，面试一问就露。")
print("=" * 76)
