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

from calibre.ptempfile import PersistentTemporaryFile, PersistentTemporaryDirectory, remove_dir
from calibre.ebooks.metadata import MetaInformation, authors_to_string
from calibre.ebooks.metadata.meta import get_metadata
from calibre.gui2 import error_dialog, warning_dialog, question_dialog, info_dialog
from calibre.gui2.dialogs.message_box import ViewLog
from calibre.gui2.dialogs.confirm_delete import confirm
from calibre.utils.date import local_tz

# The class that all interface action plugins must inherit from
from calibre.gui2.actions import InterfaceAction

from calibre_plugins.epubmerge.common_utils import (set_plugin_icon_resources, get_icon)

from calibre_plugins.epubmerge.config import (prefs, permitted_values)

from calibre_plugins.epubmerge.epubmerge import doMerge

from calibre_plugins.epubmerge.dialogs import (
    LoopProgressDialog, OrderEPUBsDialog
    )

PLUGIN_ICONS = ['images/icon.png']

class EpubMergePlugin(InterfaceAction):

    name = 'EpubMerge'

    # Declare the main action associated with this plugin
    # The keyboard shortcut can be None if you dont want to use a keyboard
    # shortcut. Remember that currently calibre has no central management for
    # keyboard shortcuts, so try to use an unusual/unused shortcut.
    # (text, icon_path, tooltip, keyboard shortcut)
    # icon_path isn't in the zip--icon loaded below.
    action_spec = (name, None,
                   'Merge multiple EPUBs into one in a new book.', ())
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
        
        if len(self.gui.library_view.get_selected_ids()) < 2:
            d = error_dialog(self.gui,
                             _('Cannot Merge Epubs'),
                             _('Less than 2 books selected.'),
                             show_copy_button=False)
            d.exec_()
        else:
            db=self.gui.current_db

            print("1:%s"%(time.time()-self.t))
            self.t = time.time()
            
            # epubstomerge = []
            # for book_id in self.gui.library_view.get_selected_ids():
            #     epubstomerge.append(StringIO(db.format(book_id,'EPUB',index_is_id=True)))

            book_list = map( partial(self._convert_id_to_book, good=False), self.gui.library_view.get_selected_ids() )
            # book_ids = self.gui.library_view.get_selected_ids()

            LoopProgressDialog(self.gui,
                               book_list,
                               partial(self._populate_book_from_calibre_id, db=self.gui.current_db),
                               self._start_merge,
                               init_label="Collecting EPUBs for merger...",
                               win_title="Get EPUBs for merg",
                               status_prefix="EPUBs collected")
                
    def _start_merge(self,book_list):
        db=self.gui.current_db
        self.previous = self.gui.library_view.currentIndex()
        # if any bad, bail.
        bad_list = filter(lambda x : not x['good'], book_list)
        if len(bad_list) > 0:
            d = error_dialog(self.gui,
                             'Cannot Merge Epubs',
                             '%s books failed.'%len(bad_list),
                             det_msg='\n'.join(map(lambda x : x['comment'] , bad_list)))
            d.exec_()
        else:
            d = OrderEPUBsDialog(self.gui,
                                 'Order EPUBs to Merge',
                                 prefs,
                                 self.qaction.icon(),
                                 book_list,
                                 )
            d.exec_()
            if d.result() != d.Accepted:
                return

            book_list = d.get_books()
            
            print("2:%s"%(time.time()-self.t))
            self.t = time.time()

            #mi = get_metadata(mergedepub,'EPUB')
            deftitle = "%s Anthology" % book_list[0]['title']
            mi = MetaInformation(deftitle,["Temp Author"])

            # if all same series, use series for name.  But only if all.
            serieslist = map(lambda x : x['series'], filter(lambda x : x['series'] != None, book_list))
            if len(serieslist) == len(book_list):
                mi.title = serieslist[0]
                for sr in serieslist:
                    if mi.title != sr:
                        mi.title = deftitle;
                        break
                
            # print("======================= mi.title:\n%s\n========================="%mi.title)

            mi.authors = list()
            authorslists = map(lambda x : x['authors'], book_list)
            for l in authorslists:
                for a in l:
                    if a not in mi.authors:
                        mi.authors.append(a)
            #mi.authors = [item for sublist in authorslists for item in sublist]

            # print("======================= mi.authors:\n%s\n========================="%mi.authors)
            
            #mi.author_sort = ' & '.join(map(lambda x : x['author_sort'], book_list))

            # print("======================= mi.author_sort:\n%s\n========================="%mi.author_sort)
            
            tagslists = map(lambda x : x['tags'], book_list)
            mi.tags = [item for sublist in tagslists for item in sublist]

            # print("======================= m.tagsi:\n%s\n========================="%mi.tags)
            
            languageslists = map(lambda x : x['languages'], book_list)
            mi.languages = [item for sublist in languageslists for item in sublist]

            mi.series = ''

            mi.comments = "Anthology containing:\n\n" + \
                '\n'.join(map(lambda x : "%s by %s" % \
                                  (x['title'],' & '.join(x['authors'])), book_list))
            

            # print("======================= mi.languages:\n%s\n========================="%mi.languages)

            book_id = db.create_book_entry(mi,
                                           add_duplicates=True)

            # set default cover to same as first book
            coverdata = db.cover(book_list[0]['calibre_id'],index_is_id=True)
            if coverdata:
                db.set_cover(book_id, coverdata)
            
            # ======================= custom columns ===================

            print("3:%s"%(time.time()-self.t))
            self.t = time.time()

            # have to get custom from db for each book.
            idslist = map(lambda x : x['calibre_id'], book_list)
            
            custom_columns = self.gui.library_view.model().custom_columns
            for col, action in prefs['custom_cols'].iteritems():
                #print("col: %s action: %s"%(col,action))
                
                if col not in custom_columns:
                    print("%s not an existing column, skipping."%col)
                    continue
                
                coldef = custom_columns[col]
                #print("coldef:%s"%coldef)
                
                if action not in permitted_values[coldef['datatype']]:
                    print("%s not a valid column type for %s, skipping."%(col,action))
                    continue
                
                label = coldef['label']

                found = False
                value = None
                idx = None
                if action == 'first':
                    idx = 0

                if action == 'last':
                    idx = -1

                if action in ['first','last']:
                    value = db.get_custom(idslist[idx], label=label, index_is_id=True)
                    if coldef['datatype'] == 'series' and value != None:
                        # get the number-in-series, too.
                        value = "%s [%s]"%(value, db.get_custom_extra(idslist[idx], label=label, index_is_id=True))
                    found = True

                if action == 'add':
                    value = 0.0
                    for bid in idslist:
                        try:
                            value += db.get_custom(bid, label=label, index_is_id=True)
                            found = True
                        except:
                            # if not set, it's None and fails.
                            pass
                
                if action == 'and':
                    value = True
                    for bid in idslist:
                        try:
                            value = value and db.get_custom(bid, label=label, index_is_id=True)
                            found = True
                        except:
                            # if not set, it's None and fails.
                            pass
                
                if action == 'or':
                    value = False
                    for bid in idslist:
                        try:
                            value = value or db.get_custom(bid, label=label, index_is_id=True)
                            found = True
                        except:
                            # if not set, it's None and fails.
                            pass
                
                if action == 'newest':
                    value = None
                    for bid in idslist:
                        try:
                            ivalue = db.get_custom(bid, label=label, index_is_id=True)
                            if not value or  ivalue > value:
                                value = ivalue
                                found = True
                        except:
                            # if not set, it's None and fails.
                            pass
                    
                if action == 'oldest':
                    value = None
                    for bid in idslist:
                        try:
                            ivalue = db.get_custom(bid, label=label, index_is_id=True)
                            if not value or  ivalue < value:
                                value = ivalue
                                found = True
                        except:
                            # if not set, it's None and fails.
                            pass
                    
                if action == 'union':
                    if not coldef['is_multiple']:
                        action = 'concat'
                    else:
                        value = set()
                        for bid in idslist:
                            try:
                                value = value.union(db.get_custom(bid, label=label, index_is_id=True))
                                found = True
                            except:
                                # if not set, it's None and fails.
                                pass
                        
                if action == 'concat':
                    value = ""
                    for bid in idslist:
                        try:
                            value = value + ' ' + db.get_custom(bid, label=label, index_is_id=True)
                            found = True
                        except:
                            # if not set, it's None and fails.
                            pass
                    value = value.strip()
                    
                if found and value != None:
                    db.set_custom(book_id,value,label=label,commit=False)
                
            db.commit()
            
            print("4:%s"%(time.time()-self.t))
            self.t = time.time()
            
            self.gui.library_view.model().books_added(1)
            self.gui.library_view.select_rows([book_id])
            
            print("5:%s"%(time.time()-self.t))
            self.t = time.time()
            
            confirm(u'''
The book for the new Merged EPUB has been created and default metadata filled in.

However, the EPUB will *not* be created until after you've reviewed, edited, and closed the metadata dialog that follows.
''',
                    'epubmerge_created_now_edit_again',
                    self.gui)
            
            self.gui.iactions['Edit Metadata'].edit_metadata(False)

            print("5:%s"%(time.time()-self.t))
            self.t = time.time()
            self.gui.tags_view.recount()

            totalsize = sum(map(lambda x : x['epub_size'], book_list))

            print("merging %s EPUBs totaling %s"%(len(book_list),gethumanreadable(totalsize)))
            if len(book_list) > 100 or totalsize > 5*1024*1024:
                confirm(u'''
You're merging %s EPUBs totaling %s.  Calibre will be locked until the merge is finished.
'''%(len(book_list),gethumanreadable(totalsize)),
                        'epubmerge_edited_now_merge_again',
                        self.gui)
            
            self.gui.status_bar.show_message('Merging %s EPUBs...'%len(book_list), 60000)

            mi = db.get_metadata(book_id,index_is_id=True)
            
            mergedepub = PersistentTemporaryFile(suffix='.epub')
            epubstomerge = map(lambda x : x['epub'] , book_list)
            
            coverjpgpath = None
            if mi.has_cover:
                # grab the path to the real image.
                coverjpgpath = os.path.join(db.library_path, db.path(book_id, index_is_id=True), 'cover.jpg')
                
            doMerge( mergedepub,
                     epubstomerge,
                     authoropts=mi.authors,
                     titleopt=mi.title,
                     descopt=mi.comments,
                     tags=mi.tags,
                     languages=mi.languages,
                     titlenavpoints=prefs['titlenavpoints'],
                     flattentoc=prefs['flattentoc'],
                     printtimes=True,
                     coverjpgpath=coverjpgpath
                     )
            
            print("6:%s"%(time.time()-self.t))
            self.t = time.time()
            db.add_format_with_hooks(book_id,
                                     'EPUB',
                                     mergedepub, index_is_id=True)
            
            print("7:%s"%(time.time()-self.t))
            self.t = time.time()
            
            self.gui.status_bar.show_message('Finished merging %s EPUBs.'%len(book_list), 3000)
            self.gui.library_view.model().refresh_ids([book_id])
            self.gui.tags_view.recount()
            current = self.gui.library_view.currentIndex()
            self.gui.library_view.model().current_changed(current, self.previous)
            #self.gui.iactions['View'].view_book(False)

    def apply_settings(self):
        # No need to do anything with perfs here, but we could.
        prefs
        
    def _convert_id_to_book(self, idval, good=True):
        book = {}
        book['good'] = good
        book['calibre_id'] = idval
        book['title'] = 'Unknown'
        book['author'] = 'Unknown'
        book['author_sort'] = 'Unknown'
        book['comment'] = ''
      
        return book
        
    def _populate_book_from_calibre_id(self, book, db=None):
        mi = db.get_metadata(book['calibre_id'], index_is_id=True)
        #book = {}
        book['good'] = True
        book['calibre_id'] = mi.id
        book['title'] = mi.title
        book['authors'] = mi.authors
        book['author_sort'] = mi.author_sort
        book['tags'] = mi.tags
        book['series'] = mi.series
        if book['series']:
            book['series_index'] = mi.series_index
        else:
            book['series_index'] = None
        book['languages'] = mi.languages
        book['comment'] = ''
        if db.has_format(mi.id,'EPUB',index_is_id=True):
            book['epub'] = StringIO(db.format(mi.id,'EPUB',index_is_id=True))
            book['epub_size'] = len(book['epub'].getvalue())
        else:
            book['good'] = False;
            book['comment'] = "%s by %s doesn't have an EPUB."%(mi.title,', '.join(mi.authors))

def gethumanreadable(size,precision=1):
    suffixes=['B','KB','MB','GB','TB']
    suffixIndex = 0
    while size > 1024:
        suffixIndex += 1 #increment the index of the suffix
        size = size/1024.0 #apply the division
    return "%.*f%s"%(precision,size,suffixes[suffixIndex])
