---
title: "DMTrack: Deformable State-Space Modeling for UAV Multi-Object Tracking"
description: "这篇论文的核心并不是简单地“用 Mamba 替换卡尔曼滤波器”，而是试图回答一个更实际的问题：在无人机多目标跟踪中，线性运动模型和学习型非线性运动模型各有优缺点，能不能让系统根据当前轨迹状态自己判断该相信谁，并把这种可信度进一步传递到数据关联阶段？"
paperId: "title:d9eee4977b8bbd81"
topics: ["论文精读"]
tags: ["论文"]
draft: false
updated: "2026-11-03"
---

# DMTrack：Deformable State-Space Modeling for UAV Multi-Object Tracking 精读

> ⚠️ 本条目由 AI 从对话中提取，所有公式与实验数字均未核实，引用前请对照原文。

| 字段 | 值 |
| --- | --- |
| 中文译名 | DMTrack：面向无人机多目标跟踪的可变形状态空间建模 |

## 总体深度解读

这篇论文的核心并不是简单地“用 Mamba 替换卡尔曼滤波器”，而是试图回答一个更实际的问题：**在无人机多目标跟踪中，线性运动模型和学习型非线性运动模型各有优缺点，能不能让系统根据当前轨迹状态自己判断该相信谁，并把这种可信度进一步传递到数据关联阶段？**

这也是我认为理解 DMTrack 最重要的主线。

无人机多目标跟踪（**UAV Multi-Object Tracking, UAV-MOT**）比固定摄像机下的 MOT 困难得多。画面中的目标运动并不完全来自目标自己，还叠加了无人机平台的平移、旋转、俯仰以及视角变化。与此同时，空中视角下目标通常尺寸小、纹理弱、遮挡频繁，因此传统依靠 **Re-ID（Re-Identification，重识别）外观特征**进行身份判别的方法也容易失效。论文因此选择了一条非常明确的路线：**完全去掉 Re-ID，把身份保持尽可能交给运动预测和运动关联解决。** 

作者认为传统 **Kalman Filter（卡尔曼滤波器）** 的主要问题是其运动假设过于刚性——通常接近恒速度或局部线性变化。当目标突然加速、转向，或者无人机本身发生剧烈运动时，Kalman 预测框容易偏离真实目标，随后 IoU 降低，匹配错误，最终发生 ID Switch。另一方面，单纯使用神经网络运动预测器虽然能学习非线性运动，却容易受到轨迹噪声、遮挡和训练分布变化影响。因此 DMTrack 没有选择“二选一”，而是构造了一个**经典模型 + 数据驱动模型 + 不确定性关联**的混合体系。

论文整个结构可以浓缩为：

**历史轨迹 → DeformMamba 非线性预测**  
　　　　　　　　　↘  
　　　　　　　　　　**MotionGate → 融合预测 → Uncertainty-Aware Association → ID匹配**  
　　　　　　　　　↗  
**历史状态 → Kalman 稳定预测**

其中第一项创新是 **DeformMamba（可变形 Mamba 运动预测器）**。这里“Deformable”不是图像中的可变形卷积，而是**在时间轴上可变形采样历史状态**。每条轨迹保留最近 $T=8$ 个状态，每个状态是

$$

[x,y,a,h,v_x,v_y,v_a,v_h]

$$

即中心位置、框尺度及对应速度。传统序列模型通常把这 8 个历史状态等距全部输入，而 DMTrack 首先通过一个 MLP 预测 $K=4$ 个连续时间偏移。例如模型可能不取固定的 $t-1,t-2,t-3,t-4$，而学习到类似 0.7、2.4、4.8、6.3 这样的历史位置，再通过线性插值得到 4 个关键状态。随后这 4 个状态被送进三层 Mamba 编码器。换句话说，**模型不仅学习“历史轨迹是什么”，还学习“当前预测应该重点看历史中的哪几个时刻”。** 图3实际上就是整篇论文最关键的技术图。

第二项创新是 **MotionGate（运动门控融合）**。作者没有默认 DeformMamba 永远比 Kalman 好，而是同时产生 Kalman 预测 $x^{kal}$ 和 Mamba 预测 $x^{mam}$，然后学习一个八维门控系数：

$$

\alpha_t\in(0,1)^8

$$

最终：

$$

x^{fuse}
=
\alpha x^{kal}
+
(1-\alpha)x^{mam}.

$$

这里非常重要的是：**α 不是一个标量，而是每一个状态维度各自决定。** 因此模型可能在 $x,y$ 位置预测上更相信 Mamba，而在目标高度、宽度变化上更相信 Kalman。这比简单平均两个预测器具有明显更高的自由度。与此同时，MotionGate 还预测 Mamba 的不确定性，并与 Kalman uncertainty 一起得到最终 $\sigma^{fuse}$。

第三项创新是 **Uncertainty-Aware Matching（不确定性感知关联）**。DMTrack 不使用外观特征，而把最终关联分数写成：

$$

Score
=
0.7\,IoU
+
0.2\,TrendSim
+
0.1\,Penalty .

$$

即空间重叠、运动方向一致性以及预测不确定性共同决定匹配。由此形成一种完整逻辑：

> **先预测目标在哪里 → 再判断这个预测有多可信 → 最后让预测可信度影响关联。**

这实际上比“把一个更强的神经网络替换 Kalman”更有研究价值，因为它开始把**运动预测误差、模型可信度以及数据关联**连接成一个体系。

实验数据也表明三部分并非完全冗余。VisDrone 上基础 Kalman tracker 为 **35.7 MOTA / 48.3 IDF1**；加入 DeformMamba 后达到 **41.8 / 54.8**；继续加入 MotionGate 后达到 **44.6 / 58.2**；最后加入 uncertainty-aware matching 后得到 **47.8 / 61.7**。UAVDT 上同样从 **41.6 / 59.1** 提升到 **54.8 / 72.2**。因此作者认为提升不只是来自神经运动预测器，而是来自**非线性运动建模—可信度融合—关联决策**三层协同。

但这篇论文也有非常值得警惕的地方。尤其是：它声称解决“无人机剧烈运动”，但实际上并没有显式估计 camera motion；所谓不确定性惩罚的公式也存在值得推敲的数学行为；而且只报告 MOTA 和 IDF1，没有 HOTA、AssA、IDSW 等指标，很难真正证明提升究竟来自检测、轨迹连续性还是身份关联。此外，作者对 VisDrone 和 UAVDT **分别训练运动模型**，因此论文更能说明“域内有效”，并不能充分证明跨场景泛化能力。

所以，我会把 DMTrack 定位为：

**一篇非常有启发性的“混合运动模型 + 运动可信度驱动关联”论文，但目前证据还不足以证明它已经彻底解决 UAV-MOT 的运动不确定性问题。**

---

### 一、研究目标：作者真正想解决的是什么？

作者针对的是 UAV-MOT 中非常具体的一条失败链：

$$

\text{复杂/突变运动}
\rightarrow
\text{运动预测错误}
\rightarrow
\text{IoU下降}
\rightarrow
\text{错误关联}
\rightarrow
\text{ID Switch}.

$$

论文指出两个根本矛盾。

第一个是**Kalman 稳定但不灵活**。短时间直线运动时，Kalman 非常可靠，而且几乎不需要训练；但突然转弯、快速加速或者摄像机发生剧烈运动后，它的恒速度假设迅速失效。

第二个是**学习型模型灵活但可能不稳定**。Mamba、LSTM 等可以学习复杂运动，但面对遮挡、噪声轨迹、分布外场景时，预测可能突然失真。

因此作者没有问：

> “怎么设计一个比 Kalman 更强的 motion model？”

而更接近于问：

> “能否让 Kalman 和学习型 Motion Model 在不同情况下发挥各自优势？”

论文原文把这一点概括为：

> “balance physical stability and learned adaptability”

即**在物理模型的稳定性和学习模型的适应能力之间取得平衡**。

从产业角度，这一点也很重要。无人机上的算力、功耗和通信带宽通常受到限制，如果能够在没有大型 Re-ID 网络的情况下完成稳定 MOT，那么在巡检、交通监控、应急响应和边缘无人机视觉中具有实际价值。

---

### 二、核心方法：DMTrack到底是怎样工作的？

论文图2给出了完整框架。我建议不要把三个创新点孤立理解，而是把它们看成三个连续层次：

| 层次 | 模块 | 解决的问题 |
|---|---|---|
| 运动信息选择 | DeformMamba | 历史轨迹中哪些时刻值得参考？ |
| 预测模型选择 | MotionGate | 当前应该更相信 Kalman 还是 Mamba？ |
| 关联可信度 | UAM | 当前预测值得多大程度用于匹配？ |

#### 1. DeformMamba：不是“所有历史都一样重要”

传统序列模型通常输入：

$$

X_{t-7},X_{t-6},...,X_t.

$$

DMTrack 首先把 $8\times8$ 的历史轨迹展平成 64 维，然后预测四个时间 offset：

$$

O=
\sigma(MLP(Flatten(X)))\cdot(T-1).

$$

因为 sigmoid 把结果限制在 $0\sim7$，所以 offset 实际表示历史轨迹中的连续位置。

假设得到：

$$

O=[0.6,2.2,4.7,6.4].

$$

其中 2.2 并不存在真实帧，于是论文做线性插值：

$$

\tilde{x}_i
=
(1-\alpha)X_l+\alpha X_r.

$$

这相当于一种**可微分时间采样器**。

它的设计思想非常漂亮：

传统方法：

$$

\text{所有历史帧}
\rightarrow
\text{模型自己提取重要信息}

$$

DMTrack：

$$

\text{先找到重要历史位置}
\rightarrow
\text{再建模运动规律}.

$$

因此 DeformMamba 的真正创新点未必是 Mamba 本身，而很可能是：

> **Learnable temporal resampling——可学习的时间重采样。**

这是阅读这篇论文时很容易被“Mamba”这个名字掩盖掉的一点。

---

#### 2. Mamba在这里到底起什么作用？

论文使用的 **State Space Model（状态空间模型，SSM）**基本形式是：

$$

h_t=\hat Ah_{t-1}+\hat Bx_t

$$

$$

y_t=Ch_t+Dx_t.

$$

直观理解就是：

$$

\text{过去状态}
+
\text{当前输入}
\rightarrow
\text{新的隐藏运动状态}.

$$

Mamba进一步让状态转移过程依赖输入，使模型能够选择性保留或者遗忘历史信息。

因此在 DMTrack 中：

$$

4个关键运动状态
\rightarrow
Mamba
\rightarrow
预测下一帧8维状态.

$$

但这里有一个非常重要的批判点：

**论文一直强调 Mamba 的 long-range dependency，但实际历史窗口只有 T=8，采样后甚至只剩 K=4 个 token。**

因此这里是否真的充分发挥了 Mamba 的“长序列建模优势”，是值得质疑的。

它的性能提升完全可能主要来自：

$$

\text{learnable temporal sampling}
+
\text{nonlinear predictor},

$$

而不一定来自 Mamba 长距离记忆能力。

---

#### 3. MotionGate：我认为这是论文最值得研究的部分

MotionGate 输入：

$$

x^{kal},\sigma^{kal},x^{mam}.

$$

经过 MLP 后，同时预测：

$$

\alpha_t

$$

和

$$

\sigma_t^{mam}.

$$

最终：

$$

x^{fuse}
=
\alpha x^{kal}
+(1-\alpha)x^{mam}.

$$

这意味着它实际上是一个**Mixture-of-Experts式运动模型选择器**：

$$

\text{Kalman expert}
\leftrightarrow
\text{Mamba expert}.

$$

例如目标稳定直行：

$$

\alpha\approx1

$$

则主要相信 Kalman。

目标突然变向：

$$

\alpha\approx0

$$

则更依赖 Mamba。

更有意思的是，它逐维选择：

$$

\alpha=
[\alpha_x,\alpha_y,\alpha_a,\alpha_h,
\alpha_{v_x},...].

$$

所以它不是简单判断“哪个模型更好”，而是在判断：

**哪个模型在当前哪个状态变量上更可信。**

---

#### 4. 不确定性感知关联

传统 ByteTrack 类方法主要依靠：

$$

IoU(\hat B_i,D_j).

$$

DMTrack加入：

$$

TrendSim=\cos(v_{track},v_{det})

$$

以及 uncertainty penalty。

最终：

$$

S_{ij}
=
0.7IoU
+
0.2TrendSim
+
0.1Penalty.

$$

其思想是：

两个候选框 IoU 相近时，运动方向更加一致、预测更加合理的候选应该获得更高匹配分数。

这一步使不确定性不再只是运动预测器的附属输出，而是真正进入了**Association Decision**。

---

#### 5. 两种训练损失

运动状态采用：

$$

L_{state}
=
\|\hat x-x^{gt}\|_1.

$$

同时预测不确定性：

$$

L_{conf}
=
\sum_i
\left[
\frac{(x_i-x_i^{gt})^2}{2\sigma_i^2}
+\log\sigma_i
\right].

$$

这是典型的异方差 Gaussian NLL。

含义非常直观：

预测准确的时候：

$$

\sigma\downarrow

$$

预测困难的时候：

$$

\sigma\uparrow.

$$

于是模型理论上不只是学习：

> “我预测什么？”

还学习：

> “我对这个预测有多确定？”

这是论文最具有延展价值的思想之一。

---

### 三、实验：论文的数据到底说明了什么？

论文使用两个 UAV-MOT 数据集。

| 数据集 | 特点 | 评价类别 |
|---|---|---|
| VisDrone-MOT | 城市/郊区、目标密集、小目标、视角变化明显 | car、bus、truck、pedestrian、van |
| UAVDT | 50个无人机视频，以车辆为主 | car、truck、bus |

检测器统一描述为 **YOLOX-S**，输入分辨率为 $1280\times736$，训练 60 epochs。

运动模块则分别在两个数据集训练：

$$

Model_{VisDrone}
\neq
Model_{UAVDT}.

$$

这点后面会成为一个重要的泛化问题。

评价指标只有：

**MOTA**：综合 FP、FN、IDSW 的经典 MOT 指标。

**IDF1**：身份一致性指标，对轨迹 ID 保持更敏感。

#### SOTA比较

论文 Table 1 的主要结果是：

| 方法 | VisDrone MOTA | VisDrone IDF1 | UAVDT MOTA | UAVDT IDF1 |
|---|---:|---:|---:|---:|
| ByteTrack | 35.7 | 48.3 | 41.6 | 59.1 |
| OC-SORT | 39.6 | 50.4 | 47.5 | 64.9 |
| TrackSSM | 41.9 | 55.3 | 48.1 | 65.4 |
| MambaTrack | 43.7 | 57.3 | 48.3 | 67.3 |
| MM-Tracker | 44.7 | 58.3 | 51.4 | 68.9 |
| **DMTrack** | **47.8** | **61.7** | **54.8** | **72.2** |

因此按照论文列出的比较方法，DMTrack 的优势相当明显。

尤其值得注意的是 IDF1。

VisDrone：

$$

58.3\rightarrow61.7

$$

UAVDT：

$$

68.9\rightarrow72.2.

$$

说明作者希望证明的核心不只是框的位置预测更准确，而是：

**更好的运动预测最终能够改善身份一致性。**

---

#### DeformMamba真的有效吗？

Table 2：

| Motion Model | VisDrone MOTA | IDF1 |
|---|---:|---:|
| KF | 35.7 | 48.3 |
| LSTM | 37.5 | 49.8 |
| Mamba | 39.8 | 51.6 |
| **DeformMamba** | **41.8** | **54.8** |

这里实际上支持两层结论：

$$

KF < LSTM < Mamba

$$

说明数据驱动的非线性建模有效；

同时：

$$

Mamba < DeformMamba

$$

说明**动态历史采样**可能确实提供额外收益。

---

#### MotionGate是不是必要？

Table 3 非常关键：

| 方法 | VisDrone MOTA | IDF1 |
|---|---:|---:|
| Mamba only | 39.8 | 51.6 |
| Average Fusion | 42.1 | 54.6 |
| **MotionGate** | **44.6** | **58.2** |

这实际上告诉我们：

即使一个学习型 Motion Model 比 Kalman 强，

$$

Mamba > KF,

$$

也不代表应该删除 Kalman。

反而：

$$

Kalman+Mamba
>
Mamba.

$$

而且：

$$

Adaptive\ Fusion
>
Fixed\ Fusion.

$$

这是这篇论文非常值得吸收的一条实验结论。

---

#### 不确定性单独使用反而变差

Table 4 有一个很有意思、但论文没有充分讨论的结果：

$$

IoU-only:
35.7/48.3

$$

而：

$$

\sigma-only:
32.3/46.8.

$$

也就是说：

**不确定性本身并不是一个好的关联线索。**

真正有效的是：

$$

Geometry
+
Motion\ Trend
+
Uncertainty.

$$

最终达到：

$$

40.8/52.8.

$$

因此论文实际上间接说明：

> uncertainty 最适合作为“辅助判断条件”，而不是独立关联依据。

---

### 四、学术价值、当前领域位置与产业意义

从当前 MOT 发展来看，DMTrack并不是突然出现的一条孤立路线。近年来已经出现一批利用 SSM/Mamba 做运动预测的工作。

MambaMOT、MambaTrack都探索了利用 Mamba 替代或增强传统 Kalman Motion Predictor；TrackSSM进一步构造了基于 SSM 的通用轨迹运动预测器。

而 UAV 场景中的 MM-Tracker 更进一步指出，无人机 MOT 的运动实际上同时包含**目标局部运动和摄像机全局运动**，并利用 Motion Mamba 对两者进行建模。

因此可以把当前发展脉络概括成：

$$

\text{Kalman}

$$

↓  

$$

\text{Learning-based Motion Predictor}

$$

↓  

$$

\text{SSM/Mamba Motion Predictor}

$$

↓  

$$

\boxed{\text{Physics + Learned Model + Uncertainty}}

$$

DMTrack比较有价值的地方正在最后一步。

它不是简单宣称：

$$

Mamba>Kalman,

$$

而是提出：

$$

\boxed{\text{什么时候应该相信哪个模型？}}

$$

这可能比继续堆叠一个更大的 Motion Network 更有研究生命力。

在产业层面，我认为真正值得关注的并不是“DMTrack这个具体网络”，而是几类技术能力：**边缘端运动预测、低算力 Re-ID-free MOT、运动可信度估计、复杂摄像机运动下的轨迹预测，以及不确定性感知的自动驾驶/无人机视觉决策**。这些模块可以进入无人机巡检、交通管理、应急搜索、机场/园区监控以及自主飞行视觉系统。

从技术投资角度，更值得长期关注的是**边缘AI芯片 + 轻量视觉模型 + 无人机感知栈 + 多模态传感器融合 + 仿真/训练数据平台**这类底层能力，而不是单独押注某一个 Mamba tracker。

---

### 五、批判性分析：这篇论文有哪些真正需要质疑的地方？

我认为这部分比看那几个 SOTA 数字更重要。

**第一，最关键的问题是它并没有真正显式建模 Camera Motion。**

论文反复把“abrupt UAV movement”作为研究动机，但输入状态仍然只是：

$$

[x,y,a,h,v_x,v_y,v_a,v_h].

$$

没有 homography、optical flow、IMU、ego-motion 或 GMC。

因此：

$$

\text{观测运动}
=
\text{camera motion}
+
\text{object motion}

$$

实际上仍然被混在一起交给 DeformMamba 学习。

所以严格来说，论文解决的是：

**复杂图像坐标轨迹预测**

而不是：

**显式分离并建模 UAV camera motion 与 object motion。**

这是非常重要的区别。

---

**第二，所谓“long-range Mamba”存在一定宣传大于实际的问题。**

作者使用：

$$

T=8,\quad K=4.

$$

最终 Mamba只处理4个 temporal tokens。

这种长度下，Mamba的线性复杂度优势几乎没有实际意义。

所以更合理的实验应该加入：

$$

MLP / GRU / Transformer / Mamba

$$

在**相同 deformable temporal sampling**条件下比较。

否则目前无法回答：

> 提升到底来自 Mamba，还是来自 adaptive offset？

---

**第三，Uncertainty Penalty的数学形式值得严重检查。**

论文定义：

$$

Penalty=
\exp
\left(
-\frac{\|\hat x-x_{det}\|^2}
{\bar\sigma_{pos}^2}
\right).

$$

但是对于固定预测误差 $d$：

$$

\sigma\uparrow
\Rightarrow
-\frac{d^2}{\sigma^2}\rightarrow0

$$

于是：

$$

Penalty\rightarrow1.

$$

而这个值又是**正向加入 matching score**的。

因此数学上可能出现：

> uncertainty 越大，反而越不容易受到距离误差惩罚。

这和论文所说的：

> “suppress unreliable predictions”

并不完全一致。

如果作者真正想“惩罚高 uncertainty”，通常还需要概率归一化项、Mahalanobis距离/NLL，或者直接引入随 $\sigma$ 增大的负项。

这是我认为全文最值得检查实现代码的地方之一。

---

**第四，TrendSim公式存在定义疑问。**

论文写：

$$

v_{track}
=
\hat x_t-\hat x_{t-1}

$$

但：

$$

v_{det}
=
\hat x_t-x_{det}.

$$

后者看起来更像：

**prediction residual**

而不是“detection motion trend”。

正常理解下，更自然的候选应该类似：

$$

x^{det}_t-x^{obs}_{t-1}.

$$

因此这里有可能只是论文公式书写问题，也可能实现与公式不同。在拿这部分思想做自己的研究之前，最好直接检查官方代码。

---

**第五，不确定性是否真的“校准”没有证据。**

论文有 NLL loss，但没有给：

- calibration curve；
- NLL/ECE；
- uncertainty 与真实 prediction error 的相关性；
- 高 σ 与 IDSW 的关系；
- σ 分位区间下 association failure rate。

所以目前只能说模型“输出 uncertainty”。

不能严格说：

$$

\sigma
\approx
\text{真实预测风险}.

$$

这是两回事。

---

**第六，跨域泛化证据不足。**

论文明确表示：

VisDrone 单独训练一个 tracking model；

UAVDT 再单独训练一个。

因此没有证明：

$$

Train_{VisDrone}
\rightarrow
Test_{UAVDT}.

$$

这实际上暴露了数据驱动 motion model 一个经典问题：

> 学到的是“运动规律”，还是数据集的轨迹统计特征？

TrackSSM等工作的“general motion predictor”路线恰恰使这个问题更值得比较。

---

**第七，实验指标不够完整。**

只报告：

$$

MOTA,\ IDF1.

$$

对于今天的 MOT 研究，我认为至少还应该给：

$$

HOTA,\ DetA,\ AssA,\ IDSW,\ FP,\ FN.

$$

尤其这篇论文声称主要改善身份保持，却没有直接报告 IDSW 和 AssA。

因此“61.7 IDF1提高说明关联更好”虽然合理，却仍然不够彻底。

---

**第八，缺少最关键的解释性实验。**

我最希望看到但论文没有提供的是：

$$

\alpha_{Kalman}

$$

到底在什么情况下变大？

例如：

稳定直线运动：

$$

\alpha\approx0.8?

$$

急转弯：

$$

\alpha\approx0.2?

$$

遮挡后：

$$

\sigma\rightarrow high?

$$

如果作者把 Gate、offset 与真实 prediction error 对齐分析，论文说服力会明显提高。

---

**第九，长遮挡能力没有充分证实。**

没有 Re-ID 后，长期消失再出现本身就非常困难。

论文声称对 occlusion/reappearance 更稳健，但没有按：

$$

1\!-\!2,\quad3\!-\!5,\quad6\!-\!10,\quad>10

$$

帧遮挡长度做分组实验。

所以“长遮挡恢复能力”目前证据并不充分。

---

**第十，运行速度报告存在内部不一致。**

Table 1 把 **28.4** 标成 FPS，而 Table 5 及正文又把接近相同的数值描述成 **ms per frame**。

FPS 和 ms/frame 并不是同一个单位。

因此这部分效率结论至少存在排版或报告错误，需要查看代码或补充材料确认。

---

### 六、从学习和研究角度，最应该吸收什么？

如果只让我从 DMTrack 中挑三个真正值得带走的思想，我不会首先选“Mamba”。

第一个是：

$$

\boxed{\text{不要问哪个 Motion Model 最强，要问当前哪个 Motion Model 值得信任}}

$$

这是 MotionGate 的真正价值。

第二个是：

$$

\boxed{\text{Prediction Error应该进一步影响Association}}

$$

很多工作把 Motion Prediction 和 Data Association 当成两个模块：

$$

Motion Predictor
\rightarrow
BBox
\rightarrow
IoU.

$$

DMTrack开始变成：

$$

Motion Predictor
\rightarrow
(BBox,\ Uncertainty)
\rightarrow
Association.

$$

也就是说：

**模型不仅提供答案，还向后续模块提供“答案可信程度”。**

第三个是：

$$

\boxed{\text{历史轨迹不是每一帧都同等重要}}

$$

DeformMamba的 temporal offset 思想完全可以脱离 Mamba 单独使用。

例如你甚至可以做：

$$

Adaptive\ Historical\ Sampling
+
Kalman

$$

或者：

$$

Adaptive\ Historical\ Sampling
+
MLP/GRU/SSM.

$$

---

对你现在的 UAV-MOT 研究而言，我认为 DMTrack **最值得借鉴的不是“再设计一个 DeformMamba”**，而是它已经非常接近你目前正在追的核心问题：

$$

\boxed{\text{当前 Motion Prediction 到底值不值得相信？}}

$$

DMTrack给出的解决方式是“学习 $\sigma$ 和 $\alpha$”；而你完全可以进一步追问一个更基础也更可解释的问题：

$$

\text{真实 Motion Prediction Error}
\rightarrow
\text{Reliability}
\rightarrow
\text{Association Failure / IDSW}.

$$

实际上，DMTrack恰恰暴露了这个方向尚未解决的空缺——它有 uncertainty，却没有证明这个 uncertainty 与真实运动预测误差高度对应；有 MotionGate，却没有证明 Gate 权重真的随着运动模型可靠性变化；有 UAM，却没有做 prediction-error → association-failure 的系统统计闭环。

这比单纯再加一个 Motion Network 更值得深入。

如果你想真正吃透这篇论文，下一步最应该补的背景知识是 **Kalman Filter及协方差意义、Gaussian NLL与异方差不确定性、Mamba/Selective SSM、Hungarian/Data Association、Mahalanobis Distance，以及 HOTA/AssA/IDF1/IDSW 之间的区别**。等这些东西理解后，再回头看 DMTrack，你会发现它真正有价值的部分其实是“**可靠性如何进入关联决策**”，而不是“Mamba”三个字本身。memcite

我也已经给你展示了 Zotero 连接选项；如果你后面要连续精读 **DMTrack、MM-Tracker、TrackSSM、MambaTrack** 这几篇，可以直接把论文和笔记组织成一组文献，之后做“运动模型演化路线”的横向对比会方便很多。

## 讨论记录
### 2026-11-03 · 6aaa02e5-b170-83ee-802d-a64a3a654ac5
这篇论文的核心并不是简单地“用 Mamba 替换卡尔曼滤波器”，而是试图回答一个更实际的问题：在无人机多目标跟踪中，线性运动模型和学习型非线性运动模型各有优缺点，能不能让系统根据当前轨迹状态自己判断该相信谁，并把这种可信度进一步传递到数据关联阶段？

## 缺失资源
- 多模态资源（image_asset_pointer，id=sediment://20d00a3479ebd）
- 多模态资源（image_asset_pointer，id=sediment://5c3baa9e5f4cf）
- 多模态资源（image_asset_pointer，id=sediment://9121fbbedf0d7）
- 多模态资源（image_asset_pointer，id=sediment://d3af57fd45344）
- 多模态资源（image_asset_pointer，id=sediment://d61d8574437b4）


## 我的研究笔记

（待写：人工笔记写在 human 区内，同步不会覆盖。）
