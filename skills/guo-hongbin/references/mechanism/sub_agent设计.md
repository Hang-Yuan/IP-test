---
title: sub-agent 设计 · M2 orchestrator 架构 + 两阶段控制流
type: architecture-design
parent: IP_Distillation/01_机制层_Loop_Model应用
status: 活跃
created: 2026-05-28
updated: 2026-05-30
---

# sub-agent 设计

> 本文件是机制层架构的权威总览。M2 作为 orchestrator 的两阶段控制流、五件角色归位、sub-agent skill 文件两层、阶段 1 交互流程、工程层映射，全部以本文件为准。

## 加载链（上下游）

**上游**：`01_机制层_Loop_Model应用/_overview.md` — 机制层子项目顶层。

**管辖文件（下游）**：
- `M2_机制详解.md` — M2 闸门评分 + 难度调度 vector + 三层框架细则
- `M3_机制详解.md` — M3 R1 记忆库检索 + 统一数据服务接口
- `M4_机制详解.md` — M4 路径库 + 第二反馈 + 起手 / 过渡语
- `C1_机制详解.md` — C1 推理算子 + 偏好参数层 + 接收接口
- `S1_机制详解.md` — S1 接收层（主 agent context window 自带）
- `协同setting.md` — 渐进序典型轨迹 + 跨件 trace

**同级联动**：
- `IP_Distillation/_overview.md §项目三块结构 · 第一块` — 机制层在项目顶层的位置
- `IP_Distillation/02_CLI_自建/_overview.md` — sub-agent 在工程层的落地（阶段 1 = Claude Code · 阶段 2+ = 王磊 demo）
- `IP_Distillation/03_前台实现/阶段一_微信呈现/_overview.md` — 阶段 1 工程入口（MCP + gateway）
- `IP_Distillation/personas/郭洪斌/` — 首例 IP 主特化文档（M2 主 agent + sub-agent 加载源）
- `Loop Model/_overview.md` — 机制层理论基底（5 件解剖结构 / 直觉桥梁 / S007 启动注入）
- `Tripartite_Personality_Model v2.2` — M2 算法层心理学描述工具（M2 主 agent 三层 schema 来源）
- `Capability_Atlas v2 §十一` — M2 三层框架（OCEAN / adaptations / Schwartz values）

---

## 架构核心 · M2 = orchestrator

系统是 **M2 主 agent + C1 / M3 / M4 三 sub-agent + S1 接收层** 的 star 拓扑：

| 角色 | 落点 | 加载源 |
|---|---|---|
| 主 agent | **M2 · orchestrator** | `personas/郭洪斌/_main.md`（IP 个性化 anchor）|
| sub-agent | C1 / M3 / M4 | C1 加载 `sub_C1.md`（偏好参数）· M3 / M4 加载 `sub_M3.md` / `sub_M4.md` + R1 数据 |
| 接收层 | S1 = 主 agent context window 自带 · 不独立 sub-agent | — |

CC sub-agent 强制 star 拓扑：子只返回主，无横向 handoff。所有环路都穿过 M2 圆心——这与 S004（M2 = 横切 orchestrator）自洽。真正的横向 graph 需王磊 CLI 层重写，是阶段 2+ 的差集需求。

---

## M2 两阶段控制流（定稿基线）

M2 的控制流分两阶段：**闸门（plan 种子）→ 遍历（interleaved walk）**。

### 阶段一 · 闸门（T0 · M2 本地 · 不调 sub-agent）

M2 收到信号后快速评分，当场产出三样东西：

1. **情绪第一反应**——纯 M2 本地，不等任何 sub-agent，直出"啊 / 嗯 / 这个事啊"。神经底物 = Amygdala fast pathway（200-500ms）。
2. **价值 / 显著性判断**——这是 M2 本职，不延后到 walk。Schwartz values 极性 + 显著性阈值在闸门就介入，判定信号"值不值得深处理 / 触没触红线 / 落在哪个价值场"。
3. **初始遍历意图**——不是完整调度 vector，是"从哪个节点开始 walk"的种子。

### 阶段二 · 遍历（interleaved walk 决策树）

从初始节点开始 walk 决策树。**每个节点 M2 只干两件事**：

- 拉**一个** sub-agent + 指定它读哪个文件
- 看返回 → 按"价值 + 逻辑够不够"判 → 决定下一节点 or 收束

C1 思考强度、要不要实时叫停、要不要多轮 M3 深检——全部是 walk 过程中**结果依赖地**决定，不是闸门一次 plan 死。

### 为什么是两阶段，不是 plan-then-execute

调度 vector（信号显著性 / 难度 / 类型 / 时间预算 / 风险）**不是闸门一次算死，是闸门给初值、walk 中精化**。硬约束来自反例：

- **纯 plan 不成立**：M3 检索结果回来之前，M2 无法知道 C1 该多深。C1 介入本就是结果依赖的触发（M2 阈值突破 / M3 检索失败 / 多候选冲突）。若 M3 回来发现是老兵有现成路径的问题，C1 根本不该启动——但 plan-then-execute 在 M3 跑之前就把 C1 强度定死，与 Loop Model 自己的触发机制矛盾。
- **纯 walk 不成立**：情绪第一反应（闸门产出①）必须在 M2 首次评分时直出，不能等 walk 完决策树。它不依赖任何 sub-agent，是 M2 本地的 plan 种子。

两阶段同时接住：情绪反应的即时性、价值判断的前置性、C1 介入的结果依赖性、渐进序、动态化（节点可跳过 = 分支条件不满足就不进）。

---

## 五件角色归位

| 件 | 在控制流中的角色 | 个人化 |
|---|---|---|
| **M2** | orchestrator = 闸门 + walk 的执行者（star 圆心）| 真个人化（价值 / 显著性 / 调度模式）|
| **C1** | 被 walk 到的推理节点 · 结果依赖触发 · 强度不预先定 | **部分个人化**（强度 / 速度 + 部分推理偏好 · 补 M3 之不足）|
| **M3** | 被 walk 到的检索节点 + 全系统统一数据服务 | 真个人化（检索权重 / 途径 / 经验池）|
| **M4** | 被 walk 到的路径节点（第二反馈 + 起手 / 过渡语）| 真个人化（路径库 / 语料）|
| **S1** | context window buffer | 无（自带）|

### C1 的个人化边界（对 S007 的精化）

C1 的**主体推理机制同构**——人人推理架构相同，深层差异是神经权重带来的强度、速度。这一点决定 C1 不能当主 agent（主 agent 必须加载 IP 个性化 anchor），仍然成立。

但**工程上必须在 C1 承担一部分偏好设计**：真人的推理偏好主要由 M3 供（检索什么经验决定推理走向），可 LLM 的原生推理会盖过 M3 引导，单靠 M3 拉不出这个人的推理原型。所以 C1 sub-agent 要主动编码一部分偏好参数——强度 / 速度档位 + 部分推理偏好（reframe / 反事实 / 逻辑性 / 升维倾向），与 M3 分工补位。这不是"C1 是个人差异"，是"为逼近真人推理原型，主动在 C1 编码偏好补 M3 不足"。详 `personas/郭洪斌/sub_C1.md`。

### S1 的本体论边界

机制层 S1 是有运算地位的 active workspace（C1 在其上做 IPS-SPL 空间运算）。工程层 S1 退化为 buffer = 主 agent context window；运算能力分散到各 sub-agent 内部 context。Loop Model "C1 → S1 更新" 这条 trace 没断，只退化为"结果回主 agent context"。

---

## sub-agent skill 文件分两层

**第一层 · 骨架**：在 sub-agent 自己的 skill 文件——通用算子 + 接口规范 + 档位逻辑（C1 额外含偏好参数层）。

**第二层 · 数据**：大量 R1 记忆 / 路径 / 案例数据。统一存入 R1 记忆库，调用时走 M3 接口——M3 = 整个系统的统一记忆检索服务。

```
M2 主 agent ──┬─→ C1 sub-agent ──┐
              ├─→ M3 sub-agent ←─┼─ R1 记忆库数据 (personas/X/R1_记忆库/)
              └─→ M4 sub-agent ──┘  路径库 / 起手语 / 过渡语 (personas/X/R1_记忆库/data/)
                                    case 样本 / 推理范例
                                    ↑
                                    统一通过 M3 检索接口拉取
                                    （索引 + 按 M2 调度强度控制检索深度）
```

**工程意义**：
- 数据层集中 = 单一权威源 + 跨 sub-agent 一致性 + 检索逻辑统一
- 骨架层分散 = 各 sub-agent 算子边界清晰，不互相纠缠，跨模块层 sub-agent 隔离保留（= Loop Model 模块化 + 有向信息流 + 隔离的物理载体）
- 与 Loop Model "M3 为整个系统提供记忆服务" 核心机制对齐

---

## 交互流程 · 阶段 1 微信文字（turn-based）

```
[用户微信消息]
   │
   ▼
MCP / gateway → S1 接收层（M2 主 agent context window）
   │
   ▼
[阶段一 · M2 闸门 · 本地评分]
   │  加载 personas/郭洪斌/_main.md（M2 IP 个性化 anchor）
   │  当场产出：① 情绪第一反应  ② 价值 / 显著性判断  ③ 初始遍历意图
   ▼
[阶段二 · M2 遍历决策树 · interleaved walk]
   │  每节点：拉一个 sub-agent + 指定读哪个文件 → 看返回 → 判够不够 → 下一节点 / 收束
   │
   │  典型 walk（中高难度信号）：
   ├─→ 节点 · M3：检索 R1 记忆库（强度 = 当前 walk 状态决定）
   │        返回候选经验 + 类比 + 反例
   ├─→ 节点 · M4：拉路径库 + 起手 / 过渡语（M2 判难时先出过渡语）
   │        返回第二反馈段 + 起手 / 过渡候选
   ├─→ 节点 · C1：接收 M3 候选作 priming + M4 桥接作延续点
   │        加载 sub_C1.md 偏好参数 · 强度由当前 walk 状态决定
   │        输出明确逻辑推理段
   │  （每节点后 M2 判"价值 + 逻辑够不够"：够则收束，不够则继续 walk）
   ▼
[M2 整合输出]
   │  按 _main.md 输出风格组装实际 walk 轨迹为段落节奏
   ▼
MCP / gateway → 微信文字回复
```

**极简信号**（如"你好"）：walk 两步收束（情绪反应 + M4 招呼），不进 C1 节点。**文字段落节奏跟实际 walk 轨迹走，不套固定模板。**

---

## 工程层映射

### 阶段 1 · Claude Code CLI + Opus 4.7

| 机制层概念 | Claude Code 工程层落地 |
|---|---|
| M2 主 agent | Claude Code 主会话（加载 `_main.md` 作系统 prompt 一部分）|
| C1 / M3 / M4 sub-agent | Claude Code sub-agent（独立 skill / agent 文件）|
| S1 接收层 | 主会话 context window（自带）|
| 闸门阶段 | M2 主会话首次 inference（本地产出情绪 + 价值判断 + 初始意图）|
| 遍历阶段 | M2 主会话用 Task tool 逐节点调 sub-agent，每次返回后再决策 |
| M3 统一数据接口 | M3 sub-agent skill 内检索（grep / glob / 索引文件）|
| 实时叫停 + 过渡语 | M2 walk 到 C1 节点前判难 → 先输出过渡语 + 再调 C1 |
| 段落节奏 | M2 整合时把实际 walk 轨迹映射为输出段落 |

### 阶段 2+ · 王磊 CLI demo

- LangGraph state machine 实现 walk 决策树 + 条件边权重 + 动态 model selection
- Redis Streams 事件总线 = 跨 sub-agent 实时消息（差集：横向 handoff，star 拓扑之外的需求）
- 真正的 streaming + sub-agent 并发 + 中断恢复

**机制层在两个阶段不变**——M2 仍是 orchestrator，两阶段控制流仍存在，sub-agent 仍是被调度对象；只是工程层从"单点 turn-based"升级到"多点 streaming"。

---

## 工程化推进纪律

1. **项目内权威源先取**：任何 sub-agent 行为决策先扫 `_overview.md` / `5环路_子维度.md` / 本文件是否已拍，不重新论证
2. **跨项目副作用 defer**：本架构跨项目影响（Loop Model 主项目 / Capability_Atlas v2 / Tripartite v2.2 / Industry_Procedure_Skill）AI 工程化阶段不发散，单点跑通先，跨项目同步归 weekly-review 或工程层稳定后回头
3. **demo 单点跑通先**：阶段 1 全部用 Claude Code + Opus 4.7，M2 单点输出，不预期 streaming

---

## 待精化点

1. **遍历阶段"判够不够"收束准则**——walk 的停机条件，skill 里唯一真要写死的判断逻辑，整个 interleaved 控制流的承重点
2. **决策树节点拓扑**——有哪些节点、分支条件长什么样
3. **调度 vector 5 维 → sub-agent 强度档位的映射**——离散档位 vs 连续值；闸门初值如何在 walk 中精化
4. **M2 闸门一次产出多件结构化数据**（情绪反应 + 价值判断 + 初始意图）——Claude Code 工程层用 structured output / tool call 实现
5. **M3 统一数据接口规范**——sub-agent skill 如何标记"需 M3 调用的数据" + M3 索引格式
6. **C1 接收 M3 引导的接口** + **C1 偏好参数注入方式**——M3 候选作 prefix / 独立 channel；偏好参数如何进 C1 system prompt
7. **M2 实时叫停 C1 的工程语义**——turn-based 下"叫停" = 先出过渡语 + 后调 C1
8. **personas/郭洪斌/ 数据目录结构**——R1 记忆库 / data 路径库 / data case 库的建立时机
