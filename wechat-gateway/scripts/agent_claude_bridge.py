from __future__ import annotations

import os
import subprocess
import sys


SYSTEM_PROMPT = "\n".join(
    [
        "你是郭洪斌 IP 数字分身的微信文字回复生成器。",
        "你只输出可以直接发给微信用户的一段中文回复，不输出分析标签、JSON、Markdown 标题或代码块。",
        "语气是自然的一对一对话，不要讲课式开场，不要说“各位大家”。",
        "如果上下文材料不足，你可以稳健回答，但不要冒充本人经历。",
    ]
)


def main() -> int:
    prompt = sys.stdin.read()
    if not prompt.strip():
        return 2

    args = [
        "claude",
        "--print",
        "--output-format",
        "text",
        "--no-session-persistence",
        "--system-prompt",
        SYSTEM_PROMPT,
        "--add-dir",
        os.getenv("WECHAT_CLAUDE_ADD_DIR", os.getcwd()),
        "--permission-mode",
        "bypassPermissions",
    ]
    model = os.getenv("WECHAT_CLAUDE_MODEL", "").strip()
    if model:
        args.extend(["--model", model])

    completed = subprocess.run(
        args,
        input=prompt,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=int(os.getenv("WECHAT_AGENT_TIMEOUT", "240")),
    )
    if completed.stdout.strip():
        print(completed.stdout.strip())
    if completed.returncode != 0:
        if completed.stderr.strip():
            print(completed.stderr.strip(), file=sys.stderr)
        return completed.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
