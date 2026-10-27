"""Offline, synthetic retrieval evaluation for the reusable Board library.

Run directly to measure the current lexical implementation against fixed classroom
requests. No teacher files, accounts, model, image provider or GUI are accessed.
The small generated PNGs exercise real local hash/availability checks; they are
plain colour blocks, not judged teaching illustrations.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
import statistics
import struct
import tempfile
import time
from typing import Any
import uuid
import zlib

from board_resources import ResourceCatalogue


@dataclass(frozen=True)
class SearchCase:
    name: str
    query: str
    relevant: tuple[str, ...]
    filters: dict[str, Any] = field(default_factory=dict)


# Relevance is declared here independently of whatever the current ranker returns.
# Multiple relevant versions are intentional: only a remembered name picks one.
CASES = (
    SearchCase('chosen-name', 'our usual water-cycle diagram', ('water-current',)),
    SearchCase('chosen-name-case', 'OUR USUAL WATER-CYCLE DIAGRAM', ('water-current',)),
    SearchCase('chosen-name-spacing', '  our   usual water-cycle diagram  ', ('water-current',)),
    SearchCase('water-title', 'Labelled water cycle diagram', ('water-current',)),
    SearchCase('water-classroom', 'Show me a labelled water cycle diagram', ('water-current',)),
    SearchCase('water-year-five', 'water cycle', ('water-current',), {'resource_types': ['image'], 'year_levels': ['5'], 'review_states': ['approved']}),
    SearchCase('water-year-three', 'water cycle', ('water-old',), {'resource_types': ['image'], 'year_levels': ['3']}),
    SearchCase('water-approved-versions', 'water cycle', ('water-current', 'water-old'), {'resource_types': ['image'], 'review_states': ['approved']}),
    SearchCase('water-draft', 'water cycle', ('water-draft',), {'resource_types': ['image'], 'review_states': ['draft']}),
    SearchCase('rejected-management', 'water cycle', ('water-rejected',), {'review_states': ['rejected']}),
    SearchCase('water-page', 'water cycle', ('water-page',), {'resource_types': ['page']}),
    SearchCase('scientific-stage', 'condensation', ('water-current', 'condensation'), {'year_levels': ['5']}),
    SearchCase('water-description', 'evaporation precipitation', ('water-current',)),
    SearchCase('corrected-title', 'Particle model of solids liquids and gases', ('particles',)),
    SearchCase('corrected-tag', 'states-of-matter', ('particles',)),
    SearchCase('science-filter', 'particles', ('particles',), {'topics': ['Science']}),
    SearchCase('year-normalisation', 'particles', ('particles',), {'year_levels': ['Year 5']}),
    SearchCase('rain-dataset', 'monthly rainfall', ('rain-data',), {'resource_types': ['dataset']}),
    SearchCase('rain-chart', 'monthly rainfall', ('rain-chart',), {'resource_types': ['chart']}),
    SearchCase('rain-units', 'rainfall millimetres', ('rain-data', 'rain-chart'), {'topics': ['Science']}),
    SearchCase('rain-remembered', 'our rainfall graph', ('rain-chart',)),
    SearchCase('fraction-chart', 'equivalent fractions', ('fractions',)),
    SearchCase('fraction-classroom', 'Find the equivalent fractions chart', ('fractions',)),
    SearchCase('area-units', 'square centimetres', ('area',)),
    SearchCase('perimeter-page', 'perimeter rectangles', ('perimeter',)),
    SearchCase('maths-topic', '', ('fractions', 'area', 'perimeter'), {'topics': ['Mathematics'], 'review_states': ['approved']}),
    SearchCase('food-web', 'food web', ('food-web',)),
    SearchCase('food-web-alias', 'feeding relationships', ('food-web',)),
    SearchCase('butterfly', 'butterfly life cycle', ('butterfly',)),
    SearchCase('life-cycle-year', 'life cycle', ('butterfly',), {'year_levels': ['2']}),
    SearchCase('poetry-page', 'Clancy bush poetry', ('clancy',)),
    SearchCase('english-topic', 'poetry', ('clancy',), {'topics': ['English']}),
    SearchCase('greek-history', 'ancient Greece', ('greece',)),
    SearchCase('vocabulary-type', 'water cycle vocabulary', ('vocabulary',), {'resource_types': ['document']}),
    SearchCase('video-metadata', 'cloud formation', ('cloud-video',), {'resource_types': ['video']}),
    SearchCase('audio-metadata', 'bird calls', ('bird-audio',), {'resource_types': ['audio']}),
    SearchCase('ambiguous-alias', 'class starter', ('water-page', 'perimeter'), {'review_states': ['approved']}),
    SearchCase('water-process-paraphrase', 'diagram showing how water moves through nature', ('water-current',)),
    SearchCase('butterfly-paraphrase', 'Find the stages of a butterfly growing', ('butterfly',)),
    SearchCase('fraction-paraphrase', 'fractions that have the same value', ('fractions',)),
    SearchCase('perimeter-paraphrase', 'centimetres around the outside of a rectangle', ('perimeter',)),
    SearchCase('rain-paraphrase', 'rain totals by month', ('rain-data', 'rain-chart')),
    SearchCase('unknown-with-generic-word', 'diagram of volcano layers', ()),
    SearchCase('no-topic-match', 'water cycle', (), {'topics': ['Humanities']}),
    SearchCase('no-year-match', 'water cycle', (), {'year_levels': ['12']}),
    SearchCase('no-type-match', 'equivalent fractions', (), {'resource_types': ['video']}),
    SearchCase('unknown-content', 'tectonic plates', ()),
    SearchCase('unknown-remembered-name', 'our usual volcano cutaway', ()),
    SearchCase('rejected-default', 'Incorrect monsoon circulation', ()),
    SearchCase('excluded-default', 'Private assessment answers', ()),
)


def _identity(value: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, 'board-search-quality:' + value))


def _png(colour: int) -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack('!I', len(data)) + kind + data + struct.pack('!I', zlib.crc32(kind + data) & 0xffffffff)
    pixels = bytes((0, colour, 120, 180, colour, 120, 180)) * 2
    return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('!2I5B', 2, 2, 8, 2, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(pixels)) + chunk(b'IEND', b'')


def build_fixture(root: Path) -> tuple[ResourceCatalogue, dict[str, str]]:
    """Create only disposable synthetic catalogue records under ``root``."""
    root = Path(root)
    media_root = root / 'synthetic-media'
    media: dict[str, dict[str, Any]] = {}
    catalogue = ResourceCatalogue(root / 'catalogue', media_root=media_root,
        resolver=lambda asset_id, version_id: media.get(version_id))
    identities: dict[str, str] = {}

    def add(key, resource_type, title, description, topic, years, *, state='approved', aliases=(), tags=(), resource_key=None):
        resource_id, version_id = _identity('resource:' + (resource_key or key)), _identity('version:' + key)
        ref = None
        if resource_type == 'image':
            raw = _png(30 + len(identities) * 7)
            digest = hashlib.sha256(raw).hexdigest()
            path = media_root / 'blobs' / 'sha256' / digest[:2] / digest[2:]
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
            ref = {'asset_id': resource_id, 'version_id': version_id, 'sha256': digest}
            media[version_id] = {**ref, 'mime': 'image/png', 'byte_size': len(raw)}
        catalogue.save_resource(resource_type, title, description=description, tags=tags,
            resource_id=resource_id, version_id=version_id, image_ref=ref, state=state,
            aliases=aliases, availability='offline', provenance={'kind': 'synthetic evaluation fixture'})
        catalogue.update_metadata(version_id, topics=[topic], year_levels=years)
        identities[key] = version_id

    add('water-current', 'image', 'Labelled water cycle diagram',
        'Evaporation condensation precipitation and collection. Arrows show water moving between sea, clouds and land.',
        'Science', ['5'], resource_key='water')
    add('water-old', 'image', 'Simple water cycle picture', 'Water cycle overview with sun sea clouds and rain.',
        'Science', ['3'], resource_key='water')
    add('water-draft', 'image', 'Water cycle unlabelled draft', 'Water cycle illustration awaiting teacher review.',
        'Science', ['5'], state='draft')
    add('water-rejected', 'image', 'Water cycle rejected diagram', 'Incorrect monsoon circulation.',
        'Science', ['5'], state='rejected')
    add('water-page', 'page', 'Water cycle lesson introduction', 'A page introducing the water cycle.',
        'Science', ['5'], aliases=['class starter'])
    add('condensation', 'image', 'Condensation on a cold glass', 'Condensation forms water droplets on a cold surface.', 'Science', ['5'])
    add('particles', 'image', 'Draft particle picture', 'Particles in three familiar states.', 'Science', ['5'])
    catalogue.update_metadata(identities['particles'], title='Particle model of solids liquids and gases',
        tags=['states-of-matter'], description='Particles show solids liquids and gases; compare their arrangement.')
    add('rain-data', 'dataset', 'Monthly rainfall measurements', 'Rainfall totals in millimetres for four months; synthetic values.', 'Science', ['5'])
    add('rain-chart', 'chart', 'Monthly rainfall bar chart', 'Rainfall in millimetres from the selected monthly measurements.', 'Science', ['5'])
    add('fractions', 'chart', 'Equivalent fractions strips', 'Fraction strips comparing halves quarters and eighths.', 'Mathematics', ['4', '5'])
    add('area', 'image', 'Area of rectangles', 'Count square centimetres to measure rectangular area.', 'Mathematics', ['5'])
    add('perimeter', 'page', 'Perimeter of rectangles', 'Measure the perimeter of rectangles in centimetres.', 'Mathematics', ['5'], aliases=['class starter'])
    add('food-web', 'image', 'Australian grassland food web', 'Producer consumer and predator arrows.', 'Science', ['4'], aliases=['feeding relationships'])
    add('butterfly', 'image', 'Butterfly life cycle', 'Egg caterpillar chrysalis adult butterfly.', 'Science', ['2'])
    add('clancy', 'page', 'Clancy bush poetry discussion', 'Poetry discussion about the speaker and contrasting settings.', 'English', ['5'])
    add('greece', 'document', 'Ancient Greece source notes', 'A source reading about ancient Greece and city states.', 'Humanities', ['6'])
    add('vocabulary', 'document', 'Water cycle vocabulary cards', 'Definitions of water cycle terms for reading support.', 'English', ['5'])
    add('cloud-video', 'video', 'Cloud formation explanation', 'Metadata for a cloud formation video; playback is outside this test.', 'Science', ['5'])
    add('bird-audio', 'audio', 'Australian bird calls', 'Metadata for bird calls; audio playback is outside this test.', 'Science', ['2'])
    add('private-answers', 'document', 'Private assessment answers', 'Excluded answer key for teacher use.', 'Mathematics', ['5'], state='excluded')
    catalogue.remember_name('our usual water-cycle diagram', identities['water-old'])
    # A changed preference must bind to the teacher's chosen version, not newest.
    catalogue.remember_name('our usual water-cycle diagram', identities['water-current'])
    catalogue.remember_name('our rainfall graph', identities['rain-chart'])
    return catalogue, identities


def evaluate(catalogue, identities: dict[str, str], cases=CASES) -> dict[str, Any]:
    """Measure relevance against the declared set; retain every case outcome."""
    by_id = {value: key for key, value in identities.items()}
    results, recalls, precisions, reciprocals, single_top1, negative_hits, timings = [], [], [], [], [], [], []
    for case in cases:
        start = time.perf_counter()
        records = catalogue.search(case.query, limit=5, **case.filters)
        elapsed_ms = (time.perf_counter() - start) * 1000
        timings.append(elapsed_ms)
        returned = [by_id.get(record['version_id'], record['version_id']) for record in records]
        expected = set(case.relevant)
        ranks = [index + 1 for index, key in enumerate(returned) if key in expected]
        recall = len(set(returned) & expected) / len(expected) if expected else None
        reciprocal = 1 / min(ranks) if ranks else 0.0
        if expected:
            recalls.append(recall)
            precisions.append(len(set(returned) & expected) / len(returned) if returned else 0.0)
            reciprocals.append(reciprocal)
            if len(expected) == 1:
                single_top1.append(bool(returned and returned[0] in expected))
        else:
            negative_hits.append(bool(returned))
        results.append({'name': case.name, 'query': case.query, 'filters': case.filters,
            'relevant': list(case.relevant), 'returned': returned, 'recall_at_5': recall,
            'reciprocal_rank_at_5': reciprocal if expected else None,
            'passed': recall == 1 if expected else not returned, 'elapsed_ms': round(elapsed_ms, 3),
            'reasons': [record.get('match_reasons', []) for record in records]})
    timings_sorted = sorted(timings)
    metrics = {'cases': len(results), 'positive_cases': len(recalls), 'negative_cases': len(negative_hits),
        'recall_at_5': statistics.mean(recalls) if recalls else None,
        'precision_at_returned_5': statistics.mean(precisions) if precisions else None,
        'mean_reciprocal_rank_at_5': statistics.mean(reciprocals) if reciprocals else None,
        'single_choice_cases': len(single_top1),
        'single_choice_top_1': statistics.mean(single_top1) if single_top1 else None,
        'no_match_false_positive_cases': sum(negative_hits),
        'no_match_false_positive_rate': statistics.mean(negative_hits) if negative_hits else None,
        'fully_recalled_or_correctly_empty': sum(result['passed'] for result in results),
        'median_ms': round(statistics.median(timings), 3) if timings else None,
        'p95_ms': round(timings_sorted[max(0, (95 * len(timings_sorted) + 99) // 100 - 1)], 3) if timings else None}
    return {'schema': 1, 'fixture': 'synthetic-classroom-v1', 'resource_count': len(identities),
        'limits': ['Synthetic relevance judgements, not teacher acceptance.',
            'Small local catalogue; no 1,000/10,000/100,000-record scale claim.',
            'Timing covers one warm local search per case, excluding fixture creation.',
            'Image previews are colour blocks; this does not assess visual correctness.'],
        'metrics': metrics, 'results': results}


def run_evaluation(work_root: Path | None = None) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix='board-search-quality-', dir=work_root) as temporary:
        catalogue, identities = build_fixture(Path(temporary))
        return evaluate(catalogue, identities)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, help='Optional JSON evidence path; its parent must already exist.')
    parser.add_argument('--work-root', type=Path, help='Optional existing folder for the disposable fixture, useful in a restricted workspace.')
    args = parser.parse_args(argv)
    report = run_evaluation(args.work_root)
    if args.output:
        args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps(report['metrics'], indent=2))
    for case in report['results']:
        if not case['passed']:
            print(f"GAP {case['name']}: expected {case['relevant']}; returned {case['returned']}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
