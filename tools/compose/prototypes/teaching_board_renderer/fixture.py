"""THROWAWAY B0 fixture. Memory only; never opens user lessons or media stores."""
import base64
import copy
import hashlib
import json
import struct
import uuid
import zlib


def image_bytes():
    width, height = 240, 160
    pixels = b''.join(b'\0' + b''.join(bytes((35, 130 + y // 4, 200)) if y > 95 else
                        bytes((210, 235, 250)) for x in range(width)) for y in range(height))
    def chunk(kind, value):
        return struct.pack('!I', len(value)) + kind + value + struct.pack('!I', zlib.crc32(kind + value))
    return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('!IIBBBBB', width, height, 8, 2, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(pixels)) + chunk(b'IEND', b'')


IMAGE = image_bytes()
IMAGE_URL = 'data:image/png;base64,' + base64.b64encode(IMAGE).decode()


def identity():
    return str(uuid.uuid4())


def obj(kind, x, y, width, height, **fields):
    return dict(id=identity(), type=kind, x=x, y=y, width=width, height=height,
                rotation=0, locked=False, **fields)


def lesson():
    pages = []
    for title in ('Evaporation', 'Condensation', 'Precipitation'):
        pages.append(dict(id=identity(), title=title, width=1600, height=900, objects=[
            obj('text', 90, 65, 1100, 100, text=title, font_size=62, colour='#17324d', align='left'),
            obj('image', 140, 260, 550, 360, image_ref=dict(asset_id=identity(), version_id=identity(), sha256=hashlib.sha256(IMAGE).hexdigest())),
            obj('shape', 850, 290, 450, 250, shape='rectangle', fill='#fff1b8', stroke='#665000', stroke_width=4),
            obj('text', 890, 350, 360, 120, text='Editable explanation', font_size=36, colour='#17324d', align='left'),
            obj('arrow', 680, 360, 180, 80, start=[0, 0], end=[180, 80], colour='#e05243', stroke_width=10),
        ]))
    return dict(schema=1, lesson_id=identity(), title='PROTOTYPE — water cycle fixture', revision=0, pages=pages)


class ProbeState:
    """Temporary adapter shaped like B1; does not import/change the real model."""
    def __init__(self):
        self.document = lesson()
        self.page = 0
        self.frozen = False
        self.audience = None
        self.audience_page = 0
        self.history = []
        self.inputs = dict(mouse=0, pen=0, touch=0)

    def apply(self, operations, *, expected_revision):
        if expected_revision != self.document['revision']:
            raise ValueError('Stale fixture revision')
        candidate = copy.deepcopy(self.document)
        for operation in operations:
            page = next(p for p in candidate['pages'] if p['id'] == operation['page_id'])
            if operation['op'] == 'add_object':
                page['objects'].append(copy.deepcopy(operation['object']))
            elif operation['op'] == 'update_object':
                next(o for o in page['objects'] if o['id'] == operation['object_id']).update(operation['changes'])
            elif operation['op'] == 'remove_object':
                page['objects'] = [o for o in page['objects'] if o['id'] != operation['object_id']]
            else:
                raise ValueError('Unsupported fixture operation')
        self.history.append(copy.deepcopy(self.document))
        candidate['revision'] += 1
        self.document = candidate

    def update(self, object_id, **changes):
        self.apply([dict(op='update_object', page_id=self.document['pages'][self.page]['id'], object_id=object_id, changes=changes)], expected_revision=self.document['revision'])

    def ink(self, points, source='mouse', audience=False):
        if audience and self.frozen:
            return False
        if len(points) < 2:
            return False
        self.inputs[source] += 1
        x, y = min(p[0] for p in points), min(p[1] for p in points)
        width, height = max(1, max(p[0] for p in points)-x), max(1, max(p[1] for p in points)-y)
        stroke = obj('ink', x, y, width, height, points=[[px-x, py-y] for px, py in points], colour='#d52b45', stroke_width=8)
        self.apply([dict(op='add_object', page_id=self.document['pages'][self.page]['id'], object=stroke)], expected_revision=self.document['revision'])
        return True

    def erase(self, object_id, audience=False):
        if audience and self.frozen:
            return False
        self.apply([dict(op='remove_object', page_id=self.document['pages'][self.page]['id'], object_id=object_id)], expected_revision=self.document['revision'])
        return True

    def navigate(self, delta, audience=False):
        if audience and self.frozen:
            return False
        self.page = (self.page + delta) % len(self.document['pages'])
        return True

    def freeze(self):
        self.audience, self.audience_page = copy.deepcopy(self.document), self.page
        self.frozen = True

    def resume(self):
        self.frozen = False
        self.audience = None

    def undo(self):
        if self.history:
            previous = self.history.pop()
            previous['revision'] = self.document['revision'] + 1
            self.document = previous

    def visible(self, audience=False):
        doc = self.audience if audience and self.frozen else self.document
        index = self.audience_page if audience and self.frozen else self.page
        return doc['pages'][index]

    def summary(self):
        return dict(revision=self.document['revision'], page=self.page+1, frozen=self.frozen,
                    audience_page=self.audience_page+1 if self.frozen else self.page+1,
                    objects=len(self.visible()['objects']), input_strokes=self.inputs)


def exercise():
    """Synthetic command checks, not physical pen/display acceptance."""
    state = ProbeState()
    state.freeze()
    before = copy.deepcopy(state.visible(True))
    state.update(state.visible()['objects'][0]['id'], text='Changed behind Freeze')
    state.navigate(1)
    checks = dict(frozen_snapshot_unchanged=state.visible(True) == before,
                  frozen_ink_blocked=not state.ink([[5, 5], [20, 20]], audience=True),
                  frozen_navigation_blocked=not state.navigate(1, audience=True))
    state.resume()
    checks['resume_presents_completed_page'] = state.visible(True) == state.visible()
    state.ink([[100, 200], [250, 350], [400, 250]])
    ink_id = state.visible()['objects'][-1]['id']
    state.erase(ink_id)
    state.undo()
    checks['ink_erase_undo'] = state.visible()['objects'][-1]['id'] == ink_id
    try:
        state.apply([], expected_revision=0)
        checks['stale_revision_rejected'] = False
    except ValueError:
        checks['stale_revision_rejected'] = True
    return checks


if __name__ == '__main__':
    print(json.dumps(exercise(), indent=2))
