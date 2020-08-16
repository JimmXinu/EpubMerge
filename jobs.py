# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import,
                        print_function)
import six

__license__   = 'GPL v3'
__copyright__ = '2020, Jim Miller, 2011, Grant Drake <grant.drake@gmail.com>'
__docformat__ = 'restructuredtext en'

import logging
logger = logging.getLogger(__name__)

import traceback
import time
from io import StringIO
from collections import defaultdict

from calibre.ptempfile import PersistentTemporaryFile
from calibre.utils.ipc.server import Server
from calibre.utils.ipc.job import ParallelJob
from calibre.ebooks.oeb.polish.container import get_container
from calibre.ebooks.conversion.cli import main as ebook_convert_cli_main

from calibre_plugins.epubmerge.epubmerge import doMerge, doUnMerge

# pulls in translation files for _() strings
try:
    load_translations()
except NameError:
    pass # load_translations() added in calibre 1.9

# ------------------------------------------------------------------------------
#
#              Functions to perform downloads using worker jobs
#
# ------------------------------------------------------------------------------

def do_merge_bg(args,
                cpus,
                notification=lambda x,y:x):
    logger.info("do_merge_bg(%s,%s)"%(args,cpus))

    # XXX - add meaningful % done
    # This server is an arbitrary_n job, so there is a notifier available.
    # Set the % complete to a small number to avoid the 'unavailable' indicator
    # notification(0.01, _('Downloading FanFiction Stories'))
    # notification(float(count)/total, _('%d of %d stories finished downloading')%(count,total))

    # XXX - add error catching & reporting

    for j in range(0,len(args['inputepubfns'])):
        fn = args['inputepubfns'][j]
        try:
            container = get_container(fn)
            if container.opf_version_parsed.major >= 3:
                logger.info("found epub3: %s"%fn)
                # this temp file is deleted when the BG process quits,
                # so don't expect it to still be there.
                epub2 = PersistentTemporaryFile(prefix="epub2_",
                                                suffix=".epub",
                                                dir=args['tdir'])
                fn2 = epub2.name
                # ebook-convert epub3.epub epub2.epub --epub-version=2
                ebook_convert_cli_main(['epubmerge calling convert',fn,fn2,'--epub-version=2','--no-default-epub-cover'])
                args['inputepubfns'][j] = fn2
                logger.info("Converted to epub2:%s"%fn2)
                # book['good'] = False;
                # book['error'] = _("%s by %s is EPUB3, EpubMerge only supports EPUB2.")%(mi.title,', '.join(mi.authors))
        except:
            raise
            # XXX do something useful
            pass

    doMerge(args['outputepubfn'],
            args['inputepubfns'],
            args['authoropts'],
            args['titleopt'],
            args['descopt'],
            args['tags'],
            args['languages'],
            args['titlenavpoints'],
            args['originalnavpoints'],
            args['flattentoc'],
            args['printtimes'],
            args['coverjpgpath'],
            args['keepmetadatafiles'])

#    time.sleep(30)
    return (args,"Done")

