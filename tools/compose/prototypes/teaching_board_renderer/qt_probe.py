"""THROWAWAY Qt B0 feasibility probe. No networking or user data."""
import argparse
import json
import math
import sys
from pathlib import Path
from PySide6.QtCore import Qt, QTimer, QPointF, QEvent
from PySide6.QtGui import QColor, QPen, QBrush, QPixmap, QPainterPath, QFont, QGuiApplication
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QComboBox, QGraphicsView, QGraphicsScene,
    QGraphicsItem)
from fixture import IMAGE, ProbeState, exercise


class View(QGraphicsView):
    def __init__(self, owner, audience):
        super().__init__()
        self.owner, self.audience, self.points = owner, audience, []
        self.setScene(QGraphicsScene(self))
        self.viewport().setAttribute(Qt.WidgetAttribute.WA_AcceptTouchEvents)
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag if not audience else QGraphicsView.DragMode.NoDrag)

    def render_page(self):
        scene = self.scene()
        scene.clear()
        page = self.owner.state.visible(self.audience)
        scene.setSceneRect(0, 0, page['width'], page['height'])
        scene.setBackgroundBrush(QColor('white'))
        for value in page['objects']:
            kind, w, h = value['type'], value['width'], value['height']
            if kind == 'text':
                item = scene.addText(value['text'], QFont('Segoe UI', value['font_size']))
                item.setDefaultTextColor(QColor(value['colour']))
                item.setTextWidth(w)
            elif kind == 'image':
                pixmap = QPixmap()
                pixmap.loadFromData(IMAGE)
                item = scene.addPixmap(pixmap.scaled(int(w), int(h), Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation))
            elif kind == 'shape':
                draw = scene.addEllipse if value['shape'] == 'ellipse' else scene.addRect
                item = draw(0, 0, w, h, QPen(QColor(value['stroke']), value['stroke_width']), QBrush(QColor(value['fill'])))
            else:
                points = value['points'] if kind == 'ink' else [value['start'], value['end']]
                path = QPainterPath(QPointF(*points[0]))
                for point in points[1:]:
                    path.lineTo(QPointF(*point))
                if kind == 'arrow':
                    a, b = points[0], points[-1]
                    angle = math.atan2(b[1]-a[1], b[0]-a[0])
                    for offset in (-0.5, 0.5):
                        path.moveTo(*b)
                        path.lineTo(b[0]-30*math.cos(angle+offset), b[1]-30*math.sin(angle+offset))
                item = scene.addPath(path, QPen(QColor(value['colour']), value['stroke_width']))
            item.setPos(value['x'], value['y'])
            item.setRotation(value['rotation'])
            item.setData(0, value['id'])
            item.setData(1, kind)
            if not self.audience:
                item.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsMovable | QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.fitInView(scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.fitInView(self.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def allowed(self):
        return not (self.audience and self.owner.state.frozen)

    def sample(self, position):
        point = self.mapToScene(position.toPoint())
        return [point.x(), point.y()]

    def finish_ink(self, source):
        self.owner.state.ink(self.points, source, self.audience)
        self.points = []
        self.owner.refresh()

    def tabletEvent(self, event):
        if not self.allowed():
            event.accept()
            return
        if event.type() == QEvent.Type.TabletPress:
            self.points = [self.sample(event.position())]
        elif event.type() == QEvent.Type.TabletMove:
            self.points.append(self.sample(event.position()))
        elif event.type() == QEvent.Type.TabletRelease:
            self.points.append(self.sample(event.position()))
            self.finish_ink('pen')
        event.accept()

    def viewportEvent(self, event):
        if event.type() in (QEvent.Type.TouchBegin, QEvent.Type.TouchUpdate, QEvent.Type.TouchEnd):
            if self.allowed() and event.points():
                if event.type() == QEvent.Type.TouchBegin:
                    self.points = []
                self.points.append(self.sample(event.points()[0].position()))
                if event.type() == QEvent.Type.TouchEnd:
                    self.finish_ink('touch')
            event.accept()
            return True
        return super().viewportEvent(event)

    def mousePressEvent(self, event):
        if not self.allowed():
            return
        if self.owner.mode.currentText() == 'Erase':
            item = self.itemAt(event.position().toPoint())
            if item and item.data(1) == 'ink':
                self.owner.state.erase(item.data(0), self.audience)
                self.owner.refresh()
        elif self.owner.mode.currentText() == 'Ink' or self.audience:
            self.points = [self.sample(event.position())]
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if not self.allowed():
            return
        if self.points:
            self.points.append(self.sample(event.position()))
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if not self.allowed():
            return
        if self.points:
            self.points.append(self.sample(event.position()))
            self.finish_ink('mouse')
            return
        super().mouseReleaseEvent(event)
        if not self.audience:
            items = self.scene().selectedItems()
            if items:
                item = items[0]
                self.owner.selected = item.data(0)
                original = next(o for o in self.owner.state.visible()['objects'] if o['id'] == self.owner.selected)
                self.owner.edit.setText(original.get('text', ''))
                if (abs(item.pos().x()-original['x']) > 0.01 or abs(item.pos().y()-original['y']) > 0.01):
                    self.owner.state.update(item.data(0), x=item.pos().x(), y=item.pos().y())
                    self.owner.refresh()


class Probe:
    def __init__(self):
        self.state, self.selected = ProbeState(), None
        self.teacher, self.audience = QWidget(), QWidget()
        self.teacher.setWindowTitle('PROTOTYPE — Qt teacher')
        self.audience.setWindowTitle('PROTOTYPE — Qt pupil')
        top = QVBoxLayout(self.teacher)
        controls = QHBoxLayout()
        top.addLayout(controls)
        self.mode = QComboBox()
        self.mode.addItems(['Select / move', 'Ink', 'Erase'])
        controls.addWidget(self.mode)
        for label, command in [('Previous', lambda: self.nav(-1)), ('Next', lambda: self.nav(1)),
                               ('Freeze', self.freeze), ('Resume', self.resume), ('Undo', self.undo)]:
            button = QPushButton(label)
            button.clicked.connect(command)
            controls.addWidget(button)
        self.edit = QLineEdit('Select a text object, then edit here')
        top.addWidget(self.edit)
        edits = QHBoxLayout()
        top.addLayout(edits)
        for label, command in [('Apply text', self.text), ('Larger', lambda: self.resize(1.2)), ('Smaller', lambda: self.resize(0.8))]:
            button = QPushButton(label)
            button.clicked.connect(command)
            edits.addWidget(button)
        self.screens = QComboBox()
        self.screens.addItems([f'Display {i+1}: {s.geometry().width()} × {s.geometry().height()}' for i, s in enumerate(QGuiApplication.screens())])
        edits.addWidget(self.screens)
        move = QPushButton('Move pupil window')
        move.clicked.connect(self.move_pupil)
        edits.addWidget(move)
        self.teacher_view, self.pupil_view = View(self, False), View(self, True)
        top.addWidget(self.teacher_view, 1)
        self.status = QLabel()
        self.status.setWordWrap(True)
        top.addWidget(self.status)
        pupil = QVBoxLayout(self.audience)
        self.pupil_status = QLabel()
        pupil.addWidget(self.pupil_status)
        pupil.addWidget(self.pupil_view, 1)
        nav = QHBoxLayout()
        pupil.addLayout(nav)
        self.pupil_buttons = []
        for label, delta in [('Previous page', -1), ('Next page', 1)]:
            button = QPushButton(label)
            button.clicked.connect(lambda checked=False, d=delta: self.nav(d, True))
            nav.addWidget(button)
            self.pupil_buttons.append(button)
        self.teacher.resize(1100, 760)
        self.audience.resize(850, 550)
        self.teacher.move(30, 30)
        self.audience.move(200, 150)
        self.refresh()

    def refresh(self):
        self.teacher_view.render_page()
        self.pupil_view.render_page()
        self.status.setText('IN MEMORY / NO BACKEND — ' + json.dumps(self.state.summary()))
        self.pupil_status.setText('FROZEN — read only' if self.state.frozen else 'LIVE — draw or navigate; no layout/text edits')
        for button in self.pupil_buttons:
            button.setEnabled(not self.state.frozen)

    def nav(self, delta, audience=False):
        self.state.navigate(delta, audience)
        self.selected = None
        self.refresh()

    def freeze(self):
        self.state.freeze()
        self.refresh()

    def resume(self):
        self.state.resume()
        self.refresh()

    def undo(self):
        self.state.undo()
        self.refresh()

    def text(self):
        if self.selected:
            value = next(o for o in self.state.visible()['objects'] if o['id'] == self.selected)
            if value['type'] == 'text':
                self.state.update(self.selected, text=self.edit.text())
                self.refresh()

    def resize(self, scale):
        if self.selected:
            value = next(o for o in self.state.visible()['objects'] if o['id'] == self.selected)
            self.state.update(self.selected, width=value['width']*scale, height=value['height']*scale)
            self.refresh()

    def move_pupil(self):
        screen = QGuiApplication.screens()[self.screens.currentIndex()]
        self.audience.windowHandle().setScreen(screen)
        self.audience.move(screen.geometry().topLeft())

    def smoke(self, destination):
        destination.mkdir(parents=True, exist_ok=True)
        self.state.update(self.state.visible()['objects'][0]['id'], text='Evaporation — synthetic edit')
        self.state.ink([[200, 700], [400, 650], [600, 710]])
        self.freeze()
        self.state.update(self.state.visible()['objects'][2]['id'], width=520)
        self.refresh()
        self.teacher.grab().save(str(destination/'qt-teacher.png'))
        self.audience.grab().save(str(destination/'qt-pupil-frozen.png'))
        result = dict(route='Qt/PySide6', checks=exercise(), actual_windows=2,
                      displays_available=len(QGuiApplication.screens()), physical_pen_tested=False,
                      physical_touch_tested=False, physical_projector_tested=False, state=self.state.summary())
        (destination/'qt-result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
        print(json.dumps(result), flush=True)
        QApplication.instance().quit()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--smoke', type=Path)
    args = parser.parse_args()
    app = QApplication(sys.argv[:1])
    probe = Probe()
    probe.teacher.show()
    probe.audience.show()
    if args.smoke:
        QTimer.singleShot(1200, lambda: probe.smoke(args.smoke))
    sys.exit(app.exec())
