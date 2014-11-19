#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2014, Jim Miller'
__docformat__ = 'restructuredtext en'

import time, os, copy, threading
from ConfigParser import SafeConfigParser
from StringIO import StringIO
from functools import partial
from datetime import datetime

try:
    from PyQt5.Qt import (QApplication, QMenu, QToolButton)
except ImportError as e:
    from PyQt4.Qt import (QApplication, QMenu, QToolButton)

from calibre.constants import numeric_version as calibre_version

from calibre.ptempfile import PersistentTemporaryFile, PersistentTemporaryDirectory, remove_dir
from calibre.ebooks.metadata import MetaInformation, authors_to_string
from calibre.ebooks.metadata.meta import set_metadata, metadata_from_formats
from calibre.gui2 import error_dialog, warning_dialog, question_dialog, info_dialog
from calibre.gui2.dialogs.message_box import ViewLog
from calibre.gui2.dialogs.confirm_delete import confirm
from calibre.utils.date import local_tz
from calibre.constants import config_dir as calibre_config_dir

# The class that all interface action plugins must inherit from
from calibre.gui2.actions import InterfaceAction

# pulls in translation files for _() strings
try:
    load_translations()
except NameError:
    pass # load_translations() added in calibre 1.9

from calibre_plugins.epubmerge.common_utils import (set_plugin_icon_resources, get_icon, create_menu_action_unique )

from calibre_plugins.epubmerge.config import (prefs, permitted_values)

from calibre_plugins.epubmerge.epubmerge import doMerge, doUnMerge

from calibre_plugins.epubmerge.dialogs import (
    LoopProgressDialog, OrderEPUBsDialog, AddOverDiscardDialog
    )

PLUGIN_ICONS = ['images/icon.png','images/unmerge.png']

class EpubMergePlugin(InterfaceAction):

    name = 'EpubMerge'

    # Declare the main action associated with this plugin
    # The keyboard shortcut can be None if you dont want to use a keyboard
    # shortcut. Remember that currently calibre has no central management for
    # keyboard shortcuts, so try to use an unusual/unused shortcut.
    # (text, icon_path, tooltip, keyboard shortcut)
    # icon_path isn't in the zip--icon loaded below.
    action_spec = (_('EpubMerge'), None,
                   _('Merge multiple EPUBs into one in a new book.'), ())
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

        base = self.interface_action_base_plugin
        self.version = base.name+" v%d.%d.%d"%base.version

        # Read the plugin icons and store for potential sharing with the config widget
        icon_resources = self.load_resources(PLUGIN_ICONS)
        set_plugin_icon_resources(self.name, icon_resources)
        
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

        # Assign our menu to this action
        self.menu = QMenu()
        self.qaction.setMenu(self.menu)
        
    def initialization_complete(self):
        # setup menu.
        self.merge_action = self.create_menu_item_ex(self.menu, _('&Merge Epubs'), image='images/icon.png',
                                                     unique_name=_('&Merge Epubs'),
                                                     triggered=self.plugin_button )

        self.unmerge_action = self.create_menu_item_ex(self.menu, _('&UnMerge Epub'), image='images/unmerge.png',
                                                       unique_name=_('&UnMerge Epub'),
                                                       triggered=self.unmerge )


        # print("platform.system():%s"%platform.system())
        # print("platform.mac_ver()[0]:%s"%platform.mac_ver()[0])
        if not self.check_macmenuhack(): # not platform.mac_ver()[0]: # Some macs crash on these menu items for unknown reasons.
            do_user_config = self.interface_action_base_plugin.do_user_config
            self.menu.addSeparator()
            self.config_action = self.create_menu_item_ex(self.menu, _('&Configure Plugin'),
                                                          image= 'config.png',
                                                          unique_name=_('Configure EpubMerge'),
                                                          shortcut_name=_('Configure EpubMerge'),
                                                          triggered=partial(do_user_config,parent=self.gui))
        
        
        self.gui.keyboard.finalize()

    def create_menu_item_ex(self, parent_menu, menu_text, image=None, tooltip=None,
                           shortcut=None, triggered=None, is_checked=None, shortcut_name=None,
                           unique_name=None):
        #print("create_menu_item_ex before %s"%menu_text)
        ac = create_menu_action_unique(self, parent_menu, menu_text, image, tooltip,
                                       shortcut, triggered, is_checked, shortcut_name, unique_name)
        #print("create_menu_item_ex after %s"%menu_text)
        return ac

    ## Kludgey, yes, but with the real configuration inside the
    ## library now, how else would a user be able to change this
    ## setting if it's crashing calibre?
    def check_macmenuhack(self):
        try:
            return self.macmenuhack
        except:
            file_path = os.path.join(calibre_config_dir,
                                     *("plugins/fanfictiondownloader_macmenuhack.txt".split('/')))
            file_path = os.path.abspath(file_path)
            print("macmenuhack file_path:%s"%file_path)
            self.macmenuhack = os.access(file_path, os.F_OK)
            return self.macmenuhack

    def do_unmerge(self, *args, **kwargs):
        '''Also called by FFDL plugin.'''
        return doUnMerge(*args, **kwargs)
        
    def do_merge(self, *args, **kwargs):
        '''Also called by FFDL plugin.'''
        return doMerge(*args, **kwargs)
            
    def unmerge(self):
        if len(self.gui.library_view.get_selected_ids()) != 1:
            d = error_dialog(self.gui,
                             _('Select One Book'),
                             _('Please select exactly one book to UnMerge.'),
                             show_copy_button=False)
            d.exec_()
        else:
            db=self.gui.current_db
            book_id=self.gui.library_view.get_selected_ids()[0]
            if db.has_format(book_id,'EPUB',index_is_id=True):
                epub = StringIO(db.format(book_id,'EPUB',index_is_id=True))
            else:
                d = error_dialog(self.gui,
                                 _('Cannot UnMerge Non-Epubs'),
                                 _('To UnMerge the source must be Epub(s) created by EpubMerge with Keep UnMerge Metadata enabled.'),
                                 show_copy_button=False)
                d.exec_()
                remove_dir(tdir)
                return
                
            tdir = PersistentTemporaryDirectory(prefix='epubmerge_')
            print("tdir:%s"%tdir)
            outfilenames = self.do_unmerge(epub,tdir)
            if not outfilenames:
                d = error_dialog(self.gui,
                                 _('No UnMerge data found'),
                                 _('To UnMerge the source must be Epub(s) created by EpubMerge with Keep UnMerge Metadata enabled.'),
                                 show_copy_button=False)
                d.exec_()
                return

            #db.import_book_directory_multiple(tdir) XXX
            #self.gui.library_view.model().books_added(len(outfilenames))
            added_list=[]
            updated_list=[]
            for formats in db.find_books_in_directory(tdir, False):
                #print("formats:%s"%formats)
                mi = metadata_from_formats(formats)
                #print("mi:%s"%mi)

                state = 'add'
                identicalbooks = db.find_identical_books(mi)
                if identicalbooks:
                    if len(identicalbooks) == 1:
                        text = _("You already have a book <i>%s</i> by <i>%s</i>.  You may Add a new book of the same title, Overwrite the Epub in the existing book, or Discard this Epub.")%(mi.title,", ".join(mi.authors))
                        over=True
                    else:
                        text = ("You already have more than one book <i>%s</i> by <i>%s</i>.  You may Add a new book of the same title, or Discard this Epub.")%(mi.title,", ".join(mi.authors))
                        over=False
                    d = AddOverDiscardDialog(self.gui,self.qaction.icon(),text,over=over)
                    d.exec_()
                    state=d.state
                    
                if not state or state == 'discard':
                    continue
                elif state == 'add':
                    book_id = db.create_book_entry(mi,
                                                   add_duplicates=True)
                    added_list.append(book_id)
                else:
                    book_id = identicalbooks.pop()
                        
                db.add_format_with_hooks(book_id,
                                         'EPUB',
                                         formats[0], index_is_id=True)
                updated_list.append(book_id)

            if len(added_list):
                self.gui.library_view.model().books_added(len(added_list))

            if len(updated_list):
                self.gui.library_view.model().refresh_ids(updated_list)
            
            remove_dir(tdir)

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
            
            book_list = map( partial(self._convert_id_to_book, good=False), self.gui.library_view.get_selected_ids() )
            # book_ids = self.gui.library_view.get_selected_ids()

            LoopProgressDialog(self.gui,
                               book_list,
                               partial(self._populate_book_from_calibre_id, db=self.gui.current_db),
                               self._start_merge,
                               init_label=_("Collecting EPUBs for merger..."),
                               win_title=_("Get EPUBs for merge"),
                               status_prefix=_("EPUBs collected"))
                
    def _start_merge(self,book_list):
        db=self.gui.current_db
        self.previous = self.gui.library_view.currentIndex()
        # if any bad, bail.
        bad_list = filter(lambda x : not x['good'], book_list)
        if len(bad_list) > 0:
            d = error_dialog(self.gui,
                             _('Cannot Merge Epubs'),
                             _('%s books failed.')%len(bad_list),
                             det_msg='\n'.join(map(lambda x : x['error'] , bad_list)))
            d.exec_()
        else:
            d = OrderEPUBsDialog(self.gui,
                                 _('Order EPUBs to Merge'),
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

            deftitle = "%s %s" % (book_list[0]['title'],prefs['mergeword'])
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
            mi.tags.extend(prefs['mergetags'].split(','))

            # print("======================= mergetags:\n%s\n========================="%prefs['mergetags'])
            # print("======================= m.tags:\n%s\n========================="%mi.tags)
            
            languageslists = map(lambda x : x['languages'], book_list)
            mi.languages = [item for sublist in languageslists for item in sublist]

            mi.series = ''

            # ======================= make book comments =========================
            
            if len(mi.authors) > 1:
                booktitle = lambda x : _("%s by %s") % (x['title'],' & '.join(x['authors']))
            else:
                booktitle = lambda x : x['title']
                
            mi.comments = (_("%s containing:")+"\n\n") % prefs['mergeword']
            
            if prefs['includecomments']:
                def bookcomments(x):
                    if x['comments']:
                        return '<b>%s</b>\n\n%s'%(booktitle(x),x['comments'])
                    else:
                        return '<b>%s</b>\n'%booktitle(x)
                    
                mi.comments += ('<div class="mergedbook">' +
                                '<hr></div><div class="mergedbook">'.join([ bookcomments(x) for x in book_list]) +
                                '</div>')
            else:
                mi.comments += '\n'.join( [ booktitle(x) for x in book_list ] )
                
            # ======================= make book entry =========================

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

                if action in ('add','average','averageall'):
                    value = 0.0
                    count = 0
                    for bid in idslist:
                        try:
                            value += db.get_custom(bid, label=label, index_is_id=True)
                            found = True
                            # only count ones with values unless averageall
                            count += 1
                        except:
                            # if not set, it's None and fails.
                            # only count ones with values unless averageall
                            if action == 'averageall':
                                count += 1
                                
                    if found and action in ('average','averageall'):
                        value = value / count
                        
                    if coldef['datatype'] == 'int':
                        value += 0.5 # so int rounds instead of truncs.
                
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
            
            confirm('\n'+_('''The book for the new Merged EPUB has been created and default metadata filled in.

However, the EPUB will *not* be created until after you've reviewed, edited, and closed the metadata dialog that follows.'''),
                    'epubmerge_created_now_edit_again',
                    self.gui)
            
            self.gui.iactions['Edit Metadata'].edit_metadata(False)

            print("5:%s"%(time.time()-self.t))
            self.t = time.time()
            self.gui.tags_view.recount()

            totalsize = sum(map(lambda x : x['epub_size'], book_list))

            print("merging %s EPUBs totaling %s"%(len(book_list),gethumanreadable(totalsize)))
            if len(book_list) > 100 or totalsize > 5*1024*1024:
                confirm('\n'+_('''You're merging %s EPUBs totaling %s.  Calibre will be locked until the merge is finished.''')%(len(book_list),gethumanreadable(totalsize)),
                        'epubmerge_edited_now_merge_again',
                        self.gui)
            
            self.gui.status_bar.show_message(_('Merging %s EPUBs...')%len(book_list), 60000)

            mi = db.get_metadata(book_id,index_is_id=True)
            
            mergedepub = PersistentTemporaryFile(suffix='.epub')
            epubstomerge = map(lambda x : x['epub'] , book_list)
            
            coverjpgpath = None
            if mi.has_cover:
                # grab the path to the real image.
                coverjpgpath = os.path.join(db.library_path, db.path(book_id, index_is_id=True), 'cover.jpg')
                
            self.do_merge( mergedepub,
                           epubstomerge,
                           authoropts=mi.authors,
                           titleopt=mi.title,
                           descopt=mi.comments,
                           tags=mi.tags,
                           languages=mi.languages,
                           titlenavpoints=prefs['titlenavpoints'],
                           flattentoc=prefs['flattentoc'],
                           printtimes=True,
                           coverjpgpath=coverjpgpath,
                           keepmetadatafiles=prefs['keepmeta'] )
                 
            print("6:%s"%(time.time()-self.t))
            print(_("Merge finished, output in:\n%s")%mergedepub.name)
            self.t = time.time()
            db.add_format_with_hooks(book_id,
                                     'EPUB',
                                     mergedepub, index_is_id=True)
            
            print("7:%s"%(time.time()-self.t))
            self.t = time.time()
            
            self.gui.status_bar.show_message(_('Finished merging %s EPUBs.')%len(book_list), 3000)
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
        book['title'] = _('Unknown')
        book['author'] = _('Unknown')
        book['author_sort'] = _('Unknown')
        book['error'] = ''
        book['comments'] = ''
      
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
        book['comments'] = mi.comments
        if book['series']:
            book['series_index'] = mi.series_index
        else:
            book['series_index'] = None
        book['languages'] = mi.languages
        book['error'] = ''
        if db.has_format(mi.id,'EPUB',index_is_id=True):
            book['epub'] = StringIO(db.format(mi.id,'EPUB',index_is_id=True))
            if prefs['keepmeta']:
                set_metadata(book['epub'], mi, stream_type='epub')
            book['epub_size'] = len(book['epub'].getvalue())
        else:
            book['good'] = False;
            book['error'] = _("%s by %s doesn't have an EPUB.")%(mi.title,', '.join(mi.authors))

def gethumanreadable(size,precision=1):
    suffixes=['B','KB','MB','GB','TB']
    suffixIndex = 0
    while size > 1024:
        suffixIndex += 1 #increment the index of the suffix
        size = size/1024.0 #apply the division
    return "%.*f%s"%(precision,size,suffixes[suffixIndex])
