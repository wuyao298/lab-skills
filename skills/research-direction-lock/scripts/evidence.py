import argparse
import re

import pandas as pd

COLUMNS = ["re", "source_db", "title", "authors", "venue", "doctype",
           "is_review", "vol", "issue", "pages", "year", "month",
           "doi", "issn", "publisher", "subtitle", "abstract",
           "keywords", "citations", "eid", "url"]


def load(db_path):
    df = pd.read_csv(db_path, encoding="utf-8-sig", dtype=str)
    if len(df.columns) == len(COLUMNS):
        df.columns = COLUMNS
    return df


def search(df, keywords, limit):
    text = (df["title"].fillna("") + " " + df["abstract"].fillna("") + " " +
            df["keywords"].fillna(""))
    for kw in keywords:
        mask = text.str.contains(re.compile(kw, re.IGNORECASE))
        hits = df[mask]
        print(f"\n=== {kw} : {len(hits)} hits ===")
        for _, r in hits.head(limit).iterrows():
            print(f"{r['re']} | {r['year']} | {r['is_review']} | {r['venue']} | {r['title'][:80]}")


def main():
    parser = argparse.ArgumentParser(description="文献库关键词检索：验证 RE 锚点")
    parser.add_argument("keywords", nargs="+", help="关键词（正则，忽略大小写）")
    parser.add_argument("--db", default="reports/literature_db.csv",
                        help="文献库 CSV 路径（默认 reports/literature_db.csv）")
    parser.add_argument("--limit", type=int, default=12,
                        help="每关键词最多展示条数（默认 12）")
    args = parser.parse_args()

    df = load(args.db)
    search(df, args.keywords, args.limit)


if __name__ == "__main__":
    main()
