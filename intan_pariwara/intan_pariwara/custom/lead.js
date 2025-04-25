// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Lead", {
    annual_revenue_dana_bos: function (frm) {
        frm.trigger("annual_revenue_potensi")
    },
    _annual_revenue_dana_bos: function (frm) {
        frm.trigger("annual_revenue_potensi")
    },
    annual_revenue_potensi_dana_siswa: function (frm) {
        frm.trigger("annual_revenue_potensi")
    },
    annual_revenue_potensi: function (frm) {
        var potensi_bos = flt(frm.doc.annual_revenue_dana_bos * frm.doc._annual_revenue_dana_bos / 100)

        frm.set_value("annual_revenue_potensi_bos", potensi_bos)
        frm.set_value("total_annual_revenue_potensi",flt(frm.doc.annual_revenue_potensi_dana_siswa + potensi_bos))
    } 
})