# Writing components

A component is one `.pwc` text file with three sections. The file
`pwct/components/control/while.pwc`:

```
[component]
name: While Loop
category: Control Structures
description: Repeat the steps inside while a condition is true.

[interaction]
title While Loop
text! cond | Condition | True

[template]
<PWCT:NEWSTEP> While <cond>
while <cond>:
```

The key of the component is its path without the extension
(`control/while`). Projects store this key, so do not rename files that
are used by saved projects.

## `[component]`

| key | meaning |
|---|---|
| `name` | shown in the components browser |
| `category` | group in the components browser |
| `description` | help text |
| `position` | `auto` (default), `inside`, `after` or `before`: where the steps go relative to the active step. `Else` uses `after`. |

## `[interaction]` – the interaction page

One line per field: `kind name | label | default | options`

| kind | widget | value |
|---|---|---|
| `text` | one line entry | the text |
| `memo` | multi line text (default may use `\n`) | the text |
| `check` | check box (default `1` or `0`) | `1` / `0` |
| `list` | drop down list, options separated by commas | the chosen option |
| `title` | section title (no name) | – |
| `help` | help text (no name) | – |

Add `!` after the kind (`text!`) for a required field.

## `[template]` – the code

Every line that is not a directive is Python code. `<name>` is replaced
with the value of the field `name`. Filters change the value:

| filter | result for `my name` |
|---|---|
| `<v\|repr>` | `'my name'` (a Python string) |
| `<v\|ident>` | `my_name` (a valid identifier) |
| `<v\|space>` | adds a space at the end when missing |
| `<v\|name>` | the part before `=` or `:` (`age=0` → `age`) |
| `<v\|comment>` | every line starts with `# ` |
| `<v\|upper>`, `lower`, `title`, `strip`, `or_none` | … |

Filters can be chained: `<prompt|space|repr>`.

### Steps

* `<PWCT:NEWSTEP> title` – create a step; the following code lines belong
  to it. Without marks, all steps are created at the insertion point, one
  after the other.
* `<PWCT:PUTMARK> n` – remember the last created step as mark `n` (2‑30).
* `<PWCT:SETMARK> n` – the next steps are created inside mark `n`.
  Mark `1` is the insertion point.
* `<PWCT:INFORMATION> text` – information shown in the Step tab.
* `<PWCT:IMPORT> module` – the step needs `import module` (or a complete
  `from x import y` line); imports are written once at the top of the file.
* `<PWCT:IGNORELAST> c` – remove a trailing `c` from the last code line.
* `<PWCT:TABPUSH>` / `<PWCT:TABPOP>` – indent / unindent the next lines.

The children of a step continue at the indentation where the step's code
ends, one level deeper when it ends with `:`. When a block has nothing to
run, `pass` is generated.

Example with marks (`gui/button.pwc`): the button step holds a
"When clicked" function where the user puts the steps to run:

```
<PWCT:NEWSTEP> Button <var>: <text>
<PWCT:PUTMARK> 2
<PWCT:SETMARK> 2
<PWCT:NEWSTEP> When <var> is clicked
def <var|ident>_click():
<PWCT:SETMARK> 2
<PWCT:NEWSTEP> Create button <var>
<var|ident> = tk.Button(<parent>, text=<text|repr>, command=<var|ident>_click)
```

### Conditions

```
<PWCT:IF> <kind> == Text        (also !=, a single value, or: not <value>)
print(<msg|repr>)
<PWCT:ELSE>
print(<msg>)
<PWCT:ENDIF>
```

A single value is true unless it is empty, `0`, `false`, `no` or `none`.

The original RPWI form is supported too:

```
<PWCT:VALUE> 1
<PWCT:POSITIVE>
<PWCT:TEST> <check_box>
code kept when the check box is 1
<PWCT:ENDTEST>
```

### Repetition

```
<PWCT:FOREACH> a in <attrs>
self.<a|name> = <a|name>
<PWCT:ENDFOREACH>
```

`<PWCT:NOTE> text` is a comment inside the template.
