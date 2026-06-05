#!/usr/bin/env python3
"""Reddit AI Agent Daily - HTML Page Generator"""

import argparse, json, os, sys
from datetime import datetime

TOOL_COLORS = {
    "Claude": "#f97316", "ChatGPT": "#10b981", "GPT-4": "#10b981",
    "n8n": "#ea580c", "Zapier": "#ff4a00", "Make": "#6d28d9",
    "Cursor": "#3b82f6", "Copilot": "#0078d4", "Gemini": "#4285f4",
    "AutoGPT": "#8b5cf6", "LangChain": "#22c55e", "CrewAI": "#ec4899",
    "Perplexity": "#06b6d4", "Notion": "#000000", "Python": "#f59e0b",
}

USE_CASE_COLORS = {
    "数据处理": "#3b82f6", "邮件自动化": "#10b981", "代码生成": "#8b5cf6",
    "客服": "#f59e0b", "文档整理": "#06b6d4", "研究分析": "#ec4899",
    "工作流程": "#f97316", "内容创作": "#84cc16", "会议总结": "#22d3ee",
    "项目管理": "#a78bfa",
}

def tool_chip(t):
    color = TOOL_COLORS.get(t, "#6b7280")
    return f'<span class="tool-chip" style="background:{color}20;color:{color};border:1px solid {color}40">{t}</span>'

def render_card(item, rank):
    title_zh = item.get("title_zh", "")
    original_title = item.get("original_title", "")
    content_zh = item.get("content_zh", "")
    tools = item.get("tools", [])
    use_case = item.get("use_case", "")
    upvotes = item.get("upvotes", 0)
    comments_count = item.get("comments", 0)
    subreddit = item.get("subreddit", "")
    item_type = item.get("type", "post")
    url = item.get("url", "#")
    pub_time = item.get("pub_time", "")

    use_case_color = USE_CASE_COLORS.get(use_case, "#6b7280")
    tools_html = "".join(tool_chip(t) for t in tools) if tools else ""
    type_badge = "💬 评论" if item_type == "comment" else "📝 帖子"
    rank_display = f'<span class="rank">#{rank}</span>' if rank <= 3 else ""

    # 格式化点赞数
    upvotes_display = f"{upvotes/1000:.1f}k" if upvotes >= 1000 else str(upvotes)

    return f"""
    <article class="card">
      <div class="card-reddit-bar"></div>
      <div class="card-body">
        <div class="card-top">
          <div class="card-top-left">
            <span class="subreddit">{subreddit}</span>
            <span class="type-badge">{type_badge}</span>
          </div>
          <div class="card-top-right">
            {rank_display}
            <span class="stat">👍 {upvotes_display}</span>
            <span class="stat">💬 {comments_count}</span>
          </div>
        </div>
        <h2 class="card-title">{title_zh}</h2>
        <p class="original-title">{original_title}</p>
        {'<div class="use-case-badge" style="background:' + use_case_color + '20;color:' + use_case_color + '">' + use_case + '</div>' if use_case else ''}
        {'<div class="tools-row">' + tools_html + '</div>' if tools_html else ''}
        <p class="card-content">{content_zh}</p>
        <div class="card-footer">
          <span class="pub-meta">{pub_time}</span>
          <a class="btn-reddit" href="{url}" target="_blank">查看原帖 →</a>
        </div>
      </div>
    </article>"""


def generate_html(items, date_str, generated_at):
    count = len(items)
    cards = "\n".join(render_card(item, i+1) for i, item in enumerate(items))

    # 统计工具使用频率
    tool_freq = {}
    for item in items:
        for t in item.get("tools", []):
            tool_freq[t] = tool_freq.get(t, 0) + 1
    top_tools = sorted(tool_freq.items(), key=lambda x: x[1], reverse=True)[:5]
    top_tools_html = "".join(
        f'<span class="top-tool-chip">{t} <b>{n}</b></span>' for t, n in top_tools
    )

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0,maximum-scale=1.0">
<title>Reddit AI Agent 日报 · {date_str}</title>
<style>
  :root {{
    --bg:#f6f7f8; --surface:#fff; --text:#1c1c1c; --text2:#576069;
    --border:#edeff1; --radius:12px; --shadow:0 1px 6px rgba(0,0,0,0.07);
    --reddit:#ff4500; --max:480px;
  }}
  @media(prefers-color-scheme:dark) {{
    :root {{ --bg:#1a1a1b; --surface:#272729; --text:#d7dadc; --text2:#818384; --border:#343536; --shadow:0 1px 6px rgba(0,0,0,0.3); }}
  }}
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif;background:var(--bg);color:var(--text);padding-bottom:48px}}

  .header{{background:var(--surface);border-bottom:1px solid var(--border);padding:16px 16px 12px;position:sticky;top:0;z-index:100}}
  .header-inner{{max-width:var(--max);margin:0 auto;display:flex;justify-content:space-between;align-items:center}}
  .logo{{font-size:18px;font-weight:800}}
  .logo span{{color:var(--reddit)}}
  .header-right{{font-size:12px;color:var(--text2);text-align:right;line-height:1.6}}
  .header-date{{font-weight:700;font-size:13px;color:var(--text)}}

  .tools-bar{{max-width:var(--max);margin:10px auto 0;padding:0 16px;display:flex;flex-wrap:wrap;gap:6px;align-items:center}}
  .tools-label{{font-size:11px;color:var(--text2);font-weight:600;margin-right:2px}}
  .top-tool-chip{{font-size:11px;background:var(--border);color:var(--text2);padding:3px 8px;border-radius:10px}}
  .top-tool-chip b{{color:var(--text);margin-left:3px}}

  main{{max-width:var(--max);margin:0 auto;padding:12px;display:flex;flex-direction:column;gap:10px}}

  .card{{background:var(--surface);border-radius:var(--radius);border:1px solid var(--border);box-shadow:var(--shadow);overflow:hidden;transition:box-shadow .15s}}
  @media(hover:hover){{.card:hover{{box-shadow:0 3px 16px rgba(0,0,0,0.12)}}}}
  .card-reddit-bar{{height:3px;background:var(--reddit)}}
  .card-body{{padding:12px 14px 14px}}

  .card-top{{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;gap:6px}}
  .card-top-left{{display:flex;gap:6px;align-items:center;flex-wrap:wrap}}
  .card-top-right{{display:flex;gap:6px;align-items:center;flex-shrink:0}}
  .subreddit{{font-size:11px;font-weight:700;color:var(--reddit)}}
  .type-badge{{font-size:10px;color:var(--text2);background:var(--border);padding:2px 6px;border-radius:6px}}
  .stat{{font-size:11px;color:var(--text2)}}
  .rank{{font-size:14px;font-weight:900;color:#f59e0b}}

  .card-title{{font-size:15px;font-weight:700;line-height:1.4;margin-bottom:4px;letter-spacing:-.2px}}
  .original-title{{font-size:11px;color:var(--text2);margin-bottom:8px;font-style:italic;line-height:1.4}}

  .use-case-badge{{display:inline-block;font-size:10px;font-weight:700;padding:3px 9px;border-radius:10px;margin-bottom:8px}}
  .tools-row{{display:flex;flex-wrap:wrap;gap:5px;margin-bottom:10px}}
  .tool-chip{{font-size:11px;font-weight:600;padding:3px 8px;border-radius:8px}}

  .card-content{{font-size:13px;color:var(--text2);line-height:1.7;margin-bottom:12px}}

  .card-footer{{display:flex;justify-content:space-between;align-items:center}}
  .pub-meta{{font-size:11px;color:var(--text2)}}
  .btn-reddit{{font-size:12px;font-weight:700;color:#fff;background:var(--reddit);padding:5px 12px;border-radius:20px;text-decoration:none;white-space:nowrap}}
  .btn-reddit:hover{{background:#e03d00}}

  .footer{{max-width:var(--max);margin:20px auto 0;padding:0 16px;font-size:11px;color:var(--text2);text-align:center;line-height:1.8}}
</style>
</head>
<body>

<header class="header">
  <div class="header-inner">
    <div class="logo">🤖 <span>Reddit</span> AI Agent</div>
    <div class="header-right">
      <div class="header-date">{date_str}</div>
      <div>真实案例 {count} 条</div>
    </div>
  </div>
  <div class="tools-bar">
    <span class="tools-label">今日热门工具：</span>
    {top_tools_html}
  </div>
</header>

<main>
{cards}
</main>

<div class="footer">
  来源：Reddit · r/ChatGPT · r/ClaudeAI · r/artificial · r/automation 等<br>
  内容为真实用户分享，由 AI 筛选翻译 · 每天 06:00 自动更新
</div>

</body>
</html>"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--file"); parser.add_argument("--data")
    parser.add_argument("--output", required=True)
    parser.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"))
    args = parser.parse_args()

    if args.file:
        with open(args.file, "r", encoding="utf-8-sig") as f:
            items = json.load(f)
    elif args.data:
        items = json.loads(args.data)
    else:
        print("Error: --file or --data required", file=sys.stderr); sys.exit(1)

    html = generate_html(items, args.date, datetime.now().strftime("%H:%M"))
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Generated: {args.output} ({len(items)} posts)")

if __name__ == "__main__":
    main()
