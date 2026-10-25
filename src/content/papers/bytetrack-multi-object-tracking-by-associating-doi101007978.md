---
title: "ByteTrack: Multi-Object Tracking by Associating Every Detection Box"
description: "提出 BYTE 关联策略：不丢弃低置信度检测框，用两次关联把它们也利用起来。高分框先与现有轨迹匹配，低分框再与剩余轨迹二次匹配，从而在遮挡场景下维持轨迹连续性。在 MOT17 上取得 80.3 HOTA、77.3 IDF1，多个数据集刷新 SOTA。"
paperId: "doi:10.1007/978-3-031-20047-2_1"
topics: ["论文精读"]
tags: ["论文", "ECCV"]
draft: false
updated: "2026-10-25"
year: 2022
doi: "10.1007/978-3-031-20047-2_1"
arxiv: "2110.06864"
paperUrl: "https://arxiv.org/abs/2110.06864"
githubUrl: "https://github.com/ifzhang/ByteTrack"
---

# ByteTrack: Multi-Object Tracking by Associating Every Detection Box

| 字段 | 值 |
| --- | --- |
| 作者 | Yifu Zhang、Peize Sun、Yi Jiang、Dongdong Yu、Fucheng Weng、Zehuan Yuan、Ping Luo、Wenyu Liu、Xinggang Wang（来源：对话/笔记，未核实） |
| 年份 | 2022 |
| 发表场所 | ECCV |
| DOI | 10.1007/978-3-031-20047-2_1 |
| arXiv | 2110.06864 |
| 论文地址 | https://arxiv.org/abs/2110.06864 |
| 代码仓库 | https://github.com/ifzhang/ByteTrack |

## 核心摘要
提出 BYTE 关联策略：不丢弃低置信度检测框，用两次关联把它们也利用起来。高分框先与现有轨迹匹配，低分框再与剩余轨迹二次匹配，从而在遮挡场景下维持轨迹连续性。在 MOT17 上取得 80.3 HOTA、77.3 IDF1，多个数据集刷新 SOTA。

## 研究背景
主流多目标跟踪流水线只保留高置信度检测框参与关联，遮挡、模糊导致的低分框被直接丢弃，造成真阳性目标丢失和轨迹碎片化。

## 主要问题
如何在不更换检测器的前提下，利用被丢弃的低分检测框提升轨迹连续性与整体跟踪精度。

## 核心方法
卡尔曼滤波预测现有轨迹；第一次关联用高分框与全部轨迹做 IoU 匹配；未匹配轨迹保留，与低分框做第二次关联；匹配上的低分框仅用于延续轨迹（更新运动状态），不参与新增轨迹的初始化，避免低质量框引入噪声轨迹。

## 关键公式
$
D = D_{	ext{high}} \cup D_{	ext{low}}
$
- 检测框按置信度阈值分为高分集合与低分集合，两阶段分别参与关联（核验状态：**未核实**）

$
au_{	ext{high}} \oplus D_{	ext{high}},\ 	au_{	ext{rem}} \oplus D_{	ext{low}}
$
- 两阶段关联：先高分框对全部轨迹，再低分框对剩余轨迹（核验状态：**未核实**）

## 创新贡献
- 证明低分检测框对跟踪有显著价值，提出无需重训练检测器的 BYTE 关联策略
- 在 MOT17/MOT20 等 8 个数据集刷新 SOTA，MOT17 HOTA 80.3（当时第一）
- 部署效率高：在单卡 V100 上达到 30 FPS 的近实时跟踪

## 实验
设置：MOT17/MOT20（训练集训练，test-dev 提交评测）；检测器 YOLOX-X；关联阈值 IoU；消融验证低分框二段关联与轨迹保留策略

实验结果：{"dataset": "MOT17 test-dev", "metrics": {"HOTA": 80.3, "MOTA": 80.7, "IDF1": 77.3, "IDs": 2196}, "verified": false}

实验结果：{"dataset": "MOT20 test-dev", "metrics": {"HOTA": 77.8, "MOTA": 77.2, "IDF1": 75.2}, "verified": false}

- MOT17 test-dev：{"HOTA": 80.3, "MOTA": 80.7, "IDF1": 77.3, "IDs": 2196}（核验状态：**未核实**）
- MOT20 test-dev：{"HOTA": 77.8, "MOTA": 77.2, "IDF1": 75.2}（核验状态：**未核实**）

## 论文局限
- 关联仍基于 IoU 与运动预测，外观重识别信息未充分利用（后续 BoT-SORT 补充）
- 低分框二次关联对检测器置信度分布较敏感

## 我的研究启发（来自对话）
- 二次关联的思路与我研究的候选接入失败（candidate-access）归因可以对照：低分框被丢弃等价于 candidate gate 过严
- 轨迹保留但降级更新的做法，对 F2c 类事件的处理有借鉴意义

## 讨论记录
### 2026-10-25 · note:bytetrack-note.json
用户：论文标题：ByteTrack: Multi-Object Tracking by Associating Every Detection Box

作者：Yifu Zhang、Peize Sun、Yi Jiang、Dongdong Yu、Fucheng Weng、Zehuan Yuan、Ping Luo、Wenyu Liu、Xinggang Wang

年份：2022

发表场所：ECCV

DOI：10.1007/978-3-031-20047-2_1

arXiv：2110.06864

论文地址：https://arxiv.org/abs/2110.06864

代码：https:


## 我的研究笔记

（待写：人工笔记写在 human 区内，同步不会覆盖。）
