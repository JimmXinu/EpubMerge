#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Jim Miller'
__docformat__ = 'restructuredtext en'

import time, os, copy, threading
from ConfigParser import SafeConfigParser
from StringIO import StringIO
from functools import partial
from datetime import datetime

from PyQt4.Qt import (QApplication, QMenu, QToolButton)

from calibre.ptempfile import PersistentTemporaryFile
from calibre.ebooks.metadata import MetaInformation, authors_to_string
from calibre.ebooks.metadata.book.formatter import SafeFormat
from calibre.ebooks.metadata.meta import get_metadata
from calibre.gui2 import error_dialog, warning_dialog, question_dialog, info_dialog
from calibre.gui2.dialogs.message_box import ViewLog
from calibre.gui2.dialogs.confirm_delete import confirm
from calibre.utils.date import local_tz

# The class that all interface action plugins must inherit from
from calibre.gui2.actions import InterfaceAction

from calibre_plugins.epubsplit.common_utils import (set_plugin_icon_resources, get_icon)

from calibre_plugins.epubsplit.config import prefs

from calibre_plugins.epubsplit.epubsplit import SplitEpub

from calibre_plugins.epubsplit.dialogs import (
    #LoopProgressDialog,
    SelectLinesDialog
    )

PLUGIN_ICONS = ['images/icon.png']

class EpubSplitPlugin(InterfaceAction):

    name = 'EpubSplit'

    # Declare the main action associated with this plugin
    # The keyboard shortcut can be None if you dont want to use a keyboard
    # shortcut. Remember that currently calibre has no central management for
    # keyboard shortcuts, so try to use an unusual/unused shortcut.
    # (text, icon_path, tooltip, keyboard shortcut)
    # icon_path isn't in the zip--icon loaded below.
    action_spec = (name, None,
                   'Split off part of an EPUB into a new book.', ())
    # None for keyboard shortcut doesn't allow shortcut.  () does, there just isn't one yet

    action_type = 'global'
    # make button menu drop down only
    #popup_type = QToolButton.InstantPopup

    # disable when not in library. (main,carda,cardb)
    def location_selected(self, loc):
        enabled = loc == 'library'
        self.qaction.setEnabled(enabled)
        self.menuless_qaction.setEnabled(enabled)
        
    def genesis(self):

        # This method is called once per plugin, do initial setup here

        # Read the plugin icons and store for potential sharing with the config widget
        icon_resources = self.load_resources(PLUGIN_ICONS)
        set_plugin_icon_resources(self.name, icon_resources)
        
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
        icon = get_icon('images/icon.png')

        # The qaction is automatically created from the action_spec defined
        # above
        self.qaction.setIcon(icon)

        # Call function when plugin triggered.
        self.qaction.triggered.connect(self.plugin_button)

    def plugin_button(self):
        self.t = time.time()
        
        if len(self.gui.library_view.get_selected_ids()) != 1:
            d = error_dialog(self.gui,
                             _('Select One Book'),
                             _('Please select exactly one book to split.'),
                             show_copy_button=False)
            d.exec_()
        else:
            self.previous = self.gui.library_view.currentIndex()
            db=self.gui.current_db

            #print("1:%s"%(time.time()-self.t))
            self.t = time.time()

            source_id = self.gui.library_view.get_selected_ids()[0]

            misource = db.get_metadata(source_id, index_is_id=True)
            
            if db.has_format(source_id,'EPUB',index_is_id=True):
                splitepub = SplitEpub(StringIO(db.format(source_id,'EPUB',index_is_id=True)))
            else:
                d = error_dialog(self.gui, _('No EPUB'),
                                 _('This plugin only works on EPUB format ebooks.'))
                d.exec_()
                return

            lines = splitepub.get_split_lines()

            # for line in lines:
            #     print("line(%d):%s"%(line['num'],line))
            # print()
            
            d = SelectLinesDialog(self.gui,
                                  'Select Sections to Split Off',
                                  prefs,
                                  self.qaction.icon(),
                                  lines,
                                  partial(self._do_split, db, source_id, misource, splitepub)
                                  )
            d.exec_()

            return
        
            if d.result() != d.Accepted:
                return
            
    def _do_split(self, db, source_id, misource, splitepub, newspecs):
    
            linenums,changedtocs = newspecs
            #print("updated tocs:%s"%changedtocs)
            
            #print("2:%s"%(time.time()-self.t))
            self.t = time.time()

            #print("linenums:%s"%linenums)
            
            deftitle = None
            defauthors = None
            
            if prefs['copytitle']:
                deftitle = "%s Split" % misource.title
                
            if prefs['copyauthors']:
                defauthors = misource.authors
                
            mi = MetaInformation(deftitle,defauthors)

            if prefs['copytags']:
                mi.tags = misource.tags # [item for sublist in tagslists for item in sublist]

            if prefs['copylanguages']:
                mi.languages = misource.languages

            if prefs['copyseries']:
                mi.series = misource.series

            if prefs['copydate']:
                mi.timestamp = misource.timestamp

            if prefs['copyrating']:
                mi.rating = misource.rating

            if prefs['copypubdate']:
                mi.pubdate = misource.pubdate

            if prefs['copypublisher']:
                mi.publisher = misource.publisher

            if prefs['copyidentifiers']:
                mi.set_identifiers(misource.get_identifiers())

            if prefs['copycomments'] and misource.comments:
                mi.comments = "Split from:\n\n" + misource.comments
            
            book_id = db.create_book_entry(mi,
                                           add_duplicates=True)

            if prefs['copycover'] and misource.has_cover:
                db.set_cover(book_id, db.cover(source_id,index_is_id=True))

            #print("3:%s"%(time.time()-self.t))
            self.t = time.time()

            custom_columns = self.gui.library_view.model().custom_columns
            for col, action in prefs['custom_cols'].iteritems():
                #print("col: %s action: %s"%(col,action))
                
                if col not in custom_columns:
                    #print("%s not an existing column, skipping."%col)
                    continue
                
                coldef = custom_columns[col]
                #print("coldef:%s"%coldef)
                label = coldef['label']
                value = db.get_custom(source_id, label=label, index_is_id=True)
                if value:
                    db.set_custom(book_id,value,label=label,commit=False)
            
            #print("3.5:%s"%(time.time()-self.t))
            self.t = time.time()

            if prefs['sourcecol'] != '' and prefs['sourcecol'] in custom_columns \
                    and prefs['sourcetemplate']:
                val = SafeFormat().safe_format(prefs['sourcetemplate'], misource, 'EpubSplit Source Template Error', misource)
                #print("Attempting to set %s to %s"%(prefs['sourcecol'],val))
                label = custom_columns[prefs['sourcecol']]['label']
                db.set_custom(book_id, val, label=label, commit=False)
                
            db.commit()
            
            #print("4:%s"%(time.time()-self.t))
            self.t = time.time()
            
            self.gui.library_view.model().books_added(1)
            self.gui.library_view.select_rows([book_id])
            
            #print("5:%s"%(time.time()-self.t))
            self.t = time.time()
            
            confirm(u'''
The book for the new Split EPUB has been created and default metadata filled in.

However, the EPUB will *not* be created until after you've reviewed, edited, and closed the metadata dialog that follows.

You can fill in the metadata yourself, or use download metadata for known books.

If you download or add a cover image, it will be included in the generated EPUB.
''',
                    'epubsplit_created_now_edit_again',
                    self.gui)
            
            self.gui.iactions['Edit Metadata'].edit_metadata(False)

            #print("5:%s"%(time.time()-self.t))
            self.t = time.time()
            self.gui.tags_view.recount()

            self.gui.status_bar.show_message('Splitting off from EPUB...', 60000)

            mi = db.get_metadata(book_id,index_is_id=True)
            
            outputepub = PersistentTemporaryFile(suffix='.epub')

            coverjpgpath = None
            if mi.has_cover:
                # grab the path to the real image.
                coverjpgpath = os.path.join(db.library_path, db.path(book_id, index_is_id=True), 'cover.jpg')
                
            splitepub.write_split_epub(outputepub,
                                       linenums,
                                       changedtocs=changedtocs,
                                       authoropts=mi.authors,
                                       titleopt=mi.title,
                                       descopt=mi.comments,
                                       tags=mi.tags,
                                       languages=mi.languages,
                                       coverjpgpath=coverjpgpath)
            
            #print("6:%s"%(time.time()-self.t))
            self.t = time.time()
            db.add_format_with_hooks(book_id,
                                     'EPUB',
                                     outputepub, index_is_id=True)

            #print("7:%s"%(time.time()-self.t))
            self.t = time.time()
            
            self.gui.status_bar.show_message('Finished splitting off EPUB.', 3000)
            self.gui.library_view.model().refresh_ids([book_id])
            self.gui.tags_view.recount()
            current = self.gui.library_view.currentIndex()
            self.gui.library_view.model().current_changed(current, self.previous)

    def apply_settings(self):
        # No need to do anything with prefs here, but we could.
        prefs
        
