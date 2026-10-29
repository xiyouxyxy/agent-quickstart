# -*- coding: utf-8 -*-
"""
看懂importlib这三行.py        ← 只读演示，不要改

专门回答一个问题：
    spec_from_file_location(...)  和  module_from_spec(...)  这两个函数什么意思？

一句话：它们干的事不是「导入模块」，而是「**分三步**把任意一个 .py 文件变成能用的对象」。

    spec_from_file_location  →  开一张取货单（告诉 Python：从哪个文件取、登记成什么名字）
    module_from_spec         →  按取货单造一个空壳（还不能用，里面什么都没有）
    spec.loader.exec_module  →  真正执行那个文件，把里面的东西装进空壳

日常写代码 99% 用不上这三行。为什么我用了？因为演示脚本要加载一个「路径我手上、但名字没登记」的文件。
真实项目里，只要文件在同一目录、名字合法，`import xxx` 一行就够了。

跑法：
  cd D:/agent-learn/project/day7
  D:/agent-learn/project/venv/Scripts/python.exe 看懂importlib这三行.py
"""

import os
import importlib.util

import 答案_key_tools as 正常  # ← 注意：这一行就成功了，说明「同目录 + 合法名字」根本不用绕

HERE = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.join(HERE, "答案_key_tools.py")


def 标题(t):
    print("\n" + "=" * 74)
    print(t)
    print("=" * 74)


# ==========================================================================
标题("第 0 步：先看正常情况——日常就是这么写的")
# ==========================================================================
print("  代码：import 答案_key_tools")
print(f"  结果：直接拿到 {len(正常.TOOLS)} 个工具 {[t['function']['name'] for t in 正常.TOOLS]}")
print()
print("  为什么一行就够？因为 Python 找模块时会先看「当前脚本所在目录」，")
print("  这个文件和答案_key_tools.py 在同一个目录里，所以自己就找到了。")
print()
print("  前端对照：import tools from './tools.js'  —— 同一个思路，只是 Python 少了 './' 这个写法。")


# ==========================================================================
标题("第 1 步：spec_from_file_location —— 开一张「取货单」")
# ==========================================================================
spec = importlib.util.spec_from_file_location("kt", TARGET)

print("  spec = importlib.util.spec_from_file_location('kt', TARGET)")
print()
print(f"  它是什么类型：{type(spec)}")
print(f"  spec.name    = {spec.name!r}          ← 登记用的名字，随你起（这里叫 kt）")
print(f"  spec.origin  = {spec.origin}")
print(f"                  ↑ 「从哪个文件取」")
print(f"  spec.loader  = {spec.loader}")
print(f"                  ↑ 真正干活的工具人（SourceFileLoader = 从源码文件加载）")
print()
print("  ★ 此刻一行代码都没执行，文件也没被读进来。你手上只有一张说明书。")
print("    等价物：前端 const spec = { path: './答案_key_tools.py', name: 'kt' } —— 只是描述，不是模块。")


# ==========================================================================
标题("第 2 步：module_from_spec —— 按取货单造一个空壳")
# ==========================================================================
mod = importlib.util.module_from_spec(spec)

print("  mod = importlib.util.module_from_spec(spec)")
print()
print(f"  它是什么类型：{type(mod)}   ← 真的是个模块对象了")
print(f"  mod.__name__ = {mod.__name__!r}   ← 第 1 步起的名字，被写进去了")
print()
print("  空壳里现在装了哪些名字：")
print(f"    {list(mod.__dict__.keys())}")
print()
print("  全是 Python 自动塞的元信息（__name__ / __file__ / __loader__ 这些）。")
print(f"  关键问题：里面有 TOOLS 吗？→ {hasattr(mod, 'TOOLS')}")
print()
print("  ★ 所以这一步只是「造了个空盒子」。答案_key_tools.py 里的函数、常量，一个都还没进来。")
print("    对照第 0 步：正常 import 完直接就能用 正常.TOOLS，因为 import 帮你把三步都做了。")


# ==========================================================================
标题("第 3 步：exec_module —— 真正执行文件，把东西装进空壳")
# ==========================================================================
print("  spec.loader.exec_module(mod)")
print("  ↑ 这一行才是真正「把对方文件从头到尾跑一遍」的动作")
print()
spec.loader.exec_module(mod)
print("  跑完了。现在再看：")
print(f"    里面有 TOOLS 吗？  → {hasattr(mod, 'TOOLS')}")
print(f"    len(mod.TOOLS)     → {len(mod.TOOLS)}")
print(f"    工具名             → {[t['function']['name'] for t in mod.TOOLS]}")
print()
print("  ★ 注意：刚才这一次执行，一个网络请求都没发。")
print("    因为答案_key_tools.py 里 Retriever 是懒加载的（顶层只有 _RETRIEVER = None）。")
print("    如果它顶层写了 retriever = Retriever(chunks)，这里就会卡住去请求 embedding ——")
print("    这就是「import 副作用」，也是今天 tools.py 必须做成懒加载的原因。")


# ==========================================================================
标题("三步对照表（记这张表，别背代码）")
# ==========================================================================
rows = [
    ("① spec_from_file_location", "开取货单", "一个 spec 对象（说明书）", "没有"),
    ("② module_from_spec", "造空壳", "一个 module 对象（空盒子）", "没有"),
    ("③ spec.loader.exec_module", "执行文件", "盒子被装满（有 TOOLS 了）", "有，全部"),
]
print(f"  {'步骤':<26}{'做的事':<12}{'你拿到什么':<28}{'代码跑了吗'}")
print("  " + "-" * 82)
for a, b, c, d in rows:
    print(f"  {a:<26}{b:<12}{c:<28}{d}")

print()
print("  最后一句实话：这三行是 importlib 的「绕路写法」。")
print("  你以后写项目，正常就是 import tools / from tools import TOOLS, search_kb。")
print("  只有当文件不在当前目录、或者名字是运行时才知道（比如插件目录里扫出来的文件）时，")
print("  才需要这三行。记不住完全不影响你今天干活。")
