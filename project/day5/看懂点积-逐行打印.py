# 看懂点积 —— 把 sum(a*b for a,b in zip(...)) 每一步打印出来
"""
你问的那行：sum(a * b for a, b in zip(q_vec, v))
这里用 3 维向量代替 1536 维，因为电脑算得快但你眼睛看得清的只有 3 个。

运行：
    cd D:/agent-learn/project/day5
    python 看懂点积-逐行打印.py
"""

A = [1, 2, 2]      # 假装这是 q_vec
C = [2, 0, 1]      # 假装这是某一条 chunk 的向量

print("=" * 60)
print("第 1 步：zip 按位置把两个数组配成一对一对（元组）")
print("=" * 60)
for pair in zip(A, C):
    print("    ", pair)

print()
print("=" * 60)
print("第 2 步：for a, b in ... 是「解包」，a 和 b 各自是一个数字")
print("=" * 60)
for a, b in zip(A, C):
    print(f"    a={a}  b={b}    a*b={a*b}    a 的类型={type(a).__name__}")
print("    ↑ 注意 a 的类型是 int（一个数），不是 list。")
print("      所以 a*b 是「两个数字相乘」，不是「两个数组逐位相乘」。")

print()
print("=" * 60)
print("第 3 步：sum 把所有乘积加起来")
print("=" * 60)
products = [a * b for a, b in zip(A, C)]     # 先存成列表，看清楚有哪些乘积
print("    所有乘积 =", products)
print("    求和     =", sum(products))

print()
print("=" * 60)
print("第 4 步：生成器表达式 = 第 2、3 步合并，边算边加，不生成中间列表")
print("=" * 60)
total = sum(a * b for a, b in zip(A, C))
print("    sum(a*b for a, b in zip(A, C)) =", total)
print("    对照手算：A·C = 1×2 + 2×0 + 2×1 = 2 + 0 + 2 = 4  ✅")

print()
print("=" * 60)
print("第 5 步（坑）：zip 长度不一样时【不报错】，直接截断")
print("=" * 60)
print("    list(zip([1,2,3], [10,20])) =", list(zip([1, 2, 3], [10, 20])))
print("    ↑ 第三个元素 3 被悄悄丢掉了，一点报错都没有。")
print("      所以如果 query 和 chunk 用了两个维度不同的 embedding 模型，")
print("      这里的点积会「少算一半」还算出一个漂亮数字 —— 这就是为什么")
print("      「同一个知识库必须用同一个 embedding 模型」。")

print()
print("=" * 60)
print("第 6 步：为什么要 zip —— 必须「同位配对」")
print("=" * 60)
right = sum(a * b for a, b in zip(A, C))
print(f"    正确配对（同位相乘）  1×2 + 2×0 + 2×1 = {right}")
mis = sum(A[i] * C[(i + 1) % 3] for i in range(3))     # 故意错开一位
print(f"    错位一位（0位乘1位…） 1×0 + 2×1 + 2×2 = {mis}")
print("    ↑ 两个数都「看起来正常」，但错位的那个没有任何数学意义，")
print("      因为它把「第 0 维的特征」乘上了「第 1 维的特征」，量纲都不一样。")
print()
print("    不用 zip 的笨办法是两个 for 嵌套：")
print(f"    {len(A)} 维 → {len(A)} × {len(A)} = {len(A) ** 2} 次乘法（外积，得到一张矩阵）")
print(f"    真实 1536 维 → 1536 × 1536 = {1536 * 1536} 次乘法，而且算出的是矩阵不是分数")
print("    zip 的作用 = 把「两两全乘」限制成「只跟同位那个乘」")

print()
print("=" * 60)
print("第 7 步：前端写法对照（其实一模一样）")
print("=" * 60)
print("    JS: q_vec.reduce((s, a, i) => s + a * v[i], 0)")
print("    zip 干的事 = JS 里那个 i（按下标取值）")
print("    sum 干的事 = reduce 里那个累加器 s")
