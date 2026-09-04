# dist/ —— 词库产物目录

这里的东西由 `python build.py all`（或一条 `python build.py release`）生成，
**默认不进 git**（只留 `.gitkeep` 和本说明），产物以 **GitHub Release** 的形式发出去。

## 每周 Release 的打包物

`python build.py release` 会在这里额外生成 `astock-ime-vYYYY.MM.DD.zip`，结构：

```text
astock-ime-v2026.09.04/
├── README-导入说明.txt        ← 普通人看这一份就够
├── ms_pinyin_astock.dat       ← 微软拼音（用户自定义短语）
├── custom_phrase_astock.txt   ← 搜狗（内容替换 PhraseEdit.txt）
├── ...                        ← 旧版微软拼音 .xml、Rime 等备用格式
└── meta/                      ← manifest、转换/回读报告、完整导入指南
```

## 单个文件用途

| 文件 | 给谁用 |
|---|---|
| `ms_pinyin_astock.dat` | Win10/11 微软拼音 · 用户自定义短语（导入即用） |
| `ms_pinyin_astock.xml` | 旧版微软拼音 / 必应拼音 |
| `custom_phrase_astock.txt` | 搜狗 · 设置 → 输入 → 自定义短语 → 直接编辑配置文件，用本文件内容整体替换 `PhraseEdit.txt`（行格式 `编码,词频=词语`） |
| `astock_rime.yaml` | Rime 中州韵（小狼毫 / 鼠须管） |
| `conversion_report.json` | 上一次深蓝转换 + 回读校验的详细结果（排障用） |

格式细节见 [../docs/formats.md](../docs/formats.md)，导入步骤见 [../docs/import-guide.md](../docs/import-guide.md)，
发布流程见 [../docs/automation.md](../docs/automation.md)。
