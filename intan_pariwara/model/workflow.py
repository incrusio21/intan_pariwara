# Copyright (c) 2025, DAS and Contributors
# License: MIT. See LICENSE

import frappe
from frappe import _
from typing import TYPE_CHECKING, Union

from frappe.model.docstatus import DocStatus
from frappe.model.workflow import (
    get_workflow, has_approval_access, is_transition_condition_satisfied,
    WorkflowStateError, WorkflowTransitionError
)
from frappe.utils import cint

if TYPE_CHECKING:
	from frappe.model.document import Document
	from frappe.workflow.doctype.workflow.workflow import Workflow

@frappe.whitelist()
def apply_workflow(doc, action, reason=None):
    """Allow workflow action on the current doc"""
    doc = frappe.get_doc(frappe.parse_json(doc))
    doc.load_from_db()
    workflow = get_workflow(doc.doctype)
    transitions = get_transitions(doc, workflow)
    user = frappe.session.user

    # find the transition
    transition = None
    for t in transitions:
        if t.action == action:
            transition = t

    if not transition:
        frappe.throw(_("Not a valid Workflow Action"), WorkflowTransitionError)

    if not has_approval_access(user, doc, transition):
        frappe.throw(_("Self approval is not allowed"))

    # update workflow state field
    doc.set(workflow.workflow_state_field, transition.next_state)

    # find settings for the next state
    next_state = next(d for d in workflow.states if d.state == transition.next_state)

    # update any additional field
    if next_state.update_field:
        doc.set(next_state.update_field, next_state.update_value)

    if workflow.reason_required and not reason \
        and action == workflow.workflow_action:
        frappe.throw(_("A reason is required to {} and Submit.".format(workflow.workflow_action)))

    if workflow.reason_required:
        doc.set(workflow.workflow_reason_field, reason)
    new_docstatus = cint(next_state.doc_status)
    if doc.docstatus.is_draft() and new_docstatus == DocStatus.draft():
        doc.save()
    elif doc.docstatus.is_draft() and new_docstatus == DocStatus.submitted():
        doc.submit()
    elif doc.docstatus.is_submitted() and new_docstatus == DocStatus.submitted():
        doc.save()
    elif doc.docstatus.is_submitted() and new_docstatus == DocStatus.cancelled():
        doc.cancel()
    else:
        frappe.throw(_("Illegal Document Status for {0}").format(next_state.state))

    doc.add_comment("Workflow", _(next_state.state))

    return doc

@frappe.whitelist()
def get_transitions(
	doc: Union["Document", str, dict], workflow: "Workflow" = None, raise_exception: bool = False
) -> list[dict]:
    """Return list of possible transitions for the given doc"""
    from frappe.model.document import Document

    if not isinstance(doc, Document):
        doc = frappe.get_doc(frappe.parse_json(doc))
        doc.load_from_db()

    if doc.is_new():
        return []

    doc.check_permission("read")

    workflow = workflow or get_workflow(doc.doctype)
    current_state = doc.get(workflow.workflow_state_field)

    if not current_state:
        if raise_exception:
            raise WorkflowStateError
        else:
            frappe.throw(_("Workflow State not set"), WorkflowStateError)

    transitions = []
    roles = frappe.get_roles()
    
    for transition in workflow.transitions:
        if transition.state == current_state and transition.allowed in roles:
            if not is_transition_condition_satisfied(transition, doc):
                continue
            
            trn = transition.as_dict()
            trn.reason = workflow.reason_required and workflow.workflow_action == transition.action
            transitions.append(trn)

    return transitions