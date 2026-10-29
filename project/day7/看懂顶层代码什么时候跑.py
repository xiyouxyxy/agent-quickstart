# -*- coding: utf-8 -*-
"""
看懂顶层代码什么时候跑.py        ← 只读演示，不要改

回答文件地图第 4 步那句话：
    「import tools 应该瞬间返回（D6 的 Retriever 本来就在 main() 里 new，所以你还没引入副作用）」

这句话在说一件事：**Python 文件里的代码，写在哪一层，决定了它什么时候跑。**
    顶层（缩进 0）    →  被 import 的瞬间就执行
    函数体内（缩进）  →  只有函数被调用时才执行

跑法：
  cd D:/agent-learn/project/day7
  D:/agent-learn/project/venv/Scripts/python.exe 看懂顶层代码什么时候跑.py
"""

import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def 标题(t):
    print("\n" + "=" * 76)
    print(t)
    print("=" * 76)


# ==========================================================================
标题("第 1 步：结论先给——代码写在哪一层，决定它什么时候跑")
# ==========================================================================
print("  顶层（缩进 0 格）    →  import 这个文件的瞬间就执行")
print("  函数体内（缩进 4 格）→  只有函数被调用时才执行")
print()
print("  前端对照：ES module 的顶层代码也是「被 import 时执行一次」。")
print("  你在 utils.js 顶层写一句 console.log，任何页面一 import 它就打印——")
print("  一模一样的机制。Python 没有区别，只是没有 export 那套语法。")


# ==========================================================================
标题("第 2 步：实测——同样 1.2 秒的耗时，放两个位置差多少")
# ==========================================================================
# 用 time.sleep(1.2) 假装「建索引要花的钱」，因为真建索引要调 2 次 HTTP，太慢
源码_顶层 = "import time\ntime.sleep(1.2)\nprint('      → 我执行了（顶层那句）')"
源码_函数 = "import time\ndef build():\n    time.sleep(1.2)\n    print('      → 我执行了（函数里那句）')"

print("  【A】把耗时活儿写在顶层：")
t0 = time.time()
exec(源码_顶层, {})
print(f"      import 完总共用了 {time.time() - t0:.1f} 秒   ← 等它跑完才返回")

print()
print("  【B】把同样的活儿包进函数里：")
t0 = time.time()
ns = {}
exec(源码_函数, ns)
print(f"      import 完总共用了 {time.time() - t0:.1f} 秒   ← 瞬间，因为函数没人调")

t0 = time.time()
ns["build"]()
print(f"      之后我主动调 build()，才又花了 {time.time() - t0:.1f} 秒")

print()
print("  ★ 这就是「瞬间返回」的意思：代码在函数里，没人调就一行都不跑。")


# ==========================================================================
标题("补充：def 明明写在顶层，为什么函数体没跑？（最容易绕住的一点）")
# ==========================================================================
print("  你可能会想：`def build():` 那一行是写在顶层的呀，它应该在 import 时就执行吧？")
print()
print("  对，但**「执行 def」不等于「执行函数体」**：")
print("    def 那一行执行的活是：造一个函数对象，贴上 build 这个标签，结束。")
print("    函数体（缩进那几行）要等你写 build() 去调用它，才会跑。")
print()
print("  跑一段 5 行的，看真实顺序：")
print()
print("      print('A 顶层第 1 句')")
print("      def build():")
print("          print('B 函数体里')")
print("      print('C 顶层第 2 句')")
print("      build()")
print("      print('D 顶层第 3 句')")
print()
print("  实际输出：")
源码 = (
    'print("        A 顶层第 1 句")\n'
    "def build():\n"
    '    print("        B 函数体里（缩进 4 格）")\n'
    'print("        C 顶层第 2 句")\n'
    "build()\n"
    'print("        D 顶层第 3 句")\n'
)
exec(源码, {})
print()
print("  顺序是 A → C → B → D。")
print("  注意 B 排在 C 后面 —— 说明 def 那行并没有跑函数体，它只是「登记」。")
print("  直到第 5 行 build() 被调用，B 才出现。")
print()
print("  所以准确的说法是：")
print("    ✓ 缩进 0 的语句，import 时按顺序执行（包括 def 那一行——它执行的是「登记」）")
print("    ✗ 不是「顶层的函数会执行」，而是「顶层的语句会执行，函数体要有人调」")


# ==========================================================================
标题("第 3 步：D6 为什么没事（它的结构长这样）")
# ==========================================================================
print("""
  def main():
      docs = load_docs()
      chunks = [...]
      r = Retriever(chunks)        ← 在函数体里（缩进 4 格）

      cases = [...]
      for q, expect in cases:
          ...

  if __name__ == '__main__':
      main()                       ← 只有「直接运行」时才调 main()
""")
print("  Retriever 只出现在 main() 里面 —— 没人调 main()，它就永远不会被 new。")
print()
print("  Python 的 Retriever(chunks)  ≈  前端的 new Retriever(chunks)")
print("  （Python 不用写 new 这个字，但意思完全一样：调构造函数、造一个对象）")
print()
print("  两层保险叠在一起：")
print("    ① 建索引的代码写在函数里 → 不调就不跑")
print("    ② if __name__ == '__main__' → 只有「python tools.py」才调，别人 import 不调")


# ==========================================================================
标题("第 4 步：实测 import 答案_key_tools.py（懒加载版）")
# ==========================================================================
t0 = time.time()
import 答案_key_tools as kt  # noqa: E402

print(f"  import 用了 {time.time() - t0:.2f} 秒")
print(f"  kt._RETRIEVER = {kt._RETRIEVER}")
print()
print("  注意：这零点几秒是 import faiss / numpy 的成本，不是建索引的成本。")
print(f"  真正的建索引要调 2 次 HTTP（22 个块分两批），几秒到几十秒，看网速。")
print()
print("  证据就在这一行：_RETRIEVER 还是 None —— 索引根本没建。")
print("  等你真调 kt.search_kb('...') 的时候，它才会去建。")


# ==========================================================================
标题("第 5 步：那「坑」在哪（第 3 步一写 search_kb 就会踩）")
# ==========================================================================
print("  你写 search_kb 的时候会立刻遇到一个问题：")
print("      「这个 retriever 放哪儿？」")
print()
print("  放函数里？每次调用都重建索引 → 每问一句就等 20 秒，显然不行。")
print("  所以本能反应是提到函数外面，也就是顶层：")
print()
print("      _r = Retriever(_build_chunks())      ← 写在顶层了")
print()
print("      def search_kb(query, top_k=3):")
print("          return _r.hybrid_search(...)")
print()
print("  看起来没问题，但代价是：")
print("    ✗ 任何文件只要 import tools 一次，就会被迫等建索引")
print("    ✗ 网络挂了 → import 直接报错 → 明天整个 agent.py 连启动都启动不了")
print("    ✗ 光跑个单元测试也会先烧掉 2 次 API 调用")
print()
print("  解法是懒加载：顶层只放一个空变量，第一次真要用时才建。")
print()
print("      _RETRIEVER = None                    ← 顶层只有这一句，import 时零成本")
print()
print("      def get_retriever():")
print("          global _RETRIEVER")
print("          if _RETRIEVER is None:")
print("              _RETRIEVER = Retriever(_build_chunks())   ← 第一次调用才建")
print("          return _RETRIEVER")
print()
print("  对照一下三种写法的差别：")
print()
print("  写法                          import 时代价        第一次检索代价")
print("  " + "-" * 66)
print("  顶层 new Retriever            建索引（几秒~几十秒） 0")
print("  函数里每次 new                0                   每次都要重建，最慢")
print("  懒加载（get_retriever）        0                   只建一次，之后复用  ← 用这个")
