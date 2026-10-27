"""Retrieval measurement contracts and a fixed, offline classroom evaluation."""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from board_search_quality import CASES, SearchCase, build_fixture, evaluate, main, run_evaluation


def test_quality_metrics_count_partial_recall_ranks_and_false_positives():
    class FakeCatalogue:
        def search(self, query, **kwargs):
            assert kwargs['limit'] == 5
            values = {'partial': ['x', 'a'], 'single': ['c'], 'wrong-empty': ['x'], 'empty': []}[query]
            return [{'version_id': value, 'match_reasons': ['Synthetic test reason']} for value in values]
    cases = (
        SearchCase('partial', 'partial', ('a', 'b')),
        SearchCase('single', 'single', ('c',)),
        SearchCase('false-positive', 'wrong-empty', ()),
        SearchCase('correct-empty', 'empty', ()),
    )
    report = evaluate(FakeCatalogue(), {value: value for value in ['a', 'b', 'c', 'x']}, cases)
    metrics = report['metrics']
    assert metrics['recall_at_5'] == .75
    assert metrics['precision_at_returned_5'] == .75
    assert metrics['mean_reciprocal_rank_at_5'] == .75
    assert metrics['single_choice_cases'] == 1
    assert metrics['single_choice_top_1'] == 1
    assert metrics['no_match_false_positive_cases'] == 1
    assert metrics['no_match_false_positive_rate'] == .5
    assert metrics['fully_recalled_or_correctly_empty'] == 2
    assert report['results'][0]['passed'] is False
    assert report['results'][0]['returned'] == ['x', 'a']
    assert report['results'][0]['reasons'][0] == ['Synthetic test reason']


def test_fixture_includes_versions_review_distractors_and_teacher_corrections(tmp_path):
    catalogue, identities = build_fixture(tmp_path)
    current = catalogue.get_resource_by_version(identities['water-current'])
    older = catalogue.get_resource_by_version(identities['water-old'])
    assert current['resource_id'] == older['resource_id']
    assert current['version_id'] != older['version_id']
    assert current['availability'] == 'offline'
    assert catalogue.resolve('our usual water-cycle diagram')['version_id'] == current['version_id']
    assert catalogue.resolve('class starter') is None  # The ambiguous alias stays a choice.
    particles = catalogue.get_resource_by_version(identities['particles'])
    assert particles['source_title'] == 'Draft particle picture'
    assert particles['title'] == 'Particle model of solids liquids and gases'
    assert catalogue.search('Incorrect monsoon circulation') == []
    assert catalogue.search('Private assessment answers') == []
    managed = catalogue.search('water cycle', review_states=['rejected'])
    assert [record['version_id'] for record in managed] == [identities['water-rejected']]


def test_fixed_classroom_evaluation_keeps_relevance_and_exposes_every_case(tmp_path):
    report = run_evaluation(tmp_path)
    assert len(CASES) == 50
    assert len({case.name for case in CASES}) == len(CASES)
    assert report['resource_count'] == 20
    assert report['metrics']['positive_cases'] == 42
    assert report['metrics']['negative_cases'] == 8
    assert len(report['results']) == 50
    assert all(case['name'] and 'passed' in case for case in report['results'])
    # Exact-name and filtered decisions are release contracts. Paraphrase quality
    # remains visible in the report rather than silently rewriting relevance.
    by_name = {case['name']: case for case in report['results']}
    assert by_name['chosen-name']['returned'][0] == 'water-current'
    assert by_name['water-year-five']['returned'][0] == 'water-current'
    assert not {'water-old', 'water-draft', 'water-rejected'} & set(by_name['water-year-five']['returned'])
    assert by_name['water-year-three']['returned'] == ['water-old']
    assert by_name['no-year-match']['returned'] == []
    assert by_name['rain-paraphrase']['relevant'] == ['rain-data', 'rain-chart']
    assert by_name['unknown-with-generic-word']['relevant'] == []


def test_quality_cli_writes_machine_readable_evidence_without_catalogue_paths(tmp_path, capsys):
    output = tmp_path / 'quality.json'
    assert main(['--output', str(output), '--work-root', str(tmp_path)]) == 0
    report = json.loads(output.read_text(encoding='utf-8'))
    assert report['schema'] == 1
    assert report['fixture'] == 'synthetic-classroom-v1'
    assert str(tmp_path) not in output.read_text(encoding='utf-8')
    assert 'recall_at_5' in capsys.readouterr().out
    assert sorted(path.name for path in tmp_path.iterdir()) == ['quality.json']
