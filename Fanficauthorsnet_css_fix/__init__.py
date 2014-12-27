from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2014, Jim Miller'
__docformat__ = 'restructuredtext en'

# import sys
# if sys.version_info >= (2, 7):
#     import logging
#     logger = logging.getLogger(__name__)
#     loghandler=logging.StreamHandler()
#     loghandler.setFormatter(logging.Formatter("myimporter:%(levelname)s:%(filename)s(%(lineno)d):%(message)s"))
#     logger.addHandler(loghandler)
#     loghandler.setLevel(logging.DEBUG)
#     logger.setLevel(logging.DEBUG)

import os
from zipfile import ZipFile, ZIP_STORED, ZIP_DEFLATED

from calibre.customize import FileTypePlugin
from calibre.ebooks.metadata.meta import get_metadata, set_metadata

class FanficAuthorsNetCSSFix(FileTypePlugin):

    name                = 'fanficauthors.net CSS Fix' # Name of the plugin
    description         = 'Change the CSS on imported fanficauthors.net EPUBs to match what I prefer.'
    supported_platforms = ['windows', 'osx', 'linux'] # Platforms this plugin will run on
    author              = 'Jim Miller' # The author of this plugin
    version             = (0, 0, 2)   # The version number of this plugin
    file_types          = set(['epub']) # The file types that this plugin will be applied to
    on_import      = True
    #on_postimport  = True
    minimum_calibre_version = (2, 0, 0)

    # def initialize(self):
        # print("initialize FanficAuthorsNetCSSFix")
        # logger.warn("logger")
    
    def run(self, path_to_ebook):
        # print("run FanficAuthorsNetCSSFix")
        # logger.warn("logger")
        book_format='epub'

        ## Really crude brute force check to see if it's a
        ## fanficauthors.net epub:
        
        epub = ZipFile(path_to_ebook, 'r') # works equally well with inputio as a path or a blob
        tocfile="content/toc.ncx"
        if not (tocfile in epub.namelist() and "fanficauthors.net" in epub.read(tocfile)):
            # bail without doing anything
            return path_to_ebook

        print("It's a fanficauthors.net epub!")
        
        tmpfile = self.temporary_file('.'+book_format)

        outputepub = ZipFile(tmpfile, "w", compression=ZIP_STORED)
        outputepub.debug = 3
        outputepub.writestr("mimetype", "application/epub+zip")
        outputepub.close()
        
        ## Re-open file for content.
        outputepub = ZipFile(tmpfile, "a", compression=ZIP_DEFLATED)
        outputepub.debug = 3

        for fname in epub.namelist():
            if fname.endswith('.html'):
                outputepub.writestr(fname,epub.read(fname).replace("""body {
	margin-top: 0px;
    padding-top: 0px;
}""","""body { background-color: #FFFFFF;
        text-align: justify;
        margin: 2%;
	adobe-hyphenate: none; }"""))
            elif fname != "mimetype":
                outputepub.writestr(fname,epub.read(fname))
        
        for zf in outputepub.filelist:
            zf.create_system = 0
        outputepub.close()
        
        # file = open(path_to_ebook, 'r+b')
        ext  = os.path.splitext(path_to_ebook)[-1][1:].lower()
        mi = get_metadata(tmpfile, ext)
        mi.publisher = "fanficauthors.net"
        set_metadata(tmpfile, mi, ext)
        # return path_to_ebook
        
        return tmpfile.name

#     def postimport(self,book_id, book_format, db):
#         logger.debug("postimport:%s"%book_id)
#         from calibre.ebooks.metadata.meta import get_metadata, set_metadata

        
#         # existingepub = db.format(book_id,book_format,index_is_id=True, as_file=True)
#         # mi = get_metadata(existingepub, book_format)
#         # mi.publisher = 'Hello World'
#         # set_metadata(existingepub, mi, book_format)

#         mi = db.get_metadata(book_id,index_is_id=True)
#         mi.publisher="fanficauthors.net"
#         db.set_metadata(book_id,mi)
# #        t=1/0
