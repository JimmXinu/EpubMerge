#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Jim Miller'
__docformat__ = 'restructuredtext en'

import traceback, copy

from PyQt4.Qt import (QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QFont, QGridLayout,
                      QTextEdit, QComboBox, QCheckBox, QPushButton, QTabWidget, QVariant, QScrollArea)

from calibre.gui2 import dynamic, info_dialog
from calibre.utils.config import JSONConfig
from calibre.gui2.ui import get_gui

from calibre_plugins.epubmerge.common_utils \
    import ( get_library_uuid, KeyboardConfigDialog, PrefsViewerDialog )

PREFS_NAMESPACE = 'EpubMergePlugin'
PREFS_KEY_SETTINGS = 'settings'

# Set defaults used by all.  Library specific settings continue to
# take from here.
default_prefs = {}
default_prefs['flattentoc'] = False
default_prefs['titlenavpoints'] = True
default_prefs['keepmeta'] = True
default_prefs['showunmerge'] = True
default_prefs['custom_cols'] = {}

def set_library_config(library_config):
    get_gui().current_db.prefs.set_namespaced(PREFS_NAMESPACE,
                                              PREFS_KEY_SETTINGS,
                                              library_config)
    
def get_library_config():
    db = get_gui().current_db
    library_id = get_library_uuid(db)
    library_config = None
    # Check whether this is a configuration needing to be migrated
    # from json into database.  If so: get it, set it, wipe it from json.
    if library_id in old_prefs:
        #print("get prefs from old_prefs")
        library_config = old_prefs[library_id]
        set_library_config(library_config)
        del old_prefs[library_id]

    if library_config is None:
        #print("get prefs from db")
        library_config = db.prefs.get_namespaced(PREFS_NAMESPACE, PREFS_KEY_SETTINGS,
                                                 copy.deepcopy(default_prefs))
    return library_config

# This is where all preferences for this plugin *were* stored
# Remember that this name (i.e. plugins/epubmerge) is also
# in a global namespace, so make it as unique as possible.
# You should always prefix your config file name with plugins/,
# so as to ensure you dont accidentally clobber a calibre config file
old_prefs = JSONConfig('plugins/EpubMerge')

# fake out so I don't have to change the prefs calls anywhere.  The
# Java programmer in me is offended by op-overloading, but it's very
# tidy.
class PrefsFacade():
    def __init__(self,default_prefs):
        self.default_prefs = default_prefs
        self.libraryid = None
        self.current_prefs = None
        
    def _get_prefs(self):
        libraryid = get_library_uuid(get_gui().current_db)
        if self.current_prefs == None or self.libraryid != libraryid:
            #print("self.current_prefs == None(%s) or self.libraryid != libraryid(%s)"%(self.current_prefs == None,self.libraryid != libraryid))
            self.libraryid = libraryid
            self.current_prefs = get_library_config()
        return self.current_prefs
        
    def __getitem__(self,k):            
        prefs = self._get_prefs()
        if k not in prefs:
            # some users have old JSON, but have never saved all the
            # options.
            if k in self.default_prefs:
                return self.default_prefs[k]
            else:
                return default_prefs[k]
        return prefs[k]

    def __setitem__(self,k,v):
        prefs = self._get_prefs()
        prefs[k]=v
        # self._save_prefs(prefs)

    def __delitem__(self,k):
        prefs = self._get_prefs()
        if k in prefs:
            del prefs[k]

    def save_to_db(self):
        set_library_config(self._get_prefs())

prefs = PrefsFacade(old_prefs)
    
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

        self.columns_tab = CustomColumnsTab(self, plugin_action)
        tab_widget.addTab(self.columns_tab, 'Custom Columns')

    def save_settings(self):
        # basic
        prefs['flattentoc'] = self.basic_tab.flattentoc.isChecked()
        prefs['titlenavpoints'] = self.basic_tab.titlenavpoints.isChecked()
        prefs['keepmeta'] = self.basic_tab.keepmeta.isChecked()
        prefs['showunmerge'] = self.basic_tab.showunmerge.isChecked()
        
        # Custom Columns tab
        colsmap = {}
        for (col,combo) in self.columns_tab.custcol_dropdowns.iteritems():
            val = unicode(combo.itemData(combo.currentIndex()).toString())
            if val != 'none':
                colsmap[col] = val
                #print("colsmap[%s]:%s"%(col,colsmap[col]))
        prefs['custom_cols'] = colsmap

        prefs.save_to_db()
        
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
        
        self.keepmeta = QCheckBox('Keep UnMerge Metadata?',self)
        self.keepmeta.setToolTip('''If set, a copy of the original metadata for each merged book will
be included, allowing for UnMerge.  This includes your calibre custom
columns.  Leave off if you plan to distribute the epub to others.''')
        self.keepmeta.setChecked(prefs['keepmeta'])
        self.l.addWidget(self.keepmeta)

        self.showunmerge = QCheckBox('Show UnMerge Option?',self)
        self.showunmerge.setToolTip('''If set, the UnMerge Epub option will be shown.
Only Epubs merged with 'Keep UnMerge Metadata' can be UnMerged.''')
        self.showunmerge.setChecked(prefs['showunmerge'])
        self.l.addWidget(self.showunmerge)

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
        
        view_prefs_button = QPushButton('&View library preferences...', self)
        view_prefs_button.setToolTip(_(
                    'View data stored in the library database for this plugin'))
        view_prefs_button.clicked.connect(self.view_prefs)
        self.l.addWidget(view_prefs_button)
        
        self.l.insertStretch(-1)
        
    def view_prefs(self):
        d = PrefsViewerDialog(self.plugin_action.gui, PREFS_NAMESPACE)
        d.exec_()
        
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

class CustomColumnsTab(QWidget):

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
        
        scrollable = QScrollArea()
        scrollcontent = QWidget()
        scrollable.setWidget(scrollcontent)
        scrollable.setWidgetResizable(True)
        self.l.addWidget(scrollable)

        self.sl = QVBoxLayout()
        scrollcontent.setLayout(self.sl)
        
        self.custcol_dropdowns = {}

        custom_columns = self.plugin_action.gui.library_view.model().custom_columns

        grid = QGridLayout()
        self.sl.addLayout(grid)
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
        
        self.sl.insertStretch(-1)

        #print("prefs['custom_cols'] %s"%prefs['custom_cols'])
