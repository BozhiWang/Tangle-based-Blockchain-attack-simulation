# DAG-blockchain-attack-simulation

## Introduction

This is a simultor of DAG-blockchain. We use this simultor to test the specific response of the blockchain network when it is facing some kinds of attack or special issue.

The working mode of the network is based on Tangle(IoTA) but removed the monitor. 

## Run the project

Make sure you have python on your PC. Run main.py

## Parameters
### Overall
Worker(user) number

Simultion time
### Network
Network delay(download speed)

Broadcast type
### Node working
Create transcation time range

Transaction weight range

PoW time
### Get father transaction(weight count)
Time/weight threshold

Weight attenuation

Historical transaction select probablity
### Attack strategy
Strategy ratio

a: check good transaction(find good father),send good transaction

b: check bad transaction,send good transaction

c: check selfish transaction,send good transaction

d: check good transaction,send bad transaction

e: check bad transaction,send bad transaction

f: check selfish transaction,send bad transaction



More futher information please check the comments.

Contact email:bozhi.wang@student.unsw.edu.au

Happy to hear your advice
