from __future__ import annotations

import os
import subprocess
import textwrap
from dataclasses import dataclass
from pathlib import Path


DEFAULT_STYLE_NOTE = """
你现在是“郭洪斌AI助手”的文字呈现层。
默认回复控制在150字以内，除非用户明确要求详细展开、方案、拆解或长回复。
短回复也要有判断和下一步，不要堆结构。
语气要自然、坚定、能跟人对话，不要像说明书。
若本轮未注入授权 IP skill，才说明这是本地 demo；若已注入 guo-hongbin skill，不要说本地 demo。
""".strip()


@dataclass(frozen=True)
class AgentRequest:
    user_id: str
    text: str
    persona: str = "guo_hongbin"


@dataclass(frozen=True)
class AgentResponse:
    text: str
    backend: str
    ok: bool
    error: str = ""


def build_prompt(request: AgentRequest) -> str:
    return textwrap.dedent(
        f"""
        {DEFAULT_STYLE_NOTE}

        微信用户ID：{request.user_id}
        用户消息：
        {request.text}

        请生成一段可以直接发回微信的中文回复。默认150字以内；只有用户明确要求详细展开时才可以超过。不要输出分析标签。
        """
    ).strip()


class LocalAgent:
    def __init__(self) -> None:
        self.mode = os.getenv("WECHAT_AGENT_MODE", "mock").strip().lower()
        self.command = os.getenv("WECHAT_AGENT_COMMAND", "").strip()
        self.timeout_seconds = int(os.getenv("WECHAT_AGENT_TIMEOUT", "120"))
        self.context_file = os.getenv("WECHAT_AGENT_CONTEXT_FILE", "").strip()

    def reply(self, request: AgentRequest) -> AgentResponse:
        prompt = build_prompt(request)
        if self.context_file:
            prompt = self._with_context_file(prompt, self.context_file)
        if self.mode == "command" and self.command:
            return self._reply_by_command(prompt)
        if self.mode in {"codex", "claude"} and self.command:
            return self._reply_by_command(prompt)
        return self._reply_by_mock(request)

    def _with_context_file(self, prompt: str, context_file: str) -> str:
        path = Path(context_file)
        try:
            context = path.read_text(encoding="utf-8").strip()
        except Exception:
            return prompt
        return textwrap.dedent(
            f"""
            以下是本轮微信回复要加载的本地 IP / Agent 上下文文件摘要，按其加载链继续下沉：

            {context}

            ---

            {prompt}
            """
        ).strip()

    def _reply_by_command(self, prompt: str) -> AgentResponse:
        env = os.environ.copy()
        env.setdefault("PYTHONUTF8", "1")
        env.setdefault("PYTHONIOENCODING", "utf-8")
        try:
            completed = subprocess.run(
                self.command,
                input=prompt,
                text=True,
                encoding="utf-8",
                errors="replace",
                shell=True,
                capture_output=True,
                timeout=self.timeout_seconds,
                env=env,
            )
        except Exception as exc:  # pragma: no cover - defensive boundary.
            return AgentResponse(
                text="本地智能体调用失败，我这边先记录下来，稍后再回复。",
                backend=self.mode,
                ok=False,
                error=str(exc),
            )

        output = completed.stdout.strip()
        error = completed.stderr.strip()
        if completed.returncode != 0 or not output:
            return AgentResponse(
                text="本地智能体暂时没有生成有效回复，我这边先记录下来，稍后再处理。",
                backend=self.mode,
                ok=False,
                error=error or f"returncode={completed.returncode}",
            )
        return AgentResponse(text=output, backend=self.mode, ok=True, error=error)

    def _reply_by_mock(self, request: AgentRequest) -> AgentResponse:
        text = (
            "我先按第一阶段的方式回应你：这个问题先不急着做成视频数字人，"
            "而是先把微信文字对话跑通。你刚才问的是："
            f"“{request.text}”\n\n"
            "我的判断是，我们先把它拆成三步：第一，确认问题到底要解决什么；"
            "第二，把这个问题放进一个可以持续对话的结构里；第三，再决定是否需要声音或视频呈现。"
            "现在这一版是本地 demo 回复，等郭洪斌 IP skill 接进来以后，回复会从这个占位逻辑切换成正式的个人化思考链路。"
        )
        return AgentResponse(text=text, backend="mock", ok=True)
