# -*- coding: utf-8 -*-
"""
看懂拒答阈值.py        ← 只读演示，不要改

回答两个问题：
    ① 拒答阈值到底是什么？
    ② 为什么 0.6 这条线是错的？调成多少才对？

它干的事：拿参考 20 题，把每题的「最高向量分」量出来，
          然后扫一遍 0.2~0.8 的阈值，看每个阈值会「误杀几道该答的 / 放过几道该拒的」。

跑法（会调 20 次 embedding，约 30 秒）：
  cd D:/agent-learn/project/day7
  D:/agent-learn/project/venv/Scripts/python.exe 看懂拒答阈值.py
"""

import os
import sys
import json

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from 答案_key_tools import get_retriever, REFUSE_THRESHOLD  # noqa: E402

EVAL_MINE = os.path.join(HERE, "eval_set.json")
EVAL_REF = os.path.join(HERE, "答案_key_eval_set（写完自己的再看）.json")
EVAL = EVAL_MINE if os.path.exists(EVAL_MINE) else EVAL_REF


def 标题(t):
    print("\n" + "=" * 78)
    print(t)
    print("=" * 78)


with open(EVAL, encoding="utf-8") as f:
    items = json.load(f)["items"]

# ==========================================================================
标题("第 0 步：一句话说清「拒答阈值」是什么")
# ==========================================================================
print("  拒答阈值 = 一条分数线。")
print()
print("  检索完，你手上有一堆片段，每块带一个相似度分（0~1，越高越像）。")
print("  系统看一眼「最高的那个分」，然后跟这条线比：")
print()
print("      最高分  ≥  阈值   →  认为「库里有货」，把片段交给模型，让它组织答案")
print("      最高分  <  阈值   →  认为「库里没有」，直接回「资料中没有相关信息」，不调模型")
print()
print(f"  你现在代码里这条线写死成 REFUSE_THRESHOLD = {REFUSE_THRESHOLD}（day5 定的，一路抄到今天）。")


# ==========================================================================
标题("第 1 步：把 20 题的「最高分」量出来（这就是数据快照）")
# ==========================================================================
rows = []
for it in items:
    res = get_retriever().hybrid_search(it["question"], recall_k=5, top_k=3)
    rows.append(
        {
            "id": it["id"],
            "type": it["type"],
            "q": it["question"],
            "max_vec": res["max_vec"],
            "should_refuse": it["should_refuse"],
        }
    )

print(f"  {'题号':<6}{'类型':<10}{'最高分':<9}{'该拒吗':<8}{'0.6 下的判定':<14}{'对不对'}")
print("  " + "-" * 72)
for r in rows:
    judged = "拒答" if r["max_vec"] < REFUSE_THRESHOLD else "回答"
    expect = "拒答" if r["should_refuse"] else "回答"
    ok = "✅" if judged == expect else "❌"
    print(
        f"  {r['id']:<6}{r['type']:<10}{r['max_vec']:<9.4f}"
        f"{('是' if r['should_refuse'] else '否'):<8}{judged:<14}{ok}"
    )

错的 = [r for r in rows if (r["max_vec"] < REFUSE_THRESHOLD) != r["should_refuse"]]
print()
print(f"  0.6 这条线一共判错 {len(错的)} 题：{[r['id'] for r in 错的]}")


# ==========================================================================
标题("第 2 步：换一条线会怎样（扫一遍所有候选阈值）")
# ==========================================================================
print("  两种错法：")
print("    误杀 = 该答的题，分数低于线 → 被当成「查不到」，用户白白被拒")
print("    漏放 = 该拒的题，分数高于线 → 明明没写，还让模型硬答（更容易编）")
print()
print(f"  {'阈值':<8}{'误杀(该答被拒)':<18}{'漏放(该拒被答)':<18}{'总错':<8}")
print("  " + "-" * 60)

best = None
for th in [0.2, 0.25, 0.3, 0.35, 0.4, 0.45, 0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8]:
    kill = sum(1 for r in rows if (not r["should_refuse"]) and r["max_vec"] < th)
    pass_ = sum(1 for r in rows if r["should_refuse"] and r["max_vec"] >= th)
    total = kill + pass_
    mark = ""
    if best is None or total < best[1]:
        best = (th, total)
    if abs(th - REFUSE_THRESHOLD) < 1e-9:
        mark = "   ← 你现在用的这条线"
    print(f"  {th:<8.2f}{kill:<18}{pass_:<18}{total:<8}{mark}")

print()
print(f"  扫下来最不坏的一条是 {best[0]:.2f}，仍然错 {best[1]} 题 —— 没有一条能让错变成 0。")


# ==========================================================================
标题("第 3 步：为什么调不好（这就是发现②）")
# ==========================================================================
print("  把错得最典型的两题挑出来看：")
print()
for r in rows:
    if r["id"] in ("Q02", "Q09", "Q18"):
        kind = "该答" if not r["should_refuse"] else "该拒"
        print(f"  {r['id']}（{kind}）最高分 {r['max_vec']:.4f}   {r['q']}")
print()
print("  Q02 / Q09 是「库里明明有，但分数低」——线调低就能救。")
print("  Q18 是「库里明明没有，但分数高」——线得调高才能挡。")
print()
print("  ★ 这两类要求的方向相反：救 Q02 要把线压低，挡 Q18 要把线拉高。")
print("    所以不管你把线定在哪，总会错一批。这就是「单靠一个分数无解」的意思。")
print()
print("  真正的解法不是调线，是换一个能「读完片段再判断」的东西 —— 也就是明天的主循环：")
print("    低阈值召回一批 → 模型把片段读完 → 自己判断「这里面到底有没有回答这个问题」")
print("    有 → 组织答案；没有 → 拒答")
print("  阈值从此只负责「别漏太多」，判断交给模型。")
