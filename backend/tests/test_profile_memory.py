from __future__ import annotations

from app.agent.profile_memory import ProfilePatch, heuristic_extract, merge_profile
from app.agent.graph import run_turn
from app.domain.models import InvestorProfile, Position


def test_merge_profile_unions_lists():
    base = InvestorProfile(circle_of_competence=["消费"], taboos=["杠杆"])
    patch = ProfilePatch(
        goals="长期复利",
        circle_of_competence=["白酒"],
        taboos=["杠杆"],
        changed_fields=["goals", "circle_of_competence", "taboos"],
    )
    merged, changed = merge_profile(base, patch)
    assert merged.goals == "长期复利"
    assert merged.circle_of_competence == ["消费", "白酒"]
    assert merged.taboos == ["杠杆"]
    assert "goals" in changed


def test_merge_positions_upsert():
    base = InvestorProfile(positions=[Position(symbol="600519", weight_pct=5)])
    patch = ProfilePatch(
        positions=[Position(symbol="600519", weight_pct=10), Position(symbol="AAPL")],
        changed_fields=["positions"],
    )
    merged, _ = merge_profile(base, patch)
    by = {p.symbol: p for p in merged.positions}
    assert by["600519"].weight_pct == 10
    assert "AAPL" in by


def test_heuristic_extract_profile_cues():
    msg = (
        "资产增值财富自由；时间范围无限期；风险承受不会失眠；"
        "能力圈：消费、白酒、简单商业模式"
    )
    patch = heuristic_extract(msg)
    assert patch.goals or patch.horizon or patch.circle_of_competence
    assert patch.circle_of_competence
    assert "白酒" in patch.circle_of_competence


def test_merge_life_finance():
    from app.agent.profile_memory import LifePatch, ProfilePatch, merge_profile
    from app.domain.models import InvestorProfile

    base = InvestorProfile()
    patch = ProfilePatch(
        life=LifePatch(income_monthly="月入3万", cash_buffer="应急金20万"),
        changed_fields=["life.income_monthly", "life.cash_buffer"],
    )
    merged, changed = merge_profile(base, patch)
    assert merged.life.income_monthly == "月入3万"
    assert "life.cash_buffer" in changed


def test_session_persist_and_resume(store):
    from app.domain.models import ChatMessage

    s = store.create_session(title="测试")
    store.append_messages(
        s.id,
        [
            ChatMessage(role="user", content="你好"),
            ChatMessage(role="assistant", content="你好，我是导师"),
        ],
    )
    loaded = store.get_or_create_current_session()
    assert loaded.id == s.id
    assert len(loaded.messages) == 2
    assert loaded.as_history_dicts()[0]["content"] == "你好"


def test_run_turn_persists_profile(store):
    msg = (
        "我的目标是资产增值和财富自由；期限可以无限期；"
        "风险上不会失眠只要能理解；能力圈是消费和白酒"
    )
    resp = run_turn(msg, store=store)
    assert resp.mode == "broad"
    assert resp.profile_updates
    saved = store.get_profile()
    assert saved.circle_of_competence
    assert "白酒" in saved.circle_of_competence or "消费" in saved.circle_of_competence
