import itertools
import logging
from pprint import pformat
import sys

from Acquisition import aq_base
import transaction
from zope.component.hooks import setSite

from uu.qiext.user.interfaces import IGroups, ISiteMembers, IWorkspaceRoster
from uu.qiext.utils import group_workspace, project_containing


SITENAMES = ('qiteamspace', 'opip', 'cnhnqi')

WORKSPACE_TYPES = ('qiproject', 'qiteam', 'qisubteam')
_getobject = lambda brain: brain._unrestrictedGetObject()


def _logger():
    logger = logging.getLogger('fix_local_roles')
    logfile = open('fixroles.log', 'a')
    handlers = (
        logging.StreamHandler(sys.stdout),
        logging.StreamHandler(logfile),
        )
    for handler in handlers:
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    return logger

logger = _logger()

ownerless = []

def fix_workspace_roles(site):
    global logger, ownerless
    setSite(site)
    catalog = site.portal_catalog
    groups = IGroups(site)
    before_groups = len(groups)
    members = ISiteMembers(site)
    spaces = map(_getobject, catalog.unrestrictedSearchResults({'portal_type': WORKSPACE_TYPES}))
    logger.info('  Checking %s workspaces' % len(spaces))
    for workspace in spaces:
        path = '/'.join(workspace.getPhysicalPath())
        logger.info('Workspace: %s (%s)' % (workspace.Title(), path))
        lr = workspace.__ac_local_roles__
        logger.info('  Found local roles for pricipals: \n%s' % pformat(lr,4))
        roster = IWorkspaceRoster(workspace)
        ignore = [g.pas_group() for g in roster.groups.values()]
        logger.info('    IGNORING native workspace groups: \n%s' % pformat(ignore,6))
        non_native_groups = set(lr.keys()) - set(ignore)
        _removed = []
        for principal_name in non_native_groups:
            if principal_name == 'admin':
                continue
            if principal_name not in groups:
                if principal_name not in members:
                    logger.info('Found principal name not a known group or '\
                                'member, removing: %s (from %s)' % (
                                    principal_name, path))
                    _removed.append(principal_name)
                    del(lr[principal_name])
                    continue
                else:
                    continue  # not a group name, but is a user name, ignore
            gw = group_workspace(principal_name)
            if gw is None:
                group = groups.get(principal_name)
                if group is None:
                    logger.info('Found name for a since-removed group, '\
                                'removing local roles: %s (from %s)' % (
                                    principal_name, path))
                    _removed.append(principal_name)
                    del(lr[principal_name])
                elif not len(group.keys()):
                    logger.info('Found principal name for an empty group, '\
                                'removing local roles: %s (from %s)' % (
                                    principal_name, path))
                    _removed.append(principal_name)
                    del(lr[principal_name])
                    groups.remove(principal_name)  # remove from PAS
                    continue
                else:
                    logger.info('WARNING: non-workspace group: "%s" in %s' % (
                        principal_name, path))
                continue  # a non-workspace group
            if aq_base(gw) is not aq_base(workspace):
                # we have a group workspace (and thus a group name) not
                # directly of this workspace...
                # 1. is group workspace is contained child of workspace?
                if aq_base(project_containing(gw)) is aq_base(workspace):
                    continue
                # if not, then group belongs to another workspace not
                # directly contained, likely result of copy/paste bug:
                logger.info('DELETING local roles for %s in %s' % (
                    principal_name,
                    path,
                    ))
                _removed.append(principal_name)
                del(lr[principal_name])
        # finally a sanity check to make sure that all workspace groups
        # still exist:
        lr_keys = workspace.__ac_local_roles__.keys()
        for group in roster.groups.values():
            assert group.pas_group() in lr_keys
        # finally, make sure there is an owner for the workspace, make
        # 'admin' user have 'Owner' role, if not:
        if not 'Owner' in list(
                itertools.chain(*workspace.__ac_local_roles__.values())
                ):
            logger.info('Found owner-less workspace, made admin owner: %s' % (
                path,))
            workspace.__ac_local_roles__[u'admin'] = ['Owner']
            workspace._p_changed = True
        if _removed:
            workspace._p_changed = True
        if workspace._p_changed:
            txn = transaction.get()
            txn.note(path)
            txn.note('Removed local roles from workspace %s for %s' % (
                workspace.getId(), tuple(set(_removed))))
            txn.commit()
            logger.info('-- TRANSACTION COMMIT --')
    
    logger.info('\n-----\nVERIFICATION PHASE\n-----')
    for workspace in spaces:
        logger.info('Workspace: %s (%s)' % (
            workspace.Title(),
            '/'.join(workspace.getPhysicalPath()),
            ))
        lr = workspace.__ac_local_roles__
        logger.info('  Updated local roles for pricipals: \n%s' % pformat(lr,4))
    
    logger.info('\n-----\nNOTES\n-----')
    after_groups = len(groups)
    logger.info('PAS GROUP COUNT (before/after): %s, %s' % (
        before_groups, after_groups))


if __name__ == '__main__' and 'app' in locals():
    sites = [app.get(name) for name in SITENAMES]
    for site in sites:
        logger.info('Checking local roles for workspaces in site %s' % site)
        fix_workspace_roles(site)

