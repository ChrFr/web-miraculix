from orcadjango.settings_pg import *

ORCA_MODULES['default'].update({'path': 'extractiontools.steps.extract_data'})

ORCA_MODULES['available'].update({
    'extraction tools': {
        'path': 'extractiontools.steps.extract_data',
        'description': ('collection of tools to extract data from the europe '
                        'database to a project database'),
        'template': 'extract_project'
    }
})

ALLOWED_HOSTS = ['localhost',
                 'miraculix.ggr-planung.de']