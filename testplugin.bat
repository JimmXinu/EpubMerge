set PYTHONIOENCODING=UTF-8

python makeplugin.py

rem set CALIBRE_DEVELOP_FROM=C:\Users\%USERNAME%\Desktop\nook\calibre\src
set CALIBRE_CONFIG_DIRECTORY=
set CALIBRE_LIBRARY_DIRECTORY=
set CALIBRE_DEVELOP_FROM=
set CALIBRE_OVERRIDE_LANG=
set CALIBRE_USE_DARK_PALETTE=

"c:\Program Files\Calibre2\calibre-customize" -a EpubMerge.zip
"c:\Program Files\Calibre2\calibre-debug" -g
