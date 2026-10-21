### File: `data/ir_cron_data.xml`
```xml
<?xml version="1.0" encoding="utf-8" ?>
<!-- Copyright 2024 thingsintouch.com
     License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl). -->
<odoo noupdate="1">
    <record id="ir_cron_retry_attendance_rfid_log" model="ir.cron">
        <field name="name">Retry Attendances on RFID Log</field>
        <field name="interval_number">1</field>
        <field name="interval_type">hours</field>
        <field name="numbercall">-1</field>
        <field
            name="model_id"
            ref="hr_attendance_rfid_log.model_hr_attendance_rfid_log"
        />
        <field name="state">code</field>
        <field name="code">model._retry_attendance_rfid_log()</field>
    </record>
    <record id="ir_cron_purge_attendance_rfid_log" model="ir.cron">
        <field name="name">Purge Log of RFID Attendances</field>
        <field name="interval_number">1</field>
        <field name="interval_type">days</field>
        <field name="numbercall">-1</field>
        <field
            name="model_id"
            ref="hr_attendance_rfid_log.model_hr_attendance_rfid_log"
        />
        <field name="state">code</field>
        <field name="code">model._purge_attendance_rfid_log()</field>
    </record>
</odoo>

```

### File: `data/system_parameters.xml`
```xml
<?xml version="1.0" encoding="utf-8" ?>
<!-- Copyright 2024 thingsintouch.com
     License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl). -->
<odoo noupdate="1">
    <record model="ir.config_parameter" id="ir_config_param_purge_period_success">
        <field name="key">hr_attendance_rfid_log.purge_period_success</field>
        <field name="value">5</field>
    </record>
    <record model="ir.config_parameter" id="ir_config_param_purge_period_general">
        <field name="key">hr_attendance_rfid_log.purge_period_general</field>
        <field name="value">40</field>
    </record>
</odoo>

```

### File: `__init__.py`
```python
from . import models
from . import wizards

```

### File: `__manifest__.py`
```python
# Copyright 2026 - nurzeit.de
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

{
    "name": "ThingsInTouch RAS Log",
    "version": "19.0.1.0.0",
    "category": "Human Resources",
    "website": "https://github.com/thingsintouch/iot-devices",
    "author": "nurzeit.de, lubusax",
    "maintainers": ["lubusax"],
    "license": "AGPL-3",
    "application": False,
    "installable": True,
    "depends": ["hr_attendance_rfid"],
    "data": [
        "data/ir_cron_data.xml",
        "data/system_parameters.xml",
        "security/groups.xml",
        "security/ir.model.access.csv",
        "views/hr_attendance_log_view.xml",
        "wizards/hr_rfid_log_assign_employee.xml",
    ],
}
```

### File: `models/hr_attendance.py`
```python
# Copyright 2026 - nurzeit.de
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

from odoo import api, fields, models


class HrEmployeeBase(models.AbstractModel):
    _inherit = "hr.employee.base"

    @api.model
    def register_attendance(self, card_code, log=False):
        res = super().register_attendance(card_code)
        new_log = self._prepare_attendance_rfid_log(res)
        if log:
            log.sudo().write(new_log)
        else:
            self.env["hr.attendance.rfid.log"].create(new_log)
        res["in_rfid_log"] = True
        return res

    def _prepare_attendance_rfid_log(self, res):
        vals = {
            "state": "success" if res.get("logged") else "failed",
            "rfid_card_code": res.get("rfid_card_code"),
            "employee_name": res.get("employee_name"),
            "employee_id": res.get("employee_id"),
            "error_message": res.get("error_message"),
            "logged": res.get("logged"),
            "action": res.get("action"),
            "timestamp": fields.Datetime.now(),
        }
        return vals

    @api.model
    def register_attendance_with_log(self, log):
        # Inject the hardware timestamp into the context so the attendance 
        # model can grab it during the create/write lifecycle before validation.
        return self.with_context(
            rfid_custom_timestamp=log.timestamp
        ).register_attendance(log.rfid_card_code, log)
```

### File: `models/hr_attendance_rfid_log.py`
```python
# Copyright 2026 - nurzeit.de
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

from datetime import timedelta

from odoo import fields, models


class RfidAttendanceLog(models.Model):
    _name = "hr.attendance.rfid.log"
    _description = "HR Attendance RFID Logging"
    _order = "id desc"

    state = fields.Selection(
        selection=[
            ("success", "Success"),
            ("failed", "Failed"),
            ("retry", "Retry"),
            ("ignore", "Ignore"),
        ],
        readonly=True,
    )
    rfid_card_code = fields.Char(
        readonly=True, string="RFID Card Code", copy=False
    )
    employee_name = fields.Char(readonly=True)
    employee_id = fields.Many2one(
        "hr.employee", string="Employee", ondelete="cascade", index=True
    )
    error_message = fields.Char(readonly=True)
    logged = fields.Boolean(readonly=True)
    action = fields.Selection(
        selection=[
            ("check_in", "check in"),
            ("check_out", "check out"),
            ("undefined", "Not Defined (in or out)"),
        ],
        readonly=True,
    )
    timestamp = fields.Datetime(
        string="RFID-Timestamp", default=fields.Datetime.now, required=True
    )
    retry_counter = fields.Integer(default=0)

    def action_open_wizard_assign_employee(self):
        action = self.env["ir.actions.actions"]._for_xml_id(
            "hr_attendance_rfid_log.action_hr_rfid_log_assign_employee"
        )
        action["context"] = {
            "default_rfid_card_code": self.rfid_card_code,
            "default_hr_attendance_rfid_log_id": self.id,
        }
        return action

    def action_set_to_retry_state(self):
        self.sudo().write({"state": "retry"})

    def action_set_to_ignore_state(self):
        self.sudo().write({"state": "ignore"})

    def action_retry_now(self):
        if self.state == "retry":
            self.sudo().retry_counter += 1
            self.env["hr.employee"].register_attendance_with_log(self)

    def _retry_attendance_rfid_log(self):
        logs_to_retry = self.search([("state", "in", ["retry"])])
        for log in logs_to_retry:
            log.action_retry_now()

    def _purge_attendance_rfid_log(self):
        current_date = fields.Datetime.now()

        default_purge_period_success = 5
        default_purge_period_general = 40

        purge_period_success = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("hr_attendance_rfid_log.purge_period_success")
        )
        purge_period_general = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("hr_attendance_rfid_log.purge_period_general")
        )

        try:
            purge_period_success = (
                int(purge_period_success)
                if purge_period_success
                else default_purge_period_success
            )
            purge_period_general = (
                int(purge_period_general)
                if purge_period_general
                else default_purge_period_general
            )
        except ValueError:
            self.env["ir.config_parameter"].sudo().set_param(
                "hr_attendance_rfid_log.purge_period_success",
                str(default_purge_period_success),
            )
            self.env["ir.config_parameter"].sudo().set_param(
                "hr_attendance_rfid_log.purge_period_general",
                str(default_purge_period_general),
            )
            purge_period_success = default_purge_period_success
            purge_period_general = default_purge_period_general

        logs_to_purge = self.search(
            [
                "|",
                "&",
                ("state", "=", "success"),
                ("timestamp", "<", current_date - timedelta(days=purge_period_success)),
                ("timestamp", "<", current_date - timedelta(days=purge_period_general)),
            ]
        )
        logs_to_purge.unlink()

```

### File: `models/hr_employee.py`
```python
# Copyright 2026 - nurezeit.de
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

from odoo import api, fields, models


class HrEmployeeBase(models.AbstractModel):
    _inherit = "hr.employee.base"

    @api.model
    def register_attendance(self, card_code, log=False):
        res = super().register_attendance(card_code)
        new_log = self._prepare_attendance_rfid_log(res)
        if log:
            log.sudo().write(new_log)
        else:
            self.env["hr.attendance.rfid.log"].create(new_log)
        res["in_rfid_log"] = True
        return res

    def _prepare_attendance_rfid_log(self, res):
        vals = {
            "state": "success" if res.get("logged") else "failed",
            "rfid_card_code": res.get("rfid_card_code"),
            "employee_name": res.get("employee_name"),
            "employee_id": res.get("employee_id"),
            "error_message": res.get("error_message"),
            "logged": res.get("logged"),
            "action": res.get("action"),
            "timestamp": fields.Datetime.now(),
        }
        return vals

    @api.model
    def register_attendance_with_log(self, log):
        # Inject the hardware timestamp into the context so the attendance 
        # model can grab it during the create/write lifecycle before validation.
        return self.with_context(
            rfid_custom_timestamp=log.timestamp
        ).register_attendance(log.rfid_card_code, log)
```

### File: `models/__init__.py`
```python
from . import hr_attendance_rfid_log, hr_employee

```

### File: `security/groups.xml`
```xml
<?xml version="1.0" encoding="utf-8" ?>
<!-- Copyright 2023 thingsintouch.com
     License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl). -->
<odoo noupdate="1">
    <record id="group_attendance_rfid_log_manager" model="res.groups">
        <field name="name">Attendances RFID Log Manager</field>
        <field
            name="users"
            eval="[(4, ref('base.user_root')),(4, ref('base.user_admin'))]"
        />
    </record>
</odoo>

```

### File: `security/ir.model.access.csv`
```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_hr_attendance_rfid_log,access_hr_attendance_rfid_log,model_hr_attendance_rfid_log,hr_attendance_rfid_log.group_attendance_rfid_log_manager,1,0,0,0
access_hr_attendance_rfid_log_assign_employee,hr.attendance.rfid.log.assign.employee,model_hr_attendance_rfid_log_assign_employee,base.group_user,1,1,1,1

```

### File: `static/description/index.html`
```text
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en" lang="en">
<head>
<meta http-equiv="Content-Type" content="text/html; charset=utf-8" />
<meta name="generator" content="Docutils: https://docutils.sourceforge.io/" />
<title>HR Attendance RFID Log</title>
<style type="text/css">

/*
:Author: David Goodger (goodger@python.org)
:Id: $Id: html4css1.css 9511 2024-01-13 09:50:07Z milde $
:Copyright: This stylesheet has been placed in the public domain.

Default cascading style sheet for the HTML output of Docutils.
Despite the name, some widely supported CSS2 features are used.

See https://docutils.sourceforge.io/docs/howto/html-stylesheets.html for how to
customize this style sheet.
*/

/* used to remove borders from tables and images */
.borderless, table.borderless td, table.borderless th {
  border: 0 }

table.borderless td, table.borderless th {
  /* Override padding for "table.docutils td" with "! important".
     The right padding separates the table cells. */
  padding: 0 0.5em 0 0 ! important }

.first {
  /* Override more specific margin styles with "! important". */
  margin-top: 0 ! important }

.last, .with-subtitle {
  margin-bottom: 0 ! important }

.hidden {
  display: none }

.subscript {
  vertical-align: sub;
  font-size: smaller }

.superscript {
  vertical-align: super;
  font-size: smaller }

a.toc-backref {
  text-decoration: none ;
  color: black }

blockquote.epigraph {
  margin: 2em 5em ; }

dl.docutils dd {
  margin-bottom: 0.5em }

object[type="image/svg+xml"], object[type="application/x-shockwave-flash"] {
  overflow: hidden;
}

/* Uncomment (and remove this text!) to get bold-faced definition list terms
dl.docutils dt {
  font-weight: bold }
*/

div.abstract {
  margin: 2em 5em }

div.abstract p.topic-title {
  font-weight: bold ;
  text-align: center }

div.admonition, div.attention, div.caution, div.danger, div.error,
div.hint, div.important, div.note, div.tip, div.warning {
  margin: 2em ;
  border: medium outset ;
  padding: 1em }

div.admonition p.admonition-title, div.hint p.admonition-title,
div.important p.admonition-title, div.note p.admonition-title,
div.tip p.admonition-title {
  font-weight: bold ;
  font-family: sans-serif }

div.attention p.admonition-title, div.caution p.admonition-title,
div.danger p.admonition-title, div.error p.admonition-title,
div.warning p.admonition-title, .code .error {
  color: red ;
  font-weight: bold ;
  font-family: sans-serif }

/* Uncomment (and remove this text!) to get reduced vertical space in
   compound paragraphs.
div.compound .compound-first, div.compound .compound-middle {
  margin-bottom: 0.5em }

div.compound .compound-last, div.compound .compound-middle {
  margin-top: 0.5em }
*/

div.dedication {
  margin: 2em 5em ;
  text-align: center ;
  font-style: italic }

div.dedication p.topic-title {
  font-weight: bold ;
  font-style: normal }

div.figure {
  margin-left: 2em ;
  margin-right: 2em }

div.footer, div.header {
  clear: both;
  font-size: smaller }

div.line-block {
  display: block ;
  margin-top: 1em ;
  margin-bottom: 1em }

div.line-block div.line-block {
  margin-top: 0 ;
  margin-bottom: 0 ;
  margin-left: 1.5em }

div.sidebar {
  margin: 0 0 0.5em 1em ;
  border: medium outset ;
  padding: 1em ;
  background-color: #ffffee ;
  width: 40% ;
  float: right ;
  clear: right }

div.sidebar p.rubric {
  font-family: sans-serif ;
  font-size: medium }

div.system-messages {
  margin: 5em }

div.system-messages h1 {
  color: red }

div.system-message {
  border: medium outset ;
  padding: 1em }

div.system-message p.system-message-title {
  color: red ;
  font-weight: bold }

div.topic {
  margin: 2em }

h1.section-subtitle, h2.section-subtitle, h3.section-subtitle,
h4.section-subtitle, h5.section-subtitle, h6.section-subtitle {
  margin-top: 0.4em }

h1.title {
  text-align: center }

h2.subtitle {
  text-align: center }

hr.docutils {
  width: 75% }

img.align-left, .figure.align-left, object.align-left, table.align-left {
  clear: left ;
  float: left ;
  margin-right: 1em }

img.align-right, .figure.align-right, object.align-right, table.align-right {
  clear: right ;
  float: right ;
  margin-left: 1em }

img.align-center, .figure.align-center, object.align-center {
  display: block;
  margin-left: auto;
  margin-right: auto;
}

table.align-center {
  margin-left: auto;
  margin-right: auto;
}

.align-left {
  text-align: left }

.align-center {
  clear: both ;
  text-align: center }

.align-right {
  text-align: right }

/* reset inner alignment in figures */
div.align-right {
  text-align: inherit }

/* div.align-center * { */
/*   text-align: left } */

.align-top    {
  vertical-align: top }

.align-middle {
  vertical-align: middle }

.align-bottom {
  vertical-align: bottom }

ol.simple, ul.simple {
  margin-bottom: 1em }

ol.arabic {
  list-style: decimal }

ol.loweralpha {
  list-style: lower-alpha }

ol.upperalpha {
  list-style: upper-alpha }

ol.lowerroman {
  list-style: lower-roman }

ol.upperroman {
  list-style: upper-roman }

p.attribution {
  text-align: right ;
  margin-left: 50% }

p.caption {
  font-style: italic }

p.credits {
  font-style: italic ;
  font-size: smaller }

p.label {
  white-space: nowrap }

p.rubric {
  font-weight: bold ;
  font-size: larger ;
  color: maroon ;
  text-align: center }

p.sidebar-title {
  font-family: sans-serif ;
  font-weight: bold ;
  font-size: larger }

p.sidebar-subtitle {
  font-family: sans-serif ;
  font-weight: bold }

p.topic-title {
  font-weight: bold }

pre.address {
  margin-bottom: 0 ;
  margin-top: 0 ;
  font: inherit }

pre.literal-block, pre.doctest-block, pre.math, pre.code {
  margin-left: 2em ;
  margin-right: 2em }

pre.code .ln { color: gray; } /* line numbers */
pre.code, code { background-color: #eeeeee }
pre.code .comment, code .comment { color: #5C6576 }
pre.code .keyword, code .keyword { color: #3B0D06; font-weight: bold }
pre.code .literal.string, code .literal.string { color: #0C5404 }
pre.code .name.builtin, code .name.builtin { color: #352B84 }
pre.code .deleted, code .deleted { background-color: #DEB0A1}
pre.code .inserted, code .inserted { background-color: #A3D289}

span.classifier {
  font-family: sans-serif ;
  font-style: oblique }

span.classifier-delimiter {
  font-family: sans-serif ;
  font-weight: bold }

span.interpreted {
  font-family: sans-serif }

span.option {
  white-space: nowrap }

span.pre {
  white-space: pre }

span.problematic, pre.problematic {
  color: red }

span.section-subtitle {
  /* font-size relative to parent (h1..h6 element) */
  font-size: 80% }

table.citation {
  border-left: solid 1px gray;
  margin-left: 1px }

table.docinfo {
  margin: 2em 4em }

table.docutils {
  margin-top: 0.5em ;
  margin-bottom: 0.5em }

table.footnote {
  border-left: solid 1px black;
  margin-left: 1px }

table.docutils td, table.docutils th,
table.docinfo td, table.docinfo th {
  padding-left: 0.5em ;
  padding-right: 0.5em ;
  vertical-align: top }

table.docutils th.field-name, table.docinfo th.docinfo-name {
  font-weight: bold ;
  text-align: left ;
  white-space: nowrap ;
  padding-left: 0 }

/* "booktabs" style (no vertical lines) */
table.docutils.booktabs {
  border: 0px;
  border-top: 2px solid;
  border-bottom: 2px solid;
  border-collapse: collapse;
}
table.docutils.booktabs * {
  border: 0px;
}
table.docutils.booktabs th {
  border-bottom: thin solid;
  text-align: left;
}

h1 tt.docutils, h2 tt.docutils, h3 tt.docutils,
h4 tt.docutils, h5 tt.docutils, h6 tt.docutils {
  font-size: 100% }

ul.auto-toc {
  list-style-type: none }

</style>
</head>
<body>
<div class="document" id="hr-attendance-rfid-log">
<h1 class="title">HR Attendance RFID Log</h1>

<!-- !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
!! This file is generated by oca-gen-addon-readme !!
!! changes will be overwritten.                   !!
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
!! source digest: sha256:08831706b12f52e3631325afab108d0fe6e0a9df3581639933d414efe87411d6
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!! -->
<p><a class="reference external image-reference" href="https://odoo-community.org/page/development-status"><img alt="Beta" src="https://img.shields.io/badge/maturity-Beta-yellow.png" /></a> <a class="reference external image-reference" href="http://www.gnu.org/licenses/agpl-3.0-standalone.html"><img alt="License: AGPL-3" src="https://img.shields.io/badge/licence-AGPL--3-blue.png" /></a> <a class="reference external image-reference" href="https://github.com/OCA/hr-attendance/tree/17.0/hr_attendance_rfid_log"><img alt="OCA/hr-attendance" src="https://img.shields.io/badge/github-OCA%2Fhr--attendance-lightgray.png?logo=github" /></a> <a class="reference external image-reference" href="https://translation.odoo-community.org/projects/hr-attendance-17-0/hr-attendance-17-0-hr_attendance_rfid_log"><img alt="Translate me on Weblate" src="https://img.shields.io/badge/weblate-Translate%20me-F47D42.png" /></a> <a class="reference external image-reference" href="https://runboat.odoo-community.org/builds?repo=OCA/hr-attendance&amp;target_branch=17.0"><img alt="Try me on Runboat" src="https://img.shields.io/badge/runboat-Try%20me-875A7B.png" /></a></p>
<p>This module provides an intermediary logging layer between external RFID
terminals and Odoo’s hr.attendance model, capturing raw clocking events
to prevent them from accumulating on devices. It features an UI
(displaying both successful and failed syncs) coupled with a transient
wizard to troubleshoot database sync errors and map new RFID cards to
employees. Includes a scheduled cron job to automatically purge old
records, utilizing separate retention periods for successful versus
failed events.</p>
<p><strong>Table of contents</strong></p>
<div class="contents local topic" id="contents">
<ul class="simple">
<li><a class="reference internal" href="#configuration" id="toc-entry-1">Configuration</a></li>
<li><a class="reference internal" href="#usage" id="toc-entry-2">Usage</a></li>
<li><a class="reference internal" href="#bug-tracker" id="toc-entry-3">Bug Tracker</a></li>
<li><a class="reference internal" href="#credits" id="toc-entry-4">Credits</a><ul>
<li><a class="reference internal" href="#authors" id="toc-entry-5">Authors</a></li>
<li><a class="reference internal" href="#contributors" id="toc-entry-6">Contributors</a></li>
<li><a class="reference internal" href="#maintainers" id="toc-entry-7">Maintainers</a></li>
</ul>
</li>
</ul>
</div>
<div class="section" id="configuration">
<h1><a class="toc-backref" href="#toc-entry-1">Configuration</a></h1>
<p><strong>Configurable Data Purging:</strong> To prevent database bloat, the system
features scheduled actions that purge old logs based on configurable
system parameters (purge_period_success and purge_period_general).</p>
<p><strong>Best Practice for Data Retention Policies:</strong> Correctly configure the
purge_period_success (e.g., 5 days) and purge_period_general (e.g., 40
days) system parameters. Successful logs don’t need to be kept for long
since the actual attendance is recorded, while failed logs should be
kept long enough to be investigated but not indefinitely.</p>
</div>
<div class="section" id="usage">
<h1><a class="toc-backref" href="#toc-entry-2">Usage</a></h1>
<p><strong>Monitoring RFID Attendances</strong></p>
<p>To track all attendance data transmitted by your external RFID device,
navigate to <strong>Attendances &gt; Reporting &gt; Logs</strong>. This view provides a
complete overview of both successful and failed synchronizations.</p>
<ul class="simple">
<li><strong>Successful Syncs:</strong> These records are retained in the log for a
specific duration, which is managed by an automated scheduled job.</li>
<li><strong>Failed Syncs:</strong> Any synchronization errors will be flagged as
“Failed”. Clicking on a failed record opens a troubleshooting wizard
to help you resolve the issue quickly:<ol class="arabic">
<li><strong>Unrecognized Card (“No employee found with card [x]”):</strong> Using
the wizard, you can assign the unregistered card to an employee,
ignore the clocking event entirely, or prompt Odoo to retry the
sync.</li>
<li><strong>Validation Errors (e.g., Missing Check-out):</strong> This error occurs
for example if an employee’s previous attendance record is
incomplete (e.g., it has a check-in but no corresponding
check-out). To resolve this, you must first manually correct the
previous record. Once you have fixed the underlying issue of a
failed sync, you can process the pending attendance record in one
of two ways:<ul>
<li><strong>Manual Retry (Recommended):</strong> Click “Retry” within the wizard
and then the new button that appears in the “Logs” view. This
instantly syncs the event, allowing you to confirm immediately
that the clocking was successfully added to the database.</li>
<li><strong>Automatic Retry:</strong> Simply wait for the scheduled cron job to
automatically retry and process the sync in the background.</li>
</ul>
</li>
</ol>
</li>
</ul>
</div>
<div class="section" id="bug-tracker">
<h1><a class="toc-backref" href="#toc-entry-3">Bug Tracker</a></h1>
<p>Bugs are tracked on <a class="reference external" href="https://github.com/OCA/hr-attendance/issues">GitHub Issues</a>.
In case of trouble, please check there if your issue has already been reported.
If you spotted it first, help us to smash it by providing a detailed and welcomed
<a class="reference external" href="https://github.com/OCA/hr-attendance/issues/new?body=module:%20hr_attendance_rfid_log%0Aversion:%2017.0%0A%0A**Steps%20to%20reproduce**%0A-%20...%0A%0A**Current%20behavior**%0A%0A**Expected%20behavior**">feedback</a>.</p>
<p>Do not contact contributors directly about support or help with technical issues.</p>
</div>
<div class="section" id="credits">
<h1><a class="toc-backref" href="#toc-entry-4">Credits</a></h1>
<div class="section" id="authors">
<h2><a class="toc-backref" href="#toc-entry-5">Authors</a></h2>
<ul class="simple">
<li>nurzeit.de</li>
</ul>
</div>
<div class="section" id="contributors">
<h2><a class="toc-backref" href="#toc-entry-6">Contributors</a></h2>
<ul class="simple">
<li>Luis Burrel &lt;<a class="reference external" href="mailto:luis&#64;nurzeit.de">luis&#64;nurzeit.de</a>&gt;</li>
<li>Jordi Ballester Alomar &lt;<a class="reference external" href="mailto:jordi.ballester&#64;forgeflow.com">jordi.ballester&#64;forgeflow.com</a>&gt;</li>
<li>Aaron Henriquez &lt;<a class="reference external" href="mailto:ahforgeflow&#64;forgeflow.com">ahforgeflow&#64;forgeflow.com</a>&gt;</li>
</ul>
</div>
<div class="section" id="maintainers">
<h2><a class="toc-backref" href="#toc-entry-7">Maintainers</a></h2>
<p>This module is maintained by the OCA.</p>
<a class="reference external image-reference" href="https://odoo-community.org">
<img alt="Odoo Community Association" src="https://odoo-community.org/logo.png" />
</a>
<p>OCA, or the Odoo Community Association, is a nonprofit organization whose
mission is to support the collaborative development of Odoo features and
promote its widespread use.</p>
<p>Current <a class="reference external" href="https://odoo-community.org/page/maintainer-role">maintainer</a>:</p>
<p><a class="reference external image-reference" href="https://github.com/lubusax"><img alt="lubusax" src="https://github.com/lubusax.png?size=40px" /></a></p>
<p>This module is part of the <a class="reference external" href="https://github.com/OCA/hr-attendance/tree/17.0/hr_attendance_rfid_log">OCA/hr-attendance</a> project on GitHub.</p>
<p>You are welcome to contribute. To learn how please visit <a class="reference external" href="https://odoo-community.org/page/Contribute">https://odoo-community.org/page/Contribute</a>.</p>
</div>
</div>
</div>
</body>
</html>

```

### File: `tests/__init__.py`
```python
from . import test_hr_attendance_rfid_log

```

### File: `tests/test_hr_attendance_rfid_log.py`
```python
# Copyright 2026 nurzeit.de
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html
from datetime import datetime, timedelta

from odoo import fields
from odoo.tests.common import TransactionCase
from odoo.tools.misc import mute_logger


class TestHrAttendance(TransactionCase):
    def setUp(self):
        super().setUp()
        self.employee_model = self.env["hr.employee"]
        self.test_employee = self.employee_model.create(
            {
                "name": "Test Employee",
            }  # noqa: E231
        )
        self.rfid_card_code = "5b3f5"
        self.test_employee.rfid_card_code = self.rfid_card_code
        self.log_failed = self.env["hr.attendance.rfid.log"].create(
            {
                "state": "failed",
                "rfid_card_code": self.rfid_card_code,
                "employee_id": self.test_employee.id,
            }
        )

    def test_create_log(self):
        """Valid employee"""
        res = self.employee_model.register_attendance(self.rfid_card_code)
        self.assertTrue("in_rfid_log" in res and res["in_rfid_log"])

    def _get_wizard(self):
        wizard = self.env["hr.attendance.rfid.log.assign.employee"].create(
            {
                "rfid_card_code": self.rfid_card_code,
                # You need to provide the ID of the attendance RFID log here
                "hr_attendance_rfid_log_id": self.log_failed.id,
                "employee_id": self.test_employee.id,
            }
        )
        return wizard

    @mute_logger("odoo.addons.hr_attendance_rfid.models.hr_employee")
    def test_exception_code(self):
        """Checkout is created for a future datetime"""
        self.env["hr.attendance"].create(
            {
                "employee_id": self.test_employee.id,
                "check_in": fields.Date.today(),
                "check_out": fields.Datetime.to_string(
                    datetime.today() + timedelta(hours=8)
                ),
            }
        )
        self.test_employee.write({"attendance_state": "checked_in"})
        res = self.employee_model.register_attendance(self.rfid_card_code)
        self.assertNotEqual(res.get("error_message", ""), "")

    def test_action_open_wizard_assign_employee(self):
        action = self.log_failed.action_open_wizard_assign_employee()
        self.assertEqual(action.get("type"), "ir.actions.act_window")
        self.assertEqual(
            action.get("res_model"), "hr.attendance.rfid.log.assign.employee"
        )
        self.assertEqual(
            action.get("context", {}).get("default_rfid_card_code"), self.rfid_card_code
        )
        self.assertEqual(
            action.get("context", {}).get("default_hr_attendance_rfid_log_id"),
            self.log_failed.id,
        )

    def test_action_set_to_retry_state(self):
        self.assertEqual(self.log_failed.state, "failed")
        self.log_failed.action_set_to_retry_state()
        self.assertEqual(self.log_failed.state, "retry")

    def test_action_set_to_ignore_state(self):
        self.assertEqual(self.log_failed.state, "failed")
        self.log_failed.action_set_to_ignore_state()
        self.assertEqual(self.log_failed.state, "ignore")

    def test_action_retry_now(self):
        self.log_failed.action_set_to_retry_state()
        initial_retry_counter = self.log_failed.retry_counter
        self.log_failed.action_retry_now()
        self.assertEqual(self.log_failed.retry_counter, initial_retry_counter + 1)
        # register_attendance_with_log changes state to success if logged
        self.assertEqual(self.log_failed.state, "success")

    def test_retry_attendance_rfid_log(self):
        self.log_failed.action_set_to_retry_state()
        self.assertEqual(self.log_failed.state, "retry")
        self.env["hr.attendance.rfid.log"]._retry_attendance_rfid_log()
        self.assertEqual(self.log_failed.state, "success")

    def test_purge_attendance_rfid_log(self):
        Log = self.env["hr.attendance.rfid.log"]
        current_date = fields.Datetime.now()

        # Test success logs older than purge_period_success
        log_success_old = Log.create(
            {
                "state": "success",
                "rfid_card_code": self.rfid_card_code,
                "timestamp": current_date - timedelta(days=6),
            }
        )

        # Test failed logs older than purge_period_general
        log_failed_old = Log.create(
            {
                "state": "failed",
                "rfid_card_code": self.rfid_card_code,
                "timestamp": current_date - timedelta(days=41),
            }
        )

        # Test success logs newer than purge_period_success
        log_success_new = Log.create(
            {
                "state": "success",
                "rfid_card_code": self.rfid_card_code,
                "timestamp": current_date - timedelta(days=4),
            }
        )

        Log._purge_attendance_rfid_log()

        self.assertFalse(log_success_old.exists())
        self.assertFalse(log_failed_old.exists())
        self.assertTrue(log_success_new.exists())
        self.assertTrue(
            self.log_failed.exists()
        )  # created today, so newer than 40 days

    def test_wizard_action_assign_employee(self):
        wizard = self._get_wizard()
        # assign to another employee to test changing
        another_employee = self.employee_model.create({"name": "Another Employee"})
        wizard.employee_id = another_employee.id

        # Test assign employee
        res = wizard.action_assign_employee()

        # Check return action
        self.assertEqual(res.get("type"), "ir.actions.act_window_close")

        # Check if RFID card code is assigned to new employee
        self.assertEqual(another_employee.rfid_card_code, self.rfid_card_code)

        # Check if log is updated
        self.assertEqual(self.log_failed.employee_id.id, another_employee.id)
        self.assertEqual(self.log_failed.state, "retry")

    def test_wizard_on_change_employee_id(self):
        wizard = self._get_wizard()

        # Initially, test_employee has rfid_card_code
        self.assertTrue(self.test_employee.rfid_card_code)

        wizard.employee_id = self.test_employee.id
        wizard.on_change_employee_id()
        self.assertTrue("already a RFID card code assigned" in wizard.warning_message)

        # Create an employee without rfid_card_code
        employee_no_rfid = self.employee_model.create({"name": "No RFID Employee"})
        wizard.employee_id = employee_no_rfid.id
        wizard.on_change_employee_id()
        self.assertEqual(wizard.warning_message, "")

    def test_employee_register_attendance_with_existing_log(self):
        # Test passing an existing log to register_attendance
        log_vals = {
            "state": "failed",
            "rfid_card_code": self.rfid_card_code,
            "employee_id": self.test_employee.id,
        }
        existing_log = self.env["hr.attendance.rfid.log"].create(log_vals)
        res = self.employee_model.register_attendance(
            self.rfid_card_code, log=existing_log
        )

        self.assertTrue("in_rfid_log" in res and res["in_rfid_log"])
        self.assertEqual(
            existing_log.state, "success" if res.get("logged") else "failed"
        )

    def test_employee_register_attendance_with_log_freeze_time(self):
        # Test register_attendance_with_log which uses freezegun
        # We need a log with a specific time
        past_time = fields.Datetime.now() - timedelta(hours=5)
        log = self.env["hr.attendance.rfid.log"].create(
            {
                "state": "failed",
                "rfid_card_code": self.rfid_card_code,
                "timestamp": past_time,
            }
        )

        res = self.employee_model.register_attendance_with_log(log)
        self.assertTrue("in_rfid_log" in res and res["in_rfid_log"])

        # In register_attendance_with_log, it registers attendance
        # at the time of the log
        attendance = self.env["hr.attendance"].search(
            [("employee_id", "=", self.test_employee.id)], order="id desc", limit=1
        )
        if attendance:
            # Depending on if it checked in or out, check the time
            time_to_check = (
                attendance.check_in if attendance.check_in else attendance.check_out
            )
            # The time should be very close to past_time
            self.assertTrue(abs((time_to_check - past_time).total_seconds()) < 60)

    def test_purge_attendance_rfid_log_bad_config(self):
        self.env["ir.config_parameter"].sudo().set_param(
            "hr_attendance_rfid_log.purge_period_success", "invalid_int"
        )
        self.env["hr.attendance.rfid.log"]._purge_attendance_rfid_log()

        # Verify it fell back to default
        success_param = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("hr_attendance_rfid_log.purge_period_success")
        )
        self.assertEqual(success_param, "5")

    def test_explicit_retry_log_processing(self):
        # explicitly creates a log record, forces its state to 'retry'
        # and runs the method
        log = self.env["hr.attendance.rfid.log"].create(
            {
                "state": "retry",
                "rfid_card_code": self.rfid_card_code,
                "employee_id": self.test_employee.id,
            }
        )
        self.env["hr.attendance.rfid.log"]._retry_attendance_rfid_log()
        self.assertEqual(log.state, "success")

```

### File: `views/hr_attendance_log_view.xml`
```xml
<?xml version="1.0" encoding="utf-8" ?>
<odoo>
    <record id="hr_attendance_rfid_log_view_list" model="ir.ui.view">
        <field name="name">hr.attendance.rfid.log.list</field>
        <field name="model">hr.attendance.rfid.log</field>
        <field name="arch" type="xml">
            <list decoration-danger="state == 'failed'">
                <field name="state" />
                <field name="retry_counter" />
                <field name="timestamp" />
                <field name="employee_id" />
                <field name="rfid_card_code" />
                <field name="action" invisible="state == 'retry'" />
                <field name="error_message" invisible="state != 'failed'" />
                <field name="create_date" />
                    <button
                    name="action_retry_now"
                    class="btn btn-primary"
                    string="Retry Now"
                    type="object"
                    invisible="state != 'retry'"
                />
            </list>
        </field>
    </record>
    <record id="hr_attendance_rfid_log_view_form" model="ir.ui.view">
        <field name="name">hr.attendance.rfid.log.form</field>
        <field name="model">hr.attendance.rfid.log</field>
        <field name="arch" type="xml">
            <form>
                <header>
                    <field name="state" invisible="1" />
                    <button
                        name="action_open_wizard_assign_employee"
                        class="btn btn-primary"
                        string="Assign Employee"
                        invisible="employee_id != False"
                        type="object"
                    />
                    <button
                        name="action_set_to_retry_state"
                        class="btn btn-primary"
                        string="Retry"
                        invisible="(state == 'success' or state == 'retry') and employee_id != False"
                        type="object"
                    />
                    <button
                        name="action_set_to_ignore_state"
                        class="btn btn-danger"
                        string="Ignore"
                        invisible="state == 'success' and employee_id != False"
                        type="object"
                    />
                    <field name="state" widget="statusbar" />
                </header>
                <sheet>
                    <group>
                        <group>
                            <field
                                name="employee_id"
                                invisible="employee_id == False"
                            />
                            <field name="rfid_card_code" />
                            <field name="timestamp" />
                        </group>
                    </group>
                    <group string="Result" name="result" invisible="state != 'success'">
                        <group>
                            <field name="action" />
                        </group>
                    </group>
                    <group string="Error" name="error" invisible="state != 'failed'">
                        <group>
                            <field
                                name="error_message"
                                nolabel="1"
                                widget="ace"
                                options="{'mode': 'python'}"
                            />
                        </group>
                    </group>
                </sheet>
            </form>
        </field>
    </record>
    <record id="action_rfid_attendance_log" model="ir.actions.act_window">
        <field name="name">RFID Attendance Logs</field>
        <field name="res_model">hr.attendance.rfid.log</field>
        <field name="type">ir.actions.act_window</field>
        <field name="view_mode">list,form</field>
        <field name="view_id" ref="hr_attendance_rfid_log_view_list" />
    </record>
<menuitem
        name="RFID Logs"
        sequence="80"
        id="menu_rfid_log"
        action="action_rfid_attendance_log"
        parent="hr_attendance.menu_hr_attendance_root"
    />
</odoo>

```

### File: `wizards/hr_rfid_log_assign_employee.py`
```python
# Copyright 2026 nurzeit.de
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class RfidLogAssignEmployee(models.TransientModel):
    _name = "hr.attendance.rfid.log.assign.employee"
    _description = "Assign an employee to a RFID card code"

    hr_attendance_rfid_log_id = fields.Many2one(
        "hr.attendance.rfid.log", string="Log", required=True
    )
    rfid_card_code = fields.Char(readonly=True, string="RFID Card Code", copy=False)
    employee_id = fields.Many2one("hr.employee", string="Employee", required=True)
    warning_message = fields.Char()

    def action_assign_employee(self):
        self.employee_id.rfid_card_code = self.rfid_card_code
        records = self.env["hr.attendance.rfid.log"].search(
            [
                ("rfid_card_code", "=", self.rfid_card_code),
            ]  # noqa: E231
        )
        records.sudo().write(
            {
                "employee_id": self.employee_id.id,
                "state": "retry",
            }  # noqa: E231
        )
        return {"type": "ir.actions.act_window_close"}

    @api.onchange("employee_id")
    def on_change_employee_id(self):
        for record in self:
            if record.employee_id.rfid_card_code:
                record.warning_message = _(
                    "Employee has already a RFID card code assigned. "
                    "If you continue it will be overwritten."
                )
            else:
                record.warning_message = ""

```

### File: `wizards/hr_rfid_log_assign_employee.xml`
```xml
<?xml version="1.0" encoding="utf-8" ?>
<odoo>
    <record id="hr_attendance_rfid_log_assign_employee_view_form" model="ir.ui.view">
        <field name="name">hr.attendance.rfid.log.assign.employee.form</field>
        <field name="model">hr.attendance.rfid.log.assign.employee</field>
        <field name="type">form</field>
        <field name="arch" type="xml">
            <form>
                <group>
                    <field name="hr_attendance_rfid_log_id" invisible="1" />
                    <field
                        name="warning_message"
                        invisible="not employee_id or warning_message == ''"
                        class="o_alert o_alert-danger"
                    />
                    <field name="rfid_card_code" />
                    <field name="employee_id" />
                </group>
                <footer>
                    <button
                        name="action_assign_employee"
                        class="btn btn-primary"
                        string="Assign"
                        type="object"
                    />
                or
                    <button string="Close" class="btn-default" special="cancel" />
                </footer>
            </form>
        </field>
    </record>
    <record id="action_hr_rfid_log_assign_employee" model="ir.actions.act_window">
        <field name="name">Assign Employee</field>
        <field name="res_model">hr.attendance.rfid.log.assign.employee</field>
        <field name="view_mode">form</field>
        <field name="target">new</field>
        <field name="view_id" ref="hr_attendance_rfid_log_assign_employee_view_form" />
    </record>
</odoo>

```

### File: `wizards/__init__.py`
```python
# Copyright 2023 thingsintouch.com
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from . import hr_rfid_log_assign_employee

```

