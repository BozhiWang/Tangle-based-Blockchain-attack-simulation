# Tangle-based-Blockchain-attack-simulation

## Introduction

This is a simulator of Tangle-based blockchain. 
We construct three types of attacks and corresponding evaluations including parasite attack (PS), double spending attack (DS) and hybrid attack (HB) to test the security of tangle-based blockchains. 


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

##

More futher information please check the comments.

Contact email:bozhi.wang@student.unsw.edu.au

Happy to hear your advice
