"""读取 docs/latest.json，向飞书群发一张简报卡片，附分享页链接。只用标准库。"""
import base64, hashlib, hmac, json, os, sys, time, urllib.request
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

CST = timezone(timedelta(hours=8))
today = os.environ.get("TODAY") or datetime.now(CST).date().isoformat()
repo = os.environ.get("GITHUB_REPOSITORY", "owner/repo")
owner, name = repo.split("/")
page = os.environ.get("PAGES_URL", "").strip() or f"https://{owner.lower()}.github.io/{name}/"

d = json.load(open("docs/latest.json", encoding="utf-8"))
m = d.get("market", {})
fmt = lambda v: "—" if v is None else f"{v:+.1f}%"

if d["date"] != today:
    title, tmpl = f"vstock 简报 · 今天没有新数据", "grey"
    body = (f"最新一期仍是 **{d['date']}**。\n今天可能不是交易日，或者本机的每日流程没有跑完（电脑没开机、网络不通）。")
else:
    title, tmpl = f"vstock 收盘简报 · {d['date']}", {"防守观望": "orange", "台风预警": "red"}.get(m.get("tone"), "blue")
    lines = [f"**定调：{m.get('tone', '—')}**　{m.get('toneNote', '')}",
             f"恐贪 **{m.get('fg', '—')}**（{m.get('fgLabel', '')}）　股债性价比 **{m.get('bond', '—')}°C**（{m.get('bondLabel', '')}）　美股风险层 {m.get('usRed', '—')} 红"]
    if d["radar"]:
        lines.append("\n**动量雷达**")
        for r in d["radar"][:8]:
            tag = "　例行公告" if r.get("routine") else ""
            lines.append(f"- {r['name']} {r['code']}　{fmt(r['chg'])}　量 {r['rvol']}x　{r['hits']}{tag}")
    a = [s for s in d["swing"] if s["grade"] == "A"]
    lines.append(f"\n**突破** A {len(a)} · B {len(d['swing']) - len(a)}")
    for s in a:
        lines.append(f"- {s['name']} {s['code']}　{s['status']}　触发 {s['trigger']}　止损 {s['stop']}")
    if d["ep"]:
        lines.append("\n**EP 跳空**")
        for e in d["ep"]:
            lines.append(f"- {e['name']} {e['code']}［{e['grade']}］跳空 {fmt(e['gap'])}　{e['catalyst']}　触发 {e['trigger']}")
    if d.get("t3"):
        t = d["t3"]
        lines.append(f"\n雷达 T+3：{t['n']} 条样本，平均 {fmt(t['avg'])}，胜率 {t['win']}%")
    lines.append("\n<font color='grey'>候选清单，不是买入建议。A 股 T+1。</font>")
    body = "\n".join(lines)

card = {"config": {"wide_screen_mode": True},
        "header": {"title": {"tag": "plain_text", "content": title}, "template": tmpl},
        "elements": [{"tag": "markdown", "content": body},
                     {"tag": "action", "actions": [{"tag": "button", "type": "primary",
                       "text": {"tag": "plain_text", "content": "打开完整简报"}, "url": page}]}]}

if os.environ.get("DRY_RUN"):
    print(title); print(body); print(page); sys.exit(0)
url = os.environ.get("FEISHU_WEBHOOK", "").strip()
if not url:
    sys.exit("没有配置仓库 Secret：FEISHU_WEBHOOK")
if urlparse(url).scheme != "https" or urlparse(url).hostname not in ("open.feishu.cn", "open.larksuite.com"):
    sys.exit("FEISHU_WEBHOOK 不是飞书地址")
msg = {"msg_type": "interactive", "card": card}
secret = os.environ.get("FEISHU_SECRET", "").strip()
if secret:
    ts = str(int(time.time()))
    msg["timestamp"] = ts
    msg["sign"] = base64.b64encode(hmac.new(f"{ts}\n{secret}".encode(), b"", hashlib.sha256).digest()).decode()
req = urllib.request.Request(url, data=json.dumps(msg, ensure_ascii=False).encode(), headers={"Content-Type": "application/json"})
resp = json.loads(urllib.request.urlopen(req, timeout=20).read().decode())
code = resp.get("code", resp.get("StatusCode"))
print("飞书返回", code, resp.get("msg") or resp.get("StatusMessage"))
sys.exit(0 if code == 0 else 1)
