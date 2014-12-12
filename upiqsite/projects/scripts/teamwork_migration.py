import time

from Acquisition import aq_base
import transaction
from zope.component.hooks import setSite


BASEPATH = '/VirtualHostBase/https/teamspace1.upiq.org'

_installed = lambda site: site.portal_quickinstaller.isProductInstalled
product_installed = lambda site, name: _installed(site)(name)


def qiext_installed(site):
    return product_installed(site, 'uu.qiext')


def commit(context, msg):
    txn = transaction.get()
    # Undo path, if you want to use it, unfortunately is site-specific,
    # so use the hostname used to access all Plone sites.
    txn.note('%s%s' % (BASEPATH, '/'.join(context.getPhysicalPath())))
    txn.note(msg)
    txn.commit()


def install_step(site, profile, stepname):
    gs = site.portal_setup
    if stepname not in gs.getSortedImportSteps():
        raise ValueError('unknown import step named %s' % stepname)
    r = gs.runImportStepFromProfile(profile, stepname, False)
    print '\n\n== SITE: %s ==\n' % site.getId()
    print r.get('messages').get(stepname)


def install_teamwork_addon(site, name='collective.teamwork'):
    # install the c.teamwork add-on if not already installed:
    if not product_installed(site, name):
        site.portal_quickinstaller.installProduct(name)
    # run the Types tool step of the "Team" profile of c.teamwork:
    install_step(site, 'profile-%s:team' % name, stepname='typeinfo')


def update_workflow_history(content):
    renames = {
        # old -> new workflow chain key/name:
        'qiext_project_workflow': 'teamwork_project_workflow',
        'qiext_workspace_workflow': 'teamwork_workspace_workflow',
    }
    history = content.workflow_history
    for old, new in renames.items():
        if old in history:
            history[new] = history[old]
            del(history[old])
    content._p_changed = True   # almost certainly changed, no need to detect


def update_portal_type(content):
    renames = {
        # old -> new portal_type values:
        'qiproject': 'collective.teamwork.project',
        'qiteam': 'collective.teamwork.team',  # TODO make this
        'qisubteam': 'collective.teamwork.workspace',
    }
    for old, new in renames.items():
        if content.portal_type == old:
            content.portal_type = new
            break
    content._p_changed = True


def get_workspaces(site):
    q = {
        'portal_type': {
            'query': ('qiproject', 'qiteam', 'qisubteam'),
            'operator': 'or',
            }
        }
    _get = lambda brain: brain._unrestrictedGetObject()
    return map(_get, site.portal_catalog.unrestrictedSearchResults(q))


def update_content_state(site):
    workspaces = get_workspaces(site)
    for workspace in workspaces:
        content = aq_base(workspace)
        update_portal_type(content)
        update_workflow_history(content)
    return workspaces


def reindex_catalog(site, workspaces):
    #site.portal_catalog.clearFindAndRebuild()
    for workspace in workspaces:
        workspace.reindexObject()


def remove_browserlayer(site, name):
    from plone.browserlayer.interfaces import ILocalBrowserLayerType
    sm = site.getSiteManager()
    util = sm.getUtility(ILocalBrowserLayerType, name=name)
    sm.unregisterUtility(util, ILocalBrowserLayerType, name=name)
    del util


def remove_skins_dir(site, name, theme='Sunburst Theme'):
    skins = site.portal_skins
    skins.manage_delObjects(name)
    sel = skins.selections[theme]
    sel = sel.replace(name, '')
    sel = sel.replace(',,', ',')
    skins.selections[theme] = sel


def uninstall_old_products(site):
    installer = site.portal_quickinstaller
    # Un-install uu.qiext:
    #   -- remove skins FSDirView and layers:
    remove_skins_dir(site, 'uu_qiext')
    #   -- remove add permissions (not roles, though):
    base = aq_base(site)
    for p_attr in (
        '_qiproject__Add_Project_Permission',
        '_qiproject__Add_Team_Permission',
        '_qiteam__Add_SubTeam_Permission',
        '_PloneHelpCenter__Add_Documentation_Permission',
        '_PloneHelpCenter__Add_Help_Center_Area_Permission',
        '_PloneHelpCenter__Add_Plone_Help_Center_Permission',
        '_Plone__Manage_Site_Layouts_Permission',
            ):
        if hasattr(base, p_attr):
            delattr(base, p_attr)
    #   -- remove ++resource++qiext.css from CSS registry:
    site.portal_css.unregisterResource('++resource++qiext.css')
    #   -- remove browser layer:
    remove_browserlayer(site, u'uu.qiext')
    #   -- remove Products.qi types from tinymce linkable, folder types:
    tmt = site.portal_tinymce
    tmt.linkable = '\n'.join(
        l for l in tmt.linkable.split('\n') if not l.startswith('qi')
        ).strip()
    tmt.containsobjects = '\n'.join(
        l for l in tmt.containsobjects.split('\n') if not l.startswith('qi')
        ).strip()
    #   -- remove workflow definitions:
    wftool = site.portal_workflow
    wftool.manage_delObjects(
        [name for name in wftool if name.startswith('qiext')]
        )
    #   -- finally, uninstall the product record:
    if product_installed(site, 'uu.qiext'):
        installer.uninstallProducts(['uu.qiext'])
    # uninstall Products.qi (types, viewlet stuff)
    #   -- remove skins:
    remove_skins_dir(site, 'qi_plone4_overrides')
    #   -- remove browser layer:
    remove_browserlayer(site, u'Products.qi')
    #   -- remove the type FTIs for qiproject, qiteam, qisubteam
    site.portal_types.manage_delObjects(['qiproject', 'qisubteam', 'qiteam'])
    #   -- finally, uninstall the product record:
    if product_installed(site, 'Products.qi'):
        installer.uninstallProducts(['Products.qi'])


def pre_install_cleanups(site):
    # the 'enhanced_localroles' PAS plugin from uu.qiext needs removal before
    # a plugin of the same name is installed by collective.teamwork setup
    # profile...
    from borg.localrole.config import LOCALROLE_PLUGIN_NAME  # stock name
    from Products.PlonePAS.Extensions.Install import activatePluginInterfaces
    from Products.PlonePAS.interfaces.plugins import ILocalRolesPlugin
    uf = site.acl_users
    # Deactivate the 'enhanced_localroles', re-activate stock; this will
    # later be overridden when collective.teamwork is installed
    uf.plugins.deactivatePlugin(ILocalRolesPlugin, 'enhanced_localroles')
    activatePluginInterfaces(site, LOCALROLE_PLUGIN_NAME)
    # remove the 'enhanced_localroles' plugin:
    site.acl_users.manage_delObjects(['enhanced_localroles'])
    # finally, clean up any intids/relations utilities not cleaned already:
    sm = site.getSiteManager()
    util_remove = ('intids', 'relations')
    sm._objects = tuple(
        o for o in sm._objects if o.get('id') not in util_remove
        )


def stamp(start, last):
    now = time.time()
    since_start = now - start
    since_last = now - last
    print '\t\t Step completed: %.0f seconds (%.0f since start)' % (
        since_last,
        since_start,
        )
    return now


def workflow_history_update(site):
    counter = 0
    for brain in site.portal_catalog.unrestrictedSearchResults({}):
        content = aq_base(brain._unrestrictedGetObject())
        if getattr(content, 'workflow_history', None) is not None:
            update_workflow_history(content)
            counter += 1
        if counter % 3000 == 0:
            site._p_jar.cacheMinimize()


def migrate(site):
    last = start = time.time()
    print '\t-- Pre-site cleanups (PAS)'
    pre_install_cleanups(site)
    last = stamp(start, last)
    print '\t-- Uninstalling old products'
    uninstall_old_products(site)
    last = stamp(start, last)
    print '\t-- Installing collective.teamwork'
    install_teamwork_addon(site)
    last = stamp(start, last)
    print '\t-- Updating content state (portal_type and workflow_history)'
    workspaces = update_content_state(site)
    last = stamp(start, last)
    print '\t-- Reindexing portal_catalog'
    reindex_catalog(site, workspaces)
    last = stamp(start, last)
    print '\t-- Updating workflow history content state in ALL site content.'
    workflow_history_update(site)
    last = stamp(start, last)
    print '\t-- Committing transaction'
    commit(site, 'Migrated site from uu.qiext to collective.teamwork')
    last = stamp(start, last)


def main(app):
    for site in app.objectValues('Plone Site'):
        if qiext_installed(site):
            print '== MIGRATING SITE: %s ==' % site.getId()
            setSite(site)
            migrate(site)
            app._p_jar.cacheMinimize()


if __name__ == '__main__' and 'app' in locals():
    main(app)  # noqa

