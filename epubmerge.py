#!/usr/bin/python
# -*- coding: utf-8 -*-

__license__   = 'GPL v3'
__copyright__ = '2012, Jim Miller'
__docformat__ = 'restructuredtext en'

import sys
import os
import re
from StringIO import StringIO
from urllib import unquote
from optparse import OptionParser      
from functools import partial

from zipfile import ZipFile, ZIP_STORED, ZIP_DEFLATED
from time import time

from exceptions import KeyError

from xml.dom.minidom import parse, parseString, getDOMImplementation, Element
        
def main(argv,usage=None):

    if not usage:
    # read in args, anything starting with -- will be treated as --<varible>=<value>
        usage = "usage: python %prog"
    optparser = OptionParser(usage+''' [options] <input epub> [<input epub>...]

Given list of epubs will be merged together into one new epub.
''')
    
    optparser.add_option("-o", "--output", dest="outputopt", default="merge.epub",
                      help="Set OUTPUT file, Default: merge.epub", metavar="OUTPUT")
    optparser.add_option("-t", "--title", dest="titleopt", default=None,
                      help="Use TITLE as the metadata title.  Default: '<first epub title> Anthology'", metavar="TITLE")
    optparser.add_option("-d", "--description", dest="descopt", default=None,
                      help="Use DESC as the metadata description.  Default: '<epub title> by <author>' for each epub.", metavar="DESC")
    optparser.add_option("-a", "--author",
                      action="append", dest="authoropts", default=[],
                      help="Use AUTHOR as a metadata author, multiple authors may be given, Default: <All authors from epubs>", metavar="AUTHOR")
    optparser.add_option("-g", "--tag",
                      action="append", dest="tagopts", default=[],
                      help="Include TAG as dc:subject tag, multiple tags may be given, Default: None", metavar="TAG")
    optparser.add_option("-l", "--language",
                      action="append", dest="languageopts", default=[],
                      help="Include LANG as dc:language tag, multiple languages may be given, Default: en", metavar="LANG")
    optparser.add_option("-n", "--no-titles-in-toc",
                      action="store_false", dest="titlenavpoints", default=True,
                      help="Default is to put an entry in the TOC for each epub, nesting each epub's chapters under it.",)
    optparser.add_option("-f", "--flatten-toc",
                      action="store_true", dest="flattentoc",
                      help="Flatten TOC down to one level only.",)
    optparser.add_option("-c", "--cover", dest="coveropt", default=None,
                      help="Path to a jpg to use as cover image.", metavar="COVER")
    optparser.add_option("-k", "--keep-meta",
                      action="store_true", dest="keepmeta",
                      help="Keep original metadata files in merged epub.  Use for UnMerging.",)
    optparser.add_option("-s", "--source", dest="sourceopt", default=None,
                      help="Include URL as dc:source and dc:identifier(opf:scheme=URL).", metavar="URL")
    
    optparser.add_option("-u", "--unmerge",
                      action="store_true", dest="unmerge",
                      help="UnMerge an existing epub that was created by merging with --keep-meta.",)
    optparser.add_option("-D", "--outputdir", dest="outputdir", default=".",
                      help="Set output directory for unmerge, Default: (current dir)", metavar="OUTPUTDIR")
    
    (options, args) = optparser.parse_args(argv)

    ## Add .epub if not already there.
    if not options.outputopt.lower().endswith(".epub"):
        options.outputopt=options.outputopt+".epub"

    print "output file: "+options.outputopt

    if not args:
        optparser.print_help()
        return

    if options.unmerge:
        doUnMerge(args[0],options.outputdir)
    else:
        doMerge(options.outputopt,
                args,
                options.authoropts,
                options.titleopt,
                options.descopt,
                options.tagopts,
                options.languageopts,
                options.titlenavpoints,
                options.flattentoc,
                coverjpgpath=options.coveropt,
                keepmetadatafiles=options.keepmeta,
                source=options.sourceopt
                )

def cond_print(flag,arg):
    if flag:
        print(arg)
    
def doMerge(outputio,
            files,
            authoropts=[],
            titleopt=None,
            descopt=None,
            tags=[],
            languages=['en'],
            titlenavpoints=True,
            flattentoc=False,
            printtimes=False,
            coverjpgpath=None,
            keepmetadatafiles=False,
            source=None):
    '''
    outputio = output file name or StringIO.
    files = list of input file names or StringIOs.
    authoropts = list of authors to use, otherwise add from all input
    titleopt = title, otherwise '<first title> Anthology'
    descopt = description, otherwise '<title> by <author>' list for all input
    tags = dc:subject tags to include, otherwise none.
    languages = dc:language tags to include
    titlenavpoints if true, put in a new TOC entry for each epub, nesting each epub's chapters under it
    flattentoc if true, flatten TOC down to one level only.
    coverjpgpath, Path to a jpg to use as cover image.
    '''

    printt = partial(cond_print,printtimes)
    
    ## Python 2.5 ZipFile is rather more primative than later
    ## versions.  It can operate on a file, or on a StringIO, but
    ## not on an open stream.  OTOH, I suspect we would have had
    ## problems with closing and opening again to change the
    ## compression type anyway.

    filecount=0
    t = time()
    
    ## Write mimetype file, must be first and uncompressed.
    ## Older versions of python(2.4/5) don't allow you to specify
    ## compression by individual file.
    ## Overwrite if existing output file.
    outputepub = ZipFile(outputio, "w", compression=ZIP_STORED)
    outputepub.debug = 3
    outputepub.writestr("mimetype", "application/epub+zip")
    outputepub.close()

    ## Re-open file for content.
    outputepub = ZipFile(outputio, "a", compression=ZIP_DEFLATED)
    outputepub.debug = 3

    ## Create META-INF/container.xml file.  The only thing it does is
    ## point to content.opf
    containerdom = getDOMImplementation().createDocument(None, "container", None)
    containertop = containerdom.documentElement
    containertop.setAttribute("version","1.0")
    containertop.setAttribute("xmlns","urn:oasis:names:tc:opendocument:xmlns:container")
    rootfiles = containerdom.createElement("rootfiles")
    containertop.appendChild(rootfiles)
    rootfiles.appendChild(newTag(containerdom,"rootfile",{"full-path":"content.opf",
                                                          "media-type":"application/oebps-package+xml"}))
    outputepub.writestr("META-INF/container.xml",containerdom.toprettyxml(indent='   ',encoding='utf-8'))    

    ## Process input epubs.
    
    items = [] # list of (id, href, type) tuples(all strings) -- From .opfs' manifests
    items.append(("ncx","toc.ncx","application/x-dtbncx+xml")) ## we'll generate the toc.ncx file,
                                                               ## but it needs to be in the items manifest.
    itemrefs = [] # list of strings -- idrefs from .opfs' spines
    navmaps = [] # list of navMap DOM elements -- TOC data for each from toc.ncx files
    is_ffdl_epub = [] # list of t/f

    itemhrefs = {} # hash of item[id]s to itemref[href]s -- to find true start of book(s).
    firstitemhrefs = []

    booktitles = [] # list of strings -- Each book's title
    allauthors = [] # list of lists of strings -- Each book's list of authors.

    filelist = []
    
    printt("prep output:%s"%(time()-t))
    t = time()
    
    booknum=1
    firstmetadom = None
    for file in files:
        if file == None : continue
        
        book = "%d" % booknum
        bookdir = "%d/" % booknum
        bookid = "a%d" % booknum
        #print "book %d" % booknum
        
        epub = ZipFile(file, 'r')

        ## Find the .opf file.
        container = epub.read("META-INF/container.xml")
        containerdom = parseString(container)
        rootfilenodelist = containerdom.getElementsByTagNameNS("*","rootfile")
        rootfilename = rootfilenodelist[0].getAttribute("full-path")

        ## Save the path to the .opf file--hrefs inside it are relative to it.
        relpath = get_path_part(rootfilename)
            
        metadom = parseString(epub.read(rootfilename))
        #print("metadom:%s"%epub.read(rootfilename))
        if booknum==1 and not source:
            try:
                firstmetadom = metadom.getElementsByTagNameNS("*","metadata")[0]
                source=firstmetadom.getElementsByTagName("dc:source")[0].firstChild.data.encode("utf-8")
            except:
                source=""
            #print "Source:%s"%source

        # if the epub was ever edited with Sigil, it changed the unique-identifier,
        # but dc:contributor was left.
        #is_ffdl_epub.append(metadom.documentElement.getAttribute('unique-identifier') == "fanficdownloader-uid")
        is_ffdl_epub.append(False)

        for c in metadom.getElementsByTagName("dc:contributor"):
            if c.getAttribute("opf:role") == "bkp" and \
                    getText(c.childNodes) == "fanficdownloader [http://fanficdownloader.googlecode.com]":
                is_ffdl_epub[-1] = True # set last.
                break;

        ## Save indiv book title
        try:
            booktitles.append(metadom.getElementsByTagName("dc:title")[0].firstChild.data)
        except:
            booktitles.append("(Title Missing)")

        ## Save authors.
        authors=[]
        for creator in metadom.getElementsByTagName("dc:creator"):
            try:
                if( creator.getAttribute("opf:role") == "aut" or not creator.hasAttribute("opf:role") and creator.firstChild != None):
                    authors.append(creator.firstChild.data)
            except:
                pass
        if len(authors) == 0:
            authors.append("(Author Missing)")
        allauthors.append(authors)

        if keepmetadatafiles:
            itemid=bookid+"rootfile"
            itemhref = rootfilename
            href=bookdir+itemhref
            #print("write rootfile %s to %s"%(itemhref,href))
            outputepub.writestr(href,
                                epub.read(itemhref))
            items.append((itemid,href,"origrootfile/xml"))
            
        # spin through the manifest--only place there are item tags.
        # Correction--only place there *should* be item tags.  But
        # somebody found one that did.
        manifesttag=metadom.getElementsByTagNameNS("*","manifest")[0]
        for item in manifesttag.getElementsByTagNameNS("*","item"):
            itemid=bookid+item.getAttribute("id")
            itemhref = unquote(item.getAttribute("href")) # remove %20, etc.
            href=bookdir+relpath+itemhref
            if( item.getAttribute("media-type") == "application/x-dtbncx+xml" ):
                # TOC file is only one with this type--as far as I know.
                # grab the whole navmap, deal with it later.
                tocdom = parseString(epub.read(relpath+item.getAttribute("href")))

                # update all navpoint ids with bookid for uniqueness.
                for navpoint in tocdom.getElementsByTagNameNS("*","navPoint"):
                    navpoint.setAttribute("id",bookid+navpoint.getAttribute("id"))

                # update all content paths with bookdir for uniqueness.
                for content in tocdom.getElementsByTagNameNS("*","content"):
                    content.setAttribute("src",bookdir+relpath+content.getAttribute("src"))

                navmaps.append(tocdom.getElementsByTagNameNS("*","navMap")[0])

                if keepmetadatafiles:
                    #print("write toc.ncx %s to %s"%(relpath+itemhref,href))
                    outputepub.writestr(href,
                                        epub.read(relpath+itemhref))
                    items.append((itemid,href,"origtocncx/xml"))
            else:
                href=href.encode('utf8')
                #print("item id: %s -> %s:"%(itemid,href))
                itemhrefs[itemid] = href
                if href not in filelist:
                    try:
                        outputepub.writestr(href,
                                            epub.read(relpath+itemhref))
                        if re.match(r'.*/(file|chapter)\d+\.x?html',href):
                            filecount+=1
                        items.append((itemid,href,item.getAttribute("media-type")))
                        filelist.append(href)
                    except KeyError, ke:
                        pass # Skip missing files.

        itemreflist = metadom.getElementsByTagNameNS("*","itemref")
        # print("itemreflist:%s"%itemreflist)
        # print("itemhrefs:%s"%itemhrefs)
        # print("bookid:%s"%bookid)
        # print("itemreflist[0].getAttribute(idref):%s"%itemreflist[0].getAttribute("idref"))
        firstitemhrefs.append(itemhrefs[bookid+itemreflist[0].getAttribute("idref")])
        for itemref in itemreflist:
            itemrefs.append(bookid+itemref.getAttribute("idref"))

        booknum=booknum+1;
        
    printt("after file loop:%s"%(time()-t))
    t = time()
    
    ## create content.opf file. 
    uniqueid="epubmerge-uid-%d" % time() # real sophisticated uid scheme.
    contentdom = getDOMImplementation().createDocument(None, "package", None)
    package = contentdom.documentElement

    package.setAttribute("version","2.0")
    package.setAttribute("xmlns","http://www.idpf.org/2007/opf")
    package.setAttribute("unique-identifier","epubmerge-id")
    metadata=newTag(contentdom,"metadata",
                    attrs={"xmlns:dc":"http://purl.org/dc/elements/1.1/",
                           "xmlns:opf":"http://www.idpf.org/2007/opf"})
    metadata.appendChild(newTag(contentdom,"dc:identifier",text=uniqueid,attrs={"id":"epubmerge-id"}))
    if( titleopt is None ):
        titleopt = booktitles[0]+" Anthology"
    metadata.appendChild(newTag(contentdom,"dc:title",text=titleopt))
    
    # If cmdline authors, use those instead of those collected from the epubs
    # (allauthors kept for TOC & description gen below.
    if( len(authoropts) > 1  ):
        useauthors=[authoropts]
    else:
        useauthors=allauthors
        
    usedauthors=dict()
    for authorlist in useauthors:
        for author in authorlist:
            if( not usedauthors.has_key(author) ):
                usedauthors[author]=author
                metadata.appendChild(newTag(contentdom,"dc:creator",
                                            attrs={"opf:role":"aut"},
                                            text=author))
    
    metadata.appendChild(newTag(contentdom,"dc:contributor",text="epubmerge",attrs={"opf:role":"bkp"}))
    metadata.appendChild(newTag(contentdom,"dc:rights",text="Copyrights as per source stories"))
    
    for l in languages:
        metadata.appendChild(newTag(contentdom,"dc:language",text=l))
    
    if not descopt:
        # created now, but not filled in until TOC generation to save loops.
        description = newTag(contentdom,"dc:description",text="Anthology containing:\n")
    else:
        description = newTag(contentdom,"dc:description",text=descopt)
    metadata.appendChild(description)
    
    if source:
        metadata.appendChild(newTag(contentdom,"dc:identifier",
                                    attrs={"opf:scheme":"URL"},
                                    text=source))
        metadata.appendChild(newTag(contentdom,"dc:source",
                                    text=source))
        
    for tag in tags:
        metadata.appendChild(newTag(contentdom,"dc:subject",text=tag))
    
    package.appendChild(metadata)
    
    manifest = contentdom.createElement("manifest")
    package.appendChild(manifest)

    spine = newTag(contentdom,"spine",attrs={"toc":"ncx"})
    package.appendChild(spine)
    
    if coverjpgpath:
        # <meta name="cover" content="cover.jpg"/>
        metadata.appendChild(newTag(contentdom,"meta",{"name":"cover",
                                                       "content":"coverimageid"}))
        guide = newTag(contentdom,"guide")
        guide.appendChild(newTag(contentdom,"reference",attrs={"type":"cover",
                                                   "title":"Cover",
                                                   "href":"cover.xhtml"}))
        package.appendChild(guide)

        manifest.appendChild(newTag(contentdom,"item",
                                    attrs={'id':"coverimageid",
                                           'href':"cover.jpg",
                                           'media-type':"image/jpeg"}))            
        
        # Note that the id of the cover xhmtl *must* be 'cover'
        # for it to work on Nook.
        manifest.appendChild(newTag(contentdom,"item",
                                    attrs={'id':"cover",
                                           'href':"cover.xhtml",
                                           'media-type':"application/xhtml+xml"}))
        
        spine.appendChild(newTag(contentdom,"itemref",
                                 attrs={"idref":"cover",
                                        "linear":"yes"}))    
            
    for item in items:
        (id,href,type)=item
        manifest.appendChild(newTag(contentdom,"item",
                                       attrs={'id':id,
                                              'href':href,
                                              'media-type':type}))
        
    for itemref in itemrefs:
        spine.appendChild(newTag(contentdom,"itemref",
                                    attrs={"idref":itemref,
                                           "linear":"yes"}))

    ## create toc.ncx file
    tocncxdom = getDOMImplementation().createDocument(None, "ncx", None)
    ncx = tocncxdom.documentElement
    ncx.setAttribute("version","2005-1")
    ncx.setAttribute("xmlns","http://www.daisy.org/z3986/2005/ncx/")
    head = tocncxdom.createElement("head")
    ncx.appendChild(head)
    head.appendChild(newTag(tocncxdom,"meta",
                            attrs={"name":"dtb:uid", "content":uniqueid}))
    depthnode = newTag(tocncxdom,"meta",
                            attrs={"name":"dtb:depth", "content":"4"})
    head.appendChild(depthnode)
    head.appendChild(newTag(tocncxdom,"meta",
                            attrs={"name":"dtb:totalPageCount", "content":"0"}))
    head.appendChild(newTag(tocncxdom,"meta",
                            attrs={"name":"dtb:maxPageNumber", "content":"0"}))
    
    docTitle = tocncxdom.createElement("docTitle")
    docTitle.appendChild(newTag(tocncxdom,"text",text=titleopt))
    ncx.appendChild(docTitle)
    
    tocnavMap = tocncxdom.createElement("navMap")
    ncx.appendChild(tocnavMap)

    booknum=0

    printt("wrote initial metadata:%s"%(time()-t))
    t = time()
    
    for navmap in navmaps:
        navpoints = filter( lambda x : isinstance(x,Element) and x.tagName=="navPoint",
                            navmap.childNodes) #getElementsByTagNameNS("*","navPoint")
        newnav = None
        if titlenavpoints:
            newnav = newTag(tocncxdom,"navPoint",{"id":"book%03d"%booknum})
            navlabel = newTag(tocncxdom,"navLabel")
            newnav.appendChild(navlabel)
            # For purposes of TOC titling & desc, use first book author.  Skip adding author if only one.
            if len(usedauthors) > 1:
                title = booktitles[booknum]+" by "+allauthors[booknum][0]
            else:
                title = booktitles[booknum]
                
            navlabel.appendChild(newTag(tocncxdom,"text",text=title))
            # Find the first 'spine' item's content for the title navpoint.
            # Many epubs have the first chapter as first navpoint, so we can't just
            # copy that anymore.
            newnav.appendChild(newTag(tocncxdom,"content",
                                      {"src":firstitemhrefs[booknum]}))

            #print("newnav:%s"%newnav.toprettyxml())
            tocnavMap.appendChild(newnav)
        else:
            newnav = tocnavMap
        
        if not descopt and len(allauthors[booknum]) > 0:
            description.appendChild(contentdom.createTextNode(booktitles[booknum]+" by "+allauthors[booknum][0]+"\n"))
            
        if len(navpoints) > 1 :
            for navpoint in navpoints:
                newnav.appendChild(navpoint)
                navpoint.is_ffdl_epub = is_ffdl_epub[booknum]
        
        booknum=booknum+1;
        # end of navmaps loop.


    maxdepth = 0
    contentsrcs = {}
    removednodes = []
    ## Force strict ordering of playOrder, stripping out some.
    playorder=0
    for navpoint in tocncxdom.getElementsByTagNameNS("*","navPoint"):
        if navpoint in removednodes:
            continue
        # need content[src] to compare for dups.  epub wants dup srcs to have same playOrder.
        contentsrc = None
        for n in navpoint.childNodes:
            if isinstance(n,Element) and n.tagName == "content":
                contentsrc = n.getAttribute("src")
                # print("contentsrc: %s"%contentsrc)
                break
            
        if( contentsrc not in contentsrcs ):
            
            parent = navpoint.parentNode
            try:
                # if the epub was ever edited with Sigil, it changed
                # the id, but the file name is the same.
                if navpoint.is_ffdl_epub and \
                        ( navpoint.getAttribute("id").endswith('log_page') \
                              or contentsrc.endswith("log_page.xhtml") ):
                    sibs = filter( lambda x : isinstance(x,Element) and x.tagName=="navPoint",
                                   parent.childNodes )
                    # if only logpage and one chapter, remove them from TOC and just show story.
                    if len(sibs) == 2:
                        parent.removeChild(navpoint)
                        # print("Removing %s:"% sibs[0].getAttribute("playOrder"))
                        parent.removeChild(sibs[1])
                        removednodes.append(sibs[1])
            except:
                pass                
            
            # New src, new number.
            contentsrcs[contentsrc] = navpoint.getAttribute("id")
            playorder += 1
            navpoint.setAttribute("playOrder","%d" % playorder)
            # print("playorder:%d:"%playorder)
            
            # need to know depth of deepest navpoint for <meta name="dtb:depth" content="2"/>
            npdepth = 1
            dp = navpoint.parentNode
            while dp and dp.tagName != "navMap":
                npdepth += 1
                dp = dp.parentNode
            
            if npdepth > maxdepth:
                maxdepth = npdepth
        else:
            # same content, look for ffdl and title_page and/or single chapter.
            
            # easier to just set it now, even if the node gets removed later.
            navpoint.setAttribute("playOrder","%d" % playorder)
            # print("playorder:%d:"%playorder)
            
            parent = navpoint.parentNode
            try:
                # if the epub was ever edited with Sigil, it changed
                # the id, but the file name is the same.
                if navpoint.is_ffdl_epub and \
                        ( navpoint.getAttribute("id").endswith('title_page') \
                              or contentsrc.endswith("title_page.xhtml") ):
                    parent.removeChild(navpoint)
                    sibs = filter( lambda x : isinstance(x,Element) and x.tagName=="navPoint",
                                   parent.childNodes )
                    # if only one chapter after removing title_page, remove it too.
                    if len(sibs) == 1:
                        # print("Removing %s:"% sibs[0].getAttribute("playOrder"))
                        parent.removeChild(sibs[0])
                        removednodes.append(sibs[0])
            except:
                pass


    if flattentoc:
        maxdepth = 1
        # already have play order and pesky dup/single chapters
        # removed, just need to flatten.
        flattocnavMap = tocncxdom.createElement("navMap")
        for n in tocnavMap.getElementsByTagNameNS("*","navPoint"):
            flattocnavMap.appendChild(n)
            
        ncx.replaceChild(flattocnavMap,tocnavMap)
        
    printt("navmap/toc maddess:%s"%(time()-t))
    t = time()
    
    depthnode.setAttribute("content","%d"%maxdepth)

    ## content.opf written now due to description being filled in
    ## during TOC generation to save loops.
    contentxml = contentdom.toxml('utf-8')        
    # tweak for brain damaged Nook STR.  Nook insists on name before content.
    contentxml = contentxml.replace('<meta content="coverimageid" name="cover"/>',
                                    '<meta name="cover" content="coverimageid"/>')
    outputepub.writestr("content.opf",contentxml)
    outputepub.writestr("toc.ncx",tocncxdom.toxml('utf-8'))

    printt("wrote opf/ncx files:%s"%(time()-t))
    t = time()
    
    if coverjpgpath:
        # write, not write string.  Pulling from file.
        outputepub.write(coverjpgpath,"cover.jpg")
        
        outputepub.writestr("cover.xhtml",'''
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en"><head><title>Cover</title><style type="text/css" title="override_css">
@page {padding: 0pt; margin:0pt}
body { text-align: center; padding:0pt; margin: 0pt; }
div { margin: 0pt; padding: 0pt; }
</style></head><body><div>
<img src="cover.jpg" alt="cover"/>
</div></body></html>
''')
        
    # declares all the files created by Windows.  otherwise, when
    # it runs in appengine, windows unzips the files as 000 perms.
    for zf in outputepub.filelist:
        zf.create_system = 0
    outputepub.close()
    
    printt("closed outputepub:%s"%(time()-t))
    t = time()

    return (source,filecount)

def doUnMerge(inputio,outdir=None):
    epub = ZipFile(inputio, 'r') # works equally well with inputio as a path or a blob
    outputios = []

    ## Find the .opf file.
    container = epub.read("META-INF/container.xml")
    containerdom = parseString(container)
    rootfilenodelist = containerdom.getElementsByTagName("rootfile")
    rootfilename = rootfilenodelist[0].getAttribute("full-path")

    contentdom = parseString(epub.read(rootfilename))

    ## Save the path to the .opf file--hrefs inside it are relative to it.
    relpath = get_path_part(rootfilename)
    #print("relpath:%s"%relpath)
            
    # spin through the manifest--only place there are item tags.
    # Correction--only place there *should* be item tags.  But
    # somebody found one that did.
    manifesttag=contentdom.getElementsByTagNameNS("*","manifest")[0]
    for item in manifesttag.getElementsByTagNameNS("*","item"):
        # look for our fake media-type for original rootfiles.
        if( item.getAttribute("media-type") == "origrootfile/xml" ):
            # found one, assume the dir containing it is a complete
            # original epub, do initial setup of epub.
            itemhref = relpath+unquote(item.getAttribute("href"))
            #print("Found origrootfile:%s"%itemhref)
            curepubpath = re.sub(r'([^\d/]+/)+$','',get_path_part(itemhref))
            savehref = itemhref[len(curepubpath):]
            #print("curepubpath:%s"%curepubpath)
            
            outputio = StringIO()
            outputepub = ZipFile(outputio, "w", compression=ZIP_STORED)
            outputepub.debug = 3
            outputepub.writestr("mimetype", "application/epub+zip")
            outputepub.close()
        
            ## Re-open file for content.
            outputepub = ZipFile(outputio, "a", compression=ZIP_DEFLATED)
            outputepub.debug = 3
            ## Create META-INF/container.xml file.  The only thing it does is
            ## point to content.opf
            containerdom = getDOMImplementation().createDocument(None, "container", None)
            containertop = containerdom.documentElement
            containertop.setAttribute("version","1.0")
            containertop.setAttribute("xmlns","urn:oasis:names:tc:opendocument:xmlns:container")
            rootfiles = containerdom.createElement("rootfiles")
            containertop.appendChild(rootfiles)
            rootfiles.appendChild(newTag(containerdom,"rootfile",{"full-path":savehref,
                                                                  "media-type":"application/oebps-package+xml"}))
            outputepub.writestr("META-INF/container.xml",containerdom.toprettyxml(indent='   ',encoding='utf-8'))

            outputepub.writestr(savehref,epub.read(itemhref))
            
            for item2 in contentdom.getElementsByTagName("item"):
                item2href = relpath+unquote(item2.getAttribute("href"))
                if item2href.startswith(curepubpath) and item2href != itemhref:
                    save2href = item2href[len(curepubpath):]
                    #print("Found %s -> %s"%(item2href,save2href))
                    outputepub.writestr(save2href,epub.read(item2href))

            # declares all the files created by Windows.  otherwise, when
            # it runs in appengine, windows unzips the files as 000 perms.
            for zf in outputepub.filelist:
                zf.create_system = 0
            outputepub.close()
            
            outputios.append(outputio)

    if outdir:
        outfilenames=[]
        for count,epubIO in enumerate(outputios):
            filename="%s/%d.epub"%(outdir,count)
            print("write %s"%filename)
            outstream = open(filename,"wb")
            outstream.write(epubIO.getvalue())
            outstream.close()
            outfilenames.append(filename)
        return outfilenames
    else:
        return outputios

def get_path_part(n):
    relpath = os.path.dirname(n)
    if( len(relpath) > 0 ):
        relpath=relpath+"/"
    return relpath


## Utility method for creating new tags.
def newTag(dom,name,attrs=None,text=None):
    tag = dom.createElement(name)
    if( attrs is not None ):
        for attr in attrs.keys():
            tag.setAttribute(attr,attrs[attr])
    if( text is not None ):
        tag.appendChild(dom.createTextNode(text))
    return tag
    
def getText(nodelist):
    rc = []
    for node in nodelist:
        if node.nodeType == node.TEXT_NODE:
            rc.append(node.data)
    return ''.join(rc)

if __name__ == "__main__":
    main(sys.argv[1:])
    #doUnMerge(sys.argv[1],sys.argv[2])
