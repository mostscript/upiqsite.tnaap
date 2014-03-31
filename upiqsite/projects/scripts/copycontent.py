"""
copycontent.py -- command line tool for copying content within a single Plone
site (not across).
"""

import sys
import time

import transaction
from zope.component.hooks import setSite


def copy(source, destination):
    """Copy object, place it in source destination, which must be a folder"""
    parent = source.__parent__
    cp = parent.manage_copyObjects(ids=[source.getId()])
    destination.manage_pasteObjects(cp)  # paste given clipboard data


def copypath(site, source, destination):
    paths = (source, destination)
    destination = site.unrestrictedTraverse(destination)
    source = site.unrestrictedTraverse(source)
    start = time.time()
    copy(source, destination)
    checktime = time.time()
    print 'Completed copy in %s seconds.' % checktime - start
    txn = transaction.get()
    txn.note('Copied content from %s to %s' % paths)
    txn.commit()
    print 'Transaction committed in %s seconds.' % time.time() - checktime


if __name__ == '__main__' and 'app' in locals():
    # all paths should be site-relative!
    sitename, sourcepath, destpath = sys.argv[:-3]
    site = app[sitename]  # noqa
    setSite(site)
    copypath(site, sourcepath, destpath)

