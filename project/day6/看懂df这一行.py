# -*- coding: utf-8 -*-
"""
看懂df这一行.py        ← 只读演示，别改

只讲一行：
    df = sum(1 for toks in TOKENS.values() if t in toks)     # 含这个词的文档数

跑法：
  cd D:/agent-learn/project/day6
  D:/agent-learn/project/venv/Scripts/python.exe 看懂df这一行.py
"""

import re

DOCS = {
    "A": "云图库专业版每月赠送 500 次 AI 扩图额度，超出后按每次 0.2 元计费。",
    "B": "云图库的付费套餐分为基础版、专业版、旗舰版三档，价格分别是 19 元 49 元 99 元。",
    "C": "所有硬件设备（含 XR-2000 型号）自签收之日起享受 12 个月免费保修。",
    "D": "设备出现故障时，请先提交工单，客服会在 1 个工作日内联系你安排寄回检测。",
}


def tokenize(text: str) -> list:
    text = text.lower()
    latin = re.findall(r"[a-z0-9]+", text)
    han = re.findall(r"[\u4e00-\u9fff]", text)
    bigram = [han[i] + han[i + 1] for i in range(len(han) - 1)]
    return latin + han + bigram


TOKENS = {k: tokenize(v) for k, v in DOCS.items()}
N = len(DOCS)


def line(width=76, ch="="):
    print(ch * width)


# ==========================================================================
line()
print("第 1 步：TOKENS 是什么形状？（先看清数据，再谈代码）")
line()
print(f"  type(TOKENS) = {type(TOKENS)}")
print(f"  TOKENS 的键  = {list(TOKENS.keys())}")
print(f"  一共 {len(TOKENS)} 个键，每个键对着一篇文档")
print()
for k, toks in TOKENS.items():
    print(f"  TOKENS['{k}'] 长度={len(toks):>2}  前 8 个词={toks[:8]}")
print()
print("  → 所以 TOKENS 不是「一篇文档」，是「4 篇文档的词典」：")
print("     {'A': [A的词...], 'B': [B的词...], 'C': [C的词...], 'D': [D的词...]}")
print("     外面是字典（键 → 值），里面每一层的值是「词列表」。")
print()

# ==========================================================================
line()
print("第 2 步：TOKENS.values() 取出来的是什么？")
line()
vals = TOKENS.values()
print(f"  type(TOKENS.values()) = {type(vals)}")
print(f"  len(TOKENS.values())  = {len(vals)}   ← 4 个值（4 篇的词列表）")
print("  注意：它和 list 不一样，不能按下标 vals[0]，只能拿来遍历（for 循环）。")
print()
print("  遍历它，每一轮拿到的 toks 是「某一篇文档的整个词列表」：")
for i, toks in enumerate(TOKENS.values(), start=1):
    print(f"    第{i}轮  toks 长度={len(toks):>2}  前 5 个={toks[:5]}")
print()

# ==========================================================================
line()
print("第 3 步：把那一行拆成 6 行来写（完全等价，只是啰嗦）")
line()


def df_verbose(t):
    count = 0                          # 计数器，从 0 开始
    for toks in TOKENS.values():       # 每一轮 = 换一篇文档
        if t in toks:                  # 这篇文档的词列表里有没有 t？
            count = count + 1          # 有，计数 +1
    return count


def df_oneline(t):
    return sum(1 for toks in TOKENS.values() if t in toks)


print("  逐字对应关系：")
print("    count = 0                                  →  sum( ... ) 的求和起点 0")
print("    for toks in TOKENS.values():               →  for toks in TOKENS.values()")
print("    if t in toks:                              →  if t in toks")
print("    count = count + 1                          →  1      （命中一次就产出数字 1）")
print("  sum 最后把这几个 1 加起来，就是「命中的文档数」。")
print()

# ==========================================================================
line()
print("第 4 步：盯住一个词，人肉跑一遍  t = 'xr'")
line()
t = "xr"
print(f"  要找的词 t = '{t}'   （问题「XR-2000 坏了怎么保修？」被切成小写后就有 'xr'）")
print()
count = 0
for k, toks in TOKENS.items():
    hit = t in toks
    if hit:
        count += 1
    got = 1 if hit else 0
    print(f"    【{k}】 {t!r} in 这篇?  {str(hit):<5}   本次产出数字={got}   累计={count}")
print()
print(f"  4 篇跑完，累计 = {count}  → df = {df_oneline(t)}   （两个版本结果一致）")
print()

# ==========================================================================
line()
print("第 5 步：换几个词看 df 的变化（这才是这行代码的用途）")
line()
Q1 = "XR-2000 坏了怎么保修？"
qt = tokenize(Q1)
print(f"  问题1 = {Q1}")
print(f"  切成的词（去重后）= {sorted(set(qt))}")
print()
print(f"  {'词':<6}{'df（含它的文档数）':<22}说明")
for t in sorted(set(qt)):
    df = df_oneline(t)
    if df == 0:
        note = "4 篇里一篇都没有 → 白算"
    elif df == 1:
        note = "只出现在 1 篇里 → 最值钱"
    else:
        note = f"出现在 {df} 篇里 → 比较通用"
    print(f"  {t:<6}{df:<22}{note}")
print()

# ==========================================================================
line()
print("第 6 步：df 拿去干什么？（下一行就用到它）")
line()
import math
print("  idf[t] = math.log((N - df + 0.5) / (df + 0.5) + 1)   # 越稀有 → 越大")
print()
for t in ["xr", "保", "的", "坏"]:
    df = df_oneline(t)
    idf = math.log((N - df + 0.5) / (df + 0.5) + 1)
    print(f"    t='{t}'  df={df}  →  idf={idf:.3f}")
print()
print("  ⚠️ 注意 df=0 那一行（比如「坏」）：idf 算出来是最大值，")
print("     但这篇文档里根本没这个词，所以后面算分时 tf=0 直接 continue，一分都拿不到。")
print("     这就是脚本里那句「这种词的 IDF 再高也没用——因为一篇都没命中」。")
print()

# ==========================================================================
line()
print("第 7 步：换成 JS 的写法（你已经熟的那套）")
line()
print("  JS:  const df = values.filter(toks => toks.includes(t)).length")
print()
print("  对照表：")
print("    TOKENS.values()      ↔  values                          （一组列表）")
print("    for toks in ...      ↔  .filter(toks => ...) 里的 toks  （同一个元素）")
print("    t in toks            ↔  toks.includes(t)               （列表里有没有）")
print("    if ...               ↔  .filter(...) 的条件")
print("    sum(1 for ...)       ↔  .length                         （数剩下几个）")
print()
print("  Python 里 `in` 用在列表上 = 「包含」，和 JS 的 includes 一个意思；")
print("  但要和 `for x in list` 的 `in` 区分开——那个是「遍历」，不是「包含」。")
