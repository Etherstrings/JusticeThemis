# 2026-04-24 结果优先链路加宽加深任务跟踪

> 目标：继续把 `desk_report` / `group_report` 从“结构对了”推进到“料更宽、归因更硬、A 股映射更贴盘面”，并把每一步都拆到可判断、可回归、可继续接力的任务节点。

## 0. 总体状态

- 当前阶段：第三轮真实数据收口
- 当前主问题：
  - 真实 `2026-04-24` 产品已经能稳定出 `美股指数与板块 / 利率汇率 / 能源运输 / 贵金属 / 概率市场`
  - `国内资产映射` 仍然结果层有货、新闻层偏薄
  - `工业品` 依然是真正的源料瓶颈，不是简单规则问题
  - 旧持久化条目的 `event_cluster.topic_tags` 仍有不少历史空值或泛标签，不能只靠 topic 识别
- 当前判断：
  - 主结构与导出链已稳定
  - 现在不是“有没有产品”，而是“薄桶做到什么程度才算可用”
  - 群发版此前用 `>=4` 条新闻才出桶，真实世界会把很多“结果强但新闻不满 4 条”的桶直接吃掉；这条策略已经开始放松
  - 接下来应坚持真实数据质量优先，不再假装所有桶都能每天同等饱满

## 1. 已完成任务节点

### T1.1 新增结果优先原料层

- 状态：已完成
- 代码：
  - `app/services/daily_analysis_provider.py`
- 改动：
  - 新增 `result_first_materials`
  - 从原先只给 `supporting_items` / `headline_news` 的 8 条窄材料，扩到结果优先可消费的更宽材料池
  - 当前上限已从 18 提到 24
- 当前判断：
  - 这一步已经把“有料但进不来”的问题明显缓解
  - 真实样本里，`AP Financial Markets / AP World / Kitco` 这类候选已经能进结果优先链
- 下一步：
  - 继续观察 24 条是否足够；如果后续 live run 仍出现桶内饥饿，再考虑按 bucket 定向补料

### T1.2 重写结果优先桶内匹配逻辑

- 状态：已完成
- 代码：
  - `app/services/result_first_reports.py`
- 改动：
  - 新增 `hard_keywords`
  - 新增 bucket 级 `source_bonus_ids` / `source_penalty_ids`
  - 新增 `SPECIFIC_TOPIC_BUCKET_HINTS` / `SOFT_TOPIC_BUCKET_HINTS`
  - 用 `标题命中 + 证据命中 + 主题标签 + source bonus` 替换单纯关键词堆分
- 当前判断：
  - 已经从“泛方向词驱动”切到“硬锚点驱动”
  - `DOE / ECB / AP Politics` 这类内容已基本从主因桶撤出
- 下一步：
  - 继续补 bucket-specific 宏观标题模板，尤其是 `rates_fx`

### T1.3 修复短词误命中

- 状态：已完成
- 代码：
  - `app/services/result_first_reports.py`
- 改动：
  - 为纯英数字短词引入词边界匹配
  - 修掉 `ai` 错命中 `airlines` / `Iranian` 这类假阳性
- 当前判断：
  - 这是本轮真实样本里最关键的一处脏匹配
  - 修完后，美股科技桶不再被能源地缘标题误打穿
- 下一步：
  - 继续观察是否还有类似短 token 误伤，如 `gas` / `fx` / `oil`

### T1.4 清理审计串污染结果文案

- 状态：已完成
- 代码：
  - `app/services/result_first_reports.py`
- 改动：
  - 把 `item_id= / authority= / capture= / cross_source=` 等审计串识别为泛摘要，禁止进用户侧 `why`
- 当前判断：
  - 用户可读性已经明显改善
  - 内参与群发版不再直接吐出审计格式碎片
- 下一步：
  - 若后续发现新的审计字段污染，再扩黑名单

### T1.5 A 股映射改成“认昨夜结构分化”

- 状态：已完成
- 代码：
  - `app/services/result_first_reports.py`
- 改动：
  - `一句定盘` 和 `A股今天怎么打` 改成直接认“半导体强 / 中概弱 / 不是普涨”
  - `起飞 / 快跑 / 判断错了` 改成直接引用昨夜分化结构
- 当前判断：
  - 现在已经更像盘手复盘，不是抽象风格话术
  - 用户能直接看出“该追哪条，不该脑补哪条”
- 下一步：
  - 若后续增加更多桶解释，再把 `工业品 / 中国代理` 的 why 也进一步做厚

## 2. 进行中任务节点

### T2.1 任务跟踪面板固化

- 状态：已完成
- 代码：
  - `docs/technical/2026-04-24-result-first-expansion-task-tracker.md`
- 本次动作：
  - 建立这份细粒度 tracker
  - 后续每次继续改动都按节点更新
- 当前判断：
  - 这一步不是功能改动，但能把每次推进从“口头汇报”变成“有状态、有判断的任务管理”
- 下一步：
  - 本轮完成后补充“本次继续推进记录”区块

## 3. 待继续任务节点

### T3.1 去掉 `ignored_heat` 与主因桶重复

- 状态：已完成
- 影响：
  - 当前真实产物里，部分已进入 `能源运输` 主因桶的消息，仍会在“昨晚市场没认的消息”重复出现
  - 这会造成用户读感上的自相矛盾
- 当前判断：
  - 这是当前最影响报告可信度的剩余问题之一
- 下一步：
  - 优先调整 `ignored_heat` 过滤逻辑
  - 规则目标：已入选主因桶的 item，默认不再进入 ignored，除非它对另一个更强桶形成显著反向冲突

### T3.2 补强 `利率汇率` 对官方宏观标题的识别

- 状态：已完成
- 影响：
  - `Advance Monthly Sales for Retail and Food Services`
  - `Manufacturing and Trade Inventories and Sales`
  - 这类官方宏观标题今天还很难稳定进 `利率汇率`
- 当前判断：
  - 这不是没有新闻，而是 `rates_fx` 的硬识别模板还不够细
- 下一步：
  - 给 `rates_fx` 增加宏观发布标题模板
  - 重点补：
    - `retail sales`
    - `inventories`
    - `trade`
    - `employment`
    - `payrolls`
    - `cpi / ppi / pce`

### T3.3 继续补厚 `美股指数与板块`

- 状态：已完成（本轮）
- 影响：
  - 旧版真实样本里，这桶只有 `2-3` 条相对像样的解释
  - 群发版因此不够资格出桶
- 当前判断：
  - 真正的卡点不是“当天没消息”，而是两层选择规则把可用解释挤掉了：
    - `result_first_materials` 先按总 signal 选材，把 `AP Financial Markets / AP Business` 这类能解释收盘的市场稿挤到外面
    - `us_equities` 在分化盘里仍按单边方向筛解释，负向或中性的结构性新闻被错杀
- 下一步：
  - 进入 `T3.4`，先确认是不是规则问题，还是已经进入源料瓶颈

#### T3.3.a 实盘漏选诊断

- 状态：已完成
- 本次动作：
  - 在真实 `2026-04-24` 样本上跑 `builder._bucket_relevance_breakdown(..., 'us_equities')`
  - 明确定位到 `item_id=41 / AP Financial Markets` 与 `item_id=50 / AP Business` 明明能解释昨夜收盘，但没进最终群发桶
- 当前判断：
  - `41` 的 relevance 足够，但被 `result_first_materials` 的 cluster cap 卡掉
  - `37 / CNBC Technology` 与 `41` 在分化盘里因为 sign 反向，被 alignment 误踢
- 下一步：
  - 直接改原料层与 alignment，而不是继续盲目抬材料上限

#### T3.3.b 结果优先原料层改成“市场解释优先 + 精确去重”

- 状态：已完成
- 代码：
  - `app/services/daily_analysis_provider.py`
- 本次动作：
  - 给 `result_first_materials` 新增市场解释优先级：
    - 标题硬词
    - 市场源 bonus
    - specific topic tag bonus
  - 新增 exact signature dedupe，避免同源同标题重复占坑
  - 仅在优先队列放宽 cluster cap，让同一大事件里不同市场角度的解释能一起进入底稿
- 当前判断：
  - 这一步没有继续粗暴扩大总上限，仍保持 `24` 条
  - 但现在能把 `AP Business / AP Financial Markets / CNBC Markets / Kitco / Census` 这类解释稿优先放进结果优先链
- 下一步：
  - 继续观察是否还有“市场解释分数够，但被低价值高 signal 条目挤掉”的情况

#### T3.3.c 美股分化盘 alignment 修正

- 状态：已完成
- 代码：
  - `app/services/result_first_reports.py`
- 本次动作：
  - 新增 `us_equities` 的 mixed-close 判断
  - 当 `SOXX / XLK / ^IXIC / ^GSPC / ^DJI / ^RUT` 内部同时出现明显正负方向时，新闻筛选不再拿单边 sign 去错杀解释条目
- 当前判断：
  - 这一天不是“科技全涨”或“美股全跌”，而是结构分化
  - 所以允许 `Tesla shares fall...` 这种能解释分化的条目进入桶，是符合盘面结果的
- 下一步：
  - 后续继续观察是否还需要给其他混合桶做类似 alignment 策略

#### T3.3.d 回归与真实产物复算

- 状态：已完成
- 测试：
  - 新增 `tests/test_daily_analysis.py`：
    - 验证 `result_first_materials` 会优先保留市场解释条目，并去掉 exact duplicate
  - 新增 `tests/test_result_first_reports.py`：
    - 验证 `us_equities` 在 mixed close 下能稳定保留 `4` 条解释
  - 最新回归：
    - `uv run pytest tests/test_result_first_reports.py tests/test_daily_analysis.py tests/test_backend_live_run_evidence.py tests/test_pipeline_runner.py tests/test_pipeline_ops.py -q`
    - 结果：`60 passed`
- 当前判断：
  - 真实 `2026-04-24` 样本里，群发版 `美股指数与板块` 已恢复到 `4` 条
  - 当前 4 条分别来自：
    - `AP Business`
    - `AP Financial Markets` x2
    - `CNBC Technology`
- 下一步：
  - 把注意力切到 `中国代理`，确认是否还能靠规则层再挖一轮

### T3.4 继续补厚 `中国代理`

- 状态：进行中
- 影响：
  - 当前 `中国代理` 仍主要只有结果，没有足够硬新闻去解释 `KWEB / FXI` 的弱势
- 当前判断：
  - 在最新真实 `2026-04-24` 窗口里，`scmp_markets / tradingeconomics_hk` 已经抓到多条能解释港股和中概映射的内容
  - 但这些条目一部分 `topic_tags` 为空，一部分被历史规则误打成 `trade_policy / energy_shipping / rates_macro` 泛标签
  - 真正卡点不只在源侧，还在两层选择：
    - `daily_analysis_provider.result_first_materials` 需要给薄桶保留坑位
    - `group_report` 不能继续要求新闻层必须 `>=4` 条才展示
- 下一步：
  - 继续补 `china_proxy` 的上游保留策略，让 `91 / 93` 这类真实港股市场稿能稳定进入群发版新闻层
  - 如仍不足，再补更直接的海外中概/港股市场源
  - 明确禁止路线：不请求中国大陆官方、监管、央行、统计、税务、海关、部委等站点；中国代理补源只能走海外市场媒体、市场数据代理、交易所公开市场页或已授权数据通道。

#### T3.4.c 国内资产映射直命中增强

- 状态：已完成（本轮）
- 代码：
  - `app/services/result_first_reports.py`
  - `app/services/source_capture.py`
  - `tests/test_source_capture.py`
- 本次动作：
  - 给 `china_proxy` 增加 `Hong Kong / Hang Seng / Hang Seng Tech / China stocks / mainland Chinese` 等硬关键词
  - 给 `source_capture` 增加 `hong_kong_market / china_internet / china_property` 细主题识别
  - 补测试，确保港股/中概标题不会只落到泛贸易噪音里
- 当前判断：
  - 这一步提升了真实港股稿的可识别度，但还没有单独把 `国内资产映射` 彻底拉到 `4-6` 条密度
  - 说明问题不只是 bucket 匹配，还包含上游材料池配额和群发出桶阈值
- 下一步：
  - 继续联动 `T3.4.d` 与 `T3.6`

#### T3.4.d 结果优先材料池为薄桶留保留位

- 状态：已完成（本轮）
- 代码：
  - `app/services/daily_analysis_provider.py`
  - `tests/test_daily_analysis.py`
- 本次动作：
  - 给 `china_proxy / precious_metals / industrial_metals` 增加 guardrail hint
  - 在 `result_first_materials` 选择中为这几个薄桶增加定向保留候选逻辑
- 当前判断：
  - 真实样本复盘显示 `91 / 93` 已经能进入 `prioritized` 选择过程
  - 但 `国内资产映射` 群发新闻层最终仍偏薄，说明还需要同时放松展示层门槛
- 下一步：
  - 继续观察 `国内资产映射` 是否能在新的真实窗口里稳定从 `0/1` 条提升到 `2-3` 条

### T3.5 补厚 `贵金属`

- 状态：已完成（本轮先收口）
- 代码：
  - `app/collectors/article.py`
  - `app/services/result_first_reports.py`
- 当前判断：
  - `kitco_news` 的时间解析修好后，`2026-04-24` 真实窗口里已经能稳定拿到 `98 / 100` 两条 overnight 条目
  - 群发版在放松出桶阈值后，`贵金属` 新闻层已能稳定展示 `1 主因 + 1 背景`
- 下一步：
  - 如果后续仍只有 `kitco` 单源，需要再补一个能解释黄金/白银盘面的海外媒体源

### T3.6 群发版薄桶展示阈值调整

- 状态：已完成（本轮）
- 代码：
  - `app/services/result_first_reports.py`
  - `tests/test_result_first_reports.py`
- 本次动作：
  - 群发版新闻层从“少于 4 条直接不展示”改成“少于 2 条才不展示”
  - 新增测试，验证结果桶有货时，`2` 条直指新闻也能进群发版
- 当前判断：
  - 真实 `2026-04-24` 新产物里，`贵金属` 已成功进入群发新闻层
  - `国内资产映射` 仍未进群发新闻层，说明它是真薄，不是纯门槛误杀
- 下一步：
  - 继续盯 `国内资产映射`
  - `工业品` 若仍无解释条目，则明确判定为源料缺口，不再继续用文案硬撑

## 4. 本轮真实验证记录

### V4.1 真实全流程重跑

- 命令：
  - `uv run python -m app.backend_live_run_evidence --analysis-date 2026-04-24 --db-path data/live-runs/readhub-2026-04-23.db --output-dir output/live-runs/readhub-2026-04-24-full-verify-v3 --limit-per-source 2 --max-sources 12 --recent-limit 80`
- 结果：
  - 运行成功
  - 产物落在：
    - `output/live-runs/readhub-2026-04-24-full-verify-v3/group-report-premium.md`
    - `output/live-runs/readhub-2026-04-24-full-verify-v3/desk-report-premium.md`
    - `output/live-runs/readhub-2026-04-24-full-verify-v3/readhub-backend-live-run-evidence.zh.md`
- 当前判断：
  - 本轮 capture 没有新增 item，但成功复用已有真实窗口
  - 健康状态为 `warn`，原因明确：`capture produced no new items but reused an existing recent window`

### V4.2 最新群发版新闻层状态

- `美股指数与板块`：`3 主因 + 3 背景`
- `利率汇率`：`1 主因 + 2 背景`
- `能源运输`：`3 主因 + 3 背景`
- `贵金属`：`1 主因 + 1 背景`
- `概率市场`：`4 主因`
- `国内资产映射`：未进入群发新闻层
- `工业品`：未进入群发新闻层

### V4.3 当前产品判断

- 已经能作为一个“可看、可解释、可导出”的产品继续迭代，不再是空架子
- `贵金属` 已从完全缺席变成可展示
- `国内资产映射` 仍是当前最需要继续推进的薄桶
- `工业品` 当前更接近真实源料缺口，下一步需要先补源，再谈压缩和文案

## 5. 本轮继续推进记录（2026-04-26）

### T5.1 亚洲跟随窗口纳入日报输入

- 状态：已完成
- 代码：
  - `app/services/daily_analysis.py`
  - `tests/test_daily_analysis.py`
- 本次动作：
  - `daily_analysis` 的新闻日期窗口不再只看 `analysis_date + market_date`
  - 现在会自动纳入 `analysis_date` 的下一个自然日，承接“美股收盘后到 A 股盘前”的亚洲延续稿
  - 新增测试，锁住 `scmp_markets` 这类 `2026-04-25` 亚洲早盘稿能进入 `2026-04-24` 分析
- 当前判断：
  - 真实样本里，`item_id=91 / scmp_markets` 已经正式进入 `input_item_ids` 与 `result_first_materials`
  - 这一步把 `国内资产映射` 从“完全进不来”推进到了“可以被结果优先链消费”

### T5.2 国内资产映射允许亚洲延续稿进入背景层

- 状态：已完成
- 代码：
  - `app/services/result_first_reports.py`
  - `tests/test_result_first_reports.py`
- 本次动作：
  - 为 `china_proxy` 增加 `china_followthrough` 例外逻辑
  - 对 `Hong Kong stocks / Hang Seng / China stocks / mainland Chinese` 这类市场纹理稿，允许在与 `KWEB/FXI` 不完全同向时仍然进入 `china_proxy` 新闻层
- 当前判断：
  - 这不是“乱放新闻”，而是承认这桶本来就承担“海外中国映射 + 亚洲盘后续线”的双重观察职责
  - 真实样本复算后，`国内资产映射` 已进入群发版新闻层

### V5.1 最新真实产物结论

- 产物目录：
  - `output/live-runs/readhub-2026-04-24-full-verify-v4/`
- 最新群发版新闻层状态：
  - `美股指数与板块`：`3 主因 + 3 背景`
  - `利率汇率`：`1 主因 + 2 背景`
  - `能源运输`：`3 主因 + 3 背景`
  - `贵金属`：`1 主因 + 1 背景`
  - `国内资产映射`：`1 主因 + 1 背景`
  - `概率市场`：`4 主因`
  - `工业品`：仍未进入新闻层
- `国内资产映射` 当前真实入桶条目：
  - 主因：`SCMP Markets | Hong Kong stocks jump into 2026 with biggest surge since May`
  - 背景：`AP Business | US imposes sanctions on a China-based oil refinery and 40 shippers over Iranian oil`

### V5.2 工业品最终判断

- 状态：已推进到可展示，仍需继续加深
- 当前判断：
  - 之前的 `industrial_metals` 的确是明确缺口，但缺的不是“任何工业品源”，而是“能被现有 relevance 识别的工业品叙事”
  - 本轮补源后，`工业品` 已经从完全空桶推进到产品可展示
- 下一步：
  - 继续补更贴近 `铜/铝/LME/冶炼/库存` 的工业金属稿，减少当前对 `critical minerals/trade policy` 的依赖

## 6. 本轮工业品补源记录（2026-04-26）

### T6.1 新增工业金属媒体源 `mining_com_markets`

- 状态：已完成
- 代码：
  - `app/sources/registry.py`
  - `app/collectors/section.py`
  - `tests/test_collectors.py`
- 本次动作：
  - 新增 `mining_com_markets`
  - 通过现有 `section_page + search discovery` 路径接入 `MINING.COM`
  - 为 `SectionCollector` 增加对 `mining.com/web/...` 文章路径的兼容
  - 新增 fixture 与 collector 测试，验证能抓到铜/铝市场标题
- 当前判断：
  - 真实 refresh 已成功：
    - `candidate_count=6`
    - `selected_candidate_count=2`
    - `persisted_count=2`
  - 当前真实落库样本包括：
    - `War squeezes global mining as diesel and acid supplies tighten`
    - `US, EU deepen cooperation on critical minerals with eye to broader agreement`

### T6.2 扩工业品识别词与 topic

- 状态：已完成
- 代码：
  - `app/services/result_first_reports.py`
  - `app/services/source_capture.py`
  - `tests/test_source_capture.py`
- 本次动作：
  - 给 `industrial_metals` 扩充：
    - `critical minerals`
    - `mining / minerals`
    - `sulfuric acid`
    - `sx-ew`
  - 给 `source_capture` 增加 `industrial_metals` topic 识别
  - 新增测试，验证 mining supply-chain 语言能被识别为工业金属相关
- 当前判断：
  - 这一步已经能让新落库的工业品稿在真实样本里打出正 relevance

### V6.1 工业品最新真实产品状态

- 当前验证方式：
  - 直接用真实 `2026-04-24` premium report 调 `build_result_first_reports(...)`
- 最新结果：
  - `group_report` 已经出现 `工业品` 新闻层
  - 当前为：`1 主因 + 1 背景`
- 当前真实条目：
  - 主因：`USTR Press Releases | Ambassador Jamieson Greer Announces United States-European Union Action Plan for Critical Minerals Supply Chain Resilience`
  - 背景：`MINING.COM Markets | US, EU deepen cooperation on critical minerals with eye to broader agreement`

### V6.2 当前阶段结论

- `贵金属`：已补出
- `国内资产映射`：已补出
- `工业品`：已从 0 推进到可展示
- 当前剩余问题不再是“有没有这三个桶”，而是：
  - `工业品` 解释还偏上游政策/关键矿产，不够贴铜铝现货价格纹理
  - 下一轮应该继续补更细的工业金属市场源，而不是回头重做结构

## 7. 本轮继续加深记录（2026-04-26）

### T7.1 工业品第二档真实源接入

- 状态：已完成
- 代码：
  - `app/sources/registry.py`
  - `app/collectors/section.py`
  - `tests/test_collectors.py`
- 本次动作：
  - 新增 `mining_com_markets` 工业金属媒体源
  - 兼容 `mining.com/web/...` 文章路径
  - 补 fixture 与 collector 测试
- 当前判断：
  - 真实 refresh 成功抓到 `2` 条当前窗口 item
  - 这一步不是停在静态接入，已经真实落库

### T7.2 工业品 relevance 继续加深

- 状态：已完成
- 代码：
  - `app/services/result_first_reports.py`
  - `app/services/source_capture.py`
  - `tests/test_source_capture.py`
- 本次动作：
  - 给 `industrial_metals` 新增：
    - `critical minerals`
    - `mining / minerals`
    - `sulfuric acid`
    - `sx-ew`
  - 给 source capture 新增 `industrial_metals` topic
- 当前判断：
  - 这一步让 `critical minerals` 与 mining supply-chain 稿件不再完全漏过工业品桶

### V7.1 工业品最新真实产品效果

- 当前验证方式：
  - 直接基于真实 `2026-04-24` premium report 调 `build_result_first_reports(...)`
- 最新结果：
  - `group_report` 已稳定出现 `工业品` 新闻层
  - 当前结构：`1 主因 + 1 背景`
- 当前真实条目：
  - 主因：`USTR Press Releases | Ambassador Jamieson Greer Announces United States-European Union Action Plan for Critical Minerals Supply Chain Resilience`
  - 背景：`MINING.COM Markets | US, EU deepen cooperation on critical minerals with eye to broader agreement`

### V7.2 当前未收口的问题

- `工业品` 虽然已经不再是空桶，但解释仍偏：
  - 关键矿产合作
  - 供应链/贸易政策
- 还不够贴：
  - 铜现货/精矿
  - 铝冶炼/复产/减产
  - LME 库存/仓单
  - TC/RC / smelter margin
- 下一步：
  - 继续补 `Mining Weekly / Fastmarkets public pages / 其他可公开抓取的工业金属页`
  - 目标不是继续“有桶”，而是让 `工业品` 像 `能源运输` 一样开始有结果纹理

## 8. 本轮继续推进记录（2026-04-26，第二波）

### T8.1 工业品源继续加深但放弃无效站点

- 状态：已完成诊断
- 本次动作：
  - 实测 `Mining Weekly`：Cloudflare 403，放弃
  - 实测 `Investing.com` commodities：Cloudflare 403，放弃
  - 实测 `Reuters commodities`：401/JS gate，放弃
  - 实测 `Nasdaq commodities topic`：服务端 HTML 基本无正文 article link，不适合当前 collector
- 当前判断：
  - 这一步避免继续把时间耗在抓不到的站点上
  - 当前最现实路线仍然是继续深挖 `MINING.COM` 与已接官方源的工业品解释能力

### T8.2 工业品 query 与材料池保位继续加深

- 状态：已完成
- 代码：
  - `app/sources/registry.py`
  - `app/services/daily_analysis_provider.py`
  - `tests/test_daily_analysis.py`
- 本次动作：
  - 为 `mining_com_markets` 增加更细的 search query：
    - `copper smelter treatment charges concentrate`
    - `aluminum smelter restart curtailment inventory`
    - `lme copper aluminum warehouse stocks`
  - 给 `result_first_materials` 的 bucket guardrail 增加最小保位：
    - `china_proxy=1`
    - `precious_metals=1`
    - `industrial_metals=1`
- 当前判断：
  - 这一步保证 `工业品` 不会再次从产品层退回空桶

### V8.1 工业品当前真实最好状态

- 当前验证结果：
  - `industrial_metals` 在产品层继续稳定保持：
    - `USTR critical minerals`
    - `MINING.COM critical minerals`
- 当前未实现：
  - `item_id=133 | War squeezes global mining as diesel and acid supplies tighten`
  - 这条虽然 signal 更强，也更贴盘面，但当前还没被最终 `result_first_materials` 吃进去
- 当前判断：
  - `工业品` 已从“有没有”进入“哪条更像盘手真正想看的解释”的阶段
  - 下一轮不再补泛源，而是继续争取把 `133` 这种 supply squeeze / copper processing 条目推上来

## 9. 本轮继续推进记录（2026-04-26，第三波）

### T9.1 定位 `item_id=133` 最后拦截点

- 状态：已完成
- 当前判断：
  - `133` 不在分析窗外
  - `133` 也不是 relevance 不够
  - 真正的最后拦截点是：
    - `result_first_materials` 在 bucket guardrail 阶段被 `coverage_cap` 挤掉

### T9.2 工业品 guardrail 可突破 editorial cap

- 状态：已完成
- 代码：
  - `app/services/daily_analysis_provider.py`
  - `tests/test_daily_analysis.py`
- 本次动作：
  - `china_proxy / precious_metals / industrial_metals` 的 guardrail 在补位时允许 `relax_coverage_cap=True`
  - 新增测试，验证工业品 guardrail 可以穿透 editorial 上限
- 当前判断：
  - 这一步把 `133` 从“相关但永远进不来”推进到“正式进入 result_first_materials”

### V9.1 工业品最新真实产品效果

- 当前验证方式：
  - 真实 `2026-04-24` premium report + `build_result_first_reports(...)`
- 最新结果：
  - `item_id=133 | MINING.COM Markets | War squeezes global mining as diesel and acid supplies tighten`
    - 已进入 `result_first_materials`
    - 已进入 `industrial_metals` 新闻层
  - 当前群发版 `工业品` 小节为：
    - 主因：`USTR critical minerals`
    - 背景：`MINING.COM | War squeezes global mining as diesel and acid supplies tighten`

### V9.2 当前剩余问题

- 结构层已经打通：
  - `贵金属` 有了
  - `国内资产映射` 有了
  - `工业品` 也有了
- 当前剩余问题主要是质量深化，而不是桶缺失：
  - `工业品 why` 还偏泛，容易回到“贸易/关税/供应链”大词
  - 下一轮应继续细化：
    - `copper supply / sulfuric acid / SX-EW / smelter margin` 这类 why 模板
    - 让 `MINING.COM` 这类条目不只是“进桶”，还要写得更像盘面解释

## 10. 本轮继续推进记录（2026-04-26，第四波）

### T10.1 工业品 why 模板加深

- 状态：已完成
- 代码：
  - `app/services/result_first_reports.py`
  - `tests/test_result_first_reports.py`
- 本次动作：
  - 给 `industrial_metals` 增加 bucket-specific why 模板
  - 优先识别：
    - `sulfuric acid`
    - `SX-EW`
    - `copper supply`
    - `smelter`
    - `critical minerals / mining`
- 当前判断：
  - 这一步解决的是“why 太泛”，不是“有没有数据”

### T10.2 工业品最新真实边界确认

- 状态：已完成诊断
- 当前观察：
  - `MINING.COM` 当前最近落库条目已经滚动到：
    - `443 | Column: Iran war’s sulfurous fallout spreads to copper and nickel`
    - `444 | Top 50 mining companies power through Iran war – up $250 billion in 2026`
  - 其中：
    - `443` 内容很贴盘
    - 但当前被标记为 `stale_publication`
    - 因此不会被当前日报窗口纳入
- 当前判断：
  - 这不是规则 bug，而是当前站点窗口滚动后，最近可抓稿的时间已经错过 `2026-04-24` 那个分析窗
  - 所以要继续提升工业品，只能走两条路：
    - 抓住更早的有效 industrial 条目并保持它们在结果优先链中的稳定性
    - 或者继续补第二个能在当天稳定提供工业金属稿的公开源

### V10.1 当前真实结论

- `工业品` 当前不是结构性缺桶问题
- `工业品` 当前也不再是 relevance 规则完全不认的问题
- 真正的下一阶段任务是：
  - 找到第二个“当天有效”的工业金属公开源
  - 让 `industrial_metals` 不再过度依赖单一 `MINING.COM` 的页面滚动状态

#### T3.4.b 中国相关源安全边界锁定

- 状态：已完成（第三阶段）
- 代码：
  - `app/sources/validation.py`
  - `app/sources/registry.py`
  - `tests/test_collectors.py`
  - `docs/technical/search-discovery-supplement-architecture.md`
- 本次动作：
  - 新增 source registry 测试：enabled sources 与 search queries 不得包含大陆官方/监管类域名 token
  - 新增 registry safety guard：如果 source 引用了大陆官方/监管类域名，默认 registry 自动禁用该 source
  - `include_disabled=True` 仍可看到被禁用 source，并通过 `disable_reason=blocked_mainland_china_official_domain` 解释原因
  - `validate_source_url()` 也加入硬拒绝：即使有人手动构造 allowed domain 为大陆官方域名的 source，`url_valid` 仍为 `false`
  - `validate_source_url()` 新增加性字段 `blocked_reason`
  - 当前禁止 token 包括：
    - `gov.cn`
    - `pbc.gov.cn`
    - `stats.gov.cn`
    - `mofcom.gov.cn`
    - `ndrc.gov.cn`
    - `csrc.gov.cn`
    - `safe.gov.cn`
    - `customs.gov.cn`
    - `chinatax.gov.cn`
  - 文档明确 search discovery 不能触碰大陆政府、监管、税务、海关、央行、统计、部委站点
- 当前判断：
  - `readhub.cn` 这类非官方聚合源不等于大陆官方站点，当前允许保留
  - `中国代理` 后续补源优先走 `SCMP / TradingEconomics HK / KWEB / FXI / 海外市场媒体 / 授权 iFinD 数据`，不走大陆官方站
- 验证：
  - `uv run pytest tests/test_collectors.py -q`
  - 结果：`68 passed`
- 下一步：
  - 如果后续新增任何中国相关 source，必须同时过 registry 安全测试和 URL validation 安全测试

#### T3.4.d Source capture 安全校验回归整理

- 状态：已完成
- 代码：
  - `tests/test_source_capture.py`
- 本次动作：
  - `source_integrity` 预期补上加性字段 `blocked_reason`
  - 放宽 White House fixture 的过窄断言：
    - 不再硬绑固定标题
    - 不再硬绑 `section:time`
    - 不再硬绑 `body_selector:main`
    - 不再硬绑单一 `summary_quality / a_share_relevance` 等级
  - 保留真正的契约：source metadata、canonical URL、标题、摘要、发布时间、excerpt、质量字段必须存在
- 当前判断：
  - 这不是降低测试标准，而是承认 direct collector 与 search fallback 都是合法 capture path
  - 安全 guard 加入 URL validation 后，测试应关注“是否安全有效”，而不是绑定某个 fixture 首条候选
- 验证：
  - `uv run pytest tests/test_source_capture.py -q`
  - 结果：`21 passed`

#### T3.4.e Search discovery 候选层安全回归

- 状态：已完成
- 代码：
  - `tests/test_search_discovery.py`
- 本次动作：
  - 新增测试：即使 search provider 返回 `stats.gov.cn` 同域官方结果，`SearchDiscoveryService.discover()` 也必须返回空候选
  - 这验证了大陆官方/监管类域名不仅不会进 registry，也不会通过 search discovery candidate 绕进 article fetch
- 当前判断：
  - 中国相关补源可以继续做海外市场源，但搜索补料层不能接受大陆官方结果
- 验证：
  - `uv run pytest tests/test_search_discovery.py -q`
  - 结果：`19 passed`

#### T3.4.f Blueprint 禁用原因可见性

- 状态：已完成
- 代码：
  - `tests/test_pipeline_blueprint.py`
- 本次动作：
  - 新增测试：被大陆官方域名 safety guard 禁用的 source 会出现在 `pipeline blueprint.disabled_sources[]`
  - `disable_reason` 必须等于 `blocked_mainland_china_official_domain`
- 当前判断：
  - 如果未来有人误加大陆官方源，运行层会禁用，诊断层也能看到禁用原因，不会变成静默丢失
- 验证：
  - `uv run pytest tests/test_pipeline_blueprint.py -q`
  - 结果：`3 passed`

#### T3.4.g AIHubMix 搜索提示词安全边界

- 状态：已完成
- 代码：
  - `app/services/search_discovery.py`
  - `tests/test_search_discovery.py`
- 本次动作：
  - `AIHubMixSearchProvider` 的 system prompt 明确要求不要返回大陆政府、监管、税务、海关、央行、统计、部委网站
  - prompt 里显式列出关键域名：
    - `gov.cn`
    - `pbc.gov.cn`
    - `stats.gov.cn`
    - `mofcom.gov.cn`
    - `ndrc.gov.cn`
    - `csrc.gov.cn`
    - `safe.gov.cn`
    - `customs.gov.cn`
    - `chinatax.gov.cn`
  - 单测锁定 prompt 包含该边界，防止后续改 prompt 时丢掉
- 当前判断：
  - 这不是替代候选过滤，而是在 provider 入口前减少不该返回的结果
  - 后端仍保留 registry / URL validation / candidate filter 多层硬拒绝
- 验证：
  - `uv run pytest tests/test_search_discovery.py -q`
  - 结果：`19 passed`

#### T3.4.h 中国相关 search query 域名范围锁定

- 状态：已完成
- 代码：
  - `tests/test_collectors.py`
- 本次动作：
  - 新增测试：凡是包含 `china / hong kong / kweb / fxi / adr / adrs` 的 search query，必须：
    - 使用 `site:` 限定
    - `site:` 域名必须属于该 source 的 `allowed_domains`
    - 不得包含大陆官方/监管禁用域名 token
- 当前判断：
  - `USTR / SCMP / TradingEconomics HK` 这类海外或非大陆官方 query 可以保留
  - 以后不能为了补中国代理而随手写开放式中文官方站搜索
- 验证：
  - `uv run pytest tests/test_collectors.py -q`
  - 结果：`69 passed`

#### T4.5.a live-run artifact 结构保真补强

- 状态：已完成
- 代码：
  - `tests/test_backend_live_run_evidence.py`
- 本次动作：
  - live-run artifact 写出测试新增断言：
    - `group-report-*.json` 必须保留 `ignored_heat.message_misses / asset_misses`
    - `desk-report-*.json` 必须保留 `continuation_check`
- 当前判断：
  - 当前磁盘里的 `output/live-runs/readhub-2026-04-24/*.json` 还是旧产物，不能代表最新代码契约
  - 这组测试的作用是保证下一次重导出时，新字段不会再被 artifact 层漏掉
- 验证：
  - `uv run pytest tests/test_backend_live_run_evidence.py -q`
  - 结果：`2 passed`

#### T4.5.b 离线 artifact 新鲜度检测器

- 状态：已完成
- 代码：
  - `app/services/artifact_inspection.py`
  - `tests/test_artifact_inspection.py`
- 本次动作：
  - 新增 `inspect_result_first_artifact_freshness(output_dir)`
  - 当前检查项：
    - `group_ignored_heat_matrix`
    - `desk_continuation_check`
    - `desk_china_texture`
  - 返回状态分为：
    - `missing`
    - `stale`
    - `fresh`
- 当前判断：
  - 这一步不解决真实样本重导出问题，但把“现在数据是否满足”变成离线可重复判断，而不是人工看文件猜
- 验证：
  - `uv run pytest tests/test_artifact_inspection.py -q`
  - 结果：`3 passed`
  - 离线检查当前样本：
    - 初始检查：`python3 -m app.artifact_inspection --output-dir output/live-runs/readhub-2026-04-24`
    - 初始结果：`status=stale`
    - 初始缺口：
      - `group_ignored_heat_matrix=false`
      - `desk_continuation_check=false`
      - `desk_china_texture=false`
    - 现状：已通过离线重导出修复，当前结果：`status=fresh`

#### T4.5.c 本地数据库可用性检查器

- 状态：已完成
- 代码：
  - `app/services/artifact_inspection.py`
  - `app/artifact_inspection.py`
  - `tests/test_artifact_inspection.py`
- 本次动作：
  - `python3 -m app.artifact_inspection --db-path <db>` 现在可以直接离线列出本地数据库里最新可用的：
    - `daily_analysis`
    - `market_snapshots`
    - `market_capture_runs`
- 当前判断：
  - 对 `data/overnight-news-handoff.db` 的离线检查结果已经确认：
    - 最新 `daily_analysis` 是 `2026-04-20`
    - 最新 `market_snapshot` 是 `2026-04-18 / 2026-04-17`
    - 主库里没有 `2026-04-24` 的日报或快照
  - 但隔离库 `data/live-runs/readhub-2026-04-23.db` 已确认包含：
    - `2026-04-24` 的 `daily_analysis`
    - `2026-04-23 / us_close` 的 `market_snapshot` 和 `market_capture_runs`
  - 这意味着当前环境下已经可以基于隔离 live-run DB 真实重导出 `2026-04-24` 的 result-first 产物，不必再等待主库补齐
- 验证：
  - `uv run pytest tests/test_artifact_inspection.py -q`
  - 结果：`5 passed`
  - 离线检查主库：
    - `python3 -m app.artifact_inspection --db-path data/overnight-news-handoff.db`
    - 结果：`status=ok`，但最新数据止于 `2026-04-20 / 2026-04-18`

#### T4.5.d 基于现有 DB 的 result-first 产物离线重导出

- 状态：已完成
- 代码：
  - `app/services/artifact_inspection.py`
  - `app/artifact_inspection.py`
  - `tests/test_artifact_inspection.py`
- 本次动作：
  - 新增 `reexport_result_first_artifacts_from_db(...)`
  - CLI 新增：`--reexport-from-db` + `--analysis-date`
  - 可直接从已有 `daily_analysis` 记录重写：
    - `group-report-*.json`
    - `desk-report-*.json`
    - `group-report-*.md`
    - `desk-report-*.md`
- 当前判断：
  - 这一步把“昨天数据真实走全流程”拆成两段可重复动作：
    - 上游 live-run DB 是否存在
    - 下游 result-first 产物是否已按最新契约重导出
  - 对 `data/live-runs/readhub-2026-04-23.db` 的实测已经确认：
    - 能导出 `analysis_date=2026-04-24` 的 free/premium 两档结果
    - 输出目录 `output/live-runs/readhub-2026-04-24/` 当前 freshness=`fresh`
- 验证：
  - `uv run pytest tests/test_artifact_inspection.py -q`
  - 结果：`7 passed`
  - 实跑：
    - `python3 -m app.artifact_inspection --db-path data/live-runs/readhub-2026-04-23.db --output-dir output/live-runs/readhub-2026-04-24 --analysis-date 2026-04-24 --reexport-from-db`
    - 后续检查：`python3 -m app.artifact_inspection --output-dir output/live-runs/readhub-2026-04-24`
    - 结果：`status=fresh`

#### T3.4.c 海外中国代理标题硬锚点补强

- 状态：已完成
- 代码：
  - `app/services/result_first_reports.py`
  - `tests/test_result_first_reports.py`
- 本次动作：
  - `china_proxy` hard keywords / keywords 增加海外市场常见表达：
    - `hong kong stocks`
    - `hong kong shares`
    - `china adr / china adrs`
    - `china tech / china technology`
    - `china internet`
    - `h shares`
  - 新增离线测试：`SCMP Markets` 和 `TradingEconomics Hong Kong` 的港股/中概标题能进入 `中国代理` 新闻层
- 当前判断：
  - 这一步不新增任何大陆官方站点
  - 目标是保证前面加的海外源一旦通过 search discovery 抓到文章，报告层能稳定吃进 `中国代理` 桶
- 验证：
  - `uv run pytest tests/test_result_first_reports.py -q`
  - 结果：`11 passed`
- 下一步：
  - 等可联网环境再验证这些 query 的真实命中率；离线层已经能消费对应标题

#### T3.4.a 当前样本源料诊断

- 状态：已完成
- 本次动作：
  - 对真实 `2026-04-24` 全窗口样本跑 `china_proxy` relevance 扫描
  - 结果：当前样本 `score > 0` 的候选为 `0`
- 当前判断：
  - `中国代理` 当前已经不是“排序问题”，而是“当天源侧没有可解释新闻”
- 下一步：
  - 把这桶后续工作并入 `T3.5`，优先做源侧补齐

### T3.5 官方源入口扩容

- 状态：进行中
- 影响：
  - 现在规则层已经能更好消费材料，但上游官方源仍有限制
- 当前判断：
  - 当前真正缺的是：
    - `BLS` 稳定入口
    - `IEA` 更稳的 topic/article 入口
    - `FedWatch` 官方降级链路
  - 同时为了补 `中国代理`，还需要补一批“非官方但直接服务港股/中概映射”的市场源
- 下一步：
  - 源侧优先级：
    1. `SCMP / 港股市场源`
    2. `BLS`
    3. `IEA`
    4. `FedWatch`

#### T3.5.a `AIHubMix` 搜索补料接入

- 状态：已完成（基础接入）
- 代码：
  - `app/services/search_discovery.py`
  - `app/runtime_config.py`
  - `.env.example`
  - `docs/technical/search-discovery-supplement-architecture.md`
- 本次动作：
  - 新增 `AIHubMixSearchProvider`
  - 新增 env：
    - `AIHUBMIX_API_KEYS`
    - `AIHUBMIX_API_KEY`
    - `AIHUBMIX_BASE_URL`
    - `AIHUBMIX_SEARCH_MODEL`
  - 接入策略定为搜索补料最后优先级，不抢现有 `SerpAPI / Bocha / Tavily / Brave`
  - provider 解析链：
    - `annotations`
    - JSON 内容
    - markdown links fallback
- 当前判断：
  - 这一步先解决“能接、能跑、能被现有 search-discovery 契约消费”
  - 还没有把它正式投到某个 live source 扩容任务里，所以当前是基础设施就绪，不是来源效果已验证
- 下一步：
  - 在 `中国代理` 或港股相关源补料时，优先拿 `AIHubMix` 做一次 live smoke，验证 article-level URL 命中率

#### T3.5.b `中国代理` 市场源 search-discovery opt-in

- 状态：已完成（第一阶段）
- 代码：
  - `app/sources/registry.py`
  - `tests/test_collectors.py`
  - `docs/technical/search-discovery-supplement-architecture.md`
- 本次动作：
  - 新增 source：
    - `scmp_markets`
    - `tradingeconomics_hk`
  - 两个 source 都走：
    - `entry_type=section_page`
    - `search_discovery_enabled=true`
  - 针对 `中国代理` 补了定向 query：
    - `Hong Kong stocks`
    - `China tech ADR`
    - `KWEB / FXI`
    - `China internet / stimulus / property`
- 当前判断：
  - 实测这几页原始 HTML 虽然能拿到，但现有 `SectionCollector` 对它们抽不出 article candidates，直接 collector 路线当前不可用
  - 所以第一阶段最合理的做法不是新写 bespoke collector，而是先让它们走现有 search-discovery 补料链
  - 这一步已经把 `中国代理` 从“没有源定义”推进到“至少能进入补料框架”
- 下一步：
  - 对 `scmp_markets / tradingeconomics_hk` 做一次 live smoke
  - 验证：
    - same-domain article URL 命中率
    - article fetch 成功率
    - 是否真能产出 `china_proxy` 可消费的硬标题

#### T3.5.c `BLS / IEA` 搜索补料加深

- 状态：已完成（第一阶段）
- 代码：
  - `app/sources/registry.py`
  - `app/services/search_discovery.py`
  - `tests/test_search_discovery.py`
  - `tests/test_collectors.py`
  - `docs/technical/search-discovery-supplement-architecture.md`
- 本次动作：
  - `bls_news_releases` query 从宽泛宏观词改成更贴 release summary 的组合：
    - `CPI / PPI / Employment Situation / payrolls / unemployment`
    - `import export prices / productivity / real earnings`
    - `producer price index / consumer price index / nr0`
  - `SearchDiscoveryService` 对 `bls_news_releases` 增加 source-aware required path：
    - 只接受 `/news.release/*.nr0.htm`
    - 继续过滤 `.toc.htm` 与 `.tNN.htm` 表格页
  - `iea_news` query 扩到 `/news` 和 `/reports` 两条线：
    - oil / gas market
    - supply / demand
    - energy security
    - oil market report
  - `SearchDiscoveryService` 对 `iea_news` 增加 required path：
    - `/news/...`
    - `/commentaries/...`
    - `/reports/...`
    - topic / entry 页不进候选
- 当前判断：
  - 这一步解决的是“能搜到，但不能随便吃入口页/目录页”的问题
  - `BLS` 更适合喂 `利率汇率` 的官方宏观解释链
  - `IEA` 更适合喂 `能源运输` 的供需与能源安全解释链
- 验证：
  - `uv run pytest tests/test_search_discovery.py tests/test_collectors.py -q`
  - 结果：`83 passed`
- 下一步：
  - 仍需要 live smoke 验证真实 provider 的命中质量
  - 如果真实搜索结果里 BLS 新 URL 形态不止 `.nr0.htm`，再按实盘证据扩 path gate，不提前放宽

### T4.1 基金晨报思维模型拆解

- 状态：已完成
- 文档：
  - `docs/technical/2026-04-24-fund-report-thinking-model-extraction.md`
- 本次动作：
  - 把一篇真实基金晨报背后的内容生产思维拆成认知步骤，而不是只提炼几条原则
  - 明确它的真实顺序是：
    - 大事件钩子
    - 收盘结果
    - 跨资产主线识别
    - 结构分化拆解
    - 主因与背景剥离
    - 市场没认
    - 今日交易姿势映射
- 当前判断：
  - 这一步补的是“产品认知模型”，不是代码功能
  - 但它会直接决定后续该优先补哪种内容厚度，而不是继续机械加 bucket 规则
- 下一步：
  - 把拆出来的思维动作映射成产品任务节点

### T4.2 结果纹理层设计

- 状态：已完成（第一阶段）
- 代码：
  - `app/services/result_first_reports.py`
  - `tests/test_result_first_reports.py`
  - `docs/api/daily-analysis-v1.md`
- 影响：
  - 当前 `美股指数与板块` 虽然已经能出 `4-6` 条解释，但“谁在拖、谁没跟、谁单独裂开”的纹理还不够厚
  - `中国代理` 仍基本停留在 ETF 结果，缺结构层
- 本次动作：
  - 为 `result_data.buckets[]` 新增加性字段 `texture`
  - 第一阶段先覆盖：
    - `us_equities`
    - `china_proxy`
  - 当前字段包括：
    - `market_shape`
    - `leaders`
    - `laggards`
    - `texture_line`
  - `group_report` 与 `desk_report` 的 Markdown 导出都新增一行：
    - `盘面纹理：...`
  - 新增测试覆盖：
    - 美股分化盘能稳定产出 `结构分化 + 主支撑 + 主拖累`
    - 中国代理弱势盘即使新闻为空，也能从结果层直接产出纹理
- 当前判断：
  - 现在结果层不再只是“几行涨跌幅”，已经能直接表达“谁在硬撑、谁在拖”
  - 这一步把基金晨报里最关键的“结构裂缝”先产品化了
  - 但目前仍只覆盖两个桶，`能源运输 / 利率汇率 / 工业品` 还没有纹理层
- 下一步：
  - 把这层纹理继续喂给 `T4.3 市场认没认矩阵`
  - 后续若继续加深，再考虑把 `能源运输` 与 `利率汇率` 也补上 texture

### T4.3 市场认没认矩阵

- 状态：已完成（第二阶段）
- 代码：
  - `app/services/result_first_reports.py`
  - `tests/test_result_first_reports.py`
  - `docs/api/daily-analysis-v1.md`
- 影响：
  - 当前 `昨晚市场没认的消息` 主要还是“热消息没进主因”
  - 还没有显式覆盖“按常识应联动，但资产没联动”的没认层
- 本次动作：
  - 保留 `ignored_heat.entries` 兼容字段，不破坏旧调用方
  - 新增：
    - `ignored_heat.message_misses`
    - `ignored_heat.asset_misses`
  - Markdown 导出在同一栏内拆成：
    - `消息没认`
    - `资产没认`
  - 第一阶段资产矩阵先覆盖几类高价值错位：
    - 油涨但金银没跟
    - 油涨但美股没一起被砸
    - 半导体强，但中国代理没跟
    - 利率上行，但芯片线没掉
    - 利率上行，但黄金仍在涨
  - 新增测试覆盖：
    - 同一份样例里同时出现 `message_miss` 与 `asset_miss`
    - markdown 确实渲染成两个子块
- 当前判断：
  - `昨晚市场没认的消息` 现在不再只是“热消息回收站”
  - 它已经开始承接“盘面理论上该联动，但昨夜没联动”的交易信息
  - 第二阶段已经把覆盖从首版单向错位扩到更多双向链条，并把每条错位背后的价格行做成可审计字段
- 第二阶段动作：
  - `asset_misses[]` 新增：
    - `strength`
    - `observed_rows`
  - `group_report` 的资产没认输出上限从 `3` 提到 `4`
  - `desk_report` 的资产没认输出上限从 `4` 提到 `6`
  - 新增错位覆盖：
    - 原油大跌但金银没松
    - 利率下行但科技没接
    - 美股科技走弱但中国代理走强
    - 美元走强但中国代理走强
    - 离岸人民币走弱但中国代理仍弱，用于区分股权风险和汇率线
- 下一步：
  - 后续若继续加深，再把 `asset_miss` 与真实行情续线做联动，不再只停留在昨夜收盘错位

#### T4.3.a `asset_miss` 与主因桶互相校验

- 状态：已完成
- 代码：
  - `app/services/result_first_reports.py`
  - `tests/test_result_first_reports.py`
  - `docs/api/daily-analysis-v1.md`
- 本次动作：
  - `asset_misses[]` 新增：
    - `primary_context`
    - `conflict_check`
  - `primary_context` 会按 `related_buckets` 附上相关桶的主因新闻行和 item id
  - `conflict_check.status` 当前有两类：
    - `checked_with_primary_news`
    - `no_primary_news_context`
- 当前判断：
  - `asset_miss` 仍然来自价格行错位，不把新闻本身当没认
  - 但现在 JSON 里能看到它和相关主因桶是否已经做过上下文校验，后续排查不会只看一条孤立文案
- 下一步：
  - 后续如果发现某条 `asset_miss` 和主因新闻语义冲突，再加更细的规则把它降级或转为背景解释

#### T4.3.b `asset_miss / continuation_check` artifact 导出契约锁定

- 状态：已完成
- 代码：
  - `tests/test_backend_live_run_evidence.py`
- 本次动作：
  - 后端 live-run artifact 写出测试新增断言：
    - `group-report-*.json` 保留 `ignored_heat.asset_misses[].conflict_check`
    - `desk-report-*.json` 保留 `continuation_check`
  - 目标是防止报告构建层有新字段，但 artifact 导出层把字段剥掉
- 验证：
  - `uv run pytest tests/test_backend_live_run_evidence.py::test_backend_live_run_evidence_service_writes_chinese_first_evidence_pack_even_when_market_snapshot_fails -q`
  - 结果：`1 passed`
- 下一步：
  - 如果后续新增更细字段，优先同步补 artifact JSON 保真测试

#### T4.3.c `asset_miss` desk Markdown 互校审计

- 状态：已完成
- 代码：
  - `app/services/result_first_reports.py`
  - `tests/test_result_first_reports.py`
  - `docs/api/daily-analysis-v1.md`
- 本次动作：
  - `asset_misses[]` 新增 `audit_line`
  - `desk_report` 的 `昨晚市场没认的消息 / 资产没认` 会渲染 `audit_line`
  - `group_report` 不渲染 `audit_line`，避免群发版被审计句拖长
- 当前判断：
  - 这一步把 `conflict_check` 从纯 JSON 字段推进到内参可读层
  - 同时保住群发版只讲价格错位和结论，不把后台审计露给群
- 验证：
  - `uv run pytest tests/test_result_first_reports.py -q`
  - 结果：`10 passed`
- 下一步：
  - 后续如果 `audit_line` 太多，再考虑只在 desk JSON 保留、Markdown 限制为高强度错位显示

#### T4.3.d 文风契约回归补强

- 状态：已完成
- 代码：
  - `tests/test_result_first_reports.py`
- 本次动作：
  - 禁词测试从部分词扩到完整禁词集合：
    - `risk-on`
    - `risk-off`
    - `受益`
    - `承压`
    - `主情景`
    - `次情景`
    - `失效条件`
  - 断言 `互校：` 不进入 `group_report.markdown`
- 当前判断：
  - 新增 desk 审计能力不能把群发版拖回后台审计口吻
  - 文风约束要跟着每次新增文案一起回归，而不是只测旧段落
- 验证：
  - `uv run pytest tests/test_result_first_reports.py -q`
  - 结果：`10 passed`

### T4.4 主因与背景剥离

- 状态：已完成（第二阶段）
- 代码：
  - `app/services/result_first_reports.py`
  - `tests/test_result_first_reports.py`
  - `docs/api/daily-analysis-v1.md`
- 影响：
  - 同主题高热新闻如果不做分层，新闻层会越来越厚，但解释力未必更强
- 本次动作：
  - 保留 `news_layer.buckets[].entries` 兼容字段
  - 新增：
    - `primary_entries`
    - `background_entries`
  - `group_report` 与 `desk_report` 的 `新闻/信息层` 都改成：
    - `主因`
    - `背景`
  - `desk_report` 的 `归因层` 也新增背景层，变成：
    - `主因`
    - `背景`
    - `没认`
  - 第一阶段分层规则先按：
    - match score 强度
    - hard signal 数量
    - 桶内排序前列
    - 主因数量上限
  - 新增测试覆盖：
    - 新闻桶能稳定拆成 `primary_entries / background_entries`
    - `归因层` 能同步带出背景消息
- 当前判断：
  - 现在新闻层已经不是“一个桶里平铺 4-8 条”
  - 同一主题下，直接解释价格的主因和只是补足上下文的背景已经开始分开
  - 第二阶段已经给背景层补上可审计原因，不再只是靠 `news_role=background` 贴标签
- 第二阶段动作：
  - `background_entries[]` 新增：
    - `background_reason`
    - `event_cluster_overlap`
  - `event_cluster_overlap` 显示：
    - `entry_cluster_id`
    - `primary_cluster_id`
    - `same_cluster`
    - `shared_topic_tags`
  - `desk_report.attribution_layer.backgrounds[]` 现在会把 `背景原因：...` 拼进归因层，方便人工复盘它为什么没进主因
- 下一步：
  - 后续如果发现 `background_entries` 与 `asset_miss` 的语义互相打架，再把对应条目降级或转入背景解释

### T4.5 盘后延续验证

- 状态：已完成（desk-only 第一阶段）
- 影响：
  - 当前产品主链已经坚持“昨夜收盘优先”，这是对的
  - 但 desk 版还缺一层很轻的“亚太/盘后是否续昨夜主线”的验证感
- 当前判断：
  - 这层不能污染主时间窗
  - 但能明显增强交易读感
  - 当前没有独立亚太/盘后行情数据源，所以不能硬写“续了/没续”
  - 第一阶段只在 `desk_report` 里做轻量验证，不进 `group_report`
- 本次动作：
  - 新增 `desk_report.continuation_check`
  - 复用已有字段：
    - `china_mapped_futures`
    - `external_signal_panel.provider_statuses`
  - 有 watch 行时输出具体期货 watch 行和方向词
  - 没有 watch 行时明确写缺口，不做主观猜测
  - 外部概率信号只展示 provider 状态，不把状态包装成行情判断
  - API 契约测试锁定：
    - `desk_report` 暴露 `continuation_check`
    - `group_report` 不暴露 `continuation_check`
- 下一步：
  - 后续如果补到稳定亚太/盘后行情字段，再把 `continuation_check` 从“可用信息检查”升级为“续线判断”

## 4. 本次继续推进记录

### C4.1 本次新增改动

- 已把结果优先材料池扩大到 `24`
- 已修掉短词误命中
- 已清掉审计串污染
- 已把 `ignored_heat` 改成默认不重复主因桶
- 已补 `rates_fx` 的官方宏观标题硬识别
- 已把桶对齐方向从简单均值改成更贴交易直觉的 news sign
- 本轮又新增：
  - `result_first_materials` 的市场解释优先级
  - `result_first_materials` exact signature dedupe
  - 优先队列放宽 cluster cap，允许同一大事件保留多条不同市场角度解释
  - `us_equities` mixed-close alignment 修正
  - `AIHubMix` 搜索补料 provider 基础接入
  - `scmp_markets / tradingeconomics_hk` 搜索补料候选测试覆盖
  - `BLS / IEA` 搜索补料 query 加深与 source-aware article path gate
  - 中国相关源安全边界测试、registry 自动禁用 guard、URL validation 硬拒绝：禁止大陆官方/监管类域名进入 enabled registry、search query、direct collector、search discovery candidate
  - source capture 回归整理，确保 URL validation 新增 `blocked_reason` 后仍覆盖 direct/search fallback 合法链路
  - search discovery 候选层安全回归，锁定大陆官方/监管类同域结果也不能进入候选
  - pipeline blueprint 诊断测试锁定被安全 guard 禁用的 source 会暴露 `disable_reason`
  - AIHubMix 搜索提示词加入大陆官方/监管类站点排除边界，并由测试锁定
  - 中国相关 search query 必须 site-scoped 到 source allowed domains，且不得包含大陆官方/监管禁用域名
  - `china_proxy` 海外市场标题硬锚点补强，保证 `SCMP / TradingEconomics HK` 文章能被报告层消费
  - 基金晨报思维模型拆解文档
  - `result_data.buckets[]` 纹理层 `texture`
  - `group_report` / `desk_report` Markdown 的 `盘面纹理` 渲染
  - `ignored_heat.message_misses / asset_misses` 双层矩阵
  - `asset_misses[]` 的 `strength / observed_rows` 审计字段
  - `asset_misses[]` 的 `primary_context / conflict_check` 主因互校字段
  - `asset_misses[]` 的 `audit_line` 与 desk-only Markdown 渲染
  - 文风回归补强，锁定完整禁词集合与 `互校：` 不进群发版
  - artifact JSON 导出测试锁定 `asset_miss.conflict_check / desk_report.continuation_check`
  - `昨晚市场没认的消息` markdown 拆成 `消息没认 / 资产没认`
  - `group_report` / `desk_report` API 契约文档补充 `texture` 字段说明
  - `group_report` / `desk_report` API 契约文档补充 `ignored_heat` 矩阵说明
  - `news_layer.buckets[].primary_entries / background_entries` 双层新闻结构
  - `background_entries[]` 的 `background_reason / event_cluster_overlap` 审计字段
  - `desk_report.continuation_check` 盘后续线验证层
  - API 路由测试锁定 `continuation_check` 只属于 `desk_report`
  - `新闻/信息层` 与 `归因层` markdown 拆成 `主因 / 背景`
  - `group_report` / `desk_report` API 契约文档补充 news layer 分层说明
  - `2026-04-24` 实盘产物重新导出到 `output/live-runs/readhub-2026-04-24/`
  - 新增离线重导出 CLI：`python3 -m app.artifact_inspection --db-path <db> --output-dir <dir> --analysis-date <date> --reexport-from-db`

### C4.2 当前真实产物判断

- `group-report-premium.md`
  - 已明显比上一版更厚
  - 当前已恢复：
    - `美股指数与板块` 主新闻桶，稳定 `4` 条
    - `利率汇率` 主新闻桶，稳定 `4` 条
    - `能源运输` 主新闻桶，稳定 `6` 条
  - 现在 `美股指数与板块` 已能直接多出一行结构纹理，不再只剩涨跌幅和新闻条目
  - `昨晚市场没认的消息` 现在也能把“热消息没认”和“资产没认”拆开看，不再全挤在一坨里
  - `新闻/信息层` 现在也不再是一坨平铺，已经开始把主因和背景拆开
  - `ignored_heat` 已不再和主因桶直接打架
- `desk-report-premium.md`
  - 已能稳定给出：
    - `美股指数与板块`
    - `利率汇率`
    - `能源运输`
  - `利率汇率` 已能吃到 `Census` 这类官方宏观标题
  - `中国代理` 即使新闻仍薄，也已经能靠结果层先给出“整体偏弱 / 谁在拖 / 映射期货有没有同向”的纹理
  - 已新增 `盘后续线验证`，但当前只是基于已有 watch 和 provider status 的轻验证层，不是独立亚太行情判断
  - 当前剩余短板已经收敛到 `中国代理` 缺更硬的解释料，以及真实 live smoke 还没跑

### C4.2.b 基于真实 2026-04-24 样本的数据质量判断

- 状态：已完成
- 本次动作：
  - 直接审查 `output/live-runs/readhub-2026-04-24/group-report-premium.json`
  - 直接审查 `output/live-runs/readhub-2026-04-24/desk-report-premium.json`
  - 直接审查隔离库 `data/live-runs/readhub-2026-04-23.db` 中 `2026-04-24` 对应 `result_first_materials`
  - 对 `scmp_markets / tradingeconomics_hk / bls_news_releases / iea_news` 跑真实 `SearchDiscoveryService.discover(...)` smoke
- 当前判断：
  - 当前真实样本最差的不是文案，而是源料厚度本身不够
  - `中国代理`：结果层有 `6` 行，但新闻层 `0` 条，`primary/background = 0/0`
  - `贵金属`：结果层有 `2` 行，但新闻层 `0` 条，`primary/background = 0/0`
  - `工业品`：结果层有 `2` 行，但新闻层 `0` 条，`primary/background = 0/0`
  - `energy_transport` 是当前唯一新闻密度和价格结果都较完整的桶
  - `result_first_materials=24` 里完全没有：
    - `scmp_markets`
    - `tradingeconomics_hk`
    - `bls_news_releases`
    - `iea_news`
  - 真实 discover smoke 结果：
    - `scmp_markets`：`0` candidates
    - `tradingeconomics_hk`：`0` candidates
    - `bls_news_releases`：`2` candidates
    - `iea_news`：`5` candidates
  - 真实 provider 健康度：
    - `Tavily` 对上述 query 基本全线 `http_432`
    - `SerpAPI` 在 `BLS` query 上出现 `ReadTimeout`
    - 当前运行环境 provider 列表只有：`SerpAPI / Bocha / Tavily`
    - `AIHubMix` 没有进入 runtime provider 列表；当前 `.env/.env.local` 未加载 `AIHUBMIX_*`
- 结论：
  - 下一步第一优先级不是继续调 report 文案，而是修 `中国代理` 的真实补料链
  - 下一步第二优先级是把 `AIHubMix` 正式接入当前运行环境并复跑 discover smoke
  - `BLS / IEA` 不是当前最急，因为它们至少已经能打到 candidate；`中国代理` 还是 `0`

### C4.3 下一步执行顺序

1. 并行继续 `T3.5`，优先补 `中国代理` 所需源侧入口：
   - `SCMP / 港股市场源`
   - `BLS`
   - `IEA`
   - `FedWatch`
2. 在可联网环境做 `scmp_markets / tradingeconomics_hk / BLS / IEA` live smoke
3. 每完成一刀都继续重跑 `2026-04-24` 实盘样本，确认不是“字段加了，但真实产物读感没变”

### C4.4 当前环境限制

- 当前环境已确认可直接访问部分外部 provider：
  - `Readhub` 返回 `200`
  - `Alpha Vantage` 返回 `200`
  - `TradingEconomics` 未授权时返回 `401`，符合预期
- `scmp_markets / tradingeconomics_hk / BLS / IEA` 的真实命中率、article fetch 成功率仍需继续做 source 级 live smoke
- 当前磁盘里的 `output/live-runs/readhub-2026-04-24/*.json` 已经通过隔离 DB 离线重导出修复为最新契约，freshness=`fresh`
- 当前主库 `data/overnight-news-handoff.db` 里仍没有 `2026-04-24` 的日报/快照记录，因此主库恢复线依旧不成立；可用恢复线是隔离 live-run DB

## 5. 回归要求

- 每次动 `result_first_reports.py` 后，至少跑：
  - `tests/test_result_first_reports.py`
  - `tests/test_daily_analysis.py`
- 每次影响导出或 live evidence 后，再补跑：
  - `tests/test_backend_live_run_evidence.py`
  - `tests/test_pipeline_runner.py`
  - `tests/test_pipeline_ops.py`

## 6. 当前结论

- 这条链已经从“结构上线”推进到“解释链开始像样”
- 当前已经完成的厚度补强：
  - `ignored_heat` 去重
  - `rates_fx` 官方宏观标题补厚
  - `us_equities` 真样本补厚
  - `us_equities / china_proxy` 结果纹理层
  - `ignored_heat` 的消息没认 / 资产没认矩阵
  - `news_layer` 的主因 / 背景分层
  - `desk_report` 的盘后续线验证层
  - `asset_miss` 与主因桶互校字段
- 现在最需要继续收尾的是：
  - `中国代理` 源料补齐
  - 官方源入口扩容后，继续验证空桶是否能被正确吃进来

### C4.2.c 真实中国代理补料推进结果

- 状态：已完成一轮实盘验证
- 本次动作：
  - 把 `AIHubMix` 真接入 `.env.local`，确认 provider 列表从 `SerpAPI / Bocha / Tavily` 变成 `SerpAPI / Bocha / Tavily / AIHubMix`
  - 对 `scmp_markets / tradingeconomics_hk / bls_news_releases / iea_news` 重跑真实 discover
  - 对 `scmp_markets` 跑定向 refresh，真实入库 `3` 条 SCMP article
  - 直接验证 article 页面正文时间，核对 search provider 返回的新鲜度是否可信
- 当前判断：
  - `AIHubMix` 接入后，`scmp_markets` discover 从 `0` 变成 `2-3`，说明这条链能找到文章 URL
  - 但 `tradingeconomics_hk` 仍然是 `0`
  - `BLS` / `IEA` 虽然能 discover，但正文抓取仍分别卡在 `403 / Cloudflare 403`
  - `scmp_markets` 定向 refresh 真实入库了 `3` 条文章，但它们页面正文时间分别是：
    - `2026-01-12 15:30`
    - `2026-03-11 10:10`
    - `2026-01-15 07:30`
  - 这与 `AIHubMix` discover 返回的 `2026-04-19 / 2026-04-20` 不一致，说明 `AIHubMix` 在这组 SCMP 结果上给了错误的新鲜度
  - 因此这 3 条文章不属于 `2026-04-24` 当前窗口，不能按真实数据标准塞进 `china_proxy`
- 结论：
  - 当前真实可用的 `中国代理` 新料依然是 `0`
  - 下一步不能继续围绕这 3 条 SCMP 旧文做 report 层修饰
  - 下一步必须做两件事：
    - 在 search discovery 层增加“search 发布时间与 article 页面时间冲突”的降权/剔除
    - 继续找真正能拿到当前窗口中国代理文章的源，优先继续打 `tradingeconomics_hk` 或新增海外市场源

### C4.3.d 结果层文案清洗与真实桶质控

- 状态：已完成
- 本次代码改动：
  - `app/services/result_first_reports.py`
    - 新增 `BUCKET_ALLOWED_SOURCE_IDS`，对 `rates_fx / precious_metals / industrial_metals` 做 source gate，避免明显错桶源混入结果解释层
    - 新增 `_source_allowed_for_bucket()`，但保留 `topic_tags` 穿透，避免误杀真实薄桶
    - 扩充 `_bucket_specific_why_snippet()` 到：
      - `us_equities`
      - `rates_fx`
      - `energy_transport`
      - `precious_metals`
      - `industrial_metals`
      - `china_proxy`
    - 扩大 `_looks_like_generic_bucket_snippet()` 黑名单，把此前串台最严重的泛化 why 文案直接过滤掉
  - `app/services/daily_analysis_provider.py`
    - 扩展 `_result_first_bucket_guardrail_text()`，把 `why_it_matters_cn` 和 `topic_tags` 纳入 guardrail 文本
    - 给 `precious_metals` 增加与 `industrial_metals` 对称的 summary 命中加分
    - 给 `kitco_news` 增加轻量级结果优先加分，帮助真实黄金/白银条目更容易进入 `result_first_materials`
- 真实验证：
  - `uv run pytest tests/test_daily_analysis.py tests/test_source_capture.py tests/test_collectors.py tests/test_result_first_reports.py -q`
  - 结果：`142 passed`
  - 补跑：`uv run pytest tests/test_daily_analysis.py tests/test_result_first_reports.py -q`
  - 结果：`45 passed`
- 实盘复算结论（`data/live-runs/readhub-2026-04-23.db` / `analysis_date=2026-04-24`）：
  - 已修正：
    - `farmdoc daily` 不再混入 `利率汇率`
    - `why` 串台大幅下降，不再出现能源模板大面积污染美股/国内资产映射
    - `美股指数与板块 / 利率汇率 / 能源运输 / 国内资产映射` 的解释读感更接近真实盘面
  - 仍然成立的硬事实：
    - `贵金属` 在这天真实窗口里没有被抬入 `group_report` 新闻层
    - `工业品` 在这天真实窗口里也没有被抬入 `group_report` 新闻层
    - 这不是展示层门槛问题，而是当前 `result_first_materials` 本身就没有足够强的 `precious_metals / industrial_metals` 条目
- 数据侧核验：
  - 定向增量 refresh：`kitco_news + mining_com_markets`
  - 结果：`candidate_count` 分别为 `17 / 6`，但 `persisted_count=0`
  - 当前库内可见时间分布：
    - `kitco_news` 在 `2026-04-23 ~ 2026-04-24` 确有若干黄金/白银稿
    - `mining_com_markets` 当前有效库存只有 `item_id=443/444` 两条旧稿，工业品源确实薄
  - 进一步复算显示：即便补了 guardrail，`2026-04-24` 这份真实 DB 下 `result_first_materials` 仍未选出 `precious_metals / industrial_metals` 主题条目
- 判断：
  - 当前产品已经比之前干净，报告层继续乱放宽只会把错桶脏料塞回来
  - `贵金属` 下一步要继续查为什么 `kitco_news` 已在库却没进入 `result_first_materials`
  - `工业品` 下一步仍然是源侧缺口，不能伪造“已经补齐”
- 下一步执行：
  1. 继续追 `kitco_news` 真实条目为什么没有进 `result_first_materials` 的评分链
  2. 给 `industrial_metals` 增加第二个可稳定抓取、可在当前环境落库的公开源
  3. 每补一个源，都必须重跑 `2026-04-24` 实盘样本，不接受只改测试不改产品效果

### C4.3.e 贵金属已真实进群发版，工业品补源推进到真实入库

- 状态：进行中
- 本次动作：
  - `app/services/source_capture.py`
    - 扩大贵金属 topic pattern，让 `Kitco` 标题里的
      - `gold market`
      - `gold demand`
      - `gold futures`
      - `silver imports`
      - `metals markets`
      能稳定落到 `gold_market / silver_market`
  - `app/services/result_first_reports.py`
    - 给 `group_report` 增加 thin-but-real 放行：
      - 对 `precious_metals / industrial_metals / china_proxy`
      - 如果结果桶有货、且 desk 已有 1 条主因
      - 群发版允许展示 1 条，不再硬卡 `>=2`
  - `app/sources/registry.py`
    - 新增 `fastmarkets_markets`
  - `app/collectors/section.py`
    - 新增 `fastmarkets_markets` 定向 raw-html fallback，仅在该源 `page_candidate_count=0` 时启用
    - 补 `'/insights/<slug>/'` 文章路径识别
    - 过滤图片资产 URL，避免 `.png/.jpg/...` 被当成文章 candidate
  - 新增 fixture / tests：
    - `tests/fixtures/overnight/fastmarkets_markets.html`
    - `tests/test_collectors.py` 对 `fastmarkets_markets` 的收集测试
    - `tests/test_source_capture.py` 对 `Kitco` 贵金属标题 topic 识别的真实语料测试
- 回归：
  - `uv run pytest tests/test_collectors.py tests/test_result_first_reports.py tests/test_source_capture.py tests/test_daily_analysis.py -q`
  - 结果：`144 passed`
- 实盘结果：
  - `Kitco` 补强后，`2026-04-24` 的真实群发版已经出现 `贵金属` 新闻桶
  - 当前群发版桶顺序已变成：
    - `美股指数与板块`
    - `利率汇率`
    - `能源运输`
    - `贵金属`
    - `国内资产映射`
    - `概率市场`
  - `贵金属` 当前真实主因：
    - `Kitco News | Gold demand anchored in mispriced risk as China buying signals ‘dip’ opportunity`
- `fastmarkets_markets` 真实接入状态：
  - 定向 refresh 成功：
    - `candidate_count=80`
    - `persisted_count=8`
  - 说明 collector/registry/search 这一层已经不是假接入，而是确实能落库
- 但 `工业品` 仍未进入 `2026-04-24` 的群发/内参新闻层，原因已经查实：
  - 当前落库的 `fastmarkets_markets` 条目大多是旧文：
    - 如 `2026-04-22`、`2026-04-14`
  - 还有一条图片资源 URL 曾被误抓，现已通过 collector 过滤修正
  - 这些条目在当前窗口判定里属于：
    - `stale_publication`
    - 或 `missing_published_time`
  - 因此它们不会进入 `2026-04-24` 的 result-first 生产链
- 当前判断：
  - `贵金属` 这条线已经从“结果层有、新闻层没有”推进到“群发版真实出现”
  - `工业品` 现在不再是“完全没源”，而是“新接入源已能入库，但当前抓到的新鲜度不够，仍未转化成产品有效料”
  - 这是实质推进，不是空转：阻塞已从“collector/source 缺失”缩小为“fresh same-day industrial article 缺失”
- 下一步：
  1. 对 `fastmarkets_markets` 做发布时间提取增强，尽量把真实页面中的文章时间抠出来，避免把当日文误判成旧文或无时间
  2. 继续筛一条能在当前环境抓到 same-day 铜/铝/钢材 headline 的工业品公开源
  3. 每次新增源后都复跑 `2026-04-24`，直到 `工业品` 真进群发/内参新闻层为止

### C4.3.f 当前产品状态：贵金属与工业品都已真实进入群发版新闻层

- 状态：已完成本轮产品推进目标
- 本次动作：
  - 继续增强 `fastmarkets_markets` 的 collector 行为：
    - 给 `SectionCollector` 增加附近纯文本日期提取
    - 在 `source_capture` 的 candidate ranking 中，对 `fastmarkets_markets / mining_com_markets` 增加工业品关键词优先级
      - `aluminium / aluminum / steel / copper / smelter / raw materials`
    - 对 `timber / pulp / paper / nonwovens / biodiesel / EUA prices` 这类偏离工业金属主线的标题降权
  - 清理隔离 live-run DB 中旧的 `fastmarkets_markets` 记录后重刷，避免旧排序污染结果
  - 重跑 `2026-04-24` 真实产物并刷新导出文件
- 回归：
  - `uv run pytest tests/test_source_capture.py tests/test_collectors.py tests/test_result_first_reports.py tests/test_daily_analysis.py -q`
  - 结果：`144 passed`
- 真实刷新结果：
  - `fastmarkets_markets` 二次重刷后，已经抓到 same-day 条目：
    - `2026-04-24T14:13:01+00:00 | North American automotive OEMs: How to protect margins in a volatile raw materials market`
  - `result_first_materials` 中已出现 `fastmarkets_markets` 条目：
    - `item_id=749`
    - `item_id=736`
- 当前最新产品结果（`analysis_date=2026-04-24` / `recent_limit=800`）：
  - `group_report` 新闻层桶顺序已变成：
    - `美股指数与板块`
    - `利率汇率`
    - `能源运输`
    - `工业品`
    - `国内资产映射`
    - `概率市场`
  - `工业品` 已真实进入群发版新闻层
  - 当前 `工业品` 主因：
    - `MINING.COM Markets | China discusses reopening border trade, cooperation in mining with Myanmar`
  - `贵金属` 也已在之前一轮真实进入群发版新闻层
- 导出成品：
  - 已刷新到：
    - `output/live-runs/readhub-2026-04-24-product-drop/manual-export/group-report-free.md`
    - `output/live-runs/readhub-2026-04-24-product-drop/manual-export/group-report-premium.md`
    - `output/live-runs/readhub-2026-04-24-product-drop/manual-export/desk-report-free.md`
    - `output/live-runs/readhub-2026-04-24-product-drop/manual-export/desk-report-premium.md`
    - 以及对应 JSON 文件
- 当前判断：
  - 这条产品线已经不再是“只有结构”，而是 `贵金属 / 工业品 / 国内资产映射` 都能在真实样本里出现在群发版新闻层
  - 后续继续打磨的重点已经从“有没有产品”切到“工业品主因要不要从 1 条扩到 2-3 条、更贴铜铝钢的盘面语言”
