set PYTHONIOENCODING=UTF-8

python3 makeplugin.py

set CALIBRE_DEVELOP_FROM=
set CALIBRE_OVERRIDE_LANG=

calibre-customize -a EpubMerge.zip
calibre-debug -g
