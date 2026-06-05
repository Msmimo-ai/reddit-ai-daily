"""
Reddit AI Agent Daily - Fetch & Generate
从 Reddit 抓取真实用户分享的 AI Agent 工作应用帖子和评论
不需要 API Key，使用 Reddit 公开 JSON 接口
"""

import json, os, sys, subprocess, time, re
from datetime import datetime, timezone, timedelta
from groq import Groq
import requests

TODAY = datetime.now().strftime("%Y-%m-%d")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "docs")
OUTPUT_HTML = os.path.join(OUTPUT_DIR, f"reddit-{TODAY}.html")
GENERATE_SCRIPT = os.path.join(os.path.dirname(__file__), "generate_page.py")

# 抓取的 subreddit 和搜索词
SUBREDDITS_TOP = [
    "ChatGPT", "ClaudeAI", "artificial", "AIAssistants",
    "automation", "productivity", "nocode", "MachineLearning",
]

SEARCH_QUERIES = [
    "ai agent work automation",
    "claude copilot agent workflow",
    "ai agent replaced automated task",
    "built agent workflow results",
    "using AI agent job productivity",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; AIAgentDaily/1.0; +https://github.com/Msmimo-ai)",
    "Accept": "application/json",
}

SELECTOR_PROMPT = """你是一个专门研究"AI Agent 在实际工作中应用"的社区观察员。

下面是从 Reddit 抓取的帖子和评论候选列表。

**任务：精选10条最有价值的真实用户分享**

筛选标准（按重要性排序）：
1. 用户亲身实践案例：用了什么 AI Agent/工具、做了什么任务、具体怎么操作、得到了什么结果
2. 有具体细节：工具名称（Claude/GPT/n8n/Zapier/Make/Cursor等）、行业、时间节省或效率提升数据
3. 讨论热度高（upvotes 多或评论多）
4. 内容独特，不与其他条目重复

**过滤掉**：纯理论讨论、新手提问（没有实践内容）、广告/推广、重复内容。

对每条精选内容，输出 JSON 数组（不加```标记），字段：

- title_zh: 中文标题（25字以内，直接描述这个用户做了什么）
- original_title: 原标题（英文，保持原文）
- content_zh: 中文摘要（150-200字，忠实翻译核心内容：用了什么工具、做了什么、怎么做的、结果如何）
- tools: 提到的工具/平台数组，如["Claude","n8n","Zapier"]
- use_case: 使用场景，如"数据处理"/"邮件自动化"/"代码生成"/"客服"/"文档整理"等
- upvotes: 原帖点赞数（整数）
- comments: 原帖评论数（整数）
- subreddit: 来自哪个 subreddit，如"r/ChatGPT"
- type: "post"或"comment"
- url: 原帖/评论的完整 Reddit 链接（必须是真实链接）
- pub_time: 发布时间 YYYY-MM-DD

候选内容：
{candidates}

只输出 JSON 数组，不要解释。"""


def fetch_subreddit_top(subreddit, limit=15):
    """抓取 subreddit 当日热帖"""
    url = f"https://www.reddit.com/r/{subreddit}/top.json?t=week&limit={limit}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            print(f"  r/{subreddit} HTTP {r.status_code}", file=sys.stderr)
            return []
        data = r.json()
        posts = []
        for p in data.get("data", {}).get("children", []):
            d = p["data"]
            # 只要有实质内容的帖子
            body = d.get("selftext", "").strip()
            if len(body) < 50 and not d.get("title", ""):
                continue
            posts.append({
                "type": "post",
                "title": d.get("title", ""),
                "body": body[:500],
                "subreddit": f"r/{subreddit}",
                "upvotes": d.get("ups", 0),
                "comments": d.get("num_comments", 0),
                "url": f"https://reddit.com{d.get('permalink', '')}",
                "created": datetime.fromtimestamp(d.get("created_utc", 0), tz=timezone.utc).strftime("%Y-%m-%d"),
                "id": d.get("id", ""),
            })
        return posts
    except Exception as e:
        print(f"  r/{subreddit} 失败: {e}", file=sys.stderr)
        return []


def fetch_reddit_search(query, limit=10):
    """全站搜索"""
    url = f"https://www.reddit.com/search.json?q={requests.utils.quote(query)}&sort=top&t=week&limit={limit}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            return []
        data = r.json()
        posts = []
        for p in data.get("data", {}).get("children", []):
            d = p["data"]
            body = d.get("selftext", "").strip()
            posts.append({
                "type": "post",
                "title": d.get("title", ""),
                "body": body[:500],
                "subreddit": f"r/{d.get('subreddit', '')}",
                "upvotes": d.get("ups", 0),
                "comments": d.get("num_comments", 0),
                "url": f"https://reddit.com{d.get('permalink', '')}",
                "created": datetime.fromtimestamp(d.get("created_utc", 0), tz=timezone.utc).strftime("%Y-%m-%d"),
                "id": d.get("id", ""),
            })
        return posts
    except Exception as e:
        print(f"  搜索 [{query[:30]}] 失败: {e}", file=sys.stderr)
        return []


def fetch_top_comments(post_url, post_id, subreddit_name, limit=3):
    """抓取帖子下热门评论"""
    url = f"https://www.reddit.com/r/{subreddit_name}/comments/{post_id}.json?sort=top&limit={limit}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            return []
        data = r.json()
        comments = []
        if len(data) < 2:
            return []
        for c in data[1].get("data", {}).get("children", [])[:limit]:
            d = c.get("data", {})
            body = d.get("body", "").strip()
            if len(body) < 100:
                continue
            comments.append({
                "type": "comment",
                "title": f"Comment on: {data[0]['data']['children'][0]['data'].get('title', '')}",
                "body": body[:600],
                "subreddit": f"r/{subreddit_name}",
                "upvotes": d.get("ups", 0),
                "comments": 0,
                "url": f"https://reddit.com{d.get('permalink', '')}",
                "created": datetime.fromtimestamp(d.get("created_utc", 0), tz=timezone.utc).strftime("%Y-%m-%d"),
                "id": d.get("id", ""),
            })
        return comments
    except Exception:
        return []


def collect_all():
    all_items = []
    seen_ids = set()

    # 1. 从各 subreddit 抓热帖
    for sub in SUBREDDITS_TOP:
        posts = fetch_subreddit_top(sub, limit=12)
        new_posts = [p for p in posts if p["id"] not in seen_ids]
        for p in new_posts:
            seen_ids.add(p["id"])
        all_items.extend(new_posts)
        print(f"  r/{sub}: {len(new_posts)} 条")
        time.sleep(1)  # 礼貌延迟，避免被限速

    # 2. 全站搜索
    for query in SEARCH_QUERIES:
        posts = fetch_reddit_search(query, limit=8)
        new_posts = [p for p in posts if p["id"] not in seen_ids]
        for p in new_posts:
            seen_ids.add(p["id"])
        all_items.extend(new_posts)
        time.sleep(1.5)

    # 3. 为点赞最高的帖子抓热门评论
    top_posts = sorted(all_items, key=lambda x: x["upvotes"], reverse=True)[:5]
    for post in top_posts:
        sub_name = post["subreddit"].replace("r/", "")
        post_id = post["id"]
        comments = fetch_top_comments(post["url"], post_id, sub_name, limit=2)
        new_comments = [c for c in comments if c["id"] not in seen_ids]
        for c in new_comments:
            seen_ids.add(c["id"])
        all_items.extend(new_comments)
        time.sleep(1)

    # 按热度排序
    all_items.sort(key=lambda x: x["upvotes"] + x["comments"] * 2, reverse=True)
    print(f"共收集 {len(all_items)} 条候选内容")
    return all_items


def format_candidates(items):
    lines = []
    for i, it in enumerate(items[:60], 1):  # 最多送60条给LLM
        lines.append(
            f"{i}. [{it['subreddit']}] {it['type'].upper()} | 👍{it['upvotes']} 💬{it['comments']} | {it['created']}\n"
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
                temperature=0.2,
                max_tokens=4096,
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
<title>Reddit AI Agent 日报</title>
<meta http-equiv="refresh" content="0;url=reddit-{TODAY}.html">
<style>body{{font-family:-apple-system,"PingFang SC",sans-serif;max-width:480px;margin:60px auto;padding:0 20px;color:#1e293b}}
h1{{font-size:24px}}p{{color:#64748b}}ul{{list-style:none;padding:0}}li{{margin:8px 0}}
a{{color:#ff4500;text-decoration:none}}a:hover{{text-decoration:underline}}</style>
</head><body>
<h1>🤖 Reddit AI Agent 日报</h1>
<p>真实用户分享 AI Agent 工作应用案例，正在跳转…</p>
<p style="font-size:13px;color:#94a3b8">如未跳转，<a href="reddit-{TODAY}.html">点击这里</a></p>
<h2 style="font-size:16px;margin-top:32px">历史归档</h2>
<ul>{archive}</ul>
</body></html>"""
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(html)
    print("index.html 已更新")


def main():
    print(f"=== Reddit AI Agent Daily {TODAY} ===")
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
