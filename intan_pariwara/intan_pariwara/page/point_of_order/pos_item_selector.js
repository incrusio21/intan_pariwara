import onScan from "onscan.js";

erpnext.PointOfOrder.ItemSelector = class {
	// eslint-disable-next-line no-unused-vars
	constructor({ frm, wrapper, events, poe_profile, company, settings }) {
		this.wrapper = wrapper;
		this.events = events;
		this.poe_profile = poe_profile;
		this.company = company;
		this.hide_images = settings.hide_images;
		this.auto_add_item = settings.auto_add_item_to_cart;
		// memoize
		this.search_index = {}
		this.non_search_term = settings.cache_non_search_term;
		this.request_item = null

		this.init_component();
	}

	init_component() {
		this.prepare_dom();
		this.make_search_bar();
		this.load_items_data();
		this.bind_events();
		this.attach_shortcuts();
	}

	prepare_dom() {
		this.wrapper.append(
			`<section class="items-selector">
				<div class="filter-section">
					<div class="label" style="grid-row: 2 span / span 2;">${__("All Items")}</div>
					<div class="search-field"></div>
					<div class="item-group-field"></div>
					<div class="mata-pelajaran-field"></div>
					<div class="jenjang-field"></div>
					<div class="kode-kelas-field"></div>
				</div>
				<div class="items-container"></div>
			</section>`
		);

		this.$component = this.wrapper.find(".items-selector");
		this.$items_container = this.$component.find(".items-container");
	}

	async load_items_data() {
		if (!this.item_group) {
			const res = await frappe.db.get_value("Item Group", { lft: 1, is_group: 1 }, "name");
			this.parent_item_group = res.message.name;
		}
		if (!this.price_list) {
			const res = await frappe.db.get_value("POE Profile", this.poe_profile, "selling_price_list");
			this.price_list = res.message.selling_price_list;
		}

		let key = [
			this.price_list,
			...(this.seller ? [this.seller] : []),
			...(this.item_group ? [this.item_group] : [this.parent_item_group]), 
			...(this.mata_pelajaran ? [this.mata_pelajaran] : []), 
			...(this.jenjang ? [this.jenjang] : []), 
			...(this.mata_pelajaran ? [this.mata_pelajaran] : []), 
			...(this.kode_kelas ? [this.kode_kelas] : [])];
		
		this.search_index[key] = this.search_index[key] || {}

		this.get_items({}).then(({ message }) => {
			// eslint-disable-next-line no-unused-vars
			const { items, serial_no, batch_no, barcode } = message;
			if (!barcode) {
				this.search_index[key][this.non_search_term] = items;
			}
			
			this.render_item_list(message.items);
		});
	}

	get_items({ start = 0, page_length = 40, search_term = "" }) {
		const price_list = this.price_list;
		let { item_group, jenjang, kode_kelas, mata_pelajaran, seller, poe_profile } = this;

		!item_group && (item_group = this.parent_item_group);
		
		if (this.request_item && this.request_item.state() === 'pending') {
			this.request_item.abort();
		}

		this.$items_container.html(`
			<div class="spinner-overlay">
				<div class="spinner"></div>
			</div>
		`);
		
		this.request_item = frappe.call({
			method: "intan_pariwara.intan_pariwara.page.point_of_order.point_of_order.get_items",
			args: { start, page_length, price_list, item_group, mata_pelajaran, jenjang, kode_kelas, search_term, seller, poe_profile },
		});

		return this.request_item
	}

	render_item_list(items) {
		this.$items_container.html("");

		items.forEach((item) => {
			const item_html = this.get_item_html(item);
			this.$items_container.append(item_html);
		});
	}

	get_item_html(item) {
		const me = this;
		// eslint-disable-next-line no-unused-vars
		const { item_image, serial_no, batch_no, barcode, actual_qty, uom, price_list_rate, produk_inti_type } = item;
		const precision = flt(price_list_rate, 2) % 1 != 0 ? 2 : 0;
		let indicator_color;
		let qty_to_display = actual_qty;

		if (item.is_stock_item) {
			indicator_color = actual_qty > 10 ? "green" : actual_qty <= 0 ? "red" : "orange";

			if (Math.round(qty_to_display) > 999) {
				qty_to_display = Math.round(qty_to_display) / 1000;
				qty_to_display = qty_to_display.toFixed(1) + "K";
			}
		} else {
			indicator_color = "";
			qty_to_display = "";
		}

		function get_item_image_html() {
			if (!me.hide_images && item_image) {
				return `<div class="item-qty-pill">
							<span class="indicator-pill whitespace-nowrap ${indicator_color}">${qty_to_display}</span>
						</div>
						<div class="flex items-center justify-center border-b-grey text-6xl text-grey-100" style="height:8rem; min-height:8rem">
							<img
								onerror="cur_pos.item_selector.handle_broken_image(this)"
								class="h-full item-img" src="${item_image}"
								alt="${frappe.get_abbr(item.item_name)}"
							>
						</div>`;
			} else {
				return `<div class="item-qty-pill">
							<span class="indicator-pill whitespace-nowrap ${indicator_color}">${qty_to_display}</span>
						</div>
						<div class="item-display abbr">${frappe.get_abbr(item.item_name)}</div>`;
			}
		}

		return `<div class="item-wrapper"
				data-item-code="${escape(item.item_code)}" data-serial-no="${escape(serial_no)}"
				data-batch-no="${escape(batch_no)}" data-uom="${escape(uom)}"
				data-rate="${escape(price_list_rate || 0)}"
				data-produk-inti-type="${escape(produk_inti_type)}"
				title="${item.item_name}">

				${get_item_image_html()}

				<div class="item-detail">
					<div class="item-name">
						${frappe.ellipsis(item.item_name, 18)}
					</div>
					<div class="item-rate">${format_currency(price_list_rate, item.currency, precision) || 0} / ${uom}</div>
				</div>
			</div>`;
	}

	handle_broken_image($img) {
		const item_abbr = $($img).attr("alt");
		$($img).parent().replaceWith(`<div class="item-display abbr">${item_abbr}</div>`);
	}

	make_search_bar() {
		const me = this;
		this.$component.find(".search-field").html("");
		this.$component.find(".item-group-field").html("");
		this.$component.find(".mata-pelajaran-field").html("");
		this.$component.find(".jenjang-field").html("");
		this.$component.find(".kode-kelas-field").html("");

		this.search_field = frappe.ui.form.make_control({
			df: {
				label: __("Search"),
				fieldtype: "Data",
				placeholder: __("Search by item code, serial number or barcode"),
			},
			parent: this.$component.find(".search-field"),
			render_input: true,
		});

		this.item_group_field = frappe.ui.form.make_control({
			df: {
				label: __("Item Group"),
				fieldtype: "Link",
				options: "Item Group",
				placeholder: __("Select item group"),
				onchange: function () {
					me.item_group = this.value;
					!me.item_group && (me.item_group = me.parent_item_group);
					me.filter_items({ search_term: me.search_field.last_value });
				},
				get_query: function () {
					const doc = me.events.get_frm().doc;
					return {
						query: "erpnext.selling.page.point_of_sale.point_of_sale.item_group_query",
						filters: {
							pos_profile: doc ? doc.pos_profile : "",
						},
					};
				},
			},
			parent: this.$component.find(".item-group-field"),
			render_input: true,
		});

		this.mata_pelajaran_field = frappe.ui.form.make_control({
			df: {
				label: __("Mata Pelajaran"),
				fieldtype: "Link",
				options: "Mata Pelajaran",
				placeholder: __("Select Mata Pelajaran"),
				onchange: function () {
					me.mata_pelajaran = this.value;
					me.filter_items({ search_term: me.search_field.last_value });
				},
			},
			parent: this.$component.find(".mata-pelajaran-field"),
			render_input: true,
		});

		this.jenjang_field = frappe.ui.form.make_control({
			df: {
				label: __("Jejang"),
				fieldtype: "Link",
				options: "Kode Jenjang",
				placeholder: __("Select Jenjang"),
				onchange: function () {
					console.log(this)
					me.jenjang = this.value;
					me.filter_items({ search_term: me.search_field.last_value });
				},
			},
			parent: this.$component.find(".jenjang-field"),
			render_input: true,
		});

		this.kode_kelas_field = frappe.ui.form.make_control({
			df: {
				label: __("Kode Kelas"),
				fieldtype: "Link",
				options: "Kode Kelas",
				placeholder: __("Select Kode Kelas"),
				onchange: function () {
					me.kode_kelas = this.value;
					me.filter_items({ search_term: me.search_field.last_value });
				},
			},
			parent: this.$component.find(".kode-kelas-field"),
			render_input: true,
		});

		this.search_field.toggle_label(false);
		this.item_group_field.toggle_label(false);
		this.mata_pelajaran_field.toggle_label(false);
		this.jenjang_field.toggle_label(false);
		this.kode_kelas_field.toggle_label(false);

		this.attach_clear_btn();
	}

	attach_clear_btn() {
		this.search_field.$wrapper.find(".control-input").append(
			`<span class="link-btn" style="top: 2px;">
				<a class="btn-open no-decoration" title="${__("Clear")}">
					${frappe.utils.icon("close", "sm")}
				</a>
			</span>`
		);

		this.$clear_search_btn = this.search_field.$wrapper.find(".link-btn");

		this.$clear_search_btn.on("click", "a", () => {
			this.set_search_value("");
			this.search_field.set_focus();
		});
	}

	set_search_value(value) {
		$(this.search_field.$input[0]).val(value).trigger("input");
	}

	bind_events() {
		const me = this;
		window.onScan = onScan;

		onScan.decodeKeyEvent = function (oEvent) {
			var iCode = this._getNormalizedKeyNum(oEvent);
			switch (true) {
				case iCode >= 48 && iCode <= 90: // numbers and letters
				case iCode >= 106 && iCode <= 111: // operations on numeric keypad (+, -, etc.)
				case (iCode >= 160 && iCode <= 164) || iCode == 170: // ^ ! # $ *
				case iCode >= 186 && iCode <= 194: // (; = , - . / `)
				case iCode >= 219 && iCode <= 222: // ([ \ ] ')
				case iCode == 32: // spacebar
					if (oEvent.key !== undefined && oEvent.key !== "") {
						return oEvent.key;
					}

					var sDecoded = String.fromCharCode(iCode);
					switch (oEvent.shiftKey) {
						case false:
							sDecoded = sDecoded.toLowerCase();
							break;
						case true:
							sDecoded = sDecoded.toUpperCase();
							break;
					}
					return sDecoded;
				case iCode >= 96 && iCode <= 105: // numbers on numeric keypad
					return 0 + (iCode - 96);
			}
			return "";
		};

		onScan.attachTo(document, {
			onScan: (sScancode) => {
				if (this.search_field && this.$component.is(":visible")) {
					this.search_field.set_focus();
					this.set_search_value(sScancode);
					this.barcode_scanned = true;
				}
			},
		});
		
		this.$component.on("click", ".item-wrapper", function () {
			const $item = $(this);
			const item_code = unescape($item.attr("data-item-code"));
			let batch_no = unescape($item.attr("data-batch-no"));
			let serial_no = unescape($item.attr("data-serial-no"));
			let uom = unescape($item.attr("data-uom"));
			let rate = unescape($item.attr("data-rate"));
			let produk_inti_type = unescape($item.attr("data-produk-inti-type"));

			// escape(undefined) returns "undefined" then unescape returns "undefined"
			batch_no = batch_no === "undefined" ? undefined : batch_no;
			serial_no = serial_no === "undefined" ? undefined : serial_no;
			uom = uom === "undefined" ? undefined : uom;
			rate = rate === "undefined" ? undefined : rate;
			
			let doc = me.events.get_frm().doc
			if((doc.items || []).length && produk_inti_type != doc.produk_inti_type){
				frappe.throw({
					title: __("Diffrent Produk Item Type"),
					message: __("Multiple Produk Item Type are present among Items."),
				});
			}

			const dialog = new frappe.ui.Dialog({
				title: __("Update Item Quantity"),
				fields: [
					{
						fieldtype: "Float",
						label: __("Quantity"),
						default: 1,
						fieldname: "qty",
						reqd: 1,
					},
				],
				primary_action: async function ({ qty }) {
					me.events.item_selected({
						field: "qty",
						value: qty,
						item: { item_code, batch_no, serial_no, uom, rate, produk_inti_type },
					});
					me.search_field.set_focus();
					dialog.hide();
				},
				primary_action_label: __("Submit"),
			});

			dialog.show();
		});

		this.search_field.$input.on("input", (e) => {
			clearTimeout(this.last_search);
			this.last_search = setTimeout(() => {
				const search_term = e.target.value;
				this.filter_items({ search_term });
			}, 500);

			this.$clear_search_btn.toggle(Boolean(this.search_field.$input.val()));
		});

		this.search_field.$input.on("focus", () => {
			this.$clear_search_btn.toggle(Boolean(this.search_field.$input.val()));
		});
	}

	attach_shortcuts() {
		const ctrl_label = frappe.utils.is_mac() ? "⌘" : "Ctrl";
		this.search_field.parent.attr("title", `${ctrl_label}+I`);
		frappe.ui.keys.add_shortcut({
			shortcut: "ctrl+i",
			action: () => this.search_field.set_focus(),
			condition: () => this.$component.is(":visible"),
			description: __("Focus on search input"),
			ignore_inputs: true,
			page: cur_page.page.page,
		});
		this.item_group_field.parent.attr("title", `${ctrl_label}+G`);
		frappe.ui.keys.add_shortcut({
			shortcut: "ctrl+g",
			action: () => this.item_group_field.set_focus(),
			condition: () => this.$component.is(":visible"),
			description: __("Focus on Item Group filter"),
			ignore_inputs: true,
			page: cur_page.page.page,
		});

		// for selecting the last filtered item on search
		frappe.ui.keys.on("enter", () => {
			const selector_is_visible = this.$component.is(":visible");
			if (!selector_is_visible || this.search_field.get_value() === "") return;

			if (this.items.length == 1) {
				this.$items_container.find(".item-wrapper").click();
				frappe.utils.play_sound("submit");
				this.set_search_value("");
			} else if (this.items.length == 0 && this.barcode_scanned) {
				// only show alert of barcode is scanned and enter is pressed
				frappe.show_alert({
					message: __("No items found. Scan barcode again."),
					indicator: "orange",
				});
				frappe.utils.play_sound("error");
				this.barcode_scanned = false;
				this.set_search_value("");
			}
		});
	}

	filter_items({ search_term = "" } = {}) {
		let cache_term = search_term
		if (!cache_term) cache_term = this.non_search_term;
		cache_term = cache_term.toLowerCase();
		
		let key = [
			this.price_list,
			...(this.seller ? [this.seller] : []),
			...(this.item_group ? [this.item_group] : [this.parent_item_group]),
			...(this.mata_pelajaran ? [this.mata_pelajaran] : []),  
			...(this.jenjang ? [this.jenjang] : []), 
			...(this.kode_kelas ? [this.kode_kelas] : [])];
		
		this.search_index[key] = this.search_index[key] || {}

		if (this.search_index[key][cache_term]) {
			const items = this.search_index[key][cache_term];
			this.items = items;
			this.render_item_list(items);
			this.auto_add_item && this.items.length == 1 && this.add_filtered_item_to_cart();
			return;
		}
		

		this.get_items({ search_term }).then(({ message }) => {
			// eslint-disable-next-line no-unused-vars
			const { items, serial_no, batch_no, barcode } = message;
			if (!barcode) {
				this.search_index[key][cache_term] = items;
			}
			
			this.items = items;
			this.render_item_list(items);
			this.auto_add_item && this.items.length == 1 && this.add_filtered_item_to_cart();
		});
	}

	add_filtered_item_to_cart() {
		this.$items_container.find(".item-wrapper").click();
		this.set_search_value("");
	}

	resize_selector(minimize) {
		minimize
			? this.$component
					.find(".filter-section")
					.css("grid-template-columns", "repeat(1, minmax(0, 1fr))")
			: this.$component
					.find(".filter-section")
					.css("grid-template-columns", "repeat(12, minmax(0, 1fr))");

		minimize
			? this.$component.find(".search-field").css("margin", "var(--margin-sm) 0px")
			: this.$component.find(".search-field").css("margin", "0px var(--margin-sm)");

		minimize
			? this.$component.css("grid-column", "span 2 / span 2")
			: this.$component.css("grid-column", "span 6 / span 6");

		minimize
			? this.$items_container.css("grid-template-columns", "repeat(1, minmax(0, 1fr))")
			: this.$items_container.css("grid-template-columns", "repeat(4, minmax(0, 1fr))");
	}

	toggle_component(show) {
		this.set_search_value("");
		this.$component.css("display", show ? "flex" : "none");
	}

	async update_filtered_item({ seller=null, price_list=null }) {

		console.log(price_list)
		if(price_list){
			this.price_list = price_list
		}

		if(seller){
			this.seller = seller
		}

		this.filter_items({ 
			search_term: this.search_field.get_value()
		});
	}
};
