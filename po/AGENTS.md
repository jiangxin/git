# Instructions for AI Agents

This file gives specific instructions for AI agents that perform
housekeeping tasks for Git l10n. Use of AI is optional; many successful
l10n teams work well without it.

The section "Housekeeping tasks for localization workflows" documents the
most commonly used housekeeping tasks.


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
