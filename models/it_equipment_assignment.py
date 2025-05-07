from odoo import api, fields, models

class ITEquipmentAssignment(models.Model):
    _name = 'it.equipment.assignment'
    _description = 'Affectation d\'équipement'
    
    equipment_id = fields.Many2one('it.equipment', string='Équipement', required=True)
    employee_id = fields.Many2one('res.partner', string='Utilisateur final', required=True)
    client_id = fields.Many2one('res.partner', string='Client')
    start_date = fields.Date(string='Date de début', default=fields.Date.today)
    end_date = fields.Date(string='Date de fin')
    notes = fields.Text(string='Notes')
    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('assigned', 'Assigné'),
        ('returned', 'Retourné')
    ], default='draft', string='État')
