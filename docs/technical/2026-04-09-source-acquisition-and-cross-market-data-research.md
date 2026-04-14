# 信源获取与跨市场数据获取调研

> **文档日期：** 2026-04-09  
> **项目：** `overnight-news-handoff`  
> **范围：** 只回答两件事  
> 1. `信源获取` 怎么做，哪些源应该抓，哪些源只是补充  
> 2. `从现有栈/同花顺 iFinD 技能里获取美股、港股等结构化市场数据` 到底可不可行，边界在哪里

## 1. 先给结论

这次调研的最终结论很明确：

1. `新闻信源` 和 `结构化行情/基本面数据` 必须拆成两条平面，不能混在一起。
2. `Bocha`、`Tavily`、`SerpAPI` 主要是 `搜索发现层`，不是主行情引擎。
3. `SerpAPI` 比 `Bocha/Tavily` 更接近“搜索 + 部分结构化金融页面抓取”的混合能力，但依然不应承担核心行情结算职责。
4. `X` 适合做 `信号雷达 / 事件监听层`，不适合做主事实层。它的价值在于更快发现事件，不在于替代正式新闻与正式披露。
5. `同花顺 iFinD` 在当前本地 skill 设计上，架构性地支持“任意 OpenAPI endpoint 调用”，因此**不是**只能做 A 股；并且本次已用真实 token 实测打通：
   - `A股` 基础数据
   - `A股` 实时行情
   - `港股` 实时行情
   - `美股` 日期序列历史数据
   - `美股` 历史 OHLC 行情
   - `港股` 历史行情数据
   - `美股指数` 历史行情（已确认 `IXIC.GI`）
   - `refresh_token -> access_token` 续期链路
6. 同时也已经实测确认部分权限边界：
   - `美股个股实时` 当前账号无权限，返回 `-4230`
   - `美股指数实时` 至少存在部分权限限制，`IXIC.GI` 返回 `-4225`
7. 但 iFinD 是否还能稳定覆盖 `更多美股指数实时`、`商品/期货`、`外汇`、`更多指标清单`，仍取决于 `账户权限`、`产品版本`、`具体 endpoint/indicator 可用性`，不能替你假设。
8. 本机现有 env 文件中还能直接加载 `Bocha / Tavily / SerpAPI / IFIND_REFRESH_TOKEN`，并已做 live provider 验证：
   - `SerpAPI` 在当前官方源 query 上是最强命中来源
   - `Tavily` 在部分官方源 query 上可用，但最新 live run 中多次返回 `http_432`
   - `Bocha` 已配置，但在官方源 same-domain 精准发现上明显偏弱
9. 现有本地参考栈已经明确证明：
   - `Yfinance` 可以作为 `美股股票 + 美股指数` 的已确认兜底路径。
   - `Akshare` 可以作为 `港股历史 + 港股实时` 的已确认路径。
   - `Pytdx / Baostock / Efinance / Tushare` 不能被当作本项目的美股主路径。
10. 这个项目的“每日固定结论”必须在 `美股收盘结束之后`、并且在 `主行情源完成入库之后` 生成，而不是边收新闻边提前下结论。
11. 如果把 `iFinD` 作为美股日线/收盘口径的主源，则根据官方 FAQ，`美股日行情数据在第二天 06:12 左右入库`，因此中国早晨固定报告的冻结时间不应早于 `06:15 Asia/Shanghai`。

## 2. 本文档的边界

本文档不展开：

- 最终 LLM prompt 怎么写
- 前端如何展示
- 个股推荐策略如何分层收费

本文档只冻结两层技术事实：

- `Part A`：信源获取平面
- `Part B`：结构化市场数据平面

这样做的原因很直接：如果前两层不稳定，后面的 AI 结论一定会漂。

## Part A. 信源获取

## 3. 信源获取的目标不是“搜到新闻”，而是“尽可能全地拿到可核实事实”

对这个项目，信源获取的目标应当定义为：

1. 覆盖中国早晨复盘最需要的 `隔夜国际政策 + 全球宏观 + 美股 + 大宗商品 + 公司事件`。
2. 先拿到 `原始事实来源`，再拿媒体解释，最后才拿社交信号。
3. 对每一条进入分析层的内容，都尽量保留：
   - 原始 URL
   - 来源域名
   - 发布时间
   - 摘要正文
   - 抓取路径
   - 是否为原站正文、还是搜索补全、还是社交信号

这意味着系统的目标不是“做一个搜索结果页”，而是做一个 `可追溯的隔夜证据池`。

## 4. 应抓的信源分层

### 4.1 第一层：官方一手源

这是必须优先抓的层，决定事实是否可靠。

优先覆盖的域名类型：

1. 美国政策与政府发布
   - `whitehouse.gov`
   - `treasury.gov`
   - `ustr.gov`
   - `state.gov`
   - `defense.gov`
   - `commerce.gov`
2. 美国宏观与监管数据
   - `federalreserve.gov`
   - `bls.gov`
   - `bea.gov`
   - `census.gov`
   - `sec.gov`
   - `cftc.gov`
   - `eia.gov`
3. 市场基础设施与交易所
   - `nasdaq.com`
   - `nyse.com`
   - `cmegroup.com`
   - `theice.com`
   - `lme.com`
4. 商品与全球供需相关官方/准官方机构
   - `eia.gov`
   - `opec.org`
   - `iea.org`
   - `usda.gov`
5. 公司正式披露
   - 公司 IR 页面
   - `sec.gov/edgar`
   - 财报新闻稿 / earnings release / 8-K / 10-Q / investor presentation

原因：

- 这层最适合回答“昨天晚上到底发生了什么”
- 对政策、制裁、关税、出口管制、产业补贴、宏观数据、公司指引等主题，必须以一手源为准
- 后续任何 AI 判断都应该尽量回溯到这里

### 4.2 第二层：主流媒体与金融媒体

这是解释层，不是最终事实层。

优先级较高的媒体类型：

1. 全球通讯社
   - Reuters
   - AP
2. 主流金融媒体
   - Bloomberg
   - Financial Times
   - Wall Street Journal
   - CNBC
   - MarketWatch
   - Barron's
3. 行业/科技市场媒体
   - 针对半导体、AI、云计算、能源、汽车、医药等专题媒体

这层的作用：

- 帮你解释“为什么涨”“为什么跌”
- 补充一手源没有明确写出来的市场解读
- 更快形成事件叙事

但这层不能单独决定结论。  
如果媒体说法和官方披露冲突，必须以一手源优先。

### 4.3 第三层：社交信号与事件雷达

这里主要指 `X`。

X 应该承担的职责：

1. 提前发现市场正在讨论的突发主题
2. 监听特定账户、关键词、主题标签
3. 辅助判断“某条新闻是否已经形成主线”

X 不应该承担的职责：

1. 直接替代正式新闻报道
2. 直接替代公司披露
3. 直接给出可交易结论

原因是 X 很强，但噪声也很高。  
它应该是 `雷达`，不是 `审判官`。

## 5. 外部搜索/发现提供方如何定位

### 5.1 Bocha

调研结论：

- 官方开放平台明确提供 `Web Search API`
- 官方首页明确把能力定位为适合 AI 使用的世界知识搜索引擎
- 结果包含 `title / url / snippet / summary / datePublished`
- 适合做 URL 发现、补全摘要、同域官方页搜索

应该怎么用：

1. 用于找一手站点的文章 URL
2. 用于目标站点 section 页被 `403/407` 或结构不稳定时做 `same-domain fallback`
3. 用于扩大 raw pool，而不是直接进入最终事实层

不应该怎么用：

1. 直接把 Bocha summary 当最终事实
2. 直接当结构化行情引擎
3. 直接替代原站正文抓取

工程判断：

- `Bocha` 很适合做 `官方站点文章发现`
- 不适合承担“昨夜美股和商品结算数据”的主来源

### 5.2 Tavily

调研结论：

- Tavily 官方 Search API 支持 `topic`
- 官方文档可见 `topic` 选项包括 `general / news / finance`
- 官方文档可见 `include_raw_content`，可返回清洗后的正文内容
- 官方文档可见 `time_range / start_date / end_date`

这意味着 Tavily 非常适合：

1. `news` 模式抓取实时政治/财经新闻
2. `finance` 模式做金融主题搜索
3. 在搜索结果中带出更可读的正文片段，减少纯 snippet 噪声

不应过度使用的原因：

- Tavily 返回的是搜索层抽取结果，不是交易所或终端级行情数据
- 当原站正文结构很差时，返回内容仍可能带导航/模板噪声

工程结论：

- `Tavily` 是当前最适合本项目做 `搜索发现 + 正文补全` 的补强层之一
- 可以继续保留在 `same-domain official fallback` 路线中
- 不应取代行情或财务结构化数据源

### 5.3 SerpAPI

调研结论：

1. `Google News API`
   - 官方文档明确提供 `engine=google_news`
   - 支持 `q / hl / gl` 等新闻搜索参数
2. `Google Finance API`
   - 官方文档明确提供 `engine=google_finance`
   - 查询对象可包括 `stock / index / mutual fund / currency / futures`
3. `Google Finance Markets API`
   - 官方文档明确提供 `engine=google_finance_markets`
   - 可获取 `indexes / most-active / gainers / losers / cryptocurrencies / currencies`

所以 SerpAPI 的定位不是单一搜索引擎，而是：

- `新闻发现`
- `金融页面抓取`
- `市场广度/强弱榜单补充`

但它仍不应被当作主行情引擎，原因有三点：

1. 本质上仍是对 Google 页面结果的抽取
2. 数据口径与字段稳定性不如专业行情终端
3. 在本项目已有 live smoke 中，`SerpAPI` 出现过 `429`

工程结论：

- `SerpAPI` 应当保留
- 但更适合：
  - 新闻发现补充
  - Google Finance 页面摘要与榜单补充
  - 作为“市场发生了什么”的辅助横截面
- 不适合作为 `Market Board` 的唯一或主结算源

### 5.4 X

官方文档调研结论：

1. `Search Posts`
   - `Recent Search` 支持最近 `7 天`
   - 对所有开发者可用
   - `Search all Posts` 支持完整历史，但需要 `Pay-per-use / Enterprise`
2. `Filtered Stream`
   - 支持规则驱动的近实时流
   - 文档给出大约 `6-7 秒 P99` 延迟
   - `Pay-per-use` 层支持 `1,000` 条规则
3. X API 总览页明确把其定位为：
   - public conversation
   - near real-time streaming
   - search & analytics

这意味着 X 在本项目里最合理的用法是：

1. `Recent Search`
   - 作为夜间回溯检索层
   - 查询“隔夜讨论是否迅速升温”
2. `Filtered Stream`
   - 作为夜间监听层
   - 跟踪白宫、商务部、主要记者、公司官方号、行业关键账号

不建议的错误用法：

1. 让 X 替代新闻采集
2. 让 X 单独驱动市场判断
3. 未经二次核验就把社交讨论写入每日固定结论

### 5.5 搜索/发现层能力定位总表

| 提供方 | 官方能力结论 | 适合承担 | 不适合承担 |
| --- | --- | --- | --- |
| Bocha | Web Search API，返回 URL/摘要/时间 | 一手源 URL 发现、同域 fallback | 主行情、最终事实判定 |
| Tavily | `topic=news/finance`，支持 `include_raw_content` | 新闻搜索、正文补全、低噪声发现 | 交易所级行情主源 |
| SerpAPI | Google News + Google Finance + Markets | 新闻发现、金融页面抓取、榜单补充 | 唯一行情引擎 |
| X Recent Search | 最近 7 天检索 | 事件回溯、话题热度确认 | 正式事实源 |
| X Filtered Stream | 近实时规则流 | 夜间监听、突发事件雷达 | 每日固定结论的唯一依据 |

## 6. 推荐的信源获取运行顺序

推荐按下面的顺序运行，而不是全丢给一个搜索 API：

1. `Direct official fetch`
   - RSS / sitemap / section page / 官方 API / 官方附件
2. `Primary media fetch`
   - 通讯社与金融媒体源
3. `Search discovery supplement`
   - Bocha / Tavily / SerpAPI
   - 只在 direct collector 为空、偏薄、被封、结构不稳定时触发
4. `X signal radar`
   - 用于追加候选主题，不直接进入最终事实层
5. `Normalization + dedupe + evidence binding`
6. `Event clustering`
7. `Mainline ranking`

核心原则：

- 搜索发现只负责 `找`
- 原站正文抓取负责 `证`
- 结构化市场数据负责 `定盘`
- 模型负责 `解释`

## 7. 推荐的信源抓取时间设计

如果这个产品目标是中国早晨看美国隔夜结果，那么时间语义必须固定。

推荐做法：

1. `持续采集窗口`
   - 从中国前一日晚间开始持续抓
   - 覆盖美国盘前、盘中、盘后、官宣夜间发布
2. `结算窗口`
   - 等美国正股收盘之后再生成“固定日报”
3. `冻结窗口`
   - 等主行情源入库完成后再冻结当日结论

对本项目更具体的建议：

1. 新闻采集可以整夜持续跑
2. `固定日报` 只生成一次
3. 如果主行情源用 iFinD 的美股日线口径，则冻结时间建议不早于 `06:15 Asia/Shanghai`
4. 如果要做盘后临时快报，应单独定义为 `alert` 产品，而不是改写固定日报

这能直接回答你前面反复强调的点：  
`每天的结论应该是固定的。`

## 8. 当前仓库在信源获取层的状态

目前 `overnight-news-handoff` 已经具备的内容：

1. 官方源 direct collector
2. `Bocha / Tavily / SerpAPI / Brave` 的环境注入式搜索补充
3. same-domain 限制
4. 搜索 provenance 落库
5. 新闻正文标准化与事件聚合基础能力

还没有做完的：

1. `X` 的 Recent Search / Filtered Stream 接入
2. 面向不同站点的 source-specific cleaner
3. 搜索提供方健康度与配额的持久化审计
4. “信号来源”和“正式证据来源”的前端显式区分

### 8.1 2026-04-09 本机 env 驱动的 live provider 验证

这一步不是只检查“变量名是否存在”，而是实际加载了本机现有 env 文件中的 provider key 做在线联调。

当前人工边界也已经明确：

1. 不碰中国政府网站
2. 美国政府官方网站可以抓
3. `State/DoD` 已按用户要求从默认采集面移除，不再作为本项目默认信源

实际加载来源：

1. `/Users/boyuewu/Projects/JusticePlutus/.env`
2. `/Users/boyuewu/Projects/JusticePlutus/.env.local`

本次确认到：

1. 已配置并可读取：
   - `BOCHA_API_KEYS`
   - `TAVILY_API_KEYS`
   - `SERPAPI_API_KEYS`
   - `IFIND_REFRESH_TOKEN`
2. 未在该 env 里确认：
   - `BRAVE_API_KEYS`

直接 provider 级别测试结果：

1. 查询 `site:treasury.gov press release`
   - `Tavily` 返回 3 条 `home.treasury.gov` 同域结果
   - `SerpAPI` 返回 3 条 `home.treasury.gov` 同域结果
   - `Bocha` 返回 0 条结果
2. 查询 `US Treasury press release`
   - `Bocha` 虽能返回结果，但偏向中文媒体转载站，same-domain 精度不足
   - `Tavily` 与 `SerpAPI` 更容易命中官方源
3. 查询 `site:state.gov spokesperson statement`
   - `Bocha` 命中 `history.state.gov` 等弱相关页面
   - `Tavily`、`SerpAPI` 更容易命中 `www.state.gov` 当前 release 页面

再往上一层，用当前仓库的 `SearchDiscoveryService.discover()` 做 source-aware 验证：

1. `whitehouse_news`
   - 成功产出 4 条可入管道候选，全部为 `same-domain`
   - 当前主命中 provider 为 `bocha`，并有 `serpapi` 补位
   - 已额外加上 source-aware 路径策略，过滤 `/gallery`、分页页与栏目 listing 页
2. `ustr_press_releases`
   - 成功产出 2 条可入管道候选，全部为 `same-domain`
   - 当前主命中 provider 为 `serpapi`
   - `ustr.gov/node` 这类弱路径已被明确过滤
3. `treasury_press_releases`
   - 成功产出 4 条可入管道候选，全部为 `same-domain`
   - 当前主命中 provider 为 `serpapi`
4. `ofac_recent_actions`
   - 成功产出 3 条可入管道候选，全部为 `same-domain`
   - 当前主命中 provider 为 `serpapi`
   - `recent-actions/general-licenses` 这类栏目 listing 页已被明确过滤
5. `bis_news_updates`
   - 当前 `search_discovery_enabled=false`
   - 这是有意禁用，不是失败；因为 direct section capture 已验证，但 search fallback 尚未单独验证
6. `doe_articles`
   - 当前 live run 返回 1 条 same-domain 候选
   - 说明 DOE 的 direct collector 正常，search query 已恢复可用但仍可继续打磨
   - `2026-04-10` 已补入第三条 DOE query，用于覆盖 `LNG / grid reliability / coal / manufacturing` 主题

工程结论：

1. 你本机当前 env 足以驱动这个项目的 `search discovery` 层
2. 就本机当前 key 与查询表现而言：
   - `SerpAPI` 是当前最稳的官方源 fallback 发现层
   - `Bocha` 在 `White House` 这类官方源上有实际补位价值
   - `Tavily` 仍值得保留，但要按 provider 健康状态做降权
   - `DOE` 这类源的 query 仍需继续迭代，但已经不再是 `0` 命中
3. 这不是架构猜测，而是当前本机密钥下的 live 结果
4. direct section capture 的现实边界也已经跑出来：
   - `White House / USTR / Treasury / OFAC / BIS / DOE` 当前可直接抓
5. 产品边界上已经明确：
   - 不碰中国政府网站
   - `State/DoD` 不再是本项目默认信源
6. same-domain 不是充分条件
   - 官方搜索结果仍必须叠加 source-aware path filter，才能避免把栏目页、分页页、弱入口页误送入后续分析
7. `BIS` 的 provider probe 结果已经补做
   - 当前最佳同域结果仍只是 `https://www.bis.gov/news-updates` 栏目页
   - 因此 `BIS` 继续保持 `search_discovery_enabled=false` 是正确决策

---

## Part B. 结构化市场数据获取

## 9. 先明确一个原则：搜索提供方不是行情提供方

`Bocha / Tavily / SerpAPI` 可以帮你发现新闻、页面、榜单。  
但要做下面这些对象，仍应优先走结构化市场数据源：

1. 美股主要指数收盘
2. 板块 ETF 收盘
3. 美股核心股票收盘/涨跌幅
4. 美债收益率、美元指数、离岸人民币
5. 黄金、白银、原油、铜等跨资产价格
6. 港股核心标的行情
7. 期货/商品相关结构化字段

否则最后会出现两个问题：

1. 价格、涨跌幅、收盘口径不稳定
2. 每日固定结论和新闻解释无法稳定对齐

## 10. 同花顺 iFinD 能力边界

### 10.1 本地 skill 的能力结论

我核查了本地 `tonghuashun-ifind-skill` 的设计和 README，结论很明确：

1. 这是一个 `raw-first` 的 iFinD OpenAPI skill
2. 主能力是 `api-call`
3. 它明确支持“调用任意 iFinD OpenAPI endpoint”
4. 浏览器自动化只负责拿 token，不负责抓业务数据

因此从架构上说：

- 这个 skill **不是** A 股专用 wrapper
- 只要 iFinD 后端 endpoint 和当前账户权限支持，理论上就可以取 `A股 / 港股 / 美股 / 指数 / 期货 / 基本面`

### 10.2 官方 iFinD 文档透露的关键信息

从同花顺官方接口帮助文档可以确认：

1. 数据接口支持多语言与 HTTP 接口
2. HTTP 接口采用 `refresh_token + access_token` 鉴权
3. 官方 FAQ 明确写出：
   - A 股日行情大约 `15:07` 入库
   - 港股日行情大约 `16:37` 入库
   - 美股日行情大约在次日 `06:12` 入库
4. 官方免费权限说明显示：
   - 免费版有 `历史行情 / 实时行情 / 日内快照`
   - 但免费版 `日内快照` 只支持上交所、深交所、上期所、大商所

这带来一个很重要的工程结论：

`iFinD 在产品能力上覆盖跨市场，并不等于你当前账户一定有跨市场实时权限。`

所以 iFinD 在这个项目中的正确定位是：

1. `优先主源`
2. 但必须做一次 `账户权限与 endpoint 实测`
3. 不能在没测前就假设“美股实时、港股实时、期货实时全部可用”

### 10.3 2026-04-09 实际 token 验证结果

本节不是理论判断，而是基于你提供的真实 `refresh/access token` 做的在线验证。

验证时间：

- `2026-04-09 Asia/Shanghai`

验证环境：

- 本地仓库 `tonghuashun-ifind-skill`
- CLI：`tonghuashun-ifind/scripts/ifind_cli.py`
- state 文件使用 `/tmp` 临时路径
- 未向文档记录任何原始 token
- 额外验证了 `/Users/boyuewu/Projects/JusticePlutus/.env.local` 中现有 `IFIND_REFRESH_TOKEN` 可直接驱动 refresh 链路

已确认成功的调用如下。

#### 10.3.1 鉴权与续期

1. `auth-set-tokens` 成功
   - 说明手动注入双 token 的路径可用
2. 构造过期 state 后再次调用 API，返回 `token_source=refresh`
   - 说明 `refresh_token -> get_access_token -> 新 access_token` 的续期链路真实可用
3. 使用本机 env 文件中现有的 `IFIND_REFRESH_TOKEN`，配合一个故意失效的 access token 再次调用 API
   - 仍返回 `token_source=refresh`
   - 说明当前机器上的现有 env 配置本身就足以自举 iFinD 链路，而不必每次重新人工贴 access token

工程含义：

- 这个项目可以不依赖浏览器登录，直接走 HTTP token 链路
- 对定时任务而言，续期能力已经从“设计支持”变成“实测支持”

#### 10.3.2 A 股基础数据

成功 endpoint：

- `/basic_data_service`

成功 payload 形态：

```json
{
  "codes": "300033.SZ,600000.SH",
  "indipara": [
    {
      "indicator": "ths_regular_report_actual_dd_stock",
      "indiparams": ["104"]
    },
    {
      "indicator": "ths_total_shares_stock",
      "indiparams": ["20220705"]
    }
  ]
}
```

实际结果：

- 返回 `errorcode=0`
- 返回了 `300033.SZ` 与 `600000.SH` 的对应字段

结论：

- A 股基础数据平面已实通

#### 10.3.3 A 股实时行情

成功 endpoint：

- `/real_time_quotation`

成功 payload 形态：

```json
{
  "codes": "300033.SZ",
  "indicators": "open,high,low,latest"
}
```

实际结果：

- 返回 `errorcode=0`
- 返回 `open/high/low/latest`
- 时间戳返回到 `2026-04-09 16:00:36`

关键实现细节：

1. 这个 endpoint 的多指标写法应使用英文逗号：
   - `open,high,low,latest`
2. 我曾测试过分号写法：
   - `open;high;low;latest`
   - 返回 `-4001 no data`

工程结论：

- 后续 `iFinD realtime adapter` 必须把 realtime 指标串与 history 指标串区分处理，不能直接复用一套拼接规则

#### 10.3.4 美股历史数据

成功 endpoint：

- `/date_sequence`

成功 payload 形态：

```json
{
  "codes": "AAPL.O",
  "startdate": "20250101",
  "enddate": "20250113",
  "functionpara": {
    "Days": "Alldays",
    "Fill": "-1"
  },
  "indipara": [
    {
      "indicator": "ths_pre_close_uss",
      "indiparams": ["", "100"]
    }
  ]
}
```

实际结果：

- 返回 `errorcode=0`
- 返回 `AAPL.O` 在 2025-01-01 到 2025-01-13 的序列值

结论：

- 你的当前权限下，`美股历史/日期序列` 至少已经有一条真实可用路径
- 对本项目而言，这足以支持“美股收盘结果在 iFinD 中落地”的工程方向

#### 10.3.5 美股历史 OHLC 行情

成功 endpoint：

- `/cmd_history_quotation`

成功 payload 形态：

```json
{
  "codes": "AAPL.O",
  "indicators": "open,high,low,close",
  "startdate": "2025-01-02",
  "enddate": "2025-01-10",
  "functionpara": {
    "Fill": "Previous"
  }
}
```

实际结果：

- 返回 `errorcode=0`
- 返回 `AAPL.O` 多个交易日的 `open/high/low/close`

结论：

- 当前权限下，美股不仅能拿日期序列指标，还能拿到历史 OHLC 行情

#### 10.3.6 港股历史行情

成功 endpoint：

- `/cmd_history_quotation`

成功 payload 形态：

```json
{
  "codes": "0700.HK",
  "indicators": "open,high,low,close",
  "startdate": "2025-01-02",
  "enddate": "2025-01-10",
  "functionpara": {
    "Fill": "Previous"
  }
}
```

实际结果：

- 返回 `errorcode=0`
- 返回 `0700.HK` 在多个交易日上的 `open/high/low/close`

同时验证到一条失败样例：

- `codes="00700.HK"` 返回 `-4210 input parameters error`

结论：

1. 港股历史行情在当前 token 下已实通
2. 本次实测中，港股代码口径应按 `0700.HK` 使用，而不是 `00700.HK`

#### 10.3.7 港股实时行情

成功 endpoint：

- `/real_time_quotation`

成功 payload 形态：

```json
{
  "codes": "0700.HK",
  "indicators": "open,high,low,latest"
}
```

实际结果：

- 返回 `errorcode=0`
- 返回 `open/high/low/latest`
- 时间戳返回到 `2026-04-09 16:08:24`

结论：

- 当前账号对港股实时至少有可用权限
- `overnight-news-handoff` 如果要扩展到港股晨报或港股映射层，可以优先接 iFinD realtime

#### 10.3.8 美股实时行情权限边界

测试 endpoint：

- `/real_time_quotation`

测试 payload：

```json
{
  "codes": "AAPL.O",
  "indicators": "latest,open"
}
```

实际结果：

- 返回 `errorcode=-4230`
- 错误信息：`You currently do not have permission for real-time US stock market quotes.`

结论：

- 当前账号对 `美股个股实时行情` 没有权限
- 这意味着本项目若要拿 `美股实时`，仍需 fallback 到：
  - `Yfinance`
  - 或未来补充的其他授权行情源

#### 10.3.9 美股指数历史与实时边界

已确认成功：

1. `IXIC.GI` 通过 `/cmd_history_quotation` 返回历史 `open/high/low/close`

已确认失败：

1. `IXIC.GI` 通过 `/real_time_quotation` 返回 `errorcode=-4225`
2. 错误信息：`Permission denied for FTSE security`

补充说明：

1. `SPX.GI` 与 `HSI.HI` 在本次猜测式历史行情测试中返回 `-4210`
2. 这类失败不能直接解释为“没有该市场权限”
3. 更稳妥的解释是：
   - 这些代码口径或参数口径尚未通过官方超级命令进一步确认

工程结论：

- 当前已能确认 `美股指数历史` 至少有一条真实可用路径（`IXIC.GI`）
- 但 `美股指数实时` 在当前权限下并不应假设可用

#### 10.3.10 失败样例也很重要

下面这些失败不是坏事，反而帮助我们收敛正确接法：

1. 早期用错误 payload 直接打 `/basic_data_service`
   - 返回 `-4210`
   - 说明 iFinD HTTP 接口对 payload 结构要求严格，不能只凭 repo 内简化示例猜字段
2. 早期用错误 payload 打 `/date_sequence`
   - 返回 `-4210`
   - 说明美股指标和日期序列参数必须按官方超级命令口径组织
3. `real_time_quotation` 用分号拼多指标
   - 返回 `-4001 no data`
   - 说明 realtime 指标拼接规则与历史行情不同
4. `AAPL.O` 调实时行情
   - 返回 `-4230`
   - 说明失败原因是权限，而不是代码不存在
5. `IXIC.GI` 调实时行情
   - 返回 `-4225`
   - 说明至少部分海外指数实时权限也受限
6. `SPX.GI`、`HSI.HI` 用当前猜测代码调历史行情
   - 返回 `-4210`
   - 说明对更多指数代码仍需通过超级命令进一步确认标准 thscode

工程结论：

- 后续写 provider adapter 时，不能只把 endpoint 通用化，还要把“正确 payload 模板”沉淀成显式映射

### 10.4 iFinD 对本项目的最佳定位

最合理的定位是：

1. `主结构化市场数据平面`
   - 美股收盘
   - 港股收盘
   - 指数
   - 外汇
   - 利率
   - 期货/商品
2. `主结构化基本面平面`
   - 公司基本资料
   - 财务指标
   - 估值
   - 研报/专题报表
3. `可付费增强平面`
   - 为 premium 个股推荐提供更稳定的结构化底座

## 11. 从现有本地参考栈能确认什么

这里不修改 `daily_stock_analysis`，只把它当作本地已存在能力证据。

### 11.1 美股

本地 `DataFetcherManager` 已明确把：

- `美股指数`
- `美股股票`

直接路由到 `YfinanceFetcher`。

结论：

- 本地代码已经证明 `Yfinance` 是现成可用的美股 fallback
- 适合：
  - 美股股票日线
  - 美股指数日线
  - 美股实时/准实时兜底

### 11.2 港股

本地 `YfinanceFetcher` 明确支持：

- `0700.HK` 这类港股代码转换

本地 `AkshareFetcher` 明确支持：

- `ak.stock_hk_hist()`
- `ak.stock_hk_spot_em()`

结论：

- 港股在本地现有栈中不是空白
- 已确认至少存在：
  - `Akshare` 港股历史
  - `Akshare` 港股实时
  - `Yfinance` 港股历史 fallback

### 11.3 不能承担跨市场主路径的提供方

本地代码显示以下提供方不适合承担本项目的美股主路径：

- `Pytdx`
- `Baostock`
- `Efinance`
- `Tushare`

原因不是这些提供方没价值，而是它们主要是 A 股生态能力。

## 12. 跨市场数据提供方能力矩阵

| 提供方 | 美股股票 | 美股指数 | 港股 | 商品/期货 | 实时/准实时 | 历史日线 | 结论 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| iFinD | 理论上支持，取决于权限/endpoint | 理论上支持 | 理论上支持 | 理论上支持 | 取决于权限 | 支持 | 应作为首选主源 |
| Yfinance | 已确认 | 已确认 | 历史已确认 | 部分已确认 | 美股已确认，港股实时未在本地代码中确认 | 已确认 | 适合美股主 fallback、港股历史 fallback |
| Akshare | 本地项目中不作为主路径 | 不推荐 | 已确认 | 国内商品更强，海外一般 | 港股已确认 | 港股已确认 | 适合港股 fallback |
| SerpAPI Google Finance | 可搜页面 | 可搜页面 | 取决于 Google Finance 页面 | 货币/期货页面可查 | 不是终端级 | 页面级 | 只能做补充 |
| Bocha | 否 | 否 | 否 | 否 | 否 | 否 | 只做发现 |
| Tavily | 否 | 否 | 否 | 否 | 否 | 否 | 只做发现 |
| Pytdx | 否 | 否 | 否 | 否 | A 股为主 | A 股为主 | 不纳入本项目跨市场主线 |
| Tushare / Efinance / Baostock | 否或不稳定 | 否 | 弱 | 弱 | A 股为主 | A 股为主 | 不纳入美股主线 |

## 13. 推荐的数据平面分工

### 13.1 主源优先级

推荐优先级如下：

1. `iFinD`
   - A 股基础数据、A 股实时、港股实时、港股历史、美股历史、美股历史 OHLC 已实测可用
   - 美股个股实时、美股指数实时存在明确权限边界
   - 只要当前账户权限覆盖目标市场，就作为主源
2. `Yfinance`
   - 负责美股股票/指数 fallback
3. `Akshare`
   - 负责港股 fallback
4. `SerpAPI Google Finance / Markets`
   - 只做榜单、热度、页面补充

### 13.2 为什么不能继续只靠 Yahoo Finance

本项目此前 live run 已暴露出一个现实问题：

- Yahoo Finance 在市场快照抓取中出现过 `429`

这意味着：

1. Yahoo 不能承担唯一主源
2. 它适合留作 fallback
3. 如果要把产品做成稳定可交付版本，必须把 `iFinD` 或其他更稳的授权源放到前面

### 13.3 面向这个项目应该优先拿哪些结构化对象

优先抓取对象建议固定为：

1. 美股指数
   - `SPX / NDX / DJI / RUT / VIX`
2. 美股板块与风格代理
   - `XLK / SOXX / XLF / XLE / XLI / XLV / XLY / XLP`
3. 核心科技与大市值股票
   - `NVDA / AMD / MSFT / AAPL / AMZN / AVGO / META / TSLA`
4. 港股核心标的
   - `00700 / 09988 / 01810 / 03690` 等
5. 利率与外汇
   - 美债收益率
   - `DXY`
   - `USD/CNH`
6. 贵金属与能源
   - 黄金
   - 白银
   - WTI
   - Brent
7. 工业品与映射商品
   - 铜
   - 天然气
   - 与国内化工链相关的海外代理价格/事件

注意：

- 国内甲醇、PX、PTA、乙二醇等分析，很多时候不应直接依赖海外新闻页面做定价，而应通过 `海外驱动 + 国内合约映射` 做第二层分析
- 这一步属于后续分析层，不属于本次“数据平面能力确认”范围

## 14. 固定日报的时间冻结规则

这个规则建议直接写死进技术方案，不要留模糊空间：

1. `新闻采集` 可以持续整夜运行
2. `市场快照` 必须等美国收盘后抓
3. `固定日报` 每个 `analysis_date` 只生成一次
4. 若主源为 iFinD 的美股日线口径，则生成时间不早于 `06:15 Asia/Shanghai`
5. 06:15 之前即使已经有搜索新闻，也不输出最终固定结论

原因：

1. 你的使用场景不是“盘中猜”，而是“早晨看昨夜已经走完的结果”
2. 如果先用新闻后补行情，很容易出现主线和市场结果不对齐
3. 先定盘，再解释，才是这个产品的正确顺序

## 15. 当前项目与后续实现建议

### 15.1 已有基础

`overnight-news-handoff` 当前已经有：

1. 新闻 direct collector
2. 搜索发现补强层
3. `iFinD-first + Yahoo fallback` 的 market snapshot
4. 事件聚类、主线、日报对象

### 15.2 这次调研后建议新增或调整的重点

1. 在文档层明确：
   - `搜索发现` 与 `结构化行情` 分层
2. 在数据层新增：
   - `US/HK entitlement smoke test`
   - `更多商品/利率代码的 iFinD code matrix`
3. 在调度层新增：
   - `US close freeze window`
4. 在对象层新增或强化：
   - `cross-market close board`
   - `US/HK movers`
   - `rates/fx/commodities settlement block`
5. 在质量控制层新增：
   - source authority
   - provider provenance
   - market-source provenance

### 15.3 不应做的错误方向

1. 不要把 `Bocha / Tavily / SerpAPI` 当市场主源
2. 不要让 `X` 直接写入最终事实
3. 不要在美国收盘前或主行情源未入库前就输出固定日报
4. 不要把 `daily_stock_analysis` 的全量逻辑直接侵入这个项目

## 16. 尚未完成但必须补的验证

截至 `2026-04-09` 的 fresh live 结果，建议把“已验证”与“未验证”彻底拆开看。  
完整运行记录见：

- `overnight-news-handoff/docs/technical/2026-04-09-live-validation-runbook.md`

已经不应再放进“未验证”里的内容：

1. `iFinD A股实时`
2. `iFinD 港股实时`
3. `iFinD 美股历史`
4. `iFinD 美股指数历史`
5. `iFinD 美股个股实时权限不足`
   - 已实测 `AAPL.O -> -4230`
6. `iFinD 美股指数实时权限不足`
   - 已实测 `IXIC.GI -> -4225`

当前仍然必须补的，是下面这些：

1. `iFinD` 更完整的商品、外汇、更多指数代码与权限矩阵
2. `iFinD` 具体用于本项目的 endpoint / indicator 固定清单
3. `market snapshot` 剩余尾项的 fallback 完整性
   - 截至最新 live rerun，`market snapshot` 已捕获 `23/23`
   - `^TNX` 已改由官方 `Treasury Yield Curve` provider 提供
   - `ALI=F` 已通过 iFinD 代理代码 `DBB.P` 补齐，但后续仍可继续寻找更直接的铝/基础金属路径
4. `X` 接入时的规则集、速率成本和夜间噪声控制
5. 商品与化工链的“海外驱动 -> 国内期货映射”字段表

这些不是架构风险，而是 `接入验证任务`。

## 17. 最终技术方案冻结

到这一步，可以把两部分方案冻结成下面的工程定义：

### 17.1 信源获取方案

1. 以 `官方一手源 + 主流媒体` 为主事实层
2. 以 `Bocha / Tavily / SerpAPI` 为搜索发现补强层
3. 以 `X Recent Search + Filtered Stream` 为信号雷达层
4. 任何搜索结果、社交结果，在进入固定日报前都必须尽量回到原站 URL

### 17.2 跨市场数据获取方案

1. 以 `iFinD` 作为首选结构化市场数据平面
2. 以 `Treasury Yield Curve` 作为 `^TNX` 的官方补充源
3. 以 `Yahoo Finance Chart` 作为美股与商品路径的通用 fallback
4. 以 `Akshare` 作为港股 fallback
5. 以 `SerpAPI Google Finance / Markets` 作为榜单与页面补充
6. 每日固定日报基于 `收盘已完成 + 主源已入库` 的事实生成

---

## 18. 参考依据

### 18.1 官方外部资料

1. Tavily Search API  
   https://docs.tavily.com/documentation/api-reference/endpoint/search
2. SerpAPI Google News API  
   https://serpapi.com/google-news-api
3. SerpAPI Google Finance API  
   https://serpapi.com/google-finance-api
4. SerpAPI Google Finance Markets API  
   https://serpapi.com/google-finance-markets
5. Bocha 开放平台总览  
   https://open.bochaai.com/
6. X API 总览  
   https://docs.x.com/x-api/introduction
7. X Search Posts  
   https://docs.x.com/x-api/posts/search/introduction
8. X Filtered Stream  
   https://docs.x.com/x-api/posts/filtered-stream/introduction
9. 同花顺数据接口 FAQ  
   https://quantapi.51ifind.com/gwstatic/static/ds_web/quantapi-web/help-center/faq.html
10. 同花顺数据接口部署/HTTP 鉴权说明  
   https://quantapi.51ifind.com/gwstatic/static/ds_web/quantapi-web/help-center/deploy.html
11. 同花顺数据接口权限说明  
   https://quantapi.51ifind.com/gwstatic/static/ds_web/quantapi-web/help-center/permission.html

### 18.2 本地代码与文档依据

1. `tonghuashun-ifind-skill/README.md`
2. `tonghuashun-ifind-skill/docs/superpowers/specs/2026-04-06-tonghuashun-ifind-skill-design.md`
3. `daily_stock_analysis/data_provider/base.py`
4. `daily_stock_analysis/data_provider/yfinance_fetcher.py`
5. `daily_stock_analysis/data_provider/akshare_fetcher.py`
6. `daily_stock_analysis/data_provider/pytdx_fetcher.py`
7. `overnight-news-handoff/docs/technical/cross-market-overnight-architecture.md`
8. `overnight-news-handoff/docs/technical/search-discovery-supplement-architecture.md`
