"""Teacher-only Board agent controls; workers never manipulate Qt widgets."""
from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import copy
import hashlib
import uuid

from PySide6.QtCore import QTimer, Qt, QSize, QRectF
from PySide6.QtGui import QFont, QTextDocument, QIcon, QTransform
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QTextEdit, QListWidget, QListWidgetItem, QDialog, QFormLayout, QSpinBox,
    QCheckBox, QDialogButtonBox, QFileDialog, QMessageBox, QGraphicsScene, QGraphicsView, QComboBox)

from board_agent import BoardAgentController, TeachingProfile, load_profile, save_profile, BoardAgentError, result_envelope
from board_library import BoardResourceLibrary
from board_model import canonical_json
from board_runtime import (PrimaryBoardComposer, BoardResourcePreparer, create_resource_service,
                           HermesBoardComposer, HermesService, truthy)
from media_store import MediaStore
from board_recovery import BoardRecoveryStore


def validate_page_layout(document, page_id, *, image_resolver=None):
    page = next(page for page in document['pages'] if page['id'] == page_id)
    for obj in page['objects']:
        frame = QTransform().translate(obj['x'], obj['y']).rotate(obj['rotation']).mapRect(QRectF(0, 0, obj['width'], obj['height']))
        if not QRectF(-.01, -.01, page['width']+.02, page['height']+.02).contains(frame):
            raise BoardAgentError('An object would be clipped at the page edge. The pupil page is unchanged.')
        if obj['type'] == 'image' and image_resolver is not None:
            from board_candidate import decode_image
            try:
                decode_image(image_resolver(obj['image_ref']))
            except Exception:
                raise BoardAgentError('A required image cannot be displayed by this Board. Choose another saved image.') from None
        if obj['type'] != 'text':
            continue
        font = QFont('Segoe UI'); font.setPixelSize(max(1, round(obj['font_size'])))
        text = QTextDocument(); text.setDefaultFont(font); text.setDocumentMargin(0)
        text.setPlainText(obj['text']); text.setTextWidth(obj['width'])
        if text.size().height() > obj['height'] + 1 or text.idealWidth() > obj['width'] + 1:
            raise BoardAgentError('The text needs more room. Shorten the request or choose a simpler layout; the pupil page is unchanged.')
    return True


class AgentPanel(QWidget):
    def __init__(self, owner, *, config=None, resource_root=None, composer=None, library=None):
        super().__init__(owner)
        self.owner = owner
        self.config = dict(config or {'LOCAL_ONLY': True})
        root = Path(resource_root or owner.store.root / 'resource-library')
        self.library = library or BoardResourceLibrary(root)
        self.profile_path = self.library.root.parent / 'teaching-profile.json'
        self.profile_error = ''
        self.library_error = ''
        try:
            self.profile = load_profile(self.profile_path)
        except Exception:
            self.profile = TeachingProfile()
            self.profile_error = 'Saved teaching profile needs repair. Edit and save it before sending a request.'
        self.lesson_media = MediaStore(owner.store.root / 'media')
        self._import_saved_catalogue()
        self.media_service = create_resource_service(self.library, self.config)
        self.preparer = BoardResourcePreparer(self.library, self.lesson_media, self.config, media_service=self.media_service)
        self.recovery_store = BoardRecoveryStore(owner.store.root / 'board-requests')
        self.hermes = None
        if composer is None and truthy(self.config.get('HERMES_ENABLED')) and not truthy(self.config.get('LOCAL_ONLY')):
            self.hermes = HermesService(self.config, self.library.root / 'agent-runtime')
            composer = HermesBoardComposer(self.hermes, recovery_store=self.recovery_store)
        self.composer = composer or PrimaryBoardComposer(self.config)
        self.controller = self._controller()
        self.request_id = None
        self.selected_resource = None
        self.records = []
        self.completed = set()
        self.accepted_preview_versions = {}
        self._speech_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='board-microphone')
        self._speech_future = None
        self._recovery_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='board-recovery')
        self._recovery_future = None
        self._saved_list_state = None
        self._audio = None
        self._closed = False
        layout = QVBoxLayout(self); layout.setContentsMargins(0, 0, 0, 0)
        heading = QHBoxLayout(); layout.addLayout(heading)
        heading.addWidget(QLabel('Board assistant'), 1)
        profile = QPushButton('Teaching profile…'); profile.clicked.connect(self.edit_profile); heading.addWidget(profile)
        self.instruction = QTextEdit(); self.instruction.setMaximumHeight(85)
        self.instruction.setPlaceholderText('Ask for a page or a targeted change. Select an object to refer to it.')
        layout.addWidget(self.instruction)
        self.exact_wording = QLineEdit(); self.exact_wording.setMaxLength(2000)
        self.exact_wording.setPlaceholderText('Exact wording to preserve (optional)'); layout.addWidget(self.exact_wording)
        actions = QHBoxLayout(); layout.addLayout(actions)
        self.send_button = QPushButton('Send Board request'); self.send_button.clicked.connect(self.send); actions.addWidget(self.send_button)
        self.mic_button = QPushButton('PC microphone'); self.mic_button.clicked.connect(self.microphone); actions.addWidget(self.mic_button)
        self.cancel_button = QPushButton('Cancel'); self.cancel_button.clicked.connect(self.cancel); actions.addWidget(self.cancel_button)
        self.preview_button = QPushButton('Review complete page…'); self.preview_button.clicked.connect(self.show_preview)
        self.preview_button.setEnabled(False); layout.addWidget(self.preview_button)
        self.progress = QLabel(self.profile_error or self.library_error or ('Local-only Board · cached resources and local model' if truthy(self.config.get('LOCAL_ONLY')) else 'Ready · requested tasks use configured services'))
        self.progress.setWordWrap(True); layout.addWidget(self.progress)
        layout.addWidget(QLabel('Saved Board requests'))
        self.recovery_requests = QComboBox(); layout.addWidget(self.recovery_requests)
        recovery_actions = QHBoxLayout(); layout.addLayout(recovery_actions)
        self.refresh_request_button = QPushButton('Refresh existing task')
        self.refresh_request_button.clicked.connect(self.refresh_saved_request); recovery_actions.addWidget(self.refresh_request_button)
        self.recover_request_button = QPushButton('Review saved result')
        self.recover_request_button.clicked.connect(self.review_saved_request); recovery_actions.addWidget(self.recover_request_button)
        self.stop_request_button = QPushButton('Cancel saved request')
        self.stop_request_button.clicked.connect(self.stop_saved_request); layout.addWidget(self.stop_request_button)
        self.recovery_note = QLabel(''); self.recovery_note.setWordWrap(True); layout.addWidget(self.recovery_note)
        self.query = QLineEdit(); self.query.setPlaceholderText('Search reusable resources'); self.query.returnPressed.connect(self.search)
        layout.addWidget(self.query)
        self.resource_type = QComboBox(); self.resource_type.addItems(['All resources', 'Images', 'Saved pages', 'Datasets', 'Charts'])
        layout.addWidget(self.resource_type)
        search_row = QHBoxLayout(); layout.addLayout(search_row)
        search = QPushButton('Search'); search.clicked.connect(self.search); search_row.addWidget(search)
        source = QPushButton('Index saved library…'); source.clicked.connect(self.add_source); search_row.addWidget(source)
        self.results = QListWidget(); self.results.setMaximumHeight(135); self.results.setIconSize(QSize(95, 65))
        self.results.itemClicked.connect(self.choose); layout.addWidget(self.results)
        clear = QPushButton('Clear selected resource'); clear.clicked.connect(self.clear_choice); layout.addWidget(clear)
        approve = QPushButton('Approve selected resource for reuse'); approve.clicked.connect(self.approve_choice); layout.addWidget(approve)
        reuse_page = QPushButton('Reuse selected saved page…'); reuse_page.clicked.connect(self.reuse_page); layout.addWidget(reuse_page)
        data = QPushButton('Use chart dataset…'); data.clicked.connect(self.load_dataset); layout.addWidget(data)
        attempts = QPushButton('Review image attempts…'); attempts.clicked.connect(self.review_attempts); layout.addWidget(attempts)
        self.timer = QTimer(self); self.timer.timeout.connect(self.tick); self.timer.start(100)
        self.index_timer = QTimer(self); self.index_timer.setSingleShot(True); self.index_timer.timeout.connect(self._index_batch)
        self.pending_sources = [self.lesson_media.root, self.library.media.root]
        self.index_timer.start(0)
        self.reload_saved_requests()

    def _controller(self):
        return BoardAgentController(self.owner.session, composer=self.composer,
            profile=self.profile, resource_preparer=self.preparer,
            recovery_store=self.recovery_store,
            page_validator=lambda document, page_id: validate_page_layout(document, page_id,
                image_resolver=self.owner.session.resolve_image))

    def session_changed(self):
        self.controller.close()
        self.lesson_media = MediaStore(self.owner.store.root / 'media')
        self._import_saved_catalogue()
        self.preparer = BoardResourcePreparer(self.library, self.lesson_media, self.config, media_service=self.media_service)
        self.recovery_store = BoardRecoveryStore(self.owner.store.root / 'board-requests')
        if isinstance(self.composer, HermesBoardComposer):
            self.composer = HermesBoardComposer(self.hermes, recovery_store=self.recovery_store)
        self.controller = self._controller(); self.request_id = None
        self.preview_button.setEnabled(False)
        self.reload_saved_requests()

    def reload_saved_requests(self):
        """Local enumeration only; opening a lesson never refreshes a remote task."""
        selected = self.recovery_requests.currentData()
        self.recovery_requests.clear()
        try:
            records = self.recovery_store.list_requests()
            for record in records:
                publication = record.get('publication_status', 'blocked')
                status = ('needs attention' if record.get('invalid') or publication == 'applying' else
                          'applied' if publication == 'applied' else
                          'cancelled' if publication == 'cancelled' else record.get('status', 'needs attention'))
                prepared = record.get('prepared') or {}
                try:
                    title = json.loads(prepared.get('context', '{}')).get('instruction', '')[:65]
                except (ValueError, TypeError):
                    title = ''
                self.recovery_requests.addItem(status + ' · ' + (title or record['request_id'][:8]), record['request_id'])
            index = self.recovery_requests.findData(selected)
            if index >= 0:
                self.recovery_requests.setCurrentIndex(index)
            self.recovery_note.setText('Saved locally. Refresh checks the same task; review never submits another request.' if records else 'No saved Board requests in this lesson.')
            if self.hermes is not None:
                bound = {record.get('hermes_request_id') for record in records}
                unbound = [row for row in self.hermes.list_requests() if row['request_id'] not in bound]
                if unbound:
                    self.recovery_note.setText(self.recovery_note.text() + ' Older unbound Hermes receipts need review in the companion Hermes tasks panel; they cannot be applied to this lesson.')
        except Exception:
            self.recovery_note.setText('Saved request records need attention. Manual editing and lesson saving remain available.')

    def _selected_saved_request(self):
        request_id = self.recovery_requests.currentData()
        if not request_id:
            raise BoardAgentError('Choose a saved Board request.')
        return self.recovery_store.get(request_id)

    def _saved_remote_action(self, action):
        if self._recovery_future is not None:
            return
        try:
            if truthy(self.config.get('LOCAL_ONLY')) or self.hermes is None:
                raise BoardAgentError('Remote task checks are unavailable in local-only mode. Saved completed results can still be reviewed.')
            record = self._selected_saved_request()
            if action == 'stop':
                self.recovery_store.update(record['request_id'], publication_status='cancelled')
                if self.request_id == record['request_id']:
                    self.controller.cancel(self.request_id)
            store, service = self.recovery_store, self.hermes
            self._recovery_future = self._recovery_executor.submit(
                store.stop if action == 'stop' else store.refresh, record['request_id'], service, local_only=False)
            self.recovery_note.setText('Checking the existing saved task…' if action == 'refresh' else 'Cancellation requested. The remote task may still be running.')
        except Exception as error:
            self.recovery_note.setText(str(error)[:400])

    def refresh_saved_request(self):
        self._saved_remote_action('refresh')

    def stop_saved_request(self):
        try:
            record = self._selected_saved_request()
            if record.get('publication_status') in {'applying', 'applied'}:
                raise BoardAgentError('This publication has already been claimed. Review its saved outcome.')
            if not record.get('hermes_request_id') or self.hermes is None or truthy(self.config.get('LOCAL_ONLY')):
                self.recovery_store.update(record['request_id'], publication_status='cancelled')
                if self.request_id == record['request_id']:
                    self.controller.cancel(self.request_id)
                self.reload_saved_requests()
                self.recovery_note.setText('Local publication cancelled. No remote termination has been verified.')
                return
            self._saved_remote_action('stop')
        except Exception as error:
            self.recovery_note.setText(str(error)[:400])

    def review_saved_request(self):
        if not self.owner.flush_pending_edits():
            return
        try:
            record = self._selected_saved_request()
            self.request_id = self.controller.recover(record)
            self.preview_button.setEnabled(True)
            self.show_preview()
        except Exception as error:
            self.recovery_note.setText(str(error)[:400])

    def _import_saved_catalogue(self):
        self.library_error = ''
        source = self.owner.store.root / 'catalogue' / 'board_resources.sqlite3'
        if source.is_file():
            try:
                self.library.import_catalogue(source.parent, self.lesson_media.root)
            except Exception:
                self.library_error = 'The imported resource catalogue needs attention. The editable lesson and its cached images remain available.'

    def _index_batch(self):
        if not self.pending_sources or self._closed:
            return
        try:
            result = self.library.index_source(self.pending_sources[0])
            if not result['more']:
                self.pending_sources.pop(0)
        except Exception:
            self.pending_sources.pop(0)
            self.progress.setText('A saved library could not be indexed. Existing local search remains available.')
        if self.pending_sources:
            self.index_timer.start(20)

    def retain_image(self, record, source_root):
        self.library._index(record, source_root)

    def edit_profile(self):
        dialog = QDialog(self); dialog.setWindowTitle('Teaching profile · saved on this computer')
        layout = QFormLayout(dialog)
        year = QSpinBox(); year.setRange(0, 12); year.setValue(self.profile.year_level); layout.addRow('Year level', year)
        instructions = QTextEdit(self.profile.instructions); layout.addRow('Default instructions', instructions)
        illustrative = QCheckBox('Permit clearly labelled illustrative chart data'); illustrative.setChecked(self.profile.allow_illustrative_data)
        layout.addRow(illustrative)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Reset)
        buttons.accepted.connect(dialog.accept); buttons.rejected.connect(dialog.reject)
        buttons.button(QDialogButtonBox.StandardButton.Reset).clicked.connect(lambda: (year.setValue(5), instructions.setPlainText(TeachingProfile().instructions), illustrative.setChecked(False)))
        layout.addRow(buttons)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                profile = TeachingProfile(revision=self.profile.revision + 1, year_level=year.value(),
                    instructions=instructions.toPlainText(), allow_illustrative_data=illustrative.isChecked())
                save_profile(self.profile_path, profile)
                self.profile = profile; self.controller.profile = profile; self.profile_error = ''
                self.progress.setText('Teaching profile saved locally. Future requests use these defaults.')
            except Exception:
                self.progress.setText('The teaching profile could not be saved; previous defaults remain active.')

    def search(self):
        try:
            from board_candidate import decode_image
            kind = {'Images': 'image', 'Saved pages': 'page', 'Datasets': 'dataset', 'Charts': 'chart'}.get(self.resource_type.currentText())
            self.records = self.library.catalogue.search(self.query.text().strip(), resource_types=[kind] if kind else None, limit=8)
            self.results.clear(); self.selected_resource = None
            for index, record in enumerate(self.records):
                item = QListWidgetItem(record['title'] + ' · ' + record['resource_type'] + (' · review needed' if record['review_state'] != 'approved' else ''))
                item.setData(Qt.ItemDataRole.UserRole, index)
                try:
                    if record['resource_type'] == 'image':
                        _, prepared = self.library.prepare_record(record)
                        item.setIcon(QIcon(decode_image(prepared.data)))
                except Exception:
                    item.setText(item.text() + ' · unavailable locally')
                self.results.addItem(item)
            self.progress.setText(f'{len(self.records)} local matches. Select one for the next request.' if self.records else 'No local match. The next request uses the agreed resource route.')
        except Exception:
            self.progress.setText('Resource search is unavailable; the lesson remains editable.')

    def choose(self, item):
        self.selected_resource = self.records[item.data(Qt.ItemDataRole.UserRole)]
        self.progress.setText('Selected exact resource: ' + self.selected_resource['title'])
        try:
            record = self.selected_resource
            if record['resource_type'] == 'dataset':
                from board_resource_policy import validate_dataset
                self.preparer.dataset = validate_dataset(record['metadata']); self.preparer.chart_spec = None
                self.progress.setText('Saved dataset selected. Ask for a chart to use its exact values.')
            elif record['resource_type'] == 'chart':
                from board_resource_policy import validate_dataset
                relation = next(item for item in self.library.catalogue.relationships(record['resource_id'], record['version_id'])
                                if item['relation'] == 'derived_from' and item['source_version_id'] == record['version_id'])
                dataset = self.library.catalogue.get_resource_by_version(relation['target_version_id'])
                self.preparer.dataset = validate_dataset(dataset['metadata'])
                self.preparer.chart_spec = {key: value for key, value in record['metadata'].items() if key in {'kind', 'title', 'colour'}}
                self.progress.setText('Saved chart and its exact dataset selected. Ask for a chart to reuse them.')
            elif record['resource_type'] == 'page':
                self.progress.setText('Saved editable page selected. Use Reuse selected saved page to preview it offline.')
        except Exception:
            self.selected_resource = None
            self.progress.setText('This resource is missing a supported dataset or dependency. Choose another saved version.')

    def clear_choice(self):
        self.selected_resource = None; self.results.clearSelection()

    def approve_choice(self):
        if self.selected_resource:
            try:
                if self.selected_resource['resource_type'] == 'image':
                    self.library.prepare_record(self.selected_resource)
                self.library.approve(self.selected_resource['version_id'])
                self.progress.setText('This exact resource is approved for reuse. Its canonical library choice is unchanged.')
            except Exception:
                self.progress.setText('The selected resource could not be verified locally; it was not approved.')

    def reuse_page(self):
        """An explicit local reuse action uses the same staged agent contract."""
        record = self.selected_resource
        if not record or record['resource_type'] != 'page':
            self.progress.setText('Choose a saved page from the reusable library first.'); return
        if not self.owner.flush_pending_edits():
            return
        try:
            actual = self.library.catalogue.get_resource_by_version(record['version_id'])
            if not actual or actual['review_state'] in {'rejected', 'excluded'}:
                raise BoardAgentError('This saved page is excluded or unavailable.')
            page = copy.deepcopy(actual['metadata']['page'])
            if hashlib.sha256(canonical_json(actual['metadata'])).hexdigest() != actual['content_hash']:
                raise BoardAgentError('This saved page no longer matches its exact content hash.')
            images, seen = [], set()
            for obj in page['objects']:
                if obj['type'] == 'image' and obj['image_ref']['version_id'] not in seen:
                    source = self.library.catalogue.get_resource_by_version(obj['image_ref']['version_id'])
                    if not source or source['image_ref'] != obj['image_ref']:
                        raise BoardAgentError('A saved page image is unavailable.')
                    images.append(self.library.select(source, self.lesson_media))
                    seen.add(obj['image_ref']['version_id'])
            view = self.owner.session.teacher_view()
            current = next(page for page in view['document']['pages'] if page['id'] == view['page_id'])
            commands = [dict(op='remove_object', page_id=current['id'], object_id=obj['id']) for obj in current['objects']]
            commands.append(dict(op='update_page', page_id=current['id'], changes={key: page[key] for key in ('title', 'width', 'height')}))
            for obj in page['objects']:
                obj['id'] = str(uuid.uuid4())
                commands.append(dict(op='add_object', page_id=current['id'], object=obj))
            def local_composer(prepared, report, cancelled):
                return result_envelope(prepared, commands=commands)
            local_composer.remote = False
            self.controller.close()
            self.controller = BoardAgentController(self.owner.session, composer=local_composer, profile=self.profile,
                page_validator=lambda document, page_id: validate_page_layout(document, page_id,
                    image_resolver=self.owner.session.resolve_image))
            prepared = self.controller.prepare('Reuse the selected saved page: ' + record['title'],
                selected_images=images, local_only=True)
            self.request_id = self.controller.start(prepared)
            self.clear_choice()
            self.preview_button.setEnabled(False)
        except BoardAgentError as error:
            self.progress.setText(str(error)[:400])
        except Exception:
            self.progress.setText('The saved page could not be restored completely. The pupil page is unchanged.')

    def add_source(self):
        path = QFileDialog.getExistingDirectory(self, 'Choose saved image library containing media.sqlite3')
        if path:
            self.pending_sources.append(Path(path)); self.index_timer.start(0)
            self.progress.setText('Indexing local metadata in small batches. Source images remain in their existing library.')

    def load_dataset(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Choose a Board dataset JSON', '', 'JSON data (*.json)')
        if not path:
            return
        try:
            from board_resource_policy import validate_dataset
            with Path(path).open('rb') as stream:
                raw = stream.read(65537)
            if len(raw) > 65536:
                raise ValueError()
            self.preparer.dataset = validate_dataset(json.loads(raw.decode('utf-8')))
            self.preparer.chart_spec = None
            self.progress.setText('Dataset selected: ' + self.preparer.dataset['title'] + '. Ask for a chart to use it.')
        except Exception:
            self.progress.setText('Dataset needs supported values, labels, units, source, date and coverage. Previous data was preserved.')

    def review_attempts(self):
        from board_resource_policy import BoardRequestAcquisition
        from PySide6.QtWidgets import QInputDialog
        try:
            pending = BoardRequestAcquisition.unresolved(self.library.root / 'board-attempts')
            if not pending:
                self.progress.setText('No unresolved automatic Board image attempts.'); return
            if self.preparer.media is None:
                self.progress.setText('Reconnect the configured resource service to review the existing image job.'); return
            labels = [item['job_id'] + ' · ' + item['status'] for item in pending]
            selected, accepted = QInputDialog.getItem(self, 'Review the existing image attempt',
                'Choose the exact job you have reviewed in the library/provider account:', labels, editable=False)
            if not accepted:
                return
            item = pending[labels.index(selected)]
            job = self.preparer.media.store.get_job(item['job_id'])
            phase = job.get('phase') if job else None
            outcome = {'preview_ready': 'saved_result_reviewed', 'needs_recovery': 'provider_account_reviewed',
                       'failed': 'pre_dispatch_failure_reviewed'}.get(phase)
            if not outcome:
                self.progress.setText('The existing job is still unresolved. No additional automatic image was authorised.'); return
            answer = QMessageBox.question(self, 'Confirm this exact review',
                'Have you reviewed the saved result or provider outcome for job ' + item['job_id'] +
                '?\nThis clears its automatic-attempt barrier. Billing allocations stay held; it does not retry or release money.',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel, QMessageBox.StandardButton.Cancel)
            if answer != QMessageBox.StandardButton.Yes:
                return
            self.preparer.reconcile_google_attempt(item['request_id'], item['job_id'], outcome=outcome)
            self.progress.setText('Existing job review recorded. Its original receipt and allocation are retained.')
        except BoardAgentError as error:
            self.progress.setText(str(error)[:400])
        except Exception:
            self.progress.setText('The image attempt still needs recovery. Existing receipts and allocations were preserved.')

    def send(self):
        if self.profile_error:
            self.progress.setText(self.profile_error); return
        if not self.owner.flush_pending_edits():
            return
        try:
            if self.selected_resource and self.selected_resource['resource_type'] == 'page':
                self.progress.setText('Use Reuse selected saved page to restore this page offline.'); return
            if self.controller.composer is not self.composer:
                self.controller.close(); self.controller = self._controller()
            view = self.owner.session.teacher_view()
            page = next(page for page in view['document']['pages'] if page['id'] == view['page_id'])
            images, seen = [], set()
            for obj in page['objects']:
                if obj['type'] != 'image' or obj['image_ref']['version_id'] in seen:
                    continue
                seen.add(obj['image_ref']['version_id'])
                version = self.lesson_media.get_version(obj['image_ref']['version_id'])
                if version:
                    item = dict(image_ref=obj['image_ref'], title=version['title'][:200], width=version['width'], height=version['height'])
                    entry = self.library.catalogue.get_resource_by_version(version['version_id'])
                    item['generated_unreviewed'] = version.get('origin') == 'generated' and (not entry or entry['review_state'] != 'approved')
                    if entry and entry['metadata'].get('visual_kind') == 'chart':
                        item['visual_kind'] = 'chart'
                    if version['source'].get('attribution'):
                        item['credit'] = version['source']['attribution']
                    images.append(item)
            prepared = self.controller.prepare(self.instruction.toPlainText(), selected_images=images[:16],
                selected_object_ids=[self.owner.selected] if self.owner.selected else [],
                local_only=truthy(self.config.get('LOCAL_ONLY')),
                required_wording=[self.exact_wording.text()] if self.exact_wording.text() else [])
            if self.selected_resource and self.selected_resource['resource_type'] == 'image':
                self.preparer.choose_for_request(prepared['request_id'], self.selected_resource)
            self.request_id = self.controller.start(prepared)
            self.preview_button.setEnabled(False)
            self.progress.setText('Preparing the complete page. The pupil page stays unchanged.')
        except BoardAgentError as error:
            self.progress.setText(str(error)[:400])
        except Exception:
            self.progress.setText('The Board request could not start. Check its selected object and configured services.')

    def tick(self):
        if self._closed:
            return
        if self._recovery_future and self._recovery_future.done():
            future, self._recovery_future = self._recovery_future, None
            try:
                record = future.result()
                self.reload_saved_requests()
                self.recovery_note.setText(record.get('message', '')[:400] or 'Existing task checked. Review its saved result when complete.')
            except Exception:
                self.recovery_note.setText('The existing task could not be checked. Its saved identity is retained; try Refresh when the connection returns.')
        if self._speech_future and self._speech_future.done():
            future, self._speech_future = self._speech_future, None
            self.mic_button.setEnabled(True)
            try:
                self.instruction.setPlainText(future.result())
                self.progress.setText('Transcription ready. Review it, then send the Board request.')
            except Exception:
                self.progress.setText('Microphone transcription failed. Type the Board request instead.')
        if self._audio and not self._audio.is_recording:
            self._finish_recording()
        if not self.request_id:
            return
        state = self.controller.poll(self.request_id)
        saved_list_state = (self.request_id, state['status'], state['stage'])
        if saved_list_state != self._saved_list_state:
            self._saved_list_state = saved_list_state
            self.reload_saved_requests()
        self.progress.setText(f"{state['message']} · {state['elapsed_seconds']:.1f} s" +
                              (' · continuing beyond the 15-second target' if state['target_exceeded'] and state['status'] == 'working' else ''))
        self.preview_button.setEnabled(state['status'] == 'awaiting_confirmation')
        if state['status'] == 'applied' and self.request_id not in self.completed:
            self.completed.add(self.request_id)
            self.owner.refresh(); self.owner.save_timer.start(300)
            # A request accepted in the complete preview approves only versions
            # actually used, never unrelated drafts or canonical pointers.
            for version_id in self.accepted_preview_versions.pop(self.request_id, ()):
                self.library.approve(version_id)
            try:
                view = self.owner.session.teacher_view()
                page = next(page for page in view['document']['pages'] if page['id'] == view['page_id'])
                self.library.retain_page(page, self.request_id, media_store=self.lesson_media)
            except Exception:
                self.progress.setText(state['message'] + ' Reusable page indexing needs attention; lesson autosave remains active.')
            self.reload_saved_requests()

    def cancel(self):
        if self.request_id:
            self.controller.cancel(self.request_id)
        self.preview_button.setEnabled(False)

    def show_preview(self):
        if not self.request_id:
            return
        state = self.controller.snapshot(self.request_id)
        document = self.controller.preview(self.request_id)
        if state['status'] != 'awaiting_confirmation' or document is None:
            return
        from board_candidate import BoardCanvas
        from board_session import BoardSession
        from board_model import BoardModel
        from types import SimpleNamespace
        dialog = QDialog(self); dialog.setWindowTitle('Review complete Board page')
        layout = QVBoxLayout(dialog)
        reasons = ' / '.join(state['confirmation_reasons'])
        layout.addWidget(QLabel('Review the complete content and image before first presentation. ' + reasons))
        preview_session = BoardSession(BoardModel(document), image_resolver=self.owner.resolver)
        page_id = self.owner.session.teacher_view()['page_id']
        view = preview_session.teacher_view(); view['page_id'] = page_id
        holder = SimpleNamespace(session=preview_session, select=lambda *_: None, selected=None)
        canvas = BoardCanvas(holder, True); canvas.setInteractive(False); canvas.render(view)
        layout.addWidget(canvas)
        effective = QTextEdit(); effective.setReadOnly(True); effective.setMaximumHeight(100)
        effective.setPlainText('Effective teaching context: ' + json.dumps(state['effective_context'], ensure_ascii=False, indent=2))
        layout.addWidget(effective)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        accept = buttons.addButton('Use image and present' if 'first_generated_image_use' in state['confirmation_reasons'] else 'Present this page', QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.accepted.connect(dialog.accept); buttons.rejected.connect(dialog.reject); layout.addWidget(buttons)
        dialog.resize(1050, 720)
        QTimer.singleShot(0, canvas.fit)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            page = next(page for page in document['pages'] if page['id'] == page_id)
            self.accepted_preview_versions[self.request_id] = [obj['image_ref']['version_id']
                for obj in page['objects'] if obj['type'] == 'image'
                and (record := self.library.catalogue.get_resource_by_version(obj['image_ref']['version_id']))
                and record['metadata'].get('origin') == 'generated' and record['review_state'] != 'approved']
            result = self.controller.confirm(self.request_id, state['proposal_digest'])
            if result['status'] != 'applied':
                self.accepted_preview_versions.pop(self.request_id, None)
            self.tick()
        preview_session.close()

    def microphone(self):
        if self._audio:
            self._finish_recording(); return
        try:
            from audio_capture import AudioCapture
            self._audio = AudioCapture(max_duration_sec=30)
            if not self._audio.start_recording():
                self._audio = None; raise ValueError()
            self.mic_button.setText('Stop microphone')
            self.progress.setText('Listening to the PC microphone for a Board request (up to 30 s).')
        except Exception:
            self.progress.setText('The PC microphone is unavailable. Type a Board request instead.')

    def _finish_recording(self):
        audio, self._audio = self._audio, None
        if audio is None:
            return
        self.mic_button.setText('PC microphone'); self.mic_button.setEnabled(False)
        def transcribe():
            from speech_pipeline import SpeechPipeline
            wav, duration, rms = audio.stop_recording()
            local_only = truthy(self.config.get('LOCAL_ONLY'))
            model = self.config.get('LOCAL_WHISPER_MODEL', 'base')
            if local_only and not (Path(model).is_dir() and (Path(model) / 'model.bin').is_file()):
                # A local-only microphone request must never trigger a model
                # download through faster-whisper's convenience model names.
                raise BoardAgentError('Choose an already downloaded local Whisper model before recording in local-only mode.')
            pipeline = SpeechPipeline(groq_api_key=self.config.get('GROQ_API_KEY'), local_model_name=model,
                                      local_only=local_only)
            result = pipeline.transcribe(wav)
            if isinstance(result, tuple):
                result = result[0]
            if not isinstance(result, str) or not result.strip():
                raise ValueError('No transcript.')
            return result[:4000]
        self._speech_future = self._speech_executor.submit(transcribe)

    def close_runtime(self):
        self._closed = True; self.timer.stop(); self.index_timer.stop(); self.controller.close()
        if self._audio:
            self._audio.stop_recording(); self._audio = None
        self._speech_executor.shutdown(wait=False, cancel_futures=True)
        self._recovery_executor.shutdown(wait=False, cancel_futures=True)
