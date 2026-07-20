---
name: financial-data
description: "AI Berkshire skill: 财务数据获取与交叉验证规范. Source: skills/financial-data.md."
agent_created: true
---

## WorkBuddy adapter note

This skill is generated from `skills/financial-data.md` so Claude Code, Codex and WorkBuddy users share one canonical workflow.

- Treat `$ARGUMENTS` (or the arguments passed when this skill is loaded) as the user's research target, e.g. a company name or ticker.
- When the source mentions Claude-only surfaces such as Task, Agent, WebSearch, Bash, Read or Write, map them to the closest WorkBuddy capability available in this session: multi-agent parallelism uses the WorkBuddy `Agent` tool (background parallel + optional team orchestration); web research uses WebSearch/WebFetch; local tools and file edits use Bash/Read/Write.
- Shared project tools under `tools/` (e.g. financial_rigor.py) depend only on the Python standard library. In this environment run them with `python3 tools/...`; if `python3` is not on PATH (some Windows machines without a Python installer), use `python` or the WorkBuddy-managed Python instead. Always run from the repository root with paths like `python3 tools/financial_rigor.py ...`; if the current thread did not start inside the repo, locate the actual checkout path first instead of assuming a fixed home-directory path.
- Before starting research, run the `date` command to confirm today's date; treat it as the baseline for "latest" data and state the data cutoff date in the report header. Never assume the current date from training data.
- Preserve the research quality rules from `AGENTS.md`: cross-check financial data from two independent sources, use exact arithmetic tools for valuation/math, and clearly label uncertainty and source gaps.

# 财务数据获取与交叉验证规范

本规范适用于所有涉及企业财务数据的研究。**每个关键数据必须来自两个独立来源，误差>1%须标记。**

---

## 数据源优先级（按查询类型分桶 + WorkBuddy 连接器）

本项目在 WorkBuddy 下运行时，可调用**已连接的股票数据连接器**：腾讯自选股（westock）、通达信（tdx）。
经验结论：**连接器强在实时 / 结构化 / 轻量查询，弱在深度、多期、非结构化查询**。因此按**查询类型分桶**排优先级，桶内顺序尝试，失败 fallback 到下一源；**深度桶连接器不参与**。

### 桶 1 · 实时行情 / 报价（price、quote、市值快照）
| 优先级 | 来源 | 获取方式 |
|--------|------|---------|
| 1 | 腾讯自选股连接器（westock，已连接） | 调用连接器行情工具 |
| 1 | 通达信连接器（tdx，已连接） | 调用连接器行情工具 |
| 2 | gtimg（tools/ashare_data.py） | `python3 tools/ashare_data.py quote {代码}` |
| 兜底 | WebSearch 抓 aastocks / eastmoney 行情页 | — |

### 桶 2 · A股基础财务快照（最新一期营收 / 利润 / 资产负债）
| 优先级 | 来源 | 获取方式 |
|--------|------|---------|
| 1 | 通达信连接器（tdx，已连接） | 调用连接器财务工具 |
| 2 | 东方财富（tools/ashare_data.py） | `python3 tools/ashare_data.py ...` |
| 3 | 巨潮资讯 cninfo.com.cn | WebSearch 抓年报 / 季报 |

### 桶 3 · 深度财报 / 原始财报（多期、电话会、附注）— 连接器不参与
直接走 web / 工具：
| 优先级 | 来源 | 获取方式 |
|--------|------|---------|
| 1 | 东方财富 + 巨潮资讯（A股） | tools/ashare_data.py + WebSearch |
| 1 | SEC EDGAR（美股 10-K / 10-Q） | WebSearch |
| 1 | HKEX 披露易（港股年报 PDF） | WebSearch |
| 2 | macrotrends / aastocks（副源交叉验证） | WebSearch |

### 桶 4 · 历史价格序列 / 动量回测 — 连接器不参与
| 优先级 | 来源 | 获取方式 |
|--------|------|---------|
| 1 | Yahoo Finance（tools/momentum_backtest.py、stock_screener.py） | `python3 tools/momentum_backtest.py ...` |

### 桶 5 · 公允价值 / 估值
| 优先级 | 来源 | 获取方式 |
|--------|------|---------|
| 1 | morningstar（tools/morningstar_fair_value.py） | `python3 tools/morningstar_fair_value.py ...` |

### 桶 6 · 大V / 舆情
| 优先级 | 来源 | 获取方式 |
|--------|------|---------|
| 1 | 雪球（tools/xueqiu_scraper.py，需登录） | `python3 tools/xueqiu_scraper.py ...` |

---

## WorkBuddy 连接器 Fallback 规则（强制）

1. **桶内顺序 + 失败才跳**：每个桶按优先级尝试，前一源"失败"才 fallback 到下一源，不要并行盲目全试。
2. **"失败"的定义**：超时、返回空、关键字段缺失、数据滞后（如连接器财报期比最新一期旧）、接口报错。
3. **快速判定，不傻等**：若连接器明确不支持该查询类型（如多期财报、长周期历史序列），**直接跳到对应桶**，不要等超时。
4. **来源必须标注**：无论最终用哪个源，输出必须标注实际来源（格式见下）。允许且鼓励"一个源是连接器、一个源是 web"的混合交叉验证。
5. **校验不掉**：连接器结果同样须过 `financial_rigor.py` / `report_audit.py`；交叉验证两源可一连接器一 web。
6. **性能**：四大师并行时若都先打连接器，可能触发限流——遵循"快速判定跳过"，连接器不支持立刻转 web，避免阻塞。
7. **连接器健康检查（执行前必做，防静默退化）**：
   - 研究开始的第一步，先探测**腾讯自选股（westock）/ 通达信（tdx）连接器是否可用**（即当前会话是否存在对应 MCP 工具）。
   - **若两个连接器都不可用**：在报告顶部**醒目标注**以下提示，再继续（不要假装连接器在工作）：
     > ⚠️ **未检测到股票数据连接器（腾讯自选股 / 通达信）**。请到 WorkBuddy 设置中连接这两个连接器以获得最优实时行情与结构化财务数据；当前已自动回退到网页抓取（eastmoney / Yahoo / macrotrends 等）+ 本地工具，数据质量不受影响但覆盖度与时效略低。
   - **若仅一个可用**：标注"已启用 X 连接器，Y 未连接，已按桶优先级回退"。
   - **若都可用**：正常走桶优先级。
   - 关键：**绝不允许**因为连接器未连接就静默降级到训练知识或编造数据——未连接只是少一个优选源，web/工具链路始终可用。

---

## 执行规范

### 第一步：获取数据

对每个财务指标（收入、净利润、毛利率、经营现金流、资产负债率等），分别从**来源1**和**来源2**取数。

### 第二步：误差计算与标记

```
误差率 = |来源1数值 - 来源2数值| / 来源1数值 × 100%
```

| 误差 | 处理方式 |
|------|---------|
| ≤ 1% | ✅ 一致，取来源1数值，标注两个来源 |
| 1% ~ 5% | ⚠️ 标记"数据存在差异"，注明两个数值，说明可能原因（汇率/会计口径） |
| > 5% | ❌ 标记"数据存在重大差异"，必须查原始财报核实，不得直接使用 |

### 第三步：数据呈现格式

每个关键数据必须按以下格式标注：

```
收入：1,239亿元 ✅
  - macrotrends: 1,241亿元
  - stockanalysis: 1,237亿元
  - 误差: 0.3%
```

差异示例：
```
净利润：245亿元 ⚠️ 数据存在差异
  - macrotrends: 245亿元（GAAP）
  - stockanalysis: 278亿元（Non-GAAP）
  - 误差: 13.5% — 原因：会计口径不同（GAAP vs Non-GAAP）
```

---

## 常见差异原因（不一定是数据错误）

| 原因 | 说明 |
|------|------|
| GAAP vs Non-GAAP | 最常见，尤其是利润类数据 |
| 汇率换算 | 港币/人民币/美元换算时间点不同 |
| 财年定义 | 自然年 vs 财年（如苹果财年10月结束） |
| 合并口径 | 是否含少数股东权益 |
| 数据更新滞后 | 某平台尚未更新最新一期财报 |

---

## 特别规则

1. **未上市公司**（米哈游、莉莉丝等）：只有一手数据来源时，数据前标记 `[估计]`，不执行交叉验证
2. **季度数据 vs 年度数据**：优先使用年度数据做交叉验证，季度数据部分来源可能有滞后
3. **原始财报优先**：若两个来源均与原始财报（10-K/年报PDF）不符，以原始财报为准，标记来源错误

---

## 股价与复权（历史序列必读）

价格有三种口径，混用会让历史股价位置、长期涨幅、历史估值分位全部失真：

| 口径 | 含义 | 用途 |
|------|------|------|
| 不复权 | 实际成交价，除权除息日跳空 | 仅用于"当前时点"快照 |
| 前复权 | 以最新价为基准回调历史价 | 历史股价对比、N年涨幅、历史PE band 一律用它 |
| 后复权 | 以上市首日为基准前推 | 计算历史总回报/年化收益 |

规则：

1. 涉及历史价格的分析统一用**前复权**，且同一分析内**不得混用**复权与不复权来源。
2. 当前市值/当前PE 用**当前实际股价 × 当前总股本**即可，与复权无关——复权只影响历史序列。
3. 跨越拆股/大比例送转的每股指标（历史EPS、历史股价），必须复权还原后再同比。
4. 总回报/年化收益需计入分红（后复权已含），只看价格涨幅会低估。
5. 增发/回购后市值验算以最新总股本为准（`financial_rigor.py verify-market-cap` 偏差>5% 会提示核对）。

---

## 快速索引

| 场景 | 主要来源 | 备用来源 | WorkBuddy 优先源 |
|------|---------|---------|----------------|
| PDD / 拼多多 | macrotrends.net/stocks/charts/PDD | stockanalysis.com/stocks/pdd | 实时报价→腾讯自选股/通达信；深度财报→SEC EDGAR |
| 腾讯 | macrotrends.net/stocks/charts/TCEHY | aastocks（0700.HK） | 实时报价→腾讯自选股/通达信；深度财报→HKEX 披露易 |
| 网易 | macrotrends.net/stocks/charts/NTES | aastocks（9999.HK） | 实时报价→腾讯自选股/通达信 |
| 三七互娱 | eastmoney.com（002555） | cninfo.com.cn | 行情/基础财务→通达信；深度财报→eastmoney+cninfo |
| 吉比特 | eastmoney.com（603444） | cninfo.com.cn | 行情/基础财务→通达信；深度财报→eastmoney+cninfo |
| Nintendo | macrotrends.net/stocks/charts/NTDOY | stockanalysis.com/stocks/ntdoy | 实时报价→腾讯自选股/通达信 |
| Capcom | macrotrends（CCOEY） | stockanalysis（CCOEY） | 实时报价→腾讯自选股/通达信 |
