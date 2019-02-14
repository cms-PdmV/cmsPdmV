import sys

class CountdownCache:
    def __init__(self, count=25):
        self.count = count
        self.__cache = {}
        self.__counter = {}

    def set(self, key, value, count=0):
        if count <= 0:
            self.__counter[key] = self.count
        else:
            self.__counter[key] = count

        self.__cache[key] = value

    def get(self, key):
        if key in self.__counter and self.__counter[key] <= 0:
            del self.__counter[key]
            if key in self.__cache:
                del self.__cache[key]

            return None

        if key in self.__cache:
            self.__counter[key] = self.__counter[key] - 1
            return self.__cache[key]

        return None

    def get_size(self):
        return sys.getsizeof(self.__cache) + sys.getsizeof(self.__counter)

    def get_length(self):
        return len(self.__cache)

    def clear(self):
        self.__cache.clear()
        self.__counter.clear()
