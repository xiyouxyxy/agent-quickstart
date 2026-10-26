# 看懂 load_docs + split_text —— 这两段每一行在干什么
"""
你贴的这两段是 RAG 的「①② Load / Split」两步。它们不调任何接口，纯本地文件操作。

    def load_docs(doc_dir=DOC_DIR):          读 3 篇 md 进来
    def split_text(text, source, ...):       把每篇切成 200 字一块

这个脚本把每一行的真实值都打印出来，包括几个「看不见但会出事」的地方：
    • 为什么 DOC_DIR 要用绝对路径
    • glob 的返回顺序为什么不保证，sorted 为什么必须加
    • encoding="utf-8" 不写会怎样（真的会报错，这里跑给你看）
    • piece.strip() 那一行挡掉的是什么垃圾
    • overlap >= chunk_size 会死循环（这个坑很多人踩）

运行：
    cd D:/agent-learn/project/day5
    python 看懂load和split-逐行打印.py
"""

import os
import glob

# =============================================================
print("=" * 66)
print("第 1 步：DOC_DIR 这一行在算什么")
print("=" * 66)
print("    原代码（答案 key 里的写法）：")
print(
    '        DOC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs")'
)
print()
print("    拆成三步看：")
print(f"      __file__        = {__file__}")
print(f"      abspath         = {os.path.abspath(__file__)}")
print(f"      dirname（所在目录）= {os.path.dirname(os.path.abspath(__file__))}")
DOC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs")
print(f"    join()方法表示两个参数拼接，  + 'docs'后 = {DOC_DIR}")
print()
print('    ⚠️ 为什么不直接写 DOC_DIR = "docs"？')
print("       因为「相对路径」是相对于「你敲命令时所在的目录」，不是脚本所在目录。")
print(f"       你现在在这个目录敲命令：{os.getcwd()}")
print("       如果你从 D:/ 下敲 `python project/day5/mini-rag.py`，")
print('       "docs" 就会被解释成 D:/docs/ —— 找不到文件，直接空目录。')
print("       👉 用 __file__ 算绝对路径，从哪运行都对。这是脚本的通用写法。")
print()

# =============================================================
print("=" * 66)
print('第 2 步：os.path.join 和 "*.md" 在拼什么')
print("=" * 66)
pattern = os.path.join(DOC_DIR, "*.md")
print(f'      os.path.join(DOC_DIR, "*.md")  = {pattern}')
print()
print("    os.path.join 干两件事：")
print("      ① 把两段用当前系统的分隔符接起来（Windows 是 \\，Linux/macOS 是 /）")
print("      ② 顺手处理多余的斜杠，不用你自己判断")
print('      → 你的项目以后要部署到 Linux，写死 "docs/" 或用 "+" 拼都容易出问题。')
print()

# =============================================================
print("=" * 66)
print("第 3 步：glob.glob 把通配符展开成真实文件列表")
print("=" * 66)
paths = glob.glob(pattern)
print(f"      glob.glob('*.md') 返回 {len(paths)} 个完整路径：")
for p in paths:
    print(f"        {p}")
print()
print("    * 就是「任意字符」的通配符，和命令行里 `ls *.md` 一个意思。")
print("    它只匹配当前这一层，不会进子目录（要递归得用 **/ 或 recursive=True）。")
print()

# =============================================================
print("=" * 66)
print("第 4 步：为什么要 sorted()？（这是最容易忽略的一行）")
print("=" * 66)
fake = ["03-c.md", "01-a.md", "02-b.md"]
print(f"    假设 glob 返回的顺序是这样的（完全是随机的）：{fake}")
print(f"    加了 sorted 之后：                                  {sorted(fake)}")
print()
print("    glob 不保证顺序 —— 文件系统给什么顺序就是什么，")
print("    Windows / Linux / 换台机器 / 删了重建，顺序都可能变。")
print()
print("    ⚠️ 顺序变了会怎样？")
print("      向量是按顺序存进 FAISS 的，第 0 条向量对应 chunks[0]。")
print("      顺序一乱 → 同一句问题，今天命中 chunks[3]、明天命中 chunks[7]。")
print("      结果每次不一样，你根本没法调试，评测指标也复现不了。")
print("    👉 sorted() 把顺序钉死，保证「同样输入 → 同样结果」。")
print()

# =============================================================
print("=" * 66)
print("第 5 步：os.path.basename 抠出文件名")
print("=" * 66)
print(f"    完整路径：{paths[0]}")
print(f"    文件名：  {os.path.basename(paths[0])}")
print()
print("    为什么要存文件名（source 字段）？")
print("      最后回答用户时如果要标「以上信息来自《01-云图库Pro产品与定价手册》」，")
print("      靠的就是这个字段。没有它，你只能答内容、说不出出处。")
print("      👉 面试里这叫「引用溯源」，是 RAG 可解释性的标配。")
print()

# =============================================================
print("=" * 66)
print("第 6 步：encoding='utf-8' 不写会怎样（真跑给你看）")
print("=" * 66)
sample = paths[0]
try:
    with open(sample, encoding="gbk") as f:  # 故意用 Windows 默认的 gbk
        f.read()
    print("    用 gbk 读居然没报错（这次运气好，字节恰好合法）—— 但内容会是乱码")
except UnicodeDecodeError as e:
    print(f"    ❌ 用 gbk 读，当场炸：UnicodeDecodeError: {e}")
print()
print("    Windows 上 Python 的默认编码是 gbk（不是 utf-8）。")
print("    md 文件是 utf-8 存的 → gbk 解 utf-8 的中文字节，要么报错要么变乱码。")
print("    👉 所以 open() 一律显式写 encoding='utf-8'，这是跨平台铁律。")
print()

# =============================================================
print("=" * 66)
print("第 7 步：with open(...) as f 里的 with 干什么")
print("=" * 66)
print("    等价于：")
print("        f = open(...)")
print("        try:    ...读...")
print("        finally: f.close()     ← 保证一定关掉")
print()
print("    with 就是自动帮你做 finally 里的 close()。")
print("    忘了 close 会怎样：文件句柄泄漏，文件被锁住删不掉（Windows 特别明显）。")
print("    JS 里没有直接对应物，最接近的是 try/finally，或者新的 using 语法。")
print()

# =============================================================
print("=" * 66)
print("第 8 步：piece.strip() 那一行挡的是什么垃圾")
print("=" * 66)
print("    看两个块的区别（左边是原始内容，右边两个是判断结果）：")
print()
print(f"    {'内容':<28} {'bool(原样)':<12} {'bool(strip后)':<14} 会被收进 chunks 吗")
print("    " + "-" * 76)
for s in ["正常内容\n\n\n\n\n", "\n\n\n\n\n\n\n", "   \t  \n  \n"]:
    keep = "✅ 收" if s.strip() else "❌ 丢掉"
    print(f"    {s!r:<28} {str(bool(s)):<12} {str(bool(s.strip())):<14} {keep}")
print()
print(
    "    Python 里空字符串 '' 在 if 判断里算 False，所以 if piece.strip(): 能挡住纯空白块。"
)
print("    文档末尾常常有一堆换行，硬切之后就会切出「全是空白」的块 ——")
print(
    "    这种块如果存进向量库，会变成一条「什么语义都没有」的向量，纯噪声，还会参与检索排位。"
)
print()
print("    ⚠️ 但注意这个细节：代码 append 的是 piece，不是 piece.strip()：")
print("        if piece.strip():                    ← 用 strip 后的结果做判断")
print("            chunks.append({... 'text': piece})   ← 存的却是原始的 piece")
print("       所以块首尾的空白还是留在里面。不影响功能（向量模型不在乎这点空白），")
print("       想更干净就存 piece.strip()。")
print()

# =============================================================
print("=" * 66)
print("第 9 步：切片 + 步长，走一遍真实数据")
print("=" * 66)
TEXT = "订单满三百元包邮，生鲜类目除外，偏远地区需要额外补差价。"
CS, OV = 10, 3
print(f"    用 28 字短文本演示（chunk_size={CS}, overlap={OV}）：{TEXT}")
start = 0
n = 1
while start < len(TEXT):
    print(f"      第{n}刀  text[{start}:{start + CS}] = {TEXT[start : start + CS]}")
    start += CS - OV
    n += 1
print(f"    最后 start={start} >= {len(TEXT)} → while 退出")
print()
print("    两个 Python 细节：")
print("      ① text[a:b] 是「左闭右开」：包含 a，不包含 b。所以 [0:10] 正好 10 个字")
print("      ② 右边界超出长度不报错，自动截到末尾。JS 的 slice 也一样")
print("         例子：", repr(TEXT[21:31]), "← 要到 31 但只有 28 字，给到 28 就停")
print()

# =============================================================
print("=" * 66)
print("第 10 步：⚠️ overlap >= chunk_size 会死循环")
print("=" * 66)
for cs, ov in [(200, 40), (200, 200), (200, 250)]:
    step = cs - ov
    verdict = "✅ 正常前进" if step > 0 else "❌ 步长 <= 0，start 永远不动 → 死循环！"
    print(f"      chunk_size={cs:<4} overlap={ov:<4} 步长={step:<5} {verdict}")
print()
print("    所以参数不能随便传：overlap 必须小于 chunk_size。")
print("    生产代码最好加一句保护：")
print("        assert 0 <= overlap < chunk_size, 'overlap 必须小于 chunk_size'")
print()

# =============================================================
print("=" * 66)
print("第 11 步：跑真实语料，看统计结果")
print("=" * 66)


def load_docs(doc_dir=DOC_DIR):
    docs = []
    for path in sorted(glob.glob(os.path.join(doc_dir, "*.md"))):
        with open(path, encoding="utf-8") as f:
            docs.append({"source": os.path.basename(path), "text": f.read()})
    return docs


def split_text(text, source, chunk_size=200, overlap=40):
    chunks, start = [], 0
    while start < len(text):
        piece = text[start : start + chunk_size]
        if piece.strip():
            chunks.append({"source": source, "text": piece})
        start += chunk_size - overlap
    return chunks


docs = load_docs()
print(f"    读了几篇：{len(docs)}")
total = 0
for d in docs:
    cs = split_text(d["text"], d["source"])
    total += len(cs)
    print(f"      {d['source']:<32} {len(d['text']):>5} 字 → {len(cs):>2} 块")
print(f"    合计：{total} 块")
print()
print(f"    前 2 块长什么样：")
for c in [c for d in docs for c in split_text(d["text"], d["source"])][:2]:
    print(f"      [{c['source']}] {len(c['text'])} 字：{c['text'][:40]!r}...")
print()
print("=" * 66)
print("一句话总结：")
print("  load_docs  = 找文件(glob) → 定顺序(sorted) → 读内容(open+utf-8) → 装进字典")
print("  split_text = 从头开始，每次切 200，往后挪 160，非空的留下，直到切完")
print("=" * 66)
