find -name '__pycache__'  -print0 |xargs -0 rm -r
find -name '*.epub'  -print0 |xargs -0 rm
find -name '*.back'  -print0 |xargs -0 rm
find -name '*.bak'  -print0 |xargs -0 rm
find -name '*.pyc'  -print0 |xargs -0 rm
find -name '*~' -print0 | xargs -0 rm
