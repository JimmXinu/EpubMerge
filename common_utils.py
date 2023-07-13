#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2011, Grant Drake <grant.drake@gmail.com>'
__docformat__ = 'restructuredtext en'

import os
from contextlib import contextmanager

import six
from six import text_type as unicode

from PyQt5.Qt import (QApplication, Qt, QIcon, QPixmap, QLabel, QDialog, QHBoxLayout,
                      QTableWidgetItem, QFont, QLineEdit, QComboBox,
                      QVBoxLayout, QDialogButtonBox, QStyledItemDelegate, QDateTime,
                      QTextEdit, QCursor,
                      QListWidget, QAbstractItemView)

from calibre.constants import numeric_version as calibre_version
from calibre.constants import iswindows
from calibre.gui2 import gprefs, error_dialog, UNDEFINED_QDATETIME, info_dialog
from calibre.gui2.actions import menu_action_unique_name
from calibre.gui2.keyboard import ShortcutConfig
from calibre.utils.config import config_dir
from calibre.utils.date import now, format_date, qt_to_dt, UNDEFINED_DATE

# Global definition of our plugin name. Used for common functions that require this.
plugin_name = None
# Global definition of our plugin resources. Used to share between the xxxAction and xxxBase
# classes if you need any zip images to be displayed on the configuration dialog.
plugin_icon_resources = {}


def set_plugin_icon_resources(name, resources):
    '''
    Set our global store of plugin name and icon resources for sharing between
    the InterfaceAction class which reads them and the ConfigWidget
    if needed for use on the customization dialog for this plugin.
    '''
    global plugin_icon_resources, plugin_name
    plugin_name = name
    plugin_icon_resources = resources

# print_tracebacks_for_missing_resources first appears in cal 6.2.0
if calibre_version >= (6,2,0):
    def get_icons_nolog(icon_name,plugin_name):
        return get_icons(icon_name,
                         plugin_name,
                         print_tracebacks_for_missing_resources=False)
else:
    get_icons_nolog = get_icons

def get_icon_6plus(icon_name):
    '''
    Retrieve a QIcon for the named image from
    1. Calibre's image cache
    2. resources/images
    3. the icon theme
    4. the plugin zip
    Only plugin zip has images/ in the image name for backward
    compatibility.
    '''
    icon = None
    if icon_name:
        icon = QIcon.ic(icon_name)
        ## both .ic and get_icons return an empty QIcon if not found.
        if not icon or icon.isNull():
            # don't need a tracestack from get_icons just because
            # there's no icon in the theme
            icon = get_icons_nolog(icon_name.replace('images/',''),
                                   plugin_name)
        if not icon or icon.isNull():
            icon = get_icons(icon_name,plugin_name)
    if not icon:
        icon = QIcon()
    return icon

def get_icon_old(icon_name):
    '''
    Retrieve a QIcon for the named image from the zip file if it exists,
    or if not then from Calibre's image cache.
    '''
    if icon_name:
        pixmap = get_pixmap(icon_name)
        if pixmap is None:
            # Look in Calibre's cache for the icon
            return QIcon(I(icon_name))
        else:
            return QIcon(pixmap)
    return QIcon()

# get_icons changed in Cal6.
if calibre_version >= (6,0,0):
    get_icon = get_icon_6plus
else:
    get_icon = get_icon_old

def get_pixmap(icon_name):
    '''
    Retrieve a QPixmap for the named image
    Any icons belonging to the plugin must be prefixed with 'images/'
    '''
    global plugin_icon_resources, plugin_name

    if not icon_name.startswith('images/'):
        # We know this is definitely not an icon belonging to this plugin
        pixmap = QPixmap()
        pixmap.load(I(icon_name))
        return pixmap

    # Check to see whether the icon exists as a Calibre resource
    # This will enable skinning if the user stores icons within a folder like:
    # ...\AppData\Roaming\calibre\resources\images\Plugin Name\
    if plugin_name:
        local_images_dir = get_local_images_dir(plugin_name)
        local_image_path = os.path.join(local_images_dir, icon_name.replace('images/', ''))
        if os.path.exists(local_image_path):
            pixmap = QPixmap()
            pixmap.load(local_image_path)
            return pixmap

    # As we did not find an icon elsewhere, look within our zip resources
    if icon_name in plugin_icon_resources:
        pixmap = QPixmap()
        pixmap.loadFromData(plugin_icon_resources[icon_name])
        return pixmap
    return None


def get_local_images_dir(subfolder=None):
    '''
    Returns a path to the user's local resources/images folder
    If a subfolder name parameter is specified, appends this to the path
    '''
    images_dir = os.path.join(config_dir, 'resources/images')
    if subfolder:
        images_dir = os.path.join(images_dir, subfolder)
    if iswindows:
        images_dir = os.path.normpath(images_dir)
    return images_dir


def create_menu_action_unique(ia, parent_menu, menu_text, image=None, tooltip=None,
                       shortcut=None, triggered=None, is_checked=None, shortcut_name=None,
                       unique_name=None):
    '''
    Create a menu action with the specified criteria and action, using the new
    InterfaceAction.create_menu_action() function which ensures that regardless of
    whether a shortcut is specified it will appear in Preferences->Keyboard
    '''
    orig_shortcut = shortcut
    kb = ia.gui.keyboard
    if unique_name is None:
        unique_name = menu_text
    if not shortcut == False:
        full_unique_name = menu_action_unique_name(ia, unique_name)
        if full_unique_name in kb.shortcuts:
            shortcut = False
        else:
            if shortcut is not None and not shortcut == False:
                if len(shortcut) == 0:
                    shortcut = None
                else:
                    shortcut = _(shortcut)

    if shortcut_name is None:
        shortcut_name = menu_text.replace('&','')

    ac = ia.create_menu_action(parent_menu, unique_name, menu_text, icon=None, shortcut=shortcut,
        description=tooltip, triggered=triggered, shortcut_name=shortcut_name)
    if shortcut == False and not orig_shortcut == False:
        if ac.calibre_shortcut_unique_name in ia.gui.keyboard.shortcuts:
            kb.replace_action(ac.calibre_shortcut_unique_name, ac)
    if image:
        ac.setIcon(get_icon(image))
    if is_checked is not None:
        ac.setCheckable(True)
        if is_checked:
            ac.setChecked(True)
    return ac


def get_library_uuid(db):
    try:
        library_uuid = db.library_id
    except:
        library_uuid = ''
    return library_uuid

# Call as ' with busy_cursor:"
@contextmanager
def busy_cursor():
    try:
        QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))
        yield
    finally:
        QApplication.restoreOverrideCursor()

class ImageTitleLayout(QHBoxLayout):
    '''
    A reusable layout widget displaying an image followed by a title
    '''
    def __init__(self, parent, icon_name, title):
        QHBoxLayout.__init__(self)
        title_image_label = QLabel(parent)
        pixmap = get_pixmap(icon_name)
        if pixmap is None:
            pixmap = get_pixmap('library.png')
            # error_dialog(parent, _('Restart required'),
            #              _('You must restart Calibre before using this plugin!'), show=True)
        else:
            title_image_label.setPixmap(pixmap)
        title_image_label.setMaximumSize(32, 32)
        title_image_label.setScaledContents(True)
        self.addWidget(title_image_label)

        title_font = QFont()
        title_font.setPointSize(16)
        shelf_label = QLabel(title, parent)
        shelf_label.setFont(title_font)
        self.addWidget(shelf_label)
        self.insertStretch(-1)


class SizePersistedDialog(QDialog):
    '''
    This dialog is a base class for any dialogs that want their size/position
    restored when they are next opened.
    '''
    def __init__(self, parent, unique_pref_name):
        QDialog.__init__(self, parent)
        self.unique_pref_name = unique_pref_name
        self.geom = gprefs.get(unique_pref_name, None)
        self.finished.connect(self.dialog_closing)

    def resize_dialog(self):
        if self.geom is None:
            self.resize(self.sizeHint())
        else:
            self.restoreGeometry(self.geom)

    def dialog_closing(self, result):
        geom = bytearray(self.saveGeometry())
        gprefs[self.unique_pref_name] = geom


class ReadOnlyTableWidgetItem(QTableWidgetItem):

    def __init__(self, text):
        if text is None:
            text = ''
        QTableWidgetItem.__init__(self, text)
        self.setFlags(Qt.ItemIsSelectable|Qt.ItemIsEnabled)


class KeyboardConfigDialog(SizePersistedDialog):
    '''
    This dialog is used to allow editing of keyboard shortcuts.
    '''
    def __init__(self, gui, group_name):
        SizePersistedDialog.__init__(self, gui, 'Keyboard shortcut dialog')
        self.gui = gui
        self.setWindowTitle('Keyboard shortcuts')
        layout = QVBoxLayout(self)
        self.setLayout(layout)

        self.keyboard_widget = ShortcutConfig(self)
        layout.addWidget(self.keyboard_widget)
        self.group_name = group_name

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.commit)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        # Cause our dialog size to be restored from prefs or created on first usage
        self.resize_dialog()
        self.initialize()

    def initialize(self):
        self.keyboard_widget.initialize(self.gui.keyboard)
        self.keyboard_widget.highlight_group(self.group_name)

    def commit(self):
        self.keyboard_widget.commit()
        self.accept()


class PrefsViewerDialog(SizePersistedDialog):

    def __init__(self, gui, namespace):
        SizePersistedDialog.__init__(self, gui, 'Prefs Viewer dialog')
        self.setWindowTitle('Preferences for: '+namespace)

        self.gui = gui
        self.db = gui.current_db
        self.namespace = namespace
        self._init_controls()
        self.resize_dialog()

        self._populate_settings()

        if self.keys_list.count():
            self.keys_list.setCurrentRow(0)

    def _init_controls(self):
        layout = QVBoxLayout(self)
        self.setLayout(layout)

        ml = QHBoxLayout()
        layout.addLayout(ml, 1)

        self.keys_list = QListWidget(self)
        self.keys_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.keys_list.setFixedWidth(150)
        self.keys_list.setAlternatingRowColors(True)
        ml.addWidget(self.keys_list)
        self.value_text = QTextEdit(self)
        self.value_text.setReadOnly(True)
        ml.addWidget(self.value_text, 1)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok)
        button_box.accepted.connect(self.accept)
        self.clear_button = button_box.addButton('Clear', QDialogButtonBox.ResetRole)
        self.clear_button.setIcon(get_icon('trash.png'))
        self.clear_button.setToolTip('Clear all settings for this plugin')
        self.clear_button.clicked.connect(self._clear_settings)
        layout.addWidget(button_box)

    def _populate_settings(self):
        self.keys_list.clear()
        ns_prefix = self._get_ns_prefix()
        keys = sorted([k[len(ns_prefix):] for k in six.iterkeys(self.db.prefs)
                       if k.startswith(ns_prefix)])
        for key in keys:
            self.keys_list.addItem(key)
        self.keys_list.setMinimumWidth(self.keys_list.sizeHintForColumn(0))
        self.keys_list.currentRowChanged[int].connect(self._current_row_changed)

    def _current_row_changed(self, new_row):
        if new_row < 0:
            self.value_text.clear()
            return
        key = unicode(self.keys_list.currentItem().text())
        val = self.db.prefs.get_namespaced(self.namespace, key, '')
        self.value_text.setPlainText(self.db.prefs.to_raw(val))

    def _get_ns_prefix(self):
        return 'namespaced:%s:'% self.namespace

    def _clear_settings(self):
        from calibre.gui2.dialogs.confirm_delete import confirm
        message = '<p>Are you sure you want to clear your settings in this library for this plugin?</p>' \
                  '<p>Any settings in other libraries or stored in a JSON file in your calibre plugins ' \
                  'folder will not be touched.</p>' \
                  '<p>You must restart calibre afterwards.</p>'
        if not confirm(message, self.namespace+'_clear_settings', self):
            return
        ns_prefix = self._get_ns_prefix()
        keys = [k for k in six.iterkeys(self.db.prefs) if k.startswith(ns_prefix)]
        for k in keys:
            del self.db.prefs[k]
        self._populate_settings()
        d = info_dialog(self, 'Settings deleted',
                        '<p>All settings for this plugin in this library have been cleared.</p>'
                        '<p>Please restart calibre now.</p>',
                        show_copy_button=False)
        b = d.bb.addButton(_('Restart calibre now'), d.bb.AcceptRole)
        b.setIcon(QIcon(I('lt.png')))
        d.do_restart = False
        def rf():
            d.do_restart = True
        b.clicked.connect(rf)
        d.set_details('')
        d.exec_()
        b.clicked.disconnect()
        self.close()
        if d.do_restart:
            self.gui.quit(restart=True)

