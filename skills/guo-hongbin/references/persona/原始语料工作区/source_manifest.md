---
title: 郭洪斌原始语料来源清单
type: source-manifest
project: IP_Distillation
persona: 郭洪斌
status: v0
created: 2026-05-28
updated: 2026-05-29
---

# 郭洪斌原始语料来源清单

## 加载链（上下游）

**上游**：`IP_Distillation/personas/郭洪斌/原始语料工作区/_index.md §当前来源总览` — 需要核查原始语料覆盖与处理进度时读取。

**管辖文件（下游）：**
- `raw/2026-05-28_郭校语料库1_水大鱼大.txt` — 已入库原始转写。
- `raw/2026-05-29_郭校长八连发_逐字稿文本-1.txt` — 已入库原始转写。
- `working_slices/2026-05-28_水大鱼大_切片_v0.md` — 首批主题切片与 trace event 候选。
- `working_slices/2026-05-29_郭洪斌课程边界总索引_v0.md` — 新旧课程转写的课节边界总索引。

**同级联动：**
- `IP_Distillation/personas/郭洪斌/_identity.md` — persona 当前状态变化时同步。
- `IP_Distillation/prototype/assets/voice/guo_hongbin/voice_manifest.json` — 授权音频进入后同步登记。

---

## Manifest 规则

本文件是 source universe 的当前版本，不代表已经覆盖全部语料。新增材料时只追加新行，不改写旧来源判断；若旧来源状态变化，追加“处理备注”或新增版本行。

---

## 来源清单

| source_id | source_group | path_or_url | type | size_or_duration | access_status | expected_signal | notes | processing_status |
|---|---|---|---|---|---|---|---|---|
| GHB-CORPUS-001 | 本人课程语料 | `原始语料工作区/raw/2026-05-28_郭校语料库1_水大鱼大.txt` | 转写文本 | 82 KB；243 行；时间戳至 01:50:30 | 本地已入库；来源为桌面 `郭校语料库1 水大鱼大.txt` | 原始课程语料；经细聊确认后沉淀为 R1 成型记忆单元；M2/M3/M4/C1 标注来源 | 转写前缀为 `Sherlock 共享音频`，先按来源标签处理，不作为说话人判定 | 已入工作切片 v0 |
| GHB-CORPUS-002 | 本人课程语料 | `原始语料工作区/raw/2026-05-29_郭校长八连发_逐字稿文本-1.txt` | 转写文本 | 311 KB；999 行；时间戳 00:00:36-06:19:30 | 本地已入库；来源为桌面 `20260529021629-郭校长八连发-逐字稿文本-1.txt` | 原始课程语料；八节课结构；经细聊确认后沉淀为 R1 成型记忆单元 | 文件内部明确回顾前七节课并进入第八节；按八节课边界处理 | 已建课程边界 v0 |
| GHB-REL-001 | 关系语境 | `White_Matter/Operations/External_Resources/郭洪斌/_overview.md` | 项目档案 | 2.9 KB | 共享项目内可读 | 外部关系定位；合作背景 | 只作语境，不直接证明机制 | 已登记 |
| GHB-REL-002 | 关系语境 | `White_Matter/Operations/External_Resources/郭洪斌/公开背调.md` | 背调文档 | 6.5 KB | 共享项目内可读 | 公开身份与业务背景 | 只作语境 | 已登记 |
| GHB-REL-003 | 关系语境 | `White_Matter/Operations/External_Resources/郭洪斌/关系背景与时间线.md` | 时间线 | 4.0 KB | 共享项目内可读 | 接触节奏与合作窗口 | 只作语境 | 已登记 |
| GHB-REL-004 | 关系语境 | `White_Matter/Operations/External_Resources/郭洪斌/合作判断.md` | 合作判断 | 5.2 KB | 共享项目内可读 | 商业合作判断 | 不进入机制抽取 | 已登记 |
| GHB-BIZ-001 | 商业呈现 | `White_Matter/Research_and_Development/In_Progress/Cognitive_Training_Quantification/2026-05-25_郭洪斌见面_PPT大纲_v1.md` | PPT 大纲 | 11 KB | 共享项目内可读 | 商业入口、对外口径、量化诉求 | 夏洛克侧准备材料，不是郭洪斌本人语料 | 已登记 |
| GHB-BIZ-002 | 商业呈现 | `White_Matter/Research_and_Development/In_Progress/Cognitive_Training_Quantification/2026-05-26_认知能力提升展示_深色版.pptx` | 演示文稿 | 1.3 MB | 共享项目内可读 | 商业呈现层 | 只作场景背景 | 已登记 |
| GHB-VIS-001 | 前台素材 | `IP_Distillation/prototype/assets/replica/guo_hongbin_authorized.jpg` | 授权照片 | 235 KB | 已授权素材 | 前台真人形象 | 不用于机制抽取 | 已登记 |
| GHB-VIS-002 | 前台素材 | `IP_Distillation/prototype/assets/replica/guo_hongbin_authorized_halfbody.jpg` | 授权半身照片 | 119 KB | 已授权素材 | 前台真人形象 | 不用于机制抽取 | 已登记 |
| GHB-AUDIO-001 | 声音素材 | `IP_Distillation/prototype/assets/voice/guo_hongbin/incoming/` | 授权音频入口 | 待定 | 待音频文件进入 | M2 情绪反应；过渡语；语速节奏；声音克隆 | 当前只有占位提示文件 | 待入库 |
| GHB-VOICE-001 | 声音工程 | `IP_Distillation/prototype/assets/voice/guo_hongbin/voice_manifest.json` | 工程 manifest | 207 B | 项目内可读 | 声音台架状态 | 前台实现文件，不是语料本体 | 已登记 |

---

## 当前覆盖判断

当前两批语料覆盖“课程讲授场景下的宏观商业判断、赛道选择、价值启动、家庭健康管理员路径、财务免疫、能量、自由、公平、核心竞争力、全方位成功人生”等多节课主题。它还不能覆盖：

- 真实互动问答中的即兴反应。
- 反对意见下的 M2 第一出口。
- 私下沟通或一对一咨询中的路径选择。
- 音频层面的停顿、语气、重音、节奏。

因此当前适合在本工作区做 **课程边界整理 + v0 trace event 候选**，不能直接定稿郭洪斌完整 setting，也不能直接写入 R1 成型记忆库。
