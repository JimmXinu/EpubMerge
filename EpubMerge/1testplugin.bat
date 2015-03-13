set PYTHONIOENCODING=UTF-8
rem set CALIBRE_DEVELOP_FROM=C:\Users\retief\Desktop\nook\calibre-src\src

c:\Python27\python.exe makeplugin.py

cp EpubMerge.zip "C:\Users\retief\AppData\Roaming\calibre\plugins\EpubMerge.zip"

set CALIBRE_OVERRIDE_LANG=

"C:\Program Files (x86)\Calibre2\calibre-debug.exe" -g
