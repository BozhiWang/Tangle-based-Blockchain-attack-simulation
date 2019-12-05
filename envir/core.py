import types
from heapq import heappush, heappop
from itertools import count

from envir.events import (AllOf, AnyOf, Event, Process, Timeout, URGENT,NORMAL)


Infinity = float('inf')


class BoundClass(object):
    def __init__(self, cls):
        self.cls = cls

    def __get__(self, obj, type=None):
        if obj is None:
            return self.cls
        return types.MethodType(self.cls, obj)

    @staticmethod
    def bind_early(instance):
        cls = type(instance)
        for name, obj in cls.__dict__.items():
            if type(obj) is BoundClass:
                bound_class = getattr(instance, name)
                setattr(instance, name, bound_class)


class EmptySchedule(Exception):
    pass


class StopSimulation(Exception):
    @classmethod
    def callback(cls, event):
        if event.ok:
            raise cls(event.value)
        else:
            raise event.value


class BaseEnvironment(object):
    def run(self, until=None):
        if until is not None:
            if not isinstance(until, Event):
                at = float(until)

                if at <= self.now:
                    raise ValueError('until(=%s) should be > the current '
                                     'simulation time.' % at)

                until = Event(self)
                until._ok = True
                until._value = None
                self.schedule(until, URGENT, at - self.now)

            elif until.callbacks is None:
                return until.value

            until.callbacks.append(StopSimulation.callback)

        try:
            while True:
                self.step()
        except StopSimulation as exc:
            return exc.args[0]  # == until.value
        except EmptySchedule:
            if until is not None:
                assert not until.triggered
                raise RuntimeError('No scheduled events left but "until" '
                                   'event was not triggered: %s' % until)


class Environment(BaseEnvironment):
    def __init__(self, initial_time=0):
        self._now = initial_time
        self._queue = []
        self._eid = count()
        self._active_proc = None

        BoundClass.bind_early(self)

    @property
    def now(self):
        return self._now

    @property
    def active_process(self):
        return self._active_proc

    process = BoundClass(Process)
    timeout = BoundClass(Timeout)
    event = BoundClass(Event)
    all_of = BoundClass(AllOf)
    any_of = BoundClass(AnyOf)

    def schedule(self, event, priority=NORMAL, delay=0):
        heappush(self._queue, (self._now + delay, priority, next(self._eid), event))

    def peek(self):
        try:
            return self._queue[0][0]
        except IndexError:
            return Infinity

    def step(self):
        try:
            self._now, _, _, event = heappop(self._queue)
        except IndexError:
            raise EmptySchedule()

        callbacks, event.callbacks = event.callbacks, None
        for callback in callbacks:
            callback(event)

        if not event._ok and not hasattr(event, '_defused'):
            exc = type(event._value)(*event._value.args)
            exc.__cause__ = event._value
            raise exc

