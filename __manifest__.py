{
    'name': 'Parc Informatique',
    'version': '1.0',
    'category': 'Services/IT',
    'summary': 'Gestion du parc informatique pour prestataires IT',
    'description': """
Gestion de Parc Informatique
============================
Module pour prestataires de services IT incluant:
- Gestion des équipements informatiques
- Suivi des contrats de service et de maintenance
- Gestion des incidents et interventions
- Facturation récurrente automatisée
    """,
    'author': 'Votre Nom',
    'depends': [
        'base',
        'mail',
        'account',
        'product',
    ],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        
        # Vues
        'views/it_asset_views.xml',
        'views/it_license_views.xml',
        'views/it_equipment_views.xml',
        # Commentez la ligne ci-dessous jusqu'à ce que vous ayez créé le fichier
        # 'views/it_equipment_assignment_views.xml',
        
        # Menu principal (dernier)
        'views/estate_menus.xml',
    ],
    'demo': [
        'data/it_asset_demo.xml',
    ],
    'application': True,
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
