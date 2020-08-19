set PYTHONIOENCODING=UTF-8

python makeplugin.py

set CALIBRE_DEVELOP_FROM=
set CALIBRE_OVERRIDE_LANG=

calibre-customize -a EpubMerge.zip
rem calibre
calibre-debug -g
