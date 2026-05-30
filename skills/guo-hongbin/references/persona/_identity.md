---
title: 郭洪斌 · IP 主身份
type: persona-identity
ip_subject: 郭洪斌
status: 骨架（v0）
created: 2026-05-27
updated: 2026-05-30
---

# 郭洪斌 · IP 主身份

## 加载链（上下游）

**上游**：`IP_Distillation/_overview.md` — 项目顶层。

**管辖文件（下游）：**
- `_main.md` — **M2 主 agent IP 个性化 anchor 配置**（M2 主 agent 加载源 · 四块 A/B/C/D）
- `sub_M3.md` — M3 sub-agent IP 个性化检索配置 + 统一数据服务接口
- `sub_M4.md` — M4 sub-agent 固有路径库 + 起手 / 过渡 / 收束语配置
- `sub_C1.md` — C1 sub-agent 偏好参数（强度 / 速度 + 部分推理偏好 · 补 M3 不足）
- `原始语料工作区/` — 原始逐字稿、来源清单、课程边界、工作切片
- `R1_记忆库/` — 成型记忆缩影目录（处理后才沉淀）

**同级联动：**
- `IP_Distillation/01_机制层_Loop_Model应用/sub_agent设计.md` — 架构总览（M2 orchestrator + 两阶段控制流 + 三 sub-agent + skill 两层）
- `IP_Distillation/01_机制层_Loop_Model应用/M2_机制详解.md` — M2 算子骨架与 `_main.md` 的对应关系
- `IP_Distillation/03_前台实现/阶段一_微信呈现/_overview.md` — 阶段 1 工程入口（MCP + gateway）
- `White_Matter/Operations/External_Resources/郭洪斌/_overview.md` — 公开背调 / 关系背景 / 合作判断（关系层 · 不是机制层 IP 化）
- `Cognitive_Training_Quantification/_overview.md` — 商业入口（认知量化 PPT · 90 秒上台口径）

---

## 项目定位

**首例 IP 主 dogfooding 案例**。

数字人需求方 · AI 获客业务量拓宽工具 · 参考樊登读书会类似数字人产品形式 · 重点是后端蒸馏机制（思考路径 / 思考环路）+ 前端数字人形态。

阶段 1 产品形态 = 微信文字对话 · 本地 Claude Code + Opus 4.7 + skill 蒸馏 + MCP 微信。

---

## 当前状态

**断点 / 下一步**：
- **课程边界 → 逐节细聊**：按 `原始语料工作区/working_slices/2026-05-29_郭洪斌课程边界总索引_v0.md`，一节课一节课做大段连续拆解。
- **工作切片 v0 → 机制候选**：把 `原始语料工作区/working_slices/2026-05-28_水大鱼大_切片_v0.md` 11 段对照四件 IP 化骨架（`_main.md` 四块 / `sub_M3.md` 检索偏好 / `sub_M4.md` 路径库 / `sub_C1.md` 偏好参数）填候选；确认后再沉淀入 R1。
- **转写工具 + 单 vs 对话比例拍板**（夏洛克）→ 后续 5-6 小时语料库批量转写入 `原始语料工作区/raw/`。
- **音频副语言层**（起手 / 过渡 / 节奏 / 停顿）阶段 2 深挖。
- **数据目录扩展**：`R1_记忆库/data/路径库/` + `data/case_库/`（M4 / C1 标注需求驱动 · 通过 `sub_M3.md §统一数据服务接口` 管理）。

> 进展节点 / 版本演进 / 推理链全部在 `IP_Distillation/_progress/_system_notes.md`，本文件只保留当前态。

---

## 子目录结构

```
郭洪斌/
├── _identity.md              · 项目层 metadata（本文件 · 不是 M2/sub-agent 配置）
├── _main.md                  · M2 主 agent IP 个性化 anchor（四块 A/B/C/D · 主 agent 加载源）
├── sub_M3.md                 · M3 sub-agent 检索配置 + 统一数据服务接口
├── sub_M4.md                 · M4 sub-agent 路径库 + 起手 / 过渡 / 收束语
├── sub_C1.md                 · C1 sub-agent 偏好参数（强度 / 速度 + 部分推理偏好）
├── 原始语料工作区/             · 原始逐字稿 / 来源清单 / 课程边界 / 工作切片
│   ├── _index.md             · 原始语料工作区索引（天璇维护）
│   ├── source_manifest.md    · 原始来源 / 授权 / 处理进度
│   ├── raw/                  · 原始转写语料
│   └── working_slices/       · 课程边界 + 粗切片 + trace event 候选
└── R1_记忆库/                · 成型记忆缩影目录（处理后才进入）
    └── _index.md             · R1 成型记忆库索引（天璇维护）
```

**未来扩展**（待 M4 / C1 标注需求驱动）：
- `R1_记忆库/data/路径库/` · 成型 M4 路径模板存放（M4 通过 M3 接口拉）
- `R1_记忆库/data/case_库/` · 成型 C1 推理 case 范例存放（C1 通过 M3 接口拉）

**处理流程**：原始语料工作区 → 逐节细聊 / 标注 / 压缩 → 稳定记忆单元 → `R1_记忆库/`。R1 是最后成型的记忆缩影，原始逐字稿 / 课程边界 / 粗切片不直接进 R1。

---

## 跨项目关系

- **`White_Matter/Operations/External_Resources/郭洪斌/`** — 公开背调 / 关系背景与时间线 / 合作判断（**关系层** · 不是机制层 IP 化 · 边界明确分离）
- **`Cognitive_Training_Quantification/`** — 商业入口（认知量化 PPT · 学员画像 · 高净值场景）
- **`IP_Distillation/03_前台实现/阶段一_微信呈现/`** — 阶段 1 工程入口（MCP + 本地 gateway · 调用本目录加载的 sub-agent）

---

## 内部管理规则

- **跨端分工**：
  - 原始语料采集 + 工作切片 + `原始语料工作区/` 维护 = 天璇
  - `R1_记忆库/` 成型记忆沉淀 = 天璇 / 瑶光按夏洛克确认后的结构协作
  - M2 / M3 / M4 二次标注 + `_main.md` / `sub_M3.md` / `sub_M4.md` / `sub_C1.md` 配置填充 = 瑶光
- **数据来源声明**：讲课语料库 / 公开内容 / 半私有材料分类标注 · 隐私边界遵循学员匿名化原则同款（不对外展示真实身份信息 · 内部使用）
- **新增 sub-agent 配置文件**：必须在 `sub_agent设计.md` 主架构内 · 不直接新增脱离架构的文件
