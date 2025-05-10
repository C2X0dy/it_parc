from odoo import models, fields, api, _
from datetime import date, timedelta


class ITAssetRenewalWizard(models.TransientModel):
    _name = 'it.asset.renewal.wizard'
    _description = 'IT Asset Renewal Planning Wizard'
    
    # Filtres
    date_from = fields.Date(string='From Date', default=date.today())
    date_to = fields.Date(string='To Date', default=lambda self: date.today() + timedelta(days=365))
    priority = fields.Selection([
        ('all', 'All Priorities'),
        ('high_critical', 'High and Critical Only'),
        ('critical', 'Critical Only')
    ], string='Priority Filter', default='all')
    partner_id = fields.Many2one('res.partner', string='Customer')
    
    asset_ids = fields.Many2many('it.asset', string='Assets to Renew')
    
    @api.onchange('date_from', 'date_to', 'priority', 'partner_id')
    def _onchange_filters(self):
        domain = [
            ('recommended_renewal_date', '>=', self.date_from),
            ('recommended_renewal_date', '<=', self.date_to),
            ('renewal_planned', '=', False)
        ]
        
        if self.priority == 'high_critical':
            domain.append(('renewal_priority', 'in', ['high', 'critical']))
        elif self.priority == 'critical':
            domain.append(('renewal_priority', '=', 'critical'))
        
        if self.partner_id:
            domain.append(('partner_id', '=', self.partner_id.id))
        
        assets = self.env['it.asset'].search(domain)
        self.asset_ids = assets
    
    def action_generate_renewal_requests(self):
        """Génère des demandes de renouvellement pour les équipements sélectionnés"""
        if not self.asset_ids:
            return {'type': 'ir.actions.act_window_close'}
        
        ticket_ids = []
        
        for asset in self.asset_ids:
            # Créer un ticket de demande de renouvellement
            ticket = self.env['it.ticket'].create({
                'name': _('Renewal Request for %s') % asset.name,
                'partner_id': asset.partner_id.id,
                'asset_id': asset.id,
                'description': _('This is a bulk renewal request generated from the renewal planning wizard.\n\nRenewal Priority: %s\nRecommended Renewal Date: %s\nCurrent Value: %s\nPurchase Value: %s\nAge: %s months') % (
                    dict(asset._fields['renewal_priority'].selection).get(asset.renewal_priority), 
                    asset.recommended_renewal_date, asset.current_value, asset.purchase_value, asset.age_in_months
                ),
                'priority': '2' if asset.renewal_priority in ['high', 'critical'] else '1',
                'state': 'new',
            })
            
            ticket_ids.append(ticket.id)
            
            # Marquer comme planifié
            asset.write({
                'renewal_planned': True,
                'renewal_date': asset.recommended_renewal_date,
                'renewal_notes': _('Renewal request generated via batch planning on %s. Ticket: %s') % (
                    fields.Date.today(), ticket.name)
            })
        
        # Retourner une action pour voir les tickets créés
        return {
            'name': _('Generated Renewal Requests'),
            'view_mode': 'tree,form',
            'res_model': 'it.ticket',
            'domain': [('id', 'in', ticket_ids)],
            'type': 'ir.actions.act_window',
        }