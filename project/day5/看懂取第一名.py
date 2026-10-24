# 看懂"取第一名" —— 三种写法，结果一模一样
"""
你在纠结的这行：
    best = max(range(len(scores)), key=lambda i: scores[i])

它不是新语法，它就是【一个 for 循环找最大值】的压缩写法。
下面三种写法跑出来的 best 都是 0，你先看哪个最像你熟悉的，就把那个当锚点。

运行：
    cd D:/agent-learn/project/day5
    python 看懂取第一名.py
"""

scores = [0.5911, 0.0201, 0.0352]
chunks = [
    "专业版每月赠送 500 次 AI 扩图额度",
    "一线城市住宿费每晚上限 600 元",
    "P0 故障要求 15 分钟内响应",
]

print("=" * 60)
print("写法 A：手写 for 循环（前端思维，最直白）")
print("=" * 60)
best_a = 0                              # 先假设第 0 个最大
for i in range(len(scores)):            # i = 0, 1, 2
    print(f"    比一下：scores[{i}]={scores[i]:.4f}  vs  当前最大 scores[{best_a}]={scores[best_a]:.4f}")
    if scores[i] > scores[best_a]:      # 谁大就换成谁的下标
        best_a = i
print(f"    → best_a = {best_a}")

print()
print("=" * 60)
print("写法 B：max + key（就是你看到的那行）")
print("=" * 60)
print("    候选名单 range(len(scores)) =", list(range(len(scores))))
print("    比较依据 key=lambda i: scores[i] → 把每个 i 翻译成分数：")
for i in range(len(scores)):
    print(f"        i={i} → {scores[i]:.4f}")
best_b = max(range(len(scores)), key=lambda i: scores[i])
print(f"    → max 在这些「分数」里挑最大的，但返回的是它对应的「i」= {best_b}")

print()
print("=" * 60)
print("写法 C：最偷懒的一行")
print("=" * 60)
best_c = scores.index(max(scores))
print(f"    scores.index(max(scores)) = {best_c}")
print("    拆开看：max(scores) 先拿到最大值 0.5911 → scores.index(0.5911) 查它在第几位 = 0")

print()
print("=" * 60)
print("三种写法结果一致吗")
print("=" * 60)
print(f"    A={best_a}   B={best_b}   C={best_c}   →  {'一致 ✅' if best_a == best_b == best_c else '不一致 ❌'}")

print()
print("=" * 60)
print("为什么一定要返回「下标」，不能返回「分数」")
print("=" * 60)
print(f"    max(scores)          → {max(scores)}      ← 只是个数字，没法拿去找原文")
print(f"    scores[best]         → {scores[best_a]}      ← 分数本身")
print(f"    chunks[best]         → {chunks[best_a]}   ← 用下标才取得到这一条")
print()
print("    记住：我们要的不是「多少分」，是「第几名」。")
