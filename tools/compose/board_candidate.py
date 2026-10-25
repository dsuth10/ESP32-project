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

from PySide6.QtCore import Qt, QTimer, QPointF, QRectF, QEvent, QBuffer, QIODevice
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
import uuid
from PySide6.QtCore import QSignalBlocker, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QInputDialog
from board_lessons import (copy_saved_lesson, refresh_saved_lesson_access,
                           new_saved_lesson_directory, is_catalogue_lesson)
from board_resize import handle_positions, resize_frame
from board_images import import_prepared, safe_path
from board_image_picker import ImagePicker

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
        self.resize_state = None
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
            self.viewport().update()

    def render(self, view):
        if (self.view and self.view['document'] == view['document'] and self.view['page_id'] == view['page_id']
                and self.view['token'] == view['token'] and self.view['frozen'] == view['frozen']):
            self.view = view
            return
        self.cancel_gesture()
        self.view = view
        self.missing_images = False
        # Destruction must not call selection handlers with partly deleted items.
        self.page_item = None
        self.scene().blockSignals(True)
        try:
            self.scene().clear()
        finally:
            self.scene().blockSignals(False)
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

    def selected_frame(self):
        if self.audience or not self.view or self.mode() != 'Select / move':
            return None
        value = next((o for o in page_from(self.view)['objects']
                      if o['id'] == self.owner.selected), None)
        if value and not value['locked'] and value['type'] in ('text', 'image', 'shape', 'arrow'):
            return value
        return None

    def drawForeground(self, painter, rect):
        super().drawForeground(painter, rect)
        value = self.selected_frame()
        if value is None:
            return
        if self.resize_state:
            value = {**value, **self.resize_state['changes']}
        positions = handle_positions(value)
        painter.save()
        pen = QPen(QColor('#1769B0'), 1, Qt.PenStyle.DashLine); pen.setCosmetic(True)
        painter.setPen(pen); painter.setBrush(Qt.BrushStyle.NoBrush)
        path = QPainterPath(QPointF(*positions['nw']))
        for key in ('ne', 'se', 'sw', 'nw'):
            path.lineTo(QPointF(*positions[key]))
        painter.drawPath(path)
        pen.setStyle(Qt.PenStyle.SolidLine); painter.setPen(pen)
        painter.setBrush(QColor('white'))
        half = 5/max(abs(self.transform().m11()), .0001)
        for x, y in positions.values():
            painter.drawRect(QRectF(x-half, y-half, half*2, half*2))
        painter.restore()

    def resize_handle_at(self, position):
        value = self.selected_frame()
        if value:
            for key, point in handle_positions(value).items():
                centre = self.mapFromScene(QPointF(*point))
                if abs(centre.x()-position.x()) <= 8 and abs(centre.y()-position.y()) <= 8:
                    return key
        return None

    def begin_resize(self, handle, position=None):
        value = self.selected_frame()
        if value is None:
            return False
        item = next((item for item in self.scene().items() if item.data(0) == value['id']), None)
        if item is None:
            return False
        view = self.owner.session.teacher_view()
        self.capture = (view['revision'], view['token'], 'resize')
        pointer = self.mapToScene(position.toPoint()) if position is not None else QPointF(*handle_positions(value)[handle])
        anchor = handle_positions(value)[handle]
        self.resize_state = dict(value=copy.deepcopy(value), item=item, handle=handle,
                                 pointer_offset=(pointer.x()-anchor[0], pointer.y()-anchor[1]),
                                 keep_aspect=self.owner.is_aspect_locked(value['id']),
                                 changes={key: value[key] for key in ('x', 'y', 'width', 'height')})
        return True

    def preview_resize(self, position):
        state = self.resize_state
        if state is None:
            return
        view = self.owner.session.teacher_view()
        if self.capture[:2] != (view['revision'], view['token']):
            self.cancel_gesture(); return
        point = self.mapToScene(position.toPoint())
        offset = state['pointer_offset']
        changes = resize_frame(state['value'], state['handle'], (point.x()-offset[0], point.y()-offset[1]),
                               keep_aspect=state['keep_aspect'])
        state['changes'] = changes
        self.preview_frame(state['item'], state['value'], changes)
        self.viewport().update()

    @staticmethod
    def preview_frame(item, original, changes):
        width, height = changes['width'], changes['height']
        if original['type'] == 'text':
            item.setTextWidth(width)
        elif original['type'] == 'shape' or (original['type'] == 'image' and not hasattr(item, 'pixmap')):
            item.setRect(0, 0, width, height)
        elif original['type'] == 'image':
            pixmap = item.pixmap()
            item.setTransform(QTransform.fromScale(width/pixmap.width(), height/pixmap.height()))
        elif original['type'] == 'arrow':
            geometry = size_changes(original, width, height)
            first, last = geometry['start'], geometry['end']
            path = QPainterPath(QPointF(*first)); path.lineTo(QPointF(*last))
            angle = math.atan2(last[1]-first[1], last[0]-first[0])
            for offset in (-.5, .5):
                path.moveTo(*last)
                path.lineTo(last[0]-25*math.cos(angle+offset), last[1]-25*math.sin(angle+offset))
            item.setPath(path)
        item.setPos(changes['x'], changes['y'])

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
        # A preceding live text/size edit must finish before this gesture's
        # revision is captured; its timer must not cancel the new stroke.
        if not self.owner.flush_pending_edits():
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
        if self.resize_state is not None:
            state, self.resize_state = self.resize_state, None
            self.preview_frame(state['item'], state['value'], state['value'])
        if self.preview is not None:
            self.scene().removeItem(self.preview)
        self.preview, self.points, self.capture = None, [], None
        self.viewport().update()

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
            if not self.owner.flush_pending_edits():
                event.accept(); return
            if event.button() == Qt.MouseButton.LeftButton:
                handle = self.resize_handle_at(event.position())
                if handle is not None and self.begin_resize(handle, event.position()):
                    event.accept(); return
            view = self.owner.session.teacher_view()
            self.capture = (view['revision'], view['token'], 'move')
            self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag if self.mode() == 'Pan' else QGraphicsView.DragMode.RubberBandDrag)
            self.setInteractive(self.mode() != 'Pan')
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.resize_state is not None:
            self.preview_resize(event.position()); event.accept()
        elif self.points:
            self.extend_ink(event.position())
        elif not self.audience:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.resize_state is not None:
            self.preview_resize(event.position())
            if self.resize_state is not None:
                state, capture = self.resize_state, self.capture
                original, changes = state['value'], state['changes']
                self.cancel_gesture()
                if any(abs(changes[key]-original[key]) > .001 for key in changes):
                    command_changes = size_changes(original, changes['width'], changes['height'])
                    command_changes.update(x=changes['x'], y=changes['y'])
                    self.owner.apply([dict(op='update_object', page_id=self.view['page_id'],
                                           object_id=original['id'], changes=command_changes)], capture)
            event.accept(); return
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
    def __init__(self, session, *, store=None, resolver=None, library_root=None):
        super().__init__()
        self.session, self.store, self.resolver = session, store, resolver
        self.library_root = Path(library_root) if library_root else None
        self.selected, self.refreshing, self.media_unavailable = None, False, False
        self.selection_view = None
        self.name_capture = None
        self.aspect_locks = {}
        self._loading_fields = False
        self._pending_fields = set()
        self._pending_view = None
        self._property_group = None
        self._committing_properties = False
        self.property_timer = QTimer(self); self.property_timer.setSingleShot(True)
        self.property_timer.timeout.connect(self.flush_pending_edits)
        self.group_timer = QTimer(self); self.group_timer.setSingleShot(True)
        self.group_timer.timeout.connect(self.end_property_group)
        self.error = ''
        self.catalogue_error = ''
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
        self.name.setToolTip('Change this lesson name. Save a copy creates a separate lesson.')
        for label, command in [('Rename lesson', self.rename)]:
            button = QPushButton(label); button.clicked.connect(command); top.addWidget(button)
        files = QHBoxLayout(); layout.addLayout(files)
        self.file_buttons = {}
        for label, command in [('Save now', self.save_now), ('Reopen saved', self.reopen),
                               ('Save a copy', self.save_copy), ('Open saved lessons', self.open_lesson_folder),
                               ('Save and close', self.close)]:
            button = QPushButton(label); button.clicked.connect(command); files.addWidget(button)
            self.file_buttons[label] = button
        self.location = QLabel(); self.location.setWordWrap(True)
        self.location.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.location)
        tools = QHBoxLayout(); layout.addLayout(tools)
        self.teacher_tools = {}
        for label in ('Select / move', 'Ink', 'Erase ink', 'Pan'):
            button = QPushButton(label); button.setCheckable(True)
            button.clicked.connect(lambda checked=False, mode=label: self.set_tool(False, mode))
            tools.addWidget(button); self.teacher_tools[label] = button
        toolbar = QHBoxLayout(); layout.addLayout(toolbar)
        self.mode = QComboBox(); self.mode.addItems(['Select / move', 'Ink', 'Erase ink', 'Pan'])
        self.mode.hide()
        self.mode.currentTextChanged.connect(lambda: self.tool_changed(False))
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
        self.add_image_button = QPushButton('Add image…')
        self.add_image_button.clicked.connect(self.add_image); side_layout.addWidget(self.add_image_button)
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
        self.aspect_lock = QCheckBox('Lock image aspect ratio'); self.aspect_lock.setChecked(True)
        self.aspect_lock.toggled.connect(self.set_aspect_lock); side_layout.addWidget(self.aspect_lock)
        live_notice = QLabel('Text and size changes update live. Freeze keeps edits private from pupils.')
        live_notice.setWordWrap(True); side_layout.addWidget(live_notice)
        self.text.textChanged.connect(lambda: self.queue_property_edit('text'))
        for field, spin in self.fields.items():
            spin.valueChanged.connect(lambda value, key=field: self.queue_property_edit(key))
        self.font_size.valueChanged.connect(lambda: self.queue_property_edit('font_size'))
        reload_button = QPushButton('Reload selected fields'); reload_button.clicked.connect(self.reload_selected_fields); side_layout.addWidget(reload_button)
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
        self.pupil_mode = QComboBox(); self.pupil_mode.addItems(['Ink', 'Erase ink']); self.pupil_mode.hide()
        self.pupil_tools = {}
        for label in ('Ink', 'Erase ink'):
            button = QPushButton(label); button.setCheckable(True)
            button.clicked.connect(lambda checked=False, mode=label: self.set_tool(True, mode))
            pupil_controls.addWidget(button); self.pupil_tools[label] = button
        self.pupil_nav = []
        for label, delta in [('Previous page', -1), ('Next page', 1)]:
            button = QPushButton(label); button.clicked.connect(lambda checked=False, d=delta: self.navigate(d, True))
            pupil_controls.addWidget(button); self.pupil_nav.append(button)
        self.pupil_page = QLabel(); pupil_controls.addWidget(self.pupil_page)
        self.show_pupil.toggled.connect(self.pupil.setVisible)
        self.pupil_mode.currentTextChanged.connect(lambda: self.tool_changed(True))
        self.resize(1240, 820); self.pupil.resize(1000, 650)
        self.refresh()
        if not self.session.teacher_view()['dirty']:
            self.sync_saved_lessons()

    def refresh(self):
        self.refreshing = True; self.media_unavailable = False
        teacher, pupil = self.session.teacher_view(), self.session.pupil_view()
        if self.selection_view is not None and not self._pending_fields:
            old_value = next((o for o in page_from(self.selection_view)['objects'] if o['id'] == self.selected), None)
            new_value = next((o for o in page_from(teacher)['objects'] if o['id'] == self.selected), None)
            if old_value != new_value:
                self.select(self.selected)
            else:
                self.selection_view = teacher
        self.teacher_canvas.render(teacher); self.pupil_canvas.render(pupil)
        self.media_unavailable = self.teacher_canvas.missing_images or self.pupil_canvas.missing_images
        self.setWindowTitle('Teaching Board — ' + teacher['document']['title'] + ' — experimental')
        if not self.name.isModified():
            self.name.setText(teacher['document']['title'])
        self.pupil_mode.setEnabled(not pupil['frozen'])
        for label, button in self.teacher_tools.items():
            button.setChecked(self.mode.currentText() == label)
        for label, button in self.pupil_tools.items():
            button.setChecked(self.pupil_mode.currentText() == label)
            button.setEnabled(not pupil['frozen'])
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
        if self.catalogue_error:
            parts.append(self.catalogue_error)
        if self.name.isModified():
            parts.append('Lesson name has unapplied changes')
        if self._pending_fields:
            parts.append('Text or size changes are waiting to be applied' if self.error else 'Updating text or size')
        if self.store:
            launcher = next((name for name in ('Open Teaching Board Lesson.cmd', 'Open Teaching Board Test.cmd')
                             if (self.store.root / name).is_file()), None)
            reopen_hint = ('Close the teacher window, then run ' + launcher + ' in this folder to reopen.' if launcher
                           else 'Close the teacher window, then relaunch with this same lesson folder to reopen.')
            if is_catalogue_lesson(self.store.root):
                self.location.setText('Saved lessons: ' + str(CANDIDATE_ROOT / 'saved-lessons')
                                      + '\nCurrent lesson data: ' + str(self.store.root)
                                      + '\nUse Open saved lessons and double-click a lesson name to reopen it.')
            else:
                self.location.setText('Lesson data: ' + str(self.store.root) + '\n' + reopen_hint)
        else:
            self.location.setText('No lesson folder configured')
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
        if capture and len(capture) > 2 and capture[2] in ('move', 'resize') and not self.error:
            self.select(self.selected)

    def add_object(self, kind):
        if not self.flush_pending_edits():
            return
        self.end_property_group()
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

    def image_library_root(self):
        if self.library_root is not None:
            return self.library_root
        if self.store:
            preference = safe_path(self.store.root / 'image-library-source.json')
            if preference.is_file() and preference.stat().st_size < 32768:
                try:
                    value = json.loads(preference.read_text(encoding='utf-8'))
                    if isinstance(value, dict) and isinstance(value.get('root'), str):
                        return Path(value['root'])
                except (OSError, ValueError):
                    pass
        explicit = os.environ.get('ESP32_COMPANION_DATA_DIR')
        return Path(explicit) if explicit else self.store.root / 'media' if self.store else CANDIDATE_ROOT / 'review/media'

    def remember_image_library(self, root):
        self.library_root = Path(root)
        if self.store:
            # Local chooser preference only; saved-copy/export helpers copy only
            # referenced media and documents, never this private source location.
            preference = safe_path(self.store.root / 'image-library-source.json')
            preference.write_text(json.dumps({'root': str(root)}), encoding='utf-8')

    def add_image(self):
        if not self.flush_pending_edits():
            return False
        self.end_property_group()
        if self.store is None:
            self.error = 'Save this lesson in a local folder before inserting images.'
            self.refresh(); return False
        capture = self.session.teacher_view()
        try:
            picker = ImagePicker(self, library_root=self.image_library_root(), decoder=decode_image,
                                 remember_library=self.remember_image_library)
        except Exception:
            self.error = 'The image chooser could not open. Check this lesson’s local image storage and try again.'
            self.refresh(); return False
        if picker.exec() != ImagePicker.DialogCode.Accepted or picker.prepared is None:
            return False
        return self.insert_prepared_image(picker.prepared, capture)

    def insert_prepared_image(self, prepared, capture=None):
        """One pinned add command, with bytes durable before document publication."""
        if not self.flush_pending_edits():
            return False
        self.end_property_group()
        captured = capture or self.session.teacher_view()
        try:
            current = self.session.teacher_view()
            if (current['revision'], current['token'], current['page_id']) != (
                    captured['revision'], captured['token'], captured['page_id']):
                raise ValueError('The Board changed while choosing an image. Open Add image again for the current page.')
            if self.store is None:
                raise ValueError('A local lesson folder is required to retain the image.')
            # Qt must also be able to decode it before it becomes a Board object.
            decode_image(prepared.data)
            media_root = self.store.root / 'media'
            for name in ('media.sqlite3', 'blobs'):
                safe_path(media_root / name)
            media = MediaStore(safe_path(media_root))
            record = import_prepared(media, prepared)
            page = page_from(captured)
            scale = min(page['width'] * .6 / prepared.width, page['height'] * .6 / prepared.height, 1)
            width, height = prepared.width * scale, prepared.height * scale
            reference = {key: record[key] for key in ('asset_id', 'version_id', 'sha256')}
            value = new_object('image', x=(page['width']-width)/2, y=(page['height']-height)/2,
                               width=width, height=height, image_ref=reference)
            self.session.teacher_apply([dict(op='add_object', page_id=page['id'], object=value)],
                                       expected_revision=captured['revision'], expected_token=captured['token'])
            self.selected = value['id']
            self.set_tool(False, 'Select / move')
            self.error = ''; self.refresh(); self.select(value['id'])
            self.save_timer.start(300)
            return True
        except Exception as error:
            self.error = 'Image was not inserted: ' + str(error)
            self.refresh(); return False

    def select(self, object_id):
        if not self.flush_pending_edits():
            return False
        self.end_property_group()
        self.selected = object_id
        self.selection_view = self.session.teacher_view()
        value = next((o for o in page_from(self.selection_view)['objects'] if o['id'] == object_id), None)
        self._loading_fields = True
        self.text.setEnabled(bool(value and value['type'] == 'text' and not value['locked']))
        self.font_size.setEnabled(bool(value and value['type'] == 'text' and not value['locked']))
        self.aspect_lock.setVisible(bool(value and value['type'] == 'image'))
        self.aspect_lock.setChecked(self.is_aspect_locked(object_id))
        self.aspect_lock.setEnabled(bool(value and not value['locked']))
        for spin in self.fields.values():
            spin.setEnabled(bool(value and not value['locked']))
        if value:
            for key, spin in self.fields.items():
                spin.setValue(value[key])
            self.text.setPlainText(value.get('text', ''))
            self.font_size.setValue(round(value.get('font_size', 40)))
        else:
            self.text.clear()
        self._loading_fields = False
        return True

    def apply_properties(self):
        """Compatibility entry point; editing widgets now schedule this automatically."""
        return self.flush_pending_edits()

    def is_aspect_locked(self, object_id):
        value = next((o for o in page_from(self.session.teacher_view())['objects'] if o['id'] == object_id), None)
        return bool(value and value['type'] == 'image' and self.aspect_locks.get(object_id, True))

    def set_aspect_lock(self, checked):
        if self._loading_fields:
            return
        if not self.flush_pending_edits():
            with QSignalBlocker(self.aspect_lock):
                self.aspect_lock.setChecked(self.is_aspect_locked(self.selected))
            return
        self.end_property_group()
        self.aspect_locks[self.selected] = bool(checked)

    def reload_selected_fields(self):
        """Explicitly discard a stale form draft and load the current object."""
        self.property_timer.stop(); self.group_timer.stop()
        self._pending_fields.clear(); self._pending_view = None; self._property_group = None
        self.error = ''
        self.select(self.selected)
        self.refresh()

    def queue_property_edit(self, field):
        if self._loading_fields or self.refreshing or self._committing_properties or self.selection_view is None:
            return
        value = next((o for o in page_from(self.selection_view)['objects'] if o['id'] == self.selected), None)
        if not value or value['locked']:
            return
        if self._pending_view is None:
            self._pending_view = self.selection_view
        self._pending_fields.add(field)
        if field in ('width', 'height') and self.is_aspect_locked(self.selected):
            ratio = value['width'] / value['height']
            width = self.fields['width'].value() if field == 'width' else self.fields['height'].value() * ratio
            height = width / ratio
            factor = max(.1 / width, .1 / height, min(1.0, 100000 / width, 100000 / height))
            width, height = width * factor, height * factor
            with QSignalBlocker(self.fields['width']), QSignalBlocker(self.fields['height']):
                self.fields['width'].setValue(width); self.fields['height'].setValue(height)
            self._pending_fields.update(('width', 'height'))
        if self._property_group is None:
            self._property_group = str(uuid.uuid4())
        self.property_timer.start(120)
        self.group_timer.start(700)

    def end_property_group(self):
        self.group_timer.stop()
        if self._pending_fields and not self.flush_pending_edits():
            return False
        self._property_group = None
        return True

    def flush_pending_edits(self):
        """Commit the captured draft, or retain it and refuse the dependent action."""
        if not self._pending_fields or self._committing_properties:
            return True
        self.property_timer.stop()
        self._committing_properties = True
        view = self._pending_view
        try:
            page = page_from(view)
            value = next(o for o in page['objects'] if o['id'] == self.selected)
            changes = {}
            if self._pending_fields & {'width', 'height'}:
                changes.update(size_changes(value, self.fields['width'].value(), self.fields['height'].value()))
            for field in self._pending_fields & {'x', 'y'}:
                changes[field] = self.fields[field].value()
            if value['type'] == 'text':
                if 'text' in self._pending_fields:
                    changes['text'] = self.text.toPlainText()
                if 'font_size' in self._pending_fields:
                    changes['font_size'] = self.font_size.value()
            changes = {key: change for key, change in changes.items() if change != value[key]}
            current = self.session.teacher_view()
            if current['revision'] != view['revision'] or current['token'] != view['token']:
                raise BoardValidationError('The board changed while you edited. Your draft is retained; reload selected fields before trying again.')
            if changes:
                self.session.teacher_apply([dict(op='update_object', page_id=page['id'], object_id=value['id'], changes=changes)],
                                           expected_revision=view['revision'], expected_token=view['token'],
                                           edit_group=self._property_group)
            self._pending_fields.clear(); self._pending_view = None
            self.selection_view = self.session.teacher_view()
            self.error = ''
            self.refresh()
            if self.session.teacher_view()['dirty']:
                self.save_timer.start(300)
            return True
        except Exception as error:
            self.error = str(error); self.refresh()
            return False
        finally:
            self._committing_properties = False

    def set_tool(self, audience, mode):
        if audience and self.session.pupil_view()['frozen']:
            return
        if not self.flush_pending_edits():
            self.refresh(); return
        self.end_property_group()
        (self.pupil_mode if audience else self.mode).setCurrentText(mode)
        self.tool_changed(audience)

    def tool_changed(self, audience):
        canvas = self.pupil_canvas if audience else self.teacher_canvas
        canvas.cancel_gesture()
        combo, buttons = (self.pupil_mode, self.pupil_tools) if audience else (self.mode, self.teacher_tools)
        for label, button in buttons.items():
            button.setChecked(combo.currentText() == label)

    def add_page(self):
        if not self.flush_pending_edits():
            return
        self.end_property_group()
        count = len(self.session.teacher_view()['document']['pages'])
        page = new_page(f'Page {count+1}')
        self.apply([dict(op='add_page', page=page)])
        view = self.session.teacher_view()
        self.run(lambda: self.session.teacher_navigate(page['id'], expected_token=view['token']))

    def navigate(self, delta, audience=False):
        if not self.flush_pending_edits():
            return
        self.end_property_group()
        view = self.session.pupil_view() if audience else self.session.teacher_view()
        pages = view['document']['pages']; index = next(i for i, p in enumerate(pages) if p['id'] == view['page_id'])
        destination = pages[(index+delta) % len(pages)]['id']
        method = self.session.pupil_navigate if audience else self.session.teacher_navigate
        self.selected = None
        self.run(lambda: method(destination, expected_token=view['token']), save=False)
        self.select(None)

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
        if not self.flush_pending_edits():
            return
        self.end_property_group()
        view = self.session.teacher_view()
        self.run(lambda: self.session.freeze(expected_token=view['token']), save=False)

    def resume(self):
        if not self.flush_pending_edits():
            return
        self.end_property_group()
        view = self.session.teacher_view()
        self.run(lambda: self.session.resume(expected_token=view['token']), save=False)

    def undo(self):
        if not self.flush_pending_edits():
            return
        self.end_property_group()
        view = self.session.teacher_view()
        self.run(lambda: self.session.teacher_undo(expected_revision=view['revision'], expected_token=view['token']))
        if not self.error:
            self.select(self.selected)

    def redo(self):
        if not self.flush_pending_edits():
            return
        self.end_property_group()
        view = self.session.teacher_view()
        self.run(lambda: self.session.teacher_redo(expected_revision=view['revision'], expected_token=view['token']))
        if not self.error:
            self.select(self.selected)

    def rename(self):
        if not self.flush_pending_edits():
            return False
        self.end_property_group()
        view = self.session.teacher_view()
        if self.name.text() != view['document']['title']:
            source = self.name_capture or view
            # Object edits may advance a live session while a name is drafted.
            # Rebase only if the same lesson/session still has the captured name;
            # a competing rename remains a stale action requiring review.
            if (source['document']['lesson_id'] == view['document']['lesson_id']
                    and source['document']['title'] == view['document']['title']
                    and source['token'].split(':')[0] == view['token'].split(':')[0]):
                source = view
            self.apply([dict(op='rename_lesson', title=self.name.text())], (source['revision'], source['token']))
            if self.error:
                self.name_capture = None
                return False
        self.name.setModified(False); self.name_capture = None; self.refresh()
        return True

    def capture_name_edit(self, _text):
        if self.name_capture is None:
            self.name_capture = self.session.teacher_view()

    def autosave(self):
        self.save_timer.stop()
        if not self.flush_pending_edits():
            return False
        view = self.session.teacher_view()
        if view['dirty']:
            self.run(lambda: self.session.save(expected_token=view['token']), save=False)
        saved = not self.session.teacher_view()['dirty']
        if saved:
            self.sync_saved_lessons()
        return saved

    def sync_saved_lessons(self):
        """Discovery failures are separate from successful durable lesson saves."""
        if self.store is None or not is_catalogue_lesson(self.store.root):
            return True
        try:
            result = refresh_saved_lesson_access((self.store.root,))
            self.catalogue_error = ('Saved lessons access needs attention: ' + '; '.join(result['warnings'])
                                    if result['warnings'] else '')
        except Exception as error:
            self.catalogue_error = 'Lesson saved, but Saved lessons could not be updated: ' + str(error)
            self.refresh()
            return False
        self.refresh()
        return True

    def save_now(self):
        if not self.flush_pending_edits():
            return False
        self.end_property_group()
        if self.name.isModified() and not self.rename():
            return False
        return self.autosave()

    def open_lesson_folder(self):
        if not self.save_now():
            return
        try:
            if self.store is None:
                raise ValueError('No lesson folder is configured.')
            result = refresh_saved_lesson_access((self.store.root,))
            self.catalogue_error = ('Saved lessons access needs attention: ' + '; '.join(result['warnings'])
                                    if result['warnings'] else '')
            if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(result['root']))):
                raise ValueError('The Saved lessons folder could not be opened.')
            self.error = ''; self.refresh()
        except Exception as error:
            self.error = str(error); self.refresh()

    def save_copy(self):
        if self.session.teacher_view()['frozen']:
            self.error = 'Resume the pupil display before opening a separate lesson copy. Your frozen view is unchanged.'
            self.refresh(); return False
        if not self.save_now():
            return False
        title, accepted = QInputDialog.getText(self, 'Save a copy',
                                              'Name the separate lesson copy. It will open after saving:',
                                              text=self.session.teacher_view()['document']['title'] + ' — copy')
        if not accepted:
            return False
        try:
            destination = new_saved_lesson_directory(title)
        except Exception as error:
            self.error = str(error); self.refresh(); return False
        return self._save_copy(destination, title)

    def _save_copy(self, destination, title):
        if self.session.teacher_view()['frozen']:
            self.error = 'Resume the pupil display before opening a separate lesson copy. Your frozen view is unchanged.'
            self.refresh(); return False
        if not self.save_now():
            return False
        try:
            replacement, store, resolver = copy_saved_lesson(self.session, self.store.root, destination, title)
        except Exception as error:
            self.error = str(error); self.refresh(); return False
        previous = self.session
        self.session, self.store, self.resolver = replacement, store, resolver
        previous.close()
        self.aspect_locks.clear(); self.selected = None; self.selection_view = None
        self.name.setModified(False); self.name_capture = None
        self.recovery_notice = False; self.error = ''
        self.refresh(); self.select(None)
        self.sync_saved_lessons()
        return True

    def reopen(self):
        if self.session.teacher_view()['frozen']:
            self.error = 'Resume the pupil display before reopening the lesson. Your frozen view is unchanged.'
            self.refresh(); return
        if not self.save_now():
            return
        self.save_timer.stop()
        self.run(self._reopen, save=False)

    def _reopen(self):
        validate_candidate_storage(self.store.root)
        replacement = BoardSession.open(BoardStore(self.store.root), image_resolver=self.resolver)
        previous = self.session
        self.session = replacement
        previous.close()
        self.aspect_locks.clear()
        self.recovery_notice = replacement.teacher_view().get('recovery_status') == 'recovered_previous'
        self.name.setText(replacement.teacher_view()['document']['title']); self.name.setModified(False)
        self.name_capture = None; self.selected = None; self.selection_view = None
        self.select(None)

    def set_zoom(self, value):
        self.teacher_canvas.zoom = value; self.teacher_canvas.fit()

    def move_pupil(self):
        screen = QGuiApplication.screens()[self.screens.currentIndex()]
        self.pupil.show(); self.show_pupil.setChecked(True)
        self.pupil.windowHandle().setScreen(screen); self.pupil.move(screen.geometry().topLeft())

    def closeEvent(self, event):
        if not self.flush_pending_edits():
            event.ignore(); return
        self.save_now()
        if self.session.teacher_view()['dirty'] or self.name.isModified():
            choice = QMessageBox.question(self, 'Unsaved lesson', 'The latest changes could not be saved. Close and discard those unsaved changes?',
                                          QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
                                          QMessageBox.StandardButton.Cancel)
            if choice != QMessageBox.StandardButton.Discard:
                event.ignore(); return
        self.save_timer.stop(); self.property_timer.stop(); self.group_timer.stop()
        self.session.close(); self.pupil.hide(); event.accept()


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
