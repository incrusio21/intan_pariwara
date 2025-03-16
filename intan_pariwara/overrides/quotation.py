# Copyright (c) 2025, DAS and Contributors
# License: GNU General Public License v3. See license.txt

from erpnext.selling.doctype.quotation.quotation import Quotation
from intan_pariwara.controllers.account_controller import AccountsController

class Quotation(AccountsController, Quotation):
    pass