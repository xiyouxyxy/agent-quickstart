# -*- coding: utf-8 -*-
"""
看懂工具返回长什么样.py        ← 只读演示，不要改

目的：搞清楚「工具函数 return 的东西」和「LLM 真正看到的东西」不是一回事。
      你 return 一个 dict，模型看到的是**一段文本**。

这一步决定了两件事：
  ① 模型能不能看懂你的返回（看不懂就会瞎答或者反复调）
  ② 你的 token 花多少（返回太长 = 每轮都烧钱，还占上下文）

跑法：
  cd D:/agent-learn/project/day7
  D:/agent-learn/project/venv/Scripts/python.exe 看懂工具返回长什么样.py
"""

import json
import numpy as np


def 标题(t):
    print("\n" + "=" * 74)
    print(t)
    print("=" * 74)


# 造 3 条假的检索结果（字段和 tools.py 里 search_kb 返回的一模一样）
hits = [
    {
        "doc_id": "c17",
        "source": "04-硬件保修与售后服务手册.md",
        "text": "# 硬件保修与售后服务手册\n\n## 一、配套硬件型号一览\n\n云图库目前配套销售三款拍摄硬件，型号分别是 XR-2000、XR-3000 与 XR-5000。\nXR-2000 为入门款标准拍摄终端，支持 800 万像素采集与基础云同步；",
        "score": 0.487,
    },
    {
        "doc_id": "c18",
        "source": "04-硬件保修与售后服务手册.md",
        "text": "每台设备出厂时贴有唯一序列号，序列号位于机身底部铭牌，格式为「XR + 8 位数字」。\n保修查询、报修提工单时都需要提供该序列号。",
        "score": 0.414,
    },
    {
        "doc_id": "c20",
        "source": "04-硬件保修与售后服务手册.md",
        "text": "设备出现硬件故障时，请先在后台提交工单并选择「硬件报修」，填写序列号与故障描述。\n客服会在 1 个工作日内联系你确认故障，并安排寄回检测。",
        "score": 0.895,
    },
]

result = {
    "found": True,
    "hits": hits,
    "message": "命中 3 块，最高相似度 0.90",
}


# ==========================================================================
标题("第 1 步：你 return 的东西，在 Python 里长这样")
# ==========================================================================
print("  type =", type(result))
print("  它的键：", list(result.keys()))
print()
print("  如果你直接 print(result)，看到的是 Python 的 repr 写法：")
print("  " + str(result)[:120] + " ...")
print()
print("  注意 hits 里每个元素是 dict，text 里带 \\n 换行符 —— 这些东西没办法直接塞进 HTTP 请求。")


# ==========================================================================
标题("第 2 步：真正发给模型前，它会被 json.dumps 变成一段字符串")
# ==========================================================================
payload = json.dumps(result, ensure_ascii=False)
print("  json.dumps(result, ensure_ascii=False) 的结果（前 300 字）：")
print("  " + payload[:300].replace("\n", "\\n") + " ...")
print()
print(f"  字符串总长：{len(payload)} 个字符")
print()
print("  模型看到的就是这一整串文本，它不知道「dict」是什么，只看到花括号和引号。")
print("  所以返回值的字段名要起得让人一眼懂：found / source / text / score")
print("  —— 别用 r、s、t 这种缩写，模型会猜错，人review 时也看不懂。")


# ==========================================================================
标题("第 3 步：为什么 score 必须转 float（D6 那个坑的根源）")
# ==========================================================================
raw = {"doc_id": "c20", "score": np.float32(0.895)}
print(f"  numpy 的 float32 值本身没问题：{raw['score']}  类型={type(raw['score'])}")
print("  但 json.dumps 它的时候：")
try:
    json.dumps(raw)
except TypeError as e:
    print(f"    TypeError: {e}")
print()
print("  原因：json 标准只认 Python 原生的 int / float / str / bool / None / list / dict，")
print("        不认 numpy 的 float32。numpy 是另一个库定义的类型。")
print("  修法：在 return 之前先 float(h['score']) 或 round(float(...), 3)。")
print("  （D6 的 search() 里那句 float(s) 就是在干这件事——当时你可能只是照抄。）")


# ==========================================================================
标题("第 4 步：拒答时该返回什么形状")
# ==========================================================================
refuse = {
    "found": False,
    "hits": [],
    "message": "知识库里没有相关内容（最高相似度 0.59 低于阈值 0.6）。可以换个关键词再试一次，或直接告诉用户查不到。",
}
print("  " + json.dumps(refuse, ensure_ascii=False))
print()
print("  三个设计要点：")
print("    ① found 用布尔，不要用 'false' 字符串 —— 模型更容易正确理解 true/false")
print("    ② hits 给空列表，不要给 None —— 模型处理 [] 比处理 null 稳")
print("    ③ message 里要写「下一步该干什么」：换词重试，还是直接说查不到")
print("       这句话就是在教模型怎么重检 —— 工具描述是提示词的一部分。")


# ==========================================================================
标题("第 5 步：返回太长会怎样（成本与上下文）")
# ==========================================================================
total_chars = sum(len(h["text"]) for h in hits)
print(f"  3 块原文合计 {total_chars} 个字符。")
print(f"  中文大约 1 字 ≈ 1~1.5 token，粗算这一轮工具结果 ≈ {int(total_chars * 1.3)} token。")
print()
print("  单次看着不多，但 Agent 是循环的：查 3 轮 × 每轮 3 块 ≈ 2000+ token 只是「资料」，")
print("  还没算系统提示和历史对话。上下文就是这么被吃掉的——")
print("  这也是为什么 11.04 要讲「上下文压缩」，以及为什么工具要「只返回片段，不返回整篇」。")
print()
print("  反面案例：如果工具直接把 4 篇文档全文返回（7777 字），一轮就 ≈ 10000 token，")
print("  循环 3 轮就爆了。所以 split_text 切块是为了省 token，不只是为了检索精度。")
