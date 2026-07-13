# Setup Guide

This guide gets `config_to_order` installed and walks through building one working
configurable item from zero, using the same "Machine Configuration" example the
automated test suite uses (`config_to_order/tests/test_configuration_constraint.py`
and `test_price_formula.py`), so this guide and the tests describe the same thing.

## 1. Prerequisites

- A working [Frappe bench](https://docs.frappe.io/framework/user/en/bench) (`bench`
  CLI installed, a bench initialized).
- **ERPNext must already be installed on the target site.** `config_to_order`
  monkey-patches ERPNext's BOM and Work Order controllers directly
  (`erpnext.manufacturing.doctype.bom.bom`, `erpnext.manufacturing.doctype.work_order.work_order`)
  and hooks into ERPNext's `Serial and Batch Bundle` doctype. It will fail to install
  (import error) on a site that only has Frappe.

  > **Note for whoever maintains this app's packaging:** neither
  > `config_to_order/requirements.txt` nor `hooks.py`'s (absent) `required_apps`
  > declares this ERPNext dependency anywhere - `bench install-app config_to_order`
  > will not install ERPNext for you automatically. Install ERPNext first, by hand,
  > every time.

- **Version**: developed and verified against **Frappe v15.113.2 / ERPNext
  v15.114.0**. In particular, the Serial No <-> Configuration Result linkage (see
  the user guide's "Serial No" section) depends on ERPNext's `Serial and Batch
  Bundle` framework firing a normal `on_submit` doc event - this is the v15
  serial/batch tracking model. If you're on an older ERPNext version that still
  creates Serial Nos through a different mechanism, verify that hook still fires
  before relying on that feature (see `config_to_order/doc_events/serial_and_batch_bundle.py`
  for exactly what it expects).

## 2. Install

```bash
bench get-app config_to_order https://github.com/karamakcsc/config_to_order.git
bench --site yoursite install-app config_to_order
bench --site yoursite migrate   # safe to re-run any time; also re-syncs fixtures below
```

## 3. What's automatic vs. what you configure by hand

**Installed automatically** - you don't create any of these yourself:

- DocTypes `Configuration Result`, `Configuration Result Item`, `Configuration
  Constraint` - these come from this app's own `doctype/` folders and are created by
  the normal Frappe doctype sync that runs on `install-app`/`migrate`, the same way
  any app's own doctypes are.

  > `hooks.py` also lists these three (plus a stray `computer`, which isn't a real
  > doctype in this app - looks like leftover config from the original author's own
  > dev site) under `fixtures` with a `DocType` filter. That list only matters for
  > **exporting** fixture data (`bench export-fixtures`); it plays no role in
  > installing this app for someone else, and there's no `fixtures/doctype.json`
  > shipped in this repo for it to import from anyway. Don't read that fixtures
  > entry as "these doctypes get fixture-imported" - they don't, they're just synced
  > like any other doctype.

- **Custom fields on ERPNext's own doctypes** - these genuinely are fixtures
  (`config_to_order/fixtures/custom_field.json`, imported on `install-app`/`migrate`):
  - `Item`: `is_configurable`, `configuration_doctype`.
  - `BOM`: `configuration_doctype` (auto-filled from the header item).
  - `BOM Item` / `BOM Explosion Item`: `item_from_configuration`,
    `qty_from_configuration`, `desc_from_configuration`, `selection_condition`,
    `price_formula`, `sub_configuration_doctype`, `sub_configuration_docname_field`.
  - `Sales Order Item` / `Quotation Item`: `configuration_doctype`,
    `configuration_docname`, `config` (button), `configuration_result`,
    `config_result` (button).
  - `Serial No`: `configuration_result`.

**You configure by hand, per configurable product:**

1. A **Configuration Template** - a plain custom DocType you create yourself
   (Frappe Desk -> DocType -> New, tick *Is Custom*). Its fields are whatever
   choices your product has (Select/Data/Link/Check/Float/...).
2. Mark the **Item** as configurable and link the template.
3. Build the **Super BOM** with the configuration-aware fields on each row.
4. (Optional) Add **Configuration Constraint** rows for validation rules.

## 4. Worked example: "Machine Configuration"

This mirrors the scenario in `tests/test_configuration_constraint.py` end to end.

### 4.1 Create the Configuration Template

Desk -> **DocType** -> New:

| Field | Value |
|---|---|
| Name | `Machine Configuration` |
| Is Custom | checked |

Add fields:

| Fieldname | Label | Type | Options |
|---|---|---|---|
| `motor_type` | Motor Type | Select | `3HP\n5HP\n7.5HP` |
| `control_panel_voltage` | Control Panel Voltage | Select | `220V\n380V\n415V` |
| `panel_length` | Panel Length | Float | |

Save.

### 4.2 Mark the item as configurable

Create (or open) the Item that represents the finished, configurable machine, e.g.
`MACHINE-100`. On the **Variants** section:

- Check **Is Configurable**.
- Set **Configuration DocType** to `Machine Configuration`.

Create the component items you'll reference from the BOM as usual (motors, control
panels, etc.) - nothing special needed on those.

### 4.3 Build the Super BOM

New BOM, **Item** = `MACHINE-100`. Add one row per possible component. For a row that
should only appear for a specific choice, or that needs a quantity/description driven
by the configuration, expand its **Configuration** section and fill in the relevant
field(s) (all optional per row - see the user guide for what each one does):

- `item_from_configuration` / `qty_from_configuration` / `desc_from_configuration`
- `selection_condition`
- `price_formula`
- `sub_configuration_doctype` / `sub_configuration_docname_field`

Leave all of these blank on a row to make that component mandatory in every build.

Save and **Submit** the BOM, and mark it **Is Default** for the item (Configuration
Result resolution looks up the item's default BOM).

### 4.4 Add Configuration Constraint rules (optional)

New **Configuration Constraint**:

- **Configuration Doctype**: `Machine Configuration`
- **Constraint Type**: `Requires`
- **If Field**: `motor_type`, **If Operator**: `=`, **If Value**: `5HP`
- **Then Field**: `control_panel_voltage`, **Then Operator**: `in`, **Then Value**: `380V,415V`
- **Message**: `A 5HP motor requires a 380V or 415V control panel.`

And a Range rule:

- **Constraint Type**: `Range`
- **Range Field**: `panel_length`, **Min Value**: `50`, **Max Value**: `200`

Save both. From here on, saving any `Machine Configuration` document that violates
either rule is rejected with your message.

### 4.5 Try it

Follow the **Sales Order Item** flow in the user guide (`docs/user-guide.md`): add
`MACHINE-100` to a Sales Order, click **Config**, fill in `motor_type = 5HP` /
`control_panel_voltage = 220V` and save - it should be rejected. Fix it to `380V` or
`415V` and it saves. Click **Config Result** to resolve the BOM into priced line
items.

## 5. Common setup mistakes

- **Mark the Item configurable *before* building the BOM.** `BOM.configuration_doctype`
  is fetched from the header item's `Item.configuration_doctype`
  (`config_to_order.doc_events.bom.validate` only checks
  `item_from_configuration`/`qty_from_configuration`/`desc_from_configuration`/
  `selection_condition` against the configuration doctype's fields **when
  `configuration_doctype` is set** - see `config_to_order/doc_events/bom.py`). Build the
  BOM before marking the item configurable, and this validation is silently skipped:
  typos in those fields will save without error, then silently resolve to nothing at
  order time instead of failing loudly.

- **BOM row field types aren't cross-checked, only existence is.** The BOM validate
  hook confirms `item_from_configuration` etc. name a *real* field on the
  configuration doctype, but not that it's the *right kind* of field. The desk UI's
  dropdown (`public/js/scripts/bom.js`) only offers Data/Select/Link fields for
  `item_from_configuration`/`desc_from_configuration` and Int/Float fields for
  `qty_from_configuration` - but if you type a fieldname directly, nothing stops you
  pointing `qty_from_configuration` at a Select field. It'll pass validation and then
  produce wrong quantities. Stick to the dropdown.

- **"Please create super BOM for configurable item."** The Configuration Result flow
  looks up the item's *default* BOM (`is_default` checked, submitted). Make sure
  exactly one BOM for the item is marked default.

- **Configuration Constraint says a field "is not a valid field in configuration
  doctype X."** This one *is* caught for you at save time
  (`configuration_constraint.py`'s `validate_referenced_fields`) - it means a typo in
  `if_field`/`then_field`/`range_field` (or you're editing the wrong Configuration
  Constraint's `configuration_doctype`). Fix the field name and save again.

- **A sub-assembly component silently resolves as a plain item, ignoring its own
  BOM.** This is intentional, not a bug: if `sub_configuration_docname_field` is set
  but the parent configuration document doesn't have that field filled in yet (or the
  sub-assembly item has no default BOM), `get_configuration_result` falls back to
  treating the row as an ordinary flat component rather than erroring
  (`api/variant_configuration.py`'s `resolve_sub_configuration`). Check that field is
  actually populated on the parent configuration document if you expected nesting.
