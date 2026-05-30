from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path


DEFAULT_SKILL_PATH = Path.home() / ".codex" / "skills" / "guo-hongbin" / "SKILL.md"
COMMON_CONTEXT_FILES = [
    Path("SKILL.md"),
    Path("references/persona/_identity.md"),
    Path("references/mechanism/sub_agent设计.md"),
]
M2_CONTEXT_FILES = [
    *COMMON_CONTEXT_FILES,
    Path("references/persona/_main.md"),
]
R1_CONTEXT_FILES = [
    Path("references/persona/R1_记忆库/_index.md"),
    Path("references/persona/原始语料工作区/_index.md"),
]


@dataclass(frozen=True)
class SubAgentSpec:
    name: str
    role: str
    context_files: tuple[Path, ...]


@dataclass(frozen=True)
class CodexResult:
    ok: bool
    text: str
    error: str = ""


SUB_AGENT_SPECS = [
    SubAgentSpec(
        name="C1",
        role="负责逻辑推理、反例、边界、因果链和是否需要展开。只给M2内部判断，不直接回复用户。",
        context_files=(
            *COMMON_CONTEXT_FILES,
            Path("references/persona/sub_C1.md"),
        ),
    ),
    SubAgentSpec(
        name="M3",
        role="负责检索记忆、案例、时间轴、语料锚点和相似问题。只给M2内部候选材料，不直接回复用户。",
        context_files=(
            *COMMON_CONTEXT_FILES,
            Path("references/persona/sub_M3.md"),
            *R1_CONTEXT_FILES,
        ),
    ),
    SubAgentSpec(
        name="M4",
        role="负责微信口吻、起手式、转折、短答路径和郭洪斌说话质感。只给M2内部表达建议，不直接回复用户。",
        context_files=(
            *COMMON_CONTEXT_FILES,
            Path("references/persona/sub_M4.md"),
            *R1_CONTEXT_FILES,
        ),
    ),
]


def find_codex() -> str | None:
    configured = os.getenv("CODEX_CLI", "").strip()
    local_bin = Path(os.getenv("LOCALAPPDATA", "")) / "OpenAI" / "Codex" / "bin"
    bundled = sorted(local_bin.glob("*/codex.exe"), reverse=True) if local_bin.exists() else []
    candidates = [configured, str(local_bin / "codex.exe"), *(str(path) for path in bundled), shutil.which("codex")]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return candidate
    return shutil.which("codex")


def get_skill_root() -> Path:
    skill_path = Path(os.getenv("WECHAT_CODEX_SKILL_PATH", str(DEFAULT_SKILL_PATH))).expanduser()
    return skill_path.parent


def load_context(skill_root: Path, files: list[Path] | tuple[Path, ...]) -> str:
    chunks: list[str] = []
    for relative in files:
        path = skill_root / relative
        try:
            text = path.read_text(encoding="utf-8", errors="replace").strip()
        except Exception:
            continue
        chunks.append(f"===== {relative.as_posix()} =====\n{text}")
    if not chunks:
        return ""
    return "\n\n".join(chunks)


def env_enabled(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}


def int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def run_codex_prompt(codex: str, prompt: str, timeout: int) -> CodexResult:
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", errors="replace", suffix=".txt", delete=False) as handle:
        handle.write(prompt)
        prompt_path = Path(handle.name)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", errors="replace", suffix=".txt", delete=False) as handle:
        output_path = Path(handle.name)

    completed: subprocess.CompletedProcess[str] | None = None
    try:
        codex_args = [
            codex,
            "exec",
            "--skip-git-repo-check",
            "--ephemeral",
            "--disable",
            "hooks",
            "--disable",
            "plugins",
            "--ignore-rules",
            "--sandbox",
            "danger-full-access",
            "--cd",
            str(prompt_path.parent),
        ]
        if env_enabled("WECHAT_CODEX_IGNORE_USER_CONFIG", True):
            codex_args.append("--ignore-user-config")
        codex_args.extend(
            [
                "-m",
                os.getenv("WECHAT_CODEX_MODEL", "gpt-5.5"),
                "-c",
                'approval_policy="never"',
                "-c",
                'model_reasoning_effort="low"',
                "-o",
                str(output_path),
            ]
        )
        runner_prompt = "\n".join(
            [
                "You are a bridge for an internal WeChat reply generator.",
                "Read the UTF-8 prompt file at this exact Windows path:",
                str(prompt_path),
                "The file contains all role instructions, local context, and the incoming message.",
                "Follow that file exactly.",
                "Return only the requested Chinese text.",
                "Do not mention files, Codex, skills, logs, or limitations.",
            ]
        )
        completed = subprocess.run(
            codex_args + [runner_prompt],
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        return CodexResult(False, "", f"timeout after {timeout}s: {exc}")
    except OSError as exc:
        return CodexResult(False, "", f"Codex CLI bridge is not executable from this shell: {exc}")
    finally:
        prompt_path.unlink(missing_ok=True)

    output = ""
    try:
        output = output_path.read_text(encoding="utf-8", errors="replace").strip()
    except Exception:
        output = completed.stdout.strip() if completed else ""
    finally:
        output_path.unlink(missing_ok=True)

    if completed.returncode != 0:
        error = completed.stderr.strip() or f"returncode={completed.returncode}"
        return CodexResult(False, output, error)
    if not output:
        return CodexResult(False, "", completed.stderr.strip() or "empty output")
    return CodexResult(True, output, completed.stderr.strip())


def build_sub_agent_prompt(spec: SubAgentSpec, context: str, inbound_prompt: str) -> str:
    return "\n".join(
        [
            f"你是郭洪斌 IP 回复系统里的 {spec.name} sub-agent。",
            spec.role,
            "这是内部并行评估，不是最终微信回复。不要和用户说话，不要输出寒暄。",
            "请严格根据你加载到的路径材料给 M2 主 agent 提供判断。",
            "默认微信最终回复会控制在150字以内；除非用户明确要求详细展开，才建议放开长度。",
            "",
            f"【{spec.name} 对应路径材料】",
            context,
            "",
            "【本轮微信消息】",
            inbound_prompt,
            "",
            "【输出要求】",
            "用中文输出不超过300字的内部意见，包含：1. 你看到的关键判断；2. 可用锚点或反例；3. 给M2的回复建议。不要输出最终回复。",
        ]
    )


def run_sub_agents(codex: str, skill_root: Path, inbound_prompt: str) -> dict[str, CodexResult]:
    timeout = int_env("WECHAT_SUB_AGENT_TIMEOUT", 240)
    results: dict[str, CodexResult] = {}
    with ThreadPoolExecutor(max_workers=len(SUB_AGENT_SPECS)) as executor:
        future_map = {}
        for spec in SUB_AGENT_SPECS:
            context = load_context(skill_root, spec.context_files)
            prompt = build_sub_agent_prompt(spec, context, inbound_prompt)
            future_map[executor.submit(run_codex_prompt, codex, prompt, timeout)] = spec.name
        for future in as_completed(future_map):
            name = future_map[future]
            try:
                results[name] = future.result()
            except Exception as exc:  # pragma: no cover - defensive boundary.
                results[name] = CodexResult(False, "", str(exc))
    return results


def build_m2_prompt(inbound_prompt: str, m2_context: str, sub_results: dict[str, CodexResult]) -> str:
    sub_blocks = []
    for name in ["C1", "M3", "M4"]:
        result = sub_results.get(name)
        if not result:
            sub_blocks.append(f"===== {name} =====\n未返回。")
        elif result.ok:
            sub_blocks.append(f"===== {name} =====\n{result.text}")
        else:
            fallback = result.text.strip() or "无有效输出"
            sub_blocks.append(f"===== {name} =====\n调用失败：{result.error}\n残余输出：{fallback}")
    return "\n".join(
        [
            "你是郭洪斌 IP 回复系统的 M2 orchestrator 主 agent。",
            "本轮已经并行拉起 C1 / M3 / M4 三个 sub-agent。你必须综合三路内部意见，再生成最终微信回复。",
            "只输出可以直接发给微信用户的一段中文回复，不输出分析标签、JSON、Markdown 标题、代码块、文件路径、调试说明或 sub-agent 名称。",
            "默认回复必须控制在150个中文字符以内。只有当用户明确要求详细展开、方案、拆解、长回复或多步骤建议时，才允许超过150字。",
            "短回复仍要保留判断、关键理由和下一步；不要为了像本人而展开成讲课稿。",
            "这是配置好的授权前端测试，不要说“本地demo”、不要说自己没有接到真实IP skill。",
            "保持一对一微信对话口吻，不要讲课式开场，不要暴露私有语料或内部机制名。",
            "",
            "【M2 主控路径材料】",
            m2_context,
            "",
            "【C1 / M3 / M4 并行内部意见】",
            "\n\n".join(sub_blocks),
            "",
            "【本轮微信消息】",
            inbound_prompt,
            "",
            "【最终输出】",
            "综合判断后，只给最终微信回复正文。",
        ]
    )


def main() -> int:
    prompt = sys.stdin.read()
    if not prompt.strip():
        return 2

    codex = find_codex()
    if not codex:
        print("Codex CLI is not available on PATH.", file=sys.stderr)
        return 1

    skill_root = get_skill_root()
    sub_results: dict[str, CodexResult] = {}
    if env_enabled("WECHAT_PARALLEL_SUB_AGENTS", True):
        sub_results = run_sub_agents(codex, skill_root, prompt)
    m2_context = load_context(skill_root, M2_CONTEXT_FILES)
    wrapped = build_m2_prompt(prompt, m2_context, sub_results)
    result = run_codex_prompt(codex, wrapped, int_env("WECHAT_M2_TIMEOUT", 300))
    if result.text:
        print(result.text)
    if not result.ok:
        if result.error:
            print(result.error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
