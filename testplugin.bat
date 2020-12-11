set PYTHONIOENCODING=UTF-8

python makeplugin.py

rem set CALIBRE_DEVELOP_FROM=C:\Users\retief\Desktop\nook\calibre\src
set CALIBRE_DEVELOP_FROM=
set CALIBRE_OVERRIDE_LANG=
set CALIBRE_USE_DARK_PALETTE=

calibre-customize -a EpubMerge.zip
calibre-debug -g
