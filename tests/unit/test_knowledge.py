"""Tests for hackrf_agent.domain.knowledge (Phase 3 knowledge tier)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hackrf_agent.domain.knowledge import (
    KnowledgeError,
    KnowledgePaths,
    clear_cache,
    cross_reference,
    default_paths,
    explain_signal,
    get_bibliography,
    list_topics,
    load_records,
    lookup_band,
    lookup_decoder,
    lookup_keyfob,
    lookup_modulation,
    lookup_protocol,
    random_file,
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


# ---------------------------------------------------------------------------
# Extended corpus fixture for the seven new knowledge verbs.
# ---------------------------------------------------------------------------


@pytest.fixture
def extended_corpus(tmp_path: Path) -> KnowledgePaths:
    """Corpus with every records file the new verbs bind to."""
    root = tmp_path / "knowledge"
    (root / "records").mkdir(parents=True)
    (root / "dsp").mkdir()
    (root / "modulation").mkdir()
    (root / "MANIFEST.md").write_text("# manifest\n", encoding="utf-8")
    (root / "dsp" / "README.md").write_text("# dsp\n", encoding="utf-8")
    (root / "modulation" / "README.md").write_text("# modulation\n", encoding="utf-8")

    (root / "records" / "protocols.json").write_text(
        json.dumps(
            [
                {
                    "id": "protocol-test-pocsag",
                    "name": "POCSAG paging (test)",
                    "aliases": ["POCSAG", "CCIR-1"],
                    "category": "protocol_phy",
                    "citations": ["fake"],
                    "confidence": "primary",
                    "technical_body": {"modulation": "2FSK", "baud": 1200},
                    "see_also": ["mod-test-2fsk", "no-such-id"],
                }
            ]
        ),
        encoding="utf-8",
    )
    (root / "records" / "keyfobs.json").write_text(
        json.dumps(
            [
                {
                    "id": "kf-chamberlain-a",
                    "name": "Chamberlain Security+ (test)",
                    "aliases": ["Security+"],
                    "category": "keyfob_system",
                    "citations": ["fake"],
                    "confidence": "primary",
                    "technical_body": {"vendor": "Chamberlain", "rolling": True},
                    "see_also": [],
                },
                {
                    "id": "kf-genie-a",
                    "name": "Genie Intellicode (test)",
                    "category": "keyfob_system",
                    "citations": ["fake"],
                    "confidence": "primary",
                    "technical_body": {"vendor": "Genie", "rolling": True},
                    "see_also": [],
                },
            ]
        ),
        encoding="utf-8",
    )
    (root / "records" / "decoders.json").write_text(
        json.dumps(
            [
                {
                    "id": "decoder-test-manchester",
                    "name": "Manchester (test)",
                    "aliases": ["biphase-L"],
                    "category": "decoder_family",
                    "citations": ["fake"],
                    "confidence": "primary",
                    "technical_body": {"self_clocking": True},
                    "see_also": [],
                }
            ]
        ),
        encoding="utf-8",
    )
    (root / "records" / "bibliography.json").write_text(
        json.dumps(
            [
                {
                    "id": "bib-test-1",
                    "name": "Fake reference (test)",
                    "category": "bibliography",
                    "citations": [],
                    "confidence": "primary",
                    "technical_body": {"url": "https://example.invalid/x"},
                },
                {
                    "id": "bib-test-2",
                    "name": "Another fake (test)",
                    "category": "bibliography",
                    "citations": [],
                    "confidence": "secondary",
                    "technical_body": {},
                },
            ]
        ),
        encoding="utf-8",
    )
    (root / "records" / "known_signals.json").write_text(
        json.dumps(
            [
                {
                    "id": "signal-test-ook-433",
                    "name": "Test OOK burst",
                    "category": "protocol_phy",
                    "citations": ["fake"],
                    "confidence": "secondary",
                    "technical_body": {
                        "center_hz": 433_920_000,
                        "bandwidth_hz": 40_000,
                        "modulation": "OOK",
                    },
                    "see_also": [],
                },
                {
                    "id": "signal-test-adsb",
                    "name": "Test ADS-B",
                    "category": "protocol_phy",
                    "citations": ["fake"],
                    "confidence": "secondary",
                    "technical_body": {
                        "center_hz": 1_090_000_000,
                        "bandwidth_hz": 2_000_000,
                        "modulation": "PPM",
                    },
                    "see_also": [],
                },
            ]
        ),
        encoding="utf-8",
    )
    # Minimal companion index for cross-reference (root protocol has see_also
    # that refers to a modulation-file id).
    (root / "records" / "modulations.json").write_text(
        json.dumps(
            [
                {
                    "id": "mod-test-2fsk",
                    "name": "2FSK (test)",
                    "category": "modulation_family",
                    "citations": ["fake"],
                    "confidence": "primary",
                    "technical_body": {},
                }
            ]
        ),
        encoding="utf-8",
    )
    return KnowledgePaths(root=root)


class TestLookupProtocol:
    def test_by_alias(self, extended_corpus: KnowledgePaths) -> None:
        rec = lookup_protocol(extended_corpus, "POCSAG")
        assert rec is not None
        assert rec["id"] == "protocol-test-pocsag"

    def test_miss_returns_none(self, extended_corpus: KnowledgePaths) -> None:
        assert lookup_protocol(extended_corpus, "not-a-real-thing") is None

    def test_empty_rejected(self, extended_corpus: KnowledgePaths) -> None:
        with pytest.raises(KnowledgeError):
            lookup_protocol(extended_corpus, "   ")


class TestLookupDecoder:
    def test_by_alias(self, extended_corpus: KnowledgePaths) -> None:
        rec = lookup_decoder(extended_corpus, "biphase-L")
        assert rec is not None
        assert rec["id"] == "decoder-test-manchester"

    def test_miss_returns_none(self, extended_corpus: KnowledgePaths) -> None:
        assert lookup_decoder(extended_corpus, "not-a-real-thing") is None


class TestLookupKeyfob:
    def test_by_vendor(self, extended_corpus: KnowledgePaths) -> None:
        hits = lookup_keyfob(extended_corpus, "Chamberlain", None)
        assert len(hits) == 1
        assert hits[0]["id"] == "kf-chamberlain-a"

    def test_by_model(self, extended_corpus: KnowledgePaths) -> None:
        hits = lookup_keyfob(extended_corpus, None, "Intellicode")
        assert len(hits) == 1
        assert hits[0]["id"] == "kf-genie-a"

    def test_requires_at_least_one(
        self, extended_corpus: KnowledgePaths
    ) -> None:
        with pytest.raises(KnowledgeError):
            lookup_keyfob(extended_corpus, None, None)

    def test_no_match(self, extended_corpus: KnowledgePaths) -> None:
        assert lookup_keyfob(extended_corpus, "Nonexistent", None) == []


class TestBibliography:
    def test_by_id(self, extended_corpus: KnowledgePaths) -> None:
        hits = get_bibliography(extended_corpus, "bib-test-1")
        assert len(hits) == 1
        assert hits[0]["id"] == "bib-test-1"

    def test_full_list(self, extended_corpus: KnowledgePaths) -> None:
        hits = get_bibliography(extended_corpus, None)
        assert len(hits) == 2

    def test_missing_id_empty_list(
        self, extended_corpus: KnowledgePaths
    ) -> None:
        assert get_bibliography(extended_corpus, "no-such-cite") == []


class TestRandomFile:
    def test_seed_determinism(self, extended_corpus: KnowledgePaths) -> None:
        first = random_file(extended_corpus, seed=42)
        second = random_file(extended_corpus, seed=42)
        assert first["topic"] == second["topic"]
        assert first["name"] == second["name"]

    def test_returns_readable_content(
        self, extended_corpus: KnowledgePaths
    ) -> None:
        rec = random_file(extended_corpus, seed=1)
        assert "content" in rec
        assert rec["name"].endswith(".md")

    def test_empty_corpus_raises(self, tmp_path: Path) -> None:
        root = tmp_path / "kb"
        (root / "records").mkdir(parents=True)
        (root / "MANIFEST.md").write_text("# manifest\n")
        paths = KnowledgePaths(root=root)
        with pytest.raises(KnowledgeError, match="no markdown files"):
            random_file(paths)


class TestExplainSignal:
    def test_by_frequency(self, extended_corpus: KnowledgePaths) -> None:
        hits = explain_signal(
            extended_corpus,
            freq_hz=433_920_000,
            bw_hz=None,
            modulation_guess=None,
        )
        assert hits
        assert hits[0]["record"]["id"] == "signal-test-ook-433"

    def test_modulation_hint_alone(
        self, extended_corpus: KnowledgePaths
    ) -> None:
        hits = explain_signal(
            extended_corpus,
            freq_hz=None,
            bw_hz=None,
            modulation_guess="OOK",
        )
        assert hits
        ids = [h["record"]["id"] for h in hits]
        assert "signal-test-ook-433" in ids

    def test_bw_narrows(self, extended_corpus: KnowledgePaths) -> None:
        # freq 433.92 + bw 40 kHz should score higher than freq alone
        hits = explain_signal(
            extended_corpus,
            freq_hz=433_920_000,
            bw_hz=40_000,
            modulation_guess="OOK",
        )
        assert hits
        assert hits[0]["score"] == 3.0

    def test_requires_a_hint(self, extended_corpus: KnowledgePaths) -> None:
        with pytest.raises(KnowledgeError):
            explain_signal(
                extended_corpus, freq_hz=None, bw_hz=None, modulation_guess=None
            )

    def test_ranks_by_score(self, extended_corpus: KnowledgePaths) -> None:
        hits = explain_signal(
            extended_corpus, freq_hz=1_090_000_000, bw_hz=None, modulation_guess=None
        )
        assert hits[0]["record"]["id"] == "signal-test-adsb"


class TestCrossReference:
    def test_resolves_related(self, extended_corpus: KnowledgePaths) -> None:
        result = cross_reference(extended_corpus, "protocol-test-pocsag")
        assert result["record"]["id"] == "protocol-test-pocsag"
        related_ids = [r["id"] for r in result["related"]]
        assert "mod-test-2fsk" in related_ids
        assert "no-such-id" in result["unresolved"]

    def test_unknown_root_record(
        self, extended_corpus: KnowledgePaths
    ) -> None:
        result = cross_reference(extended_corpus, "no-such-record")
        assert result["record"] is None
        assert result["related"] == []
        assert result["unresolved"] == []

    def test_empty_id_rejected(self, extended_corpus: KnowledgePaths) -> None:
        with pytest.raises(KnowledgeError):
            cross_reference(extended_corpus, "   ")
