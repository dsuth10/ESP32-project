"""Experimental, isolated Qt Teaching Board candidate; no remote integrations.

Requires an explicit directory inside the repository's reserved candidate root.
All document changes use BoardSession/BoardModel; user pilot data is never found.
"""
from __future__ import annotations

import argparse
import copy
import json
import math
import os
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QPointF, QEvent, QBuffer, QIODevice
from PySide6.QtGui import (QColor, QPen, QBrush, QPixmap, QPainterPath, QFont,
                          QGuiApplication, QImage, QPainter, QPointingDevice,
                          QImageReader, QTransform)
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QComboBox, QGraphicsView, QGraphicsScene,
    QGraphicsItem, QTextEdit, QDoubleSpinBox, QSpinBox, QFormLayout, QSplitter,
    QMessageBox, QCheckBox)

from board_model import BoardModel, BoardValidationError, new_lesson, new_page, new_object
from board_store import BoardStore
from board_session import BoardSession
from media_store import MediaStore

REPOSITORY = Path(__file__).resolve().parents[2]
CANDIDATE_ROOT = REPOSITORY / '.local' / 'teaching-board-candidate'


def candidate_directory(value):
    raw = Path(value).expanduser().absolute()
    for entry in (raw, *raw.parents):
        if entry.is_symlink() or entry.is_junction():
            raise ValueError('Candidate folders must not redirect through links or junctions.')
    path = raw.resolve()
    allowed = CANDIDATE_ROOT.absolute()
    if path == allowed or allowed not in path.parents:
        raise ValueError('Choose a lesson subfolder inside .local/teaching-board-candidate/.')
    return path


def validate_candidate_storage(root):
    candidate_directory(root)
    if root.exists():
        for directory, folders, files in os.walk(root, followlinks=False):
            for name in folders + files:
                entry = Path(directory)/name
                if entry.is_symlink() or entry.is_junction():
                    raise ValueError('Candidate storage must not contain links or junctions.')


def image_resolver(store):
    """Read exact managed versions only; the session additionally verifies SHA-256."""
    def resolve(reference):
        version = store.get_version(reference['version_id'])
        if not version or any(version[key] != reference[key] for key in ('asset_id', 'version_id', 'sha256')):
            raise ValueError('Pinned image version is unavailable.')
        path = store.blob_path(reference['sha256']).resolve()
        if store.blobs.resolve() not in path.parents or path.stat().st_size > 20*1024*1024:
            raise ValueError('Image is outside the managed candidate library or oversized.')
        return path.read_bytes()
    return resolve


def decode_image(data):
    if not isinstance(data, bytes) or not 0 < len(data) <= 20*1024*1024:
        raise ValueError('Image exceeds the candidate byte limit.')
    buffer = QBuffer(); buffer.setData(data); buffer.open(QIODevice.OpenModeFlag.ReadOnly)
    reader = QImageReader(buffer)
    size = reader.size()
    if (bytes(reader.format()).lower() not in (b'png', b'jpeg', b'jpg', b'webp')
            or size.width() <= 0 or size.height() <= 0 or size.width()*size.height() > 25_000_000):
        raise ValueError('Image has an unsupported format or unsafe pixel dimensions.')
    image = reader.read()
    if image.isNull():
        raise ValueError('Image could not be decoded.')
    return QPixmap.fromImage(image)


def demo_model(media):
    image = QImage(480, 280, QImage.Format.Format_RGB32)
    image.fill(QColor('#d4efff'))
    painter = QPainter(image)
    painter.fillRect(0, 170, 480, 110, QColor('#159ec0'))
    painter.setBrush(QColor('#ffe06b')); painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(350, 25, 70, 70); painter.end()
    buffer = QBuffer(); buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, 'PNG')
    version = media.import_bytes(bytes(buffer.data()), 'Synthetic water-cycle illustration', tags=['candidate', 'synthetic'])
    reference = {key: version[key] for key in ('asset_id', 'version_id', 'sha256')}
    lesson = new_lesson('Water cycle — synthetic candidate lesson')
    lesson['pages'] = []
    for title in ('Evaporation', 'Condensation', 'Precipitation'):
        page = new_page(title)
        page['objects'] = [
            new_object('text', x=80, y=55, width=1400, height=100, text=title, font_size=62),
            new_object('image', x=100, y=250, width=680, height=397, image_ref=reference),
            new_object('shape', x=950, y=280, width=490, height=280, fill='#FFF1B8', stroke='#665000', stroke_width=3),
            new_object('text', x=990, y=335, width=410, height=160, text='Edit this explanation for your lesson.', font_size=38),
            new_object('arrow', x=760, y=420, width=200, height=80, start=[0, 0], end=[200, 80], colour='#E05243', stroke_width=7),
        ]
        lesson['pages'].append(page)
    return BoardModel(lesson)


def page_from(view):
    return next(page for page in view['document']['pages'] if page['id'] == view['page_id'])


def size_changes(value, width, height):
    changes = dict(width=width, height=height)
    if value['type'] == 'ink':
        changes['points'] = [[x*width/value['width'], y*height/value['height']] for x, y in value['points']]
    elif value['type'] == 'arrow':
        for key in ('start', 'end'):
            changes[key] = [value[key][0]*width/value['width'], value[key][1]*height/value['height']]
    return changes


class BoardCanvas(QGraphicsView):
    def __init__(self, owner, audience=False):
        super().__init__()
        self.owner, self.audience = owner, audience
        self.view = None
        self.points, self.capture, self.preview = [], None, None
        self.missing_images = False
        self.page_item = None
        self.zoom = 100
        self.setScene(QGraphicsScene(self))
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        self.viewport().setAttribute(Qt.WidgetAttribute.WA_AcceptTouchEvents)
        self.scene().selectionChanged.connect(self.selection_changed)

    def selection_changed(self):
        if not self.audience and not self.owner.refreshing:
            selected = self.scene().selectedItems()
            self.owner.select(selected[0].data(0) if selected else None)

    def render(self, view):
        if (self.view and self.view['document'] == view['document'] and self.view['page_id'] == view['page_id']
                and self.view['token'] == view['token'] and self.view['frozen'] == view['frozen']):
            self.view = view
            return
        self.cancel_gesture()
        self.view = view
        self.missing_images = False
        self.scene().clear()
        page = page_from(view)
        self.scene().setSceneRect(0, 0, page['width'], page['height'])
        self.scene().setBackgroundBrush(QColor('#DDE2E7'))
        self.page_item = self.scene().addRect(0, 0, page['width'], page['height'],
                                             QPen(Qt.PenStyle.NoPen), QBrush(QColor('white')))
        self.page_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemClipsChildrenToShape)
        for value in page['objects']:
            self.add_item(value)
        self.fit()

    def add_item(self, value):
        scene, kind, width, height = self.scene(), value['type'], value['width'], value['height']
        if kind == 'text':
            font = QFont('Segoe UI'); font.setPixelSize(round(value['font_size']))
            item = scene.addText(value['text'], font)
            item.document().setDocumentMargin(0)
            option = item.document().defaultTextOption()
            option.setAlignment({'left': Qt.AlignmentFlag.AlignLeft, 'centre': Qt.AlignmentFlag.AlignHCenter,
                                 'right': Qt.AlignmentFlag.AlignRight}[value['align']])
            item.document().setDefaultTextOption(option)
            item.setTextWidth(width)
            item.setDefaultTextColor(QColor(value['colour']))
        elif kind == 'image':
            try:
                data = self.owner.session.resolve_image(value['image_ref'])
                pixmap = decode_image(data)
                item = scene.addPixmap(pixmap)
                item.setTransform(QTransform.fromScale(width/pixmap.width(), height/pixmap.height()))
                item.setTransformationMode(Qt.TransformationMode.SmoothTransformation)
            except Exception:
                item = scene.addRect(0, 0, width, height, QPen(QColor('#B73535'), 3), QBrush(QColor('#FFF0F0')))
                label = scene.addText('Image unavailable', QFont('Segoe UI', 20))
                label.setParentItem(item); label.setPos(15, 15)
                self.missing_images = True
        elif kind == 'shape':
            draw = scene.addEllipse if value['shape'] == 'ellipse' else scene.addRect
            item = draw(0, 0, width, height, QPen(QColor(value['stroke']), value['stroke_width']), QBrush(QColor(value['fill'])))
        else:
            points = value['points'] if kind == 'ink' else [value['start'], value['end']]
            path = QPainterPath(QPointF(*points[0]))
            for point in points[1:]:
                path.lineTo(QPointF(*point))
            if kind == 'arrow':
                first, last = points[0], points[-1]
                angle = math.atan2(last[1]-first[1], last[0]-first[0])
                for offset in (-0.5, 0.5):
                    path.moveTo(*last)
                    path.lineTo(last[0]-25*math.cos(angle+offset), last[1]-25*math.sin(angle+offset))
            pen = QPen(QColor(value['colour']), value['stroke_width'])
            pen.setCapStyle(Qt.PenCapStyle.RoundCap); pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            item = scene.addPath(path, pen)
        item.setParentItem(self.page_item)
        item.setData(0, value['id']); item.setData(1, kind)
        item.setPos(value['x'], value['y']); item.setRotation(value['rotation'])
        if not self.audience and not value['locked']:
            item.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsMovable | QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
            if value['id'] == self.owner.selected:
                item.setSelected(True)

    def fit(self):
        if self.sceneRect().width():
            self.fitInView(self.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
            self.scale(self.zoom/100, self.zoom/100)

    def resizeEvent(self, event):
        super().resizeEvent(event); self.fit()

    def mode(self):
        return (self.owner.pupil_mode if self.audience else self.owner.mode).currentText()

    def can_ink(self):
        return self.view and (not self.audience or not self.view['frozen'])

    def coordinate(self, position):
        point, rect = self.mapToScene(position.toPoint()), self.sceneRect()
        return [max(0, min(rect.width(), point.x())), max(0, min(rect.height(), point.y()))]

    def begin_ink(self, position, source, eraser=False):
        if not self.can_ink():
            return
        view = self.owner.session.pupil_view() if self.audience else self.owner.session.teacher_view()
        self.capture = (view['revision'], view['token'], source)
        if eraser or self.mode() == 'Erase ink':
            item = self.itemAt(position.toPoint())
            while item and item.data(0) is None:
                item = item.parentItem()
            if item and item.data(1) == 'ink':
                self.owner.erase(self.audience, item.data(0), view)
            self.capture = None
            return
        self.points = [self.coordinate(position)]

    def extend_ink(self, position):
        if self.points and len(self.points) < 10000:
            point = self.coordinate(position)
            if math.dist(point, self.points[-1]) < 1:
                return
            self.points.append(point)
            path = QPainterPath(QPointF(*self.points[0]))
            for item in self.points[1:]:
                path.lineTo(QPointF(*item))
            if self.preview is None:
                self.preview = self.scene().addPath(path, QPen(QColor('#C52D48'), 6))
                self.preview.setParentItem(self.page_item)
            else:
                self.preview.setPath(path)

    def finish_ink(self, position):
        if self.capture and self.points:
            self.extend_ink(position)
            points, capture = self.points[:], self.capture
            self.cancel_gesture()
            self.owner.ink(self.audience, points, capture)

    def cancel_gesture(self):
        if self.preview is not None:
            self.scene().removeItem(self.preview)
        self.preview, self.points, self.capture = None, [], None

    def tabletEvent(self, event):
        eraser = event.pointingDevice().pointerType() == QPointingDevice.PointerType.Eraser
        if event.type() == QEvent.Type.TabletPress:
            self.begin_ink(event.position(), 'pen', eraser)
        elif event.type() == QEvent.Type.TabletMove:
            self.extend_ink(event.position())
        elif event.type() == QEvent.Type.TabletRelease:
            self.finish_ink(event.position())
        event.accept()

    def viewportEvent(self, event):
        if event.type() == QEvent.Type.TouchCancel:
            self.cancel_gesture(); event.accept(); return True
        if event.type() in (QEvent.Type.TouchBegin, QEvent.Type.TouchUpdate, QEvent.Type.TouchEnd):
            # One contact draws. Gestures and hardware palm rejection remain unaccepted.
            if event.points() and (not self.capture or self.capture[2] == 'touch'):
                position = event.points()[0].position()
                if event.type() == QEvent.Type.TouchBegin:
                    self.begin_ink(position, 'touch')
                elif event.type() == QEvent.Type.TouchUpdate:
                    self.extend_ink(position)
                else:
                    self.finish_ink(position)
            event.accept(); return True
        return super().viewportEvent(event)

    def mousePressEvent(self, event):
        if self.audience and self.view['frozen']:
            return
        if self.mode() in ('Ink', 'Erase ink'):
            self.begin_ink(event.position(), 'mouse')
        elif not self.audience:
            view = self.owner.session.teacher_view()
            self.capture = (view['revision'], view['token'], 'move')
            self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag if self.mode() == 'Pan' else QGraphicsView.DragMode.RubberBandDrag)
            self.setInteractive(self.mode() != 'Pan')
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.points:
            self.extend_ink(event.position())
        elif not self.audience:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.points:
            self.finish_ink(event.position()); return
        if self.audience:
            return
        capture = self.capture
        self.capture = None
        super().mouseReleaseEvent(event)
        if capture and capture[2] == 'move':
            changed = []
            page = page_from(self.view)
            for item in self.scene().selectedItems():
                value = next(o for o in page['objects'] if o['id'] == item.data(0))
                if math.dist([value['x'], value['y']], [item.pos().x(), item.pos().y()]) > 0.01:
                    changed.append(dict(op='update_object', page_id=page['id'], object_id=value['id'],
                                        changes=dict(x=item.pos().x(), y=item.pos().y())))
            if changed:
                self.owner.apply(changed, capture)


class PupilWindow(QWidget):
    def __init__(self, owner):
        super().__init__(); self.owner = owner

    def closeEvent(self, event):
        event.ignore(); self.hide()
        self.owner.show_pupil.setChecked(False)


class BoardCandidate(QWidget):
    def __init__(self, session, *, store=None, resolver=None):
        super().__init__()
        self.session, self.store, self.resolver = session, store, resolver
        self.selected, self.refreshing, self.media_unavailable = None, False, False
        self.selection_view = None
        self.name_capture = None
        self.error = ''
        self.recovery_notice = session.teacher_view().get('recovery_status') == 'recovered_previous'
        self.save_timer = QTimer(self); self.save_timer.setSingleShot(True)
        self.save_timer.timeout.connect(self.autosave)
        self.setWindowTitle('Teaching Board — experimental isolated candidate')
        layout = QVBoxLayout(self)
        notice = QLabel('Experimental Teaching Board · local candidate lesson')
        layout.addWidget(notice)
        top = QHBoxLayout(); layout.addLayout(top)
        self.name = QLineEdit(session.teacher_view()['document']['title'])
        self.name.textEdited.connect(self.capture_name_edit)
        top.addWidget(self.name, 1)
        for label, command in [('Rename lesson', self.rename), ('Save now', self.autosave), ('Reopen saved', self.reopen)]:
            button = QPushButton(label); button.clicked.connect(command); top.addWidget(button)
        toolbar = QHBoxLayout(); layout.addLayout(toolbar)
        self.mode = QComboBox(); self.mode.addItems(['Select / move', 'Ink', 'Erase ink', 'Pan'])
        self.mode.currentTextChanged.connect(lambda: self.teacher_canvas.cancel_gesture())
        toolbar.addWidget(self.mode)
        for label, command in [('Previous', lambda: self.navigate(-1)), ('Next', lambda: self.navigate(1)),
                               ('New page', self.add_page), ('Undo', self.undo), ('Redo', self.redo),
                               ('Freeze', self.freeze), ('Resume', self.resume)]:
            button = QPushButton(label); button.clicked.connect(command); toolbar.addWidget(button)
        self.zoom = QSpinBox(); self.zoom.setRange(25, 300); self.zoom.setSuffix('%'); self.zoom.setValue(100)
        self.zoom.valueChanged.connect(self.set_zoom); toolbar.addWidget(self.zoom)
        splitter = QSplitter(); layout.addWidget(splitter, 1)
        self.teacher_canvas = BoardCanvas(self); splitter.addWidget(self.teacher_canvas)
        side = QWidget(); side_layout = QVBoxLayout(side); splitter.addWidget(side)
        side.setMaximumWidth(320)
        for label, kind in [('Add text', 'text'), ('Rectangle', 'rectangle'), ('Ellipse', 'ellipse'), ('Arrow', 'arrow')]:
            button = QPushButton(label); button.clicked.connect(lambda checked=False, k=kind: self.add_object(k)); side_layout.addWidget(button)
        self.text = QTextEdit(); self.text.setPlaceholderText('Select a text box to edit its text.'); self.text.setMaximumHeight(120)
        side_layout.addWidget(self.text)
        form = QFormLayout(); side_layout.addLayout(form)
        self.fields = {}
        for field, label in [('x', 'Left'), ('y', 'Top'), ('width', 'Width'), ('height', 'Height')]:
            spin = QDoubleSpinBox(); spin.setDecimals(1); spin.setRange(-100000 if field in ('x', 'y') else .1, 100000)
            form.addRow(label, spin); self.fields[field] = spin
        self.font_size = QSpinBox(); self.font_size.setRange(1, 1000); form.addRow('Text size', self.font_size)
        apply_button = QPushButton('Apply selected changes'); apply_button.clicked.connect(self.apply_properties); side_layout.addWidget(apply_button)
        reload_button = QPushButton('Reload selected fields'); reload_button.clicked.connect(lambda: self.select(self.selected)); side_layout.addWidget(reload_button)
        side_layout.addStretch()
        self.show_pupil = QCheckBox('Show pupil window'); self.show_pupil.setChecked(True)
        side_layout.addWidget(self.show_pupil)
        self.screens = QComboBox()
        self.screens.addItems([f'Display {i+1}' for i, _ in enumerate(QGuiApplication.screens())]); side_layout.addWidget(self.screens)
        move = QPushButton('Move pupil to display'); move.clicked.connect(self.move_pupil); side_layout.addWidget(move)
        self.status = QLabel(); self.status.setWordWrap(True); layout.addWidget(self.status)
        self.pupil = PupilWindow(self); self.pupil.setWindowTitle('Teaching Board — pupil display')
        pupil_layout = QVBoxLayout(self.pupil)
        self.pupil_canvas = BoardCanvas(self, True); pupil_layout.addWidget(self.pupil_canvas, 1)
        pupil_controls = QHBoxLayout(); pupil_layout.addLayout(pupil_controls)
        self.pupil_mode = QComboBox(); self.pupil_mode.addItems(['Ink', 'Erase ink']); pupil_controls.addWidget(self.pupil_mode)
        self.pupil_nav = []
        for label, delta in [('Previous page', -1), ('Next page', 1)]:
            button = QPushButton(label); button.clicked.connect(lambda checked=False, d=delta: self.navigate(d, True))
            pupil_controls.addWidget(button); self.pupil_nav.append(button)
        self.pupil_page = QLabel(); pupil_controls.addWidget(self.pupil_page)
        self.show_pupil.toggled.connect(self.pupil.setVisible)
        self.pupil_mode.currentTextChanged.connect(lambda: self.pupil_canvas.cancel_gesture())
        self.resize(1240, 820); self.pupil.resize(1000, 650)
        self.refresh()

    def refresh(self):
        self.refreshing = True; self.media_unavailable = False
        teacher, pupil = self.session.teacher_view(), self.session.pupil_view()
        self.teacher_canvas.render(teacher); self.pupil_canvas.render(pupil)
        self.media_unavailable = self.teacher_canvas.missing_images or self.pupil_canvas.missing_images
        self.setWindowTitle('Teaching Board — ' + teacher['document']['title'] + ' — experimental')
        if not self.name.isModified():
            self.name.setText(teacher['document']['title'])
        self.pupil_mode.setEnabled(not pupil['frozen'])
        for button in self.pupil_nav:
            button.setEnabled(not pupil['frozen'])
        page_index = next(i for i, p in enumerate(pupil['document']['pages']) if p['id'] == pupil['page_id'])
        self.pupil_page.setText(f"Page {page_index+1} of {len(pupil['document']['pages'])}")
        state = 'Unsaved changes' if teacher['dirty'] else 'Saved'
        if teacher.get('save_error'):
            state = 'Unsaved — save failed. ' + str(teacher['save_error'])
        parts = [state, 'Pupil display frozen' if teacher['frozen'] else 'Pupil display live']
        if self.recovery_notice:
            parts.append('Recovered previous save — review this lesson')
        if self.media_unavailable:
            parts.append('An image is unavailable; its position is preserved')
        if self.error:
            parts.append(self.error)
        if self.name.isModified():
            parts.append('Lesson name has unapplied changes')
        self.status.setText(' · '.join(parts))
        self.refreshing = False

    def run(self, operation, *, save=True):
        try:
            operation(); self.error = ''
        except Exception as error:
            self.error = str(error)
        self.refresh()
        if save and self.session.teacher_view()['dirty']:
            self.save_timer.start(300)

    def apply(self, commands, capture=None):
        view = self.session.teacher_view()
        revision, token = capture[:2] if capture else (view['revision'], view['token'])
        self.run(lambda: self.session.teacher_apply(commands, expected_revision=revision, expected_token=token))
        if capture and len(capture) > 2 and capture[2] == 'move' and not self.error:
            self.select(self.selected)

    def add_object(self, kind):
        view = self.session.teacher_view(); page = page_from(view)
        if kind == 'text':
            value = new_object('text', x=120, y=160, width=600, height=160, text='New text', font_size=40)
        elif kind == 'arrow':
            value = new_object('arrow', x=300, y=300, width=300, height=160, start=[0, 0], end=[300, 160])
        else:
            value = new_object('shape', x=250, y=250, width=300, height=200, shape=kind, fill='#FFF1B8')
        self.selected = value['id']
        self.apply([dict(op='add_object', page_id=page['id'], object=value)])
        self.select(value['id'])

    def select(self, object_id):
        self.selected = object_id
        self.selection_view = self.session.teacher_view()
        value = next((o for o in page_from(self.selection_view)['objects'] if o['id'] == object_id), None)
        self.text.setEnabled(bool(value and value['type'] == 'text'))
        if value:
            for key, spin in self.fields.items():
                spin.setValue(value[key])
            self.text.setPlainText(value.get('text', ''))
            self.font_size.setValue(round(value.get('font_size', 40)))

    def apply_properties(self):
        view = self.selection_view
        if view is None:
            return
        page = page_from(view)
        value = next((o for o in page['objects'] if o['id'] == self.selected), None)
        if not value or value['locked']:
            return
        changes = size_changes(value, self.fields['width'].value(), self.fields['height'].value())
        changes.update(x=self.fields['x'].value(), y=self.fields['y'].value())
        if value['type'] == 'text':
            changes.update(text=self.text.toPlainText(), font_size=self.font_size.value())
        self.apply([dict(op='update_object', page_id=page['id'], object_id=value['id'], changes=changes)], (view['revision'], view['token']))
        if not self.error:
            self.select(value['id'])

    def add_page(self):
        count = len(self.session.teacher_view()['document']['pages'])
        page = new_page(f'Page {count+1}')
        self.apply([dict(op='add_page', page=page)])
        view = self.session.teacher_view()
        self.run(lambda: self.session.teacher_navigate(page['id'], expected_token=view['token']))

    def navigate(self, delta, audience=False):
        view = self.session.pupil_view() if audience else self.session.teacher_view()
        pages = view['document']['pages']; index = next(i for i, p in enumerate(pages) if p['id'] == view['page_id'])
        destination = pages[(index+delta) % len(pages)]['id']
        method = self.session.pupil_navigate if audience else self.session.teacher_navigate
        self.selected = None
        self.run(lambda: method(destination, expected_token=view['token']), save=False)

    def ink(self, audience, points, capture):
        if len(points) < 2:
            return
        x, y = min(p[0] for p in points), min(p[1] for p in points)
        value = new_object('ink', x=x, y=y, width=max(.1, max(p[0] for p in points)-x),
                           height=max(.1, max(p[1] for p in points)-y),
                           points=[[px-x, py-y] for px, py in points], colour='#C52D48', stroke_width=6)
        if audience:
            self.run(lambda: self.session.pupil_add_ink(value, expected_revision=capture[0], expected_token=capture[1]))
        else:
            page_id = self.session.teacher_view()['page_id']
            self.apply([dict(op='add_object', page_id=page_id, object=value)], capture)

    def erase(self, audience, object_id, view):
        if audience:
            self.run(lambda: self.session.pupil_erase_ink(object_id, expected_revision=view['revision'], expected_token=view['token']))
        else:
            self.apply([dict(op='remove_object', page_id=view['page_id'], object_id=object_id)], (view['revision'], view['token']))

    def freeze(self):
        view = self.session.teacher_view()
        self.run(lambda: self.session.freeze(expected_token=view['token']), save=False)

    def resume(self):
        view = self.session.teacher_view()
        self.run(lambda: self.session.resume(expected_token=view['token']), save=False)

    def undo(self):
        view = self.session.teacher_view()
        self.run(lambda: self.session.teacher_undo(expected_revision=view['revision'], expected_token=view['token']))

    def redo(self):
        view = self.session.teacher_view()
        self.run(lambda: self.session.teacher_redo(expected_revision=view['revision'], expected_token=view['token']))

    def rename(self):
        view = self.session.teacher_view()
        if self.name.text() != view['document']['title']:
            source = self.name_capture or view
            self.apply([dict(op='rename_lesson', title=self.name.text())], (source['revision'], source['token']))
            if self.error:
                self.name_capture = None
                return
        self.name.setModified(False); self.name_capture = None; self.refresh()

    def capture_name_edit(self, _text):
        if self.name_capture is None:
            self.name_capture = self.session.teacher_view()

    def autosave(self):
        self.save_timer.stop()
        view = self.session.teacher_view()
        if view['dirty']:
            self.run(lambda: self.session.save(expected_token=view['token']), save=False)

    def reopen(self):
        if self.session.teacher_view()['dirty']:
            self.error = 'Save your changes before reopening.'; self.refresh(); return
        self.save_timer.stop()
        self.run(self._reopen, save=False)

    def _reopen(self):
        validate_candidate_storage(self.store.root)
        replacement = BoardSession.open(BoardStore(self.store.root), image_resolver=self.resolver)
        previous = self.session
        self.session = replacement
        previous.close()
        self.recovery_notice = replacement.teacher_view().get('recovery_status') == 'recovered_previous'
        self.name.setText(replacement.teacher_view()['document']['title']); self.name_capture = None; self.selected = None

    def set_zoom(self, value):
        self.teacher_canvas.zoom = value; self.teacher_canvas.fit()

    def move_pupil(self):
        screen = QGuiApplication.screens()[self.screens.currentIndex()]
        self.pupil.show(); self.show_pupil.setChecked(True)
        self.pupil.windowHandle().setScreen(screen); self.pupil.move(screen.geometry().topLeft())

    def closeEvent(self, event):
        self.autosave()
        if self.session.teacher_view()['dirty']:
            choice = QMessageBox.question(self, 'Unsaved lesson', 'The latest changes could not be saved. Close and discard those unsaved changes?',
                                          QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
                                          QMessageBox.StandardButton.Cancel)
            if choice != QMessageBox.StandardButton.Discard:
                event.ignore(); return
        self.save_timer.stop(); self.session.close(); self.pupil.hide(); event.accept()


def smoke(candidate, root):
    """Actual session/store and synthetic commands; no physical-input acceptance."""
    checks = {}
    candidate.autosave()
    initial = candidate.session.teacher_view()
    candidate.freeze(); pinned = candidate.session.pupil_view()
    candidate.add_object('text')
    candidate.navigate(1)
    checks['freeze_pupil_view_unchanged'] = candidate.session.pupil_view() == pinned
    before = copy.deepcopy(candidate.session.teacher_view()['document'])
    candidate.ink(True, [[100, 100], [200, 200]], (pinned['revision'], pinned['token'], 'synthetic'))
    checks['frozen_pupil_ink_denied'] = candidate.session.teacher_view()['document'] == before
    candidate.navigate(1, True)
    checks['frozen_pupil_navigation_denied'] = candidate.session.pupil_view() == pinned
    candidate.resume()
    checks['resume_complete_document'] = candidate.session.pupil_view()['document'] == candidate.session.teacher_view()['document']
    live = candidate.session.pupil_view()
    candidate.ink(True, [[140, 700], [340, 650], [540, 720]], (live['revision'], live['token'], 'synthetic'))
    stroke = page_from(candidate.session.pupil_view())['objects'][-1]
    candidate.erase(True, stroke['id'], candidate.session.pupil_view()); candidate.undo(); candidate.redo()
    checks['ink_erase_undo_redo'] = all(o['id'] != stroke['id'] for o in page_from(candidate.session.teacher_view())['objects'])
    candidate.autosave(); saved = candidate.session.teacher_view()['document']
    candidate.reopen()
    checks['save_reopen_exact'] = candidate.session.teacher_view()['document'] == saved
    candidate.undo(); candidate.autosave()
    checks['history_survives_reopen'] = candidate.session.teacher_view()['revision'] > saved['revision']
    candidate.refresh()
    evidence = root/'evidence'; evidence.mkdir(exist_ok=True)
    candidate.grab().save(str(evidence/'teacher.png'))
    candidate.pupil.grab().save(str(evidence/'pupil.png'))
    result = dict(checks=checks, revision=candidate.session.teacher_view()['revision'],
                  dirty=candidate.session.teacher_view()['dirty'], actual_model_session_store=True,
                  native_windows=2, displays_available=len(QGuiApplication.screens()),
                  synthetic_input=True, physical_pen_touch_projector_tested=False)
    (evidence/'result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result), flush=True)
    candidate.save_timer.stop(); candidate.session.close()
    candidate.pupil.hide(); candidate.hide(); QApplication.instance().exit(0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-root', type=candidate_directory, required=True)
    parser.add_argument('--demo', action='store_true', help='Create a synthetic three-page lesson in a fresh candidate folder.')
    parser.add_argument('--smoke', action='store_true', help='Run synthetic native checks in a fresh candidate folder and exit.')
    args = parser.parse_args()
    validate_candidate_storage(args.data_root)
    existing = any((args.data_root/name).exists() for name in ('lesson.json', 'lesson.previous.json'))
    if existing and (args.demo or args.smoke):
        parser.error('Demo/smoke requires a fresh candidate folder; existing lesson was preserved.')
    app = QApplication(sys.argv[:1])
    store = BoardStore(args.data_root); media = MediaStore(args.data_root/'media'); resolver = image_resolver(media)
    try:
        if existing:
            session = BoardSession.open(store, image_resolver=resolver)
        else:
            model = demo_model(media) if args.demo or args.smoke else BoardModel()
            session = BoardSession(model, store=store, image_resolver=resolver)
        candidate = BoardCandidate(session, store=store, resolver=resolver)
        candidate.show(); candidate.pupil.show()
        if args.smoke:
            QTimer.singleShot(600, lambda: smoke(candidate, args.data_root))
        elif session.teacher_view()['dirty']:
            candidate.save_timer.start(300)
        return app.exec()
    except Exception as error:
        if args.smoke:
            raise
        QMessageBox.critical(None, 'Lesson could not open', str(error) + '\nExisting lesson files were preserved.')
        return 1


if __name__ == '__main__':
    sys.exit(main())
