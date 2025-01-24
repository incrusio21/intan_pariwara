# Copyright (c) 2025, DAS and Contributors
# License: GNU General Public License v3. See license.txt

from base64 import b32encode
import os
import requests
import json

import pyotp

import frappe
from frappe import _
from frappe.email.doctype.notification.notification import get_context

excluded_doctypes = [
    "DocType",
    "Version",
    "Comment",
    "Property Setter",
    "OTP Setting",
    "OTP Service",
    "OTP Notification",
]

class OtpNotification:
    def __init__(self, doc, method):
        self.doc = doc
        self.method = method

        if self.doc.doctype in excluded_doctypes:
            return

        self.set_otp_setting()
        self.otp_notification = self.get_otp_notification()
        if not self.otp_notification:
            return

        self.run_otp_notification()

    def set_otp_setting(self):
        self.interval, self.digits = get_otp_setting()

    def get_otp_notification(self):
        def _get_notifications():
            """returns enabled notifications for the current doctype"""

            return frappe.get_all(
                "OTP Notification",
                fields=["name", "event", "otp_service", "workflow_state", "field_otp_secret", "body"],
                filters={"enabled": 1, "document_type": self.doc.doctype},
            )

        return frappe.cache.hget("otp_notifications", self.doc.doctype, _get_notifications)

    def run_otp_notification(self):
        event_map = {
			"on_update": "Save",
			"after_insert": "New",
			"on_submit": "Submit",
			"on_cancel": "Cancel",
		}

        for alert in self.otp_notification:
            event = event_map.get(self.method, None)
            if event and alert.event == event:
                self.send_otp(alert)
            elif alert.event == "Workflow" and self.method == "on_change":
                self.get_doctype_workflow(alert)

    def get_doctype_workflow(self, alert):
        from frappe.model.workflow import get_workflow

        workflow = get_workflow(self.doc.doctype)
        if not workflow:
            return
        
        doc_before_save = self.doc.get_doc_before_save()
        field_value_before_save = doc_before_save.get(workflow.workflow_state_field) if doc_before_save else None

        if self.doc.get(workflow.workflow_state_field) == field_value_before_save \
            and alert.workflow_state == self.doc.get(workflow.workflow_state_field):
            # value not changed
            return

        self.send_otp(alert)
        
    def set_otp_secret(self, tmp_id):
        otp_secret = b32encode(os.urandom(10)).decode("utf-8")

        for k, v in {"_otp_secret": otp_secret}.items():
            frappe.cache.set(f"{tmp_id}{k}", v)
            frappe.cache.expire(f"{tmp_id}{k}", self.interval)

        return otp_secret
    
    def get_otp(self, otp_secret):
        tmp_id = self.doc.get(otp_secret)
        if not tmp_id:
            frappe.throw("FIeld {} not Found / Empty".format(otp_secret))
        
        return int(pyotp.TOTP(self.set_otp_secret(tmp_id), self.digits, interval=self.interval).now())

    def send_otp(self, alert):
        otp_setting = frappe.get_cached_doc("OTP Service", alert.otp_service)

        headers = {
            'Content-Type': 'application/json',
            'Authorization': f"{otp_setting.authorization_type} {otp_setting.authorization}"
        }

        context = get_context(self.doc)
        context.update({
            "otp_number": self.get_otp(alert.field_otp_secret)
        })
        
        response = requests.request("POST", otp_setting.url, headers=headers, data=frappe.render_template(alert.body, context))
        
        # response ini hanya berlaku untuk mekari qontak. jika terdapat service lain tolong d tambahkan
        ress = json.loads(response.text)
        if ress["status"] == "success":
            return
        
        frappe.throw("<br>".join(ress["error"]["messages"]), title=ress["error"]["code"])

def get_otp_setting():
    otp_setting = frappe.get_cached_doc("OTP Setting")
    return [otp_setting.validity_period * 60, otp_setting.number_length]

def request_otp_notification(document_type, document_no, method):
    doc = frappe.get_doc(document_type, document_no)
    OtpNotification(doc, method)

    frappe.msgprint("Your OTP has been Sent")

def get_verification_otp(otp, tmp_id):
    otp_secret = frappe.cache.get(tmp_id + "_otp_secret")
    if not otp_secret:
        frappe.throw(_("OTP already expired"))
    
    interval, digits = get_otp_setting()
    totp = pyotp.TOTP(otp_secret, digits, interval=interval)
    if totp.verify(otp):
        return True
    else:
        frappe.throw(_("Incorrect Verification code"))