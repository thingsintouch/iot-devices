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