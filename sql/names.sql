-- astock-ime 默认取数 SQL（模板，实际由 src/astock_ime/db.py 按 config.json 拼装）
-- 数据源：本地 PostgreSQL 的 stock_basic_cache 表，由同步任务每周三 / 周五全量刷新。
-- 本工具只读不写，也不会去调 Tushare 接口（接口限额很紧，一天可能就 1 次）。

SELECT ts_code,
       name,
       industry
  FROM stock_basic_cache
 WHERE name IS NOT NULL
   AND btrim(name) <> ''
   AND COALESCE(dead_tag, 0) = 0          -- 剔除已退市（dead_tag 列没有时删掉这行）
 ORDER BY ts_code;

-- 只想看有没有 *ST 之类的风险警示股：
--   SELECT name FROM stock_basic_cache WHERE name LIKE '%*%';
--
-- 想按热度加权（--freq hot）时会额外查行情表，取近 N 个交易日成交额：
--   WITH recent AS (
--     SELECT code AS ts_code, sum(amount) AS amount
--       FROM a_share_daily
--      WHERE date >= (SELECT max(date) - 40 FROM a_share_daily)
--      GROUP BY code)
--   SELECT ts_code, amount FROM recent ORDER BY amount DESC NULLS LAST;
