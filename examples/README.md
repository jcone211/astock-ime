# examples/ —— 离线试跑用的最小数据

| 文件 | 说明 |
|---|---|
| `stock_names.sample.csv` | 35 行真实股票名（从 `stock_basic_cache` 挑的，特意包含 `*ST`、`TCL科技`、`万科A`、`重庆钢铁` 这类会踩坑的名字） |
| `astock.sample.txt` | 用上面这份 CSV 跑 `python build.py build` 得到的产物（`编码<TAB>词频<TAB>词语`） |

用途：

```bash
# 不连数据库，验证整条链路
python build.py all --source csv --csv examples/stock_names.sample.csv --no-imewl

# 对着样例看编码规则
column -t -s "$(printf '\t')" examples/astock.sample.txt | less
```

CI（`.github/workflows/build.yml`）用的就是这条离线通道。
