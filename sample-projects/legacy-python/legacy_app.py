import os
from ConfigParser import ConfigParser

def greet():
    name = raw_input("Enter your name: ")
    print "Hello,", name  # print is fine inside this comment
    return name

def total(prices):
    result = 0
    for k, v in prices.iteritems():
        result += v
    print "Total:", result
    return result / len(prices)

for i in xrange(3):
    try:
        greet()
    except IOError, e:
        print "failed", e
