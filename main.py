from envir.core import Environment
from envir.events import Process, Timeout
import time
import random
from network_delay import getdelay, getdownloadspeed
from broadcasttype import BroadcastPipe, unicast, broadcast

TRANSAC_WEIGHT = [1, 4]
TRANSAC_TIME = [10, 40]  # time range for per transaction in per node
LIMIT = 30  # threshold for transaction weight
OVERTIME = 1000  # transaction overtime limit


def delaypipe(env, in_pipe):
    # add network delay
    while True:
        msg1 = yield in_pipe.get()
        msg = list(msg1)
        '''
        sendtime=msg[0]
        receivetitletime=msg[1]
        source=msg[2]
        destination=msg[3]
        size=msg[4]
        information=msg[5]
        finishreceivetime=msg[6]
        '''
        delay = getdelay(msg[2], msg[3], msg[4])
        msg[1] = msg[0] + delay

        # insert the new message as right order
        i = 0
        while i < len(userdelaylist[msg[3]]):
            if userdelaylist[msg[3]][i][1] > msg[1]:
                break
            i = i + 1
        userdelaylist[msg[3]].insert(i, msg)


class goodWorker(object):
    def __init__(self, env, id, out_pipe, totalusernumber):
        # initialization
        self.env = env
        self.out_pipe = out_pipe
        self.id = id
        self.workerdatabase = []
        self.savebase = []
        self.downloadspeed = getdownloadspeed(self.id)
        self.usernum = totalusernumber
        self.weightcount = {}
        self.waitchecklist = []
        self.messagebase = {}
        self.badtran = {}
        self.avaliabletoken = [100 for i in range(totalusernumber)]
        self.highest_height = 0
        self.env.process(self.gettingmsg())
        self.env.process(self.workinguser())

    def gettingmsg(self):
        while True:
            # Synchronize database with time
            basicyield = True
            if (len(userdelaylist[self.id]) > 0):
                msg = userdelaylist[self.id][0]
                if (self.env.now >= msg[1]):
                    userdelaylist[self.id].pop(0)
                    basicyield = False
                    yield self.env.timeout(msg[4] / self.downloadspeed)
                    msg.append(self.env.now)
                    self.workerdatabase.append(msg)
                    self.savebase.append(msg)

            # no new transaction, step time
            if basicyield:
                yield self.env.timeout(1)

    def addweight(self, weight, father, startweight, L):
        self.weightcount[father][0] = self.weightcount[father][0] + weight  # add weight

        if self.weightcount[father][0] > LIMIT:  # reach threshold
            # current transaction has been checked, remove it from parent pool
            if (len(self.waitchecklist) > 2):
                while (self.waitchecklist.count(father) > 0):
                    self.waitchecklist.remove(father)
                    inf = self.messagebase[father][5]
                    self.avaliabletoken[inf[1]] = self.avaliabletoken[inf[1]] + inf[2]
                    self.messagebase[father][5][4] = 1
                    self.messagebase[father][7] = self.env.now

        # recursion add father transaction's weight
        if (self.weightcount[father][1] != 0) and (self.weightcount[father][2] != 0):
            if (self.env.now - self.messagebase[self.weightcount[father][1]][6] <= OVERTIME) and (
                    self.env.now - self.messagebase[self.weightcount[father][1]][6] <= OVERTIME):
                # weight attenuation
                L = L + 1
                if L <= 6:
                    weight = weight * 0.8
                elif L <= 16:
                    weight = weight * 0.9
                else:
                    weight = 0.01 * startweight
                self.addweight(weight, self.weightcount[father][1], startweight, L)
                self.addweight(weight, self.weightcount[father][2], startweight, L)
        return

    def getparent(self):
        # count single transaction(from good transactions)'s probability to be chosen as parent,return parent ID
        count = 0
        value = [0 for i in range(-1, len(self.waitchecklist))]
        parent = 0
        allzero = False

        for i in self.waitchecklist:
            weight = abs(15 - self.weightcount[i][0])
            level = self.highest_height - self.messagebase[i][4]
            time = int((self.env.now - self.messagebase[i][6]) / 60)
            p = int(3 * weight + 100 / (5 ** level) - 1.5 ** time)
            if p < 0:
                p = 0
            elif p > 0:
                allzero = True
            count = count + p
            value[parent] = count
            parent = parent + 1

        if not allzero:
            choose = random.randint(0, len(self.waitchecklist) - 1)
            return self.waitchecklist[choose]

        choose = random.randint(0, count)
        parent = 0
        if choose <= value[0]:
            return self.waitchecklist[0]
        for i in range(1, len(self.waitchecklist)):
            if (choose <= value[i]) and (choose > value[i - 1]):
                parent = self.waitchecklist[i]
                return parent

    def workinguser(self):
        while True:
            # wait for interval time
            yield self.env.timeout(random.randint(TRANSAC_TIME[0], TRANSAC_TIME[1]))

            # process historical message during interval time
            while (len(self.workerdatabase) > 0):
                msg = self.workerdatabase[0]
                del (self.workerdatabase[0])
                inf = msg[5]
                if inf[4] > self.highest_height:
                    self.highest_height = inf[4]
                self.messagebase[inf[0]] = inf
                if inf[5][3] == -1:
                    self.badtran[inf[0]] = -1
                self.waitchecklist.append(inf[0])
                self.avaliabletoken[inf[5][0]] = self.avaliabletoken[inf[5][0]] - inf[5][2]

                # weight graph renewal
                self.weightcount[inf[0]] = [inf[1], inf[2], inf[3]]
                self.addweight(inf[1], inf[2], inf[1], 1)
                self.addweight(inf[1], inf[3], inf[1], 1)

            # check failure transaction
            for id in self.waitchecklist:
                inf = self.messagebase[id]
                if (self.highest_height - inf[4] > 30) or (self.env.now - inf[6] > OVERTIME):
                    self.waitchecklist.remove(id)
                    self.avaliabletoken[inf[5][0]] = self.avaliabletoken[inf[5][0]] + inf[5][2]
                    self.messagebase[id][5][4] = -1
                    self.messagebase[id][7] = self.env.now

            # create new transaction
            if self.avaliabletoken[self.id] > 0:
                weight = random.randint(TRANSAC_WEIGHT[0], TRANSAC_WEIGHT[1])
                parent1 = self.getparent()
                while parent1 in self.badtran:
                    parent1 = self.getparent()
                parent2 = self.getparent()
                while (parent1 == parent2) or (parent2 in self.badtran):
                    parent2 = self.getparent()
                if self.messagebase[parent1][4] > self.messagebase[parent2][4]:
                    height = self.messagebase[parent2][4] + 1
                else:
                    height = self.messagebase[parent1][4] + 1
                global usernumber
                receiver = random.randint(0, self.usernum - 1)
                token = random.randint(1, self.avaliabletoken[self.id] % 10 + 1)
                validity = 1
                status = 0

                yield self.env.timeout(20)

                global tranID
                tranID = tranID + 1
                broadcast(self.out_pipe, self.env.now, self.id, (i for i in range(self.usernum)), 1,
                          [tranID, weight, parent1, parent2, height, [self.id, receiver, token, validity, status],
                           self.env.now, 0])


class badWorker(object):
    def __init__(self, env, id, out_pipe, totalusernumber, goodusernumber):
        # initialization
        self.friend = goodusernumber
        self.friendtran = 0
        self.env = env
        self.out_pipe = out_pipe
        self.id = id
        self.workerdatabase = []
        self.savebase = []
        self.downloadspeed = getdownloadspeed(self.id)
        self.usernum = totalusernumber
        self.weightcount = {}
        self.txnumcount = {}
        self.waitchecklist = []
        self.waitchecklistbad = []
        self.messagebase = {}
        self.badtran = {}
        self.badparent = {}
        self.goodchecknum = 0
        self.badchecknum = 0
        self.goodforbnum = 0
        self.badforbnum = 0
        self.goodchecktime = 0
        self.badchecktime = 0
        self.goodforbtime = 0
        self.badforbtime = 0
        self.goodcheckTxnum = 0
        self.badcheckTxnum = 0
        self.goodforbTxnum = 0
        self.badforbTxnum = 0
        self.avaliabletoken = [100 for i in range(totalusernumber)]
        self.highest_height = 0
        self.env.process(self.gettingmsg())
        self.env.process(self.workinguser())

    def gettingmsg(self):
        while True:
            # Synchronize database with time
            basicyield = True
            if (len(userdelaylist[self.id]) > 0):
                msg = userdelaylist[self.id][0]
                if (self.env.now >= msg[1]):
                    userdelaylist[self.id].pop(0)
                    basicyield = False
                    yield self.env.timeout(msg[4] / self.downloadspeed)
                    msg.append(self.env.now)
                    self.workerdatabase.append(msg)
                    self.savebase.append(msg)

            # no new transaction, step time
            if basicyield:
                yield self.env.timeout(1)

    def addweight(self, weight, father, startweight, L):
        self.weightcount[father][0] = self.weightcount[father][0] + weight  # add weight
        self.txnumcount[father] = self.txnumcount[father] + 1
        if self.messagebase[father][5][0] >= self.friend:
            self.badparent[father] = self.badparent[father] + 1

        if self.weightcount[father][0] > LIMIT:  # reach threshold
            # current transaction has been checked, remove it from parent pool
            if (len(self.waitchecklist) > 2):
                if (self.waitchecklist.count(father) > 0):
                    self.waitchecklist.remove(father)
                    if father in self.waitchecklistbad:
                        self.waitchecklistbad.remove(father)
                        self.badchecknum = self.badchecknum + 1
                        self.badcheckTxnum = self.badcheckTxnum + self.txnumcount[father]
                        self.badchecktime = self.badchecktime + self.env.now - self.messagebase[father][6]
                    else:
                        self.goodchecknum = self.goodchecknum + 1
                        self.goodcheckTxnum = self.goodcheckTxnum + self.txnumcount[father]
                        self.goodchecktime = self.goodchecktime + self.env.now - self.messagebase[father][6]
                    inf = self.messagebase[father][5]

                    if inf[0] >= self.friend:
                        self.friendtran = self.friendtran - 1
                    self.avaliabletoken[inf[1]] = self.avaliabletoken[inf[1]] + inf[2]
                    self.messagebase[father][5][4] = 1
                    self.messagebase[father][7] = self.env.now

        # recursion add father transaction's weight
        if (self.weightcount[father][1] != 0) and (self.weightcount[father][2] != 0):
            if (self.env.now - self.messagebase[self.weightcount[father][1]][6] <= OVERTIME) and (
                    self.env.now - self.messagebase[self.weightcount[father][1]][6] <= OVERTIME):
                # weight attenuation
                L = L + 1
                if L <= 6:
                    weight = weight * 0.8
                elif L <= 16:
                    weight = weight * 0.9
                else:
                    weight = 0.01 * startweight
                self.addweight(weight, self.weightcount[father][1], startweight, L)
                self.addweight(weight, self.weightcount[father][2], startweight, L)

        return

    def getparent(self):
        # count single transaction(from good transactions)'s probability to be chosen as parent,return parent ID
        count = 0
        value = [0 for i in range(-1, len(self.waitchecklist))]
        parent = 0
        allzero = False

        for i in self.waitchecklist:
            weight = abs(15 - self.weightcount[i][0])
            level = self.highest_height - self.messagebase[i][4]
            time = int((self.env.now - self.messagebase[i][6]) / 60)
            p = int(3 * weight + 100 / (5 ** level) - 1.5 ** time)
            if p < 0:
                p = 0
            elif p > 0:
                allzero = True
            count = count + p
            value[parent] = count
            parent = parent + 1

        if not allzero:
            choose = random.randint(0, len(self.waitchecklist) - 1)
            return self.waitchecklist[choose]

        choose = random.randint(0, count)
        parent = 0
        if choose <= value[0]:
            return self.waitchecklist[0]
        for i in range(1, len(self.waitchecklist)):

            if (choose <= value[i]) and (choose > value[i - 1]):
                parent = self.waitchecklist[i]
                return parent

    def getbadparent(self):
        # count single transaction(from bad transactions)'s probability to be chosen as parent,return parent ID
        count = 0
        value = [0 for i in range(-1, len(self.waitchecklistbad))]
        parent = 0
        allzero = False

        for i in self.waitchecklistbad:
            weight = abs(15 - self.weightcount[i][0])
            level = self.highest_height - self.messagebase[i][4]
            time = int((self.env.now - self.messagebase[i][6]) / 60)
            p = int(3 * weight + 100 / (5 ** level) - 1.5 ** time)
            if p < 0:
                p = 0
            elif p > 0:
                allzero = True
            count = count + p
            value[parent] = count
            parent = parent + 1
        if not allzero:
            choose = random.randint(0, len(self.waitchecklistbad) - 1)
            return self.waitchecklistbad[choose]

        choose = random.randint(0, count)
        parent = 0
        if choose <= value[0]:
            return self.waitchecklistbad[0]
        for i in range(1, len(self.waitchecklistbad)):
            if (choose <= value[i]) and (choose > value[i - 1]):
                parent = self.waitchecklistbad[i]
                return parent

    def workinguser(self):
        while True:
            # wait for interval time
            yield self.env.timeout(random.randint(TRANSAC_TIME[0], TRANSAC_TIME[1]))

            # process historical message during interval time
            while (len(self.workerdatabase) > 0):
                msg = self.workerdatabase[0]
                del (self.workerdatabase[0])
                inf = msg[5]
                if inf[4] > self.highest_height:
                    self.highest_height = inf[4]
                self.messagebase[inf[0]] = inf
                if inf[5][0] >= self.friend:
                    self.friendtran = self.friendtran + 1
                if inf[5][3] == -1:
                    self.badtran[inf[0]] = -1
                    self.waitchecklistbad.append(inf[0])
                self.badparent[inf[0]] = 0
                self.waitchecklist.append(inf[0])
                self.avaliabletoken[inf[5][0]] = self.avaliabletoken[inf[5][0]] - inf[5][2]

                # weight graph renewal
                self.weightcount[inf[0]] = [inf[1], inf[2], inf[3]]
                self.txnumcount[inf[0]] = 0
                self.addweight(inf[1], inf[2], inf[1], 1)
                self.addweight(inf[1], inf[3], inf[1], 1)

            # check failure transaction
            for id in self.waitchecklist:
                inf = self.messagebase[id]
                if (self.highest_height - inf[4] > 30) or (self.env.now - inf[6] > OVERTIME):
                    self.waitchecklist.remove(id)
                    if id in self.waitchecklistbad:
                        self.waitchecklistbad.remove(id)
                        self.badforbnum = self.badforbnum + 1
                        self.badforbTxnum = self.badforbTxnum + self.txnumcount[id]
                        self.badforbtime = self.badforbtime + self.env.now - self.messagebase[id][6]
                    else:
                        self.goodforbnum = self.goodforbnum + 1
                        self.goodforbTxnum = self.goodforbTxnum + self.txnumcount[id]
                        self.goodforbtime = self.goodforbtime + self.env.now - self.messagebase[id][6]

                    if inf[5][0] >= self.friend:
                        self.friendtran = self.friendtran - 1
                    self.avaliabletoken[inf[5][0]] = self.avaliabletoken[inf[5][0]] + inf[5][2]
                    self.messagebase[id][5][4] = -1
                    self.messagebase[id][7] = self.env.now

            global badTx

            # create new transaction
            if self.avaliabletoken[self.id] > 0:
                weight = random.randint(TRANSAC_WEIGHT[0], TRANSAC_WEIGHT[1])

                # choose bad worker strategy
                stra = random.randint(0, 9)
                if stra < 0:
                    # strategy 1 find good parent
                    parent1 = self.getparent()
                    while parent1 in self.badtran:
                        parent1 = self.getparent()
                    parent2 = self.getparent()
                    while (parent1 == parent2) or (parent2 in self.badtran):
                        parent2 = self.getparent()
                    if stra <= 10:
                        # strategy a
                        validity = 1
                    else:
                        # strategy d
                        validity = -1
                        badTx = badTx + 1

                # strategy 2 find selfish parent
                elif stra < 10:
                    if self.friendtran >= 2:
                        parent1 = self.getparent()
                        while self.messagebase[parent1][5][0] < self.friend:
                            parent1 = self.getparent()
                        parent2 = self.getparent()
                        while (parent1 == parent2) or (self.messagebase[parent2][5][0] < self.friend):
                            parent2 = self.getparent()
                    elif self.friendtran == 1:
                        parent1 = self.getparent()
                        while self.messagebase[parent1][5][0] < self.friend:
                            parent1 = self.getparent()
                        parent2 = self.getparent()
                        while (parent1 == parent2):
                            parent2 = self.getparent()
                    else:
                        parent1 = self.getparent()
                        parent2 = self.getparent()
                        while (parent1 == parent2):
                            parent2 = self.getparent()
                    global selfishTx
                    selfishTx = selfishTx + 1
                    if stra <= 10:
                        # strategy c
                        validity = 1
                    else:
                        # strategy f
                        validity = -1
                        badTx = badTx + 1

                # strategy 3 find bad parent
                else:
                    if len(self.waitchecklistbad) >= 2:
                        parent1 = self.getbadparent()
                        parent2 = self.getbadparent()
                        while (parent1 == parent2):
                            parent2 = self.getbadparent()
                    elif len(self.waitchecklistbad) == 1:
                        parent1 = self.getbadparent()
                        parent2 = self.getparent()
                        while (parent1 == parent2):
                            parent2 = self.getparent()
                    else:
                        parent1 = self.getparent()
                        parent2 = self.getparent()
                        while (parent1 == parent2):
                            parent2 = self.getparent()
                    if stra <= 10:
                        # strategy b
                        validity = 1
                    else:
                        # strategy e
                        validity = -1
                        badTx = badTx + 1

                if self.messagebase[parent1][4] > self.messagebase[parent2][4]:
                    height = self.messagebase[parent2][4] + 1
                else:
                    height = self.messagebase[parent1][4] + 1
                global usernumber
                receiver = random.randint(0, self.usernum - 1)
                token = random.randint(1, self.avaliabletoken[self.id] % 10 + 1)
                status = 0

                yield self.env.timeout(20)

                global tranID
                tranID = tranID + 1
                broadcast(self.out_pipe, self.env.now, self.id, (i for i in range(self.usernum)), 1,
                          [tranID, weight, parent1, parent2, height, [self.id, receiver, token, validity, status],
                           self.env.now, 0])


def timestamp(env, step):
    # show elapsed time for per 'step' simulation time
    while True:
        start = time.time()
        yield env.timeout(step)
        elapsed = (time.time() - start)
        print(env.now, ':', elapsed)


def sim(goodusernum, badusernum, SIM_TIME):
    # initialization
    global userdelaylist, goodusernumber, badusernumber, totalusernumber
    goodusernumber = goodusernum
    badusernumber = badusernum
    totalusernumber = goodusernumber + badusernumber
    userdelaylist = [[] for i in range(totalusernumber)]  # network waiting list for each node

    i = 0
    global selfishTx, badTx
    selfishTx = 0
    badTx = 0
    # simulation environment initialization
    env = Environment()
    bc_pipe = BroadcastPipe(env)

    # start network delay process
    env.process(delaypipe(env, bc_pipe.get_output_conn()))

    # genesis transactions
    for i in range(0, 5):
        broadcast(bc_pipe, 0, 0, (j for j in range(totalusernumber)), 1, [i, 1, 0, 0, 0, [0, 0, 0, 0, 0], 0, 0])
        # out_pipe, send time, source, target group, size, information
        # information [tranID,weight,parent1,parent2,height,[senderID,receiverID,token number,validity,status],send time,checked time]
    global tranID
    tranID = 4

    # start basic node process
    goodusers = [goodWorker(env, i, bc_pipe, totalusernumber) for i in range(goodusernumber)]

    badusers = [badWorker(env, i, bc_pipe, totalusernumber, goodusernumber) for i in
                range(goodusernumber, totalusernumber)]

    # timestamp
    env.process(timestamp(env, 10))  # step

    # start simulation
    env.run(until=SIM_TIME)

    # result print

    # print one chain
    doc = open('1_80_c_10.txt', 'w')
    for user in goodusers[2].messagebase:
        doc.write(str(goodusers[2].messagebase[user]))
        doc.write('\n')
    doc.close()
    
    #statistic print
    conclu=badusers[0]
    per80=0
    aveTx=conclu.goodcheckTxnum/conclu.goodchecknum
    for transaction in conclu.messagebase:
        if (conclu.messagebase[transaction][5][4]==1):
            if conclu.badparent[transaction] > 0.8 * aveTx:
                per80 = per80 + 1

    res=open('result.csv','w')
    
    res.write(str(100))
    res.write('\t')
    res.write(str(80))
    res.write('\t')
    res.write(str(20))
    res.write('\t')
    res.write(str(tranID))
    res.write('\t')
    res.write(str(tranID-badTx))
    res.write('\t')
    res.write(str(badTx))
    res.write('\t')
    res.write(str(conclu.goodchecknum))
    res.write('\t')
    if conclu.goodchecknum>0:
        res.write(str(conclu.goodchecktime/conclu.goodchecknum))
        res.write('\t')
        res.write(str(conclu.goodcheckTxnum/conclu.goodchecknum))
        res.write('\t')
    else:
        res.write(str(0))
        res.write('\t')
        res.write(str(0))
        res.write('\t')

    res.write(str(conclu.badchecknum))
    res.write('\t')
    if conclu.badchecknum>0:
        res.write(str(conclu.badchecktime/conclu.badchecknum))
        res.write('\t')
        res.write(str(conclu.badcheckTxnum/conclu.badchecknum))
        res.write('\t')
    else:
        res.write(str(0))
        res.write('\t')
        res.write(str(0))
        res.write('\t')

    res.write(str(conclu.goodforbnum))
    res.write('\t')
    if conclu.goodforbnum > 0:
        res.write(str(conclu.goodforbtime / conclu.goodforbnum))
        res.write('\t')
        res.write(str(conclu.goodforbTxnum / conclu.goodforbnum))
        res.write('\t')
    else:
        res.write(str(0))
        res.write('\t')
        res.write(str(0))
        res.write('\t')

    res.write(str(conclu.badforbnum))
    res.write('\t')
    if conclu.badforbnum > 0:
        res.write(str(conclu.badforbtime / conclu.badforbnum))
        res.write('\t')
        res.write(str(conclu.badforbTxnum / conclu.badforbnum))
        res.write('\t')
    else:
        res.write(str(0))
        res.write('\t')
        res.write(str(0))
        res.write('\t')

    
    res.write(str(per80))
    res.write('\t')
    res.write('\n')
    res.close()

if __name__ == "__main__":
    sim(80, 20, 10800)
# good worker number, bad worker number , simulation time

