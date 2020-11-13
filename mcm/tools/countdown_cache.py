import sys

class CountdownCache:
    def __init__(self, count=25):
        self.count = count
        self.__cache = {}

    def set(self, key, value, count=0):
        if count <= 0:
            count = self.count

        self.__cache[key] = {'value': value, 'count': count}

    def get(self, key):
        cached_pair = self.__cache.get(key)
        if not cached_pair:
            return None

        cached_pair['count'] -= 1
        if cached_pair['count'] < 0:
            self.__cache.pop(key, None)
            return None

        return cached_pair['value']

    def get_size(self):
        return sys.getsizeof(self.__cache)

    def get_length(self):
        return len(self.__cache)

    def clear(self):
        self.__cache.clear()
