set PYTHONIOENCODING=UTF-8
c:\Python27\tx.exe pull --minimum-perc=80 -f -a

cd translations
for %%f in (*.po) do (
    "C:\Program Files (x86)\Calibre2\calibre-debug.exe" -c "from calibre.translations.msgfmt import main; main()" %%~nf
)

cd ..
