# Instructions for AI Agents

This file gives specific instructions for AI agents that perform
housekeeping tasks for Git l10n. Use of AI is optional; many successful
l10n teams work well without it.

The section "Housekeeping tasks for localization workflows" documents the
most commonly used housekeeping tasks:

1. Generating or updating po/git.pot
2. Updating po/XX.po
3. Translating po/XX.po


## Background knowledge for localization workflows

Essential background for the workflows below; understand these concepts before
performing any housekeeping tasks in this document.

### Language code and notation (XX, ll, ll\_CC)

XX is a placeholder for the language code. The code is either `ll` (ISO 639)
or `ll_CC` (e.g. `de`, `zh_CN` for Simplified Chinese). It appears in the PO
file's header entry metadata (e.g. `"Language: zh_CN\n"`) and is typically used
as the filename: `po/XX.po`.


### Header Entry

Every PO file (`po/XX.po`) contains a special entry called the "header entry"
at the beginning of the file. This entry has an empty `msgid` and contains
metadata about the translation in its `msgstr`:

```po
msgid ""
msgstr ""
"Project-Id-Version: Git\n"
"Report-Msgid-Bugs-To: Git Mailing List <git@vger.kernel.org>\n"
"POT-Creation-Date: 2026-02-14 13:38+0800\n"
"PO-Revision-Date: 2026-02-14 11:41+0800\n"
"Last-Translator: Teng Long <dyroneteng@gmail.com>\n"
"Language-Team: GitHub <https://github.com/dyrone/git/>\n"
"Language: zh_CN\n"
"MIME-Version: 1.0\n"
"Content-Type: text/plain; charset=UTF-8\n"
"Content-Transfer-Encoding: 8bit\n"
"Plural-Forms: nplurals=2; plural=(n != 1);\n"
"X-Generator: Gtranslator 42.0\n"
```

**CRITICAL**: Do not modify the header's `msgstr` during translation. Extracted
files (e.g. `po/l10n-pending.po`) include this header; preserve it exactly.

The header provides: translation metadata (translator, language, dates);
pluralization rules (`Plural-Forms`); encoding and MIME type; project/version.


### Glossary Section

PO files may have a glossary in comments before the header entry (first
`msgid ""`), giving terminology guidelines:

```po
# Git glossary for Chinese translators
#
#   English                          |  Chinese
#   ---------------------------------+--------------------------------------
#   3-way merge                      |  三路合并
#   branch                           |  分支
#   commit                           |  提交
#   ...
```

**IMPORTANT**: Read and use the glossary when translating or reviewing. It is
in `#` comments and is preserved when extracting with `msgattrib`.


### Single-line vs Multi-line Entries

**Single-line entries**:

```po
msgid "commit message"
msgstr "提交说明"
```

**Multi-line entries** (the first line of both `msgid` and `msgstr` is an empty
string):

```po
msgid ""
"Line 1\n"
"Line 2"
msgstr ""
"行 1\n"
"行 2"
```

**CRITICAL** for multi-line: the first line is `msgid ""` / `msgstr ""`; the
following lines are quoted strings; use `\n` for line breaks. Preserve quotes
and structure exactly.

Because multi-line entries also use `msgstr ""` on the first line, `grep
'^msgstr ""'` yields false positives when locating untranslated strings. See
the next section for the correct approach.


### Locating untranslated, fuzzy, and obsolete entries

**The commands below are used in "Task 3: translating po/XX.po".** For
translation tasks, follow Task 3 steps strictly; do not run these commands in
isolation.

This section describes how to locate untranslated, fuzzy, and obsolete entries.
Do **not** use `grep '^msgstr ""$'`—it matches multi-line entries and causes
false positives. Use `msgattrib`:

- **Untranslated**: `msgattrib --untranslated --no-obsolete po/XX.po`
- **Fuzzy**: `msgattrib --only-fuzzy --no-obsolete po/XX.po`
- **Obsolete** (`#~`): `msgattrib --obsolete --no-wrap po/XX.po`

To get only message IDs:
`msgattrib --untranslated --no-obsolete po/XX.po | sed -n '/^msgid /,/^$/p'`
(Same pattern for fuzzy with `--only-fuzzy`.)

When counting entries, the header is included; subtract 1 to exclude it.


### Translating fuzzy entries

Fuzzy entries need re-translation because the source text changed. The format
differs by file type:

- **PO file**: A `#, fuzzy` tag in the entry comments marks the entry as fuzzy.
- **JSON file**: The entry has `"fuzzy": true`.

**Translation principles**: Re-translate the `msgstr` (and, for plural entries,
`msgstr[n]`) into the target language. Do **not** modify `msgid` or
`msgid_plural`. After translation, **clear the fuzzy mark**: in PO, remove the
`#, fuzzy` tag from comments; in JSON, omit or set `fuzzy` to `false`.


### Preserving Special Characters

Preserve escape sequences (`\n`, `\"`, `\\`, `\t`), placeholders (`%s`, `%d`,
etc.), and quotes exactly as in `msgid`. Only reorder placeholders with
positional syntax when needed (see Placeholder Reordering below).

**Correct**: `msgstr "行 1\n行 2"` (keep `\n` as escape).
**Wrong**: `msgstr "行 1\\n行 2"` or actual line breaks inside the string.


### Placeholder Reordering

When reordering placeholders from the original `msgid`, use positional syntax
(`%n$`) so each argument maps to the correct value. Keep width/precision
modifiers and put the position before them.

**Example 1** (precision):
```po
#, c-format
msgid "missing environment variable '%s' for configuration '%.*s'"
msgstr "配置 '%3$.*2$s' 缺少环境变量 '%1$s'"
```
`%s` → argument 1 → `%1$s`. `%.*s` needs precision (arg 2) and string (arg 3) →
`%3$.*2$s`.

**Example 2** (multi-line, four `%s` reordered):
```po
#, c-format
msgid ""
"the 'submodule.%s.gitdir' config does not exist for module '%s'. Please "
"ensure it is set, for example by running something like: 'git config "
"submodule.%s.gitdir .git/modules/%s'. For details see the "
"extensions.submodulePathConfig documentation."
msgstr ""
"模块 '%2$s' 的 'submodule.%1$s.gitdir' 配置不存在。请确保已设置，例如运行类"
"似：'git config submodule.%3$s.gitdir .git/modules/%4$s'。详细信息请参见 "
"extensions.submodulePathConfig 文档。"
```

Original order 1,2,3,4; in translation 2,1,3,4. Each line must be a complete
quoted string.

**Rules**: Use `%n$` (n = 1-based position); place the position number before
width/precision modifiers; for `%.*s` map both precision and string; verify all
placeholders are mapped.


### Validating PO File Format

Validate any PO file (e.g. `po/XX.po`, `po/l10n-pending.po`):

```shell
msgfmt --check -o /dev/null po/XX.po
```

Common validation errors include:
- Unclosed quotes
- Missing escape sequences
- Invalid placeholder syntax
- Malformed multi-line entries
- Incorrect line breaks in multi-line strings

**Handling validation errors**:
When `msgfmt` reports an error, it provides the line number where the error
was detected. Use this information to locate and fix the issue.


### Using git-po-helper

[git-po-helper](https://github.com/git-l10n/git-po-helper) is a helper program
for Git localization (l10n) contributions. It serves two main purposes:
**quality checking** (conventions for git-l10n pull requests) and
**AI-assisted translation** (evaluating the impact of this document on
automated translation; providing subcommands that simplify the AI translation
workflow and improve efficiency). When available, this document uses
`git-po-helper` for PO operations; otherwise it falls back to gettext tools.

**This section serves as a reference for housekeeping tasks.** AI agents should
follow the task steps when executing; this content provides command reference
information. Do not run commands in isolation.


#### Splitting large PO files

When a PO file is too large for translation or review, use `git-po-helper
msg-select` to split it by entry index.

- **Entry 0** is the header (included by default; use `--no-header` to omit).
- **Entries 1, 2, 3, …** are content entries.
- **Range format**: `--range "1-50"` (entries 1 through 50), `--range "-50"`
  (first 50 entries), `--range "51-"` (from entry 51 to end).
- **Output format**: PO by default; use `--json` for GETTEXT JSON. See the
  "GETTEXT JSON format" section (under git-po-helper) for details.
- **State filter**: Use `--translated`, `--untranslated`, `--fuzzy` to filter
  by state (OR relationship). Use `--no-obsolete` to exclude obsolete entries;
  `--with-obsolete` to include (default). Use `--only-same` or `--only-obsolete`
  for a single state. Range applies to the filtered list.

```shell
# First 50 entries (header + entries 1–50)
git-po-helper msg-select --range "-50" po/in.po -o po/out1.po

# Entries 51–100
git-po-helper msg-select --range "51-100" po/in.po -o po/out2.po

# Entries 101 to end
git-po-helper msg-select --range "101-" po/in.po -o po/out3.po

# Entries 1–50 without header (content only)
git-po-helper msg-select --range "1-50" --no-header po/in.po -o po/frag.po

# Output as JSON; select untranslated and fuzzy entries, exclude obsolete
git-po-helper msg-select --json --untranslated --fuzzy --no-obsolete po/in.po >po/filtered.json
```


#### Comparing PO files for translation and review

Use `git-po-helper compare` for scenarios that `git diff` or `git show` cannot
handle well:

- **Show changes with full context**: Get new and modified entries with
  complete `msgid` and `msgstr`. Plain `git diff` either fragments the output
  or loses PO context.
- **Detect msgid tampering**: When an AI-generated PO file may have altered
  `msgid`, a translation becomes an add instead of a replace. Use `--msgid`
  to compare by msgid only. No diff output means the target and source files
  are consistent in the data source (msgid).

These capabilities support both translation workflows and code review. Redirect
output to a file:

```shell
# Check msgid consistency (detect tampering); no output means target matches source
git-po-helper compare --msgid po/old.po po/new.po >po/out.po

# Get full context of local changes (HEAD vs working tree)
git-po-helper compare po/XX.po -o po/out.po

# Get full context of changes in a specific commit (parent vs commit)
git-po-helper compare --commit <commit> po/XX.po -o po/out.po

# Get full context of changes since a commit (commit vs working tree)
git-po-helper compare --since <commit> po/XX.po -o po/out.po

# Get full context between two commits
git-po-helper compare -r <commit1>..<commit2> po/XX.po -o po/out.po

# Get full context of two worktree files
git-po-helper compare po/old.po po/new.po -o po/out.po
```

**Options summary**

| Option              | Meaning                                        |
|---------------------|------------------------------------------------|
| (none)              | Compare HEAD with working tree (local changes) |
| `--commit <commit>` | Compare parent of commit with the commit       |
| `--since <commit>`  | Compare commit with working tree               |
| `-r x..y`           | Compare revision x with revision y             |
| `-r x..`            | Compare revision x with working tree           |
| `-r x`              | Compare parent of x with x                     |

Output is empty when there are no new or changed entries; otherwise it
includes a valid PO header.


#### Concatenating multiple PO/JSON files

Use `git-po-helper msg-cat` to merge one or more input files (PO, POT, or
gettext JSON) into a single output. Input format is auto-detected by content
or extension. For duplicate `msgid` values, the first occurrence by file
order wins. Use `-o <file>` for output; omit or use `-o -` for stdout. Use
`--json` for JSON output; otherwise the output is in PO format.

```shell
# Convert JSON to PO (e.g. after translation)
git-po-helper msg-cat --unset-fuzzy -o po/out.po po/in.json

# Merge multiple PO files
git-po-helper msg-cat -o po/out.po po/in-1.po po/in-2.po
```


#### GETTEXT JSON format

The **GETTEXT JSON** format is an internal format defined by `git-po-helper`
for convenient batch processing of translation and related tasks by AI models.
`git-po-helper msg-select`, `git-po-helper msg-cat`, and `git-po-helper compare`
read and write this format.

**Top-level structure**:

```json
{
  "header_comment": "string",
  "header_meta": "string",
  "entries": [ /* array of entry objects */ ]
}
```

| Field            | Description                                                                    |
|------------------|--------------------------------------------------------------------------------|
| `header_comment` | Lines above the first `msgid ""` (comments, glossary), directly concatenated.  |
| `header_meta`    | Decoded `msgstr` of the header entry (Project-Id-Version, Plural-Forms, etc.). |
| `entries`        | List of PO entries. Order matches source.                                      |

**Entry object** (each element of `entries`):

| Field           | Type     | Description                                                  |
|-----------------|----------|--------------------------------------------------------------|
| `msgid`         | string   | Singular message ID. PO escapes encoded (e.g. `\n` → `\\n`). |
| `msgstr`        | string   | Singular message string. Empty for plural entries.           |
| `msgid_plural`  | string   | Plural form of msgid. Omit for non-plural.                   |
| `msgstr_plural` | []string | Array of msgstr[0], msgstr[1], … Omit for non-plural.        |
| `comments`      | []string | Comment lines (`#`, `#.`, `#:`, `#,`, etc.).                 |
| `fuzzy`         | bool     | True if entry has fuzzy flag.                                |
| `obsolete`      | bool     | True for `#~` obsolete entries. Omit if false.               |

**Example (single-line entry)**:

```json
{
  "header_comment": "# Glossary:\\n# term1\\tTranslation 1\\n#\\n",
  "header_meta": "Project-Id-Version: git\\nContent-Type: text/plain; charset=UTF-8\\n",
  "entries": [
    {
      "msgid": "Hello",
      "msgstr": "你好",
      "comments": ["#. Comment for translator\\n", "#: src/file.c:10\\n"],
      "fuzzy": false
    }
  ]
}
```

**Example (plural entry)**:

```json
{
  "msgid": "One file",
  "msgstr": "",
  "msgid_plural": "%d files",
  "msgstr_plural": ["一个文件", "%d 个文件"],
  "comments": ["#, c-format\\n"],
  "fuzzy": false
}
```

**Example (fuzzy entry before translation)**:

```json
{
  "msgid": "Old message",
  "msgstr": "旧翻译",
  "comments": ["#, fuzzy\\n"],
  "fuzzy": true
}
```

**Translation notes for GETTEXT JSON files**:

- **Preserve structure**: Keep `header_comment`, `header_meta`, `comments`,
  `msgid`, `msgid_plural` unchanged. Only modify `msgstr` and `msgstr_plural`.
- **Fuzzy entries**: Entries extracted from fuzzy PO entries have `"fuzzy": true`.
  After translating, **remove the `fuzzy` field** or set it to `false` in the
  output (`po/l10n-done.json`). The merge step uses `--unset-fuzzy`, which can
  also remove the `fuzzy` field.
- **Placeholders**: Preserve `%s`, `%d`, etc. exactly; use `%n$` when
  reordering (see "Placeholder Reordering" above).


### Quality checklist

- **Accuracy**: Faithful to original meaning; no omissions or distortions.
- **Fuzzy entries**: Re-translate fully and clear the fuzzy flag (see
  "Translating fuzzy entries" above).
- **Terminology**: Consistent with glossary (see "Glossary Section" above) or
  domain standards.
- **Grammar and fluency**: Correct and natural in the target language.
- **Placeholders**: Preserve variables (`%s`, `{name}`, `$1`) exactly; use
  positional parameters when reordering (see "Placeholder Reordering" above).
- **Special characters**: Preserve escape sequences (`\n`, `\"`, `\\`, `\t`),
  placeholders, and quotes exactly as in `msgid`. Correct: `msgstr "行 1\n行 2"`
  (keep `\n` as escape). Wrong: `"行 1\\n行 2"` or actual line breaks inside the
  string. See "Preserving Special Characters" above.
- **Plurals and gender**: Correct forms and agreement.
- **Context fit**: Suitable for UI space, tone, and use (e.g. error vs. tooltip).
- **Cultural appropriateness**: No offensive or ambiguous content.
- **Consistency**: Match prior translations of the same source.
- **Technical integrity**: Do not translate code, paths, commands, brands, or
  proper nouns.
- **Readability**: Clear, concise, and user-friendly.


## Housekeeping tasks for localization workflows

This section describes housekeeping tasks listed in the introduction. Read
"Background knowledge for localization workflows" above before performing
any task.


### Task 1: Generating or updating po/git.pot

When asked to "update po/git.pot" or given similar requests:

1. **Directly execute** the command `make po/git.pot` without checking
   if the file exists beforehand.

2. **Do not verify** the generated file after execution. Simply run the
   command and consider the task complete.

The command will handle all necessary steps including file creation or
update automatically.


### Task 2: Updating po/XX.po

When asked to "update po/XX.po" or given similar requests (where XX is a
language code):

1. **Directly execute** the command `make po-update PO_FILE=po/XX.po`
   without reading or checking the file content beforehand.

2. **Do not verify, translate, or review** the updated file after execution.
   Simply run the command and consider the task complete.

The command will handle all necessary steps including generating
"po/git.pot" and merging new translatable strings into "po/XX.po"
automatically.


### Task 3: Translating po/XX.po

When asked to translate `po/XX.po`, follow the steps below. The workflow
**automatically selects** the tool based on availability: use `git-po-helper`
if present, otherwise use gettext tools. With `git-po-helper`, the content to
translate is converted to JSON, enabling batch translation instead of
entry-by-entry translation for better efficiency. Translate every untranslated
and fuzzy entry; do not stop before the loop completes.

1. **Extract entries to translate**: Generate `po/l10n-pending.po` with
   untranslated and fuzzy messages. If the generated `po/l10n-pending.po` file
   is empty or does not exist, translation is complete. In that case, you
   **MUST** skip to the last step (clean up); do not run further translation
   steps.

   ```shell
   po_extract_pending () {
       test $# -ge 1 || { echo "Usage: po_extract_pending <po-file>" >&2; exit 1; }
       PO_FILE="$1"
       PENDING="po/l10n-pending.po"
       rm -f "$PENDING"

       if command -v git-po-helper >/dev/null 2>&1
       then
           git-po-helper msg-select --untranslated --fuzzy --no-obsolete -o "$PENDING" "$PO_FILE"
       else
           msgattrib --untranslated --no-obsolete "$PO_FILE" >"${PENDING}.untranslated"
           msgattrib --only-fuzzy --no-obsolete --clear-fuzzy --empty "$PO_FILE" >"${PENDING}.fuzzy"
           msgattrib --only-fuzzy --no-obsolete "$PO_FILE" >"${PENDING}.fuzzy.reference"
           msgcat --use-first "${PENDING}.untranslated" "${PENDING}.fuzzy" >"$PENDING"
           rm -f "${PENDING}.untranslated" "${PENDING}.fuzzy"
       fi
   }
   # Run the extraction. Example: po_extract_pending po/zh_CN.po
   po_extract_pending po/XX.po
   ```

2. **Prepare one batch for translation**: **BEFORE translating**, run the
   script below. It truncates large tasks so each run processes one chunk,
   keeping file size within model capacity.

   Output: `po/l10n-todo.json` (git-po-helper) or `po/l10n-todo.po` (gettext
   only). If `po/l10n-todo.json` exists, go to step 3a; if `po/l10n-todo.po`
   exists, go to step 3b.

   ```shell
   l10n_one_batch () {
       test $# -ge 1 || { echo "Usage: l10n_one_batch <po-file> [min_batch_size]" >&2; exit 1; }
       PO_FILE="$1"
       min_batch_size=${2:-100}
       PENDING="po/l10n-pending.po"
       rm -f po/l10n-todo.json po/l10n-done.json po/l10n-todo.po po/l10n-done.po

       ENTRY_COUNT=$(grep -c '^msgid ' "$PENDING" 2>/dev/null || true)
       ENTRY_COUNT=$((ENTRY_COUNT > 0 ? ENTRY_COUNT - 1 : 0))

       if test "$ENTRY_COUNT" -gt $min_batch_size
       then
           if test "$ENTRY_COUNT" -gt $((min_batch_size * 8))
           then
               NUM=$((min_batch_size * 2))
           elif test "$ENTRY_COUNT" -gt $((min_batch_size * 4))
           then
               NUM=$((min_batch_size + min_batch_size / 2))
           else
               NUM=$min_batch_size
           fi
           BATCHING=1
       else
           NUM=$ENTRY_COUNT
           BATCHING=
       fi

       if command -v git-po-helper >/dev/null 2>&1
       then
           if test -n "$BATCHING"
           then
               git-po-helper msg-select --json --range "-$NUM" -o po/l10n-todo.json "$PENDING"
               echo "Processing batch of $NUM entries (out of $ENTRY_COUNT remaining)"
           else
               git-po-helper msg-select --json -o po/l10n-todo.json "$PENDING"
               echo "Processing all $ENTRY_COUNT entries at once"
           fi
       else
           if test -n "$BATCHING"
           then
               awk -v num="$NUM" '/^msgid / && count++ > num {exit} 1' "$PENDING" |
                   tac | awk '/^$/ {found=1} found' | tac >po/l10n-todo.po
               echo "Processing batch of $NUM entries (out of $ENTRY_COUNT remaining)"
           else
               cp "$PENDING" po/l10n-todo.po
               echo "Processing all $ENTRY_COUNT entries at once"
           fi
       fi
   }
   # Prepare batch for translation. Second param controls batch size; reduce if
   # the batch file is too large for the Agent to process.
   l10n_one_batch po/XX.po 100
   ```

3a. **Translate JSON batch** (`po/l10n-todo.json` → `po/l10n-done.json`):

   - **Task**: Translate `po/l10n-todo.json` (input, GETTEXT JSON) into
     `po/l10n-done.json` (output, GETTEXT JSON). See the "GETTEXT JSON format"
     section above for format details and translation rules.
   - **Reference glossary**: Read the glossary from the batch file's
     `header_comment` (see "Glossary Section" above) and use it for
     consistent terminology.
   - **When translating**: Follow the "Quality checklist" above for correctness
     and quality. Handle escape sequences (`\n`, `\"`, `\\`, `\t`), placeholders,
     and quotes correctly as in `msgid`. For JSON, correctly escape and unescape
     these sequences when reading and writing. Modify `msgstr` and `msgstr[n]`
     (for plural entries); clear the fuzzy flag (omit or set `fuzzy` to `false`).
     Do **not** modify `msgid` or `msgid_plural`.

3b. **Translate PO batch** (`po/l10n-todo.po` → `po/l10n-done.po`):

   - **Task**: Translate `po/l10n-todo.po` (input, PO) into `po/l10n-done.po`
     (output, PO).
   - **Reference glossary**: Read the glossary from the pending file header
     (see "Glossary Section" above) and use it for consistent terminology.
   - **When translating**: Follow the "Quality checklist" above for correctness
     and quality. Preserve escape sequences (`\n`, `\"`, `\\`, `\t`), placeholders,
     and quotes as in `msgid`. Modify `msgstr` and `msgstr[n]` (for plural
     entries); remove the `#, fuzzy` tag from comments when done. Do **not**
     modify `msgid` or `msgid_plural`.

4. **Validate `po/l10n-done.po`**:

   Whether from step 3a (JSON converted to PO) or step 3b (direct PO output),
   the result may have two kinds of issues. Run the validation script; proceed to
   step 5 only if it succeeds:

   ```shell
   l10n_validate_done () {
       DONE_PO="po/l10n-done.po"
       DONE_JSON="po/l10n-done.json"
       PENDING="po/l10n-pending.po"

       if test -f "$DONE_JSON" && { ! test -f "$DONE_PO" || test "$DONE_JSON" -nt "$DONE_PO"; }
       then
           git-po-helper msg-cat --unset-fuzzy -o "$DONE_PO" "$DONE_JSON" || {
               echo "ERROR [JSON to PO conversion]: Fix $DONE_JSON and re-run." >&2
               return 1
           }
       fi

       # Check 1: msgid should not be modified
       MSGID_OUT=$(git-po-helper compare -q --msgid --assert-no-changes \
           "$PENDING" "$DONE_PO" 2>&1)
       MSGID_RC=$?
       if test $MSGID_RC -ne 0 || test -n "$MSGID_OUT"
       then
           echo "ERROR [msgid modified]: The following entries appeared after" >&2
           echo "translation because msgid was altered. Fix in $DONE_PO." >&2
           echo "$MSGID_OUT" >&2
           return 1
       fi

       # Check 2: PO format (see "Validating PO File Format" for error handling)
       MSGFMT_OUT=$(msgfmt --check -o /dev/null "$DONE_PO" 2>&1)
       MSGFMT_RC=$?
       if test $MSGFMT_RC -ne 0
       then
           echo "ERROR [PO format]: Fix errors in $DONE_PO." >&2
           echo "$MSGFMT_OUT" >&2
           return 1
       fi

       echo "Validation passed."
   }
   l10n_validate_done
   ```

   If the script fails, fix **directly in `po/l10n-done.po`**. Editing
   `po/l10n-done.json` is not recommended because it adds an extra JSON-to-PO
   conversion step. Use the error message to decide:

   - **`[msgid modified]`**: The listed entries have altered `msgid`; restore
     them to match `po/l10n-pending.po`.
   - **`[PO format]`**: `msgfmt` reports line numbers; fix the errors in place.
     See "Validating PO File Format" for common issues.

   Re-run `l10n_validate_done` until it succeeds. If repair fails, exit
   immediately.

5. **Merge translation results into `po/XX.po`**: Run the following script:

   ```shell
   l10n_merge_batch () {
       test $# -ge 1 || { echo "Usage: l10n_merge_batch <po-file>" >&2; exit 1; }
       PO_FILE="$1"
       DONE_PO="po/l10n-done.po"
       DONE_JSON="po/l10n-done.json"
       MERGED="po/l10n-done.merged"
       PENDING="po/l10n-pending.po"
       if test -f "$DONE_JSON" && { ! test -f "$DONE_PO" || test "$DONE_JSON" -nt "$DONE_PO"; }
       then
           git-po-helper msg-cat --unset-fuzzy -o "$DONE_PO" "$DONE_JSON" || {
               echo "ERROR [JSON to PO conversion]: Fix $DONE_JSON and re-run." >&2
               return 1
           }
       fi
       msgcat --use-first "$DONE_PO" "$PO_FILE" >"$MERGED" || {
           echo "ERROR [msgcat merge]: Fix errors in $DONE_PO and re-run." >&2
           exit 1
       }
       mv "$MERGED" "$PO_FILE"
       rm -f "$PENDING"
   }
   # Run the merge. Example: l10n_merge_batch po/zh_CN.po
   l10n_merge_batch po/XX.po
   ```

   If `msgcat` fails, fix **directly in `po/l10n-done.po`**. Editing
   `po/l10n-done.json` is not recommended because it adds an extra JSON-to-PO
   conversion step. If repair fails, exit immediately.

6. **Repeat steps 1–5** until `po/l10n-pending.po` is empty (or does not exist).
   Do not stop early.

7. **Final verification**:

   ```shell
   # Final check
   UNTRANS=$(msgattrib --untranslated --no-obsolete po/XX.po 2>/dev/null | grep -c '^msgid ' || true)
   UNTRANS=$((UNTRANS > 0 ? UNTRANS - 1 : 0))
   FUZZY=$(msgattrib --only-fuzzy --no-obsolete po/XX.po 2>/dev/null | grep -c '^msgid ' || true)
   FUZZY=$((FUZZY > 0 ? FUZZY - 1 : 0))
   if test "$UNTRANS" -eq 0 && test "$FUZZY" -eq 0
   then
       echo "Translation complete! All entries translated."
   else
       echo "WARNING: Still have $UNTRANS untranslated + $FUZZY fuzzy entries."
       echo "Do not clean up. Continue with step 1."
       exit 1
   fi
   ```

8. **Clean up** (only after step 7 passes):

   ```shell
   po_cleanup () {
       rm -f "po/l10n-pending.po"
       rm -f "po/l10n-pending.po.fuzzy"
       rm -f "po/l10n-pending.po.fuzzy.reference"
       rm -f "po/l10n-pending.po.untranslated"
       rm -f "po/l10n-todo.json"
       rm -f "po/l10n-todo.po"
       rm -f "po/l10n-done.json"
       rm -f "po/l10n-done.merged"
       rm -f "po/l10n-done.po"
       echo "Cleanup complete. Translation finished successfully."
   }
   # Run cleanup
   po_cleanup
   ```


## Human translators remain in control

Git translation is human-driven; language team leaders and contributors are
responsible for:

- Understanding technical context of Git commands and messages
- Making linguistic and cultural decisions for the target language
- Maintaining translation quality and consistency
- Ensuring translations follow Git l10n conventions and standards
- Building and maintaining language glossaries
- Reviewing and approving all changes before submission

AI tools, if used, only accelerate routine tasks.

AI-generated output should always be treated as rough drafts requiring human
review, editing, and approval by someone who understands both the technical
context and the target language. The best results come from combining AI
efficiency with human judgment, cultural insight, and community engagement.
