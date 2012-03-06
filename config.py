#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Jim Miller'
__docformat__ = 'restructuredtext en'

import traceback, copy

from PyQt4.Qt import (QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QFont, QGridLayout,
                      QTextEdit, QComboBox, QCheckBox, QPushButton, QTabWidget, QVariant)

from calibre.gui2 import dynamic, info_dialog
from calibre.utils.config import JSONConfig
from calibre.gui2.ui import get_gui

from calibre_plugins.epubmerge.common_utils \
    import ( get_library_uuid, KeyboardConfigDialog )

# This is where all preferences for this plugin will be stored
# Remember that this name (i.e. plugins/epubmerge) is also
# in a global namespace, so make it as unique as possible.
# You should always prefix your config file name with plugins/,
# so as to ensure you dont accidentally clobber a calibre config file
all_prefs = JSONConfig('plugins/EpubMerge')

# Set defaults used by all.  Library specific settings continue to
# take from here.
all_prefs.defaults['flattentoc'] = False
all_prefs.defaults['titlenavpoints'] = True
all_prefs.defaults['custom_cols'] = {}

# The list of settings to copy from all_prefs or the previous library
# when config is called for the first time on a library.
copylist = ['flattentoc',
            'titlenavpoints']

# fake out so I don't have to change the prefs calls anywhere.  The
# Java programmer in me is offended by op-overloading, but it's very
# tidy.
class PrefsFacade():
    def __init__(self,all_prefs):
        self.all_prefs = all_prefs
        self.lastlibid = None

    def _get_copylist_prefs(self,frompref):
        return filter( lambda x : x[0] in copylist, frompref.items() )
        
    def _get_prefs(self):
        libraryid = get_library_uuid(get_gui().current_db)
        if libraryid not in self.all_prefs:
            if self.lastlibid == None:
                self.all_prefs[libraryid] = dict(self._get_copylist_prefs(self.all_prefs))
            else:
                self.all_prefs[libraryid] = dict(self._get_copylist_prefs(self.all_prefs[self.lastlibid]))
            self.lastlibid = libraryid
            
        return self.all_prefs[libraryid]

    def _save_prefs(self,prefs):
        libraryid = get_library_uuid(get_gui().current_db)
        self.all_prefs[libraryid] = prefs
        
    def __getitem__(self,k):            
        prefs = self._get_prefs()
        if k not in prefs:
            # pulls from all_prefs.defaults automatically if not set
            # in all_prefs
            return self.all_prefs[k]
        return prefs[k]

    def __setitem__(self,k,v):
        prefs = self._get_prefs()
        prefs[k]=v
        self._save_prefs(prefs)

    # to be avoided--can cause unexpected results as possibly ancient
    # all_pref settings may be pulled.
    def __delitem__(self,k):
        prefs = self._get_prefs()
        del prefs[k]
        self._save_prefs(prefs)

prefs = PrefsFacade(all_prefs)
    
class ConfigWidget(QWidget):

    def __init__(self, plugin_action):
        QWidget.__init__(self)
        self.plugin_action = plugin_action
        
        self.l = QVBoxLayout()
        self.setLayout(self.l)

        tab_widget = QTabWidget(self)
        self.l.addWidget(tab_widget)

        self.basic_tab = BasicTab(self, plugin_action)
        tab_widget.addTab(self.basic_tab, 'Basic')

        self.columns_tab = ColumnsTab(self, plugin_action)
        tab_widget.addTab(self.columns_tab, 'Custom Columns')

    def save_settings(self):
        # basic
        prefs['flattentoc'] = self.basic_tab.flattentoc.isChecked()
        prefs['titlenavpoints'] = self.basic_tab.titlenavpoints.isChecked()
        
        # Custom Columns tab
        colsmap = {}
        for (col,combo) in self.columns_tab.custcol_dropdowns.iteritems():
            val = unicode(combo.itemData(combo.currentIndex()).toString())
            if val != 'none':
                colsmap[col] = val
                #print("colsmap[%s]:%s"%(col,colsmap[col]))
        prefs['custom_cols'] = colsmap

    def edit_shortcuts(self):
        self.save_settings()
        d = KeyboardConfigDialog(self.plugin_action.gui, self.plugin_action.action_spec[0])
        if d.exec_() == d.Accepted:
            self.plugin_action.gui.keyboard.finalize()

class BasicTab(QWidget):

    def __init__(self, parent_dialog, plugin_action):
        self.parent_dialog = parent_dialog
        self.plugin_action = plugin_action
        QWidget.__init__(self)
        
        self.l = QVBoxLayout()
        self.setLayout(self.l)

        label = QLabel('These settings control the basic features of the plugin.')
        label.setWordWrap(True)
        self.l.addWidget(label)
        self.l.addSpacing(5)
        
        self.titlenavpoints = QCheckBox('Insert Table of Contents entry for each title?',self)
        self.titlenavpoints.setToolTip('''If set, a new TOC entry will be made for each title and
it's existing TOC nested underneath it.''')
        self.titlenavpoints.setChecked(prefs['titlenavpoints'])
        self.l.addWidget(self.titlenavpoints)

        self.flattentoc = QCheckBox('Flatten Table of Contents?',self)
        self.flattentoc.setToolTip('Remove nesting and make TOC all on one level.')
        self.flattentoc.setChecked(prefs['flattentoc'])
        self.l.addWidget(self.flattentoc)
        
        self.l.addSpacing(15)        

        label = QLabel("These controls aren't plugin settings as such, but convenience buttons for setting Keyboard shortcuts and getting all the EpubMerge confirmation dialogs back again.")
        label.setWordWrap(True)
        self.l.addWidget(label)
        self.l.addSpacing(5)
        
        keyboard_shortcuts_button = QPushButton('Keyboard shortcuts...', self)
        keyboard_shortcuts_button.setToolTip(_(
                    'Edit the keyboard shortcuts associated with this plugin'))
        keyboard_shortcuts_button.clicked.connect(parent_dialog.edit_shortcuts)
        self.l.addWidget(keyboard_shortcuts_button)

        reset_confirmation_button = QPushButton(_('Reset disabled &confirmation dialogs'), self)
        reset_confirmation_button.setToolTip(_(
                    'Reset all show me again dialogs for the EpubMerge plugin'))
        reset_confirmation_button.clicked.connect(self.reset_dialogs)
        self.l.addWidget(reset_confirmation_button)
        
        self.l.insertStretch(-1)
        
    def reset_dialogs(self):
        for key in dynamic.keys():
            if key.startswith('epubmerge_') and key.endswith('_again') \
                                                  and dynamic[key] is False:
                dynamic[key] = True
        info_dialog(self, _('Done'),
                    _('Confirmation dialogs have all been reset'),
                    show=True,
                    show_copy_button=False)

permitted_values = {
    'int' : ['add', 'first', 'last'],
    'float' : ['add', 'first', 'last'],
    'bool' : ['and', 'or', 'first', 'last'],
    'datetime' : ['newest', 'oldest', 'first', 'last'],
    'enumeration' : ['first', 'last'],
    'series' : ['first', 'last'],
    'text' : ['union', 'concat', 'first', 'last'],
    'comments' : ['concat', 'first', 'last']
    }

titleLabels = {
    'first':'Take value from first source book',
    'last':'Take value from last source book',
    'add':'Add values from all source books',
    'and':'True if true on all source books (and)',
    'or':'True if true on any source books (or)',
    'newest':'Take newest value from source books',
    'oldest':'Take oldest value from source books',
    'union':'Include values from all source books',
    'concat':'Concatenate values from all source books',
    }

class ColumnsTab(QWidget):

    def __init__(self, parent_dialog, plugin_action):
        self.parent_dialog = parent_dialog
        self.plugin_action = plugin_action
        QWidget.__init__(self)
        
        self.l = QVBoxLayout()
        self.setLayout(self.l)

        label = QLabel("If you have custom columns defined, they will be listed below.  Choose how you would like these columns handled.")
        label.setWordWrap(True)
        self.l.addWidget(label)
        self.l.addSpacing(5)
        
        self.custcol_dropdowns = {}

        custom_columns = self.plugin_action.gui.library_view.model().custom_columns

        grid = QGridLayout()
        self.l.addLayout(grid)
        row=0
        for key, column in custom_columns.iteritems():
            if column['datatype'] in permitted_values:
                # print("\n============== %s ===========\n"%key)
                # for (k,v) in column.iteritems():
                #     print("column['%s'] => %s"%(k,v))
                label = QLabel('%s(%s)'%(column['name'],key))
                label.setToolTip("Set this %s column on new merged books..."%column['datatype'])
                grid.addWidget(label,row,0)

                dropdown = QComboBox(self)
                dropdown.addItem('',QVariant('none'))
                for md in permitted_values[column['datatype']]:
                    # tags-like column also 'text'
                    if md == 'union' and not column['is_multiple']:
                        continue
                    if md == 'concat' and column['is_multiple']:
                        continue
                    dropdown.addItem(titleLabels[md],QVariant(md))
                self.custcol_dropdowns[key] = dropdown
                if key in prefs['custom_cols']:
                    dropdown.setCurrentIndex(dropdown.findData(QVariant(prefs['custom_cols'][key])))
                dropdown.setToolTip("How this column will be populated by default.")
                grid.addWidget(dropdown,row,1)
                row+=1
        
        self.l.insertStretch(-1)

        #print("prefs['custom_cols'] %s"%prefs['custom_cols'])
