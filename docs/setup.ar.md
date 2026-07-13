# دليل التثبيت والإعداد

يشرح هذا الدليل كيفية تثبيت تطبيق `config_to_order`، ثم يبني معك مثالاً عملياً كاملاً
لصنف قابل للتهيئة من الصفر - وهو نفس مثال "Machine Configuration" المستخدم في مجموعة
الاختبارات الآلية (`config_to_order/tests/test_configuration_constraint.py` و
`test_price_formula.py`)، حتى يروي هذا الدليل ومجموعة الاختبارات نفس القصة.

> **ملاحظة:** أسماء الحقول (fieldnames)، أسماء الأنواع المستندية (DocTypes)، وأسماء
> الأزرار تبقى بالإنجليزية لأنها النصوص الحرفية التي ستراها على الشاشة، حتى لو كانت
> الواجهة بالعربية.

## 1. المتطلبات الأساسية

- بيئة [Frappe bench](https://docs.frappe.io/framework/user/en/bench) جاهزة (أداة
  `bench` مثبّتة، وقد تم تهيئة bench).
- **يجب أن يكون ERPNext مثبتاً مسبقاً على الموقع (site) المستهدف.** تطبيق
  `config_to_order` يقوم بتعديل (monkey-patch) وحدات تحكم BOM و Work Order في
  ERPNext مباشرة (`erpnext.manufacturing.doctype.bom.bom`،
  `erpnext.manufacturing.doctype.work_order.work_order`)، ويرتبط أيضاً بنوع
  المستند `Serial and Batch Bundle` الخاص بـ ERPNext. لن ينجح تثبيته (خطأ استيراد)
  على موقع لا يحتوي إلا على Frappe فقط.

  > **ملاحظة لمن يتولى صيانة تغليف هذا التطبيق مستقبلاً:** لا يُصرَّح باعتمادية
  > ERPNext هذه في أي مكان - لا في `config_to_order/requirements.txt` ولا عبر
  > `required_apps` في `hooks.py` (وهي غائبة أصلاً). أي أن `bench install-app
  > config_to_order` لن يقوم بتثبيت ERPNext تلقائياً نيابة عنك. ثبّت ERPNext يدوياً
  > أولاً، في كل مرة.

- **الإصدار**: تم التطوير والتحقق مقابل **Frappe v15.113.2 / ERPNext v15.114.0**.
  وبشكل خاص، ربط Serial No بـ Configuration Result (انظر قسم "Serial No" في دليل
  المستخدم) يعتمد على إطار عمل `Serial and Batch Bundle` في ERPNext - وهذا هو نموذج
  تتبع الأرقام التسلسلية/الدفعات في الإصدار 15. إذا كنت تستخدم إصداراً أقدم من
  ERPNext ما زال ينشئ Serial No بآلية مختلفة، تحقق أولاً من أن هذا الخطاف (hook) ما
  زال يعمل قبل الاعتماد على تلك الميزة (راجع
  `config_to_order/doc_events/serial_and_batch_bundle.py` لمعرفة ما يتوقعه بالضبط).

## 2. التثبيت

```bash
bench get-app config_to_order https://github.com/karamakcsc/config_to_order.git
bench --site yoursite install-app config_to_order
bench --site yoursite migrate   # يمكن إعادة تشغيله بأمان في أي وقت؛ يعيد مزامنة الـ fixtures أدناه أيضاً
```

## 3. ما يحدث تلقائياً مقابل ما تُعِدُّه يدوياً

**يُثبَّت تلقائياً** - لن تُنشئ أياً من هذه بنفسك:

- الأنواع المستندية `Configuration Result`، `Configuration Result Item`،
  `Configuration Constraint` - هذه تأتي من مجلدات `doctype/` الخاصة بهذا التطبيق
  نفسه، وتُنشأ عبر آلية مزامنة الأنواع المستندية العادية في Frappe التي تعمل عند
  `install-app`/`migrate`، تماماً كما يحدث مع أي أنواع مستندية أخرى تابعة لأي تطبيق.

  > يذكر `hooks.py` أيضاً هذه الأنواع الثلاثة (إضافة إلى `computer` وهو ليس نوعاً
  > مستندياً حقيقياً في هذا التطبيق - يبدو أنه بقايا إعداد من بيئة تطوير المطوّر
  > الأصلي) ضمن قائمة `fixtures` بفلتر `DocType`. هذه القائمة لا تؤثر إلا على
  > **تصدير** بيانات الـ fixtures (`bench export-fixtures`)؛ وليس لها أي دور في
  > تثبيت هذا التطبيق لدى مستخدم آخر، كما أنه لا يوجد ملف `fixtures/doctype.json`
  > في هذا المستودع أصلاً ليُستورد منه. لا تفهم من هذا الإدخال في الـ fixtures أن
  > هذه الأنواع المستندية "تُستورد كـ fixtures" - فهي لا تُستورد كذلك، بل تُزامَن
  > مثل أي نوع مستندي آخر تماماً.

- **الحقول المخصصة (custom fields) على الأنواع المستندية الخاصة بـ ERPNext** - هذه
  فعلاً fixtures حقيقية (`config_to_order/fixtures/custom_field.json`، تُستورد عند
  `install-app`/`migrate`):
  - `Item`: `is_configurable`، `configuration_doctype`.
  - `BOM`: `configuration_doctype` (تُملأ تلقائياً من الصنف الرئيسي).
  - `BOM Item` / `BOM Explosion Item`: `item_from_configuration`،
    `qty_from_configuration`، `desc_from_configuration`، `selection_condition`،
    `price_formula`، `sub_configuration_doctype`، `sub_configuration_docname_field`.
  - `Sales Order Item` / `Quotation Item`: `configuration_doctype`،
    `configuration_docname`، الزر `config`، `configuration_result`،
    الزر `config_result`.
  - `Serial No`: `configuration_result`.

**عليك إعدادها يدوياً، لكل منتج قابل للتهيئة:**

1. **قالب تهيئة (Configuration Template)** - وهو مجرد نوع مستندي مخصص (DocType)
   تُنشئه أنت بنفسك (Frappe Desk -> DocType -> New، وفعّل خيار *Is Custom*). حقوله
   هي أياً كانت الخيارات التي يحتويها منتجك (Select/Data/Link/Check/Float/...).
2. تحديد **الصنف (Item)** كقابل للتهيئة وربطه بالقالب.
3. بناء **الـ Super BOM** مع تفعيل الحقول الخاصة بالتهيئة على كل سطر.
4. (اختياري) إضافة صفوف **Configuration Constraint** لقواعد التحقق.

## 4. مثال عملي: "Machine Configuration"

هذا يعكس تماماً السيناريو الموجود في `tests/test_configuration_constraint.py`.

### 4.1 إنشاء قالب التهيئة (Configuration Template)

Desk -> **DocType** -> New:

| الحقل | القيمة |
|---|---|
| Name | `Machine Configuration` |
| Is Custom | مفعّل |

أضف الحقول التالية:

| Fieldname | Label | النوع | Options |
|---|---|---|---|
| `motor_type` | Motor Type | Select | `3HP\n5HP\n7.5HP` |
| `control_panel_voltage` | Control Panel Voltage | Select | `220V\n380V\n415V` |
| `panel_length` | Panel Length | Float | |

احفظ.

### 4.2 تحديد الصنف كقابل للتهيئة

أنشئ (أو افتح) الصنف الذي يمثل الآلة النهائية القابلة للتهيئة، مثلاً `MACHINE-100`.
في قسم **Variants**:

- فعّل **Is Configurable**.
- اضبط **Configuration DocType** على `Machine Configuration`.

أنشئ أصناف المكونات التي ستستخدمها في الـ BOM كالمعتاد (المحركات، لوحات التحكم،
إلخ) - لا حاجة لأي شيء خاص في هذه الأصناف.

### 4.3 بناء الـ Super BOM

أنشئ BOM جديد، **Item** = `MACHINE-100`. أضف سطراً لكل مكون محتمل. للسطر الذي يجب
أن يظهر فقط لخيار معين، أو يحتاج كمية/وصف مرتبط بالتهيئة، افتح قسم **Configuration**
واملأ الحقل (أو الحقول) المناسبة (كلها اختيارية لكل سطر - انظر دليل المستخدم لمعرفة
وظيفة كل منها):

- `item_from_configuration` / `qty_from_configuration` / `desc_from_configuration`
- `selection_condition`
- `price_formula`
- `sub_configuration_doctype` / `sub_configuration_docname_field`

اترك جميع هذه الحقول فارغة في سطر معين لجعل ذلك المكوّن إلزامياً في كل عملية بناء.

احفظ و**Submit** الـ BOM، وحدّده كـ **Is Default** للصنف (عملية استخراج
Configuration Result تبحث عن الـ BOM الافتراضي للصنف).

### 4.4 إضافة قواعد Configuration Constraint (اختياري)

أنشئ **Configuration Constraint** جديد:

- **Configuration Doctype**: `Machine Configuration`
- **Constraint Type**: `Requires`
- **If Field**: `motor_type`، **If Operator**: `=`، **If Value**: `5HP`
- **Then Field**: `control_panel_voltage`، **Then Operator**: `in`،
  **Then Value**: `380V,415V`
- **Message**: `A 5HP motor requires a 380V or 415V control panel.`

وقاعدة Range:

- **Constraint Type**: `Range`
- **Range Field**: `panel_length`، **Min Value**: `50`، **Max Value**: `200`

احفظ كلتا القاعدتين. من الآن فصاعداً، أي محاولة لحفظ مستند `Machine Configuration`
يخالف أياً من القاعدتين سترفض مع رسالتك.

### 4.5 جرّب الأمر

اتبع مسار **Sales Order Item** الموضح في دليل المستخدم (`docs/user-guide.ar.md`):
أضف `MACHINE-100` إلى Sales Order، اضغط **Config**، املأ `motor_type = 5HP` /
`control_panel_voltage = 220V` واحفظ - يجب أن تُرفض العملية. صحّح القيمة إلى `380V`
أو `415V` فتُحفظ بنجاح. اضغط **Config Result** لاستخراج مكونات الـ BOM مسعّرة.

## 5. أخطاء إعداد شائعة

- **حدّد الصنف كقابل للتهيئة *قبل* بناء الـ BOM.** حقل `BOM.configuration_doctype`
  يُملأ تلقائياً من `Item.configuration_doctype` الخاص بصنف رأس الـ BOM
  (`config_to_order.doc_events.bom.validate` يتحقق من
  `item_from_configuration`/`qty_from_configuration`/`desc_from_configuration`/
  `selection_condition` مقابل حقول قالب التهيئة **فقط عندما يكون
  `configuration_doctype` مضبوطاً** - انظر `config_to_order/doc_events/bom.py`).
  إذا بنيت الـ BOM قبل تحديد الصنف كقابل للتهيئة، يُتخطى هذا التحقق بصمت: أي خطأ
  إملائي في هذه الحقول سيُحفظ دون رسالة خطأ، ثم يفشل بصمت في التهيئة عند إنشاء
  الطلب بدلاً من أن يفشل بوضوح فوراً.

- **أنواع حقول سطر الـ BOM لا يُتحقق منها، فقط وجودها.** خطاف التحقق في BOM يؤكد أن
  `item_from_configuration` وما شابهها تشير إلى حقل *حقيقي* في قالب التهيئة، لكن
  دون التأكد من أنه *النوع الصحيح* من الحقول. قائمة الاختيار في واجهة desk
  (`public/js/scripts/bom.js`) تعرض فقط حقول Data/Select/Link لـ
  `item_from_configuration`/`desc_from_configuration` وحقول Int/Float لـ
  `qty_from_configuration` - لكن إذا كتبت اسم حقل مباشرة، لا شيء يمنعك من توجيه
  `qty_from_configuration` نحو حقل Select. سيمر التحقق بنجاح ثم ينتج كميات خاطئة.
  التزم بقائمة الاختيار المنسدلة.

- **"Please create super BOM for configurable item."** عملية Configuration Result
  تبحث عن الـ BOM *الافتراضي* للصنف (محدد كـ `is_default` ومُقدَّم/submitted).
  تأكد من أن BOM واحداً فقط للصنف محدد كافتراضي.

- **رسالة Configuration Constraint تقول إن حقلاً "ليس حقلاً صالحاً في قالب التهيئة
  X".** هذا الخطأ *يُلتقط* فعلاً عند الحفظ (`configuration_constraint.py` في دالة
  `validate_referenced_fields`) - يعني وجود خطأ إملائي في
  `if_field`/`then_field`/`range_field` (أو أنك تعدّل `configuration_doctype`
  خطأً في Configuration Constraint غير الصحيح). صحّح اسم الحقل واحفظ مرة أخرى.

- **مكوّن التجميع الفرعي (sub-assembly) يُحل بصمت كصنف عادي، متجاهلاً الـ BOM
  الخاص به.** هذا سلوك مقصود وليس خللاً: إذا كان `sub_configuration_docname_field`
  مضبوطاً لكن مستند التهيئة الأصل لا يحتوي على قيمة في ذلك الحقل بعد (أو لا يوجد
  BOM افتراضي لصنف التجميع الفرعي)، فإن `get_configuration_result` يعود إلى معاملة
  السطر كمكوّن عادي مسطّح بدلاً من إظهار خطأ
  (`api/variant_configuration.py` في دالة `resolve_sub_configuration`). تحقق من أن
  ذلك الحقل مملوء فعلاً في مستند التهيئة الأصل إذا كنت تتوقع تداخلاً (nesting).
