import csv
import os
from datetime import date, timedelta
from StringIO import StringIO

from zope.component.hooks import setSite
from zope.interface import Interface, implements
from zope import schema
from zope.schema import getFieldNamesInOrder
from zope.schema.vocabulary import SimpleVocabulary, SimpleTerm
from AccessControl.SecurityManagement import newSecurityManager
from Products.CMFCore.utils import getToolByName

from uu.qiext.interfaces import IProjectContext, IWorkspaceContext
from uu.qiext.user.interfaces import IWorkspaceRoster
from upiqsite.projects.migration import not_yet_migrated, migrate_site


_u = lambda v: v.decode('utf-8') if isinstance(v, str) else unicode(v)
_utf8 = lambda v: v.encode('utf-8') if isinstance(v, unicode) else v

_mkvocab = lambda seq: SimpleVocabulary([SimpleTerm(t) for t in seq])


# site order matters, first breaks ties on same project name!
SITES = (
    'cnhnqi',
    'qiteamspace',
    'opip',
    )

# ignored users are typically site-testing users of project managers
# who have other primary userid/email identification we care about
# reporting on without duplication.
USER_IGNORE = (
    # UPIQ:
    'sdupton@gmail.com',
    'snaeole@llu.edu',
    'snaeole@hotmail.com',
    'snaeole@gwu.edu',
    # OPIP:
    'ross8305@gmail.com',
    'ktconner3@yahoo.com',
    # CNHNQI:
    'tamaranjohn@yahoo.com',
    'tamaranjohn@gmail.com',
    )

ignore_user = lambda u: 'hsc.utah.edu' in str(u) or u in USER_IGNORE

DIRNAME = '/var/www/usage'

MONTHS = {
    1: 'January',
    2: 'February',
    3: 'March',
    4: 'April',
    5: 'May',
    6: 'June',
    7: 'July',
    8: 'August',
    9: 'September',
    10: 'October',
    11: 'November',
    12: 'December',
}


class IProjectSnapshot(Interface):
    name = schema.BytesLine()
    title = schema.TextLine()
    month = schema.Choice(
        vocabulary=_mkvocab(MONTHS.values()),
        )
    date = schema.Date()
    users = schema.Int(constraint=lambda v: v >= 0)
    managers = schema.Int(constraint=lambda v: v >= 0)
    form_users = schema.Int(constraint=lambda v: v>=0)
    teams = schema.Int(constraint=lambda v: v >= 0)


class ProjectSnapshot(object):
    
    implements(IProjectSnapshot)
    
    NAMES = schema.getFieldNamesInOrder(IProjectSnapshot)
    
    def __init__(self, **kwargs):
        
        for k, v in kwargs.items():
            if k in self.NAMES:
                IProjectSnapshot[k].validate(v)
                setattr(self, k, v)
    
    def __setattr__(self, name, value):
        """Validating setattr for any schema fields"""
        if name in self.NAMES:
            IProjectSnapshot[name].validate(value)
        self.__dict__[name] = value


def is_end_of_month(datestamp):
    next_day = datestamp + timedelta(days=1)
    if next_day.month != datestamp.month:
        return True
    return False


def all_workspaces(project):
    """
    Return flattened list of all contained workspaces,
    including project itself.
    """
    catalog = getToolByName(project, 'portal_catalog')
    r = catalog.search({
        'portal_type' : ('qiteam', 'qisubteam', 'qiproject'),
        'path' : {'query': '/'.join(project.getPhysicalPath())},
        })
    workspaces = map(lambda b: b._unrestrictedGetObject(), r)
    return workspaces


def form_users(workspace):
    """Given a workspace, get the ids of users with forms role"""
    roster = IWorkspaceRoster(workspace)
    _formusers = set(roster.groups['forms'].keys())
    _leads = set(roster.groups['managers'].keys())
    return list(_formusers | _leads)


def merged_form_users(project):
    """
    Given a project, get de-duped set of form users from all 
    contained workspaces, not including managers at root of the
    project.
    """
    workspaces = all_workspaces(project)
    _form_users = [form_users(w) for w in workspaces]
    merged = set(reduce(lambda a,b: set(a)|set(b), _form_users))
    exclude = set(IWorkspaceRoster(project).groups['managers'].keys())
    return list(merged - exclude)


def filtered_users(c):
    """
    Given collection c of users, return list of non-ignored
    users.
    """
    return [u for u in c if not ignore_user(u)]


def report_main(site, datestamp):
    """
    Given site and datestamp for snapshot, append report result to
    file named project_users.csv with column format:
    
    month, date, project_name, #users, #managers, #teams, #forms.
    """
    catalog = getToolByName(site, 'portal_catalog')
    r = catalog.search({'object_provides': IProjectContext.__identifier__})
    projects = [brain._unrestrictedGetObject() for brain in r]
    outputs = {}
    if not os.path.isdir(DIRNAME):
        os.mkdir(DIRNAME)
    for project in projects:
        filename = os.path.join(DIRNAME, '%s.csv' % project.getId())
        columns = ('month', 'date', 'users', 'managers', 'teams', 'form_users')
        if os.path.exists(filename):
            out = open(filename, 'r')
            data = out.readlines()  # existing data in file
            out.close()
            if any([(str(datestamp) in line) for line in data]):
                continue  # don't duplicate entry for date if already in file
            out = open(filename, 'a')  # append to EOF
        else:
            out = open(filename, 'w')  # will create
            out.write('%s\n' % ','.join(columns))  # new file, ergo headings
        writer = csv.DictWriter(out, columns, extrasaction='ignore')
        roster = IWorkspaceRoster(project)
        snapshot = ProjectSnapshot(
            name=project.getId(),
            title=_u(project.Title()),
            )
        snapshot.date = datestamp
        snapshot.month = MONTHS.get(datestamp.month)
        snapshot.users = len(filtered_users(roster))
        snapshot.managers = len(
            filtered_users(
                roster.groups['managers'].keys()
                )
            )
        snapshot.form_users = len(
            filtered_users(
                merged_form_users(project)
                )
            )
        teams = [o for o in project.contentValues()
                    if IWorkspaceContext.providedBy(o)]
        snapshot.teams = len(teams)
        # write row to CSV from snapshot, convert unicode to utf-8 as needed
        writer.writerow(
            dict([(k,_utf8(v)) for k,v in snapshot.__dict__.items()]))
        out.close()


def main(app, datestamp=None, username='admin'):
    for sitename in SITES:
        site = app.get(sitename)
        setSite(site)
        # user spoofins, try site user folder and instance/app/root user folder
        contexts = (site, app)
        for context in contexts:
            uf = context.acl_users
            user = uf.getUserById(username)
            if user is not None:
                newSecurityManager(None, user)
                break
        if user is None:
            raise RuntimeError('Unable to obtain user for username %s' % username)
        # 2012-03-15 migration; if not yet migrated (pre March 15), migrate.
        if sitename=='qiteamspace' and not_yet_migrated(site):
            migrate_site(site)
        report_main(site, datestamp)


if 'app' in locals():
    import sys
    datestamp = date.today()
    if len(sys.argv) > 1:
        datestamp = sys.argv[1]
        year, month, day = (datestamp[0:4], datestamp[5:7], datestamp[8:10])
        datestamp = date(*[int(v) for v in (year, month, day)])
    main(app, datestamp)

