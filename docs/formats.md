# 词库格式与产物说明

本文档里的每一段样例，都是用当前代码在你这台机器上真实跑出来的（数据源：本地 PostgreSQL 的 `stock_basic_cache`，5552 只在市股票）。

## 1. 中间产物 `build/`

### `build/astock.txt` —— 全流程的母本
行格式：`编码 <TAB> 词频 <TAB> 词语`，UTF-8 无 BOM，LF。

```text
aajg	1	艾艾精工
stbg	1	*ST八钢
stbg	1	ST八钢
wka	1	万科A
```

注意 `stbg` 有两条：一条上屏官方名称 `*ST八钢`，一条上屏去掉星号的 `ST八钢`。
原因见 [第 4 节](#4-为什么st-股票要放两条)。

### `build/astock_imewl.txt` —— 给深蓝的词面清洗版
和 `astock.txt` 同格式，但把所有「以符号开头」的词面清洗掉前导符号（`*ST美丽` → `ST美丽`），
避免深蓝把它们整批丢弃。**不要**手改这个文件，改规则请动 `src/astock_ime/phrase.py: imewl_safe()`。

---

## 2. 交付产物 `dist/`

| 文件 | 目标输入法 | 行格式 | 编码 | 需要深蓝 | 回读校验 |
|---|---|---|---|---|---|
| `ms_pinyin_astock.dat` | Win10/11 微软拼音（用户自定义短语） | 二进制 `mschxudp` | - | ✅ | 5552/5552 ✅ |
| `ms_pinyin_astock.xml` | 旧版微软拼音 / 必应拼音词库 | XML `dctx` | UTF-8 BOM | ✅ | 5552/5552 ✅ |
| `custom_phrase_astock.txt` | 搜狗 · 自定义短语（内容直接替换 `PhraseEdit.txt`） | `编码,词频=词语` | UTF-8 BOM | ❌（自带） | - |
| `astock_rime.yaml` | Rime 中州韵（小狼毫/鼠须管，附赠） | Rime table_txt | UTF-8 | ❌（自带） | - |

样例（各取前三行）：

```text
# custom_phrase_astock.txt   （搜狗：内容整体替换 PhraseEdit.txt）
aajg,1=艾艾精工
abhw,1=安邦护卫
abl,1=艾布鲁

# astock_rime.yaml
---
name: astock
version: "2026.0904.2149"
sort: by_weight
use_preset_vocabulary: false
columns:
  - text
  - code
  - weight
...
艾艾精工	aajg	1
```

---

## 3. 编码规则（本项目最关键的部分）

| 股票名称 | 旧流程编码 | 本项目编码 | 说明 |
|---|---|---|---|
| `平安银行` | `payh` | `payh` | 汉字取拼音首字母 |
| `万科A` | `wkA` ⚠️ | `wka` | **大写字母转小写**，和输入习惯一致 |
| `深振业A` | `szyA` ⚠️ | `szya` | 同上 |
| `*ST美丽` | `*STml` ⚠️ | `stml` | **去掉 `*`**；旧编码会被深蓝判为非法并静默丢弃 |
| `TCL科技` | `TCLkj` ⚠️ | `tclkj` | 字母段整体小写 |
| `长江电力` | `cjdl` | `cjdl` | 整词注音，`长` 按 chang 取 `c` |
| `重庆钢铁` | `cqgt` | `cqgt` | 整词注音，`重` 按 chong 取 `c`（不是 `zggt`） |
| `三六零` | `sll` | `sll` | 零 = líng → `l`，不是 `z`（拼音事实，别当 bug 提） |

规则实现见 `src/astock_ime/pinyin.py`，逐条有单元测试覆盖（`tests/test_pinyin.py`）：

1. 先剔除星号 `*` `＊` `∗` `✱` `✳` `❋`；
2. 只保留汉字、ASCII 字母、数字参与编码，空格/括号/间隔号/标点直接忽略；
3. 交给 `pypinyin` 以**整词**方式取「拼音首字母」（多音字按词组读法），逐字取会出错；
4. 结果统一 `lower()`，最后校验：`^[a-z0-9]{2,16}$`，不合格就丢弃并计入 `bad_key`。

已知取舍：多音字只取一个读音。像 `单`（shàn/dān）、`行`（háng/xíng）这类姓氏/名字里的生僻读法，
可能和你的直觉不一致；撞码/漏码时可以按 `--limit`、`--exclude-st` 收缩词库，或者自己按需在 `dist/` 里加行。

---

## 4. 为什么 ST 股票要放两条

实测（深蓝词库转换 3.4，命令行版）：

```text
输入 8 条：其中 1 条词面是 *ST美丽
转换完成: 导入 8 条, 过滤 1 条, 导出 7 条
```

只要**词面以标点符号开头**（`*`、`＊`、`（` …），深蓝就在导入阶段把它过滤掉，且只在那行小字里出现「过滤 1 条」，
很容易一路无感。5552 只股票里有 **95 只 `*ST` 风险警示股**，旧流程等于把这一整类股票从词库里删掉了。

处理方式：

* 交给深蓝的原生格式（`.dat` / `.xml`）→ 用清洗过词面的 `astock_imewl.txt`，保证 95 只全进得去，上屏形态是 `ST美丽`；
* 我们自己写的文本词库 → 同时写两条：`*ST美丽`（官方名称，能导入就用它）+ `ST美丽`（保底）。

### 新旧产物对比（都是回读实测，不是估算）

```bash
# 旧流程产物（上一版 astock.dat，和本仓库同目录）
ImeWlConverterCmd.exe ../astock.dat -i win10mspy -o rime -O dump.txt
```

| | 旧 `astock.dat` | 新 `ms_pinyin_astock.dat` |
|---|---|---|
| 条目数 | **5444** | **5552** |
| 词面以 `*` 开头的条目 | 0（全被过滤） | 95（以 `STxx` 形式保留） |
| 带大写字母的编码 | 146 | 0 |
| 回读校验 | 无此环节 | `[verify] 回读 5552/5552 OK` |

---

## 5. 关于 `.scel`（搜狗细胞词库）

深蓝 3.4 的 scel **导出**功能实测不可用：不管输入多少条，产物都是固定 9768 字节的表头，回读只剩 2 条。

```text
[imewl] scel -> astock.scel   OK  导入 5552 / 过滤 0 / 导出 5552   ← 看起来一切正常
[verify] astock.scel          回读 2/5552 LOSS                      ← 实际是空的
```

所以默认 **不导 scel**（见 `src/astock_ime/imewl.py: TARGETS` 里 `default: False`）。
想用 `--targets scel` 强行导也可以，但请先跑一次 `all` 看 `[verify]` 那行的回读条数。
搜狗也不需要细胞词库：走「自定义短语」→ 用 `custom_phrase_astock.txt` 替换 `PhraseEdit.txt` 就行。

> 教训就是 `verify` 这一步的由来：**任何"转换完成"都不作数，回读条数对上才算数。**
