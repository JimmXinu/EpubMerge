#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division,
                        print_function)

import os
import logging
logger = logging.getLogger(__name__)

__license__   = 'GPL v3'
__copyright__ = '2014, Jim Miller'
__docformat__ = 'restructuredtext en'

import traceback
from functools import partial

from six import text_type as unicode
from six.moves import range

from PyQt5 import QtWidgets as QtGui
from PyQt5.Qt import (QDialog, QTableWidget, QMessageBox, QVBoxLayout, QHBoxLayout, QGridLayout,
                      QPushButton, QProgressDialog, QLabel, QCheckBox, QIcon, QTextCursor,
                      QTextEdit, QLineEdit, QInputDialog, QComboBox, QClipboard,
                      QProgressDialog, QTimer, QDialogButtonBox, QPixmap, Qt,QAbstractItemView,
                      QTableWidgetItem, QGroupBox, QRadioButton )

from calibre.gui2 import error_dialog, warning_dialog, question_dialog, info_dialog
from calibre.gui2 import choose_files
from calibre.ebooks.metadata.epub import get_metadata
from calibre.gui2.dialogs.confirm_delete import confirm
from calibre.ebooks.metadata import fmt_sidx
from calibre.ptempfile import PersistentTemporaryDirectory

from calibre import confirm_config_name
from calibre.gui2 import dynamic

# pulls in translation files for _() strings
try:
    load_translations()
except NameError:
    pass # load_translations() added in calibre 1.9

from calibre_plugins.epubmerge.common_utils \
    import (ReadOnlyTableWidgetItem, SizePersistedDialog,
            ImageTitleLayout, get_icon)

def LoopProgressDialog(gui,
                       book_list,
                       foreach_function,
                       finish_function,
                       init_label=_("Starting..."),
                       win_title=_("Working"),
                       status_prefix=_("Completed so far")):
    ld = _LoopProgressDialog(gui,
                             book_list,
                             foreach_function,
                             init_label,
                             win_title,
                             status_prefix)
    # Mac OS X gets upset if the finish_function is called from inside
    # the real _LoopProgressDialog class.

    # reflect old behavior.
    if not ld.wasCanceled():
        finish_function(book_list)

class _LoopProgressDialog(QProgressDialog):
    '''
    ProgressDialog displayed while fetching metadata for each story.
    '''
    def __init__(self,
                 gui,
                 book_list,
                 foreach_function,
                 init_label=_("Starting..."),
                 win_title=_("Working"),
                 status_prefix=_("Completed so far")):
        QProgressDialog.__init__(self,
                                 init_label,
                                 _('Cancel'), 0, len(book_list), gui)
        self.setWindowTitle(win_title)
        self.setMinimumWidth(500)
        self.book_list = book_list
        self.foreach_function = foreach_function
        self.status_prefix = status_prefix
        self.i = 0

        ## self.do_loop does QTimer.singleShot on self.do_loop also.
        ## A weird way to do a loop, but that was the example I had.
        QTimer.singleShot(0, self.do_loop)
        self.exec_()

    def updateStatus(self):
        self.setLabelText("%s %d of %d"%(self.status_prefix,self.i+1,len(self.book_list)))
        self.setValue(self.i+1)

    def do_loop(self):

        if self.i == 0:
            self.setValue(0)

        book = self.book_list[self.i]
        try:
            self.foreach_function(book)

        except Exception as e:
            book['good']=False
            book['comment']=unicode(e)
            logger.error("Exception: %s:%s"%(book,unicode(e)),exc_info=True)

        self.updateStatus()
        self.i += 1

        if self.i >= len(self.book_list) or self.wasCanceled():
            return self.do_when_finished()
        else:
            QTimer.singleShot(0, self.do_loop)

    def do_when_finished(self):
        # Queues a job to process these books in the background.
        self.setLabelText(_("Starting Merge..."))
        self.setValue(self.i+1)

        self.hide()

class AuthorTableWidgetItem(ReadOnlyTableWidgetItem):
    def __init__(self, text, sort_key):
        ReadOnlyTableWidgetItem.__init__(self, text)
        self.sort_key = sort_key

    #Qt uses a simple < check for sorting items, override this to use the sortKey
    def __lt__(self, other):
        return self.sort_key < other.sort_key

class SeriesTableWidgetItem(ReadOnlyTableWidgetItem):
    def __init__(self, series_name, series_index):
        if series_name:
            text = '%s [%s]' % (series_name, fmt_sidx(series_index))
        else:
            text = ''
        ReadOnlyTableWidgetItem.__init__(self, text)
        self.series_name = series_name
        self.series_index = series_index

    #Qt uses a simple < check for sorting items, override this to use the sortKey
    def __lt__(self, other):
        if self.series_name == other.series_name:
            return self.series_index < other.series_index
        else:
            return self.series_name < other.series_name

class MergeTargetDialog(SizePersistedDialog):
    def __init__(self, gui, header, prefs, icon, books,
                 save_size_name='epubmerge:merge target dialog'):
        SizePersistedDialog.__init__(self, gui, save_size_name)
        self.gui = gui

        self.setWindowTitle(header)
        if icon:
            self.setWindowIcon(icon)
        
        layout = QVBoxLayout(self)
        
        self.merge_group = QGroupBox(_("Select Merge Target"), self)
        group_layout = QVBoxLayout()
        self.merge_group.setLayout(group_layout)
        
        self.overwrite_combo = QComboBox(self)

        self.library_books = {}
        for b in books:
            if b.get('calibre_id') is not None:
                self.library_books[b['calibre_id']] = b
                self.overwrite_combo.addItem(b['title'], b['calibre_id'])
        
        group_layout.addWidget(self.overwrite_combo)
        layout.addWidget(self.merge_group)
        
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
    def get_target_title(self):
        target_id = self.overwrite_combo.currentData()
        return self.library_books[target_id]['title']

    def get_target_id(self):
        target_id = self.overwrite_combo.currentData()
        return target_id

class OrderEPUBsDialog(SizePersistedDialog):
    def __init__(self, gui, header, prefs, icon, books,
                 save_size_name='epubmerge:update list dialog'):
        SizePersistedDialog.__init__(self, gui, save_size_name)
        self.gui = gui

        self.setWindowTitle(header)
        self.setWindowIcon(icon)

        layout = QVBoxLayout(self)
        self.setLayout(layout)
        title_layout = ImageTitleLayout(self, 'images/icon.png',
                                        header)
        layout.addLayout(title_layout)
        books_layout = QHBoxLayout()
        layout.addLayout(books_layout)

        self.books_table = StoryListTableWidget(self)
        books_layout.addWidget(self.books_table)

        button_layout = QVBoxLayout()
        books_layout.addLayout(button_layout)
        spacerItem = QtGui.QSpacerItem(20, 40, QtGui.QSizePolicy.Minimum, QtGui.QSizePolicy.Expanding)
        button_layout.addItem(spacerItem)
        self.move_up_button = QtGui.QToolButton(self)
        self.move_up_button.setToolTip(_('Move selected books up the list'))
        self.move_up_button.setIcon(QIcon(I('arrow-up.png')))
        self.move_up_button.clicked.connect(self.books_table.move_rows_up)
        button_layout.addWidget(self.move_up_button)
        self.remove_button = QtGui.QToolButton(self)
        self.remove_button.setToolTip(_('Remove selected books from the list'))
        self.remove_button.setIcon(get_icon('list_remove.png'))
        self.remove_button.clicked.connect(self.remove_from_list)
        button_layout.addWidget(self.remove_button)
        self.move_down_button = QtGui.QToolButton(self)
        self.move_down_button.setToolTip(_('Move selected books down the list'))
        self.move_down_button.setIcon(QIcon(I('arrow-down.png')))
        self.move_down_button.clicked.connect(self.books_table.move_rows_down)
        button_layout.addWidget(self.move_down_button)
        self.local_upload_button = QtGui.QToolButton(self)
        self.local_upload_button.setToolTip(_('Add EPUBs from PC...'))
        self.local_upload_button.setIcon(get_icon('add_book.png'))
        self.local_upload_button.clicked.connect(self.local_upload)
        button_layout.addWidget(self.local_upload_button)
        spacerItem1 = QtGui.QSpacerItem(20, 40, QtGui.QSizePolicy.Minimum, QtGui.QSizePolicy.Expanding)
        button_layout.addItem(spacerItem1)

        options_layout = QHBoxLayout()

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        options_layout.addWidget(button_box)

        layout.addLayout(options_layout)

        # Cause our dialog size to be restored from prefs or created on first usage
        self.resize_dialog()
        self.books_table.populate_table(books)

    def remove_from_list(self):
        self.books_table.remove_selected_rows()

    def get_books(self):
        return self.books_table.get_books()

    def populate_book_from_local_upload(self, book, db=None, tdir=None):
        try:
            filepath = book['epub']
            with open(filepath, 'rb') as f:
                mi = get_metadata(f)

            book['calibre_id'] = None
            book['title'] = mi.title or _('Unknown')
            book['authors'] = mi.authors or [_('Unknown')]
            book['author_sort'] = mi.author_sort or _('Unknown')
            book['tags'] = mi.tags or []
            book['series'] = mi.series or ''
            book['comments'] = mi.comments or ''
            book['publisher'] = mi.publisher or ''
            book['pubdate'] = mi.pubdate or None
            book['series_index'] = mi.series_index if mi.series else None
            book['languages'] = mi.languages or ['en']
            book['error'] = ''
            book['epub_size'] = os.path.getsize(filepath)

            return book

        except Exception as e:
            book['good'] = False
            book['error'] = str(e)
            raise e

    def _append_book_to_table(self, book_list, db=None, tdir=None):
        failed_files = []
        for book in book_list:
            if book.get('good'):
                row = self.books_table.rowCount()
                self.books_table.setRowCount(row + 1)
                self.books_table.populate_table_row(row, book)
                self.books_table.books[row] = book
            else:
                failed_files.append(f"{os.path.basename(book['epub'])}: {book.get('error') or book.get('comment')}")

        self.books_table.resizeColumnsToContents()

        if failed_files:
            error_dialog(self, _('Error reading files'),
                         _('Could not read metadata from the following files:<br><br>%s') % '<br>'.join(failed_files),
                         show_copy_button=False).exec_()

    def local_upload(self):

        files = choose_files(self, 'epubmerge:local_upload_dialog',
                             _('Choose EPUB files to merge'),
                             filters=[(_('EPUB files'), ['epub'])],
                             all_files=False, select_only_single_file=False)
        if not files:
            return

        book_list = []
        for filepath in files:
            book_list.append({
                'good': True,
                'epub': filepath,
                'epub_size': os.path.getsize(filepath)
            })

        tdir = PersistentTemporaryDirectory(prefix='epubmerge_')
        LoopProgressDialog(self.gui,
                            book_list,
                            partial(self.populate_book_from_local_upload, db=self.gui.current_db, tdir=tdir),
                            partial(self._append_book_to_table,tdir=tdir),
                            init_label=_("Collecting EPUBs for merger..."),
                            win_title=_("Get EPUBs for merge"),
                            status_prefix=_("EPUBs collected"))


class StoryListTableWidget(QTableWidget):

    def __init__(self, parent):
        QTableWidget.__init__(self, parent)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)

    def on_headersection_clicked(self):
        self.setSortingEnabled(True)

    def populate_table(self, books):
        self.clear()
        self.setAlternatingRowColors(True)
        self.setRowCount(len(books))
        header_labels = [_('Title'), _('Author(s)'), _('Series')]
        self.setColumnCount(len(header_labels))
        self.setHorizontalHeaderLabels(header_labels)
        self.horizontalHeader().setStretchLastSection(True)
        #self.verticalHeader().setDefaultSectionSize(24)
        self.verticalHeader().hide()

        self.horizontalHeader().sectionClicked.connect(self.on_headersection_clicked)

        self.books={}
        for row, book in enumerate(books):
            self.populate_table_row(row, book)
            self.books[row] = book

        self.resizeColumnsToContents()
        self.setMinimumColumnWidth(1, 100)
        self.setMinimumColumnWidth(2, 100)
        self.setMinimumColumnWidth(3, 100)
        self.setMinimumSize(300, 0)

    def setMinimumColumnWidth(self, col, minimum):
        if self.columnWidth(col) < minimum:
            self.setColumnWidth(col, minimum)

    def populate_table_row(self, row, book):

        title_cell = ReadOnlyTableWidgetItem(book['title'])
        title_cell.setData(Qt.UserRole, row)
        self.setItem(row, 0, title_cell)

        self.setItem(row, 1, AuthorTableWidgetItem(' & '.join(book['authors']),
                                                   book['author_sort']))

        series_cell = SeriesTableWidgetItem(book['series'],book['series_index'])
        self.setItem(row, 2, series_cell)

    def get_books(self):
        books = []
        for row in range(self.rowCount()):
            rnum = self.item(row, 0).data(Qt.UserRole)
            book = self.books[rnum]
            books.append(book)
        return books

    def remove_selected_rows(self):
        self.setFocus()
        rows = self.selectionModel().selectedRows()
        rows = sorted(rows, key=lambda x: x.row(), reverse=True)
        if len(rows) == 0:
            return
        message = '<p>'+_('Are you sure you want to remove this book from the list?')
        if len(rows) > 1:
            message = '<p>'+_('Are you sure you want to remove the selected %d books from the list?')%len(rows)
        if not confirm(message,'epubmerge_delete_item_again', self):
            return
        first_sel_row = self.currentRow()
        for selrow in rows:
            self.removeRow(selrow.row())
        if first_sel_row < self.rowCount():
            self.select_and_scroll_to_row(first_sel_row)
        elif self.rowCount() > 0:
            self.select_and_scroll_to_row(first_sel_row - 1)

    def select_and_scroll_to_row(self, row):
        self.selectRow(row)
        self.scrollToItem(self.currentItem())

    def move_rows_up(self):
        rows = self.selectionModel().selectedRows()
        if len(rows) == 0:
            return
        selrows = []
        for row in rows:
            selrows.append(row.row())
        selrows.sort()
        first_sel_row = selrows[0]
        if first_sel_row <= 0:
            return
        # Workaround for strange selection bug in Qt which "alters" the selection
        # in certain circumstances which meant move down only worked properly "once"
        for selrow in selrows:
            self.swap_row_widgets(selrow - 1, selrow + 1)
        scroll_to_row = first_sel_row - 1
        if scroll_to_row > 0:
            scroll_to_row = scroll_to_row - 1
        self.scrollToItem(self.item(scroll_to_row, 0))

    def move_rows_down(self):
        self.setFocus()
        rows = self.selectionModel().selectedRows()
        if len(rows) == 0:
            return
        selrows = []
        for row in rows:
            selrows.append(row.row())
        selrows.sort()
        last_sel_row = selrows[-1]
        if last_sel_row == self.rowCount() - 1:
            return
        # Workaround for strange selection bug in Qt which "alters" the selection
        # in certain circumstances which meant move down only worked properly "once"
        for selrow in reversed(selrows):
            self.swap_row_widgets(selrow + 2, selrow)
        scroll_to_row = last_sel_row + 1
        if scroll_to_row < self.rowCount() - 1:
            scroll_to_row = scroll_to_row + 1
        self.scrollToItem(self.item(scroll_to_row, 0))

    def swap_row_widgets(self, src_row, dest_row):
        self.blockSignals(True)
        self.setSortingEnabled(False)
        self.insertRow(dest_row)
        for col in range(0, self.columnCount()):
            self.setItem(dest_row, col, self.takeItem(src_row, col))
        self.removeRow(src_row)
        self.blockSignals(False)

class AddOverDiscardDialog(QDialog):

    def __init__(self, parent, icon, text, over=True):
        QDialog.__init__(self, parent)
        self.state=None

        layout = QVBoxLayout(self)
        self.setLayout(layout)
        self.setWindowTitle(_('UnMerge Epub'))

        label = QLabel(text)
        label.setOpenExternalLinks(True)
        label.setWordWrap(True)
        layout.addWidget(label)

        self.applyall = QCheckBox(_('Apply to all EPUBs?'),self)
        self.applyall.setToolTip(_('Apply the same action to the rest of the EPUBs after this.'))
        layout.addWidget(self.applyall)

        button_box = QDialogButtonBox(self)
        button = button_box.addButton(_("Add"), button_box.AcceptRole)
        button.clicked.connect(self.add)

        if over:
            button = button_box.addButton(_("Overwrite"), button_box.AcceptRole)
            button.clicked.connect(self.over)

        button = button_box.addButton(_("Discard"), button_box.AcceptRole)
        button.clicked.connect(self.discard)
        button_box.accepted.connect(self.accept)

        layout.addWidget(button_box)

    def get_applyall(self):
        return self.applyall.isChecked()

    def add(self):
        self.state="add"

    def over(self):
        self.state="over"

    def discard(self):
        self.state="discard"

