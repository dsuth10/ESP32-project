"""Teacher curation and practical lexical retrieval use disposable local stores."""
from pathlib import Path
import sqlite3
import sys
import uuid

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from board_resources import ResourceCatalogue


def test_teacher_corrections_survive_reopen_reingestion_and_index_rebuild(tmp_path):
    catalogue = ResourceCatalogue(tmp_path)
    source = catalogue.save_resource("page", "Watre cycel", description="Old caption", tags=["Unsorted"],
                                     metadata={"page": "original bytes"}, idempotency_key="water-v1")
    with sqlite3.connect(catalogue.path) as db:
        original = db.execute("SELECT * FROM resource_version").fetchone()
    corrected = catalogue.update_metadata(source["version_id"], title="Water cycle", description="Labelled evaporation diagram",
                                         tags=["Hydrology", "hydrology"], topics=["Science"], year_levels=["Year 5"])
    assert corrected["source_title"] == "Watre cycel"
    assert corrected["source_description"] == "Old caption"
    assert corrected["source_tags"] == ["Unsorted"]
    assert corrected["tags"] == ["Hydrology"]
    repeated = catalogue.save_resource("page", "Watre cycel", description="Old caption", tags=["Unsorted"],
                                      metadata={"page": "original bytes"}, idempotency_key="water-v1")
    assert repeated["title"] == "Water cycle"
    reopened = ResourceCatalogue(tmp_path)
    assert reopened.rebuild_index() == 1
    assert reopened.search("evaporation", topics=["science"], year_levels=["5"])[0]["version_id"] == source["version_id"]
    with sqlite3.connect(catalogue.path) as db:
        assert db.execute("SELECT * FROM resource_version").fetchone() == original
        assert db.execute("PRAGMA user_version").fetchone()[0] == 1


def test_partial_edits_and_explicit_clearing_preserve_other_corrections(tmp_path):
    catalogue = ResourceCatalogue(tmp_path)
    item = catalogue.save_resource("document", "Resource", description="Source description")
    catalogue.update_metadata(item["version_id"], title="Revised", tags=["Science"], topics=["Water"], year_levels=["Prep"])
    record = catalogue.update_metadata(item["version_id"], description="", tags=[])
    assert record["title"] == "Revised"
    assert record["description"] == ""
    assert record["tags"] == []
    assert record["topics"] == ["Water"]
    assert record["year_levels"] == ["0"]
    assert catalogue.search("Revised", year_levels=["Foundation"])


def test_remembered_name_pins_chosen_version_and_reassignment_is_explicit(tmp_path):
    catalogue = ResourceCatalogue(tmp_path)
    first = catalogue.save_resource("page", "Cycle one", state="approved", aliases=["our usual water-cycle diagram"])
    chosen = catalogue.save_resource("page", "Cycle two", state="approved")
    catalogue.remember_name("our usual water-cycle diagram", first["version_id"])
    newer = catalogue.save_resource("page", "Cycle three", resource_id=first["resource_id"], state="approved")
    assert catalogue.resolve("our usual water-cycle diagram")["version_id"] == first["version_id"]
    catalogue.remember_name(" OUR   usual water-cycle diagram ", chosen["version_id"])
    assert catalogue.resolve("OUR usual water-cycle diagram")["version_id"] == chosen["version_id"]
    rows = catalogue.search("our usual water-cycle diagram")
    assert rows[0]["version_id"] == chosen["version_id"]
    assert rows[0]["match_reasons"][0].startswith("Remembered name:")
    assert not catalogue.get_resource_by_version(first["version_id"])["remembered_names"]
    assert not catalogue.get_resource_by_version(newer["version_id"])["remembered_names"]
    assert catalogue.forget_name("our USUAL water-cycle diagram")
    assert not catalogue.forget_name("our usual water-cycle diagram")
    assert catalogue.resolve("our usual water-cycle diagram")["version_id"] == first["version_id"]


def test_remembered_draft_or_rejected_choice_cannot_fall_back_to_approved_alias(tmp_path):
    catalogue = ResourceCatalogue(tmp_path)
    catalogue.save_resource("page", "Earlier", aliases=["usual diagram"], state="approved")
    chosen = catalogue.save_resource("page", "New draft")
    catalogue.remember_name("usual diagram", chosen["version_id"])
    assert catalogue.auto_select("usual diagram") is None
    catalogue.set_review_state(chosen["resource_id"], chosen["version_id"], "rejected")
    assert catalogue.resolve("usual diagram") is None
    assert catalogue.auto_select("usual diagram") is None
    assert catalogue.resolve("usual diagram", include_excluded=True)["version_id"] == chosen["version_id"]


def test_filters_apply_before_limit_and_explain_evidence(tmp_path):
    catalogue = ResourceCatalogue(tmp_path)
    for index in range(105):
        catalogue.save_resource("page", f"Water cycle activity {index}", state="approved")
    correct = catalogue.save_resource("page", "Water cycle diagram", state="approved")
    catalogue.update_metadata(correct["version_id"], topics=["Science"], year_levels=["5"], tags=["labelled"])
    result = catalogue.search("Please show me a labelled water-cycle diagram for Year 5", topics=["science"],
                              year_levels=["Year 5"], resource_types=["page"], review_states=["approved"], limit=1)
    assert [item["version_id"] for item in result] == [correct["version_id"]]
    assert "Title: water, cycle, diagram" in result[0]["match_reasons"]
    assert "Tags: labelled" in result[0]["match_reasons"]
    assert "Approval filter: approved" in result[0]["match_reasons"]
    assert catalogue.search("water", topics=["History"]) == []
    assert catalogue.search("water", year_levels=["6"]) == []


def test_approval_filter_exposes_exclusions_only_when_requested(tmp_path):
    catalogue = ResourceCatalogue(tmp_path)
    good = catalogue.save_resource("page", "Water approved", state="approved")
    rejected = catalogue.save_resource("page", "Water rejected", state="rejected")
    assert [item["version_id"] for item in catalogue.search("water")] == [good["version_id"]]
    result = catalogue.search("water", review_states=["rejected"])
    assert [item["version_id"] for item in result] == [rejected["version_id"]]
    assert catalogue.search("water", review_states=["approved"])[0]["version_id"] == good["version_id"]


@pytest.mark.parametrize("kwargs", [
    {"title": ""}, {"title": "x" * 201}, {"description": 12}, {"tags": "Science"},
    {"topics": [False]}, {"year_levels": ["13"]}, {"year_levels": [5]}, {"tags": 42},
])
def test_invalid_corrections_leave_previous_metadata_intact(tmp_path, kwargs):
    catalogue = ResourceCatalogue(tmp_path)
    item = catalogue.save_resource("page", "Original")
    with pytest.raises(ValueError):
        catalogue.update_metadata(item["version_id"], **kwargs)
    assert catalogue.get_resource_by_version(item["version_id"])["title"] == "Original"


def test_exact_punctuation_name_and_query_syntax_are_data(tmp_path):
    catalogue = ResourceCatalogue(tmp_path)
    item = catalogue.save_resource("page", "Cycle", state="approved")
    catalogue.remember_name("?!", item["version_id"])
    assert catalogue.search("?!")[0]["version_id"] == item["version_id"]
    assert catalogue.search('" OR 1=1 --') == []
    assert catalogue.search()[0]["match_reasons"] == ["Browse saved resources"]
    with pytest.raises(ValueError):
        catalogue.search(review_states=["accepted"])


def test_empty_facet_corrections_remain_distinguishable_from_source_defaults(tmp_path):
    catalogue = ResourceCatalogue(tmp_path)
    item = catalogue.save_resource("page", "Source facets", metadata={"topics": ["Science"], "year_levels": ["5"]})
    assert not item["has_teacher_metadata"]
    assert item["topics"] == ["Science"]
    assert item["year_levels"] == ["5"]
    corrected = catalogue.update_metadata(item["version_id"], topics=[], year_levels=[])
    assert corrected["has_teacher_metadata"]
    assert corrected["topics"] == []
    assert corrected["year_levels"] == []
    reopened = ResourceCatalogue(tmp_path).get_resource_by_version(item["version_id"])
    assert reopened["has_teacher_metadata"]
    assert reopened["topics"] == []


def test_fts_normalised_spelling_has_an_honest_matching_reason(tmp_path):
    catalogue = ResourceCatalogue(tmp_path)
    item = catalogue.save_resource("document", "Café")
    results = catalogue.search("cafe")
    assert results[0]["version_id"] == item["version_id"]
    assert results[0]["match_reasons"] == ["Local keyword match (normalised spelling)"]


def test_type_filtered_resolution_preserves_global_explicit_choices(tmp_path):
    catalogue = ResourceCatalogue(tmp_path)
    page = catalogue.save_resource("page", "Usual diagram", state="approved")
    image = catalogue.save_resource("image", "Usual diagram", state="approved",
        image_ref={"asset_id": str(uuid.uuid4()), "version_id": str(uuid.uuid4()), "sha256": "a" * 64})
    assert catalogue.resolve("Usual diagram") is None
    assert catalogue.resolve("Usual diagram", resource_types=["image"])["version_id"] == image["version_id"]
    assert catalogue.resolve(page["version_id"], resource_types=["image"]) is None
    assert catalogue.resolve(page["resource_id"], resource_types=["image"], include_excluded=True) is None
    assert catalogue.auto_select("Usual diagram", resource_types=["page"])["version_id"] == page["version_id"]
    catalogue.remember_name("Usual diagram", page["version_id"])
    assert catalogue.resolve("Usual diagram", resource_types=["image"]) is None
    assert catalogue.auto_select("Usual diagram", resource_types=["image"]) is None
    with pytest.raises(ValueError):
        catalogue.resolve("Usual diagram", resource_types=["unsupported"])
