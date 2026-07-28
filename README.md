# majiang-coach · 川麻血战教练

血战到底核心算法实现。

- **Phase 1**:纯 Python、零第三方依赖的核心算法层——给定手牌 → 是否胡牌/听牌、向听数、有效牌列表。
- **Phase 2**:完整血战到底 Game Engine——发牌→换三张→定缺→摸打→碰/杠/胡→血战续打→终局,4 个可插拔 Actor(默认随机)跑通一局,输出结构化 JSON 牌谱。结算桩记录胡牌事件与算番所需事实(番种/分数推迟)。
- **Phase 3**:Analysis Engine(硬计算,不依赖 LLM)——输入一个座位视角 `PlayerView`,输出结构化 JSON:手牌差张下叫/进张(含副露)、每张可弃牌的进攻期望 + 安全度 + 综合排序推荐。供 Phase 4 LLM 引用防幻觉、Phase 5 启发式 AI 消费、Phase 6 复盘复用。

> Phase 3 完成后停下等用户确认再进 Phase 4。

## 术语约定(川麻口语,最终成品统一使用)

> 说明:
> 1. 川麻无统一书面术语,均为线下牌桌通用口语;不同地区(成都、重庆、川东)说法略有差异。
> 2. 日麻「一向聴(イーシャンテン)」俗称圈内简写 **E听**;テンパイ=听牌。
> 3. 川麻核心词汇:**下叫=听牌**。

### 一、手牌状态
| 日麻术语 | 日文读音 | 通俗简称 | 川麻口语 | 释义 |
| ---- | ---- | ---- | ---- | ---- |
| 一向聴 | イーシャンテン | E听 | 一进叫 / 差一张下叫 | 再摸一张有效牌就能听牌 |
| 聴牌 | テンパイ | 听牌 | 下叫 | 只差一张牌胡牌 |
| 空聴 | カラテン | 空听 | 死叫 | 所有待牌全部打完,没有胡牌机会 |
| ノーテン | — | 无听 | 没下叫 | 手牌没有进入听牌状态 |

### 二、听牌类型(待ち形状)
| 日麻术语 | 简称 | 川麻口语 | 例子 |
| ---- | ---- | ---- | ---- |
| 単騎待ち | 单骑 | 单吊叫 | 555万+7筒,等7筒胡牌 |
| 両面待ち | 两面 | 两面叫 | 34万,等2、5万 |
| 嵌張待ち | 嵌张 | 卡张叫 | 35万,等4万 |
| 辺張待ち | 边张 | 边张叫 | 12万,等3万 |
| 双碰待ち(シャンポン待ち) | 双碰 | 对对叫 / 双碰叫 | 22万、44筒,等2万、4筒 |
| 三面待ち | 三面 | 三面叫 | 3456万,等2、5、8万 |
| 多面待ち | 多面 | 多面叫 | 九莲宝灯、纯正九莲等复合型听牌 |

### 三、胡牌相关
| 日麻术语 | 川麻口语 | 备注 |
| ---- | ---- | ---- |
| 和了(アガリ) | 胡牌 |  |
| 自摸(ツモ) | 自摸 | 川麻通用叫法 |
| 荣和(ロン) | 点炮 / 放炮 | 别人打出你胡牌 |
| 振听 | 振听 | **川麻没有振听规则!** 川麻打过的牌依旧可以胡,不存在振听限制 |
| 役 | 番数 / 名堂 | 日麻靠役胡牌;川麻靠番型 |

### 四、牌型组合
| 日麻术语 | 川麻口语 |
| ---- | ---- |
| 面子 | 搭子、成副 |
| 順子 | 顺子 | 345万这类连续三张,叫法一致 |
| 刻子 | 对子杠/坎 | 三张相同:暗刻=暗坎;明刻=碰牌 |
| 暗刻 | 暗坎 | 手里三张一样,没有碰出 |
| 明刻 | 碰 | 碰出来的三张 |
| 槓子(カン) | 杠 |
| 暗槓 | 暗杠 | 手里四张直接杠 |
| 明槓 | 明杠 | 先碰再杠 / 别人打出四张开杠 |
| 雀頭 | 将对/对子 | 胡牌所需的一对将牌 |

### 五、动作术语
| 日麻术语 | 川麻口语 |
| ---- | ---- |
| ポン | 碰 | 通用 |
| チー | 吃 | **川麻绝大多数规则禁止吃牌!** |
| カン | 杠 | 通用 |
| リーチ | 立直 | **川麻无立直,没有"报听、立直棒"规则** |

### 六、重要规则差异提醒(非常关键,避免混淆)
1. **吃牌**:日麻可以吃;主流血战川麻**不能吃**
2. **立直**:日麻专属;川麻不存在
3. **振听**:日麻核心限制;川麻完全没有振听
4. **E听(一向听)**:形态互通,但本地人听不懂这个词,聊天请说「一进叫」
5. 日麻必须有役才能胡;**普通川麻无"役"门槛,满足基本牌型即可胡**

### 补充小短句转换示范
- 日麻:现在一向听,摸牌进张就能立直听牌
- 川麻:现在一进叫,摸到有效牌就能下叫
- 日麻:这个牌是两面待ち
- 川麻:这个牌是两面叫

> 本项目代码内部仍保留日麻技术词(`shanten`/`ukeire`/`win`)作函数名(国际通用、便于对接开源算法),但**面向用户的输出(CLI/API)一律用川麻口语**。向听数对外显示为「差几张下叫」语义,听牌待ち显示为「叫牌」。

## 牌表示约定

- **牌池**:万(m)/条(s)/筒(p)三门,各 1-9 共 27 种 × 4 张 = 108 张。无字牌、无宝牌/红中。
- **索引**:`0-8` 万(1m-9m)、`9-17` 条(1s-9s)、`18-26` 筒(1p-9p)。
- **字符串码**:`1m..9m / 1s..9s / 1p..9p`(`m=万 / s=条(竹) / p=筒(点)`,标准麻将字母码,非拼音首字母)。
- **内部**:长度 27 的计数数组 `counts[27]`,每项 0-4。

## 目录结构

```
majiang-coach/
├─ pyproject.toml             # pytest 配置 + 可选依赖 (fastapi/uvicorn/pydantic 仅 api 模块)
├─ src/majiang_coach/
│  ├─ tiles.py                # 牌表示:索引/字符串码/emoji 互转 + 常量
│  ├─ hand.py                 # Hand:counts[27] 不可变结构 + add/remove/clone/缺门判定
│  ├─ decompose.py            # 内部:单门面子/搭子分解 (win/shanten 复用)
│  ├─ win.py                  # win(hand, lack_suit, melds=0) -> bool (标准形 ‖ 七对,副露扩展)
│  ├─ shanten.py              # shanten(hand, lack_suit, melds=0) -> int (副露扩展)
│  ├─ ukeire.py               # ukeire(hand待摸态, lack_suit, melds=0) -> 有效牌列表(副露扩展)
│  ├─ demo.py                 # Phase 1 CLI demo
│  ├─ demo_game.py            # Phase 2 CLI:跑一局 4 随机 AI,打印牌谱摘要
│  ├─ demo_analyze.py         # Phase 3 CLI:给手牌+局面,输出分析 JSON/摘要
│  ├─ engine/                 # Phase 2 Game Engine(零依赖)
│  │  ├─ wall.py              # TileWall:种子洗牌/发牌/摸牌/杠尾摸牌/流局
│  │  ├─ melds.py             # Meld:碰/杠副露数据类
│  │  ├─ action.py            # Action 判别联合 + 合法动作生成(缺门约束)
│  │  ├─ view.py              # PlayerView:信息隔离视角(含公开缺门 lack_suits)
│  │  ├─ rules.py             # 申索裁定:ron>碰/杠、一炮多响、抢杠
│  │  ├─ state.py             # GameState:完整可回放状态(make_view 填 lack_suits)
│  │  ├─ game.py              # Game 主循环 + Actor 协议 + RandomActor
│  │  ├─ record.py            # GameRecord JSON 事件流 + replay()
│  │  └─ settlement.py        # 结算桩(记胡牌事实/花猪标志,不算番)
│  └─ analysis/               # Phase 3 Analysis Engine(零依赖,纯函数)
│     ├─ visible.py           # visible_counts/remaining_counts(未见张=牌墙+他家暗手)
│     ├─ threat.py            # opponent_threat v0(听牌概率粗估,软权重)
│     ├─ safety.py            # safety_of:0-100 危险度 + 壁/缺门/现物/巡目
│     ├─ offense.py           # offense_of:进张期望(差张下叫+进张+未见)
│     ├─ recommend.py         # analyze:逐候选弃牌指标 + 综合排序 + 推荐 + claim
│     └─ result.py            # to_dict/from_dict 序列化聚合
├─ api/main.py                # FastAPI: phase1/analyze + phase2/play + phase3/analyze
└─ tests/                     # 单元 + 集成测试
```

## 安装与运行

```bash
# 仅核心(零依赖):只需 Python 3.12+

# 安装测试依赖
pip install -e ".[dev]"

# 跑测试(必须用 python -m pytest,因 api 包在仓库根)
python -m pytest

# (可选)安装 api demo 依赖
pip install -e ".[api]"
```

## CLI demo

```bash
# 13 张听牌:两杯口听 5s
python -m majiang_coach.demo 1m2m3m 1m2m3m 7m8m9m 7m8m9m 4s5s --lack p

# 14 张胡牌
python -m majiang_coach.demo 1m2m3m 4m5m6m 7m8m9m 1s2s3s 5s5s --lack p

# 不显示 emoji(兼容不支持 unicode 的终端)
python -m majiang_coach.demo 1m2m3m 4m5m6m 7m8m9m 1s2s3s 5s5s --lack p --no-emoji
```

输出含:张数、缺门、是否胡牌(14 张)、向听数、听牌待ち(13 张听牌)或有效牌(向听≥1)。

## API demo

```bash
pip install -e ".[api]"
uvicorn api.main:app --reload
```

```bash
curl -X POST http://127.0.0.1:8000/api/phase1/analyze \
  -H "Content-Type: application/json" \
  -d '{"codes":["1m2m3m","4m5m6m","7m8m9m","1s2s3s","5s5s"],"lack_suit":"p"}'
```

响应字段:`total / suits_present / lack_suit / is_win / is_tenpai / shanten / ukeire[]`。

## Phase 2 CLI demo(跑一局)

```bash
# 跑一局 4 随机 AI,打印摘要
python -m majiang_coach.demo_game 42

# 打印摘要 JSON
python -m majiang_coach.demo_game 42 --json

# 打印完整 JSON 牌谱(meta + 事件流 + 结果)
python -m majiang_coach.demo_game 42 --full
```

摘要含:种子、换三张方向、各座缺门、事件数、胡家(座/自摸或点炮/胡牌/抢杠)、输家(座/花猪)、是否流局。

## Phase 2 API demo

```bash
pip install -e ".[api]"
uvicorn api.main:app --reload
```

```bash
curl -X POST http://127.0.0.1:8000/api/phase2/play \
  -H "Content-Type: application/json" \
  -d '{"seed":42}'
```

响应:`{record: {meta, events, result}, summary: {winners, losers, drawn, ...}}`。

## 牌谱 GameRecord 字段说明

牌谱为语言无关 JSON 事件流(Phase 6 复盘依赖):

| 事件 `t` | 字段 | 说明 |
| ---- | ---- | ---- |
| `deal` | seat, tiles | 发牌(换三张前初始 13 张) |
| `swap` | direction, given, received | 换三张(方向 cw/ccw/across) |
| `lack` | seat, suit | 定缺(0=万 1=条 2=筒) |
| `draw` | seat, tile, src | 摸牌(src=wall) |
| `discard` | seat, tile | 弃牌 |
| `pon` | seat, from, tile | 碰 |
| `kan` | seat, kind, tile, from? | 杠(kind=ankan/daiminkan/shouminkan) |
| `kan_draw` | seat, tile, src | 杠尾摸牌(src=rinshan) |
| `tsumo` | seat, tile, hand, melds, lack | 自摸胡(记录全暗手) |
| `ron` | seat, from, tile, hand, melds, lack, robbery | 点炮胡(robbery=抢杠) |
| `ryuukyoku` | — | 流局 |

- `meta`:version/ruleset/seats/dealer/direction/seed/swap_direction/lack。
- `result`:winners(座/自摸或点炮/胡牌/暗手/副露/缺门/抢杠)、losers(座/暗手/副露/缺门/花猪)、drawn。
- `replay(record)`:按事件流复现终局(FinalState),供复盘校验。
- 终局事件(tsumo/ron)记录全暗手;过程事件不泄露他家暗手。

## Phase 3 Analysis Engine(硬计算结构化输出)

`analyze(view, weights=None) -> AnalysisResult` 是纯函数:同一 `PlayerView` 必产出同一结果,可复用于复盘任意牌谱位置。核心算法零第三方依赖,后端/小程序直接复用,前端只消费 JSON。

### 14 张 vs 13 张语义
- **14 张(刚摸、待弃)**:对每张合法弃牌算 `offense_after`(弃后进攻期望)+ 安全度 + 综合,产出 `candidates` 与 `recommend`(综合最高,平手按 tile 升序)。并标 `best_offense`/`best_defense`。
- **13 张(轮别人 / 刚弃完)**:只输出 `hand`(整体差张下叫/进张)+ 可选 `claim`(若有 `last_discard` 可申索)。不产出弃牌候选。
- **缺门约束**:候选复用 `engine.action.legal_discards(view)`(有缺门牌时只列缺门牌),推荐绝不会建议打非缺门。

### 副露扩展(shanten/ukeire 镜像 win 的 melds)
- `melds>0`:标准形目标 = `(4-melds)` 面子 + 1 将对;差张下叫基线 `2*(4-melds)`;**七对路径禁用**。
- **暗手张数**:`14-3*melds`(刚摸态)/ `13-3*melds`(待摸态)。碰/杠均扣 3(杠后岭上补摸抵消第 4 张),`3*melds` 已验证正确(勿改"杠扣4")。
- 张数校验放宽:`melds=0` 时仍为 `{13,14}`,原 12/16 张报错用例继续生效(全部回归绿)。

### 评分模型(粗算,权重可调,v0 标注)
- **可见/未见张**:`visible = 自家暗手 + 全部副露 + 全部弃牌`;`remaining = 4 - visible = 牌墙 + 他家暗手`。恒等 `sum(visible)+sum(remaining)==108`。
- **安全度 `safety_of(tile, view)`**(0 安全 / 100 极险):
  - 未见0 → 绝对安全;对手缺门牌对该对手 → 0;壁(绝张墙,§6.3 定义)削弱危险度。
  - 软信号:筋 ×0.7、现物 ×0.8(**川麻无振听,现物非硬安全**,remaining>0 时危险仍 >0)、早巡 ×0.7 / 晚巡 ×1.2。
  - 逐对手取最危险者(max);`defense_score = 100 - danger`;附川麻理由 + 逐对手明细。
- **对手威胁度 v0** `opponent_threat`(0..1,软权重):副露数 +0.15/副(≤0.6)+ 缺门已清 +0.2 + 晚巡 +0.2,经 `0.5+0.5*threat` 调节危险度。
- **进攻期望 `offense_of`**:`score = base[差张下叫](0→50/1→25/2→12/3→5)+ 3*活进张数 + 活进张未见张和`;已胡→100;死待(remaining0)不计;clamp 0..100。
- **综合 + 权重回传**:`composite = w_off*offense + w_def*defense`,默认 `0.6/0.4`(经 `analyze(view, weights=...)` 可调,`weights_used` 回传实际权重)。
- **claim 段**(13 张、有 last_discard):`can_ron = win(hand+last, lack, melds)`;`can_pon`(排除缺门);`pon_shanten_after = shanten(碰后暗手, lack, melds+1)`(走刚摸态路径)。

### Phase 3 CLI demo

```bash
# 14 张(刚摸态):输出弃牌候选与推荐
python -m majiang_coach.demo_analyze 1m2m3m 4m5m6m 7m8m9m 1s2s3s 5s5s --lack p

# 13 张(待摸态):输出 hand + claim
python -m majiang_coach.demo_analyze 1m2m3m 4m5m6m 7m8m9m 5s5s 3m4m --lack p --last-discard 5m

# 副露(已碰 5m):--pon 5m
python -m majiang_coach.demo_analyze 1m2m3m 4m5m6m 7m8m9m 5s5s --lack p --pon 5m

# 输出完整 JSON
python -m majiang_coach.demo_analyze 1m2m3m 4m5m6m 7m8m9m 1s2s3s 5s5s --lack p --json
```

### Phase 3 API demo

```bash
curl -X POST http://127.0.0.1:8000/api/phase3/analyze \
  -H "Content-Type: application/json" \
  -d '{"codes":["1m2m3m","4m5m6m","7m8m9m","1s2s3s","5s5s"],"lack_suit":"p"}'
```

响应(具名数字字段,供 Phase 4 LLM 强制引用防幻觉):
```jsonc
{
  "seat":0,"hand_total":14,"lack_suit":2,"melds":[],
  "weights_used":{"offense":0.6,"defense":0.4},
  "hand":{"score":..,"shanten":..,"is_tenpai":..,"ukeire":[{"tile_index":..,"code":"5m","remaining":2,"new_shanten":0}],"ukeire_count":..,"ukeire_remaining_total":..},
  "candidates":[{"tile":..,"code":"5p","shanten_after":..,"is_tenpai_after":..,"ukeire":[..],"ukeire_count":..,"ukeire_remaining_total":..,"offense_score":..,"danger":..,"defense_score":..,"composite_score":..,"safety_reasons":["对家缺筒,对其绝对安全"],"per_opponent":[{"seat":1,"danger":0,"lack":2,"threat":0.4,"reasons":[..]}]}],
  "recommend":{"tile":..,"code":"..","composite_score":..},
  "best_offense":{"tile":..},"best_defense":{"tile":..},
  "claim": null
}
```
- `to_dict`/`from_dict` 往返一致;`analyze` 纯函数确定性。

## 与 Phase 4 的衔接

- Phase 3 扩展了 `shanten`/`ukeire` 的 `melds` 参数(镜像 Phase 2 的 `win`),`melds=0` 严格回归。
- `analyze(view)` 纯函数、核心零依赖;`PlayerView` 加 `lack_suits`(4 座公开缺门,默认 `()` 向后兼容)。
- Actor 协议为 Phase 4(LLM 教练,强制引用 Phase 3 数字防幻觉)、Phase 5(启发式 AI 按 `composite_score` 选牌)、Phase 6(复盘 `make_view`→`analyze` 点评)预留同一接口。

## API 语义说明

- **`shanten`**:
  - 14 张:`-1` 已胡,否则 = 弃一张后最优 13 张向听数的最小值。
  - 13 张:`0` 听牌,`>=1` 向听。
- **`ukeire`**:仅 13 张返回非空。听牌→待ち牌(摸入即胡);向听≥1→改进牌(摸入降向听)。
- **缺一门**:`lack_suit` 留空时自动枚举三门取最小向听(玩家选最优缺门)。
- **龙七对**:杠(count==4)在七对形中计为两对,Phase 1 不识别番名。

## 进度

### Phase 1:核心算法
- [x] tiles.py(索引/码/emoji 互转)
- [x] hand.py(不可变 Hand)
- [x] decompose.py(面子/搭子分解,Pareto 剪枝)
- [x] win.py(标准形 + 七对 + 龙七对 + 缺一门)
- [x] shanten.py(13/14 语义,缺门禁占位)
- [x] ukeire.py(听牌待ち / 向听改进牌)
- [x] demo.py(CLI) + api/main.py(FastAPI)

### Phase 2:血战到底状态机
- [x] engine/wall.py(种子洗牌/发牌/杠尾/流局)
- [x] win.py 扩展 melds 参数(副露胡牌,向后兼容)
- [x] engine/melds.py + view.py(副露数据类 + 信息隔离视角)
- [x] engine/action.py(合法动作:缺门优先/碰/杠/胡)
- [x] engine/rules.py(ron>碰/杠、一炮多响、抢杠)
- [x] engine/state.py(GameState 完整状态)
- [x] engine/game.py(主循环 + Actor + RandomActor 能胡必胡)
- [x] engine/record.py(JSON 事件流 + replay 复现)
- [x] engine/settlement.py(结算桩:记胡牌事实/花猪,不算番)
- [x] demo_game.py(CLI) + api/main.py POST /api/phase2/play

**Phase 2 完成。** 测试全绿(Phase 1 + Phase 2 新增)。

### Phase 3:Analysis Engine(硬计算结构化输出)
- [x] shanten.py / ukeire.py 扩展 melds 参数(副露向听/进张,`melds=0` 严格回归)
- [x] PlayerView.lack_suits + make_view(4 座公开缺门,默认 `()` 向后兼容)
- [x] analysis/visible.py(visible/remaining,sum==108)
- [x] analysis/threat.py(opponent_threat v0 软权重)
- [x] analysis/safety.py(安全度:未见0/缺门/壁/现物非硬/巡目,逐对手明细)
- [x] analysis/offense.py(进张期望:差张下叫+活进张+未见,死待不计)
- [x] analysis/recommend.py(analyze:逐候选+综合排序+推荐+claim,缺门约束,weights_used 回传)
- [x] analysis/result.py(to_dict/from_dict 往返)
- [x] demo_analyze.py(CLI) + api/main.py POST /api/phase3/analyze
- [x] README Phase 3 文档

**Phase 3 完成。** 测试全绿(Phase 1+2 + Phase 3 新增)。等待确认后进 Phase 4(可插拔 LLM 助手 + 提示开关,强制引用 Phase 3 数字)。
