#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2014, Jim Miller'
__docformat__ = 'restructuredtext en'

import traceback, copy

try:
    from PyQt5.Qt import (QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QFont, QGridLayout,
                          QTextEdit, QComboBox, QCheckBox, QPushButton, QTabWidget, QScrollArea)
except ImportError as e:    
    from PyQt4.Qt import (QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QFont, QGridLayout,
                          QTextEdit, QComboBox, QCheckBox, QPushButton, QTabWidget, QScrollArea)

from calibre.gui2 import dynamic, info_dialog
from calibre.utils.config import JSONConfig
from calibre.gui2.ui import get_gui

# pulls in translation files for _() strings
try:
    load_translations()
except NameError:
    pass # load_translations() added in calibre 1.9

from calibre_plugins.epubsplit.common_utils \
    import ( get_library_uuid, KeyboardConfigDialog, PrefsViewerDialog )

PREFS_NAMESPACE = 'EpubSplitPlugin'
PREFS_KEY_SETTINGS = 'settings'

# Set defaults used by all.  Library specific settings continue to
# take from here.
default_prefs = {}
default_prefs['copytitle'] = True
default_prefs['copyauthors'] = True
default_prefs['copytags'] = True

default_prefs['copyrating'] = True
default_prefs['copydate'] = True
default_prefs['copyidentifiers'] = False
default_prefs['copypublisher'] = True
default_prefs['copypubdate'] = True

default_prefs['copylanguages'] = True
default_prefs['copyseries'] = True
default_prefs['copycomments'] = True
default_prefs['copycover'] = True

default_prefs['custom_cols'] = {}

default_prefs['sourcecol'] = ''
default_prefs['sourcetemplate'] = "{title} by {authors}"

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
# Remember that this name (i.e. plugins/epubsplit) is also
# in a global namespace, so make it as unique as possible.
# You should always prefix your config file name with plugins/,
# so as to ensure you dont accidentally clobber a calibre config file
old_prefs = JSONConfig('plugins/EpubSplit')

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
        tab_widget.addTab(self.basic_tab, _('Basic'))

        self.columns_tab = CustomColumnsTab(self, plugin_action)
        tab_widget.addTab(self.columns_tab, _('Custom Columns'))

    def save_settings(self):
        prefs['copytitle'] = self.basic_tab.copytitle.isChecked()
        prefs['copyauthors'] = self.basic_tab.copyauthors.isChecked()
        prefs['copytags'] = self.basic_tab.copytags.isChecked()
        prefs['copylanguages'] = self.basic_tab.copylanguages.isChecked()
        prefs['copyseries'] = self.basic_tab.copyseries.isChecked()
        prefs['copycomments'] = self.basic_tab.copycomments.isChecked()
        prefs['copycover'] = self.basic_tab.copycover.isChecked()
        prefs['copydate'] = self.basic_tab.copydate.isChecked()
        prefs['copyrating'] = self.basic_tab.copyrating.isChecked()
        prefs['copypubdate'] = self.basic_tab.copypubdate.isChecked()
        prefs['copyidentifiers'] = self.basic_tab.copyidentifiers.isChecked()
        prefs['copypublisher'] = self.basic_tab.copypublisher.isChecked()

        # Custom Columns tab
        colsmap = {}
        for (col,chkbx) in self.columns_tab.custcol_checkboxes.iteritems():
            if chkbx.isChecked():
                colsmap[col] = chkbx.isChecked()
            #print("colsmap[%s]:%s"%(col,colsmap[col]))
        prefs['custom_cols'] = colsmap

        prefs['sourcecol'] = unicode(self.columns_tab.sourcecol.itemData(self.columns_tab.sourcecol.currentIndex()))
        prefs['sourcetemplate'] = unicode(self.columns_tab.sourcetemplate.text())
        
        prefs.save_to_db()
        
    def edit_shortcuts(self):
        self.save_settings()
        d = KeyboardConfigDialog(self.plugin_action.gui, self.plugin_action.action_spec[0])
        if d.exec_() == d.Accepted:
            self.plugin_action.gui.keyboard.finalize()

class BasicTab(QWidget):

    def __init__(self, parent_dialog, plugin_action):
        QWidget.__init__(self)
        self.parent_dialog = parent_dialog
        self.plugin_action = plugin_action
        
        self.l = QVBoxLayout()
        self.setLayout(self.l)

        label = QLabel(_('When making a new Epub, the metadata from the source book will be copied or not as you choose below.'))
        label.setWordWrap(True)
        self.l.addWidget(label)
        #self.l.addSpacing(5)
        
        scrollable = QScrollArea()
        scrollcontent = QWidget()
        scrollable.setWidget(scrollcontent)
        scrollable.setWidgetResizable(True)
        self.l.addWidget(scrollable)

        self.sl = QVBoxLayout()
        scrollcontent.setLayout(self.sl)
        
        self.copytitle = QCheckBox(_('Copy Title'),self)
        self.copytitle.setToolTip(_('Copy Title from the source Epub to the Split Epub.  Adds "Split" to the title.'))
        self.copytitle.setChecked(prefs['copytitle'])
        self.sl.addWidget(self.copytitle)
        
        self.copyauthors = QCheckBox(_('Copy Authors'),self)
        self.copyauthors.setToolTip(_('Copy Authors from the source Epub to the Split Epub.'))
        self.copyauthors.setChecked(prefs['copyauthors'])
        self.sl.addWidget(self.copyauthors)
        
        self.copyseries = QCheckBox(_('Copy Series'),self)
        self.copyseries.setToolTip(_('Copy Series from the source Epub to the Split Epub.'))
        self.copyseries.setChecked(prefs['copyseries'])
        self.sl.addWidget(self.copyseries)
        
        self.copycover = QCheckBox(_('Copy Cover'),self)
        self.copycover.setToolTip(_('Copy Cover from the source Epub to the Split Epub.'))
        self.copycover.setChecked(prefs['copycover'])
        self.sl.addWidget(self.copycover)
        
        self.copyrating = QCheckBox(_('Copy Rating'),self)
        self.copyrating.setToolTip(_('Copy Rating from the source Epub to the Split Epub.'))
        self.copyrating.setChecked(prefs['copyrating'])
        self.sl.addWidget(self.copyrating)
        
        self.copytags = QCheckBox(_('Copy Tags'),self)
        self.copytags.setToolTip(_('Copy Tags from the source Epub to the Split Epub.'))
        self.copytags.setChecked(prefs['copytags'])
        self.sl.addWidget(self.copytags)
        
        self.copyidentifiers = QCheckBox(_('Copy Identifiers'),self)
        self.copyidentifiers.setToolTip(_('Copy Identifiers from the source Epub to the Split Epub.'))
        self.copyidentifiers.setChecked(prefs['copyidentifiers'])
        self.sl.addWidget(self.copyidentifiers)
        
        self.copydate = QCheckBox(_('Copy Date'),self)
        self.copydate.setToolTip(_('Copy Date from the source Epub to the Split Epub.'))
        self.copydate.setChecked(prefs['copydate'])
        self.sl.addWidget(self.copydate)
        
        self.copypubdate = QCheckBox(_('Copy Published Date'),self)
        self.copypubdate.setToolTip(_('Copy Published Date from the source Epub to the Split Epub.'))
        self.copypubdate.setChecked(prefs['copypubdate'])
        self.sl.addWidget(self.copypubdate)
        
        self.copypublisher = QCheckBox(_('Copy Publisher'),self)
        self.copypublisher.setToolTip(_('Copy Publisher from the source Epub to the Split Epub.'))
        self.copypublisher.setChecked(prefs['copypublisher'])
        self.sl.addWidget(self.copypublisher)
        
        self.copylanguages = QCheckBox(_('Copy Languages'),self)
        self.copylanguages.setToolTip(_('Copy Languages from the source Epub to the Split Epub.'))
        self.copylanguages.setChecked(prefs['copylanguages'])
        self.sl.addWidget(self.copylanguages)
        
        self.copycomments = QCheckBox(_('Copy Comments'),self)
        self.copycomments.setToolTip(_('Copy Comments from the source Epub to the Split Epub.  Adds "Split from:" to the comments.'))
        self.copycomments.setChecked(prefs['copycomments'])
        self.sl.addWidget(self.copycomments)
        
        self.sl.insertStretch(-1)
        
        self.l.addSpacing(15)        

        label = QLabel(_("These controls aren't plugin settings as such, but convenience buttons for setting Keyboard shortcuts and getting all the EpubSplit confirmation dialogs back again."))
        label.setWordWrap(True)
        self.l.addWidget(label)
        self.l.addSpacing(5)
        
        keyboard_shortcuts_button = QPushButton(_('Keyboard shortcuts...'), self)
        keyboard_shortcuts_button.setToolTip(_('Edit the keyboard shortcuts associated with this plugin'))
        keyboard_shortcuts_button.clicked.connect(parent_dialog.edit_shortcuts)
        self.l.addWidget(keyboard_shortcuts_button)

        reset_confirmation_button = QPushButton(_('Reset disabled &confirmation dialogs'), self)
        reset_confirmation_button.setToolTip(_('Reset all show me again dialogs for the EpubSplit plugin'))
        reset_confirmation_button.clicked.connect(self.reset_dialogs)
        self.l.addWidget(reset_confirmation_button)
                
        view_prefs_button = QPushButton(_('View library preferences...'), self)
        view_prefs_button.setToolTip(_('View data stored in the library database for this plugin'))
        view_prefs_button.clicked.connect(self.view_prefs)
        self.l.addWidget(view_prefs_button)
        
    def view_prefs(self):
        d = PrefsViewerDialog(self.plugin_action.gui, PREFS_NAMESPACE)
        d.exec_()
        
    def reset_dialogs(self):
        for key in dynamic.keys():
            if key.startswith('epubsplit_') and key.endswith('_again') \
                                                  and dynamic[key] is False:
                dynamic[key] = True
        info_dialog(self, _('Done'),
                    _('Confirmation dialogs have all been reset'),
                    show=True,
                    show_copy_button=False)

class CustomColumnsTab(QWidget):

    def __init__(self, parent_dialog, plugin_action):
        self.parent_dialog = parent_dialog
        self.plugin_action = plugin_action
        QWidget.__init__(self)
        
        self.l = QVBoxLayout()
        self.setLayout(self.l)

        label = QLabel(_("If you have custom columns defined, they will be listed below.  Choose if you would like these columns copied to new split books."))
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
        
        self.custcol_checkboxes = {}

        custom_columns = self.plugin_action.gui.library_view.model().custom_columns
        for key, column in custom_columns.iteritems():
            # print("\n============== %s ===========\n"%key)
            # for (k,v) in column.iteritems():
            #     print("column['%s'] => %s"%(k,v))
            checkbox = QCheckBox('%s(%s)'%(column['name'],key))
            checkbox.setToolTip(_("Copy this %s column to new split books...")%column['datatype'])
            checkbox.setChecked(key in prefs['custom_cols'] and prefs['custom_cols'][key])
            self.custcol_checkboxes[key] = checkbox
            self.sl.addWidget(checkbox)
            
        self.sl.insertStretch(-1)

        self.l.addSpacing(5)
        label = QLabel(_("Source column:"))
        label.setToolTip(_("If set, the column below will be populated with the template below to record the source of the split file."))
        label.setWordWrap(True)
        self.l.addWidget(label)
        
        horz = QHBoxLayout()
        self.sourcecol = QComboBox(self)
        self.sourcecol.setToolTip(_("Choose a column to populate with template on split."))
        self.sourcecol.addItem('','none')
        for key, column in custom_columns.iteritems():
            if column['datatype'] in ('text','comments'):
                self.sourcecol.addItem(column['name'],key)
        self.sourcecol.setCurrentIndex(self.sourcecol.findData(prefs['sourcecol']))
        horz.addWidget(self.sourcecol)
        
        self.sourcetemplate = QLineEdit(self)
        self.sourcetemplate.setToolTip(_("Template from source book. Example: {title} by {authors}"))
        # if 'sourcetemplate' in prefs:
        self.sourcetemplate.setText(prefs['sourcetemplate'])
        # else:
        #      self.sourcetemplate.setText("{title} by {authors}")
        horz.addWidget(self.sourcetemplate)
        
        self.l.addLayout(horz)
