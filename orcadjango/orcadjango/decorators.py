import orca

def group(groupname='Group1'):
    """
    Decorates functions that will be injected into other functions.
    """
    def decorator(func):
        name = func.__name__
        orcafunc_wrapper = orca.orca._STEPS.get(name,
                                                orca.orca._INJECTABLES.get(name))
        orcafunc_wrapper.groupname = groupname
        return func
    return decorator