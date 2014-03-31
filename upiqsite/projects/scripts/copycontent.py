"""
copycontent.py -- command line tool for copying content within a single Plone
site (not across).
"""

import sys
import time

from AccessControl.SecurityManagement import newSecurityManager
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


def get_site(app, name):
    """Get site, with local component context set, and security manager"""
    site = app[sitename]
    setSite(site)
    user = app.acl_users.getUser('admin')
    newSecurityManager(None, user)


if __name__ == '__main__' and 'app' in locals():
    # all paths should be site-relative!
    sitename, sourcepath, destpath = sys.argv[:-3]
    site = get_site(app, sitename)  # noqa
    copypath(site, sourcepath, destpath)

