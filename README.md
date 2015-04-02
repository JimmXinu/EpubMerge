# EpubMerge

This is a repository for the EpubMerge Calibre Plugin.

Most discussion of this plugin takes place in the [EpubMerge Calibre Plugin forum].

Merging together multiple eBooks together into one eBook seems to be a common request, but there haven't been many tools to do so.

This plugin provides the ability to create new EPUBs by combining the contents of existing (non-DRM) EPUB format eBooks.

The source may be seen, and a Command Line version obtained, from the project home page.

Main Features of EpubMerge Plugin:

* Select a list of stories in calibre,
* Order them,
* Edit the metadata for the new combined eBook, and then,
* Merge the contents of the EPUBs together into the new eBook, now including cover from metadata if set.
* UnMerge previously merged epubs if metadata was saved during merge.
* Configurably able to save the metadata for each merged book for UnMerging later if desired. (Defaults to On.)
* Configurably able to populate custom columns from source books.
* Options now stored inside the Library rather than an external JSON file.
* CLI via calibre-debug --run-plugin

There are a few configurable options: whether or not to insert a Table of Contents entry for each merged book (with it's original TOC nested underneath it), an option to flatten the TOC down to one level only, and including the merged books comments. These options are stored by Library.

[EpubMerge Calibre Plugin forum]: http://www.mobileread.com/forums/showthread.php?t=169744

