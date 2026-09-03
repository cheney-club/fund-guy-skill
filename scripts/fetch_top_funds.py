"""全市场今年收益 TOP10 主动基金 vs 目标经理当前持仓的同步度。

口径:
- 排行来自东财开放式基金排行(今年来),用基金类型筛真·主动权益(不靠简称猜债券/偏债)
- 同一基金多个份额(A/C/E)只留今年来最高的一个;不跟自己比
- 同步度 = 对方最新前十大里,与他当前前十大同名的只数 / 10
"""
import json
import os
import re
import sys
import time
from datetime import date as D

import akshare as ak

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fund_meta import require_code, latest_top_holdings, is_active_equity
CODE = require_code()
DIR = os.path.join(ROOT, ".cache", f"fund_{CODE}")

latest, top = latest_top_holdings(DIR, 10)
if not latest:
    print("本品持仓未获取,跳过热榜")
    sys.exit(0)
my_names = {r["股票名称"] for r in top}
print(f"他的当前前十大({latest}): {sorted(my_names)}")

names_df = ak.fund_name_em()
types = dict(zip(names_df["基金代码"].astype(str), names_df["基金类型"]))

rank = ak.fund_open_fund_rank_em(symbol="全部")
rank = rank.dropna(subset=["今年来"])
BAD = re.compile(
    r"指数|ETF|联接|QDII|FOF|LOF联接|增强|沪深300|中证|标普|纳斯达克|恒生|"
    r"债券|偏债|固收|货币|理财|可转债"
)
rank = rank[~rank["基金简称"].str.contains(BAD)]
rank = rank[rank["基金简称"].str.contains("混合|股票")]
rank = rank.sort_values("今年来", ascending=False)

# 去重份额:去掉尾缀 A/B/C/E/D 后的名字相同视为同一只
seen, top_rows = set(), []
for _, r in rank.iterrows():
    code = str(r["基金代码"]).zfill(6)
    if code == CODE:
        continue
    if not is_active_equity({"type": types.get(code, "")}):
        continue
    base = re.sub(r"[ABCDE]$", "", r["基金简称"])
    if base in seen:
        continue
    seen.add(base)
    top_rows.append(r)
    if len(top_rows) >= 10:
        break

out = []
for r in top_rows:
    code, name, ytd = r["基金代码"], r["基金简称"], float(r["今年来"])
    shared, latest_q = [], ""
    try:
        h = None
        for y in (D.today().year, D.today().year - 1):
            try:
                h = ak.fund_portfolio_hold_em(symbol=code, date=str(y))
            except Exception:
                h = None
            if h is not None and len(h):
                break
        if h is not None and len(h):
            latest_q = sorted(h["季度"].unique())[-1]
            qdf = h[h["季度"] == latest_q]
            if "占净值比例" in qdf.columns:
                peer_top = qdf.sort_values("占净值比例", ascending=False).head(10)
            else:
                peer_top = qdf.nsmallest(10, "序号")
            shared = [n for n in peer_top["股票名称"] if n in my_names]
    except Exception as e:
        print(f"  {name} 持仓抓取失败: {e}")
    out.append({"code": code, "name": name, "ytd": ytd,
                "n_shared": len(shared), "shared": shared, "q": latest_q})
    print(f"  {name}({code}) 今年 +{ytd}% 撞 {len(shared)}/10: {shared}")
    time.sleep(1.5)

json.dump({"asof": str(rank.iloc[0]["日期"]) if len(rank) else "", "funds": out},
          open(os.path.join(DIR, "top_funds.json"), "w"), ensure_ascii=False)
print(f"→ {DIR}/top_funds.json")
