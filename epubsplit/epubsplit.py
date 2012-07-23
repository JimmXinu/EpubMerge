#!/usr/bin/env python
# -*- coding: utf-8 -*-

__license__   = 'GPL v3'
__copyright__ = '2012, Jim Miller'
__docformat__ = 'restructuredtext en'

import sys, re, os, traceback, copy
from urllib import unquote
from posixpath import normpath

from zipfile import ZipFile, ZIP_STORED, ZIP_DEFLATED
    
from xml.dom.minidom import parse, parseString, getDOMImplementation, Element
from time import time

import BeautifulSoup as bs
#import html5lib

class SplitEpub:

    def __init__(self, inputio):
        self.epub = ZipFile(inputio, 'r')
        self.content_dom = None
        self.content_relpath = None
        self.manifest_items = None
        self.guide_items = None
        self.toc_dom = None
        self.toc_map = None
        self.split_lines = None

    def get_file(self,href):
        return self.epub.read(href)

    def get_content_dom(self):
        if not self.content_dom:
            ## Find the .opf file.
            container = self.epub.read("META-INF/container.xml")
            containerdom = parseString(container)
            rootfilenodelist = containerdom.getElementsByTagName("rootfile")
            rootfilename = rootfilenodelist[0].getAttribute("full-path")

            self.content_dom = parseString(self.epub.read(rootfilename))
            self.content_relpath = get_path_part(rootfilename)
        return self.content_dom

    def get_content_relpath(self):
        ## Save the path to the .opf file--hrefs inside it are relative to it.
        if not self.content_relpath:
            self.get_content_dom() # sets self.content_relpath also.
        return self.content_relpath

    def get_manifest_items(self):
        if not self.manifest_items:
            self.manifest_items = {}

            for item in self.get_content_dom().getElementsByTagName("item"):
                fullhref=unquote(self.get_content_relpath()+item.getAttribute("href"))
                #print("---- item href:%s path part: %s"%(href,get_path_part(href)))
                self.manifest_items[fullhref]=(item.getAttribute("id"),item.getAttribute("media-type"))
                self.manifest_items[item.getAttribute("id")]=(fullhref,item.getAttribute("media-type"))
                    
                if( item.getAttribute("media-type") == "application/x-dtbncx+xml" ):
                    # TOC file is only one with this type--as far as I know.
                    self.toc_dom = parseString(self.epub.read(fullhref))
        
        return self.manifest_items

    def get_guide_items(self):
        if not self.guide_items:
            self.guide_items = {}

            for item in self.get_content_dom().getElementsByTagName("reference"):
                fullhref=unquote(self.get_content_relpath()+item.getAttribute("href"))
                self.guide_items[fullhref]=(item.getAttribute("type"),item.getAttribute("title"))
                #print("---- reference href:%s value:%s"%(fullhref,self.guide_items[fullhref],))
                #self.guide_items[item.getAttribute("type")]=(fullhref,item.getAttribute("media-type"))
                    
        return self.guide_items

    def get_toc_dom(self):
        if not self.toc_dom:
            self.get_manifest_items() # also sets self.toc_dom
        return self.toc_dom

    # dict() of href->[(text,anchor),...],...
    # eg: "file0001.html"->[("Introduction","anchor01"),("Chapter 1","anchor02")],...
    def get_toc_map(self):
        if not self.toc_map:
            self.toc_map = {}
            # update all navpoint ids with bookid for uniqueness.
            for navpoint in self.get_toc_dom().getElementsByTagName("navPoint"):
                # The first of these in each navPoint should be the appropriate one.
                # (may be others due to nesting.
                text = navpoint.getElementsByTagName("text")[0].firstChild.data.encode("utf-8")
                src = unquote(self.get_content_relpath()+navpoint.getElementsByTagName("content")[0].getAttribute("src"))
                if '#' in src:
                    (href,anchor)=src.split("#")
                else:
                    (href,anchor)=(src,None)
                if href not in self.toc_map:
                    self.toc_map[href] = []
                self.toc_map[href].append((text,anchor))
                        
        return self.toc_map
        
    # list of dicts with href, anchor & toc text.
    # 'split lines' are all the points that the epub can be split on.
    # Offer a split at each spine file and each ToC point.
    def get_split_lines(self):
        self.split_lines = [] # list of dicts with href, anchor and toc
        # spin on spine files.
        count=0
        for itemref in self. get_content_dom().getElementsByTagName("itemref"):
            idref = itemref.getAttribute("idref")
            (href,type) = self.get_manifest_items()[idref]
            current = {}
            self.split_lines.append(current)
            current['href']=href
            current['anchor']=None
            current['toc'] = []
            if href in self.get_guide_items():
                current['guide'] = self.get_guide_items()[href]
            current['id'] = idref
            current['type'] = type
            current['num'] = count
            count += 1
            #print("spine:%s->%s"%(idref,href))
            
            # if href is in the toc.
            if href in self.get_toc_map():
                # For each toc entry, check to see if there's an anchor, if so,
                # make a new split line.
                for tocitem in self.get_toc_map()[href]:
                    (text,anchor) = tocitem
                    # XXX for outputing to screen in CLI--hopefully won't need in plugin?
                    try:
                        text = "%s"%text
                    except:
                        text = "(error text)"
                        
                    if anchor:
                        #print("breakpoint: %d"%count)
                        current = {}
                        self.split_lines.append(current)
                        current['href']=href
                        current['anchor']=anchor
                        current['toc']=[]
                        current['id'] = idref
                        current['type'] = type
                        current['num'] = count
                        count += 1
                    # There can be more than one toc to the same split line.
                    # This won't find multiple toc to the same anchor yet.
                    current['toc'].append(text)
                    #print("\ttoc:'%s' %s#%s"%(text,href,anchor))
        return self.split_lines

    # pass in list of line numbers(?)
    def get_split_files(self,linenums):

        self.filecache = FileCache(self.get_manifest_items())
        
        # grab a copy--going to be modifying it.  Doesn't do deep copy.
        lines = self.get_split_lines()
        for j in linenums:
            lines[int(j)]['include']=True

        # loop through finding 'chunks' -- contiguous pieces in the
        # same file.  Each included file is at least one chunk, but if
        # parts are left out, one original file can end up being more
        # than one chunk.
        outchunks = [] # list of tuples=(filename,start,end) 'end' is not inclusive.
        inchunk = False
        currentfile = None
        start = None
        for line in lines:
            if 'include' in line:
                if not inchunk: # start new chunk
                    inchunk = True
                    currentfile = line['href']
                    start = line
                else: # inchunk
                    # different file, new chunk.
                    if currentfile != line['href']:
                        outchunks.append((currentfile,start,line))
                        inchunk=True
                        currentfile=line['href']
                        start=line
            else: # not include
                if inchunk: # save previous chunk.
                    outchunks.append((currentfile,start,line))
                    inchunk=False
                
        # final chunk for when last in list is include.
        if inchunk:
            outchunks.append((currentfile,start,None))
    
        outfiles=[]  # tuples, (filename,type,data) -- filename changed to unique
        for (href,start,end) in outchunks:
            filedata = self.epub.read(href).decode('utf-8')
            
            # discard before start if anchor.
            if start['anchor'] != None:
                filedata = splitHtml(filedata,start['anchor'],before=False)
    
            # discard from end anchor on(inclusive), but only if same file.  If
            # different file, keep rest of file.  If no 'end', then it was the
            # last chunk and went to the end of the last file.
            if end != None and end['anchor'] != None and end['href']==href:
                filedata = splitHtml(filedata,end['anchor'],before=True)

            filename = self.filecache.add_content_file(href,filedata)
            outfiles.append([filename,start['id'],start['type'],filedata])

        # print("self.oldnew:%s"%self.filecache.oldnew)
        # print("self.newold:%s"%self.filecache.newold)
        print("\nanchors:%s\n"%self.filecache.anchors)
        print("\nlinkedfiles:%s\n"%self.filecache.linkedfiles)
        #print("relpath:%s"%get_path_part())
        # Spin through to replace internal URLs
        for fl in outfiles:
            print("file:%s"%fl[0])
            soup = bs.BeautifulSoup(fl[3])
            changed = False
            for a in soup.findAll('a'):
                if a.has_key('href'):
                    path = normpath(unquote("%s%s"%(get_path_part(fl[0]),a['href'])))
                    print("full a['href']:%s"%path)
                    if path in self.filecache.anchors and self.filecache.anchors[path] != path:
                        a['href'] = self.filecache.anchors[path][len(get_path_part(fl[0])):]
                        print("replacement path:%s"%a['href'])
                        changed = True
            if changed:
                fl[3] = soup.__str__('utf-8').decode('utf-8')

        return outfiles

    def write_split_epub(self,
                         outputio,
                         linenums,
                         changedtocs={},
                         authoropts=[],
                         titleopt=None,
                         descopt=None,
                         tags=[],
                         languages=['en'],
                         coverjpgpath=None):

        files = self.get_split_files(linenums)

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


####    ## create content.opf file. 
        uniqueid="epubsplit-uid-%d" % time() # real sophisticated uid scheme.
        contentdom = getDOMImplementation().createDocument(None, "package", None)
        package = contentdom.documentElement
    
        package.setAttribute("version","2.0")
        package.setAttribute("xmlns","http://www.idpf.org/2007/opf")
        package.setAttribute("unique-identifier","epubsplit-id")
        metadata=newTag(contentdom,"metadata",
                        attrs={"xmlns:dc":"http://purl.org/dc/elements/1.1/",
                               "xmlns:opf":"http://www.idpf.org/2007/opf"})
        metadata.appendChild(newTag(contentdom,"dc:identifier",text=uniqueid,attrs={"id":"epubsplit-id"}))
        if( titleopt is None ):
            titleopt = "Testing title"
        metadata.appendChild(newTag(contentdom,"dc:title",text=titleopt))
        
        # If cmdline authors, use those instead of those collected from the epubs
        # (allauthors kept for TOC & description gen below.
        if( len(authoropts) > 0  ):
            useauthors=[authoropts]
        else:
            useauthors=[['testing author']]

        usedauthors=dict()
        for authorlist in useauthors:
            for author in authorlist:
                if( not usedauthors.has_key(author) ):
                    usedauthors[author]=author
                    metadata.appendChild(newTag(contentdom,"dc:creator",
                                                attrs={"opf:role":"aut"},
                                                text=author))
        
        metadata.appendChild(newTag(contentdom,"dc:contributor",text="epubsplit",attrs={"opf:role":"bkp"}))
        metadata.appendChild(newTag(contentdom,"dc:rights",text="Copyrights as per source stories"))
        
        for l in languages:
            metadata.appendChild(newTag(contentdom,"dc:language",text=l))
        
        if not descopt:
            # created now, but not filled in until TOC generation to save loops.
            description = newTag(contentdom,"dc:description",text="Anthology containing:\n")
        else:
            description = newTag(contentdom,"dc:description",text=descopt)
        metadata.appendChild(description)
        
        for tag in tags:
            metadata.appendChild(newTag(contentdom,"dc:subject",text=tag))
        
        package.appendChild(metadata)
        
        manifest = contentdom.createElement("manifest")
        package.appendChild(manifest)
        spine = newTag(contentdom,"spine",attrs={"toc":"ncx"})
        package.appendChild(spine)

        manifest.appendChild(newTag(contentdom,"item",
                                    attrs={'id':'ncx',
                                           'href':'toc.ncx',
                                           'media-type':'application/x-dtbncx+xml'}))

        if coverjpgpath:
            # <meta name="cover" content="cover.jpg"/>
            metadata.appendChild(newTag(contentdom,"meta",{"name":"cover",
                                                           "content":"coverimageid"}))
            # cover stuff for later:
            # at end of <package>:
            # <guide>
            # <reference type="cover" title="Cover" href="Text/cover.xhtml"/>
            # </guide>
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
        
        contentcount=0
        for (filename,id,type,filedata) in files:
            #filename = self.filecache.addHtml(href,filedata)
            #print("writing :%s"%filename)
            # add to manifest and spine
            
            if coverjpgpath and filename == "cover.xhtml":
                continue # don't dup cover.
                
            outputepub.writestr(filename,filedata.encode('utf-8'))
            id = "a%d"%contentcount
            contentcount += 1
            manifest.appendChild(newTag(contentdom,"item",
                                        attrs={'id':id,
                                               'href':filename,
                                               'media-type':type}))
            spine.appendChild(newTag(contentdom,"itemref",
                                     attrs={"idref":id,
                                            "linear":"yes"}))

        for (linked,type) in self.filecache.linkedfiles:
            # add to manifest 
            if coverjpgpath and linked == "cover.jpg":
                continue # don't dup cover.

            try:
                outputepub.writestr(linked,self.get_file(linked))
            except Exception, e:
                print("Failed to copy linked file (%s)\nException: %s"%(linked,e))
                
            id = "a%d"%contentcount
            contentcount += 1
            manifest.appendChild(newTag(contentdom,"item",
                                        attrs={'id':id,
                                               'href':linked,
                                               'media-type':type}))

        contentxml = contentdom.toxml('utf-8')        
        # tweak for brain damaged Nook STR.  Nook insists on name before content.
        contentxml = contentxml.replace('<meta content="coverimageid" name="cover"/>',
                                        '<meta name="cover" content="coverimageid"/>')
        outputepub.writestr("content.opf",contentxml)

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
                                attrs={"name":"dtb:depth", "content":"1"})
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

        # come back to lines again for TOC because files only has files(gasp-shock!)
        count=1
        for line in self.split_lines:
            if 'include' in line:
                # if changed, use only changed values.
                if line['num'] in changedtocs:
                    line['toc'] = changedtocs[line['num']]
                # can have more than one toc entry.
                for title in line['toc']:
                    newnav = newTag(tocncxdom,"navPoint",
                                    {"id":"a%03d"%count,"playOrder":"%d" % count})
                    count += 1
                    tocnavMap.appendChild(newnav)
                    navlabel = newTag(tocncxdom,"navLabel")
                    newnav.appendChild(navlabel)
                    # For purposes of TOC titling & desc, use first book author
                    navlabel.appendChild(newTag(tocncxdom,"text",text=title))
                    # Find the first 'spine' item's content for the title navpoint.
                    # Many epubs have the first chapter as first navpoint, so we can't just
                    # copy that anymore.
                    if line['anchor'] and line['href']+"#"+line['anchor'] in self.filecache.anchors:
                        src = self.filecache.anchors[line['href']+"#"+line['anchor']]
                        #print("toc from anchors(%s#%s)(%s)"%(line['href'],line['anchor'],src))
                    else:
                        #print("toc from href(%s)"%line['href'])
                        src = line['href']
                    newnav.appendChild(newTag(tocncxdom,"content",
                                              {"src":src}))

        outputepub.writestr("toc.ncx",tocncxdom.toxml('utf-8'))
        
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
    
class FileCache:

    def __init__(self,manifest_items={}):
        self.manifest_items = manifest_items
        self.oldnew = {}
        self.newold = {}
        self.anchors = {}
        self.linkedfiles = set()

    def add_linked_file(self, href):
        href = normpath(unquote(href)) # fix %20 & /../
        if href in self.manifest_items:
            type = self.manifest_items[href][1]
        else:
            type = 'unknown'
        self.linkedfiles.add((href,type))

    def add_content_file(self, href, filedata):

        changedname = False
        if href not in self.oldnew:
            self.oldnew[href]=[]
            newfile = href
        else:
            changedname = True
            newfile = "%s%d-%s"%(get_path_part(href),
                                 len(self.oldnew[href]),
                                 get_file_part(href))
            
        self.oldnew[href].append(newfile)
        self.newold[newfile]=href
        print("newfile:%s"%newfile)

        soup = bs.BeautifulSoup(filedata) #.encode('utf-8')
        #print("soup head:%s"%soup.find('head'))

        # same name?  Don't need to worry about changing links to anchors
        for a in soup.findAll(): # not just 'a', any tag.
            #print("a:%s"%a)
            if a.has_key('id'):
                self.anchors[href+'#'+a['id']]=newfile+'#'+a['id']

        for img in soup.findAll('img'):
            if img.has_key('src'):
                src=img['src']
            if img.has_key('xlink:href'):
                src=img['xlink:href']
            self.add_linked_file(get_path_part(href)+src)

        # from baen epub.
        # <image width="462" height="616" xlink:href="cover.jpeg"/>
        for img in soup.findAll('image'):
            if img.has_key('src'):
                src=img['src']
            if img.has_key('xlink:href'):
                src=img['xlink:href']
            self.add_linked_file(get_path_part(href)+src)

        # link href="0.css" type="text/css"
        for style in soup.findAll('link',{'type':'text/css'}):
            #print("link:%s"%style)
            if style.has_key('href'):
                self.add_linked_file(get_path_part(href)+style['href'])
        
        return newfile

def splitHtml(data,tagid,before=False):
    soup = bs.BeautifulSoup(data)
    #print("splitHtml.soup head:%s"%soup.find('head'))

    splitpoint = soup.find(id=tagid)

    print("splitpoint:%s"%splitpoint)

    if splitpoint == None:
        return data
    
    if before:
        # remove all next siblings.
        for n in splitpoint.findNextSiblings():
            n.extract()

        parent = splitpoint.parent
        while parent and parent.name != 'body':
            for n in parent.findNextSiblings():
                n.extract()
            parent = parent.parent

        splitpoint.extract()
    else:
        # remove all prev siblings.
        for n in splitpoint.findPreviousSiblings():
            n.extract()

        parent = splitpoint.parent
        while parent and parent.name != 'body':
            for n in parent.findPreviousSiblings():
                n.extract()
            parent = parent.parent

    return re.sub(r'( *\r?\n)+','\r\n',soup.__str__('utf-8').decode('utf-8'))

def get_path_part(n):
    relpath = os.path.dirname(n)
    if( len(relpath) > 0 ):
        relpath=relpath+"/"
    return relpath

def get_file_part(n):
    return os.path.basename(n)

## Utility method for creating new tags.
def newTag(dom,name,attrs=None,text=None):
    tag = dom.createElement(name)
    if( attrs is not None ):
        for attr in attrs.keys():
            tag.setAttribute(attr,attrs[attr])
    if( text is not None ):
        tag.appendChild(dom.createTextNode(text))
    return tag
    
