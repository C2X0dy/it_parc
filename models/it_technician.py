from odoo import models, fields, api

class ITTechnician(models.Model):
    _name = 'it.technician'
    _description = 'IT Technician'
    _inherits = {'hr.employee': 'employee_id'}
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    employee_id = fields.Many2one('hr.employee', required=True, ondelete='cascade', string='Employee')
    user_id = fields.Many2one('res.users', related='employee_id.user_id', string='User Account')
    
    skill_ids = fields.Many2many('it.skill', string='Technical Skills')
    certification_ids = fields.One2many('it.certification', 'technician_id', string='Certifications')
    
    intervention_count = fields.Integer(compute='_compute_intervention_count', string='Interventions')
    current_workload = fields.Float(compute='_compute_workload', string='Current Workload (%)')
    availability_status = fields.Selection([
        ('available', 'Available'),
        ('busy', 'Busy'),
        ('unavailable', 'Unavailable')
    ], compute='_compute_availability', string='Availability')
    
    @api.depends('user_id')
    def _compute_intervention_count(self):
        for tech in self:
            if tech.user_id:
                tech.intervention_count = self.env['it.intervention'].search_count([
                    ('technician_id', '=', tech.user_id.id),
                    ('state', 'in', ['planned', 'in_progress'])
                ])
            else:
                tech.intervention_count = 0
    
    @api.depends('user_id')
    def _compute_workload(self):
        for tech in self:
            # Calcul basé sur les heures planifiées vs heures standards de travail
            if tech.user_id:
                today = fields.Date.today()
                next_week = fields.Date.today() + fields.relativedelta(days=7)
                
                # Récupérer toutes les interventions planifiées pour la semaine
                interventions = self.env['it.intervention'].search([
                    ('technician_id', '=', tech.user_id.id),
                    ('state', 'in', ['planned', 'in_progress']),
                    ('date_start', '>=', today),
                    ('date_start', '<=', next_week)
                ])
                
                total_hours = sum(i.duration for i in interventions)
                # 40 heures étant une semaine standard de travail
                tech.current_workload = min(100, (total_hours / 40) * 100)
            else:
                tech.current_workload = 0
    
    @api.depends('current_workload')
    def _compute_availability(self):
        for tech in self:
            if not tech.user_id or self.env['hr.leave'].search_count([
                ('employee_id', '=', tech.employee_id.id),
                ('date_from', '<=', fields.Datetime.now()),
                ('date_to', '>=', fields.Datetime.now()),
                ('state', '=', 'validate')
            ]) > 0:
                tech.availability_status = 'unavailable'
            elif tech.current_workload >= 80:
                tech.availability_status = 'busy'
            else:
                tech.availability_status = 'available'

class ITSkill(models.Model):
    _name = 'it.skill'
    _description = 'IT Skill'
    
    name = fields.Char('Skill Name', required=True)
    description = fields.Text('Description')
    category = fields.Selection([
        ('hardware', 'Hardware'),
        ('software', 'Software'),
        ('network', 'Network'),
        ('security', 'Security'),
        ('other', 'Other')
    ], string='Category', required=True)

class ITCertification(models.Model):
    _name = 'it.certification'
    _description = 'IT Certification'
    
    name = fields.Char('Certification Name', required=True)
    organization = fields.Char('Issuing Organization', required=True)
    date_obtained = fields.Date('Date Obtained')
    expiry_date = fields.Date('Expiry Date')
    technician_id = fields.Many2one('it.technician', string='Technician')