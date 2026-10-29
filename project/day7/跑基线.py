# -*- coding: utf-8 -*-
"""
跑基线.py        ← 只读脚本，不用改。跑完你会得到三个数字，明天做 Agent 后要拿它对比。

它在干什么：
  拿 eval_set.json 里的 20 个问题，一道一道喂给 tools.search_kb，
  然后统计三个指标：
    HR@3      —— top3 里有没有出现「标准答案来源的那份文件」，有就算命中
    MRR       —— 第一份正确文件排在第几名，第 1 名得 1 分、第 2 名 0.5、第 3 名 0.33
    拒答准确率 —— 该拒的题有没有真的 found=False

跑法：
  cd D:/agent-learn/project/day7
  D:/agent-learn/project/venv/Scripts/python.exe 跑基线.py
  （想跑我给的参考 20 题：末尾加参数 --ref）
"""

import os
import sys
import json

_HERE = os.path.dirname(os.path.abspath(__file__))

# ---- 找工具来源：优先你自己的 tools.py；没有就退回参考实现 ----
sys.path.insert(0, _HERE)
try:
    from tools import search_kb, get_retriever  # noqa: F401

    SOURCE = "tools.py（你自己写的）"
except ImportError:
    from 答案_key_tools import search_kb, get_retriever  # noqa: F401

    SOURCE = "答案_key_tools.py（参考实现）"


def load_eval(path: str) -> list:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    items = data["items"] if isinstance(data, dict) else data
    print(f"评测集：{path}")
    print(f"题数：{len(items)}")
    return items


def run(items: list, raw: bool = False) -> dict:
    rows = []
    for it in items:
        if raw:
            # raw 模式：绕过 search_kb，直接调检索内核 → 不判拒答，只看「捞没捞到」
            res = get_retriever().hybrid_search(it["question"], recall_k=5, top_k=3)
            hits = [
                {"source": h["source"], "doc_id": h["doc_id"], "text": h["text"]}
                for h in res["hits"]
            ]
            found = bool(hits)
        else:
            r = search_kb(it["question"], top_k=3)
            hits = r.get("hits", [])
            found = r.get("found", False)

        # ① 该拒答的题：只看 found 是否为 False
        if it["should_refuse"]:
            ok = not found
            rows.append(
                {
                    "id": it["id"],
                    "type": it["type"],
                    "hit": ok,
                    "rr": 0.0,
                    "top1": hits[0]["source"] if hits else "（无召回）",
                    "note": "正确拒答" if ok else "漏答：该拒没拒",
                }
            )
            continue

        # ② 有答案的题：看 gold_sources 里的文件有没有出现在 top3
        gold = set(it["gold_sources"])
        rank = 0
        for pos, h in enumerate(hits, start=1):
            if h["source"] in gold:
                rank = pos
                break
        rows.append(
            {
                "id": it["id"],
                "type": it["type"],
                "hit": rank > 0,
                "rr": (1.0 / rank) if rank else 0.0,
                "top1": hits[0]["source"] if hits else "（拒答）",
                "note": f"命中第 {rank} 名" if rank else "top3 里没命中",
            }
        )
    return rows


def report(rows: list, raw: bool = False) -> None:
    print("\n" + "=" * 88)
    print(f"{'题号':<6}{'类型':<12}{'命中':<6}{'RR':<8}{'top1 来源':<34}{'备注'}")
    print("-" * 88)
    for r in rows:
        print(
            f"{r['id']:<6}{r['type']:<12}{'✅' if r['hit'] else '❌':<6}"
            f"{r['rr']:<8.3f}{r['top1'][:32]:<34}{r['note']}"
        )

    answerable = [r for r in rows if not r["type"] == "应拒答"]
    refusable = [r for r in rows if r["type"] == "应拒答"]

    hr3 = sum(1 for r in answerable if r["hit"]) / len(answerable) if answerable else 0
    mrr = sum(r["rr"] for r in answerable) / len(answerable) if answerable else 0
    acc = sum(1 for r in refusable if r["hit"]) / len(refusable) if refusable else 0

    print("=" * 88)
    print(f"HR@3      = {hr3:.1%}   （{sum(1 for r in answerable if r['hit'])}/{len(answerable)} 道可答题，top3 召回到了正确文件）")
    print(f"MRR       = {mrr:.3f}  （越高说明正确文件排得越靠前，1.000 是满分）")
    if raw:
        print("拒答准确率 = 不评（raw 模式绕过了拒答阈值，只看检索能力）")
    else:
        print(f"拒答准确率 = {acc:.1%}   （{sum(1 for r in refusable if r['hit'])}/{len(refusable)} 道该拒的题真的拒了）")
    print("=" * 88)
    print("\n把这三个数字抄进 day7 笔记，标上「D7 基线 · 纯检索、无 Agent」。")
    print("注意：这只评「检索有没有捞到正确文件」，不评算术和最终答案质量——")
    print("     算术靠 calc 工具，答案质量等 D8 有了 Agent 主循环再评。这个区分面试会问到。")
    if not raw:
        print("\n想看不带拒答阈值的「纯检索能力」→ 加 --raw 再跑一遍。")
        print("两遍数字一对比，你就知道分是被「检索」拉低的，还是被「阈值」误杀的。")


if __name__ == "__main__":
    use_ref = "--ref" in sys.argv
    raw = "--raw" in sys.argv
    fname = "答案_key_eval_set（写完自己的再看）.json" if use_ref else "eval_set.json"
    path = os.path.join(_HERE, fname)
    if not os.path.exists(path):
        print(f"[没找到] {path}")
        print("  先自己写 eval_set.json（至少 12 题）再跑；只想看参考结果就加参数 --ref")
        raise SystemExit(1)

    print(f"工具来源：{SOURCE}")
    print(f"模式：{'raw（绕过拒答阈值，只评检索）' if raw else '默认（search_kb 完整逻辑，含拒答）'}")
    items = load_eval(path)
    report(run(items, raw=raw), raw=raw)
