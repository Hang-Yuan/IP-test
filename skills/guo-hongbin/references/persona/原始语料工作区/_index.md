---
title: 郭洪斌原始语料工作区索引
type: corpus-workspace-index
project: IP_Distillation
persona: 郭洪斌
status: active
created: 2026-05-29
updated: 2026-05-29
---

# 郭洪斌原始语料工作区索引

## 加载链（上下游）

**上游**：`IP_Distillation/personas/郭洪斌/_identity.md §子目录结构` — 需要查看原始逐字稿、来源清单、课程边界或工作切片时加载。

**管辖文件（下游）：**
- `source_manifest.md` — 原始来源、授权状态、处理进度。
- `raw/` — 原始逐字稿副本，只保留文本与校验信息，不做成型记忆判断。
- `working_slices/` — 课程边界、粗切片、trace event 候选和讨论前工作材料。

**同级联动：**
- `IP_Distillation/personas/郭洪斌/R1_记忆库/_index.md` — 只有当原始语料经过讨论、标注、压缩后成为稳定可调用记忆时，才同步进入 R1。
- `IP_Distillation/personas/郭洪斌/_main.md` — 稳定机制沉淀为 M2 主 agent 配置候选时同步。
- `IP_Distillation/personas/郭洪斌/sub_M3.md` — 稳定检索偏好或数据服务接口变化时同步。
- `IP_Distillation/personas/郭洪斌/sub_M4.md` — 固定回答路径、起手、过渡、收束语沉淀时同步。

---

## 定位

本目录是 **原始语料工作区**，不是 R1 记忆库。

这里存放桌面逐字稿、来源清单、课程边界、粗切片和待讨论的 trace event 候选。它的职责是保证证据可追溯、材料可回看、讨论可展开。

**边界校正（2026-05-29）**：R1 记忆库是最后成型的记忆缩影；原始文档、未压缩逐字稿、粗切片不能直接放进 R1。处理流程应为：

```text
原始语料工作区 → 逐节细聊 / 标注 / 压缩 → 稳定记忆单元 → R1_记忆库
```

---

## 当前来源总览

| source_id | 来源 | 当前材料 | 状态 |
|---|---|---|---|
| GHB-CORPUS-001 | `郭校语料库1 水大鱼大.txt` | `raw/2026-05-28_郭校语料库1_水大鱼大.txt` + `working_slices/2026-05-28_水大鱼大_切片_v0.md` | 已入原始语料工作区；连续长课稿，待细聊 |
| GHB-CORPUS-002 | `20260529021629-郭校长八连发-逐字稿文本-1.txt` | `raw/2026-05-29_郭校长八连发_逐字稿文本-1.txt` + `working_slices/2026-05-29_郭洪斌课程边界总索引_v0.md` | 已入原始语料工作区；八节课边界 v0 |

---

## 下一步

- 先按 `working_slices/2026-05-29_郭洪斌课程边界总索引_v0.md` 做逐节细聊。
- 每轮只把稳定共识转为 trace event 或机制候选。
- 只有经过压缩、校验、可调用的记忆单元，才写入 `R1_记忆库/`。
