"""抓取天天基金 pingzhongdata 单文件接口,解析关键变量落缓存。

一次请求可得:申购赎回/总份额、持有人结构、规模、经理(含照片+东财五维分)、
平台五维评价、同类排名走势、估算仓位序列。见 SKILL.md「一击必中接口」。
"""
import json
import os
import re
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fund_meta import require_code
CODE = require_code()
DIR = os.path.join(ROOT, ".cache", f"fund_{CODE}")
os.makedirs(DIR, exist_ok=True)

req = urllib.request.Request(
    f"https://fund.eastmoney.com/pingzhongdata/{CODE}.js",
    headers={"User-Agent": "Mozilla/5.0", "Referer": "https://fund.eastmoney.com/"})
raw = urllib.request.urlopen(req, timeout=15).read().decode("utf-8-sig", errors="ignore")


def grab(name):
    m = re.search(rf'var {name}\s*=\s*(\[.*?\]|\{{.*?\}}|"[^"]*")\s*;', raw, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError:
        return None


out = {k: grab(k) for k in [
    "Data_buySedemption",        # 每期申购/赎回/总份额(亿份)
    "Data_holderStructure",      # 机构/个人/内部持有比例
    "Data_fluctuationScale",     # 每期规模+环比
    "Data_currentFundManager",   # 经理:任期/总规模/星级/照片/东财五维
    "Data_performanceEvaluation",  # 平台五维评价(基金口径)
    "Data_rateInSimilarType",    # 同类排名走势
    "Data_fundSharesPositions",  # 估算股票仓位(derived,非披露值)
]}
json.dump(out, open(os.path.join(DIR, "pingzhongdata.json"), "w"), ensure_ascii=False)

bs = out["Data_buySedemption"]
print(f"申赎期数: {len(bs['categories'])}  {bs['categories'][0]} → {bs['categories'][-1]}")
for s in bs["series"]:
    print(f"  {s['name']}: 最近3期 {s['data'][-3:]}")
mgrs = out["Data_currentFundManager"] or []
if not isinstance(mgrs, list):
    mgrs = [mgrs] if mgrs else []
mgr = mgrs[0] if mgrs else {}
print(f"经理: {mgr.get('name')} 东财五维均分 {mgr.get('power', {}).get('avr')}")


def _photo_candidates(url):
    u = (url or "").strip()
    if u.startswith("//"):
        u = "https:" + u
    if not u.startswith("http"):
        return []
    out = [u]
    if u.startswith("http://"):
        out.append("https://" + u[7:])
    else:
        out.append("http://" + u[8:])
    return list(dict.fromkeys(out))


def _looks_like_image(data):
    return bool(data) and len(data) >= 800 and (
        data.startswith(b"\x89PNG") or data[:2] == b"\xff\xd8" or data[:6] in (b"GIF87a", b"GIF89a")
    )


def _save_photo(url, dest):
    last = None
    for u in _photo_candidates(url):
        try:
            req2 = urllib.request.Request(
                u, headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                    "Referer": "https://fund.eastmoney.com/",
                    "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
                })
            data = urllib.request.urlopen(req2, timeout=20).read()
            if _looks_like_image(data):
                open(dest, "wb").write(data)
                return True
            last = f"not image ({len(data)}B) {u[:48]}"
        except Exception as e:
            last = e
    if last:
        print(f"  照片未获取: {last}")
    return False


photo = os.path.join(DIR, "manager_photo.png")
cached = b""
if os.path.exists(photo):
    cached = open(photo, "rb").read()
have = _looks_like_image(cached)
if not have:
    pics = [m.get("pic") for m in mgrs if isinstance(m, dict) and m.get("pic")]
    for pic in pics:
        if _save_photo(pic, photo):
            print(f"  照片 → {photo}")
            break
    else:
        if cached:
            print(f"  照片缓存不是图片 ({len(cached)}B),未替换")
else:
    print(f"  照片已缓存 {len(cached)}B")
print(f"→ {DIR}/pingzhongdata.json")
