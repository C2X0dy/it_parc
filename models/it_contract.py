from odoo import api, fields, models, _
from dateutil.relativedelta import relativedelta
from datetime import timedelta
import base64
from odoo.exceptions import UserError

class ITContract(models.Model):
    _name = 'it.contract'
    _description = 'IT Maintenance Contract'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    name = fields.Char(string='Référence', required=True, copy=False)
    partner_id = fields.Many2one('res.partner', string='Client', required=True)
    description = fields.Text(string='Description')
    
    start_date = fields.Date(string='Date de début', required=True)
    end_date = fields.Date(string='Date de fin', required=True)
    
    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('active', 'Actif'),
        ('expired', 'Expiré'),
        ('cancelled', 'Annulé')
    ], string='État', default='draft', tracking=True)
    
    asset_ids = fields.Many2many('it.asset', string='Équipements couverts')
    
    # Champs pour la facturation
    product_id = fields.Many2one('product.product', string='Service', domain=[('type', '=', 'service')])
    amount = fields.Float(string='Montant du contrat')
    billing_frequency = fields.Selection([
        ('monthly', 'Mensuel'),
        ('quarterly', 'Trimestriel'),
        ('semi_annual', 'Semestriel'),
        ('annual', 'Annuel')
    ], string='Fréquence de facturation', default='monthly', required=True)
    next_invoice_date = fields.Date(string='Prochaine date de facturation')
    
    invoice_ids = fields.One2many('account.move', 'contract_id', string='Factures')
    invoice_count = fields.Integer(string='Nombre de factures', compute='_compute_invoice_count')
    
    expiry_alert = fields.Boolean(string="Alerte d'expiration", compute='_compute_expiry_alert', store=True)
    
    # Champs complémentaires pour la facturation avancée
    extra_service_ids = fields.One2many('it.contract.service', 'contract_id', string='Services supplémentaires')
    discount_rate = fields.Float(string='Taux de remise (%)', default=0.0)
    discount_amount = fields.Float(string='Montant remise fixe')
    price_per_asset = fields.Float(string='Prix par équipement', help="Si défini, le montant du contrat sera calculé en fonction du nombre d'équipements")
    auto_invoice_send = fields.Boolean(string='Envoi auto. des factures', default=True)
    
    # Conditions particulières
    has_special_conditions = fields.Boolean(string='Conditions particulières')
    special_conditions = fields.Text(string='Description des conditions')
    
    # Facturation des interventions hors forfait
    include_out_of_scope = fields.Boolean(string='Facturer interventions hors forfait', default=False)
    out_of_scope_count = fields.Integer(string='Interventions hors forfait', compute='_compute_out_of_scope_count')
    out_of_scope_intervention_ids = fields.Many2many('it.intervention', string='Interventions à facturer',
        domain="[('billable', '=', True), ('invoiced', '=', False), ('partner_id', '=', partner_id)]")
    
    @api.depends('invoice_ids')
    def _compute_invoice_count(self):
        for contract in self:
            contract.invoice_count = len(contract.invoice_ids)
    
    @api.depends('end_date')
    def _compute_expiry_alert(self):
        today = fields.Date.today()
        alert_date = today + timedelta(days=30)
        for contract in self:
            contract.expiry_alert = contract.end_date and contract.state == 'active' and contract.end_date <= alert_date
    
    def _compute_out_of_scope_count(self):
        for contract in self:
            contract.out_of_scope_count = self.env['it.intervention'].search_count([
                ('billable', '=', True),
                ('invoiced', '=', False),
                ('partner_id', '=', contract.partner_id.id)
            ])
    
    @api.model
    def _cron_generate_invoices(self):
        """Tâche planifiée pour générer automatiquement les factures"""
        today = fields.Date.today()
        contracts = self.search([
            ('state', '=', 'active'),
            ('next_invoice_date', '<=', today)
        ])
        
        for contract in contracts:
            invoice = self._create_invoice(contract)
            
            # Envoi automatique des factures par email si l'option est activée
            if contract.auto_invoice_send and invoice:
                template = self.env.ref('it_parc.email_template_it_contract_invoice', False)
                if template:
                    # Générer le PDF de la facture
                    report_action = self.env.ref('account.account_invoices')
                    pdf_content, content_type = report_action._render_qweb_pdf(invoice.id)
                    
                    # Créer un attachement avec le PDF
                    attachment_vals = {
                        'name': f"Facture_{invoice.name.replace('/', '_')}.pdf",
                        'datas': base64.b64encode(pdf_content),
                        'res_model': 'account.move',
                        'res_id': invoice.id,
                        'type': 'binary',
                    }
                    attachment = self.env['ir.attachment'].create(attachment_vals)
                    
                    # Envoyer l'email avec la pièce jointe
                    template.send_mail(
                        invoice.id, 
                        force_send=True,
                        email_values={'attachment_ids': [(4, attachment.id)]}
                    )
        
        return True
    
    def _create_invoice(self, contract):
        """Créer une facture pour le contrat avec toutes les options configurées"""
        # Créer l'entête de la facture
        invoice_vals = {
            'move_type': 'out_invoice',
            'partner_id': contract.partner_id.id,
            'invoice_date': fields.Date.today(),
            'invoice_origin': contract.name,
            'contract_id': contract.id,
            'narration': contract.special_conditions if contract.has_special_conditions else '',
        }
        
        invoice = self.env['account.move'].create(invoice_vals)
        invoice_lines = []
        
        # 1. Ligne pour le service de base du contrat
        base_amount = contract.amount
        
        # Calculer le montant en fonction du nombre d'équipements si configuré
        if contract.price_per_asset > 0 and contract.asset_ids:
            base_amount = contract.price_per_asset * len(contract.asset_ids)
        
        # Ajouter la ligne principale du contrat
        line_vals = {
            'product_id': contract.product_id.id,
            'name': f'Maintenance IT - {contract.name} ({self._get_frequency_display(contract.billing_frequency)})',
            'quantity': 1,
            'price_unit': base_amount,
            'move_id': invoice.id,
        }
        
        # Appliquer la remise si configurée
        if contract.discount_rate > 0:
            line_vals['discount'] = contract.discount_rate
        
        invoice_lines.append((0, 0, line_vals))
        
        # 2. Ajouter les services supplémentaires du contrat
        for service in contract.extra_service_ids:
            service_line = {
                'product_id': service.product_id.id,
                'name': service.name or service.product_id.name,
                'quantity': service.quantity,
                'price_unit': service.price_unit,
                'move_id': invoice.id,
            }
            invoice_lines.append((0, 0, service_line))
        
        # 3. Ajouter les interventions hors forfait si configuré
        if contract.include_out_of_scope and contract.out_of_scope_intervention_ids:
            for intervention in contract.out_of_scope_intervention_ids:
                # Calculer le temps passé en heures
                hours = 0
                if intervention.date_start and intervention.date_end:
                    delta = fields.Datetime.from_string(intervention.date_end) - fields.Datetime.from_string(intervention.date_start)
                    hours = delta.total_seconds() / 3600
                
                intervention_line = {
                    'product_id': self.env.ref('it_parc.product_intervention_service').id,
                    'name': f'Intervention {intervention.name} du {intervention.date_start}',
                    'quantity': hours,
                    'price_unit': intervention.hourly_rate or 75.0,
                    'move_id': invoice.id,
                }
                invoice_lines.append((0, 0, intervention_line))
                
                # Marquer l'intervention comme facturée
                intervention.write({'invoiced': True, 'invoice_id': invoice.id})
        
        # 4. Ajouter une ligne de remise fixe si configurée
        if contract.discount_amount > 0:
            discount_line = {
                'name': 'Remise contractuelle',
                'quantity': 1,
                'price_unit': -contract.discount_amount,  # Négatif pour une remise
                'move_id': invoice.id,
            }
            invoice_lines.append((0, 0, discount_line))
        
        # Mettre à jour la facture avec toutes les lignes
        invoice.write({'invoice_line_ids': invoice_lines})
        
        # Mettre à jour la prochaine date de facturation
        self.calculate_next_invoice_date()
        
        return invoice
    
    def _get_frequency_display(self, frequency):
        """Convertir la fréquence en texte lisible"""
        mapping = {
            'monthly': 'Mensuel',
            'quarterly': 'Trimestriel',
            'semi_annual': 'Semestriel',
            'annual': 'Annuel'
        }
        return mapping.get(frequency, '')
    
    def calculate_next_invoice_date(self):
        """Calcule la prochaine date de facturation en fonction de la fréquence"""
        for contract in self:
            if not contract.next_invoice_date:
                contract.next_invoice_date = contract.start_date
            else:
                if contract.billing_frequency == 'monthly':
                    contract.next_invoice_date = contract.next_invoice_date + relativedelta(months=1)
                elif contract.billing_frequency == 'quarterly':
                    contract.next_invoice_date = contract.next_invoice_date + relativedelta(months=3)
                elif contract.billing_frequency == 'semi_annual':
                    contract.next_invoice_date = contract.next_invoice_date + relativedelta(months=6)
                elif contract.billing_frequency == 'annual':
                    contract.next_invoice_date = contract.next_invoice_date + relativedelta(years=1)
    
    def action_view_billable_interventions(self):
        """Ouvrir une vue des interventions facturables pour ce client"""
        self.ensure_one()
        
        # Rechercher les interventions facturables non facturées pour ce client
        interventions = self.env['it.intervention'].search([
            ('billable', '=', True),
            ('invoiced', '=', False),
            ('partner_id', '=', self.partner_id.id)
        ])
        
        # Mettre à jour la liste des interventions à facturer
        self.out_of_scope_intervention_ids = [(6, 0, interventions.ids)]
        
        # Retourner l'action
        return {
            'name': _('Interventions facturables'),
            'type': 'ir.actions.act_window',
            'res_model': 'it.intervention',
            'view_mode': 'list,form',
            'domain': [('id', 'in', interventions.ids)],
            'context': {'default_billable': True}
        }
    
    def action_create_invoice_now(self):
        """Créer une facture immédiatement"""
        self.ensure_one()
        if self.state != 'active':
            raise UserError(_("Vous ne pouvez générer une facture que pour un contrat actif."))
        
        invoice = self._create_invoice(self)
        
        return {
            'name': _('Facture générée'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': invoice.id,
        }
    
    def action_view_invoices(self):
        """Ouvre une vue des factures liées à ce contrat"""
        self.ensure_one()
        
        action = {
            'name': _('Factures'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('contract_id', '=', self.id)],
            'context': {'default_contract_id': self.id, 'default_partner_id': self.partner_id.id}
        }
        
        return action