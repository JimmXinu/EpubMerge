#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Jim Miller'
__docformat__ = 'restructuredtext en'

import traceback
from functools import partial

from PyQt4 import QtGui
from PyQt4.Qt import (QDialog, QTableWidget, QMessageBox, QVBoxLayout, QHBoxLayout, QGridLayout,
                      QPushButton, QProgressDialog, QString, QLabel, QCheckBox, QIcon, QTextCursor,
                      QTextEdit, QLineEdit, QInputDialog, QComboBox, QClipboard, QVariant,
                      QProgressDialog, QTimer, QDialogButtonBox, QPixmap, Qt,QAbstractItemView, SIGNAL, QTableWidgetItem )

from calibre.gui2 import error_dialog, warning_dialog, question_dialog, info_dialog
from calibre.gui2.dialogs.confirm_delete import confirm
from calibre.ebooks.metadata import fmt_sidx

from calibre import confirm_config_name
from calibre.gui2 import dynamic

from calibre_plugins.epubsplit.common_utils \
    import (ReadOnlyTableWidgetItem, SizePersistedDialog,
            ImageTitleLayout, get_icon)
        
class SelectLinesDialog(SizePersistedDialog):
    def __init__(self, gui, header, prefs, icon, lines,
                 do_split_fn,
                 save_size_name='epubsplit:update list dialog'):
        SizePersistedDialog.__init__(self, gui, save_size_name)
        self.gui = gui
        self.do_split_fn = do_split_fn
      
        self.setWindowTitle(header)
        self.setWindowIcon(icon)
      
        layout = QVBoxLayout(self)
        self.setLayout(layout)
        title_layout = ImageTitleLayout(self, 'images/icon.png',
                                        header)
        layout.addLayout(title_layout)
        lines_layout = QHBoxLayout()
        layout.addLayout(lines_layout)

        self.lines_table = LinesTableWidget(self)
        lines_layout.addWidget(self.lines_table)

        options_layout = QHBoxLayout()
        
        button_box = QDialogButtonBox(self)
        new_book = button_box.addButton("New Book", button_box.ActionRole)
        new_book.clicked.connect(self.new_book)        
        
        new_book = button_box.addButton("Done", button_box.RejectRole)
        button_box.rejected.connect(self.reject)
        options_layout.addWidget(button_box)
      
        layout.addLayout(options_layout)
      
        # Cause our dialog size to be restored from prefs or created on first usage
        self.resize_dialog()
        self.lines_table.populate_table(lines)


    def new_book(self):
        self.do_split_fn(self.get_selected_linenums_tocs())
        
    def get_selected_linenums_tocs(self):
        return self.lines_table.get_selected_linenums_tocs()

class LinesTableWidget(QTableWidget):

    def __init__(self, parent):
        QTableWidget.__init__(self, parent)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)

    def populate_table(self, lines):
        self.clear()
        self.setAlternatingRowColors(True)
        self.setRowCount(len(lines))
        header_labels = ['HREF', 'Guide', 'Table of Contents'] #, 'extra'
        self.setColumnCount(len(header_labels))
        self.setHorizontalHeaderLabels(header_labels)
        self.horizontalHeader().setStretchLastSection(True)
        self.verticalHeader().hide()

        self.lines={}
        for row, line in enumerate(lines):
            self.populate_table_row(row, line)
            self.lines[row] = line

        self.resizeColumnsToContents()
        self.setMinimumColumnWidth(1, 100)
        self.setMinimumColumnWidth(2, 10)
        self.setMinimumColumnWidth(3, 100)
        self.setMinimumSize(300, 0)

    def setMinimumColumnWidth(self, col, minimum):
        if self.columnWidth(col) < minimum:
            self.setColumnWidth(col, minimum)

    def populate_table_row(self, row, line):

        href = line['href']
        if line['anchor']:
            href = "%s#%s"%(href,line['anchor'])
            
        href_cell = ReadOnlyTableWidgetItem(href)
        href_cell.setData(Qt.UserRole, QVariant(line['num']))
        self.setItem(row, 0, href_cell)

        if 'guide' in line:
            guide = "(%s):%s"%line['guide']
        else:
            guide = ""
        guide_cell = ReadOnlyTableWidgetItem(guide)
        guide_cell.setToolTip("Indicates 'special' pages: copyright, titlepage, etc.")
        self.setItem(row, 1, guide_cell)

        toc_str = "|".join(line['toc'])
        toc_cell = QTableWidgetItem(toc_str)
        toc_cell.setData(Qt.UserRole, QVariant(toc_str))
        toc_cell.setToolTip('''Click and copy hotkey to copy text.
Double-click to edit ToC entry.
Pipes(|) divide different ToC entries to the same place.''')
        self.setItem(row, 2, toc_cell)
      
    def get_selected_linenums_tocs(self):
        # lines = []
        # for row in range(self.rowCount()):
        #     rnum = self.item(row, 0).data(Qt.UserRole).toPyObject()
        #     line = self.lines[rnum]
        #     lines.append(line)
        # return lines
        linenums = []
        changedtocs = {}
        
        for row in self.selectionModel().selectedRows():
            linenum = row.data(Qt.UserRole).toPyObject()
            linenums.append(linenum)
            # changed tocs only.
            if self.item(row.row(),2).data(Qt.UserRole).toPyObject() != self.item(row.row(),2).text():
                changedtocs[linenum] = unicode(self.item(row.row(),2).text()).strip().split('|')

        linenums.sort()
        return linenums, changedtocs


