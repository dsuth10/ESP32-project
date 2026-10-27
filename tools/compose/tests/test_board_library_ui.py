"""Native, offline teacher resource-library management flows."""
import os
from pathlib import Path
import sys

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtWidgets import QDialog, QLineEdit, QTextEdit

import board_agent_ui as ui
from test_board_agent_ui import app, editor, generated_image


def choose_first(panel):
    assert panel.results.count(), panel.progress.text()
    panel.choose(panel.results.item(0))


def test_library_filters_reasons_and_thumbnail_are_visible(editor):
    panel = editor.agent_panel
    record, _ = generated_image(panel)
    panel.library.catalogue.update_metadata(record['version_id'], title='Water-cycle diagram',
        description='Evaporation and condensation', topics=['Science'], year_levels=['5'], tags=['water cycle'])
    panel.library.approve(record['version_id'])
    panel.resource_type.setCurrentText('Images')
    panel.topic_filter.setText('science')
    panel.year_filter.setCurrentText('Year 5')
    panel.review_filter.setCurrentText('Approved')
    panel.query.setText('condensation')
    panel.search()
    assert len(panel.records) == 1, panel.progress.text()
    assert panel.records[0]['version_id'] == record['version_id']
    item = panel.results.item(0)
    assert 'approved' in item.text() and 'condensation' in item.text().casefold()
    assert not item.icon().isNull()
    assert record['version_id'] in item.toolTip()
    panel.year_filter.setCurrentText('Year 4'); panel.search()
    assert panel.results.count() == 0
    assert 'filters' in panel.progress.text()


def test_edit_details_dialog_saves_local_corrections(editor, monkeypatch):
    panel = editor.agent_panel
    record, _ = generated_image(panel)
    panel.query.clear(); panel.search(); choose_first(panel)

    def edit(dialog):
        assert 'Resource details' in dialog.windowTitle()
        dialog.findChild(QLineEdit, 'resource_title').setText('Our class water-cycle diagram')
        dialog.findChild(QTextEdit, 'resource_description').setPlainText('Corrected cloud labels')
        dialog.findChild(QLineEdit, 'resource_tags').setText('water, clouds')
        dialog.findChild(QLineEdit, 'resource_topics').setText('Science')
        dialog.findChild(QLineEdit, 'resource_years').setText('5, 6')
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(QDialog, 'exec', edit)
    panel.edit_resource_button.click()
    saved = panel.library.catalogue.get_resource_by_version(record['version_id'])
    assert saved['title'] == 'Our class water-cycle diagram', panel.progress.text()
    assert saved['description'] == 'Corrected cloud labels'
    assert saved['tags'] == ['water', 'clouds'] and saved['topics'] == ['Science']
    assert saved['year_levels'] == ['5', '6']
    assert saved['review_state'] == record['review_state']
    assert saved['image_ref'] == record['image_ref']


def test_remembered_names_pin_replace_and_forget_exact_versions(editor, monkeypatch):
    panel = editor.agent_panel
    record, _ = generated_image(panel)
    panel.search(); choose_first(panel)
    monkeypatch.setattr(ui.QInputDialog, 'getText', lambda *args, **kwargs: ('our usual diagram', True))
    panel.remember_button.click()
    saved = panel.library.catalogue.get_resource_by_version(record['version_id'])
    assert saved['remembered_names'] == ['our usual diagram']
    panel.query.setText('our usual diagram'); panel.search(); choose_first(panel)
    assert 'Remembered: our usual diagram' in panel.results.item(0).text()
    monkeypatch.setattr(ui.QInputDialog, 'getItem', lambda *args, **kwargs: ('our usual diagram', True))
    panel.forget_button.click()
    assert not panel.library.catalogue.get_resource_by_version(record['version_id'])['remembered_names']


def test_management_review_filters_never_select_rejected_for_request(editor, monkeypatch):
    panel = editor.agent_panel
    record = panel.library.catalogue.save_resource('document', 'Rejected labels', state='rejected')
    panel.review_filter.setCurrentText('Rejected'); panel.search(); choose_first(panel)
    panel.preparer.dataset = {'old': 'data'}; panel.preparer.chart_spec = {'old': 'chart'}
    choose_first(panel)
    assert panel.library_record['version_id'] == record['version_id']
    assert panel.selected_resource is None
    assert panel.preparer.dataset is None and panel.preparer.chart_spec is None
    assert 'management only' in panel.progress.text()
    monkeypatch.setattr(ui.QInputDialog, 'getText', lambda *args, **kwargs: ('labels needing repair', True))
    panel.remember_choice()
    assert panel.library.catalogue.get_resource_by_version(record['version_id'])['remembered_names']
    assert panel.library.catalogue.auto_select('labels needing repair') is None


def test_clear_or_search_removes_previously_queued_dataset_and_chart(editor):
    panel = editor.agent_panel
    for clear in (panel.clear_choice, panel.search):
        panel.preparer.dataset = {'old': 'data'}; panel.preparer.chart_spec = {'old': 'chart'}
        clear()
        assert panel.preparer.dataset is None and panel.preparer.chart_spec is None


def test_missing_thumbnail_is_reported_without_claiming_available_bytes(editor, monkeypatch):
    panel = editor.agent_panel
    generated_image(panel)
    monkeypatch.setattr(panel.library, 'prepare_record', lambda *args: (_ for _ in ()).throw(ValueError('Missing bytes')))
    panel.query.setText('Generated class diagram')
    panel.search()
    assert panel.results.count() == 1
    assert 'Thumbnail unavailable locally' in panel.results.item(0).text()
    assert panel.results.item(0).icon().isNull()


def test_cancelled_details_and_name_dialogs_preserve_record(editor, monkeypatch):
    panel = editor.agent_panel
    record, _ = generated_image(panel)
    panel.search(); choose_first(panel)
    before = panel.library.catalogue.get_resource_by_version(record['version_id'])
    monkeypatch.setattr(QDialog, 'exec', lambda *args: QDialog.DialogCode.Rejected)
    panel.edit_resource()
    monkeypatch.setattr(ui.QInputDialog, 'getText', lambda *args, **kwargs: ('ignored', False))
    panel.remember_choice()
    assert panel.library.catalogue.get_resource_by_version(record['version_id']) == before
