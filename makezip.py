#!/usr/bin/python
# -*- coding: utf-8 -*-

__license__   = 'GPL v3'
__copyright__ = '2019, Jim Miller'
__docformat__ = 'restructuredtext en'

import os, zipfile, sys
from glob import glob
from six import text_type as unicode

def addFolderToZip(myZipFile,folder,exclude=[]):
    folder = unicode(folder) #convert path to ascii for ZipFile Method
    excludelist=[]
    for ex in exclude:
        excludelist.extend(glob(folder+"/"+ex))
    for file in glob(folder+"/*"):
        if file in excludelist:
            continue
        if os.path.isfile(file):
            #print file
            myZipFile.write(file, file)
        elif os.path.isdir(file):
            addFolderToZip(myZipFile,file,exclude=exclude)

def createZipFile(filename,mode,files,exclude=[]):
    myZipFile = zipfile.ZipFile( filename, mode, zipfile.ZIP_STORED ) # Open the zip file for writing
    excludelist=[]
    for ex in exclude:
        excludelist.extend(glob(ex))
    for file in files:
        if file in excludelist:
            continue
        file = unicode(file) #convert path to ascii for ZipFile Method
        if os.path.isfile(file):
            (filepath, filename) = os.path.split(file)
            #print file
            myZipFile.write( file, filename )
        if os.path.isdir(file):
            addFolderToZip(myZipFile,file,exclude=exclude)
    myZipFile.close()
    return (1,filename)

