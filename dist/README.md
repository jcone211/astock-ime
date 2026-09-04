# dist/ —— 词库产物目录

这里的东西是 `python build.py all` 生成的，**默认不进 git**（只留本说明）。
想看每个文件的行格式和验证结论，读 [../docs/formats.md](../docs/formats.md)；
想看导入步骤，读 [../docs/import-guide.md](../docs/import-guide.md)。

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
| `conversion_report.json` | 上一次深蓝转换 + 回读校验的详细结果 |

要发给别人 / 存档，就把这个目录打包成 Release 附件：

```bash
python build.py all && zip -r astock-ime-$(date +%Y%m%d).zip dist/
```
