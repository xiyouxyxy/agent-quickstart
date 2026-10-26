# 看懂这两行 —— with open 和 append 到底在做什么
"""
你要解析的两行：
    with open(path, encoding="utf-8") as f:
        docs.append({"source": os.path.basename(path), "text": f.read()})

拆成 5 个零件，每个都跑一遍给你看：
    ① with ... as ...   上下文管理器（自动关闭文件）
    ② open()            打开文件，需要 3 个参数
    ③ f.read()          把文件内容读成一个字符串
    ④ os.path.basename  从路径里抠文件名
    ⑤ docs.append(...)  把结果塞进列表

还有 3 个坑：
    • f.read() 读完一次，再读一次是空的（文件指针）
    • with 结束后文件已关，再用 f 会报错
    • append 的缩进必须在 with 里面

运行：
    cd D:/agent-learn/project/day5
    python 看懂with-open.py
"""

import os
import glob

DOC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs")
paths = sorted(glob.glob(os.path.join(DOC_DIR, "*.md")))
path = paths[0]

# =====================================================================
print("=" * 70)
print("第 1 步：with 到底干了什么（展开给你看）")
print("=" * 70)
print("    with 不是「打开文件专用语法」，它是通用的「上下文管理器」：")
print("    进入时做一件事（打开），退出时保证做另一件事（关闭）。")
print()
print("        with open(path) as f:        等价于        f = open(path)")
print("            ...内容...                            try:")
print("                                                      ...内容...")
print("                                                  finally:")
print("                                                      f.close()")
print()
print("    👉 关键差别：不管是正常跑完、还是中途报错崩掉，finally 里的 close() 一定执行。")
print("       这就是 with 的意义 —— 你不可能「忘记关文件」。")
print()


def demo_try_finally():
    f = open(path, encoding="utf-8")
    try:
        return f.read()
    finally:
        f.close()


content_a = demo_try_finally()
print(f"    手写 try/finally 读到的字数：{len(content_a)}")


def demo_with():
    with open(path, encoding="utf-8") as f:
        return f.read()


content_b = demo_with()
print(f"    用 with 读到的字数：        {len(content_b)}（完全一样，但少写 4 行）")
print()

# =====================================================================
print("=" * 70)
print("第 2 步：open() 的三个参数")
print("=" * 70)
print('    open(path, encoding="utf-8")')
print("          ↑         ↑")
print("          |         └─ 用哪种编码解码字节（不写就用系统默认，Windows 是 gbk）")
print("          └─ 文件路径")
print()
print("    还有个隐藏的第二参数 mode，默认是 'r'（只读文本）：")
print("        'r'  读文本（默认）      'rb' 读二进制（图片/zip 用这个）")
print("        'w'  写（清空原内容！）  'a'  追加")
print()
print(f'    这里的 mode 没写 → 默认 "r"，也就是「只读文本」模式。')
print()

# =====================================================================
print("=" * 70)
print("第 3 步：as f 里的 f 是什么")
print("=" * 70)
with open(path, encoding="utf-8") as f:
    print(f"    type(f) = {type(f)}")
    print(f"    f.name  = {f.name}")
    print()
    print("    它叫 TextIOWrapper，就是「文本文件对象」。翻译成人话：")
    print("    一个连着磁盘文件的把手，你可以通过它读内容。")
    print("    f 只是变量名，叫 x、叫 file 都行，习惯上写 f。")
    print()

# =====================================================================
print("=" * 70)
print("第 4 步：f.read() 返回什么")
print("=" * 70)
with open(path, encoding="utf-8") as f:
    text = f.read()
print(f"    type(text) = {type(text).__name__}")
print(f"    len(text)  = {len(text)} 字")
print(f"    前 60 个字符 = {text[:60]!r}")
print()
print("    👉 一次性把整个文件读成一个**字符串**（str）。")
print("       注意 repr 里能看到 \\n —— 换行符就在字符串里，没有被去掉。")
print()

# =====================================================================
print("=" * 70)
print("第 5 步：⚠️ 坑一 —— read() 读完一次，再读是空的")
print("=" * 70)
with open(path, encoding="utf-8") as f:
    first = f.read()
    second = f.read()
print(f"    第一次 read()：{len(first)} 字")
print(f"    第二次 read()：{len(second)} 字   ← 空字符串！")
print()
print("    原因：文件对象里有个「指针」，读完就停在文件末尾。")
print("          再读，从末尾往后读，当然什么都没有。")
print("    想要回到开头：f.seek(0)")
print("    👉 所以 f.read() 一个文件只调一次，读到的内容自己存好。")
print()

# =====================================================================
print("=" * 70)
print("第 6 步：⚠️ 坑二 —— with 结束后文件已关，再用 f 会报错")
print("=" * 70)
with open(path, encoding="utf-8") as f:
    inside = len(f.read())
print(f"    with 里面读到了：{inside} 字")
try:
    f.read()
    print("    咦，居然还能读？")
except ValueError as e:
    print(f"    with 外面再用 f.read() → ValueError: {e}")
print()
print("    这就是 with 的「副作用」：它真的帮你关掉了。")
print("    所以读出来的内容必须在 with 内部用完、或者赋给外面的变量：")
print()
print("        with open(...) as f:")
print("            text = f.read()      ← 在内部读出来")
print("        print(text)              ← 在外部用变量 text，不再碰 f")
print()

# =====================================================================
print("=" * 70)
print("第 7 步：为什么用 read() 而不是 readlines() / 逐行读")
print("=" * 70)
with open(path, encoding="utf-8") as f:
    whole = f.read()
with open(path, encoding="utf-8") as f:
    lines = f.readlines()
print(f"    f.read()        → 1 个字符串，{len(whole)} 字")
print(f"    f.readlines()   → {len(lines)} 个元素，每个是一行：{lines[:2]}")
print()
print("    为什么这里选 read()：因为下一步要「按 200 字一刀切」。")
print("    我需要的是「一整段连续的文本」，不是「一行的列表」。")
print("    如果按行读，还得先把它们 ''.join(lines) 拼回去，多此一举。")
print()
print("    什么时候该用逐行读（for line in f）：文件几十万行时。")
print("    逐行读不会一次性把整个文件塞进内存，省内存。")
print()

# =====================================================================
print("=" * 70)
print("第 8 步：os.path.basename 抠文件名")
print("=" * 70)
print(f"    path     = {path}")
print(f"    basename = {os.path.basename(path)}")
print()
print("    为什么存文件名而不是完整路径？")
print("      ① 完整路径带盘符和一堆目录，写进向量库很丑，换台机器就失效")
print("      ② 回答用户时要标出处，用户只需要看文件名")
print()

# =====================================================================
print("=" * 70)
print("第 9 步：append 进去的到底是什么结构")
print("=" * 70)
docs = []
with open(path, encoding="utf-8") as f:
    docs.append({"source": os.path.basename(path), "text": f.read()})

print(f"    docs 现在有 {len(docs)} 个元素")
print(f"    type(docs)      = {type(docs).__name__}")
print(f"    type(docs[0])   = {type(docs[0]).__name__}")
print(f"    docs[0].keys()  = {list(docs[0].keys())}")
print()
print(f'    docs[0]["source"] = {docs[0]["source"]!r}')
print(f'    docs[0]["text"]   = {docs[0]["text"][:30]!r}...   （{len(docs[0]["text"])} 字）')
print()
print("    👉 结构是「列表里装字典」：[{source, text}, {source, text}, ...]")
print('       这种形状在 Python 里很常见，等价于 JS 的：')
print('       [{ source: "...", text: "..." }, ...]')
print()

# =====================================================================
print("=" * 70)
print("第 10 步：⚠️ 坑三 —— append 的缩进必须在 with 里面")
print("=" * 70)
print("    正确（append 在 with 内部，f 还活着）：")
print("        with open(path, encoding='utf-8') as f:")
print("            docs.append({'source': ..., 'text': f.read()})")
print()
print("    错误（append 缩进退到外面）：")
print("        with open(path, encoding='utf-8') as f:")
print("            pass")
print("        docs.append({'source': ..., 'text': f.read()})   ← f 已关闭 → ValueError")
print()
print("    Python 靠缩进区分「在不在 with 里面」，这跟 JS 的 {} 花括号一样是语法边界，")
print("    只不过 JS 用符号，Python 用空格。")
print()

# =====================================================================
print("=" * 70)
print("第 11 步：一次跑完整的 load_docs，看最终结果")
print("=" * 70)


def load_docs(doc_dir=DOC_DIR):
    docs = []
    for path in sorted(glob.glob(os.path.join(doc_dir, "*.md"))):
        with open(path, encoding="utf-8") as f:
            docs.append({"source": os.path.basename(path), "text": f.read()})
    return docs


all_docs = load_docs()
print(f"    读了几篇：{len(all_docs)}")
for i, d in enumerate(all_docs):
    print(f"      [{i}] source={d['source']:<34} text={len(d['text'])} 字")
print()
print("=" * 70)
print("一句话总结：")
print("  with open(...) as f  = 打开文件，并保证用完一定关掉")
print("  f.read()             = 把整个文件读成一个大字符串")
print("  basename(path)       = 抠出文件名，当出处用")
print("  docs.append({...})   = 把这一篇打包成字典，塞进列表")
print("=" * 70)
