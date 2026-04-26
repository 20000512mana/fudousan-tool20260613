# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## プロジェクト概要

Streamlit ベースの不動産物件調査ツール。住所・物件名を入力し、ポータルサイト（LIFULL HOME'S / SUUMO）からスクレイピングで情報を収集、周辺地価・収益性を概算表示し、Markdown レポートとしてダウンロードできる。

## コマンド

```bash
pip install -r requirements.txt    # 依存パッケージのインストール
streamlit run app.py               # アプリ起動 (デフォルト: localhost:8501)
```

## アーキテクチャ

単一ファイル構成（`app.py`）。主要な処理ブロック:

1. **スクレイピング** (`search_lifull`, `search_suumo`) — ポータルサイトへ requests + BeautifulSoup でアクセスし物件情報を取得
2. **スペック解析** (`parse_property_specs`) — 取得テキストから正規表現で築年数・構造・間取り・戸数を抽出
3. **地価データ** (`fetch_land_price`) — 国土交通省 不動産取引価格情報API を利用
4. **利回り計算** (`calc_yield_table`) — 表面利回り・実質利回りの概算
5. **レポート生成** (`generate_report`) — 全結果を Markdown 形式に変換
6. **UI** (`main`) — Streamlit のサイドバー入力 + メイン領域に結果表示

状態管理は `st.session_state` で行い、調査結果はセッション内で保持される。

## コーディング規約

- ファイル名は `YYYYMMDD_ファイル名` の形式にする
- 出力・コメントは日本語
- 説明は結論ファースト、論理的に階層・粒度を分けて記述
- 端的に話す
