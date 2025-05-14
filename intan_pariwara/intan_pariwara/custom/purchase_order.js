// Copyright (c) 2025, DAS and Contributors
// License: GNU General Public License v3. See license.txt

intan_pariwara.buying.PurchaseOrderController = class PurchaseOrderController extends erpnext.buying.PurchaseOrderController {
	setup() {
		super.setup();

        const transaction = new intan_pariwara.utils.Transaction({ frm: this.frm });
        transaction.default_warehouse()
	}
}

cur_frm.script_manager.make(intan_pariwara.buying.PurchaseOrderController);