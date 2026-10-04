"""来源清单的离线测试，不依赖网络。"""

from src.build_feed import load_sources
from src.collectors import COLLECTORS


def test_sources_loadable_and_valid():
    sources = load_sources("sources.yaml")
    assert len(sources) > 10
    for src in sources:
        assert src["id"] and src["name"] and src["url"]
        assert src["category"] in ("lab", "paper", "cn-media")
        assert src["type"] in COLLECTORS


def test_source_ids_unique():
    ids = [s["id"] for s in load_sources("sources.yaml")]
    assert len(ids) == len(set(ids))