from odoo import models, fields, api

class ITLicense(models.Model):
    _name = 'it.license'
    _description = 'Licence Logicielle'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    name = fields.Char('Nom', required=True, tracking=True)
    product_id = fields.Many2one('product.product', string='Produit', 
                               domain=[('type', '=', 'service')], tracking=True)
    license_key = fields.Char('Clé de licence', tracking=True)
    start_date = fields.Date('Date de début', tracking=True)
    expiry_date = fields.Date('Date d\'expiration', tracking=True)
    seats = fields.Integer('Nombre de postes', default=1, tracking=True)
    company_id = fields.Many2one('res.company', string='Société', 
                               default=lambda self: self.env.company, required=True)
    
    client_id = fields.Many2one('res.partner', string='Client', 
                               domain=[('is_company', '=', True)], tracking=True)
    vendor_id = fields.Many2one('res.partner', string='Fournisseur', 
                               domain=[('is_company', '=', True)], tracking=True)
    
    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('active', 'Active'),
        ('expired', 'Expirée'),
        ('cancelled', 'Annulée')
    ], string='État', default='draft', tracking=True)
    
    notes = fields.Text('Notes')