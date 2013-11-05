import functools
from time import time as sys_time
from tornado.options import options
import cPickle
import logging
__all__ = ['cached', 'autocache']


class _Cache(object):
    """python-memcahe compatable instance cache
    """
    def __init__(self):
        self._app_cache = {}

    @classmethod
    def create_memcache(cls):
        if hasattr(cls, '_memcache'):
            return cls._memcache

        if hasattr(options, 'memcache_clients') and options.memcache_clients:
            try:
                import pylibmc
                cache = pylibmc.Client(options.memcache_clients,
                                       **options.memcache_kwargs)
                cls._memcache = cache
                return cls._memcache
            except ImportError:
                import memcache
                cache = memcache.Client(options.memcache_clients,
                                        **options.memcache_kwargs)
                cls._memcache = cache
                return cls._memcache
            except ImportError:
                cls._memcache = cls()
                return cls._memcache
        else:
            cls._memcache = cls()
            return cls._memcache

    @classmethod
    def create_redis(cls):
        if hasattr(cls, '_redis'):
            return cls._redis

        if hasattr(options, 'redis_clients') and options.redis_clients:
            try:
                import redis
                pool = redis.ConnectionPool(host=options.redis_clients['host'], port=options.redis_clients['port'])
                client =  redis.Redis(connection_pool=pool)
                cls._redis = client
                print "import redis.py, create default redis from "+ options.redis_clients['host']
                return cls._redis
             
            except ImportError as e:
                print "import error, create default redis member cache"
                raise e
                # cls._redis = cls()

                # return cls._redis
        else:
            print "has no redis client options, create default redis member cache"
            cls._redis = cls()
            return cls._redis


    def flush_all(self):
        self._app_cache = {}

    def set(self, key, val, time=0):
        key = str(key)
        if time < 0:
            time = 0

        self._app_cache[key] = (val, sys_time(), time)
        return val

    def get(self, key):
        key = str(key)
        _store = self._app_cache.get(key, None)
        if not _store:
            return None
        value, begin, seconds = _store
        if seconds and sys_time() > begin + seconds:
            del self._app_cache[key]
            return None
        return value

    def add(self, key, val, time=0):
        key = str(key)
        if key not in self._app_cache:
            return self.set(key, val, time)
        return self.get(key)

    def delete(self, key, time=0):
        key = str(key)
        if key in self._app_cache:
            del self._app_cache[key]
        return None

    def incr(self, key, delta=1):
        key = str(key)
        _store = self._app_cache.get(key, None)
        if not _store:
            return None

        value, begin, seconds = _store
        if seconds and sys_time() > begin + seconds:
            del self._app_cache[key]
            return None

        if isinstance(value, basestring):
            value = int(value)

        value = value + delta
        self.set(key, value)
        return value

    def decr(self, key, delta=1):
        return self.incr(key, -delta)

    def set_multi(self, mapping, time=0, key_prefix=''):
        for key, value in mapping.items():
            self.set('%s%s' % (key_prefix, key), value, time)

        return True

    def get_multi(self, keys, key_prefix=''):
        dct = {}
        for key in keys:
            value = self.get('%s%s' % (key_prefix, key))
            if value:
                dct[key] = value

        return dct

    def delete_multi(self, keys, time=0, key_prefix=''):
        for key in keys:
            self.delete('%s%s' % (key_prefix, key))

        return None


simple_cache = _Cache.create_memcache()
complex_cache =_Cache.create_redis()



class cached(object):
    """Cache decorator, an easy way to manage cache.
    The result key will be like: prefix:arg1-arg2
    """
    def __init__(self, prefix, time=0):
        self.prefix = prefix
        self.time = time

    def __call__(self, method):
        @functools.wraps(method)
        def wrapper(cls, *args):
            if args:
                key = self.prefix + ':' + '-'.join(map(str, args))
            else:
                key = self.prefix
            value = simple_cache.get(key)
            if value is None:
                value = method(cls, *args)
                simple_cache.set(key, value, self.time)
            return value
        return wrapper

def cached_clear(key):
    simple_cache.delete(key)

class autocached(object):
    """Cache decorator, an easy way to manage redis_cache.
    The result key will be like: prefix:arg1-arg2
    """
    def __init__(self, prefix, time=0):
        self.prefix = prefix
        self.time = time

    def __call__(self, method):
        @functools.wraps(method)
        def wrapper(cls, *args):
            key = self.prefix
            if args:
                key = self.prefix +  '-'.join(map(str, args))
            # else:
            #     key = self.prefix
            value = complex_cache.get(key)
            if value is None:
                value = method(cls, *args)
                v = cPickle.dumps(value)
                complex_cache.set(key, v, self.time)

            else:                
                logging.debug("complex_cache load from cache", key)
                value = cPickle.loads(value)
            return value
        return wrapper

def autocached_clear(key):
    logging.debug("complex_cache delete from cache", key)
    complex_cache.delete(key)
    # if isinstance(key, list):
    #     for k in key:
    #         complex_cache.delete(k)
    # else:
    #     complex_cache.delete(key)

def complex_cache_del(key_pattern):
    logging.debug("complex_cache delete pattern from cache", key_pattern)
    keys = complex_cache.keys(key_pattern)
    if keys:
        for key in keys:
            complex_cache.delete(key)
    else:
        logging.debug("del pattern keys is none")

def get_simple_cache_list(model, id_list, key_prefix, time=600, site_prefix=None):
    if site_prefix is None:
        site_prefix = options.site_cache_prefix
    if not id_list:
        return {}
    id_list = set(id_list)
    data = cache.get_multi(id_list, key_prefix=site_prefix+key_prefix)
    missing = id_list - set(data)
    if missing:
        dct = {}
        for item in model.query.filter_by(id__in=missing).all():
            dct[item.id] = item

        cache.set_multi(dct, time=time, key_prefix=key_prefix)
        data.update(dct)

    return data

def get_cache_list(model, id_list, key_hash, time=600, site_prefix=None):
    if site_prefix is None:
        site_prefix = options.site_cache_prefix
        
    if not id_list:
        return {}
    int_id_list = []
    data_id_list = []
    data_dict= dict()
    for id in id_list:
        int_id_list.append(str(id))
    # str_id_list = complex_cache.hkeys('people')
    # print str_id_list
    if len(int_id_list)>0:
        data = complex_cache.hmget(key_hash, int_id_list)
        # return data
        # id_list = set(id_list)
        
        
        for d in data:
            if d:
                d_value = cPickle.loads(d)
                #print d_value.id, d_value, type(d_value)
                data_dict[d_value.id] = d_value
                data_id_list.append(str(d_value.id))

    missing = set(int_id_list) - set(data_id_list)
    # print "missing", missing
    if len(missing) > 0:
        # print "missing2", missing
        dct = {}
        for item in model.query.filter_by(id__in=missing).all():
            # print "item id", item.id
            dct[item.id] = cPickle.dumps(item)
            data_dict[item.id] = item
        complex_cache.hmset(key_hash, dct)

    return data_dict
