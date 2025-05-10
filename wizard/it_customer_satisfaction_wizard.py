from odoo import models, fields, api, _

class ITCustomerSatisfactionWizard(models.TransientModel):
    _name = 'it.customer.satisfaction.wizard'
    _description = 'Assistant d\'enquête de satisfaction'
    
    customer_id = fields.Many2one('it.customer', string='Client', required=True)
    template_id = fields.Many2one('mail.template', string='Modèle d\'email', 
                                 domain="[('model', '=', 'it.customer')]")
    subject = fields.Char(string='Sujet', required=True, default='Enquête de satisfaction')
    body = fields.Html(string='Corps du message', required=True, 
                      default="""
                        <p>Cher client,</p>
                        <p>Nous souhaitons recueillir votre avis sur nos services. Merci de prendre quelques minutes pour répondre à notre enquête de satisfaction.</p>
                        <p>Cliquez sur le lien suivant pour accéder à l'enquête : [LIEN_ENQUETE]</p>
                        <p>Cordialement,</p>
                        <p>L'équipe support</p>
                      """)
    
    @api.onchange('template_id')
    def _onchange_template_id(self):
        if self.template_id:
            self.subject = self.template_id.subject
            self.body = self.template_id.body_html
    
    def action_send_survey(self):
        self.ensure_one()
        # Logique d'envoi d'enquête
        # Vous pouvez intégrer avec le module 'survey' d'Odoo ou un service externe
        
        # Créer un mail.mail
        vals = {
            'subject': self.subject,
            'body_html': self.body,
            'email_to': self.customer_id.partner_id.email,
            'auto_delete': True,
        }
        mail = self.env['mail.mail'].create(vals)
        mail.send()
        
        # Créer une activité
        self.env['mail.activity'].create({
            'activity_type_id': self.env.ref('mail.mail_activity_data_todo').id,
            'note': _('Enquête de satisfaction envoyée'),
            'user_id': self.env.user.id,
            'res_id': self.customer_id.id,
            'res_model_id': self.env['ir.model'].search([('model', '=', 'it.customer')], limit=1).id,
            'summary': _('Suivi enquête satisfaction'),
            'date_deadline': fields.Date.today(),
        })
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': _('Enquête de satisfaction envoyée avec succès !'),
                'type': 'success',
                'sticky': False,
            }
        }