# Copyright 2026 - nurzeit.de
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

from odoo import api, models


class HrAttendance(models.Model):
    _inherit = "hr.attendance"

    @api.model_create_multi
    def create(self, vals_list):
        custom_time = self.env.context.get('rfid_custom_timestamp')
        if custom_time:
            for vals in vals_list:
                if 'check_in' in vals:
                    vals['check_in'] = custom_time
        return super().create(vals_list)

    def write(self, vals):
        custom_time = self.env.context.get('rfid_custom_timestamp')
        if custom_time and 'check_out' in vals:
            vals['check_out'] = custom_time
        return super().write(vals)