from envir.core import BoundClass
import envir.base


class StorePut(envir.base.Put):

    def __init__(self, store, item):
        self.item = item
        super(StorePut, self).__init__(store)


class StoreGet(envir.base.Get):
    pass


class Store(envir.base.BaseResource):
    def __init__(self, env, capacity=float('inf')):
        if capacity <= 0:
            raise ValueError('"capacity" must be > 0.')

        super(Store, self).__init__(env, capacity)

        self.items = []

    put = BoundClass(StorePut)

    get = BoundClass(StoreGet)

    def _do_put(self, event):
        if len(self.items) < self._capacity:
            self.items.append(event.item)
            event.succeed()

    def _do_get(self, event):
        if self.items:
            event.succeed(self.items.pop(0))
