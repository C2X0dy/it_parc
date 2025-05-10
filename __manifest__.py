{
    'name': 'IT Asset Management',
    'version': '1.0',
    'category': 'Services/IT',
    'summary': 'Manage IT assets, contracts and support tickets',
    'description': """
        This module allows you to manage your IT assets, maintenance contracts and support tickets.
        
        Features:
        - Track IT assets (hardware, software)
        - Manage maintenance contracts with automatic invoicing
        - Handle support tickets 
        - Plan technical interventions with technician scheduling
        - Customer portal for self-service
        - Integration with HR, Stock and Accounting
        - Asset depreciation and renewal planning
        - Automated alert system for contracts, warranties, licenses and maintenance
        - Automated invoice generation with flexible configuration
        - Enhanced customer management with detailed profiles and analytics
    """,
    'depends': [
        'base',
        'mail',
        'website',
        'portal',
        'web',
        'hr',
        'stock',
        'purchase',
        'account',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'data/cron_data.xml',
        'data/email_templates.xml',
        'data/communication_data.xml',  # Ajout de ce fichier
        'data/product_data.xml',
        'views/it_asset_views.xml', 
        'views/it_software_views.xml',
        'views/it_license_views.xml',  # Ajout du nouveau fichier de vues
        'views/it_ticket_views.xml',
        'views/it_contract_views.xml',
        'views/it_intervention_views.xml',
        'views/it_technician_views.xml',
        'views/it_dashboard_views.xml',
        'views/it_asset_depreciation_views.xml',
        'views/it_alert_views.xml',
        'views/it_customer_views.xml',
        'views/it_inbox_views.xml',  # Ajout de ce fichier
        'views/it_asset_lifecycle_views.xml',  # Vérifiez cette ligne aussi
        'views/menu_views.xml',
        'views/portal_templates.xml',
        'views/website_templates.xml',
        'views/website_menus.xml',
        'wizard/it_asset_renewal_wizard_views.xml',
        'wizard/it_customer_satisfaction_wizard_views.xml',  # Nouvelle vue
    ],
    'demo': [
        'demo/demo_data.xml',
    ],
    'application': True,
    'installable': True,
    'auto_install': False,
}
