#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Jim Miller'
__docformat__ = 'restructuredtext en'

import time

from calibre.gui2 import question_dialog

# The class that all interface action plugins must inherit from
from calibre.gui2.actions import InterfaceAction

from calibre_plugins.smarteject.common_utils import get_icon
from calibre_plugins.smarteject.config import prefs

# PLUGIN_ICONS = ['images/icon.png']

class SmartEjectPlugin(InterfaceAction):

    name = 'SmartEject'

    # Declare the main action associated with this plugin
    # The keyboard shortcut can be None if you dont want to use a keyboard
    # shortcut. Remember that currently calibre has no central management for
    # keyboard shortcuts, so try to use an unusual/unused shortcut.
    # (text, icon_path, tooltip, keyboard shortcut)
    # icon_path isn't in the zip--icon loaded below.
    action_spec = (name, None,
                   'Check for duplicated/deleted/added books before ejecting.', ())
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

        self.qaction.setText('SmartEject')
        # The qaction is automatically created from the action_spec defined
        # above
        self.qaction.setIcon(icon)

        # Call function when plugin triggered.
        self.qaction.triggered.connect(self.plugin_button)

    def plugin_button(self):

        t = time.time()
        if prefs['checkdups'] and self.gui.library_view.model().db.search_getting_ids(prefs['checkdups_search'], None):
            print("dups find:%s"%(time.time()-t))
            t = time.time()
            
            if question_dialog(self.gui, "Duplicates on Device", "There are duplicate ebooks on the device.<p>Display duplicates?", show_copy_button=False):
#            print("Duplicates on Device warning:%s"%warning_dialog(self.gui, "Duplicates on Device", "There are duplicate ebooks on the device.", show=True, show_copy_button=False))
                t = time.time()
                self.gui.location_manager._location_selected('library')
                print("select library:%s"%(time.time()-t))
                t = time.time()
                self.gui.search.setEditText(prefs['checkdups_search'])
                print("setEditText:%s"%(time.time()-t))
                t = time.time()
                self.gui.search.do_search()
                print("do_search:%s"%(time.time()-t))
                t = time.time()
                return

        if prefs['checknotinlibrary'] and self.checkdevice(self.gui.memory_view.model(),"Main"):
            t = time.time()
            self.gui.location_manager._location_selected('main')
            print("_location_selected('main'):%s"%(time.time()-t))
            return
        
        if prefs['checknotinlibrary'] and self.checkdevice(self.gui.card_a_view.model(),"Card A"):
            t = time.time()
            self.gui.location_manager._location_selected('carda')
            print("_location_selected('carda'):%s"%(time.time()-t))
            return
        
        if prefs['checknotinlibrary'] and self.checkdevice(self.gui.card_b_view.model(),"Card B"):
            t = time.time()
            self.gui.location_manager._location_selected('cardb')
            print("_location_selected('cardb'):%s"%(time.time()-t))
            return
        
        t = time.time()
        if prefs['checknotondevice'] and self.gui.library_view.model().db.search_getting_ids(prefs['checknotondevice_search'], None):
            print("checknotondevice find:%s"%(time.time()-t))
            t = time.time()
            
            if question_dialog(self.gui,
                               "Books in Library not on Device",
                               "There are books in the Library that are not on the Device.<p>Display books not on Device?",
                               show_copy_button=False):
                t = time.time()
                self.gui.location_manager._location_selected('library')
                print("select library:%s"%(time.time()-t))
                t = time.time()
                self.gui.search.setEditText(prefs['checknotondevice_search'])
                print("setEditText:%s"%(time.time()-t))
                t = time.time()
                self.gui.search.do_search()
                print("do_search:%s"%(time.time()-t))
                t = time.time()
                return
            
        # savesearch = self.gui.memory_view.model().last_search
        # print("\nself.gui.memory_view.model().last_search:%s"%self.gui.memory_view.model().last_search)
        # print("self.gui.memory_view.model().count():%s"%self.gui.memory_view.model().count())
        # self.gui.memory_view.model().search('inlibrary:false')
        # print("self.gui.memory_view.model().count():%s"%self.gui.memory_view.model().count())
        # if self.gui.memory_view.model().count() > 0:
        #     warning_dialog(self.gui, "Books on Device not in Library", "There are books on the device not in Library.", show=True)
        #     return        
        # self.gui.memory_view.model().search(savesearch)
        # print("self.gui.memory_view.model().count():%s"%self.gui.memory_view.model().count())
        
        t = time.time()
        self.gui.location_manager._location_selected('library')
        print("_location_selected('library'):%s"%(time.time()-t))
        
        t = time.time()
        self.gui.location_manager._eject_requested()
        print("_eject_requested:%s"%(time.time()-t))

        # if one of the configured searchs, clear it.
        print("self.gui.search.current_text :(%s)"%self.gui.search.current_text )
        if self.gui.search.current_text in (prefs['checkdups_search'],prefs['checknotinlibrary_search'],prefs['checknotondevice_search']): 
            t = time.time()
            self.gui.search.clear()
            print("search.clear:%s"%(time.time()-t))

    def checkdevice(self,model,loc):
        savesearch = model.last_search
        #print("\nmodel.last_search:%s"%model.last_search)
        #print("model.count():%s"%model.count())
        t = time.time()
        model.search('inlibrary:false')
        print("checkdevice model.search:%s"%(time.time()-t))
        t = time.time()
        #print("model.count():%s"%model.count())
        if model.count() > 0:
            if question_dialog(self.gui, "Books on Device not in Library", "There are books on the device in %s that are not in the Library.<p>Display books not in Library?"%loc, show_copy_button=False):
#            print("not in Library warning:%s"%warning_dialog(self.gui, "Books on Device not in Library", "There are books on the device not in Library.", show=True, show_copy_button=False))
                t = time.time()
                self.gui.search.setEditText(prefs['checknotinlibrary_search'])
                print("checkdevice setEditText:%s"%(time.time()-t))
                t = time.time()
                self.gui.search.do_search()
                print("checkdevice do_search:%s"%(time.time()-t))
                t = time.time()
                return True
        model.search(savesearch)
        print("checkdevice savesearch:%s"%(time.time()-t))
        t = time.time()
        #print("model.count():%s"%model.count())

        return False
        
    def apply_settings(self):
        # No need to do anything with prefs here, but we could.
        prefs
        
