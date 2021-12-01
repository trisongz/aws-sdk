from lazycls.types import *

def getAwsFilters(string_only: bool = False, remove_null: bool = True, **filters) -> Dict[str, List[Any]]:
    kwargs = {'Filters': []}
    for key, values in filters.items():
        if not values and remove_null: continue
        if not isinstance(values, list): values = [values]
        if string_only: values = [str(v) for v in values]
        kwargs['Filters'].append({'Name': key, 'Values': values})
    return kwargs
