#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
抓取 TWSE 日交易資料（JSON 版本），整併成過去 N 年的 Date,Close CSV
預設抓 0050、00830 近 10 年。自動處理中文欄位、民國年、SSL fallback。
"""

import time
import math
import argparse
from pathlib import Path
from typing import List, Dict, Any

import pandas as pd
import requests
import certifi
from requests.exceptions import SSLError

TWSE_URL = "https://www.twse.com.tw/exchangeReport/STOCK_DAY"
DEFAULT_SYMBOLS = ["0050", "00830", "00670L"]
LOOKBACK_YEARS = 10
RETRY = 3
SLEEP_SEC = 0.4  # 禮貌間隔
OUT_DIR = Path(__file__).resolve().parent

# ---------- 安全請求：先用 certifi 驗證，不行就臨時關閉驗證 ----------
def safe_get(url: str, **kwargs) -> requests.Response:
    headers = kwargs.pop("headers", {})
    headers.setdefault("User-Agent", "Mozilla/5.0")
    try:
        return requests.get(url, verify=certifi.where(), headers=headers, **kwargs)
    except SSLError:
        import warnings, urllib3
        warnings.filterwarnings("ignore")
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        return requests.get(url, verify=False, headers=headers, **kwargs)

# ---------- 產生月份清單 ----------
def month_list(last_years: int) -> List[str]:
    end = pd.Timestamp.today().normalize()
    start = end - pd.DateOffset(years=last_years)
    months = pd.date_range(start=start, end=end, freq="MS")
    return [f"{d.year}{d.month:02d}" for d in months]

# ---------- 解析 TWSE JSON 一個月 ----------
def fetch_month_json(stock_no: str, yyyymm: str) -> pd.DataFrame:
    params = {"response": "json", "date": f"{yyyymm}01", "stockNo": stock_no}
    last_err = None
    for _ in range(RETRY):
        try:
            r = safe_get(TWSE_URL, params=params, timeout=30)
            if r.status_code != 200:
                last_err = f"HTTP {r.status_code}"
                time.sleep(SLEEP_SEC)
                continue
            j = r.json()
            # 無資料 or 結構不同
            if "data" not in j or "fields" not in j or not j["data"]:
                return pd.DataFrame(columns=["Date", "Close"])

            fields: List[str] = j["fields"]
            data: List[List[Any]] = j["data"]

            # 找出欄位位置
            try:
                idx_date = fields.index("日期")
                idx_close = fields.index("收盤價")
            except ValueError:
                # 有時候欄位名變動，保底處理
                # 常見變化：收盤價含註記、或「成交筆數」移位，但日期與收盤價通常存在
                # 若找不到就回空
                return pd.DataFrame(columns=["Date", "Close"])

            rows = []
            for row in data:
                try:
                    roc = str(row[idx_date]).strip()        # 例如 114/08/07
                    y, m, d = roc.split("/")
                    y = int(y) + 1911
                    date_iso = f"{y}-{int(m):02d}-{int(d):02d}"

                    close_str = str(row[idx_close]).replace(",", "").strip()
                    # 去除可能的註記，例如 "124.50*" → 124.50
                    close_str = "".join(ch for ch in close_str if (ch.isdigit() or ch == "." or ch == "-"))
                    close_val = float(close_str)
                    rows.append((date_iso, close_val))
                except Exception:
                    # 忽略非交易日或異常行
                    continue

            if not rows:
                return pd.DataFrame(columns=["Date", "Close"])

            df = pd.DataFrame(rows, columns=["Date", "Close"])
            return df

        except (requests.RequestException, ValueError) as e:
            last_err = str(e)
            time.sleep(SLEEP_SEC)

    print(f"[WARN] {stock_no} {yyyymm} 下載失敗：{last_err}")
    return pd.DataFrame(columns=["Date", "Close"])

# ---------- 合併多月份 ----------
def fetch_range(stock_no: str, years: int) -> pd.DataFrame:
    frames = []
    for yyyymm in month_list(years):
        df_m = fetch_month_json(stock_no, yyyymm)
        if not df_m.empty:
            frames.append(df_m)
        time.sleep(SLEEP_SEC)
    if not frames:
        return pd.DataFrame(columns=["Date", "Close"])
    df = pd.concat(frames, ignore_index=True)
    df = df.drop_duplicates(subset=["Date"]).sort_values("Date").reset_index(drop=True)
    return df

# ---------- 進入點 ----------
def main(symbols: List[str], years: int):
    for sym in symbols:
        print(f"抓取 {sym} 近 {years} 年資料…")
        df = fetch_range(sym, years)
        if df.empty:
            print(f"[ERROR] {sym} 沒抓到資料（可能是上市未滿期間或網路被擋）")
            continue
        out = OUT_DIR / f"{sym}.csv"
        df.to_csv(out, index=False)
        print(f"完成：{out}（{len(df)} 筆）")

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Download TWSE daily close CSVs (Date,Close) via JSON API.")
    ap.add_argument("--symbols", nargs="*", default=DEFAULT_SYMBOLS, help="e.g. 0050 00830 00662")
    ap.add_argument("--years", type=int, default=LOOKBACK_YEARS, help="lookback years (default 10)")
    args = ap.parse_args()
    main(args.symbols, args.years)
