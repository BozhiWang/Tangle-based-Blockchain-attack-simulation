from envir.store import Store
from envir.core import Infinity

class BroadcastPipe(object):

    def __init__(self, env, capacity=Infinity):
        self.env = env
        self.capacity = capacity
        self.pipes = []

    def put(self, value):
        if not self.pipes:
            raise RuntimeError('There are no output pipes.')
        events = [store.put(value) for store in self.pipes]
        return self.env.all_of(events)  # Condition event for all "events"

    def get_output_conn(self):
        pipe = Store(self.env, capacity=self.capacity)
        self.pipes.append(pipe)
        return pipe

def unicast(out_pipe,sendtime,source,destination,size,information):
    msg=(sendtime,0,source,destination,size,information)
    out_pipe.put(msg)

def broadcast(out_pipe,sendtime,source,target,size,information):
    for i in target:
        unicast(out_pipe,sendtime,source,i,size,information)

