# -*- coding: utf-8 -*-
"""
看懂TOOLS和tool_calls.py        ← 只读演示，不要改

回答两个问题：
    ① TOOLS 那一大坨是干什么用的？
    ② _selfcheck_offline / _selfcheck_online 这两个自检是干什么用的？

一句话：
    TOOLS   = 给模型看的「菜单」（不给人看，每次调 API 都跟着发过去）
    自检     = 给自己用的「自动验货」（不用肉眼检查，跑一下就知道对不对）

跑法：
  cd D:/agent-learn/project/day7
  D:/agent-learn/project/venv/Scripts/python.exe 看懂TOOLS和tool_calls.py
"""

import os
import sys
import json

import httpx

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from 答案_key_tools import TOOLS, DISPATCH, BASE_URL, API_KEY, MODEL_NAME  # noqa: E402


def 标题(t):
    print("\n" + "=" * 76)
    print(t)
    print("=" * 76)


# ==========================================================================
标题("第 1 步：TOOLS 是菜单——发给模型的那三样东西")
# ==========================================================================
print("  你调 LLM 接口时，请求体里会带一个 tools 字段：")
print()
print("      httpx.post(url, json={'model':..., 'messages':..., 'tools': TOOLS})")
print("                                                            ↑ 就是它")
print()
print(f"  现在 TOOLS 里有 {len(TOOLS)} 个工具：{[t['function']['name'] for t in TOOLS]}")
print()
print("  每个工具的三段：")
print()
print("    name         → 工具叫什么（模型只能通过这个名字点它）")
print("    description  → 什么时候该用它（= 提示词，写不好模型就不会用）")
print("    parameters   → 要填哪些参数、什么类型、哪些必填")
print()
print("  拿 search_kb 举个实例，模型实际收到的是这样：")
print()
first = TOOLS[0]["function"]
print("    name        :", first["name"])
print("    description :", first["description"][:60], "...（后面还有三句边界说明）")
print("    parameters  :", json.dumps(first["parameters"], ensure_ascii=False)[:110], "...")


# ==========================================================================
标题("第 2 步：模型怎么「点单」——tool_calls 长什么样（真的调一次）")
# ==========================================================================
question = "XR-2000 的保修期是多久？"
print(f"  问：{question}")
print("  只给它 search_kb 一个工具，看它会不会点、点的时候参数填什么：")
print()

try:
    resp = httpx.post(
        f"{BASE_URL}/chat/completions",
        headers={"Authorization": f"Bearer {API_KEY}"},
        json={
            "model": MODEL_NAME,
            "messages": [
                {"role": "system", "content": "你是助手，需要资料时调用工具，不要编造"},
                {"role": "user", "content": question},
            ],
            "tools": TOOLS,           # ← 菜单发过去
        },
        timeout=60,
    )
    resp.raise_for_status()
    msg = resp.json()["choices"][0]["message"]
    print("  模型回来的 message：")
    print("  " + json.dumps(msg, ensure_ascii=False, indent=2).replace("\n", "\n  ")[:700])
except Exception as e:
    print(f"  [调用失败] {type(e).__name__}: {e}")
    print("  网络问题不影响理解，接着看第 3 步。")
    msg = None


# ==========================================================================
标题("第 3 步：DISPATCH 是后厨——把「点单」变成真正执行")
# ==========================================================================
print("  模型只会说「我要调 search_kb，参数是 {'query': 'XR-2000 保修期'}」。")
print("  它不会、也不能自己执行代码。真正干活的永远是你的程序：")
print()
print("      fn = tc['function']['name']                    # 'search_kb'")
print("      args = json.loads(tc['function']['arguments']) # {'query': '...'}")
print("      result = DISPATCH[fn](**args)                  # ← 查表，然后调用")
print()
print(f"  你的 DISPATCH 现在挂着：{list(DISPATCH.keys())}")
print()
print("  这就是三者关系：")
print()
print("      TOOLS      →  菜单，你写给模型看")
print("      tool_calls →  点单，模型返回给你")
print("      DISPATCH   →  后厨，你查表去执行")
print()
print("  ★ 模型从头到尾没有「执行」任何东西，它只输出了一段 JSON。")
print("    这一点面试必问：「Function Calling 是谁执行的？」答案就是这里。")


# ==========================================================================
标题("第 4 步：自检是干什么的——assert 就是「自动验货」")
# ==========================================================================
print("  print 检查 → 要你人眼看，看漏了就是没检查。")
print("  assert     → 机器判定，条件不成立直接抛 AssertionError，脚本当场停在那行。")
print()
print("  写一段故意失败的，看它长什么样：")
print()
try:
    assert 1 + 1 == 3, "这条是故意写错的：1+1 根本不等于 3"
except AssertionError as e:
    print(f"    捕获到 AssertionError：{e}")
print()
print("  真实用法就是这样一条条卡住：")
print()
print("      assert len(TOOLS) == 3, f'应该正好 3 个工具，现在是 {len(TOOLS)}'")
print("      assert set(names) == set(DISPATCH), 'TOOLS 的名字和 DISPATCH 的键必须对上'")
print()
print("  好处：你改完代码跑一次，错的地方立刻报出来，不用一行行 print 去猜。")
print()
print("  为什么分 offline / online 两段？")
print()
print("      离线自检  不联网、不花钱、1 秒出结果  → 每改一点代码都可以跑")
print("      联网自检  要调 embedding、慢、可能被网络搞挂 → 跑通了再跑一次就行")
print()
print("  如果混在一起：任何一次小改动都得等 20 秒+ 还烧 API，你就不想跑了。")
print("  分开之后，日常 90% 的问题离线就能抓住。")


# ==========================================================================
标题("一句话带走")
# ==========================================================================
print("  TOOLS    = 菜单，给模型看（不给人看）")
print("  自检      = 验货，给自己用（不给人看）")
print("  DISPATCH = 后厨，给程序用")
print()
print("  三样东西各自服务一个对象，混了就乱：")
print("    菜单写给人看 → 模型看不懂 → 不会调")
print("    验货写给人看 → 你得自己肉眼查 → 迟早漏")
