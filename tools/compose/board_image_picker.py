"""Teacher-only offline image chooser with an explicit preview before insertion."""
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTabWidget, QWidget, QLineEdit, QListWidget, QFileDialog, QDialogButtonBox)

from board_images import SavedImageLibrary, prepare_file


class ImagePicker(QDialog):
    def __init__(self, parent, *, library_root, decoder, remember_library=None):
        super().__init__(parent)
        self.setWindowTitle('Add image to this page')
        self.resize(720, 720)
        self.prepared, self.library = None, None
        self.decoder, self.remember_library = decoder, remember_library
        self.records, self.assets = [], []
        layout = QVBoxLayout(self)
        intro = QLabel('Choose a saved image version or a local PNG, JPEG or WebP file. '
                       'A copy stays with this lesson for offline reopening.')
        intro.setWordWrap(True); layout.addWidget(intro)
        self.tabs = QTabWidget(); layout.addWidget(self.tabs)
        saved = QWidget(); saved_layout = QVBoxLayout(saved)
        self.tabs.addTab(saved, 'Saved image library')
        source_row = QHBoxLayout(); saved_layout.addLayout(source_row)
        self.source = QLabel(); self.source.setWordWrap(True); source_row.addWidget(self.source, 1)
        choose = QPushButton('Choose library folder'); choose.clicked.connect(self.choose_library)
        source_row.addWidget(choose)
        self.search = QLineEdit(); self.search.setPlaceholderText('Search saved titles and tags')
        self.search.textChanged.connect(self.refresh_assets); saved_layout.addWidget(self.search)
        self.asset_list = QListWidget(); self.asset_list.setMaximumHeight(130)
        self.asset_list.currentRowChanged.connect(self.select_asset); saved_layout.addWidget(self.asset_list)
        self.catalogue_notice = QLabel(); self.catalogue_notice.setWordWrap(True)
        saved_layout.addWidget(self.catalogue_notice)
        saved_layout.addWidget(QLabel('Choose a saved version (latest 500 plus canonical):'))
        self.version_list = QListWidget(); self.version_list.setMaximumHeight(100)
        self.version_list.currentRowChanged.connect(self.select_version); saved_layout.addWidget(self.version_list)
        local = QWidget(); local_layout = QVBoxLayout(local)
        self.tabs.addTab(local, 'Local file')
        file_button = QPushButton('Choose local image file'); file_button.clicked.connect(self.choose_file)
        local_layout.addWidget(file_button)
        local_layout.addWidget(QLabel('Supported: PNG, JPEG, WebP · up to 20 MiB and 25 megapixels.'))
        self.file_label = QLabel('No file chosen'); self.file_label.setWordWrap(True); local_layout.addWidget(self.file_label)
        self.preview = QLabel('Choose an image to preview'); self.preview.setMinimumHeight(180)
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter); layout.addWidget(self.preview, 1)
        self.details = QLabel(); self.details.setWordWrap(True); layout.addWidget(self.details)
        self.message = QLabel(); self.message.setWordWrap(True); layout.addWidget(self.message)
        for label in (self.source, self.file_label, self.details, self.message):
            label.setTextFormat(Qt.TextFormat.PlainText)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        self.insert_button = buttons.addButton('Insert on this page', QDialogButtonBox.ButtonRole.AcceptRole)
        self.insert_button.setEnabled(False); buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.tabs.currentChanged.connect(self.clear_choice)
        self.load_library(library_root)

    def clear_choice(self, *_):
        self.prepared = None; self.insert_button.setEnabled(False)
        self.preview.clear(); self.preview.setText('Choose an image to preview')
        self.details.clear(); self.message.clear()
        # Re-selecting a tab must explicitly preview its own source, never insert
        # an image left over from the other tab.
        if self.tabs.currentIndex() == 0:
            self.select_version(self.version_list.currentRow())

    def show_choice(self, prepared):
        pixmap = self.decoder(prepared.data)
        self.preview.setPixmap(pixmap.scaled(620, 230, Qt.AspectRatioMode.KeepAspectRatio,
                                            Qt.TransformationMode.SmoothTransformation))
        self.prepared = prepared; self.insert_button.setEnabled(True); self.message.clear()
        caption = f'{prepared.title} · {prepared.width} × {prepared.height} pixels'
        if prepared.versions:
            record = prepared.versions[-1]
            caption += '\nSaved version ' + record['version_id'][:8]
            attribution = record['source'].get('attribution') or record['source'].get('creator')
            if attribution:
                caption += ' · ' + str(attribution)
            if record['source'].get('licence'):
                caption += ' · ' + str(record['source']['licence'])
        self.details.setText(caption)

    def load_library(self, root):
        self.library = None
        self.source.setText('Library folder: ' + str(root))
        try:
            self.library = SavedImageLibrary(root)
            self.refresh_assets()
        except Exception as error:
            self.clear_choice(); self.asset_list.clear(); self.version_list.clear()
            self.message.setText(str(error) + '\nChoose your companion image-library data folder. '
                                 'Browsing is read-only and does not create an empty library.')

    def choose_library(self):
        root = QFileDialog.getExistingDirectory(self, 'Choose saved image library folder')
        if root:
            self.load_library(Path(root))
            if self.library and self.remember_library:
                try:
                    self.remember_library(self.library.root)
                except Exception:
                    self.message.setText('Library opened. Its location could not be remembered for next time.')

    def refresh_assets(self):
        self.prepared = None; self.insert_button.setEnabled(False)
        self.asset_list.blockSignals(True); self.asset_list.clear()
        try:
            self.assets = self.library.assets(self.search.text()) if self.library else []
            self.asset_list.addItems([record['title'] for record in self.assets])
            self.catalogue_notice.setText('Showing up to 500 matching images. Narrow your search to find older images.'
                                           if len(self.assets) == 500 else '')
        except Exception:
            self.assets = []
            self.message.setText('The saved library could not be read. Choose its folder again.')
        finally:
            self.asset_list.blockSignals(False)
        self.select_asset(-1)
        if self.assets:
            self.asset_list.setCurrentRow(0)
        elif self.library:
            self.message.setText('No matching saved images. Choose another library or use Local file.')

    def select_asset(self, index):
        self.records = []; self.version_list.blockSignals(True); self.version_list.clear()
        try:
            if 0 <= index < len(self.assets):
                asset = self.assets[index]
                self.records = self.library.versions(asset['asset_id'])
                self.version_list.addItems([record['title'] + ' · ' + record['version_id'][:8]
                    + (' · canonical' if record['version_id'] == asset['canonical_version_id'] else '')
                    for record in self.records])
        except Exception:
            self.message.setText('Saved versions could not be read. Choose the image again.')
        finally:
            self.version_list.blockSignals(False)
        self.select_version(-1)
        if self.records:
            canonical = self.assets[index]['canonical_version_id']
            preferred = next((i for i, row in enumerate(self.records) if row['version_id'] == canonical), 0)
            self.version_list.setCurrentRow(preferred)

    def select_version(self, index):
        self.prepared = None; self.insert_button.setEnabled(False)
        self.preview.clear(); self.details.clear()
        if not 0 <= index < len(self.records):
            return
        try:
            self.show_choice(self.library.prepare(self.records[index]))
        except Exception as error:
            self.message.setText(str(error))

    def choose_file(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Choose image file', '',
                                             'Images (*.png *.jpg *.jpeg *.webp);;All files (*)')
        if not path:
            return
        self.prepared = None; self.insert_button.setEnabled(False)
        self.preview.clear(); self.details.clear(); self.file_label.setText(Path(path).name)
        try:
            self.show_choice(prepare_file(Path(path)))
        except Exception as error:
            self.message.setText(str(error))
