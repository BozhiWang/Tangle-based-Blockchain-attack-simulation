PENDING = object()

URGENT = 0
NORMAL = 1

class Event(object):
    def __init__(self, env):
        self.env = env
        self.callbacks = []
        self._value = PENDING

    def __repr__(self):
        return '<%s object at 0x%x>' % (self._desc(), id(self))

    def _desc(self):
        return '%s()' % self.__class__.__name__

    @property
    def triggered(self):
        return self._value is not PENDING

    @property
    def processed(self):
        return self.callbacks is None

    @property
    def ok(self):
        return self._ok

    @property
    def defused(self):
        return hasattr(self, '_defused')

    @defused.setter
    def defused(self, value):
        self._defused = True

    @property
    def value(self):
        if self._value is PENDING:
            raise AttributeError('Value of %s is not yet available' % self)
        return self._value

    def trigger(self, event):
        self._ok = event._ok
        self._value = event._value
        self.env.schedule(self)

    def succeed(self, value=None):
        if self._value is not PENDING:
            raise RuntimeError('%s has already been triggered' % self)

        self._ok = True
        self._value = value
        self.env.schedule(self)
        return self

    def fail(self, exception):
        if self._value is not PENDING:
            raise RuntimeError('%s has already been triggered' % self)
        if not isinstance(exception, BaseException):
            raise ValueError('%s is not an exception.' % exception)
        self._ok = False
        self._value = exception
        self.env.schedule(self)
        return self

    def __and__(self, other):
        return Condition(self.env, Condition.all_events, [self, other])

    def __or__(self, other):
        return Condition(self.env, Condition.any_events, [self, other])


class Timeout(Event):
    def __init__(self, env, delay, value=None):
        if delay < 0:
            raise ValueError('Negative delay %s' % delay)
        self.env = env
        self.callbacks = []
        self._value = value
        self._delay = delay
        self._ok = True
        env.schedule(self, NORMAL, delay)

    def _desc(self):
        return '%s(%s%s)' % (self.__class__.__name__, self._delay,
                             '' if self._value is None else
                             (', value=%s' % self._value))


class ConditionValue(object):
    def __init__(self):
        self.events = []

    def __getitem__(self, key):
        if key not in self.events:
            raise KeyError(str(key))

        return key._value

    def __contains__(self, key):
        return key in self.events

    def __eq__(self, other):
        if type(other) is ConditionValue:
            return self.events == other.events

        return self.todict() == other

    def __repr__(self):
        return '<ConditionValue %s>' % self.todict()

    def __iter__(self):
        return self.keys()

    def keys(self):
        return (event for event in self.events)

    def values(self):
        return (event._value for event in self.events)

    def items(self):
        return ((event, event._value) for event in self.events)

    def todict(self):
        return dict((event, event._value) for event in self.events)


class Condition(Event):
    def __init__(self, env, evaluate, events):
        super(Condition, self).__init__(env)
        self._evaluate = evaluate
        self._events = events if type(events) is tuple else tuple(events)
        self._count = 0

        if not self._events:
            self.succeed(ConditionValue())
            return

        for event in self._events:
            if self.env != event.env:
                raise ValueError('It is not allowed to mix events from '
                                 'different environments')

        for event in self._events:
            if event.callbacks is None:
                self._check(event)
            else:
                event.callbacks.append(self._check)

        self.callbacks.append(self._build_value)

    def _desc(self):
        return '%s(%s, %s)' % (self.__class__.__name__,
                               self._evaluate.__name__, self._events)

    def _populate_value(self, value):
        for event in self._events:
            if isinstance(event, Condition):
                event._populate_value(value)
            elif event.callbacks is None:
                value.events.append(event)

    def _build_value(self, event):
        self._remove_check_callbacks()
        if event._ok:
            self._value = ConditionValue()
            self._populate_value(self._value)

    def _remove_check_callbacks(self):
        for event in self._events:
            if event.callbacks and self._check in event.callbacks:
                event.callbacks.remove(self._check)
            if isinstance(event, Condition):
                event._remove_check_callbacks()

    def _check(self, event):
        if self._value is not PENDING:
            return

        self._count += 1

        if not event._ok:
            event._defused = True
            self.fail(event._value)
        elif self._evaluate(self._events, self._count):
            self.succeed()

    @staticmethod
    def all_events(events, count):
        return len(events) == count

    @staticmethod
    def any_events(events, count):
        return count > 0 or len(events) == 0


class AllOf(Condition):
    def __init__(self, env, events):
        super(AllOf, self).__init__(env, Condition.all_events, events)


class AnyOf(Condition):
    def __init__(self, env, events):
        super(AnyOf, self).__init__(env, Condition.any_events, events)


class Initialize(Event):
    def __init__(self, env, process):
        self.env = env
        self.callbacks = [process._resume]
        self._value = None
        self._ok = True
        env.schedule(self, URGENT)


class Process(Event):
   def __init__(self, env, generator):
        if not hasattr(generator, 'throw'):
            raise ValueError('%s is not a generator.' % generator)

        self.env = env
        self.callbacks = []
        self._value = PENDING

        self._generator = generator

        self._target = Initialize(env, self)

   def _resume(self, event):
        self.env._active_proc = self

        while True:
            try:
                if event._ok:
                    event = self._generator.send(event._value)
                else:
                    event._defused = True

                    exc = type(event._value)(*event._value.args)
                    exc.__cause__ = event._value
                    event = self._generator.throw(exc)
            except StopIteration as e:
                event = None
                self._ok = True
                self._value = e.args[0] if len(e.args) else None
                self.env.schedule(self)
                break
            except BaseException as e:
                event = None
                self._ok = False
                tb = e.__traceback__
                e.__traceback__ = tb.tb_next
                self._value = e
                self.env.schedule(self)
                break

            try:
                if event.callbacks is not None:
                    event.callbacks.append(self._resume)
                    break
            except AttributeError:
                if not hasattr(event, 'callbacks'):
                    msg = 'Invalid yield value "%s"' % event

                descr = _describe_frame(self._generator.gi_frame)
                error = RuntimeError('\n%s%s' % (descr, msg))
                error.__cause__ = None
                raise error

        self._target = event
        self.env._active_proc = None