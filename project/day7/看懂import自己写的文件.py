# -*- coding: utf-8 -*-
"""
看懂import自己写的文件.py        ← 只读演示，不要改

目的：把「模块 / import / __name__ / 副作用」这四件事用看得见的方式跑一遍。
全程不联网、不花钱，随便跑多少次。

跑法：
  cd D:/agent-learn/project/day7
  D:/agent-learn/project/venv/Scripts/python.exe 看懂import自己写的文件.py
"""

import os
import sys
import math
import importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))


def 标题(t):
    print("\n" + "=" * 74)
    print(t)
    print("=" * 74)


# ==========================================================================
标题("第 1 步：__name__ 是什么")
# ==========================================================================
print("  直接运行这个文件时，Python 会给它取个名字叫 __main__")
print(f"  现在这个文件的 __name__ = {__name__!r}") # 打印 __name__ = '__main__'
print()
print("  而别人 import 它的时候，它的 __name__ 会变成文件名（不含 .py）")
print("  这就是为什么每个脚本末尾都写：")
print("      if __name__ == '__main__':")
print("  意思是「只有我被直接运行时，才执行下面这些」——被 import 时那段不跑。")


# ==========================================================================
标题("第 2 步：import 一个标准库，看看它到底给了你什么")
# ==========================================================================
print(f"  math.__name__ = {math.__name__!r}") 
# math.__name__ = 'math'

print(f"  math 身上挂着 {len([x for x in dir(math) if not x.startswith('_')])} 个可用的名字，前 6 个：")
print(f"    {[x for x in dir(math) if not x.startswith('_')][:6]}")
# ['acos', 'acosh', 'asin', 'asinh', 'atan', 'atan2']
print(f"  math.sqrt(16) = {math.sqrt(16)}")
print()
print("  一句话：import math = 执行 math.py + 把结果打包成一个叫 math 的对象塞给你。")
print("  你写 math.sqrt，就是「从 math 这个包里拿 sqrt 这个名字」。")
print("  前端等价物：import math from './math.js' —— 一模一样的思路。")


# ==========================================================================
标题("第 3 步：为什么 day6 那个文件 import 不了（今天的核心动机）")
# ==========================================================================
print("  day6 的主文件叫：D6-混合检索和rerank.py")
print("  你想写：  import D6-混合检索和rerank")
print()
print("  Python 读这行会切成：import D6  −  混合检索和rerank")
print("                         ↑              ↑")
print("                      导入 D6        这里是个减号，语法就崩了")
print()
print("  真的试一次，看报什么错：")
try:
    exec("import D6-混合检索和rerank") 
except SyntaxError as e:
    print(f"    SyntaxError: {e.msg}   ← 不是文件不存在，是这行代码本身不合法") # SyntaxError: invalid syntax   ← 不是文件不存在，是这行代码本身不合法
print()
print("  注意一个常见误解：中文名其实是可以 import 的（Python 3 支持 Unicode 名字），")
print("  真正不合法的是这三种字符：")
print("    -  连字符（被当成减号）")
print("    .  点号（被当成层级分隔，意思是「子模块」）")
print("    空格")
print("  所以答案_key_tools.py 能 import，D6-混合检索和rerank.py 不能。")


# ==========================================================================
标题("第 4 步：用 importlib 硬加载一个「中文名但合法」的模块")
# ==========================================================================
target = os.path.join(HERE, "答案_key_tools.py")
print(f"  目标文件：{os.path.basename(target)}") # 目标文件：答案_key_tools.py
print()

spec = importlib.util.spec_from_file_location("kt", target) # 开取货单：记录从哪个文件取、登记成什么名字
mod = importlib.util.module_from_spec(spec) # 按取货单造一个空壳
print("  执行 spec.loader.exec_module(mod) —— 这一行会把对方文件顶层的代码全跑一遍")
spec.loader.exec_module(mod) # 真正执行那个文件，把东西装进空壳

print(f"  跑完了。拿到的东西里有个 TOOLS，长度 = {len(mod.TOOLS)}") # 3
print(f"  三个工具分别叫：{[t['function']['name'] for t in mod.TOOLS]}") # ['search_kb', 'calc', 'get_doc_meta']
print()
print("  ★ 关键观察：刚才这一下，一次网络请求都没发生。")
print("    因为答案_key_tools.py 里的 Retriever 是懒加载 —— 顶层只有 _RETRIEVER = None，")
print("    真正建索引是在第一次调 search_kb 时。")
print()
print("    如果它顶层写了 retriever = Retriever(chunks)，那么「任何人 import 它一次」")
print("    就会触发 2 次 HTTP 请求（22 个块分 2 批 embedding）。这就叫 import 副作用，")
print("    面试问「你的模块为什么这么设计」时，这就是标准答案。")
print()
print(f"  另外注意：对方文件里的 __name__ 被我指定成了 {mod.__name__!r}（不是 '__main__'），")
print("  所以它文件末尾的 if __name__ == '__main__': 那段没有执行 —— 自检没跑，正合我意。")


# ==========================================================================
标题("第 5 步：同一份文件加载两次，会跑两遍吗")
# ==========================================================================
print(f"  加载前 sys.modules 里有 'kt' 吗：{'kt' in sys.modules}")
spec2 = importlib.util.spec_from_file_location("kt2", target)
mod2 = importlib.util.module_from_spec(spec2)
print("  用新名字 kt2 再加载一次……（会重新执行一遍顶层代码）")
spec2.loader.exec_module(mod2)
print(f"  mod 和 mod2 是同一个对象吗：{mod is mod2}")
print()
print("  结论：用 import 语句时，Python 会把结果按模块名存进 sys.modules，")
print("        第二次 import 同一个名字直接拿缓存，不会再执行一遍。")
print("        （用 importlib 手动加载两次当然跑两遍——因为是我叫它跑的。）")


# ==========================================================================
标题("第 6 步：一句话总结（这 6 行就是面试答案）")
# ==========================================================================
print("  模块（module） = 一个 .py 文件，import 它的本质是「执行它 + 把里面的名字给你」")
print("  import 的代价 = 对方文件顶层代码会执行一次 → 所以顶层别放耗时/联网的活")
print("  今天要做的事 = 把 day6 的检索内核搬进 tools.py（名字合法、能被 import）")
print("                再把能力包成 3 个函数 + 一份 schema，交给 LLM 去挑")
print()
print("  文件名的规矩（以后都按这个来）：")
print("    要给别人 import 的 → 只用英文小写 + 下划线，例如 tools.py / retriever.py")
print("    自己单独跑的脚本   → 随便叫，中文连字符都行，例如 跑基线.py")
