from odoo import models, fields, api

class AccountMove(models.Model):
    _inherit = 'account.move'
    
    contract_id = fields.Many2one('it.contract', string='Contrat IT', readonly=True)
    intervention_id = fields.Many2one('it.intervention', string='Intervention IT', readonly=True)
    asset_ids = fields.Many2many('it.asset', string='Équipements IT', readonly=True)
    
    def _get_it_assets_domain(self):
        """Domaine pour filtrer les équipements liés à ce partenaire"""
        return [('partner_id', '=', self.partner_id.id)]
    
    @api.onchange('partner_id')
    def _onchange_partner_it_assets(self):
        """Réinitialiser les équipements si le partenaire change"""
        if self.asset_ids:
            self.asset_ids = False
