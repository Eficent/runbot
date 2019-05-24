# -*- coding: utf-8 -*-
from psycopg2.extensions import AsIs
import re
import string

from .. import common
from odoo import api, fields, models
from odoo.exceptions import UserError

RE_POSTGRE_URI = re.compile(r'(?P<protocol>postgres|postgresql)://(?P<user>\w+)?:?(?P<password>[\w%s]+)?@?\w+' % string.punctuation.replace('@', ''))


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    runbot_workers = fields.Integer('Total number of workers')
    runbot_running_max = fields.Integer('Maximum number of running builds')
    runbot_timeout = fields.Integer('Max allowed step timeout (in seconds)')
    runbot_starting_port = fields.Integer('Starting port for running builds')
    runbot_domain = fields.Char('Runbot domain')
    runbot_max_age = fields.Integer('Max branch age (in days)')
    runbot_logdb_uri = fields.Char('Runbot URI for build logs')
    runbot_update_frequency = fields.Integer('Update frequency (in seconds)')

    @api.model
    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        get_param = self.env['ir.config_parameter'].sudo().get_param
        res.update(runbot_workers=int(get_param('runbot.runbot_workers', default=6)),
                   runbot_running_max=int(get_param('runbot.runbot_running_max', default=75)),
                   runbot_timeout=int(get_param('runbot.runbot_timeout', default=10000)),
                   runbot_starting_port=int(get_param('runbot.runbot_starting_port', default=2000)),
                   runbot_domain=get_param('runbot.runbot_domain', default=common.fqdn()),
                   runbot_max_age=int(get_param('runbot.runbot_max_age', default=30)),
                   runbot_logdb_uri=get_param('runbot.runbot_logdb_uri', default=False),
                   runbot_update_frequency=int(get_param('runbot.runbot_update_frequency', default=10)),
                   )
        return res

    @api.multi
    def set_values(self):
        super(ResConfigSettings, self).set_values()
        self.grant_access()
        set_param = self.env['ir.config_parameter'].sudo().set_param
        set_param("runbot.runbot_workers", self.runbot_workers)
        set_param("runbot.runbot_running_max", self.runbot_running_max)
        set_param("runbot.runbot_timeout", self.runbot_timeout)
        set_param("runbot.runbot_starting_port", self.runbot_starting_port)
        set_param("runbot.runbot_domain", self.runbot_domain)
        set_param("runbot.runbot_max_age", self.runbot_max_age)
        set_param("runbot.runbot_logdb_uri", self.runbot_logdb_uri)
        set_param('runbot.runbot_update_frequency', self.runbot_update_frequency)

    def grant_access(self):
        """ validate postgresql uri. See Connections URI:
            https://www.postgresql.org/docs/10/libpq-connect.html
            and grant access to the log user
        """
        logdb_uri = self.runbot_logdb_uri
        if not logdb_uri:
            return
        res = RE_POSTGRE_URI.search(logdb_uri)
        if not res:
            raise UserError('Invalid URI in the runbot build logs')
        if not res.group('user'):
            raise UserError('A username is required in the runbot URI for build logs')
        if not res.group('password'):
            raise UserError('A Password is required in the runbot URI for build logs')

        self.env.cr.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (res.group('user'), ))
        user_exists = self.env.cr.fetchone()
        if not user_exists:
            self.env.cr.execute("CREATE USER %s WITH PASSWORD %s", (AsIs(res.group('user')), res.group('password')))
        else:
            self.env.cr.execute("ALTER USER %s WITH PASSWORD %s", (AsIs(res.group('user')), res.group('password')))
        self.env.cr.execute("GRANT INSERT,SELECT,UPDATE ON ir_logging TO %s", (AsIs(res.group('user')), ))
        self.env.cr.execute("GRANT UPDATE ON ir_logging_id_seq TO %s", (AsIs(res.group('user')), ))
        self.env.cr.execute("GRANT UPDATE(triggered_result) on runbot_build to %s", (AsIs(res.group('user')), ))
        self.env.cr.execute("GRANT SELECT(id) on runbot_build to %s", (AsIs(res.group('user')), ))
