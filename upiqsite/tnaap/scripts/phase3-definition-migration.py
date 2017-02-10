# one-off migration script for TNAAP BPPR project

from Acquisition import aq_base
from OFS.event import ObjectClonedEvent
from plone.uuid.interfaces import IUUID
import transaction
from zope.component.hooks import setSite, getSite
from zope.event import notify
from zope.lifecycleevent import ObjectModifiedEvent, ObjectCopiedEvent

from uu.formlibrary.formsets import DefinitionFormSet
from uu.formlibrary.interfaces import IMultiForm


multi_to_single = [
    {
        'source_field':
            'what_was_the_age_in_years_at_completion_of_the_third_hpv_',
        'dest_field':
            'what_was_the_age_in_years_at_completion_for_the_final_hpv_',
    },
    {
        'source_field': 'what_is_the_patient_s_gender_',
        'dest_field': 'what_is_the_patient_s_gender',
    },
    {
        'source_field': 'is_the_adolescent_sexually_active_',
        'dest_field': 'was_the_adolescent_screened_for_sexual_activity_',
    },
    {
        'source_field': 'how_many_hpv_vaccines_has_the_patient_received_',
        'dest_field': 'how_many_hpv_vaccines_has_the_patient_received_',
        'value_map': {
            '3 or more': '3',
            '2': '2 - less than 6 months apart'
        },
    },
]


_marker = object()


def migrate_form_data(form, definition):
    for record in form.values():
        # update signature of schema:
        record.sign(definition.schema)
        # modify data in place:
        for spec in multi_to_single:
            source_name = spec.get('source_field')
            dest_name = spec.get('dest_field', source_name)
            vmap = spec.get('value_map', None)
            fielddata = getattr(record, source_name, _marker)
            if fielddata is not _marker and fielddata:
                first = list(fielddata)[0]
                if vmap is not None and first in vmap:
                    first = vmap[first]
                setattr(record, dest_name, first)
                if source_name != dest_name:
                    delattr(record, source_name)  # delete old after move data
            else:
                setattr(record, dest_name, definition.schema[dest_name].default)


def backup_form(form, site):
    formId = form.getId()
    copyId = 'original-premigration-%s' % formId
    series = form.__parent__
    ## make clone:
    unwrapped = aq_base(form)
    copied = unwrapped._getCopy(series)
    copied._setId(copyId)
    copied.title = '%s (archival copy, pre-migration)' % copied.title
    notify(ObjectCopiedEvent(copied, form))
    series._setObject(copyId, copied)
    copied = series._getOb(copyId)
    notify(ObjectClonedEvent(copied))
    ## make clone private:
    site.portal_workflow.doActionFor(copied, 'hide')


def migrate_form(form, old_def, new_def, site=None):
    site = site or getSite()
    has_data = len(form) > 0
    # create a private backup copy:
    backup_form(form, site)
    # update form binding to new definition:
    form.definition = IUUID(new_def)
    if has_data:
        migrate_form_data(form, new_def)
    notify(ObjectModifiedEvent(form))


def migrate(site):
    project = site.bppr
    formlib = project['form-library']
    old_def = formlib['bppr-phase-3-chart-review']
    new_def = formlib['bppr-phase-3-chart-review-revised']
    formset = DefinitionFormSet(old_def)
    site = getSite()
    for form in formset.itervalues():
        if IMultiForm.providedBy(form):
            migrate_form(form, old_def, new_def, site)


def commit(message):
    txn = transaction.get()
    txn.note(message)
    txn.commit()


def main(app):
    site = app.tnaap
    setSite(site)
    migrate(site)
    commit('Migrated forms to new schema')


if __name__ == '__main__' and 'app' in locals():
    main(app)  # noqa

