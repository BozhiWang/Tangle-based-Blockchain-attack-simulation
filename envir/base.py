from envir.core import BoundClass
from envir.events import Event


class Put(Event):
    def __init__(self, resource):
        super(Put, self).__init__(resource._env)
        self.resource = resource
        self.proc = self.env.active_process

        resource.put_queue.append(self)
        self.callbacks.append(resource._trigger_get)
        resource._trigger_put(None)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.cancel()

    def cancel(self):
        if not self.triggered:
            self.resource.put_queue.remove(self)


class Get(Event):
    def __init__(self, resource):
        super(Get, self).__init__(resource._env)
        self.resource = resource
        self.proc = self.env.active_process

        resource.get_queue.append(self)
        self.callbacks.append(resource._trigger_put)
        resource._trigger_get(None)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.cancel()

    def cancel(self):
        if not self.triggered:
            self.resource.get_queue.remove(self)


class BaseResource(object):
    PutQueue = list
    GetQueue = list

    def __init__(self, env, capacity):
        self._env = env
        self._capacity = capacity
        self.put_queue = self.PutQueue()
        self.get_queue = self.GetQueue()

        BoundClass.bind_early(self)

    @property
    def capacity(self):
        return self._capacity

    put = BoundClass(Put)

    get = BoundClass(Get)

    def _do_put(self, event):
        raise NotImplementedError(self)

    def _trigger_put(self, get_event):
        idx = 0
        while idx < len(self.put_queue):
            put_event = self.put_queue[idx]
            proceed = self._do_put(put_event)
            if not put_event.triggered:
                idx += 1
            elif self.put_queue.pop(idx) != put_event:
                raise RuntimeError('Put queue invariant violated')

            if not proceed:
                break

    def _do_get(self, event):
        raise NotImplementedError(self)

    def _trigger_get(self, put_event):
        idx = 0
        while idx < len(self.get_queue):
            get_event = self.get_queue[idx]
            proceed = self._do_get(get_event)
            if not get_event.triggered:
                idx += 1
            elif self.get_queue.pop(idx) != get_event:
                raise RuntimeError('Get queue invariant violated')

            if not proceed:
                break
