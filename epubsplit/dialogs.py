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
                      QProgressDialog, QTimer, QDialogButtonBox, QPixmap, Qt,QAbstractItemView, SIGNAL )

from calibre.gui2 import error_dialog, warning_dialog, question_dialog, info_dialog
from calibre.gui2.dialogs.confirm_delete import confirm
from calibre.ebooks.metadata import fmt_sidx

from calibre import confirm_config_name
from calibre.gui2 import dynamic

from calibre_plugins.epubsplit.common_utils \
    import (ReadOnlyTableWidgetItem, SizePersistedDialog,
            ImageTitleLayout, get_icon)
        
# class LoopProgressDialog(QProgressDialog):
#     '''
#     ProgressDialog displayed while fetching metadata for each story.
#     '''
#     def __init__(self,
#                  gui,
#                  line_list,
#                  foreach_function,
#                  finish_function,
#                  init_label="Starting...",
#                  win_title="Working",
#                  status_prefix="Completed so far"):
#         QProgressDialog.__init__(self,
#                                  init_label,
#                                  QString(), 0, len(line_list), gui)
#         self.setWindowTitle(win_title)
#         self.setMinimumWidth(500)
#         self.gui = gui
#         self.line_list = line_list
#         self.foreach_function = foreach_function
#         self.finish_function = finish_function
#         self.status_prefix = status_prefix
#         self.i = 0
        
#         ## self.do_loop does QTimer.singleShot on self.do_loop also.
#         ## A weird way to do a loop, but that was the example I had.
#         QTimer.singleShot(0, self.do_loop)
#         self.exec_()

#     def updateStatus(self):
#         self.setLabelText("%s %d of %d"%(self.status_prefix,self.i+1,len(self.line_list)))
#         self.setValue(self.i+1)

#     def do_loop(self):

#         if self.i == 0:
#             self.setValue(0)

#         line = self.line_list[self.i]
#         try:
#             self.foreach_function(line)
            
#         except Exception as e:
#             line['good']=False
#             line['comment']=unicode(e)
#             print("Exception: %s:%s"%(line,unicode(e)))
#             traceback.print_exc()
            
#         self.updateStatus()
#         self.i += 1
            
#         if self.i >= len(self.line_list) or self.wasCanceled():
#             return self.do_when_finished()
#         else:
#             QTimer.singleShot(0, self.do_loop)

#     def do_when_finished(self):
#         # Queues a job to process these lines in the background.
#         self.setLabelText("Starting Split...")
#         self.setValue(self.i+1)
        
#         self.finish_function(self.line_list)
#         self.gui = None        
#         self.hide()        

# class AuthorTableWidgetItem(ReadOnlyTableWidgetItem):
#     def __init__(self, text, sort_key):
#         ReadOnlyTableWidgetItem.__init__(self, text)
#         self.sort_key = sort_key

#     #Qt uses a simple < check for sorting items, override this to use the sortKey
#     def __lt__(self, other):
#         return self.sort_key < other.sort_key

# class SeriesTableWidgetItem(ReadOnlyTableWidgetItem):
#     def __init__(self, series_name, series_index):
#         if series_name:
#             text = '%s [%s]' % (series_name, fmt_sidx(series_index))
#         else:
#             text = ''
#         ReadOnlyTableWidgetItem.__init__(self, text)
#         self.series_name = series_name
#         self.series_index = series_index

#     #Qt uses a simple < check for sorting items, override this to use the sortKey
#     def __lt__(self, other):
#         if self.series_name == other.series_name:
#             return self.series_index < other.series_index
#         else:
#             return self.series_name < other.series_name

class SelectLinesDialog(SizePersistedDialog):
    def __init__(self, gui, header, prefs, icon, lines,
                 save_size_name='epubsplit:update list dialog'):
        SizePersistedDialog.__init__(self, gui, save_size_name)
        self.gui = gui
      
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

        # button_layout = QVBoxLayout()
        # lines_layout.addLayout(button_layout)
        # spacerItem = QtGui.QSpacerItem(20, 40, QtGui.QSizePolicy.Minimum, QtGui.QSizePolicy.Expanding)
        # button_layout.addItem(spacerItem)
        # self.move_up_button = QtGui.QToolButton(self)
        # self.move_up_button.setToolTip('Move selected lines up the list')
        # self.move_up_button.setIcon(QIcon(I('arrow-up.png')))
        # self.move_up_button.clicked.connect(self.lines_table.move_rows_up)
        # button_layout.addWidget(self.move_up_button)
        # self.remove_button = QtGui.QToolButton(self)
        # self.remove_button.setToolTip('Remove selected lines from the list')
        # self.remove_button.setIcon(get_icon('list_remove.png'))
        # self.remove_button.clicked.connect(self.remove_from_list)
        # button_layout.addWidget(self.remove_button)
        # self.move_down_button = QtGui.QToolButton(self)
        # self.move_down_button.setToolTip('Move selected lines down the list')
        # self.move_down_button.setIcon(QIcon(I('arrow-down.png')))
        # self.move_down_button.clicked.connect(self.lines_table.move_rows_down)
        # button_layout.addWidget(self.move_down_button)
        # spacerItem1 = QtGui.QSpacerItem(20, 40, QtGui.QSizePolicy.Minimum, QtGui.QSizePolicy.Expanding)
        # button_layout.addItem(spacerItem1)

        options_layout = QHBoxLayout()

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        options_layout.addWidget(button_box)
      
        layout.addLayout(options_layout)
      
        # Cause our dialog size to be restored from prefs or created on first usage
        self.resize_dialog()
        self.lines_table.populate_table(lines)

    # def remove_from_list(self):
    #     self.lines_table.remove_selected_rows()

    def get_selected_linenums(self):
        return self.lines_table.get_selected_linenums()

class LinesTableWidget(QTableWidget):

    def __init__(self, parent):
        QTableWidget.__init__(self, parent)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)

    # def on_headersection_clicked(self):
    #     self.setSortingEnabled(True)
        
    def populate_table(self, lines):
        self.clear()
        self.setAlternatingRowColors(True)
        self.setRowCount(len(lines))
        header_labels = ['HREF', 'Table of Contents'] #, 'extra'
        self.setColumnCount(len(header_labels))
        self.setHorizontalHeaderLabels(header_labels)
        self.horizontalHeader().setStretchLastSection(True)
        #self.verticalHeader().setDefaultSectionSize(24)
        self.verticalHeader().hide()

        # # need sortingEnbled to sort, but off to up & down.
        # self.connect(self.horizontalHeader(),
        #              SIGNAL('sectionClicked(int)'),
        #              self.on_headersection_clicked)
        
        self.lines={}
        for row, line in enumerate(lines):
            self.populate_table_row(row, line)
            self.lines[row] = line

        self.resizeColumnsToContents()
        self.setMinimumColumnWidth(1, 100)
        self.setMinimumColumnWidth(2, 100)
        #self.setMinimumColumnWidth(3, 100)
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

        toc_str = ", ".join(line['toc'])
        if 'guide' in line:
            toc_str = toc_str+" {Guide(%s):%s}"%line['guide']
        toc_cell = ReadOnlyTableWidgetItem(toc_str)
        toc_cell.setData(Qt.UserRole, QVariant(row))
        self.setItem(row, 1, toc_cell)
      
        # extra_cell = ReadOnlyTableWidgetItem(line['id'])
        # extra_cell.setData(Qt.UserRole, QVariant(row))
        # self.setItem(row, 2, extra_cell)

        
        # self.setItem(row, 1, AuthorTableWidgetItem(' & '.join(line['authors']),
        #                                            line['author_sort']))
      
        # series_cell = SeriesTableWidgetItem(line['series'],line['series_index'])
        # self.setItem(row, 2, series_cell)
      
    def get_selected_linenums(self):
        # lines = []
        # for row in range(self.rowCount()):
        #     rnum = self.item(row, 0).data(Qt.UserRole).toPyObject()
        #     line = self.lines[rnum]
        #     lines.append(line)
        # return lines
        linenums = []
        
        for row in self.selectionModel().selectedRows():
            linenums.append(row.data(Qt.UserRole).toPyObject())

        linenums.sort()
        return linenums

    # def remove_selected_rows(self):
    #     self.setFocus()
    #     rows = self.selectionModel().selectedRows()
    #     if len(rows) == 0:
    #         return
    #     message = '<p>Are you sure you want to remove this line from the list?'
    #     if len(rows) > 1:
    #         message = '<p>Are you sure you want to remove the selected %d lines from the list?'%len(rows)
    #     if not confirm(message,'epubsplit_delete_item_again', self):
    #         return
    #     first_sel_row = self.currentRow()
    #     for selrow in reversed(rows):
    #         self.removeRow(selrow.row())
    #     if first_sel_row < self.rowCount():
    #         self.select_and_scroll_to_row(first_sel_row)
    #     elif self.rowCount() > 0:
    #         self.select_and_scroll_to_row(first_sel_row - 1)

    # def select_and_scroll_to_row(self, row):
    #     self.selectRow(row)
    #     self.scrollToItem(self.currentItem())

    # def move_rows_up(self):
    #     self.setFocus()
    #     rows = self.selectionModel().selectedRows()
    #     if len(rows) == 0:
    #         return
    #     first_sel_row = rows[0].row()
    #     if first_sel_row <= 0:
    #         return
    #     # Workaround for strange selection bug in Qt which "alters" the selection
    #     # in certain circumstances which meant move down only worked properly "once"
    #     selrows = []
    #     for row in rows:
    #         selrows.append(row.row())
    #     selrows.sort()
    #     for selrow in selrows:
    #         self.swap_row_widgets(selrow - 1, selrow + 1)
    #     scroll_to_row = first_sel_row - 1
    #     if scroll_to_row > 0:
    #         scroll_to_row = scroll_to_row - 1
    #     self.scrollToItem(self.item(scroll_to_row, 0))

    # def move_rows_down(self):
    #     self.setFocus()
    #     rows = self.selectionModel().selectedRows()
    #     if len(rows) == 0:
    #         return
    #     last_sel_row = rows[-1].row()
    #     if last_sel_row == self.rowCount() - 1:
    #         return
    #     # Workaround for strange selection bug in Qt which "alters" the selection
    #     # in certain circumstances which meant move down only worked properly "once"
    #     selrows = []
    #     for row in rows:
    #         selrows.append(row.row())
    #     selrows.sort()
    #     for selrow in reversed(selrows):
    #         self.swap_row_widgets(selrow + 2, selrow)
    #     scroll_to_row = last_sel_row + 1
    #     if scroll_to_row < self.rowCount() - 1:
    #         scroll_to_row = scroll_to_row + 1
    #     self.scrollToItem(self.item(scroll_to_row, 0))

    # def swap_row_widgets(self, src_row, dest_row):
    #     self.blockSignals(True)
    #     self.setSortingEnabled(False)
    #     self.insertRow(dest_row)
    #     for col in range(0, self.columnCount()):
    #         self.setItem(dest_row, col, self.takeItem(src_row, col))
    #     self.removeRow(src_row)
    #     self.blockSignals(False)
