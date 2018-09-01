set PYTHONIOENCODING=UTF-8
tx.exe pull --minimum-perc=25 -f -a

cd translations
for %%f in (*.po) do (
    "C:\Program Files\Calibre2\calibre-debug.exe" -c "from calibre.translations.msgfmt import main; main()" %%~nf
)

cd ..
