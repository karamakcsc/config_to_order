// Shared logic behind any "*_item" child table that carries the configuration_doctype/
// configuration_docname/configuration_result custom fields (Sales Order Item, Quotation Item, ...).
// make_configuration_item_scripts(source_doctype) returns the frappe.ui.form.on() handler object
// for that child doctype; source_doctype is passed through to get_configuration_docname so
// re-config search stays scoped to the right parent transaction.
export function make_configuration_item_scripts(source_doctype){
	source_doctype = source_doctype || 'Sales Order Item';

	return {
		config: function(frm,cdt,cdn){
		    var row = locals[cdt][cdn]
		    var link_field = frm.fields_dict[row.parentfield].grid.grid_rows_by_docname[row.name].grid_form.fields_dict['configuration_docname'];
		    if (!row.configuration_docname){
				const fields = [{
					fieldtype: 'Check',
					fieldname: 'new_config',
					default: 1,
					label: __('New Config'),
					description: __('Uncheck New Config allows re-config base on existing configuration'),
				},
				{
					fieldtype: 'Link',
					fieldname: 'configuration_docname',
					options: row.configuration_doctype,
					depends_on:'eval:!doc.new_config',
					label: __('Existing Config for re-config'),
					description: __('input order number or configuration name to get existing configuration'),
					get_query: function (doc) {
						return {
						query: "config_to_order.api.variant_configuration.get_configuration_docname",
						filters: {configuration_doctype: row.configuration_doctype, source_doctype: source_doctype} };
					}
				}]
				var d = new frappe.ui.Dialog({
					title: __('New Config or Re-config'),
					fields: fields,
					primary_action: function() {
						var data = d.get_values();
						if (data.new_config){
							link_field && link_field.new_doc();
						}
						else{
							if (! data.configuration_docname){
								frappe.msgprint(__('Please select existing configuration for re-config'), __('Missing Value'));
								return
							}
							frappe.model.with_doc(row.configuration_doctype, data.configuration_docname,
								(doc) => {
									var newdoc = frappe.model.copy_doc(locals[row.configuration_doctype][doc]);
									newdoc.idx = null;
									newdoc.__run_link_triggers = false;
									frappe._from_link = link_field
									frappe.set_route('Form', newdoc.doctype, newdoc.name);
								}
							)
						}
					},
					primary_action_label: __('Config')
				});
				d.show();
		    }
		    else{
		        frappe._from_link = link_field
		        link_field && frappe.set_route('Form', link_field.get_options(), link_field.value);
		    }
		},

		configuration_result: function(frm,cdt,cdn){
		    var doc = locals[cdt][cdn];
		    var configuration_result = doc.configuration_result;
		    if (configuration_result){
		        var config_doc = locals["Configuration Result"][configuration_result]
		        var rate = 0;
		        $.each(config_doc.config_items || [], (i, rec) =>{rate += rec.amount});
		        frappe.model.set_value(cdt, cdn, 'rate', rate);
		    }
		},

		config_result: function(frm,cdt,cdn){
			var row = locals[cdt][cdn]
			var link_field = frm.fields_dict[row.parentfield].grid.grid_rows_by_docname[row.name].grid_form.fields_dict['configuration_result'];
			if (!row.configuration_result){
				frappe.db.get_value('BOM', {'item': row.item_code, 'is_default':1},
					'name').then((r) => {
					if(!r.message) {
						frappe.msgprint({
							title: __('No valid Bom'),
							message: __('Please create super BOM for configurable item'),
							indicator: 'orange'
						});
						return;
					} else {
						var default_bom_no = r.message.name;
						frappe.call({
							method: 'config_to_order.api.variant_configuration.get_sub_configuration_requirements',
							args: { bom_no: default_bom_no },
							callback: function(sub_r) {
								show_config_result_dialog(frm, row, link_field, default_bom_no, sub_r.message || []);
							}
						});
					}
				})
			}
			else{
				frappe._from_link = link_field
				link_field && frappe.set_route('Form', link_field.get_options(), link_field.value);
			}
		}
	};
}

// Sub-assembly components (BOM Item.sub_configuration_doctype set) each need their own
// configuration document picked/created before the parent config can be resolved - this
// extends the existing "Select BOM No." dialog with one Link field per such component,
// rather than a fully recursive nested dialog flow (kept deliberately minimal).
var show_config_result_dialog = function(frm, row, link_field, default_bom_no, sub_configuration_requirements){
	const fields = [{
		fieldtype: 'Link',
		fieldname: 'bom_no',
		options: 'BOM',
		default: default_bom_no,
		reqd: 1,
		label: __('Select BOM'),
		get_query: function (doc) {
			return { filters: { item: row.item_code } };
		}
	},
	{
		fieldtype: 'Check',
		fieldname: 'fetch_exploded',
		default: 1,
		label: __('Use Multi Level BOM')
	}];

	if (sub_configuration_requirements.length) {
		fields.push({ fieldtype: 'Section Break', label: __('Sub-assembly Configurations') });
		sub_configuration_requirements.forEach((req) => {
			fields.push({
				fieldtype: 'Link',
				fieldname: 'sub_config__' + req.item_code,
				options: req.sub_configuration_doctype,
				label: __('{0} Configuration', [req.item_code]),
				description: __('Pick or create the {0} configuration for {1}', [req.sub_configuration_doctype, req.item_code]),
			});
		});
	}

	var d = new frappe.ui.Dialog({
		title: __('Select BOM No.'),
		fields: fields,
		primary_action: function() {
			var data = d.get_values();
			var pending_sub_config_updates = sub_configuration_requirements.map((req) => {
				var value = data['sub_config__' + req.item_code];
				if (!value) return Promise.resolve();
				return frappe.db.set_value(row.configuration_doctype, row.configuration_docname,
					req.sub_configuration_docname_field, value);
			});
			Promise.all(pending_sub_config_updates).then(() => {
				frm.call({
					method: 'config_to_order.api.variant_configuration.get_configuration_result',
					args: {
						bom_no: data.bom_no,
						fetch_exploded: data.fetch_exploded,
						configuration_doctype: row.configuration_doctype,
						configuration_docname: row.configuration_docname,
						args: {
							customer: frm.doc.customer || frm.doc.party_name,
							company: frm.doc.company,
							conversion_rate: frm.doc.conversion_rate || 1.0,
							selling_price_list: frm.doc.selling_price_list,
							price_list_currency: frm.doc.price_list_currency,
							plc_conversion_rate: frm.doc.plc_conversion_rate || 1.0,
							doctype: frm.doctype,
							name: frm.docname,
							transaction_date: frm.doc.transaction_date,
							ignore_pricing_rule: frm.doc.ignore_pricing_rule
						}
					},
					freeze: true,
					callback: function(r) {
						if(!r.exc && r.message) {
							frappe._from_link = link_field;
							var dt = 'Configuration Result'
							var dn = frappe.model.make_new_doc_and_get_name(dt);
							frappe.model.set_value(dt,dn,'reference_doctype', row.configuration_doctype);
							frappe.model.set_value(dt,dn,'reference_docname', row.configuration_docname);
							frappe.model.set_value(dt,dn,'bom_no', data.bom_no);
							frappe.model.set_value(dt,dn,'currency', frm.doc.currency);
							var doc = locals[dt][dn]
							var total = 0
							$.each(r.message.config_items || [], (i, record)=>{
								var child = frappe.model.add_child(doc,'Configuration Result Item','config_items');
								$.each(record, (k, v) =>{child[k] = v});
								child.parent = dn;
								total += record.amount;
							})
							frappe.model.set_value(dt,dn,'total', total);
							frappe.set_route("Form", r.message.doctype, dn);
						}
						d.hide();
					}
				});
			});
		},
		primary_action_label: __('Make Configuration Result')
	});
	d.show();
}
