# PWCT-Python

A visual programming environment written in Python and inspired by
**PWCT – Programming Without Coding Technology** (Mahmoud Fayed, 2006‑2010).
You build a program as a tree of steps by filling small forms
(*interaction pages*); PWCT-Python generates the Python code, shows it and
runs it.

![PWCT-Python Goal Designer](docs/screenshot.png)

The windows follow the forms of the original PWCT, with the same layout
and colours: the main window with the standard toolbar and the vertical
**Designers** bar (`DoubleS.scx`, `mytool.vcx`), the **Goal Designer**
(`rpwi.scx`), the **Select Component** browser (`selser.scx`), the
**Interaction Using Transporter** page (`runtrf.scx`), the pages made by
the **Interaction Pages Generator** (`ipwriter.scx`), the **Transporter
Designer** (`transd.scx`), the **Interaction Designer** (`interd.scx`) and
the **Welcome** window (`welcome.scx`).

| Select Component | Interaction page |
|---|---|
| ![Components browser](docs/components_browser.png) | ![Interaction page](docs/interaction.png) |

### Component Designer

Make your own components without writing Python code for the environment:

| Interaction Designer | Transporter Designer (Code Mask) |
|---|---|
| ![Interaction Designer](docs/interaction_designer.png) | ![Transporter Designer](docs/transporter_designer.png) |

* **Interaction Designer**: add controls with the toolbox buttons named
  after the PWCT script commands (TITLE, SMALLGET, LARGEGET, LISTBOX,
  CHECKBOX, ENTER, PAGE ...), edit their properties (variable, caption,
  default value, list items, required) and see the page live.
* **Transporter Designer**: *Component* (name, file, domain - the
  "Install Component" page), *Interaction Pages*, *Code Mask* (the template
  with directive buttons, syntax colours and a syntax window), *Matching*
  (page variables against code mask variables) and *Test* (the steps and
  the Python code the component makes, then "Add to Goal Designer").
* **Install / Uninstall**: an installed component goes to
  `~/.pwct-python/components` (or `$PWCT_HOME/components`) and appears in
  the components browser at once. Installing a component with the file
  name of a built-in one replaces it; Uninstall gives the built-in one back.
* **Import from PWCT 1.x**: open a `TRF` file of the original PWCT (with
  its `IDF` page and the `PAF` tree next to it): the interaction page, the
  code mask and the domain are converted, so the 417 components of the
  original can be opened, studied and ported to Python.
  From the command line: `python -m pwct import-trf TRF10.TRF -o image.pwc`.

## بالعربية

**PWCT-Python** بيئة برمجة مرئية مكتوبة بلغة بايثون، مبنية على فكرة برنامج
PWCT (البرمجة بدون كتابة كود). بدل كتابة الكود:

1. تختار خطوة في **مصمم الأهداف** (Goal Designer)، وفي البداية توجد خطوة "Start Here" فقط.
2. تضغط **Interact** (أو Ctrl+Space) فتظهر نافذة **Select Component**: المجالات على اليسار والمكونات على اليمين (طباعة، إدخال، شرط، حلقة، دالة، صنف، نافذة رسومية...).
3. تملأ **صفحة التفاعل** (Interaction Page) وتضغط OK، فتُضاف خطوات جديدة للشجرة.
4. تُولَّد شيفرة بايثون تلقائياً ويمكنك تشغيلها بـ F5 ومشاهدة المخرجات وإدخال البيانات.
5. للتعديل: اختر الخطوة واضغط **Modify** (أو انقر عليها مرتين) فتُفتح صفحة التفاعل من جديد، وتبقى الخطوات التي أضفتها داخلها كما هي.
6. عند حدوث خطأ أثناء التشغيل يتم تحديد الخطوة المسؤولة عنه في الشجرة.

**مصمم المكونات (Component Designer)**: من الشريط العمودي على اليسار
(Goal / Transporter / Interaction) كما في PWCT الأصلي:

* **Interaction** – مصمم صفحات التفاعل: أزرار بأسماء أوامر PWCT
  (TITLE, SMALLGET, LARGEGET, LISTBOX, CHECKBOX, ENTER, PAGE) لإضافة
  العناصر، مع خصائص كل عنصر (المتغير، العنوان، القيمة الافتراضية، عناصر
  القائمة) ومعاينة مباشرة للصفحة.
* **Transporter** – مصمم الناقل: بيانات المكوّن (الاسم، الملف، المجال)،
  صفحات التفاعل، **Code Mask** (قالب الكود مع أزرار أوامر RPWI وتلوين)،
  **Matching** (مطابقة متغيرات الصفحة مع متغيرات القالب) و **Test** (تجربة
  المكوّن ورؤية الخطوات والكود ثم إضافته لمصمم الأهداف).
* **Install** يحفظ المكوّن في `~/.pwct-python/components` فيظهر فوراً في
  نافذة اختيار المكونات، و **Uninstall** يحذفه.
* **Import PWCT 1.x (TRF)** يفتح مكوّنات PWCT الأصلي (ملفات TRF + IDF + PAF)
  ويحوّلها إلى صيغة PWCT-Python لتعديلها إلى بايثون.

التشغيل:

```bash
python -m pwct                                    # فتح البيئة المرئية
python -m pwct pwct/samples/guess_number.pwct     # فتح مثال
python -m pwct run pwct/samples/hello_world.pwct  # تشغيل مشروع من سطر الأوامر
python -m pwct build project.pwct -o program.py   # حفظ الكود المولَّد
```

لا يحتاج أي مكتبات خارجية، فقط بايثون 3.8+ مع Tkinter
(على أوبونتو: `sudo apt install python3-tk`).

## How it maps to the original PWCT

The original source (Visual FoxPro IDE `RPWI` + Harbour libraries) keeps
every component in several DBF tables. PWCT-Python keeps the same ideas in
plain text:

| Original PWCT | PWCT-Python |
|---|---|
| Goal Designer (steps tree, `T38` table) | `pwct/engine/project.py` – `Project`, `Step` |
| Interaction pages (`IDF` / `ISF` files) | `[interaction]` section of a `.pwc` file, shown by `pwct/gui/interaction.py` |
| Transporter + template (`TRF`, field `F_MASK`) | `[template]` section of a `.pwc` file |
| Interaction Designer, Interaction Pages Generator, Transporter Designer, Install Component | `pwct/gui/designer.py` |
| DBF / FPT tables of PWCT 1.x | `pwct/engine/legacy.py` (reader and importer, no dependency) |
| Components tree (`MAHMOUD.PAF`) | folders of `pwct/components/`, `category:` field |
| `<RPWI:NEWSTEP>`, `PUTMARK`, `SETMARK`, `TEST`/`VALUE`/`POSITIVE`/`NEGATIVE`, `INFORMATION`, `IGNORELAST`, `TABPUSH`/`TABPOP` | same directives, `pwct/engine/template.py` (both `<RPWI:…>` and `<PWCT:…>` spellings) |
| Editing an interaction regenerates its steps, user sub-steps are kept | `Project.edit` |
| Code generation from the tree (Harbour / xBase) | `pwct/engine/generator.py` (Python, indentation from the tree) |

`<RPWI:NEWVAR>`, `SETVARVALUE`, `SELECTVAR` and `REPLACEVARSWITHVALUES`
(variables computed in the template) and the `<*>` comment lines work as
in the original.

New in this version: `<PWCT:IF>/<PWCT:ELSE>/<PWCT:ENDIF>`, `<PWCT:FOREACH>`,
`<PWCT:IMPORT>` (imports collected at the top of the file) and placeholder
filters such as `<name|repr>` and `<name|ident>`.

## Features

* Goal Designer like PWCT: New Step, Delete Step, Edit Step, move up / down,
  Interact, Modify, "Ignore (Disable) Step", and the Steps Tree / Step
  Details / Source Code / Output views.
* Steps: add, modify (re-open the interaction), rename, delete,
  cut / copy / paste, move up / down / in / out, drag and drop,
  enable / disable (a disabled step is written as a comment), comments,
  unlimited undo / redo.
* 47 components in 12 categories: console, variables, lists & dictionaries,
  control structures (if / elif / else, for, while, try, break…), functions,
  classes & objects, modules, files, date & time, math, GUI (Tkinter) and
  free Python code.
* Code view synchronised with the tree (click a line to find its step).
* Run inside the environment with an input box; runtime errors select
  the step that caused them.
* Projects are JSON files (`.pwct`); the code can be exported as `.py`.
* Make your own components with the Component Designer, or write `.pwc`
  files by hand (see [docs/components.md](docs/components.md)); extra
  folders can be listed in the `PWCT_COMPONENTS` environment variable.

## Project layout

```
pwct/
  engine/        template language, components, steps tree, code generator,
                 PWCT 1.x importer (no GUI)
  gui/           Tkinter environment, designers, interaction pages, program runner
  components/    the component library (.pwc files)
  samples/       example projects
tests/           unit tests (python -m unittest discover -s tests)
tools/           make_samples.py builds the samples with the engine API
```

## Using the engine from Python

```python
from pwct.engine import Library, Project, generate

lib = Library.default()
p = Project("Demo")
loop = p.apply(lib["control/for_range"], {"var": "i", "start": "1", "end": "3"})
p.apply(lib["console/print"], {"msg": "i", "kind": "Expression"}, parent=loop)
print(generate(p)[0])
```

## Tests

```bash
python -m unittest discover -s tests
xvfb-run python -m unittest tests.test_gui    # GUI tests on a server without a display
```

## Credits

The concepts (Goal Designer, interaction pages, components, RPWI template
directives) come from PWCT by Mahmoud Samir Fayed
(http://doublesvsoop.sourceforge.net). This is an independent re-creation
in Python; no code of the original is used.
