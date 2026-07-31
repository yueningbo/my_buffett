from __future__ import annotations

from app.tools import cn_a_share, contracts, live_data


def test_cn_secid_and_codes():
    assert cn_a_share.em_secid("600519") == "1.600519"
    assert cn_a_share.em_secid("000858") == "0.000858"
    assert cn_a_share.em_market_code("600519") == "SH600519"
    assert cn_a_share.sina_list_code("000858") == "sz000858"
    assert cn_a_share.is_cn_a_share("600519")
    assert not cn_a_share.is_cn_a_share("AAPL")


def test_hk_normalize():
    assert cn_a_share.normalize_hk_symbol("00700") == "00700"
    assert cn_a_share.normalize_hk_symbol("0700.HK") == "00700"
    assert cn_a_share.normalize_hk_symbol("HK00700") == "00700"
    assert cn_a_share.hk_secid("00700") == "116.00700"
    assert cn_a_share.is_hk_share("00700")
    assert not cn_a_share.is_hk_share("600519")


def test_cn_live_path_used_for_a_shares(monkeypatch):
    monkeypatch.setenv("MY_BUFFETT_TOOL_MODE", "auto")
    live_data._CACHE.clear()

    def fake_cn(symbol: str):
        return {
            "symbol": symbol,
            "name": "贵州茅台",
            "industry": "白酒",
            "business": "白酒生产销售",
            "currency": "CNY",
            "last_price": 1350.6,
            "pe_ttm": 15.49,
            "roe_pct": 32.53,
            "gross_margin_pct": 91.18,
            "provider": "eastmoney",
        }

    monkeypatch.setattr(live_data, "fetch_cn_bundle", fake_cn)
    tr = contracts.get_quote("600519")
    assert tr.numbers[0].source.startswith("eastmoney")
    assert tr.numbers[0].value == 1350.6
    fin = contracts.get_financials_snapshot("600519")
    assert any(n.key == "roe_pct" and n.value == 32.53 for n in fin.numbers)


def test_hk_live_path(monkeypatch):
    monkeypatch.setenv("MY_BUFFETT_TOOL_MODE", "auto")
    live_data._CACHE.clear()

    def fake_hk(symbol: str):
        return {
            "symbol": symbol,
            "name": "腾讯控股",
            "industry": "主板",
            "business": "互联网",
            "currency": "HKD",
            "last_price": 474.2,
            "pe_ttm": 16.4,
            "roe_pct": 21.13,
            "gross_margin_pct": 56.21,
            "provider": "eastmoney",
            "market": "HK",
        }

    monkeypatch.setattr(live_data, "fetch_hk_bundle", fake_hk)
    tr = contracts.get_quote("00700.HK")
    assert tr.raw["provider"] == "eastmoney"
    assert tr.numbers[0].unit == "HKD"
    assert tr.numbers[0].value == 474.2
