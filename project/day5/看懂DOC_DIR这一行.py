# 单独拆解这一行 —— 四个东西各自在干什么
"""
这一行：
    DOC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs")

里面有 4 个东西，从里往外是：
    __file__            ← 变量，不是函数
    os.path.abspath()   ← 相对路径 → 绝对路径
    os.path.dirname()   ← 完整路径 → 所在目录
    os.path.join()      ← 两段拼成一段

这个脚本把这 4 个各自拆开跑，每个都显示「输入 → 输出」，
并且演示 3 个如果不注意就会踩的坑。

前端对照（你熟了再看这个表会更快）：
    Python                    Node.js
    __file__                  __filename
    os.path.abspath(p)        path.resolve(p)
    os.path.dirname(p)        path.dirname(p)
    os.path.join(a, b)        path.join(a, b)
  概念几乎一一对应，只是 Python 的模块叫 os.path，Node 叫 path。

运行：
    cd D:/agent-learn/project/day5
    python 看懂DOC_DIR这一行.py
"""

import os

print("=" * 70)
print("第 0 步：先给答案，这一行算出来的值")
print("=" * 70)
DOC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs")
print(f"    DOC_DIR = {DOC_DIR}")
print()

# =====================================================================
print("=" * 70)
print("第 1 步：__file__ —— 它是个变量，不是函数")
print("=" * 70)
print(f"    __file__ = {__file__!r}")
print()
print("    这是 Python 在运行脚本前自动塞进来的一个全局变量，值是「当前 .py 文件的路径」。")
print("    它不需要 import，也不能调用（不是 __file__()，是 __file__）。")
print()
is_abs = os.path.isabs(__file__)
print(f"    os.path.isabs(__file__) = {is_abs}")
if is_abs:
    print("    👉 你这台机器的 Python（3.9+）已经把 __file__ 自动变成绝对路径了。")
    print("       所以这一行里的 abspath() 对 __file__ 来说其实是「多余的保险」。")
    print("       但为什么还要写？见第 2 步。")
else:
    print("    👉 你这台机器的 __file__ 是相对路径，abspath 是必需的。")
print()

# =====================================================================
print("=" * 70)
print("第 2 步：os.path.abspath —— 相对路径 → 绝对路径，基准是「当前工作目录」")
print("=" * 70)
print(f"    当前工作目录 os.getcwd() = {os.getcwd()}")
print()
cases = ["docs", "mini-rag.py", "../day4", "D:/already/absolute.md"]
for p in cases:
    print(f"      abspath({p!r:<24}) = {os.path.abspath(p)}")
print()
print("    ⚠️ 关键点：abspath 的基准是 os.getcwd()（你敲命令时所在的目录），")
print("       不是脚本所在目录！所以同一个相对路径，从不同地方运行结果完全不同：")
print()
print("        在 D:/agent-learn/project/day5 下运行 → abspath('docs') = D:\\agent-learn\\project\\day5\\docs")
print("        在 D:/agent-learn 下运行           → abspath('docs') = D:\\agent-learn\\docs   ← 找错了")
print()
print("    👉 这就是为什么必须先 abspath 再 dirname：把「取决于 cwd」变成「取决于脚本自己」。")
print()

# =====================================================================
print("=" * 70)
print("第 3 步：os.path.dirname —— 去掉最后一段，留下目录")
print("=" * 70)
for p in [
    r"D:\agent-learn\project\day5\mini-rag.py",
    r"D:\agent-learn\project\day5",
    "mini-rag.py",
]:
    print(f"      dirname({p!r:<46}) = {os.path.dirname(p)!r}")
print()
print("    ⚠️ 坑在这里：最后一行 dirname('mini-rag.py') 返回的是空字符串 ''，不是 '.'")
print("       因为「文件名前面没有目录」这件事，它用空串表示。")
print("       所以如果你的 __file__ 是相对路径 'mini-rag.py'，")
print("       dirname 会给你 ''，后面 join('', 'docs') 就变回相对路径 'docs' —— 白算了。")
print()
print("    👉 这就是第 2 步那个「多余的保险」为什么值得留着：")
print("       万一运行环境给的 __file__ 是相对路径（Python 3.8 及更早就是这样），")
print("       先 abspath 一层，dirname 才拿得到真目录。")
print()

# =====================================================================
print("=" * 70)
print("第 4 步：os.path.join —— 把两段拼成一段")
print("=" * 70)
pairs = [
    (r"D:\agent-learn\project\day5", "docs"),
    (r"D:\agent-learn\project\day5" + "\\", "docs"),
    ("", "docs"),
    (r"D:\agent-learn", "D:/other/absolute"),
]
for a, b in pairs:
    print(f"      join({a!r:<36}, {b!r:<22}) = {os.path.join(a, b)!r}")
print()
print("    join 干了三件你没让它干的事：")
print("      ① 用**当前系统的分隔符**连接：Windows 给 \\，Linux/macOS 给 /")
print("         （你在代码里写死 '/' 或写死 '\\\\'，换系统都可能坏）")
print("      ② 自动处理多余的斜杠：'day5\\\\' + 'docs' 不会变成 'day5\\\\docs' 双层")
print("      ③ ⚠️ 如果后一段是**绝对路径**，前面整段会被丢掉！看最后一行示例。")
print()
print("      第 ③ 条是个隐蔽坑：join('D:/a', '/b') 在 Windows/Unix 上结果不同，")
print("      所以传参数时别把绝对路径塞进第二段。")
print()

# =====================================================================
print("=" * 70)
print("第 5 步：从里往外读这一行（执行顺序）")
print("=" * 70)
print("    DOC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), \"docs\")")
print()
print("    读的顺序是「括号最里面的先算」：")
print("      ① __file__                          → 拿脚本自己的路径")
print("      ② os.path.abspath(__file__)         → 保证是绝对路径")
print("      ③ os.path.dirname(...)              → 去掉文件名，得到所在目录")
print("      ④ os.path.join(..., \"docs\")         → 目录 + docs")
print()
print("    一行一行验证：")
print(f"      ① {__file__!r}")
print(f"      ② {os.path.abspath(__file__)!r}")
print(f"      ③ {os.path.dirname(os.path.abspath(__file__))!r}")
print(f"      ④ {os.path.join(os.path.dirname(os.path.abspath(__file__)), 'docs')!r}")
print()

# =====================================================================
print("=" * 70)
print("第 6 步：验证它真的能用 —— 拿这个目录去读文件")
print("=" * 70)
import glob
files = sorted(glob.glob(os.path.join(DOC_DIR, "*.md")))
print(f"    glob(join(DOC_DIR, '*.md')) 找到 {len(files)} 个文件：")
for f in files:
    print(f"      {os.path.basename(f)}")
print()
print("    如果 DOC_DIR 算错了，这里会是 0 个文件 —— 所以「读到 3 个」本身就是验证。")
print()

# =====================================================================
print("=" * 70)
print("第 7 步：顺序反过来会怎样（错误写法对比）")
print("=" * 70)
print("    错误写法 A：dirname 在 abspath 之前")
print("        dirname(__file__)  ← 如果 __file__ 恰好是相对路径，返回 ''")
print(f"        演示：dirname('mini-rag.py') = {os.path.dirname('mini-rag.py')!r}")
print("        → join('', 'docs') = " + repr(os.path.join("", "docs")) + "  （还是相对路径，白干）")
print()
print("    错误写法 B：干脆写死相对路径")
print("        DOC_DIR = 'docs'")
print("        → 只有从 day5 目录下运行才对；")
print("          从别处运行、或以后被别的脚本 import，立刻找不到文件。")
print()
print("    正确写法（就是原来那行）：")
print("        锚定 __file__ → abspath → dirname → join")
print("        → 无论从哪个目录运行、无论谁 import 它，永远指向同一个真实位置。")
print()
print("=" * 70)
print("一句话记住：这一行是在回答「docs 文件夹到底在哪」——")
print("  用「脚本自己所在的位置」当地基，而不是用「你此刻站在哪」。")
print("=" * 70)
