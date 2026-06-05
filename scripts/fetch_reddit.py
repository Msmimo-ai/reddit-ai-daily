"""
AI Community Daily - Fetch & Generate
从 Hacker News（官方API）+ Reddit RSS 抓取 AI Agent 工作应用真实案例
完全免费，无需任何 API Key
"""

import json, os, sys, subprocess, time, re
from datetime import datetime, timezone, timedelta
from groq import Groq
import requests

TODAY = datetime.now().strftime("%Y-%m-%d")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "docs")
OUTPUT_HTML = os.path.join(OUTPUT_DIR, f"reddit-{TODAY}.html")
GENERATE_SCRIPT = os.path.join(os.path.dirname(__file__), "generate_page.py")

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; AICommunityDaily/1.0)"}

# Hacker News 搜索关键词
HN_QUERIES = [
    "AI agent workflow automation",
    "claude copilot agent productivity",
    "built AI agent replaced task",
    "LLM automation workflow results",
    "AI agent work experience",
]

# Reddit RSS 源（RSS 不受 IP 封锁）
REDDIT_RSS = [
    "https://www.reddit.com/r/ChatGPT/search.rss?q=ai+agent+work&sort=top&t=week",
    "https://www.reddit.com/r/ClaudeAI/top.rss?t=week",
    "https://www.reddit.com/r/artificial/search.rss?q=agent+workflow&sort=top&t=week",
    "https://www.reddit.com/r/automation/top.rss?t=week",
    "https://www.reddit.com/r/MachineLearning/search.rss?q=agent+application&sort=top&t=week",
]

SELECTOR_PROMPT = """你是一个专门研究"AI Agent 在实际工作中应用"的社区观察员。

下面是从 Hacker News 和 Reddit 抓取的帖子和评论候选列表。

**任务：精选10条最有价值的真实用户分享**

筛选标准（按重要性排序）：
1. 用户亲身实践案例：用了什么 AI Agent/工具、做了什么任务、具体怎么操作、得到了什么结果
2. 有具体细节：工具名称（Claude/GPT/n8n/Zapier/Make/Cursor等）、行业、时间节省或效率提升
3. 讨论热度高（points/upvotes 多）
4. 内容独特不重复

**过滤掉**：纯理论讨论、新手提问、广告推广、重复内容。

输出 JSON 数组（不加```标记），每条字段：
- title_zh: 中文标题（25字以内，描述用户做了什么）
- original_title: 原标题（英文）
- content_zh: 中文摘要（150-200字，翻译核心内容：工具、做法、结果）
- tools: 提到的工具数组，如["Claude","n8n","Zapier"]
- use_case: 使用场景，如"数据处理"/"邮件自动化"/"代码生成"/"文档整理"等
- points: 热度分数（整数，没有填0）
- comments: 评论数（整数）
- source: 来源平台，如"Hacker News"或"Reddit r/ChatGPT"
- type: "post"或"comment"
- url: 原帖完整链接（必须真实）
- pub_time: 发布时间 YYYY-MM-DD

候选内容：
{candidates}

只输出 JSON 数组，不要解释。"""


def fetch_hn_search(query, limit=8):
    """从 Hacker News Algolia 搜索 API 抓取"""
    url = f"https://hn.algolia.com/api/v1/search?query={requests.utils.quote(query)}&tags=story&hitsPerPage={limit}&numericFilters=created_at_i>{int((datetime.now(timezone.utc) - timedelta(days=14)).timestamp())}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            return []
        hits = r.json().get("hits", [])
        results = []
        for h in hits:
            story_id = h.get("objectID", "")
            results.append({
                "type": "post",
                "title": h.get("title", ""),
                "body": h.get("story_text") or h.get("comment_text") or "",
                "source": "Hacker News",
                "points": h.get("points", 0) or 0,
                "comments": h.get("num_comments", 0) or 0,
                "url": h.get("url") or f"https://news.ycombinator.com/item?id={story_id}",
                "hn_url": f"https://news.ycombinator.com/item?id={story_id}",
                "created": datetime.fromtimestamp(h.get("created_at_i", 0), tz=timezone.utc).strftime("%Y-%m-%d"),
                "id": story_id,
            })
        return results
    except Exception as e:
        print(f"  HN搜索失败 [{query[:30]}]: {e}", file=sys.stderr)
        return []


def fetch_hn_top_comments(story_id, limit=3):
    """抓取 HN 帖子的热门评论"""
    url = f"https://hn.algolia.com/api/v1/search?tags=comment,story_{story_id}&hitsPerPage={limit}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code != 200:
            return []
        hits = r.json().get("hits", [])
        results = []
        for h in hits:
            body = h.get("comment_text", "").strip()
            body_clean = re.sub(r"<[^>]+>", " ", body).strip()
            if len(body_clean) < 80:
                continue
            results.append({
                "type": "comment",
                "title": f"HN Comment: {h.get('story_title', '')}",
                "body": body_clean[:600],
                "source": "Hacker News",
                "points": h.get("points", 0) or 0,
                "comments": 0,
                "url": f"https://news.ycombinator.com/item?id={h.get('objectID','')}",
                "hn_url": f"https://news.ycombinator.com/item?id={h.get('objectID','')}",
                "created": datetime.fromtimestamp(h.get("created_at_i", 0), tz=timezone.utc).strftime("%Y-%m-%d"),
                "id": h.get("objectID", ""),
            })
        return results
    except Exception:
        return []


def fetch_reddit_rss(feed_url):
    """通过 RSS 抓取 Reddit（不受 IP 封锁）"""
    try:
        import feedparser
        resp = requests.get(feed_url, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            print(f"  Reddit RSS {resp.status_code}: {feed_url[:60]}", file=sys.stderr)
            return []
        feed = feedparser.parse(resp.content)
        results = []
        for entry in feed.entries[:10]:
            url = entry.get("link", "")
            title = entry.get("title", "")
            summary = entry.get("summary", "")
            summary_clean = re.sub(r"<[^>]+>", " ", summary).strip()[:500]
            # 从 URL 提取 subreddit
            sub_match = re.search(r'/r/(\w+)/', url)
            subreddit = f"Reddit r/{sub_match.group(1)}" if sub_match else "Reddit"
            results.append({
                "type": "post",
                "title": title,
                "body": summary_clean,
                "source": subreddit,
                "points": 0,
                "comments": 0,
                "url": url,
                "created": TODAY,
                "id": url,
            })
        return results
    except Exception as e:
        print(f"  Reddit RSS 失败: {e}", file=sys.stderr)
        return []


def collect_all():
    all_items, seen_ids = [], set()

    # 1. Hacker News 搜索
    print("抓取 Hacker News...")
    for query in HN_QUERIES:
        posts = fetch_hn_search(query, limit=8)
        new = [p for p in posts if p["id"] not in seen_ids]
        for p in new: seen_ids.add(p["id"])
        all_items.extend(new)
        print(f"  HN [{query[:25]}]: {len(new)} 条")
        time.sleep(0.5)

    # 2. HN 热帖评论
    top_hn = sorted([i for i in all_items if i["source"] == "Hacker News"],
                    key=lambda x: x["points"], reverse=True)[:5]
    for post in top_hn:
        comments = fetch_hn_top_comments(post["id"], limit=2)
        new = [c for c in comments if c["id"] not in seen_ids]
        for c in new: seen_ids.add(c["id"])
        all_items.extend(new)
        time.sleep(0.3)

    # 3. Reddit RSS（备用源）
    print("抓取 Reddit RSS...")
    for rss_url in REDDIT_RSS:
        posts = fetch_reddit_rss(rss_url)
        new = [p for p in posts if p["id"] not in seen_ids]
        for p in new: seen_ids.add(p["id"])
        all_items.extend(new)
        print(f"  {len(new)} 条")
        time.sleep(1)

    all_items.sort(key=lambda x: x["points"] + x["comments"] * 2, reverse=True)
    print(f"共收集 {len(all_items)} 条候选内容")
    return all_items


def format_candidates(items):
    lines = []
    for i, it in enumerate(items[:60], 1):
        lines.append(
            f"{i}. [{it['source']}] {it['type'].upper()} | 👍{it['points']} 💬{it['comments']} | {it['created']}\n"
            f"   标题: {it['title']}\n"
            f"   内容: {it['body'][:300]}\n"
            f"   链接: {it['url']}"
        )
    return "\n\n".join(lines)


def clean_json(raw):
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw[raw.index("\n")+1:] if "\n" in raw else raw[3:]
    if raw.rstrip().endswith("```"):
        raw = raw.rstrip()[:-3].rstrip()
    return raw.strip()


def process_with_groq(raw_items, retry=3):
    client = Groq(api_key=os.environ["GROQ_API_KEY"])
    prompt = SELECTOR_PROMPT.format(candidates=format_candidates(raw_items))
    for attempt in range(1, retry + 1):
        try:
            print(f"调用 Groq API（第{attempt}次）...")
            resp = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2, max_tokens=4096,
            )
            raw = clean_json(resp.choices[0].message.content)
            print(f"输出前200字: {raw[:200]}")
            items = json.loads(raw)
            print(f"精选 {len(items)} 条")
            return items
        except json.JSONDecodeError as e:
            print(f"JSON解析失败（{attempt}）: {e}", file=sys.stderr)
            if attempt == retry: raise
            time.sleep(5)
        except Exception as e:
            print(f"API失败（{attempt}）: {e}", file=sys.stderr)
            if attempt == retry: raise
            time.sleep(10)


def generate_html(items):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    tmp = os.path.join(OUTPUT_DIR, f"_tmp_{TODAY}.json")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    result = subprocess.run(
        [sys.executable, GENERATE_SCRIPT, "--file", tmp, "--output", OUTPUT_HTML, "--date", TODAY],
        capture_output=True, text=True, env={**os.environ, "PYTHONUTF8": "1"}
    )
    os.remove(tmp)
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr); sys.exit(1)
    print(result.stdout.strip())


def update_index():
    import glob
    index_path = os.path.join(OUTPUT_DIR, "index.html")
    pages = sorted(glob.glob(os.path.join(OUTPUT_DIR, "reddit-????-??-??.html")), reverse=True)
    archive = "".join(
        f'<li><a href="reddit-{os.path.basename(p).replace("reddit-","").replace(".html","")}.html">'
        f'{"✦ " if os.path.basename(p).replace("reddit-","").replace(".html","") == TODAY else ""}'
        f'{os.path.basename(p).replace("reddit-","").replace(".html","")}</a></li>\n'
        for p in pages[:30]
    )
    html = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AI 社区实战日报</title>
<meta http-equiv="refresh" content="0;url=reddit-{TODAY}.html">
<style>body{{font-family:-apple-system,"PingFang SC",sans-serif;max-width:480px;margin:60px auto;padding:0 20px;color:#1e293b}}
h1{{font-size:24px}}p{{color:#64748b}}ul{{list-style:none;padding:0}}li{{margin:8px 0}}
a{{color:#ff4500;text-decoration:none}}a:hover{{text-decoration:underline}}</style>
</head><body>
<h1>🤖 AI 社区实战日报</h1>
<p>Hacker News + Reddit 真实用户 AI Agent 工作案例，正在跳转…</p>
<p style="font-size:13px;color:#94a3b8">如未跳转，<a href="reddit-{TODAY}.html">点击这里</a></p>
<h2 style="font-size:16px;margin-top:32px">历史归档</h2>
<ul>{archive}</ul>
</body></html>"""
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(html)
    print("index.html 已更新")


def main():
    print(f"=== AI Community Daily {TODAY} ===")
    if not os.environ.get("GROQ_API_KEY"):
        print("ERROR: 未设置 GROQ_API_KEY", file=sys.stderr); sys.exit(1)
    raw = collect_all()
    if not raw:
        print("ERROR: 未抓取到内容", file=sys.stderr); sys.exit(1)
    items = process_with_groq(raw)
    generate_html(items)
    update_index()
    print(f"完成！{OUTPUT_HTML}")

if __name__ == "__main__":
    main()
