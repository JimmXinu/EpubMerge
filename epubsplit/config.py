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
default_prefs['copylanguages'] = True
default_prefs['copyseries'] = True
default_prefs['copycomments'] = True
default_prefs['copycover'] = True

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
        print("get prefs from old_prefs")
        library_config = old_prefs[library_id]
        set_library_config(library_config)
        del old_prefs[library_id]

    if library_config is None:
        print("get prefs from db")
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
            print("self.current_prefs == None(%s) or self.libraryid != libraryid(%s)"%(self.current_prefs == None,self.libraryid != libraryid))
            self.libraryid = libraryid
            self.current_prefs = get_library_config()
        return self.current_prefs
        
    def __getitem__(self,k):            
        prefs = self._get_prefs()
        if k not in prefs:
            # pulls from default_prefs.defaults automatically if not set
            # in default_prefs
            return self.default_prefs[k]
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

        label = QLabel('When making a new Epub, the metadata from the source book will be copied or not as you choose below.')
        label.setWordWrap(True)
        self.l.addWidget(label)
        #self.l.addSpacing(5)
        
        self.copytitle = QCheckBox('Copy Title',self)
        self.copytitle.setToolTip('Copy title from the source Epub to the Split Epub.  Adds "Split" to the title.')
        self.copytitle.setChecked(prefs['copytitle'])
        self.l.addWidget(self.copytitle)
        
        self.copyauthors = QCheckBox('Copy Authors',self)
        self.copyauthors.setToolTip('Copy Authors from the source Epub to the Split Epub.')
        self.copyauthors.setChecked(prefs['copyauthors'])
        self.l.addWidget(self.copyauthors)
        
        self.copytags = QCheckBox('Copy Tags',self)
        self.copytags.setToolTip('Copy Tags from the source Epub to the Split Epub.')
        self.copytags.setChecked(prefs['copytags'])
        self.l.addWidget(self.copytags)
        
        self.copylanguages = QCheckBox('Copy Languages',self)
        self.copylanguages.setToolTip('Copy Languages from the source Epub to the Split Epub.')
        self.copylanguages.setChecked(prefs['copylanguages'])
        self.l.addWidget(self.copylanguages)
        
        self.copyseries = QCheckBox('Copy Series',self)
        self.copyseries.setToolTip('Copy Series from the source Epub to the Split Epub.')
        self.copyseries.setChecked(prefs['copyseries'])
        self.l.addWidget(self.copyseries)
        
        self.copycomments = QCheckBox('Copy Comments',self)
        self.copycomments.setToolTip('Copy Comments from the source Epub to the Split Epub.  Adds "Split from:" to the comments.')
        self.copycomments.setChecked(prefs['copycomments'])
        self.l.addWidget(self.copycomments)
        
        self.copycover = QCheckBox('Copy Cover',self)
        self.copycover.setToolTip('Copy Cover from the source Epub to the Split Epub.')
        self.copycover.setChecked(prefs['copycover'])
        self.l.addWidget(self.copycover)
        
        self.l.addSpacing(15)        

        label = QLabel("These controls aren't plugin settings as such, but convenience buttons for setting Keyboard shortcuts and getting all the EpubSplit confirmation dialogs back again.")
        label.setWordWrap(True)
        self.l.addWidget(label)
        self.l.addSpacing(5)
        
        keyboard_shortcuts_button = QPushButton('Keyboard shortcuts...', self)
        keyboard_shortcuts_button.setToolTip(_(
                    'Edit the keyboard shortcuts associated with this plugin'))
        keyboard_shortcuts_button.clicked.connect(self.edit_shortcuts)
        self.l.addWidget(keyboard_shortcuts_button)

        reset_confirmation_button = QPushButton(_('Reset disabled &confirmation dialogs'), self)
        reset_confirmation_button.setToolTip(_(
                    'Reset all show me again dialogs for the EpubSplit plugin'))
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
        
    def save_settings(self):
        prefs['copytitle'] = self.copytitle.isChecked()
        prefs['copyauthors'] = self.copyauthors.isChecked()
        prefs['copytags'] = self.copytags.isChecked()
        prefs['copylanguages'] = self.copylanguages.isChecked()
        prefs['copyseries'] = self.copyseries.isChecked()
        prefs['copycomments'] = self.copycomments.isChecked()
        prefs['copycover'] = self.copycover.isChecked()

        prefs.save_to_db()
        
    def edit_shortcuts(self):
        self.save_settings()
        d = KeyboardConfigDialog(self.plugin_action.gui, self.plugin_action.action_spec[0])
        if d.exec_() == d.Accepted:
            self.plugin_action.gui.keyboard.finalize()

    def reset_dialogs(self):
        for key in dynamic.keys():
            if key.startswith('epubsplit_') and key.endswith('_again') \
                                                  and dynamic[key] is False:
                dynamic[key] = True
        info_dialog(self, _('Done'),
                    _('Confirmation dialogs have all been reset'),
                    show=True,
                    show_copy_button=False)

