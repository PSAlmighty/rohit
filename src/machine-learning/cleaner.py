import json, datetime, time, copy, sys, csv, logging
from openpyxl import Workbook
from openpyxl.worksheet.table import Table, TableStyleInfo
from pymongo import MongoClient
from multiprocessing.dummy import Pool as ThreadPool

import numpy as np
import talib 
from talib.abstract import *

connection = MongoClient('localhost',27017)
db = connection.Nsedata
db.drop_collection('technical')
db.drop_collection('buy.overlap')
db.drop_collection('sell.overlap')
db.drop_collection('buy.pattern')
db.drop_collection('sell.pattern')
db.drop_collection('buy.momentum')
db.drop_collection('sell.momentum')
db.drop_collection('buy.volume')
db.drop_collection('sell.volume')
db.drop_collection('regression')
db.drop_collection('classification')