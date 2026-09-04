# dist/ —— 词库产物目录

这里的东西由 `python build.py all`（或一条 `python build.py release`）生成，
**默认不进 git**（只留 `.gitkeep` 和本说明），产物以 **GitHub Release** 的形式发出去。

## 每周 Release 的打包物

`python build.py release` 会在这里额外生成 `astock-ime-vYYYY.MM.DD.zip`，结构：

```text
astock-ime-v2026.09.04/
├── README-导入说明.txt        ← 普通人看这一份就够
├── ms_pinyin_astock.dat       ← 微软拼音
├── wechat_astock_words.txt    ← 微信输入法
├── sogou_astock.txt           ← 搜狗（GBK）
├── ...                        ← 其余备用格式
└── meta/                      ← manifest、转换/回读报告、完整导入指南
```

## 单个文件用途

| 文件 | 给谁用 |
|---|---|
| `ms_pinyin_astock.dat` | Win10/11 微软拼音 · 用户自定义短语（导入即用） |
| `ms_pinyin_astock.xml` | 旧版微软拼音 / 必应拼音 |
| `sogou_astock.txt` | 搜狗拼音 · 文本词库导入（**GBK**，别另存为 UTF-8） |
| `wechat_astock_words.txt` | 微信输入法 · 导入本地词库（纯词表） |
| `wechat_astock_code.txt` | 微信输入法 · 需要「词+编码」两列时用 |
| `custom_phrase_astock.txt` | 通用「自定义短语」批量文件（`编码,词频=词语`） |
| `custom_phrase_astock_alt.txt` | 同上，另一种写法（`编码;词频,词语`） |
| `astock_rime.yaml` | Rime 中州韵（小狼毫 / 鼠须管） |
| `conversion_report.json` | 上一次深蓝转换 + 回读校验的详细结果（排障用） |

格式细节见 [../docs/formats.md](../docs/formats.md)，导入步骤见 [../docs/import-guide.md](../docs/import-guide.md)，
发布流程见 [../docs/automation.md](../docs/automation.md)。
