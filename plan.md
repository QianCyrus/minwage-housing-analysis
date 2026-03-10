# 项目计划书

## 一、项目标题

**中文**  
**最低工资上调是否改善住房可负担性？——基于美国州级年度面板数据的双重差分研究**

**英文**  
**Do Minimum Wage Increases Improve Housing Affordability? Evidence from a U.S. State-Level Annual Panel**

---

## 二、项目概述

本项目拟使用美国 **50 个州 + Washington, DC** 的**州级年度面板数据**，研究最低工资上调是否改善住房可负担性。样本期初步设定为 **2010–2024**，但由于 **ACS 2020 1-year 数据存在疫情期可比性问题**，基准样本建议使用 **2010–2019 和 2021–2024**，将 2020 年作为附录或稳健性分析处理。

项目将整合最低工资、租金负担、租金水平、失业率和工资等公开数据，构建州级政策评估数据库，并通过固定效应回归、双重差分和事件研究方法识别最低工资政策变动对住房可负担性的影响。

该项目适合个人独立完成，数据公开、结构清晰、因果识别路径明确，能够较完整展示以下能力：

- 面板数据清洗与合并
- 因果推断与政策评估
- 计量经济学建模
- Python 数据分析与可视化
- 经济学叙事与研究写作

---

## 三、研究背景与问题动机

最低工资政策通常从就业、工资和收入分配的角度讨论，但其影响并不止于劳动力市场。对于低收入家庭而言，住房支出是预算中最核心的刚性支出之一，因此最低工资上调是否能缓解租房负担，具有重要的政策意义。

理论上，这一问题存在双向机制：

1. **收入效应**：最低工资提高后，低收入劳动者的劳动收入增加，支付租金的能力增强，从而可能改善住房可负担性。
2. **成本传导效应**：工资成本上升也可能通过服务业成本、地方价格水平和住房市场供需压力传导，最终推高租金或生活成本。
3. **净效应不确定**：因此最低工资对住房可负担性的总体影响需要通过经验分析加以识别，而不能仅凭直觉判断。

从数据可得性看，FRED、DOL、ACS、LAUS 和 QCEW 都提供公开、长期、结构化的州级数据，适合构造一个可复现的政策评估项目。

---

## 四、研究问题与研究假设

### 4.1 核心研究问题

**最低工资上调是否改善美国州级层面的住房可负担性？**

### 4.2 研究假设

**H1：** 最低工资上调会改善住房可负担性，表现为租金收入比下降。  

**H2：** 最低工资上调也可能推高租金水平，因此其对住房可负担性的净效应不一定单向。  

**H3：** 在低工资州或劳动力市场较弱的州，最低工资上调对住房可负担性的改善可能更明显；而在住房市场更紧张的州，租金传导效应可能更强。

---

## 五、项目范围与样本设计

为确保项目可由个人独立完成，第一版只做一个**小而完整**的州级年度面板项目，不扩展至县级、月频或城市最低工资。

### 5.1 地理范围
- 美国 **50 州 + DC**

### 5.2 时间范围
- 原始下载范围：**2010–2024**
- 基准回归样本：**2010–2019, 2021–2024**
- 2020 年：单独标记，作为稳健性或附录分析

### 5.3 分析频率
- **年度**

### 5.4 研究重点
- 主结果变量：**租房可负担性**
- 附加稳健性：**租金水平**、**房价水平**

### 5.5 暂不纳入
- 县级数据
- 月频面板
- 地方/城市最低工资
- Puerto Rico、Guam 等非州地区

这样处理的好处是：

- 数据清洗难度可控
- 识别逻辑清楚
- 足够完成面板固定效应、DiD、事件研究和稳健性检验
- 更适合课程项目、个人 GitHub 仓库和简历展示

---

## 六、数据来源与下载清单

## 6.1 州最低工资数据（核心处理变量）

**来源：**
- FRED: *Minimum Wage Rate by State*
- U.S. Department of Labor: *State Minimum Wage History / Consolidated Tables*

**主要变量：**
- `state`
- `year`
- `state_min_wage`
- `federal_min_wage`
- `mw_gap = state_min_wage - federal_min_wage`

**建议文件名：**
- `raw/fred_state_min_wage.csv`
- `raw/dol_state_min_wage_history.xlsx`

**用途：**
- 构造政策变化时间
- 定义处理组与事件时间
- 构造连续处理强度变量

---

## 6.2 ACS 住房可负担性与租金数据（主结果变量）

**来源：**
- American Community Survey (ACS), 1-year estimates

**建议使用表：**
- `B25071`: Median Gross Rent as a Percentage of Household Income
- `B25064`: Median Gross Rent (Dollars)

**建议变量：**
- `B25071_001E` → `median_rent_pct_income`
- `B25064_001E` → `median_gross_rent`

**建议文件名：**
- `raw/acs_b25071_state_2010_2024.csv`
- `raw/acs_b25064_state_2010_2024.csv`

**用途：**
- `median_rent_pct_income`：主结果变量
- `median_gross_rent`：辅助结果变量

**备注：**
- 为保证可比性，基准样本建议排除 **2020 ACS 1-year**。

---

## 6.3 LAUS 州失业率数据（控制变量）

**来源：**
- Bureau of Labor Statistics (BLS), Local Area Unemployment Statistics (LAUS)

**建议变量：**
- `state`
- `year`
- `unemployment_rate`

**建议文件名：**
- `raw/laus_state_unemployment_2010_2024.csv`

**用途：**
- 控制州级劳动力市场状况

---

## 6.4 QCEW 州平均周薪数据（控制变量）

**来源：**
- Bureau of Labor Statistics (BLS), Quarterly Census of Employment and Wages (QCEW)

**建议变量：**
- `state`
- `year`
- `avg_weekly_wage`
- `annual_employment`（可选）

**建议文件名：**
- `raw/qcew_state_avg_weekly_wage_2010_2024.csv`

**用途：**
- 控制收入水平
- 用于异质性分析（低工资州 vs 高工资州）

---

## 6.5 Zillow ZHVI（可选稳健性变量）

**来源：**
- Zillow Research Data

**建议口径：**
- `ZHVI All Homes, Smoothed, Seasonally Adjusted`
- Geography: U.S. State
- 先下载月度数据，再聚合成年平均值或年末值

**建议变量：**
- `state`
- `date`
- `zhvi`

**建议文件名：**
- `raw/zillow_zhvi_state_monthly.csv`

**用途：**
- 作为房价稳健性指标
- 丰富住房金融叙事

---

## 七、核心变量设计

最终主表建议命名为：

`processed/state_year_panel.csv`

### 7.1 索引变量
- `state`
- `state_abbr`
- `year`

### 7.2 政策变量
- `state_min_wage`
- `federal_min_wage`
- `mw_gap`
- `treat_ever`
- `first_treat_year`
- `post`
- `event_time`

### 7.3 结果变量
- `median_rent_pct_income`
- `median_gross_rent`
- `zhvi`（可选）

### 7.4 控制变量
- `unemployment_rate`
- `avg_weekly_wage`
- `log_avg_weekly_wage`

### 7.5 可选衍生变量
- `rent_burden_high`：如 `median_rent_pct_income >= 30` 的二元指标
- `log_median_gross_rent`
- `log_zhvi`

---

## 八、数据清洗与面板构造步骤

## 8.1 统一州标识

所有数据统一为同一套州名/州缩写标准：

- `state`
- `state_abbr`

合并前必须先统一格式，避免全称与缩写混用。

---

## 8.2 统一频率

- 最低工资：按年度整理
- ACS：年度
- LAUS：取年度平均失业率
- QCEW：取年度平均周薪
- ZHVI：月度聚合为年度均值或年末值

---

## 8.3 缺失值与样本清理

- 保留 50 州 + DC
- 不纳入 Puerto Rico、Guam 等地区
- 对缺失值先检查覆盖率，不盲目插值
- 对 2020 年单独标记，不直接混入基准样本

---

## 8.4 处理变量的定义（修正版）

为避免“相对 2014 年水平”定义不够稳健，建议采用更清晰的处理方式：

### 方案 A：首个最低工资上调年份（推荐）
对每个州，定义：

- 若某州在 **2015–2024** 期间首次出现  
  `state_min_wage_t > state_min_wage_{t-1}`  
  则该年记为 `first_treat_year`
- 若该州在样本期内从未上调州最低工资，则视为未处理州

进一步定义：

- `treat_ever = 1`：样本期内至少发生过一次州最低工资上调
- `post = 1(year >= first_treat_year)`，否则为 0
- `event_time = year - first_treat_year`

这种定义的优点是：

- 逻辑直接
- 便于构造事件研究
- 适合个人项目第一版

### 方案 B：连续处理强度（稳健性）
使用：

- `mw_gap = state_min_wage - federal_min_wage`
- 或 `log(state_min_wage)`

作为连续处理变量，检验政策强度而非仅仅是否加薪。

---

## 九、计量方法设计

## 9.1 基准模型：州固定效应 + 年份固定效应

基准回归写为：

\[
Y_{st} = \alpha_s + \lambda_t + \beta \cdot Post_{st} + \gamma X_{st} + \varepsilon_{st}
\]

其中：

- \(Y_{st}\)：州 \(s\) 在年份 \(t\) 的住房可负担性指标
- \(\alpha_s\)：州固定效应
- \(\lambda_t\)：年份固定效应
- \(X_{st}\)：控制变量（失业率、平均周薪等）

主结果变量优先使用：

- `median_rent_pct_income`

辅助结果变量包括：

- `median_gross_rent`
- `zhvi`（可选）

---

## 9.2 事件研究模型

为识别动态效应并检验政策前趋势，构造事件时间模型：

\[
Y_{st} = \alpha_s + \lambda_t + \sum_{k \neq -1} \beta_k \cdot 1[event\_time = k] + \gamma X_{st} + \varepsilon_{st}
\]

其中通常将 `event_time = -1` 作为基准期。

事件研究的目的包括：

- 检验政策实施前是否存在明显预趋势
- 观察政策影响是立即出现还是逐步累积
- 更清楚地展示政策冲击路径

---

## 9.3 关于 TWFE 的方法说明（重要）

由于最低工资上调是**分批发生的政策变化**，不同州的处理时间可能不同，因此传统 TWFE 在 staggered adoption 场景下可能存在权重问题。

因此，本项目建议：

- **将 TWFE 作为基础规格和直观展示**
- **将 staggered DiD / cohort-based event study 作为更稳健的主结论依据**

也就是说，项目呈现上可以写成：

1. 先报告传统 TWFE 结果，便于读者理解
2. 再用更稳妥的事件研究 / 分组时点方法验证结论是否一致

这样既保留了展示简洁性，也避免方法上被指出“直接套 TWFE 不够严谨”。

---

## 十、稳健性检验设计

第一版建议至少完成以下三类稳健性检验：

### 10.1 替换因变量
- 主因变量：`median_rent_pct_income`
- 替代因变量：`median_gross_rent`

### 10.2 连续处理强度
- 使用 `mw_gap`
- 或 `log(state_min_wage)`

### 10.3 样本与趋势敏感性
- 排除极端州（如住房成本异常高州）
- 加入州线性时间趋势
- 排除 2020 年后重新估计
- 对早期处理州与晚期处理州分别检验

---

## 十一、异质性分析（可选加分项）

若时间允许，可进一步做两类异质性分析：

### 11.1 按工资水平分组
- 低工资州
- 高工资州

用初始期平均周薪中位数划分。

### 11.2 按住房市场压力分组
- 高租金压力州
- 低租金压力州

用基期 `median_rent_pct_income` 或 `median_gross_rent` 划分。

这样能更好地回答：

- 最低工资在哪类州更可能改善住房可负担性？
- 租金传导在何种住房市场环境下更强？

---

## 十二、Python 实现路线

## 12.1 推荐工具栈

- `pandas`：数据清洗、合并、重塑
- `numpy`：数值处理
- `statsmodels`：OLS 与固定效应虚拟变量写法
- `linearmodels`：PanelOLS
- `matplotlib`：图形输出
- `scikit-learn`：可选，仅用于聚类或分组辅助

---

## 12.2 建议脚本结构

1. `download_data.py`  
   下载或整理 FRED、ACS、LAUS、QCEW、Zillow 原始数据

2. `clean_policy.py`  
   清洗最低工资数据，构造 `first_treat_year`

3. `clean_outcomes.py`  
   清洗 ACS 住房可负担性与租金数据

4. `clean_controls.py`  
   清洗 LAUS 与 QCEW 数据

5. `build_panel.py`  
   合并得到州-年主面板

6. `eda.py`  
   输出描述统计与趋势图

7. `did_baseline.py`  
   运行基准固定效应 / DiD 回归

8. `event_study.py`  
   运行事件研究模型

9. `robustness.py`  
   完成稳健性检验

10. `make_figures.py`  
    导出最终图表和结果表

---

## 十三、项目时间规划

### 第 1 周
- 确定研究问题与样本范围
- 下载数据
- 整理字段字典
- 完成原始数据检查

### 第 2 周
- 清洗最低工资数据
- 清洗 ACS、LAUS、QCEW
- 合并主面板

### 第 3 周
- 完成描述统计
- 绘制趋势图
- 跑基准固定效应 / DiD 模型

### 第 4 周
- 完成事件研究
- 完成稳健性检验
- 补充异质性分析（如有时间）

### 第 5 周
- 完善 GitHub 仓库
- 撰写 README
- 整理图表与报告

若时间较紧，也可压缩为 4 周版本，但优先保证第一版完整跑通。

---

## 十四、GitHub 仓库结构

```text
minimum-wage-housing-affordability/
├── README.md
├── requirements.txt
├── data/
│   ├── raw/
│   ├── interim/
│   └── processed/
├── notebooks/
│   ├── 01_data_checks.ipynb
│   ├── 02_eda.ipynb
│   └── 03_results.ipynb
├── src/
│   ├── utils.py
│   ├── config.py
│   ├── download_data.py
│   ├── clean_policy.py
│   ├── clean_outcomes.py
│   ├── clean_controls.py
│   ├── build_panel.py
│   ├── did_baseline.py
│   ├── event_study.py
│   ├── robustness.py
│   └── make_figures.py
├── outputs/
│   ├── figures/
│   └── tables/
└── report/
    └── project_report.pdf