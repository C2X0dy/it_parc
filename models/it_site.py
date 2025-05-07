from odoo import api, fields, models

class ITClientSite(models.Model):
    _name = 'it.client.site'
    _description = 'Site client'
    
    name = fields.Char(string='Nom du site', required=True)
    client_id = fields.Many2one('res.partner', string='Client', required=True)
    address = fields.Char(string='Adresse')
    city = fields.Char(string='Ville')
    zip_code = fields.Char(string='Code postal')
    country_id = fields.Many2one('res.country', string='Pays')
    equipment_ids = fields.One2many('it.equipment', 'site_id', string='Équipements')
    contact_id = fields.Many2one('res.partner', string='Contact sur site')
    notes = fields.Text(string='Notes')