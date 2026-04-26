"""不動産物件調査ツール - Streamlit アプリケーション"""

import re
import datetime
import urllib.parse

import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd

# ---------------------------------------------------------------------------
# 定数
# ---------------------------------------------------------------------------
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

REQUEST_TIMEOUT = 15  # seconds


# ---------------------------------------------------------------------------
# スクレイピング関数
# ---------------------------------------------------------------------------
def search_lifull(address: str, property_name: str) -> list[dict]:
    """LIFULL HOME'S で物件情報を検索する。"""
    query = f"{address} {property_name}".strip()
    url = (
        "https://www.homes.co.jp/search/main/"
        f"?keyword={urllib.parse.quote(query)}"
    )
    results: list[dict] = []
    try:
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        # 検索結果からカード要素を取得
        cards = soup.select(".mod-mergeBuilding--card, .prg-building")
        for card in cards[:5]:
            title_el = card.select_one(
                ".prg-building-name a, .prg-buildingName a"
            )
            title = title_el.get_text(strip=True) if title_el else "不明"
            link = title_el["href"] if title_el and title_el.has_attr("href") else ""
            if link and not link.startswith("http"):
                link = "https://www.homes.co.jp" + link

            info_items = card.select(".prg-buildingInfoItem, .prg-building-spec dd")
            specs = [item.get_text(strip=True) for item in info_items]

            results.append({
                "ソース": "LIFULL HOME'S",
                "物件名": title,
                "詳細": " / ".join(specs) if specs else "詳細ページを参照",
                "URL": link,
            })
    except Exception as e:
        results.append({
            "ソース": "LIFULL HOME'S",
            "物件名": f"取得エラー: {e}",
            "詳細": "",
            "URL": url,
        })
    return results


def search_suumo(address: str, property_name: str) -> list[dict]:
    """SUUMO で物件情報を検索する。"""
    query = f"{address} {property_name}".strip()
    url = (
        "https://suumo.jp/jj/common/ichiran/JJ010FJ001/"
        f"?keyword={urllib.parse.quote(query)}"
    )
    results: list[dict] = []
    try:
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        cards = soup.select(".property_unit, .cassette_item")
        for card in cards[:5]:
            title_el = card.select_one(
                ".property_unit-title a, .cassette_item-title a"
            )
            title = title_el.get_text(strip=True) if title_el else "不明"
            link = title_el["href"] if title_el and title_el.has_attr("href") else ""
            if link and not link.startswith("http"):
                link = "https://suumo.jp" + link

            detail_els = card.select("td, .cassette_item-detail dd")
            specs = [el.get_text(strip=True) for el in detail_els[:6]]

            results.append({
                "ソース": "SUUMO",
                "物件名": title,
                "詳細": " / ".join(specs) if specs else "詳細ページを参照",
                "URL": link,
            })
    except Exception as e:
        results.append({
            "ソース": "SUUMO",
            "物件名": f"取得エラー: {e}",
            "詳細": "",
            "URL": url,
        })
    return results


# ---------------------------------------------------------------------------
# 物件スペック解析 (簡易)
# ---------------------------------------------------------------------------
def parse_property_specs(detail_text: str) -> dict:
    """詳細テキストから基本スペックを抽出する。"""
    specs = {
        "築年数": "不明",
        "構造": "不明",
        "間取り": "不明",
        "戸数": "不明",
    }

    # 築年数
    m = re.search(r"築(\d+)年", detail_text)
    if m:
        specs["築年数"] = f"築{m.group(1)}年"
    m2 = re.search(r"(\d{4})年築", detail_text)
    if m2:
        year_built = int(m2.group(1))
        age = datetime.date.today().year - year_built
        specs["築年数"] = f"築{age}年 ({m2.group(1)}年建築)"

    # 構造
    for structure in ["RC", "SRC", "鉄筋コンクリート", "鉄骨", "木造", "S造", "軽量鉄骨"]:
        if structure in detail_text:
            specs["構造"] = structure
            break

    # 間取り
    m = re.search(r"\d[LDKS]+", detail_text)
    if m:
        specs["間取り"] = m.group(0)

    # 戸数
    m = re.search(r"(\d+)\s*戸", detail_text)
    if m:
        specs["戸数"] = f"{m.group(1)}戸"

    return specs


# ---------------------------------------------------------------------------
# 地価データ (国土交通省 API)
# ---------------------------------------------------------------------------
def fetch_land_price(address: str) -> pd.DataFrame | None:
    """国土交通省の不動産取引価格情報APIから周辺地価を取得する。"""
    current_year = datetime.date.today().year
    # 直近5年分を対象
    from_period = f"{current_year - 5}1"
    to_period = f"{current_year}1"

    api_url = (
        "https://www.land.mlit.go.jp/webland/api/TradeListSearch"
        f"?from={from_period}&to={to_period}"
        f"&area=13"  # デフォルト: 東京都
        f"&station={urllib.parse.quote(address)}"
    )
    try:
        resp = requests.get(api_url, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") == "OK" and data.get("data"):
            records = []
            for item in data["data"][:20]:
                records.append({
                    "取引時期": item.get("Period", ""),
                    "所在地": item.get("Municipality", "") + item.get("DistrictName", ""),
                    "取引価格(万円)": (
                        int(item["TradePrice"]) // 10000
                        if item.get("TradePrice") else ""
                    ),
                    "面積(㎡)": item.get("Area", ""),
                    "用途": item.get("Use", ""),
                })
            return pd.DataFrame(records)
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# 利回り計算
# ---------------------------------------------------------------------------
def calc_yield_table(
    purchase_price: float,
    monthly_rent: float,
    units: int,
    vacancy_rate: float,
) -> dict:
    """表面利回り・実質利回り（概算）を計算する。"""
    annual_rent = monthly_rent * units * 12
    effective_rent = annual_rent * (1 - vacancy_rate / 100)

    gross_yield = (annual_rent / purchase_price * 100) if purchase_price else 0
    net_yield = (effective_rent / purchase_price * 100) if purchase_price else 0

    return {
        "年間賃料収入(満室)": f"¥{annual_rent:,.0f}",
        "想定空室率": f"{vacancy_rate:.1f}%",
        "年間賃料収入(実効)": f"¥{effective_rent:,.0f}",
        "取得価格": f"¥{purchase_price:,.0f}",
        "表面利回り": f"{gross_yield:.2f}%",
        "実質利回り(概算)": f"{net_yield:.2f}%",
    }


# ---------------------------------------------------------------------------
# Markdown レポート生成
# ---------------------------------------------------------------------------
def generate_report(
    address: str,
    property_name: str,
    search_results: list[dict],
    specs: dict | None,
    land_df: pd.DataFrame | None,
    yield_info: dict | None,
) -> str:
    """調査結果を Markdown 形式でまとめる。"""
    today = datetime.date.today().isoformat()
    lines = [
        f"# 不動産物件調査レポート",
        f"",
        f"- **調査日**: {today}",
        f"- **住所**: {address}",
        f"- **物件名**: {property_name}",
        f"",
        f"---",
        f"",
        f"## 1. ポータルサイト検索結果",
        f"",
    ]

    if search_results:
        lines.append("| ソース | 物件名 | 詳細 | URL |")
        lines.append("|--------|--------|------|-----|")
        for r in search_results:
            url_str = f"[リンク]({r['URL']})" if r["URL"] else "-"
            lines.append(
                f"| {r['ソース']} | {r['物件名']} | {r['詳細']} | {url_str} |"
            )
    else:
        lines.append("検索結果はありませんでした。")

    lines += ["", "## 2. 物件基本スペック", ""]
    if specs:
        lines.append("| 項目 | 値 |")
        lines.append("|------|-----|")
        for k, v in specs.items():
            lines.append(f"| {k} | {v} |")
    else:
        lines.append("スペック情報を取得できませんでした。")

    lines += ["", "## 3. 周辺地価データ", ""]
    if land_df is not None and not land_df.empty:
        lines.append(land_df.to_markdown(index=False))
    else:
        lines.append("地価データを取得できませんでした。")

    lines += ["", "## 4. 収益性概算", ""]
    if yield_info:
        lines.append("| 項目 | 値 |")
        lines.append("|------|-----|")
        for k, v in yield_info.items():
            lines.append(f"| {k} | {v} |")
    else:
        lines.append("収益性の計算は行われませんでした。")

    lines += [
        "",
        "---",
        f"*本レポートは自動生成されたものであり、投資判断の参考としてご利用ください。*",
        "",
    ]
    return "\n".join(lines)


# ===========================================================================
# Streamlit UI
# ===========================================================================
def main():
    st.set_page_config(page_title="不動産物件調査ツール", page_icon="🏠", layout="wide")
    st.title("🏠 不動産物件調査ツール")
    st.caption("住所・物件名から各種ポータルサイトの情報を収集し、収益性を概算します。")

    # --- サイドバー: 入力フォーム ---
    with st.sidebar:
        st.header("物件情報入力")
        address = st.text_input("住所", placeholder="例: 東京都渋谷区神南1丁目")
        property_name = st.text_input("物件名", placeholder="例: 渋谷マンション")

        st.divider()
        st.header("収益性パラメータ")
        purchase_price = st.number_input(
            "取得価格 (円)", min_value=0, value=100_000_000, step=1_000_000, format="%d"
        )
        monthly_rent = st.number_input(
            "月額賃料 (1戸あたり・円)", min_value=0, value=80_000, step=5_000, format="%d"
        )
        units = st.number_input("総戸数", min_value=1, value=10, step=1)
        vacancy_rate = st.slider("想定空室率 (%)", 0.0, 50.0, 5.0, 0.5)

        search_button = st.button("🔍 調査開始", use_container_width=True, type="primary")

    # --- セッション state 初期化 ---
    for key in ["search_results", "specs", "land_df", "yield_info", "report"]:
        if key not in st.session_state:
            st.session_state[key] = None

    # --- 調査実行 ---
    if search_button:
        if not address and not property_name:
            st.warning("住所または物件名を入力してください。")
            return

        # 1) ポータルサイト検索
        with st.spinner("ポータルサイトを検索中..."):
            results = []
            results.extend(search_lifull(address, property_name))
            results.extend(search_suumo(address, property_name))
            st.session_state["search_results"] = results

        # 2) スペック解析
        combined_details = " ".join(r.get("詳細", "") for r in results)
        st.session_state["specs"] = parse_property_specs(combined_details)

        # 3) 地価データ取得
        with st.spinner("地価データを取得中..."):
            st.session_state["land_df"] = fetch_land_price(address)

        # 4) 利回り計算
        st.session_state["yield_info"] = calc_yield_table(
            purchase_price, monthly_rent, units, vacancy_rate
        )

        # 5) レポート生成
        st.session_state["report"] = generate_report(
            address,
            property_name,
            st.session_state["search_results"],
            st.session_state["specs"],
            st.session_state["land_df"],
            st.session_state["yield_info"],
        )

    # --- 結果表示 ---
    if st.session_state["search_results"] is not None:
        st.header("📋 ポータルサイト検索結果")
        df_results = pd.DataFrame(st.session_state["search_results"])
        st.dataframe(df_results, use_container_width=True, hide_index=True)

    if st.session_state["specs"] is not None:
        st.header("🏗 物件基本スペック")
        spec_df = pd.DataFrame(
            [st.session_state["specs"]]
        ).T.reset_index()
        spec_df.columns = ["項目", "値"]
        st.table(spec_df)

    if st.session_state["land_df"] is not None:
        st.header("📈 周辺地価データ")
        if not st.session_state["land_df"].empty:
            st.dataframe(
                st.session_state["land_df"], use_container_width=True, hide_index=True
            )
        else:
            st.info("該当する地価データが見つかりませんでした。")

    if st.session_state["yield_info"] is not None:
        st.header("💰 収益性概算")
        yield_df = pd.DataFrame(
            list(st.session_state["yield_info"].items()),
            columns=["項目", "値"],
        )
        st.table(yield_df)

    if st.session_state["report"] is not None:
        st.header("📥 レポートダウンロード")
        st.download_button(
            label="Markdown レポートをダウンロード",
            data=st.session_state["report"],
            file_name=f"property_report_{datetime.date.today().isoformat()}.md",
            mime="text/markdown",
            use_container_width=True,
        )
        with st.expander("レポートプレビュー"):
            st.markdown(st.session_state["report"])


if __name__ == "__main__":
    main()
