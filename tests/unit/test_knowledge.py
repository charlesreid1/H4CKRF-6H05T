"""Tests for hackrf_agent.domain.knowledge (Phase 3 knowledge tier)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hackrf_agent.domain.knowledge import (
    KnowledgeError,
    KnowledgePaths,
    clear_cache,
    default_paths,
    list_topics,
    load_records,
    lookup_band,
    lookup_modulation,
    read_file,
    search,
    verify_claim,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def synthetic_corpus(tmp_path: Path) -> KnowledgePaths:
    """Build a minimal corpus in tmp_path for isolated tests."""
    root = tmp_path / "knowledge"
    (root / "records").mkdir(parents=True)
    (root / "dsp").mkdir()
    (root / "modulation").mkdir()
    (root / "MANIFEST.md").write_text("# manifest\n", encoding="utf-8")
    (root / "dsp" / "README.md").write_text(
        "# dsp\nManchester encoding basics live here.\n", encoding="utf-8"
    )
    (root / "dsp" / "reference.md").write_text(
        "# dsp reference\nSampling: Nyquist requires fs >= 2B.\n",
        encoding="utf-8",
    )
    (root / "modulation" / "README.md").write_text(
        "# modulation\nOOK is amplitude-shift keying with 2 levels.\n",
        encoding="utf-8",
    )
    (root / "records" / "bands.json").write_text(
        json.dumps(
            [
                {
                    "id": "band-test-ism",
                    "name": "Test ISM band",
                    "category": "band_allocation",
                    "citations": ["fake"],
                    "confidence": "primary",
                    "technical_body": {
                        "start_hz": 433_000_000,
                        "stop_hz": 435_000_000,
                    },
                    "blocked_tx": False,
                },
                {
                    "id": "band-test-blocked",
                    "name": "Test blocked band",
                    "category": "band_allocation",
                    "citations": ["fake"],
                    "confidence": "primary",
                    "technical_body": {
                        "start_hz": 1_087_000_000,
                        "stop_hz": 1_093_000_000,
                    },
                    "blocked_tx": True,
                },
            ]
        ),
        encoding="utf-8",
    )
    (root / "records" / "modulations.json").write_text(
        json.dumps(
            [
                {
                    "id": "modulation-test-ook",
                    "name": "On-Off Keying (test record)",
                    "aliases": ["OOK", "ASK-2"],
                    "category": "modulation_family",
                    "citations": ["fake"],
                    "confidence": "primary",
                    "technical_body": {"levels": 2},
                }
            ]
        ),
        encoding="utf-8",
    )
    return KnowledgePaths(root=root)


# ---------------------------------------------------------------------------
# KnowledgePaths — safety
# ---------------------------------------------------------------------------


class TestKnowledgePathsSafety:
    def test_topic_dir_rejects_traversal(self, synthetic_corpus: KnowledgePaths) -> None:
        with pytest.raises(KnowledgeError):
            synthetic_corpus.topic_dir("../etc")

    def test_topic_dir_rejects_uppercase(self, synthetic_corpus: KnowledgePaths) -> None:
        with pytest.raises(KnowledgeError):
            synthetic_corpus.topic_dir("DSP")

    def test_topic_dir_rejects_absolute(self, synthetic_corpus: KnowledgePaths) -> None:
        with pytest.raises(KnowledgeError):
            synthetic_corpus.topic_dir("/etc")

    def test_topic_file_rejects_traversal_in_name(
        self, synthetic_corpus: KnowledgePaths
    ) -> None:
        with pytest.raises(KnowledgeError):
            synthetic_corpus.topic_file("dsp", "../../../etc/passwd")

    def test_topic_dir_accepts_valid_slug(
        self, synthetic_corpus: KnowledgePaths
    ) -> None:
        p = synthetic_corpus.topic_dir("dsp")
        assert p.name == "dsp"


# ---------------------------------------------------------------------------
# list_topics
# ---------------------------------------------------------------------------


class TestListTopics:
    def test_returns_topics_and_files(self, synthetic_corpus: KnowledgePaths) -> None:
        topics = list_topics(synthetic_corpus)
        names = {t["topic"] for t in topics}
        assert "dsp" in names
        assert "modulation" in names
        # records/ is not surfaced as a topic
        assert "records" not in names

    def test_files_are_sorted(self, synthetic_corpus: KnowledgePaths) -> None:
        topics = list_topics(synthetic_corpus)
        for t in topics:
            assert t["files"] == sorted(t["files"])

    def test_only_md_files_listed(self, synthetic_corpus: KnowledgePaths) -> None:
        # Author a non-.md file and confirm it's skipped.
        (synthetic_corpus.root / "dsp" / "notes.txt").write_text("ignore me")
        topics = list_topics(synthetic_corpus)
        dsp = next(t for t in topics if t["topic"] == "dsp")
        assert "notes.txt" not in dsp["files"]
        assert "README.md" in dsp["files"]

    def test_hidden_dirs_skipped(self, synthetic_corpus: KnowledgePaths) -> None:
        (synthetic_corpus.root / ".git").mkdir()
        (synthetic_corpus.root / ".git" / "README.md").write_text("")
        topics = list_topics(synthetic_corpus)
        names = {t["topic"] for t in topics}
        assert ".git" not in names


# ---------------------------------------------------------------------------
# read_file
# ---------------------------------------------------------------------------


class TestReadFile:
    def test_returns_content(self, synthetic_corpus: KnowledgePaths) -> None:
        out = read_file(synthetic_corpus, "dsp", "README.md")
        assert out["topic"] == "dsp"
        assert out["name"] == "README.md"
        assert "Manchester" in out["content"]

    def test_rejects_non_md(self, synthetic_corpus: KnowledgePaths) -> None:
        (synthetic_corpus.root / "dsp" / "notes.txt").write_text("nope")
        with pytest.raises(KnowledgeError):
            read_file(synthetic_corpus, "dsp", "notes.txt")

    def test_rejects_missing_file(self, synthetic_corpus: KnowledgePaths) -> None:
        with pytest.raises(KnowledgeError):
            read_file(synthetic_corpus, "dsp", "nonexistent.md")

    def test_rejects_oversize_file(self, synthetic_corpus: KnowledgePaths) -> None:
        big = "x" * (1_048_577)  # 1 MB + 1 byte
        (synthetic_corpus.root / "dsp" / "big.md").write_text(big)
        with pytest.raises(KnowledgeError, match="too large"):
            read_file(synthetic_corpus, "dsp", "big.md")


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------


class TestSearch:
    def test_finds_case_insensitive(self, synthetic_corpus: KnowledgePaths) -> None:
        hits = search(synthetic_corpus, "MANCHESTER")
        assert any("dsp" == h["topic"] for h in hits)

    def test_max_results_caps(self, synthetic_corpus: KnowledgePaths) -> None:
        # 'dsp' appears in multiple files; cap at 1.
        hits = search(synthetic_corpus, "dsp", max_results=1)
        assert len(hits) == 1

    def test_empty_query_rejected(self, synthetic_corpus: KnowledgePaths) -> None:
        with pytest.raises(KnowledgeError):
            search(synthetic_corpus, "   ")


# ---------------------------------------------------------------------------
# load_records + lookup_band + lookup_modulation
# ---------------------------------------------------------------------------


class TestLookupBand:
    def test_hit_inside_range(self, synthetic_corpus: KnowledgePaths) -> None:
        hits = lookup_band(synthetic_corpus, 433_920_000)
        ids = [r["id"] for r in hits]
        assert "band-test-ism" in ids

    def test_boundary_inclusive_low(self, synthetic_corpus: KnowledgePaths) -> None:
        hits = lookup_band(synthetic_corpus, 433_000_000)
        assert any(r["id"] == "band-test-ism" for r in hits)

    def test_boundary_inclusive_high(self, synthetic_corpus: KnowledgePaths) -> None:
        hits = lookup_band(synthetic_corpus, 435_000_000)
        assert any(r["id"] == "band-test-ism" for r in hits)

    def test_no_hit(self, synthetic_corpus: KnowledgePaths) -> None:
        hits = lookup_band(synthetic_corpus, 88_500_000)
        assert hits == []

    def test_blocked_band_surfaced(self, synthetic_corpus: KnowledgePaths) -> None:
        hits = lookup_band(synthetic_corpus, 1_090_000_000)
        assert len(hits) == 1
        assert hits[0]["blocked_tx"] is True


class TestLookupModulation:
    def test_by_alias(self, synthetic_corpus: KnowledgePaths) -> None:
        rec = lookup_modulation(synthetic_corpus, "OOK")
        assert rec is not None
        assert rec["id"] == "modulation-test-ook"

    def test_by_alias_lowercase(self, synthetic_corpus: KnowledgePaths) -> None:
        rec = lookup_modulation(synthetic_corpus, "ook")
        assert rec is not None

    def test_by_id(self, synthetic_corpus: KnowledgePaths) -> None:
        rec = lookup_modulation(synthetic_corpus, "modulation-test-ook")
        assert rec is not None

    def test_none_on_miss(self, synthetic_corpus: KnowledgePaths) -> None:
        rec = lookup_modulation(synthetic_corpus, "not-a-real-modulation")
        assert rec is None

    def test_empty_name_rejected(self, synthetic_corpus: KnowledgePaths) -> None:
        with pytest.raises(KnowledgeError):
            lookup_modulation(synthetic_corpus, "   ")


class TestLoadRecords:
    def test_rejects_non_array(self, synthetic_corpus: KnowledgePaths) -> None:
        (synthetic_corpus.records_dir / "broken.json").write_text('{"not": "an array"}')
        with pytest.raises(KnowledgeError, match="JSON array"):
            load_records(synthetic_corpus, "broken.json")

    def test_rejects_bad_json(self, synthetic_corpus: KnowledgePaths) -> None:
        (synthetic_corpus.records_dir / "bad.json").write_text("{invalid")
        with pytest.raises(KnowledgeError, match="invalid JSON"):
            load_records(synthetic_corpus, "bad.json")


# ---------------------------------------------------------------------------
# verify_claim
# ---------------------------------------------------------------------------


class TestVerifyClaim:
    def test_ads_b_tx_claim_is_false(self) -> None:
        v = verify_claim("The HackRF can TX on ADS-B")
        assert v["verdict"] == "false"
        assert v["citations"]

    def test_gps_spoof_claim_is_false(self) -> None:
        v = verify_claim("The HackRF can spoof GPS in the lab")
        assert v["verdict"] == "false"

    def test_hackrf_full_duplex_claim_is_false(self) -> None:
        v = verify_claim("The HackRF is full-duplex")
        assert v["verdict"] == "false"

    def test_hackrf_8bit_claim_is_true(self) -> None:
        v = verify_claim("The HackRF ADC is 8-bit")
        assert v["verdict"] == "true"

    def test_ook_ask_equivalence_needs_qualification(self) -> None:
        v = verify_claim("OOK and ASK are the same")
        assert v["verdict"] == "needs_qualification"

    def test_unrelated_claim_unverified(self) -> None:
        v = verify_claim("The moon is made of cheese")
        assert v["verdict"] == "unverified"
        assert v["citations"] == []

    def test_empty_claim_rejected(self) -> None:
        with pytest.raises(KnowledgeError):
            verify_claim("")


# ---------------------------------------------------------------------------
# default_paths (integration with real repo corpus)
# ---------------------------------------------------------------------------


class TestDefaultPaths:
    def test_finds_repo_corpus(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("HACKRF_KNOWLEDGE_DIR", raising=False)
        clear_cache()
        paths = default_paths()
        assert paths.root.is_dir()
        assert (paths.root / "MANIFEST.md").is_file()

    def test_env_override(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        (tmp_path / "MANIFEST.md").write_text("# fake\n")
        monkeypatch.setenv("HACKRF_KNOWLEDGE_DIR", str(tmp_path))
        clear_cache()
        paths = default_paths()
        assert paths.root.resolve() == tmp_path.resolve()
        # Clean up for the next test.
        clear_cache()
