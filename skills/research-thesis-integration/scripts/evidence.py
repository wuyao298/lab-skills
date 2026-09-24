#!/usr/bin/env python3
"""方向证据 CSV 检索：RE 锚点库内实测（段8 论文故事整合用）。

用法：
  # 关键词检索（标题+摘要+作者关键词，正则，忽略大小写）
  python evidence.py <关键词...> --db directions/<slug>/search/evidence.csv
  # 编号检索（逐个实测是否命中库内，打印元数据行）
  python evidence.py --re RE003 RE033 RE206 --db directions/<slug>/search/evidence.csv

兼容 21 列建库 CSV 与 23 列方向证据 CSV（编号/标题/摘要/作者关键词/来源名称/出版年/是否综述 列名相同）。
"""

import argparse
import re

import pandas as pd

EN_COLUMNS = ["re", "source_db", "title", "authors", "venue", "doctype",
              "is_review", "vol", "issue", "pages", "year", "month",
              "doi", "issn", "publisher", "subtitle", "abstract",
              "keywords", "citations", "eid", "url"]


def load(db_path):
    df = pd.read_csv(db_path, encoding="utf-8-sig", dtype=str)
    if len(df.columns) == len(EN_COLUMNS):
        df.columns = EN_COLUMNS
    return df


def col(df, *names):
    for n in names:
        if n in df.columns:
            return df[n]
    return None


def re_num(df, i):
    c = col(df, "编号", "re")
    if c is None:
        return ""
    return re.sub(r"[^0-9]", "", str(c.iloc[i]))


def fmt_row(df, i):
    def cell(*names):
        c = col(df, *names)
        if c is None:
            c = pd.Series([""] * len(df))
        return str(c.iloc[i]).strip()

    return (f"[RE{re_num(df, i)}] | {cell('出版年', 'year')} | {cell('是否综述', 'is_review')} | "
            f"{cell('来源名称', 'venue')} | {cell('标题', 'title')[:80]}")


def search(df, keywords, limit):
    title = col(df, "标题", "title")
    abstract = col(df, "摘要", "abstract")
    keywords_col = col(df, "作者关键词", "keywords")
    parts = [c.fillna("") if c is not None else pd.Series([""] * len(df))
             for c in (title, abstract, keywords_col)]
    text = parts[0] + " " + parts[1] + " " + parts[2]
    for kw in keywords:
        mask = text.str.contains(re.compile(kw, re.IGNORECASE), regex=True)
        hits = df[mask]
        print(f"\n=== {kw} : {len(hits)} hits ===")
        for i in hits.head(limit).index:
            print(fmt_row(df, i))


def lookup(df, re_ids, limit=12):
    rids = [re_num(df, i) for i in range(len(df))]
    for rid in re_ids:
        idxs = [i for i, r in enumerate(rids) if r == rid]
        print(f"\n=== [RE{rid}] : {len(idxs)} hits ===")
        for i in idxs[:limit]:
            print(fmt_row(df, i))
        if not idxs:
            print("（未命中——禁止引用，请改引库内编号）")


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    parser = argparse.ArgumentParser(description="方向证据 CSV 关键词/编号检索：RE 锚点实测")
    parser.add_argument("keywords", nargs="*", help="关键词（正则，忽略大小写）")
    parser.add_argument("--re", nargs="+", dest="re_ids", default=None,
                        help="RE 编号（如 RE003），逐个实测命中")
    parser.add_argument("--db", default="reports/literature_db.csv",
                        help="CSV 路径（段8 用 directions/<slug>/search/evidence.csv）")
    parser.add_argument("--limit", type=int, default=12,
                        help="每关键词/编号最多展示条数（默认 12）")
    args = parser.parse_args()

    df = load(args.db)
    if args.re_ids:
        lookup(df, [re.sub(r"[^0-9]", "", r) for r in args.re_ids], args.limit)
    elif args.keywords:
        search(df, args.keywords, args.limit)
    else:
        parser.error("需提供关键词或 --re 编号")


if __name__ == "__main__":
    main()
