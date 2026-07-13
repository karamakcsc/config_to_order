export default {
	onload: function(frm) {
		set_field_queries(frm);
	},
	configuration_doctype: function(frm) {
		set_field_queries(frm);
	}
}

var set_field_queries = function(frm){
	frm.set_query("if_field", () => set_query(frm, ['Data','Select','Link','Check','Int','Float']));
	frm.set_query("then_field", () => set_query(frm, ['Data','Select','Link','Check','Int','Float']));
	frm.set_query("range_field", () => set_query(frm, ['Int','Float']));
}

var set_query = function(frm, field_types){
	return {
		query: "config_to_order.api.variant_configuration.get_configuration_fields",
		filters: {
			configuration_doctype: frm.doc.configuration_doctype,
			field_types: field_types
		}
	}
}
