import boto3
import functools
import contextvars
import asyncio

from .utils import getAwsFilters
from .config import *
from lazycls.types import *
from lazycls.funcs import caseCamelToSnake
from lazycls import create_lazycls, BaseCls


from .logz import get_logger
logger = get_logger('Aws')

async def _to_thread(func, *args, **kwargs):
    """Asynchronously run function *func* in a separate thread.
    Any *args and **kwargs supplied for this function are directly passed
    to *func*. Also, the current :class:`contextvars.Context` is propogated,
    allowing context variables from the main thread to be accessed in the
    separate thread.
    Return a coroutine that can be awaited to get the eventual result of *func*.
    """
    loop = asyncio.events.get_running_loop()
    ctx = contextvars.copy_context()
    func_call = functools.partial(ctx.run, func, *args, **kwargs)
    return await loop.run_in_executor(None, func_call)


def convert_to_cls(resp: DictAny, submodule: str) -> List[Type[BaseCls]]:
    _ = resp.pop('ResponseMetadata', None)
    moduleName = f'Aws{submodule.capitalize()}'
    for key, vals in resp.items():
        modKey = f'{moduleName}{key}'
        if isinstance(vals, list): vals = [create_lazycls(modKey, v, modulename='Aws') for v in vals]
        else: vals = create_lazycls(modKey, vals, modulename='Aws')
        resp[key] = vals
    return resp

## Does not work atm.
def expand_boto3_resource(obj, name: str, resource: boto3.resource):
    for operation in resource.meta.resource_model:
        print(operation)
        operation_camelcase = caseCamelToSnake(operation)
        sync_func = getattr(resource, operation_camelcase)
        setattr(obj, f'{name}_{operation_camelcase}', sync_func)
    return obj


def asyncify_boto3_obj(obj, name: str, client: boto3.client):
    """
    Adds async methods to each of the sync methods of a boto3 client.
    Keyword arguments
    obj -- the object class that will be modified
    name -- name to be set
    client -- The client to add sync methods to. Notice that the client
        will be updated in place, and will also be returned as a return
        value.
    Returns:
    The same obj.
    """
    def create_async_func(base_func):
        async def async_func(*args, filters: DictAny = None, filter_args: DictAny = {}, as_cls: bool = AutoCls, **kwargs):
            if filters: 
                if filter_args: filters.update(filter_args)
                kwargs['Filters'] = getAwsFilters(**filters)
            resp = await _to_thread(base_func, *args, **kwargs)
            if as_cls: resp = convert_to_cls(resp, submodule=name)
            return resp

        return async_func

    def create_sync_func(base_func):
        def sync_func(*args, filters: DictAny = None, filter_args: DictAny = {}, as_cls: bool = AutoCls, **kwargs):
            if filters: 
                if filter_args: filters.update(filter_args)
                kwargs['Filters'] = getAwsFilters(**filters)
            resp = base_func(*args, **kwargs)
            if as_cls: resp = convert_to_cls(resp, submodule=name)
            return resp
        return sync_func

    for operation in client._service_model.operation_names:
        operation_camelcase = caseCamelToSnake(operation)
        base_func = getattr(client, operation_camelcase)
        sync_func = create_sync_func(base_func)
        async_func = create_async_func(base_func)
        setattr(obj, f'{name}_{operation_camelcase}', sync_func)
        setattr(obj, f'async_{name}_{operation_camelcase}', async_func)
        
    return obj


class AwsBaseClient:
    def __init__(self, clients: DictAny = None, resources: DictAny = None, region: str = AwsRegion, boto_kwargs: DictAny = {}):
        clients = clients or DefaultClients
        resources = resources or DefaultResources
        self._region = region
        self._sess: boto3.Session = None
        self._clients: Dict[str, boto3.client] = {}
        self._resources: Dict[str, boto3.resource] = {}
        self._clients_to_load = clients
        self._resources_to_load = resources
        self._boto_kwargs: DictAny = boto_kwargs
        self._setup_clients()
        self._setup_resources()

    @property
    def sess(self):
        if not self._sess: self._sess = boto3.session.Session(region_name=self._region, **self._boto_kwargs)
        return self._sess
    
    def _setup_clients(self):
        for name, client_name in self._clients_to_load.items():
            self._clients[name] = self.sess.client(client_name)
            asyncify_boto3_obj(self, name, self._clients[name])
    
    def _setup_resources(self):
        for name, resource_name in self._resources_to_load.items():
            self._resources[name] = self.sess.resource(resource_name)
            self.__dict__[name] = self._resources[name]
    
    def getClient(self, name: str, **kwargs) -> boto3.client:
        if not self._clients.get(name):
            self._clients[name] = self.sess.client(name, **kwargs)
            try: self._clients[name] = asyncify_boto3_obj(self, name, self._clients[name])
            except: return None
        return self._clients[name]
    
    def getResource(self, name: str, **kwargs) -> boto3.resource:
        if not self._resources.get(name): 
            try: 
                self._resources[name] = self.sess.resource(name, **kwargs)
                self.__dict__[name] = self._resources[name]
            except Exception as e: 
                logger.error(e)
                return None
        return self._resources[name]


class AwsClient:
    v1: AwsBaseClient = AwsBaseClient()

    @classmethod
    def reset(cls, *args, **kwargs):
        cls.v1  = AwsBaseClient(*args, **kwargs)


__all__ = [
    'AwsClient',
    'AwsBaseClient'
]