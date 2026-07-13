## Config To Order

An ERPNext app for SAP-style variant configuration: a "Configuration Template" is any
custom doctype you create; a configurable Item's Super BOM references that template's
fields to decide which components go into an order, in what quantity, and at what price.

Original discussion / background: https://discuss.erpnext.com/t/new-feature-config-to-order-erpnext-version-of-saps-variant-configuration-need-community-feedback/55621

### Install

```
bench get-app config_to_order https://github.com/karamakcsc/config_to_order.git
bench --site yoursite install-app config_to_order
```

### Core flow: configurable item -> Super BOM -> order line -> Configuration Result

1. **Configuration Template**: create a new DocType (custom checkbox on), with whatever
   fields describe the choices a customer makes (Select/Data/Link/Check/Float/...).

2. **Configurable Item**: on the Item's Variants section, check *Is Configurable* and set
   *Configuration DocType* to the template from step 1.

3. **Other items**: create the components that make up the configurable item's BOM as usual.

4. **Super BOM**: create a BOM with the configurable item as the header item, and one row
   per possible component. Each BOM Item / BOM Explosion Item row has a Configuration
   section with:
   - `item_from_configuration` / `qty_from_configuration` / `desc_from_configuration` -
     each names a field on the Configuration Template; at resolution time its value is
     read off the actual configuration document. Leave both `item_from_configuration`
     and `selection_condition` blank to make a row mandatory in every configuration.
   - `selection_condition` - a Python expression (`doc` is the configuration document,
     e.g. `doc.harddisk == 'samsung'`) deciding whether this row is included at all.
   - `sub_configuration_doctype` / `sub_configuration_docname_field`, `price_formula` -
     see Nested configuration and Price formulas below.

5. **Sales Order Item / Quotation Item**: once the line item is a configurable item, a
   Configuration section appears with **Config** and **Config Result** buttons.
   - **Config**: create a new configuration document, or re-config from an existing one
     (searched by order number or configuration name).
   - **Config Result**: pick the Super BOM (and whether to explode multi-level BOMs);
     this resolves the configuration into a **Configuration Result** (one row per
     included component, priced), which you can review/adjust before saving. Its total
     is copied back to the order line's rate.
   - Once the order is placed, a Work Order created against the Super BOM only pulls in
     the components relevant to that specific configuration (via the same resolution
     logic, `config_to_order.utils.check_selection_condition` /
     `get_qty_or_desc` / `get_bom_items_as_dict`, shared between the Sales Order flow
     and `WorkOrder.set_required_items`).

### Configuration Constraint - validation rules without writing code

A **Configuration Constraint** record attaches a validation rule to a Configuration
Template (`configuration_doctype`) without needing a custom `validate` hook for every
template. Four kinds:

- **Requires**: if `if_field if_operator if_value` is true, `then_field then_operator
  then_value` must also be true (e.g. `motor_type = 5HP` requires
  `control_panel_voltage in 380V,415V`).
- **Excludes**: if the "if" side is true, the "then" side must be false.
- **Range**: `range_field` must fall within `[min_value, max_value]` (either bound may
  be left blank for an open range).
- **Expression**: an arbitrary Python expression (`doc` is the configuration document),
  for anything the structured forms can't express.

Operators for Requires/Excludes: `= != > >= < <= in "not in"` (`in`/`not in` compare
against a comma-separated list). Set a `message` for a clear error on violation, or
leave it blank for a generic one. Uncheck `is_active` to disable a rule without
deleting it.

This is wired in generically via `doc_events["*"]`, so it applies to *any* doctype you
attach constraints to (not just Configuration Templates) - guarded by a cheap, indexed
`frappe.db.exists()` check so doctypes with no constraints pay effectively nothing on
save. See `config_to_order/doc_events/configuration.py`.

### Nested / sub-assembly configuration

A BOM component can itself be a configurable sub-assembly with its own Super BOM and
its own Configuration Template - e.g. a "Machine" whose BOM includes a "Control Panel"
that is separately configured. On that BOM row, set:

- `sub_configuration_doctype`: the sub-assembly's own Configuration Template doctype.
- `sub_configuration_docname_field`: the field *on the parent* Configuration Template
  that holds the sub-assembly's own configuration document name.

When resolving the parent, `get_configuration_result` recurses: it looks up the
sub-assembly item's own default Super BOM, resolves it the same way (selection
conditions, qty/desc overrides, price formulas, further nesting - all of it), and rolls
the nested total up into the parent row's rate/amount instead of a flat item price
lookup. The nested Configuration Result is a real, saved document
(`parent_configuration_result` links it back to its parent; the parent row's
`nested_configuration_result` links down to it) so you can open and review it directly.
If a sub-assembly's configuration document isn't set yet (or no default BOM exists for
it), that component just falls back to being treated as an ordinary flat item rather
than erroring.

In the Sales Order/Quotation Item's "Config Result" dialog, any component needing a
sub-configuration shows as an extra field to pick or create one, before "Make
Configuration Result" resolves everything.

### Price formulas

Set `price_formula` on a BOM row to price it by a Python expression instead of the
item's list price - `doc` is the configuration document, `qty` is the row's resolved
quantity (e.g. a custom-cut panel: `doc.length * doc.width * 10`). Leave it blank to
keep the normal item-price lookup. The formula's result is the row's per-unit rate;
`amount` is still `rate * qty`.

### Quotation support

Quotation Item carries the same Configuration/Config Result fields and buttons as
Sales Order Item (`config_to_order.public.js.scripts.configuration_item` is the shared
implementation both wrap). `get_configuration_docname`'s re-config search takes an
optional `source_doctype` filter (defaulting to `"Sales Order Item"` for existing
callers) so it can search Quotation Items too, or any other future `*_item` doctype
with the same custom fields - it resolves the parent doctype generically via the Table
docfield linking them, not a hardcoded map.

### Configuration snapshot & Serial No tracking

Every Configuration Result stores a `configuration_snapshot` - a JSON dump of the
source configuration document's field values at the moment it was resolved - so
editing a Configuration Template's fields later doesn't retroactively reinterpret
configurations that were already turned into orders.

For serialized items, once a Work Order's Manufacture Stock Entry generates Serial Nos,
each one gets its `configuration_result` field set to the Configuration Result that
drove the build (traced through Stock Entry -> Work Order -> Sales Order Item). This
hooks `doc_events["Serial and Batch Bundle"]["on_submit"]` rather than Serial No
directly - ERPNext creates manufactured Serial Nos via a raw bulk insert, so no Serial
No document hooks ever fire for them; the Serial and Batch Bundle *is* saved normally,
so that's the reliable integration point (`config_to_order/doc_events/serial_and_batch_bundle.py`).

### Whitelisted API (`config_to_order.api.variant_configuration`)

- `get_configuration_result(bom_no, fetch_exploded, configuration_doctype, configuration_docname, args)`
  - `args` may be a dict or a JSON string (JS calls send it serialized).
- `get_configuration_fields(doctype, txt, searchfield, start, page_len, filters)` -
  powers the smart field-picker dropdowns (`filters.field_types` restricts by fieldtype).
- `get_configuration_docname(doctype, txt, searchfield, start, page_len, filters)` -
  re-config search; `filters.source_doctype` defaults to `"Sales Order Item"`.
- `get_sub_configuration_requirements(bom_no)` - BOM rows needing a sub-configuration.

None of these signatures have changed in a way that breaks existing callers - new
behavior is opt-in via new fields/filters with backward-compatible defaults.

### Tests

`bench --site yoursite run-tests --app config_to_order` (requires
`bench --site yoursite set-config allow_tests true`). Coverage lives under
`config_to_order/tests/`, one file per feature area.

#### License

MIT
