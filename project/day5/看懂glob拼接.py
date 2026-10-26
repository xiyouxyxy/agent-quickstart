# 看懂 glob 那一步的拼接 —— 为什么必须先拼成一个字符串
"""
你问：为什么要拼接 DOC_DIR 和 "*.md"？

一句话：**glob.glob() 只收「一个字符串」，它不会自己帮你把目录和文件模式接起来。**
而且字符串直接相加会少一个分隔符，粘成一个找不到的路径。

这个脚本把 6 种写法都跑一遍，直接看结果。

运行：
    cd D:/agent-learn/project/day5
    python 看懂glob拼接.py
"""

import os
import glob

DOC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs")

print("=" * 70)
print("第 0 步：先看清楚 glob.glob() 到底要什么")
print("=" * 70)
print("    glob.glob(pattern) 只有一个参数，叫 pattern，类型是「字符串」。")
print("    它不接收两个参数（目录、文件名），所以你必须先自己拼成一个字符串。")
print("    然后它在里面找 * 号，把 * 展开成真实文件名。")
print()

# =====================================================================
print("=" * 70)
print("第 1 步：★ 直接字符串相加会怎样（不 join 的后果）")
print("=" * 70)
wrong = DOC_DIR + "*.md"
print(f"    DOC_DIR          = {DOC_DIR}")
print(f'    DOC_DIR + "*.md" = {wrong}')
print()
print("    ❌ 看结尾：docs*.md —— 少了一个反斜杠，变成了「名字叫 docs*.md 的文件」")
print(f"    这个路径存在吗：{os.path.exists(wrong)}")
print()

# =====================================================================
print("=" * 70)
print("第 2 步：6 种写法跑一遍，看各自返回什么")
print("=" * 70)


def show(label, pattern, mark):
    try:
        res = glob.glob(pattern)
    except Exception as e:
        print(f"    {mark} {label}")
        print(f"        传进去：{pattern}")
        print(f"        异常：  {type(e).__name__}: {e}")
        print()
        return
    n = len(res)
    print(f"    {mark} {label}")
    print(f"        传进去：{pattern}")
    print(f"        拿到 {n} 个：{[os.path.basename(x) for x in res] if n else '空列表 []'}")
    print()


show('① 只传目录，不带 * 号', DOC_DIR, "…")
show('② 字符串相加（漏分隔符）', DOC_DIR + "*.md", "❌")
show('③ 手写反斜杠（Windows 专用）', DOC_DIR + "\\*.md", "⚠️")
show('④ 手写正斜杠', DOC_DIR + "/*.md", "⚠️")
show('⑤ os.path.join（正确写法）', os.path.join(DOC_DIR, "*.md"), "✅")
show('⑥ 只传目录 + 通配子目录', os.path.join(DOC_DIR, "**", "*.md"), "…")

# =====================================================================
print("=" * 70)
print("第 3 步：逐条解释上面的结果")
print("=" * 70)
print("    ① 只传目录 DOC_DIR")
print("       → 返回 [目录自己] 或 []。因为这里没有 * 号，glob 就只是判断")
print("         「这个路径存不存在」，存在就把它自己还给你，不会列里面的文件。")
print("       → 报错不是它的事，它就是「你给什么模式，我按模式匹配」。")
print()
print("    ② 漏了分隔符")
print("       → 匹配的是一个叫 docs*.md 的东西，不存在，返回空列表。")
print("       → 这就是「为什么必须拼接」的第一个理由：不拼分隔符就粘成一坨。")
print()
print("    ③ 手写 \\ 和 ④ 手写 /")
print("       → 在 Windows 上都能跑，结果一模一样。")
print("       → 但 ③ 换到 Linux/macOS 会坏（那边分隔符是 /）；")
print("         ④ 换到某些老版本 Python + Windows 组合会有转义风险。")
print("       → 所以两者都不如 join 稳：join 会按当前系统给正确的分隔符。")
print()
print("    ⑤ os.path.join 拼出来的，就是官方推荐写法。")
print()
print("    ⑥ ** 意思是「任意层子目录」。docs 下面没有子目录，所以是 0 个。")
print("       （如果要递归，还得加 recursive=True）")
print()

# =====================================================================
print("=" * 70)
print("第 4 步：为什么第二段是 \"*.md\" 而不是 \".md\"")
print("=" * 70)
print("    * 是通配符，意思是「任意字符，任意长度」。")
print()
for p in [".md", "*.md", "0*.md", "01-*.md"]:
    res = glob.glob(os.path.join(DOC_DIR, p))
    print(f'    "{p:<12}" → {len(res)} 个  {[os.path.basename(x)[:12] for x in res]}')
print()
print('    所以 "*.md" = 「任意名字 + .md 结尾」= 所有 markdown 文件。')
print('    写成 ".md" 就变成「名字正好是 .md 的文件」，一般不存在。')
print()

# =====================================================================
print("=" * 70)
print("第 5 步：那能不能不用 glob？对比 os.listdir")
print("=" * 70)
names = os.listdir(DOC_DIR)
print(f"    os.listdir(DOC_DIR) 返回 {len(names)} 个：")
for n in names:
    print(f"        {n!r}")
print()
print("    ⚠️ 注意区别：listdir 给的是**纯文件名**（'01-xxx.md'），")
print("       不是完整路径；而且要你自己写 for 循环 + if 判断后缀来过滤。")
print()
print("    glob 的好处正是这两点：")
print("      ① 直接给你**完整路径**，拿到就能 open()")
print("      ② 用通配符一行搞定筛选，不用自己写 if x.endswith('.md')")
print()
print("    listdir 版本大概要这么写（glob 一行就顶了）：")
print("        for name in os.listdir(DOC_DIR):")
print("            if name.endswith('.md'):")
print("                path = os.path.join(DOC_DIR, name)   ← 你还得自己拼回来")
print()

# =====================================================================
print("=" * 70)
print("第 6 步：完整链路，从目录到文件列表")
print("=" * 70)
print("    DOC_DIR                       一个目录")
print("      ↓ os.path.join + \"*.md\"     拼成「带通配符的完整路径」")
print("    DOC_DIR\\*.md                  一个模式字符串")
print("      ↓ glob.glob()               按模式匹配，展开成真实文件")
print("    [完整路径1, 完整路径2, ...]    一个列表")
print("      ↓ sorted()                  钉死顺序")
print("    [有序的完整路径列表]")
print("      ↓ for path in ...: open(path)")
print("    每个文件的内容")
print()
print("    实测这条链路的结果：")
final = sorted(glob.glob(os.path.join(DOC_DIR, "*.md")))
for i, p in enumerate(final):
    print(f"        [{i}] {os.path.basename(p)}")
print()
print("=" * 70)
print("一句话记住：glob 要的是「一条完整的、带通配符的路径字符串」。")
print("  join 的责任就是把这个字符串拼对 —— 别漏分隔符，别写死斜杠。")
print("=" * 70)
