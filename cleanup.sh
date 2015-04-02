
/bin/find -name '*.epub'  -print0 |xargs -0 rm
/bin/find -name '*.back'  -print0 |xargs -0 rm
/bin/find -name '*.bak'  -print0 |xargs -0 rm
/bin/find -name '*.pyc'  -print0 |xargs -0 rm
/bin/find -name '*~' -print0 | xargs -0 rm
