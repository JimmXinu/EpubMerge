#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2014, Jim Miller'
__docformat__ = 'restructuredtext en'

from functools import partial
import string
import copy

from PyQt5.Qt import ( QProgressDialog, QTimer )

from calibre.gui2 import question_dialog

# The class that all interface action plugins must inherit from
from calibre.gui2.actions import InterfaceAction

from calibre.gui2.dialogs.message_box import ViewLog
from calibre_plugins.columnsum.common_utils import get_icon
from calibre_plugins.columnsum.config import prefs

load_translations()

class ColumnSumPlugin(InterfaceAction):

    name = 'ColumnSum'

    # Declare the main action associated with this plugin
    # The keyboard shortcut can be None if you dont want to use a keyboard
    # shortcut. Remember that currently calibre has no central management for
    # keyboard shortcuts, so try to use an unusual/unused shortcut.
    # (text, icon_path, tooltip, keyboard shortcut)
    # icon_path isn't in the zip--icon loaded below.
    action_spec = (_('ColumnSum'),
                   None,
                   _('Calculate Sum or other Aggregate for numeric columns of selected books.'),
                   ())
    # None for keyboard shortcut doesn't allow shortcut.  () does, there just isn't one yet

    action_type = 'global'
    # make button menu drop down only
    #popup_type = QToolButton.InstantPopup

    # # disable when not in library. (main,carda,cardb)
    # def location_selected(self, loc):
    #     enabled = loc == 'library'
    #     self.qaction.setEnabled(enabled)
    #     self.menuless_qaction.setEnabled(enabled)

    def genesis(self):

        # This method is called once per plugin, do initial setup here

        base = self.interface_action_base_plugin
        self.version = base.name+" v%d.%d.%d"%base.version

        # Set the icon for this interface action
        # The get_icons function is a builtin function defined for all your
        # plugin code. It loads icons from the plugin zip file. It returns
        # QIcon objects, if you want the actual data, use the analogous
        # get_resources builtin function.

        # Note that if you are loading more than one icon, for performance, you
        # should pass a list of names to get_icons. In this case, get_icons
        # will return a dictionary mapping names to QIcons. Names that
        # are not found in the zip file will result in null QIcons.
        icon = get_icon('column.png')

        self.qaction.setText(_('ColumnSum'))
        # The qaction is automatically created from the action_spec defined
        # above
        self.qaction.setIcon(icon)

        # Call function when plugin triggered.
        self.qaction.triggered.connect(self.plugin_button)

    def plugin_button(self):

        if not self.gui.current_view().selectionModel().selectedRows() :
            self.gui.status_bar.show_message(_('No Selected Books for ColumnSum'),
                                             3000)
            return
            
        if self.is_library_view():
            book_list = [ {'id':x} for x in self.gui.library_view.get_selected_ids() ]

        else: # device view, get from epubs on device.
            self.gui.status_bar.show_message(_('ColumnSum only works in libary'),
                                             3000)

        # copy of custom_columns because model() gives us the same copy each time.
        custom_columns = copy.deepcopy(self.gui.library_view.model().custom_columns)

        num_cust_cols=[]
        for col,coldef in custom_columns.iteritems():
            if coldef['datatype'] in ('int','float'):
                num_cust_cols.append(coldef)
        
        LoopProgressDialog(self.gui,
                           book_list,
                           partial(self.sum_columns_loop, db=self.gui.current_db,sum_cols=num_cust_cols),
                           partial(self.sum_columns_finish, sum_cols=num_cust_cols))
            
    def sum_columns_loop(self,bookid,db=None,sum_cols=[]):
        #print("bookid:%s"%bookid)
        for col in sum_cols:
            value = db.get_custom(bookid['id'],
                                  label=col['label'],
                                  index_is_id=True)
            # print("Col: %s val: %s %s"%(col['name'],
            #                             value,
            #                             col['display']['number_format']))
            if 'values' not in col:
                col['values']=[]
            if value is not None:
                col['values'].append(value)

    def do_sum(self, x):
        return x['display']['number_format'].format(sum(x['values']))
    
    def do_average(self, x):
        if len(x['values']) > 0 :
            aver=float(sum(x['values']))/float(len(x['values']))
            x['aver']=aver
            return '{:,.1f}'.format(aver) #x['display']['number_format'].replace('d','.1f')
        else:
            return "0.0"

    def do_median(self, x):
        if len(x['values']) > 0 :
            sorts = sorted(x['values'])
            length = len(sorts)
            print("length:%s"%length)
            i=int(length/2)
            if not length % 2:
                median = (sorts[i] + sorts[i - 1]) / 2.0
            else:
                median = sorts[i]
            return '{:,.1f}'.format(median) #x['display']['number_format'].replace('d','.1f')
        else:
            return "0.0"

    def do_stddev(self, x):
        if len(x['values']) > 0 :
            if 'aver' in x:
                aver=x['aver']
            else:
                aver=float(sum(x['values']))/float(len(x['values']))
            import math
            def average(s): return sum(s) * 1.0 / len(s)
            variance = map(lambda y: (y - aver)**2, x['values'])
            return '{:,.1f}'.format(math.sqrt(average(variance))) #x['display']['number_format'].replace('d','.1f')
        else:
            return "0.0"

    def sum_columns_finish(self, book_list,sum_cols=[]):
        #print("sum_cols:%s"%sum_cols)
        #print("book_list:%s"%book_list)

        values = []
        for j, x in enumerate(sum_cols):
            values.append(
                [x['name'],
                 "%s"%len(x['values']),
                 self.do_sum(x),
                 self.do_average(x),
                 self.do_median(x),
                 self.do_stddev(x)
                 ])
        
        d = ViewLog(_("Column Sums"),
                    "",
                    parent=self.gui)
        # override ViewLog's default of wrapping content with <pre>
        html = '''<table border='1'><tr><th>Column</th><th>Book Count</th><th>Sum</th><th>Average</th><th>Median</th><th>Std Dev</th></tr>'''
        for row in values:
            html += "<tr><td align='right'>"+("</td><td align='right'>".join(row))+"</td></tr>"
        html += "</table>"
        d.tb.setHtml(html)
        d.setWindowIcon(get_icon('bookmarks.png'))
        d.exec_()
        
    def apply_settings(self):
        # No need to do anything with prefs here, but we could.
        prefs

    def is_library_view(self):
        # 0 = library, 1 = main, 2 = card_a, 3 = card_b
        return self.gui.stack.currentIndex() == 0
    
class LoopProgressDialog(QProgressDialog):
    '''
    ProgressDialog displayed while fetching metadata for each story.
    '''
    def __init__(self, gui,
                 book_list,
                 foreach_function,
                 finish_function,
                 init_label=_("Collecting ..."),
                 win_title=_("Summing Columns"),
                 status_prefix=_("Books collected")):
        QProgressDialog.__init__(self,
                                 init_label,
                                 _('Cancel'), 0, len(book_list), gui)
        self.setWindowTitle(win_title)
        self.setMinimumWidth(500)
        self.book_list = book_list
        self.foreach_function = foreach_function
        self.finish_function = finish_function
        self.status_prefix = status_prefix
        self.i = 0
        
        ## self.do_loop does QTimer.singleShot on self.do_loop also.
        ## A weird way to do a loop, but that was the example I had.
        QTimer.singleShot(0, self.do_loop)
        self.exec_()
        
    def updateStatus(self):
        self.setLabelText("%s %d / %d"%(self.status_prefix,self.i+1,len(self.book_list)))
        self.setValue(self.i+1)
        #print(self.labelText())

    def do_loop(self):

        if self.i == 0:
            self.setValue(0)

        book = self.book_list[self.i]
        try:
            ## collision spec passed into getadapter by partial from ffdl_plugin
            ## no retval only if it exists, but collision is SKIP
            self.foreach_function(book)
            
        except Exception as e:
            book['good']=False
            book['comment']=unicode(e)
            traceback.print_exc()
            
        self.updateStatus()
        self.i += 1
            
        if self.i >= len(self.book_list) or self.wasCanceled():
            return self.do_when_finished()
        else:
            QTimer.singleShot(0, self.do_loop)

    def do_when_finished(self):
        self.hide()
        # Queues a job to process these books in the background.
        self.finish_function(self.book_list)
