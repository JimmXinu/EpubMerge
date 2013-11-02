#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Jim Miller'
__docformat__ = 'restructuredtext en'

from calibre.gui2 import question_dialog

# The class that all interface action plugins must inherit from
from calibre.gui2.actions import InterfaceAction

from calibre_plugins.smarteject.common_utils import get_icon
from calibre_plugins.smarteject.config import prefs

# pulls in translation files for _() strings
try:
    load_translations()
except NameError:
    pass # load_translations() added in calibre 1.9

# PLUGIN_ICONS = ['images/icon.png']

class SmartEjectPlugin(InterfaceAction):

    # Declare the main action associated with this plugin
    # The keyboard shortcut can be None if you dont want to use a keyboard
    # shortcut. Remember that currently calibre has no central management for
    # keyboard shortcuts, so try to use an unusual/unused shortcut.
    # (text, icon_path, tooltip, keyboard shortcut)
    # icon_path isn't in the zip--icon loaded below.
    action_spec = (_('SmartEject'), None,
                   _('Check for duplicated/deleted/added books before ejecting.'), ())
    # None for keyboard shortcut doesn't allow shortcut.  () does, there just isn't one yet

    action_type = 'global'
    # make button menu drop down only
    #popup_type = QToolButton.InstantPopup

    #: Set of locations to which this action must not be added.
    #: See :attr:`all_locations` for a list of possible locations
    dont_add_to = frozenset(['toolbar', 'context-menu', 'toolbar-child',
                             'context-menu-device', 'menubar',
                             'context-menu-cover-browser'])

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
        icon = get_icon('eject.png')

        self.qaction.setText(_('SmartEject'))
        # The qaction is automatically created from the action_spec defined
        # above
        self.qaction.setIcon(icon)

        # Call function when plugin triggered.
        self.qaction.triggered.connect(self.plugin_button)

    def plugin_button(self):

        if 'Reading List' in self.gui.iactions and prefs['checkreadinglistsync']:
            rl_plugin = self.gui.iactions['Reading List']
            list_names = rl_plugin.get_list_names(exclude_auto=True)
            all_list_names = rl_plugin.get_list_names(exclude_auto=False)
            auto_list_names = list(set(all_list_names) - set(list_names))
            if self.gui.device_manager.is_device_connected:
                sync_total = rl_plugin._count_books_for_connected_device()
                rl_plugin.sync_now_action.setEnabled(bool(sync_total > 0) or len(auto_list_names) > 0)
                if sync_total > 0:
                    if question_dialog(self.gui, _("Sync Reading List?"), _("There are books that need syncing according to Reading List.<p>Sync Books?"), show_copy_button=False):
                        rl_plugin.sync_now(force_sync=True)
                        return

        
        if prefs['checkdups'] and self.gui.library_view.model().db.search_getting_ids(prefs['checkdups_search'], None):
            
            if question_dialog(self.gui, _("Duplicates on Device"), _("There are duplicate ebooks on the device.<p>Display duplicates?"), show_copy_button=False):
#            print("Duplicates on Device warning:%s"%warning_dialog(self.gui, "Duplicates on Device", "There are duplicate ebooks on the device.", show=True, show_copy_button=False))
                self.gui.location_manager._location_selected('library')
                self.gui.search.setEditText(prefs['checkdups_search'])
                self.gui.search.do_search()
                return

        if prefs['checknotinlibrary'] and self.checkdevice(self.gui.memory_view.model(),"Main"):
            self.gui.location_manager._location_selected('main')
            return
        
        if prefs['checknotinlibrary'] and self.checkdevice(self.gui.card_a_view.model(),"Card A"):
            self.gui.location_manager._location_selected('carda')
            return
        
        if prefs['checknotinlibrary'] and self.checkdevice(self.gui.card_b_view.model(),"Card B"):
            self.gui.location_manager._location_selected('cardb')
            return
        
        if prefs['checknotondevice'] and self.gui.library_view.model().db.search_getting_ids(prefs['checknotondevice_search'], None):
            if question_dialog(self.gui,
                               _("Books in Library not on Device"),
                               _("There are books in the Library that are not on the Device.<p>Display books not on Device?"),
                               show_copy_button=False):
                self.gui.location_manager._location_selected('library')
                self.gui.search.setEditText(prefs['checknotondevice_search'])
                self.gui.search.do_search()
                return
            
        self.gui.location_manager._location_selected('library')

        self.gui.location_manager._eject_requested()

        # if one of the configured searchs, clear it.
        #print("self.gui.search.current_text :(%s)"%self.gui.search.current_text )
        if self.gui.search.current_text in (prefs['checkdups_search'],prefs['checknotinlibrary_search'],prefs['checknotondevice_search']): 
            self.gui.search.clear()

    def checkdevice(self,model,loc):
        savesearch = model.last_search
        #print("\nmodel.last_search:%s"%model.last_search)
        #print("model.count():%s"%model.count())
        model.search(prefs['checknotinlibrary_search'])
        #print("model.count():%s"%model.count())
        if model.count() > 0:
            if question_dialog(self.gui, _("Books on Device not in Library"), _("There are books on the device in %s that are not in the Library.<p>Display books not in Library?")%loc, show_copy_button=False):
#            #print("not in Library warning:%s"%warning_dialog(self.gui, "Books on Device not in Library", "There are books on the device not in Library.", show=True, show_copy_button=False))
                self.gui.search.setEditText(prefs['checknotinlibrary_search'])
                self.gui.search.do_search()
                return True
        model.search(savesearch)
        #print("model.count():%s"%model.count())

        return False
        
    def apply_settings(self):
        # No need to do anything with prefs here, but we could.
        prefs
