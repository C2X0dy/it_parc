from odoo import models, fields, api

class ITSoftware(models.Model):
    _name = 'it.software'
    _description = 'IT Software'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Name', required=True)
    version = fields.Char(string='Version')
    publisher = fields.Char(string='Publisher')
    license_type = fields.Selection([
        ('open_source', 'Open Source'),
        ('proprietary', 'Proprietary'),
        ('subscription', 'Subscription')
    ], string='License Type')
    expiration_date = fields.Date(string='Expiration Date')
    asset_ids = fields.Many2many('it.asset', string='Installed On')
    partner_id = fields.Many2one('res.partner', string='Customer')
    notes = fields.Text(string='Notes')
    license_count = fields.Integer(string='Nombre de licences', compute='_compute_license_count')
    license_ids = fields.One2many('it.license', 'software_id', string='Licences')

    @api.depends('license_ids')
    def _compute_license_count(self):
        for software in self:
            software.license_count = len(software.license_ids)

    def action_view_licenses(self):
        self.ensure_one()
        return {
            'name': _('Licences'),
            'view_mode': 'tree,form',
            'res_model': 'it.license',
            'domain': [('software_id', '=', self.id)],
            'type': 'ir.actions.act_window',
            'context': {'default_software_id': self.id}
        }

