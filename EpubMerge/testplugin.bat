set PYTHONIOENCODING=UTF-8
rem set CALIBRE_DEVELOP_FROM=C:\Users\retief\Desktop\nook\calibre-src\src

c:\Python27\python.exe makeplugin.py

cp EpubMerge.zip "C:\Users\retief\AppData\Roaming\calibre\plugins\EpubMerge.zip"

set CALIBRE_OVERRIDE_LANG=

calibre-debug -g
