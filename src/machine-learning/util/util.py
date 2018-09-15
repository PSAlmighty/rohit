import csv
from openpyxl import Workbook
from openpyxl.worksheet.table import Table, TableStyleInfo
from openpyxl.styles import Color, PatternFill, Font, Border
from pymongo import MongoClient
from multiprocessing.dummy import Pool as ThreadPool

import quandl, math, time
from nsepy import get_history
from nsepy.derivatives import get_expiry_date
from datetime import date
import datetime   
import pandas as pd
pd.options.mode.chained_assignment = None  # default='warn'
import numpy as np

connection = MongoClient('localhost',27017)
db = connection.Nsedata

soft=False
BUY_VERY_LESS_DATA=False
SELL_VERY_LESS_DATA=False

buyMLP = 1
buyMLP_MIN = 0
buyKN = 1
buyKN_MIN = 0
sellMLP = -1
sellMLP_MIN = 0
sellKN = -1
sellKN_MIN = 0

def add_in_csv(regression_data, regressionResult, ws=None, filter=None, filter1=None, filter2=None):
    if ((filter is not None) and (filter not in regression_data['filter'])):
        regression_data['filter'] = regression_data['filter'] + filter + ','
        if ('P@[' in str(regression_data['sellIndia'])) and (('buy' or 'Buy') in regression_data['filter']):
            if '***SELLPATTERN***' not in regression_data['filter']:
               regression_data['filter'] = regression_data['filter'] + '***SELLPATTERN***' + ','
        if ('P@[' in str(regression_data['buyIndia'])) and (('sell' or 'Sell') in regression_data['filter']):
            if '***BUYPATTERN***' not in regression_data['filter']:
               regression_data['filter'] = regression_data['filter'] + '***BUYPATTERN***' + ','
    if ((filter1 is not None) and (filter1 not in regression_data['filter1'])):
        regression_data['filter1'] = regression_data['filter1'] + filter1 + ','
    if ((filter2 is not None) and (filter2 not in regression_data['filter2'])):
        regression_data['filter2'] = regression_data['filter2'] + filter2 + ','    
    tempRegressionResult = regressionResult.copy() 
    tempRegressionResult.append(regression_data['filter'])
    tempRegressionResult.append(regression_data['filter1'])
    tempRegressionResult.append(regression_data['filter2'])
    ws.append(tempRegressionResult) if (ws is not None) else False
    if(db.resultScripFutures.find_one({'scrip':regression_data['scrip']}) is None):
        db.resultScripFutures.insert_one({
            "scrip": regression_data['scrip'],
            "date": regression_data['date']
            })

def add_in_csv_hist_pattern(regression_data, regressionResult, ws, filter, avg, count):
    if ((filter is not None) and (filter not in regression_data['filter'])):
        regression_data['filter'] = regression_data['filter'] + filter + ','
    tempRegressionResult = regressionResult.copy() 
    tempRegressionResult.append(regression_data['filter'])
    tempRegressionResult.append(avg)
    tempRegressionResult.append(count)
    ws.append(tempRegressionResult) if (ws is not None) else False

def is_algo_buy(regression_data):
    if((regression_data['mlpValue'] >= buyMLP and regression_data['kNeighboursValue'] >= buyKN_MIN) 
        or (regression_data['mlpValue'] >= buyMLP_MIN and regression_data['kNeighboursValue'] >= buyKN)
        or (regression_data['mlpValue'] >= 0.5 and regression_data['kNeighboursValue'] >= 0.5)
        ):
        return True
    else:
        return False   
    
def is_algo_sell(regression_data):
    if((regression_data['mlpValue'] <= sellMLP and regression_data['kNeighboursValue'] <= sellKN_MIN)
       or (regression_data['mlpValue'] <= sellMLP_MIN and regression_data['kNeighboursValue'] <= sellKN)
       or (regression_data['mlpValue'] <= -0.5 and regression_data['kNeighboursValue'] <= -0.5)
       ):   
        return True
    else:
        return False
    
def is_algo_buy_classifier(regression_data):
    if((regression_data['mlpValue'] >= 0 and regression_data['kNeighboursValue'] >= 3) 
        or (regression_data['mlpValue'] >= 3 and regression_data['kNeighboursValue'] >= 0)
        or (regression_data['mlpValue'] >= 1 and regression_data['kNeighboursValue'] >= 1)
        ):
        return True
    else:
        return False   
    
def is_algo_sell_classifier(regression_data):
    if((regression_data['mlpValue'] <= 0 and regression_data['kNeighboursValue'] <= -3) 
        or (regression_data['mlpValue'] <= -3 and regression_data['kNeighboursValue'] <= 0)
        or (regression_data['mlpValue'] <= -1 and regression_data['kNeighboursValue'] <= -1)
        ):   
        return True
    else:
        return False    

def getScore(vol_change, pct_change):
    try:
        return float(vol_change)/float(pct_change) 
    except ZeroDivisionError:
        return 0

def all_day_pct_change_negative(regression_data):
    if(regression_data['forecast_day_PCT_change'] < 0
        and regression_data['forecast_day_PCT2_change'] <= 0
        and regression_data['forecast_day_PCT3_change'] <= 0
        and regression_data['forecast_day_PCT4_change'] <= 0
        and regression_data['forecast_day_PCT5_change'] <= 0
        and regression_data['forecast_day_PCT7_change'] <= 0
        and regression_data['forecast_day_PCT10_change'] <= 0):
        return True;
    
def all_day_pct_change_positive(regression_data):
    if(regression_data['forecast_day_PCT_change'] > 0
        and regression_data['forecast_day_PCT2_change'] > -0.5
        and regression_data['forecast_day_PCT3_change'] > -0.5
        and regression_data['forecast_day_PCT4_change'] > -0.5
        and regression_data['forecast_day_PCT5_change'] > -0.5
        and regression_data['forecast_day_PCT7_change'] > -0.5
        and regression_data['forecast_day_PCT10_change'] > -0.5):
        return True; 

def all_day_pct_change_negative_except_today(regression_data):
    if(regression_data['forecast_day_PCT2_change'] <= 0
        and regression_data['forecast_day_PCT3_change'] <= 0
        and regression_data['forecast_day_PCT4_change'] <= 0
        and regression_data['forecast_day_PCT5_change'] <= 0
        and regression_data['forecast_day_PCT7_change'] <= 0
        and regression_data['forecast_day_PCT10_change'] <= 0):
        return True;
    
def all_day_pct_change_positive_except_today(regression_data):
    if(regression_data['forecast_day_PCT2_change'] >= 0
        and regression_data['forecast_day_PCT3_change'] >= 0
        and regression_data['forecast_day_PCT4_change'] >= 0
        and regression_data['forecast_day_PCT5_change'] >= 0
        and regression_data['forecast_day_PCT7_change'] >= 0
        and regression_data['forecast_day_PCT10_change'] >= 0):
        return True;  
     
def pct_change_negative_trend(regression_data):
    if (regression_data['forecast_day_PCT_change'] < 0
        and regression_data['forecast_day_PCT2_change'] < 0
        and regression_data['forecast_day_PCT3_change'] < 0):
        pct_change_list = [regression_data['forecast_day_PCT_change'],
                           regression_data['forecast_day_PCT2_change'],
                           regression_data['forecast_day_PCT3_change'],
                           regression_data['forecast_day_PCT4_change'],
                           regression_data['forecast_day_PCT5_change'],
                           regression_data['forecast_day_PCT7_change'],
                           regression_data['forecast_day_PCT10_change']
                           ]
        trend_change = False
        trend = True
        for pct_change in pct_change_list:
            if pct_change < 0 and trend_change == False:
                trend = True
            elif pct_change > 0 and trend_change == True: 
                trend = True    
            elif pct_change > 0 and trend_change == False:
                trend_change = True
                trend = True
            else:
                trend = False
        return trend            
    return False           
    
def pct_change_positive_trend(regression_data):
    if (regression_data['forecast_day_PCT_change'] > 0
        and regression_data['forecast_day_PCT2_change'] > 0
        and regression_data['forecast_day_PCT3_change'] > 0):
        pct_change_list = [regression_data['forecast_day_PCT_change'],
                           regression_data['forecast_day_PCT2_change'],
                           regression_data['forecast_day_PCT3_change'],
                           regression_data['forecast_day_PCT4_change'],
                           regression_data['forecast_day_PCT5_change'],
                           regression_data['forecast_day_PCT7_change'],
                           regression_data['forecast_day_PCT10_change']
                           ]
        trend_change = False
        trend = True
        for pct_change in pct_change_list:
            if pct_change > 0 and trend_change == False:
                trend = True
            elif pct_change < 0 and trend_change == True: 
                trend = True    
            elif pct_change < 0 and trend_change == False:
                trend_change = True
                trend = True
            else:
                trend = False
        return trend
    return False       

def preDayPctChangeUp_orVolHigh(regression_data):
    if(regression_data['PCT_day_change_pre1'] > 0 
       or (regression_data['volume'] > regression_data['volume_pre2'] and regression_data['volume'] > regression_data['volume_pre3'])
    ):
        return True
    else:
        return False
    
def preDayPctChangeDown_orVolHigh(regression_data):
    if(regression_data['PCT_day_change_pre1'] < 0 
       or (regression_data['volume'] > regression_data['volume_pre2'] and regression_data['volume'] > regression_data['volume_pre3'])
    ):
        return True
    else:
        return False    

def all_between_five_and_up_score(regression_data):
    if(-5 < regression_data['forecast_day_PCT_change'] < 5
        and -5 < regression_data['forecast_day_PCT2_change'] < 5
        and -5 < regression_data['forecast_day_PCT3_change'] < 5
        and -5 < regression_data['forecast_day_PCT4_change'] < 5
        and -5 < regression_data['forecast_day_PCT5_change'] < 5
        and -5 < regression_data['forecast_day_PCT7_change'] < 5
        and -6 < regression_data['forecast_day_PCT10_change'] < 6
        and regression_data['score'] == '10'
        and regression_data['trend'] != 'down'
        ):
        return True
    else:
        return False

def all_between_five_and_down_score(regression_data):
    if(-5 < regression_data['forecast_day_PCT_change'] < 5
        and -5 < regression_data['forecast_day_PCT2_change'] < 5
        and -5 < regression_data['forecast_day_PCT3_change'] < 5
        and -5 < regression_data['forecast_day_PCT4_change'] < 5
        and -5 < regression_data['forecast_day_PCT5_change'] < 5
        and -5 < regression_data['forecast_day_PCT7_change'] < 5
        and -6 < regression_data['forecast_day_PCT10_change'] < 6
        and regression_data['score'] == '0-1'
        and regression_data['trend'] != 'up'
        ):
        return True
    else:
        return False        

def all_between_zero_and_five_up_score(regression_data):
    if(0 < regression_data['forecast_day_PCT_change'] < 5
        and 0 < regression_data['forecast_day_PCT2_change'] < 5
        and 0 < regression_data['forecast_day_PCT3_change'] < 5
        and 0 < regression_data['forecast_day_PCT4_change'] < 5
        and 0 < regression_data['forecast_day_PCT5_change'] < 5
        and 0 < regression_data['forecast_day_PCT7_change'] < 5
        and 0 < regression_data['forecast_day_PCT10_change'] < 6
        and regression_data['score'] == '10'
        and regression_data['trend'] != 'down'
        ):
        return True
    else:
        return False

def all_between_zero_and_five_down_score(regression_data):
    if(-5 < regression_data['forecast_day_PCT_change'] < 0
        and -5 < regression_data['forecast_day_PCT2_change'] < 0
        and -5 < regression_data['forecast_day_PCT3_change'] < 0
        and -5 < regression_data['forecast_day_PCT4_change'] < 0
        and -5 < regression_data['forecast_day_PCT5_change'] < 0
        and -5 < regression_data['forecast_day_PCT7_change'] < 0
        and -6 < regression_data['forecast_day_PCT10_change'] < 0
        and regression_data['score'] == '0-1'
        and regression_data['trend'] != 'up'
        ):
        return True
    else:
        return False           

def abs_yearHigh_more_than_yearLow(regression_data):
    if(abs(regression_data['yearHighChange']) > abs(regression_data['yearLowChange'])):
        return True;
    else:
        return False;

def abs_yearHigh_less_than_yearLow(regression_data):
    if(abs(regression_data['yearHighChange']) < abs(regression_data['yearLowChange'])):
        return True;
    else:
        return False;
    
def last_5_day_all_up_except_today(regression_data):
    if(regression_data['PCT_day_change_pre1'] > 0
        and regression_data['PCT_day_change_pre2'] > 0
        and regression_data['PCT_day_change_pre3'] > 0
        and regression_data['PCT_day_change_pre4'] > 0): 
        return True
    else:
        return False 
    
def last_5_day_all_down_except_today(regression_data):
    if(regression_data['PCT_day_change_pre1'] < 0
        and regression_data['PCT_day_change_pre2'] < 0
        and regression_data['PCT_day_change_pre3'] < 0
        and regression_data['PCT_day_change_pre4'] < 0): 
        return True
    else:
        return False      

def last_4_day_all_up(regression_data):
    if(regression_data['PCT_day_change'] > 0
        and regression_data['PCT_day_change_pre1'] > 0
        and regression_data['PCT_day_change_pre2'] > 0
        and regression_data['PCT_day_change_pre3'] > 0
        and regression_data['PCT_day_change_pre4'] > 0
        ): 
        return True
    else:
        return False 
    
def last_4_day_all_down(regression_data):
    if(regression_data['PCT_day_change'] < 0
        and regression_data['PCT_day_change_pre1'] < 0
        and regression_data['PCT_day_change_pre2'] < 0
        and regression_data['PCT_day_change_pre3'] < 0
        and regression_data['PCT_day_change_pre4'] < 0
        ): 
        return True
    else:
        return False      

def last_7_day_all_up(regression_data):
    if(regression_data['PCT_day_change'] > 0
        and regression_data['PCT_day_change_pre1'] > 0
        and regression_data['PCT_day_change_pre2'] > 0
        and regression_data['PCT_day_change_pre3'] > 0
        and regression_data['PCT_day_change_pre4'] > 0
        and regression_data['PCT_day_change_pre5'] > 0
        and regression_data['PCT_day_change_pre6'] > 0
        ): 
        return True
    else:
        return False 
    
def last_7_day_all_down(regression_data):
    if(regression_data['PCT_day_change'] < 0
        and regression_data['PCT_day_change_pre1'] < 0
        and regression_data['PCT_day_change_pre2'] < 0
        and regression_data['PCT_day_change_pre3'] < 0
        and regression_data['PCT_day_change_pre4'] < 0
        and regression_data['PCT_day_change_pre5'] < 0
        and regression_data['PCT_day_change_pre6'] < 0
        ): 
        return True
    else:
        return False      

def historical_data_OI(data):
    ardate = np.array([str(x) for x in (np.array(data['data'])[:,3][::-1]).tolist()])
    aroipctchange = np.array([float(x.encode('UTF8')) for x in (np.array(data['data'])[:,6][::-1]).tolist()])
    arcontractpctchange = np.array([float(x.encode('UTF8')) for x in (np.array(data['data'])[:,7][::-1]).tolist()])
    return ardate, aroipctchange, arcontractpctchange

def high_tail_pct(regression_data):
    if(regression_data['high'] - regression_data['bar_high'] == 0):
        return 0
    else:
        return (((regression_data['high'] - regression_data['bar_high'])/regression_data['bar_high'])*100)
    
def low_tail_pct(regression_data):
    if((regression_data['bar_low'] - regression_data['low']) == 0):
        return 0
    else:
        return (((regression_data['bar_low'] - regression_data['low'])/regression_data['bar_low'])*100)

def tail_pct_filter(regression_data, regressionResult):
    if(high_tail_pct(regression_data) < 0.1):
        add_in_csv(regression_data, regressionResult, None, None, None, 'NoHighTail-0.1')
    if(low_tail_pct(regression_data) < 0.1):
        add_in_csv(regression_data, regressionResult, None, None, None, 'NoLowTail-0.1')

def historical_data(data):
    ardate = np.array([str(x) for x in (np.array(data['data'])[:,0][::-1]).tolist()])
    aropen = np.array([float(x.encode('UTF8')) for x in (np.array(data['data'])[:,1][::-1]).tolist()])
    arhigh = np.array([float(x.encode('UTF8')) for x in (np.array(data['data'])[:,2][::-1]).tolist()])
    arlow  = np.array([float(x.encode('UTF8')) for x in (np.array(data['data'])[:,3][::-1]).tolist()])
    arlast = np.array([float(x.encode('UTF8')) for x in (np.array(data['data'])[:,4][::-1]).tolist()])
    arclose= np.array([float(x.encode('UTF8')) for x in (np.array(data['data'])[:,5][::-1]).tolist()])
    arquantity = np.array([float(x.encode('UTF8')) for x in (np.array(data['data'])[:,6][::-1]).tolist()])
    arturnover = np.array([float(x.encode('UTF8')) for x in (np.array(data['data'])[:,7][::-1]).tolist()])
    return ardate, aropen, arhigh, arlow, arlast, arclose, arquantity, arturnover

def no_doji_or_spinning_buy_india(regression_data):
    if ('SPINNINGTOP' not in str(regression_data['buyIndia']) and 'DOJI' not in str(regression_data['buyIndia'])):
        return True;
    else:
        return False
    
def no_doji_or_spinning_sell_india(regression_data): 
    if ('SPINNINGTOP' not in str(regression_data['sellIndia']) and 'DOJI' not in str(regression_data['sellIndia'])):
        return True;
    else:
        return False   

def get_open_interest_data(regression_data, db_collection):
    data = db_collection.find_one({'scrip':regression_data['scrip']})
    if(data is None or (np.array(data['data'])).size < 1):
        return '0', '0'
    ardate, aroipctchange, arcontractpctchange = historical_data_OI(data)   
    if(ardate[-1] == regression_data['date']):
        return str(round(aroipctchange[-1], 2)), str(round(arcontractpctchange[-1], 2))
    return '0', '0'
 
def scrip_patterns_to_dict(filename):  
    tempDict = {}
    count = 0
    with open(filename) as csvfile:
        readCSV = csv.reader(csvfile, delimiter=',')
        for row in readCSV:
            try:
                if (count != 0):
                    dictValue = {}
                    dictValue['avg'] = row[1]
                    dictValue['count'] = row[2]
                    tempDict[row[0]] = dictValue
                count = count + 1
            except:
                pass
    return tempDict 

def get_regressionResult(regression_data, scrip, db, mlp_o, kneighbours_o):
    regression_data['filter'] = " "
    regression_data['filter1'] = " "
    regression_data['filter2'] = " "
    regression_data['series_trend'] = "NA"
    if pct_change_negative_trend(regression_data):
        regression_data['series_trend'] = "downTrend"
    if pct_change_positive_trend(regression_data):
         regression_data['series_trend'] = "upTrend"    
    
    regression_data['oi'] = float(-10000)
    regression_data['contract'] = float(-10000)
    if(db is not None):
        oi, contract = get_open_interest_data(regression_data, db.historyOpenInterest)
        regression_data['oi'] = float(oi)
        regression_data['contract'] = float(contract)
    
    regression_data['oi_next'] = float(-10000)
    regression_data['contract_next'] = float(-10000)
    if(db is not None):
        oi, contract = get_open_interest_data(regression_data, db.historyOpenInterestNext)
        regression_data['oi_next'] = float(oi)
        regression_data['contract_next'] = float(contract)
    
    resultDeclared = ""
    resultDate = ""
    resultSentiment = ""
    resultComment = ""
    if(db is not None):
        result_data = db.scrip_result.find_one({'scrip':scrip.replace('&','').replace('-','_')})
        if(result_data is not None):
            resultDate = result_data['result_date'].strip()
            resultSentiment = result_data['result_sentiment']
            resultComment = result_data['comment']
            start_date = (datetime.datetime.now() - datetime.timedelta(hours=0))
            start_date = datetime.datetime(start_date.year, start_date.month, start_date.day, start_date.hour)
            result_time = datetime.datetime.strptime(resultDate, "%Y-%m-%d")
            if result_time < start_date: 
                resultDeclared = resultDate 
                resultDate = ""
    regressionResult = [ ]
    regressionResult.append(regression_data['buyIndia'])
    regressionResult.append(regression_data['sellIndia'])
    regressionResult.append(regression_data['scrip'])
    regressionResult.append(regression_data['forecast_day_VOL_change'])
    regressionResult.append(regression_data['oi'])
    regressionResult.append(regression_data['contract'])
    regressionResult.append(regression_data['oi_next'])
    regressionResult.append(regression_data['contract_next'])
    regressionResult.append(regression_data['forecast_day_PCT_change'])
    regressionResult.append(regression_data['forecast_day_PCT2_change'])
    regressionResult.append(regression_data['forecast_day_PCT3_change'])
    regressionResult.append(regression_data['forecast_day_PCT4_change'])
    regressionResult.append(regression_data['forecast_day_PCT5_change'])
    regressionResult.append(regression_data['forecast_day_PCT7_change'])
    regressionResult.append(regression_data['forecast_day_PCT10_change'])
    regressionResult.append(regression_data['PCT_day_change'])
    regressionResult.append(regression_data['PCT_change'])
    regressionResult.append(regression_data['score'])
    regressionResult.append(regression_data['mlpValue'])
    regressionResult.append(regression_data['kNeighboursValue'])
    regressionResult.append(mlp_o)
    regressionResult.append(kneighbours_o)
    regressionResult.append(regression_data['trend'])
    regressionResult.append(regression_data['yearHighChange'])
    regressionResult.append(regression_data['yearLowChange'])
    regressionResult.append(regression_data['series_trend'])
    regressionResult.append(regression_data['short_term'])
    regressionResult.append(regression_data['long_term'])
    regressionResult.append(regression_data['consolidation'])
    regressionResult.append(resultDate)
    regressionResult.append(resultDeclared)
    regressionResult.append(resultSentiment)
    regressionResult.append(resultComment)
    return regressionResult

def all_withoutml(regression_data, regressionResult, ws):
    add_in_csv(regression_data, regressionResult, ws, '')

def ten_days_more_than_ten(regression_data):
    if(25 > regression_data['forecast_day_PCT10_change'] > 5
       and (regression_data['forecast_day_PCT5_change'] > 10
         or regression_data['forecast_day_PCT7_change'] > 10
         or regression_data['forecast_day_PCT10_change'] > 10)
    ):
        return True
    else:
        return False

def ten_days_less_than_ten(regression_data):
    if(regression_data['forecast_day_PCT_change'] < 5
       and regression_data['forecast_day_PCT2_change'] < 5
       and regression_data['forecast_day_PCT3_change'] < 5
       and regression_data['forecast_day_PCT4_change'] < 10
       and regression_data['forecast_day_PCT5_change'] < 10
       and regression_data['forecast_day_PCT7_change'] < 10
       and regression_data['forecast_day_PCT10_change'] < 10
    ):
        return True
    else:
        return False

def ten_days_less_than_five(regression_data):
    if(regression_data['forecast_day_PCT_change'] < 5
       and regression_data['forecast_day_PCT2_change'] < 5
       and regression_data['forecast_day_PCT3_change'] < 5
       and regression_data['forecast_day_PCT4_change'] < 5
       and regression_data['forecast_day_PCT5_change'] < 5
       and regression_data['forecast_day_PCT7_change'] < 5
       and regression_data['forecast_day_PCT10_change'] < 5
    ):
        return True
    else:
        return False
       
def ten_days_less_than_minus_ten(regression_data):
    if(-25 < regression_data['forecast_day_PCT10_change'] < -5
       and (regression_data['forecast_day_PCT5_change'] < -10
         or regression_data['forecast_day_PCT7_change'] < -10
         or regression_data['forecast_day_PCT10_change'] < -10)
    ):
        return True
    else:
        return False

def ten_days_more_than_minus_ten(regression_data):
    if(regression_data['forecast_day_PCT_change'] > -5
       and regression_data['forecast_day_PCT2_change'] > -5 
       and regression_data['forecast_day_PCT3_change'] > -5 
       and regression_data['forecast_day_PCT4_change'] > -10
       and regression_data['forecast_day_PCT5_change'] > -10 
       and regression_data['forecast_day_PCT7_change'] > -10 
       and regression_data['forecast_day_PCT10_change'] > -10
    ):
        return True
    else:
        return False
  
def ten_days_more_than_minus_five(regression_data):
    if(regression_data['forecast_day_PCT_change'] > -5
       and regression_data['forecast_day_PCT2_change'] > -5 
       and regression_data['forecast_day_PCT3_change'] > -5 
       and regression_data['forecast_day_PCT4_change'] > -5
       and regression_data['forecast_day_PCT5_change'] > -5 
       and regression_data['forecast_day_PCT7_change'] > -5 
       and regression_data['forecast_day_PCT10_change'] > -5
    ):
        return True
    else:
        return False
       
def ten_days_more_than_seven(regression_data):
    if(25 > regression_data['forecast_day_PCT10_change'] > 5
       and (regression_data['forecast_day_PCT5_change'] > 7
         or regression_data['forecast_day_PCT7_change'] > 7
         or regression_data['forecast_day_PCT10_change'] > 7)
    ):
        return True
    else:
        return False
        
def ten_days_less_than_minus_seven(regression_data):
    if(-25 < regression_data['forecast_day_PCT10_change'] < -5
       and (regression_data['forecast_day_PCT5_change'] < -7
         or regression_data['forecast_day_PCT7_change'] < -7
         or regression_data['forecast_day_PCT10_change'] < -7)
    ):
        return True
    else:
        return False    

def ten_days_more_than_five(regression_data):
    if(25 > regression_data['forecast_day_PCT10_change'] > 5
       and regression_data['forecast_day_PCT7_change'] > 5
       and regression_data['forecast_day_PCT5_change'] > 1
       and regression_data['forecast_day_PCT4_change'] > 1
       and regression_data['forecast_day_PCT3_change'] > 1
    ):
        return True
    else:
        return False
        
def ten_days_less_than_minus_five(regression_data):
    if(-25 < regression_data['forecast_day_PCT10_change'] < -5
       and regression_data['forecast_day_PCT7_change'] < -5
       and regression_data['forecast_day_PCT5_change'] < -1
       and regression_data['forecast_day_PCT4_change'] < -1
       and regression_data['forecast_day_PCT3_change'] < -1
    ):
        return True
    else:
        return False    

def buy_pattern_without_mlalgo(regression_data, regressionResult, ws_buyPattern2, ws_sellPattern2):
    buyPatternsDict=scrip_patterns_to_dict('../../data-import/nselist/all-buy-filter-by-PCT-Change.csv')
    if regression_data['buyIndia'] != '' and regression_data['buyIndia'] in buyPatternsDict:
        if (abs(float(buyPatternsDict[regression_data['buyIndia']]['avg'])) >= .1 and float(buyPatternsDict[regression_data['buyIndia']]['count']) >= 2):
            if(-0.5 < regression_data['PCT_day_change'] < 3 and float(buyPatternsDict[regression_data['buyIndia']]['avg']) > 1):
                avg = buyPatternsDict[regression_data['buyIndia']]['avg']
                count = buyPatternsDict[regression_data['buyIndia']]['count']
                #add_in_csv_hist_pattern(regression_data, regressionResult, ws_buyPattern2, 'wml_buy', avg, count)
            elif(-3 < regression_data['PCT_day_change'] < 0.5 and float(buyPatternsDict[regression_data['buyIndia']]['avg']) < -1):
                avg = buyPatternsDict[regression_data['buyIndia']]['avg']
                count = buyPatternsDict[regression_data['buyIndia']]['count']
                #add_in_csv_hist_pattern(regression_data, regressionResult, ws_sellPattern2, 'wml_buy', avg, count)

def buy_pattern_from_history(regression_data, regressionResult, ws_buyPattern2):
    buyPatternsDict=scrip_patterns_to_dict('../../data-import/nselist/patterns-buy.csv')
    buyIndiaAvg = 0
    flag = False
    if regression_data['buyIndia'] != '' and regression_data['buyIndia'] in buyPatternsDict:
        if (abs(float(buyPatternsDict[regression_data['buyIndia']]['avg'])) >= .1):
            buyIndiaAvg = float(buyPatternsDict[regression_data['buyIndia']]['avg'])
            if(int(buyPatternsDict[regression_data['buyIndia']]['count']) >= 2):
                if(is_algo_buy(regression_data)
                    and 'P@[' not in str(regression_data['sellIndia'])
                    #and regression_data['trend'] != 'up'
                    and -1 < regression_data['PCT_day_change'] < 3):
                    avg = buyPatternsDict[regression_data['buyIndia']]['avg']
                    count = buyPatternsDict[regression_data['buyIndia']]['count']
                    if(float(buyPatternsDict[regression_data['buyIndia']]['avg']) > 0.8 and int(buyPatternsDict[regression_data['buyIndia']]['count']) >= 5):
                       flag = True
                       add_in_csv_hist_pattern(regression_data, regressionResult, ws_buyPattern2, 'buyPattern2', avg, count)
                    elif(float(buyPatternsDict[regression_data['buyIndia']]['avg']) > 0.5 
                       or (float(buyPatternsDict[regression_data['buyIndia']]['avg']) > 0.3 and (ten_days_less_than_minus_ten(regression_data) or regression_data['yearHighChange'] < -40))):
                        if(regression_data['forecast_day_PCT10_change'] < 0 and regression_data['forecast_day_PCT_change'] >= 0):
                            flag = True
                            add_in_csv_hist_pattern(regression_data, regressionResult, ws_buyPattern2, 'buyPattern2', avg, count)
                        elif(regression_data['forecast_day_PCT10_change'] > 0):    
                            flag = True
                            add_in_csv_hist_pattern(regression_data, regressionResult, ws_buyPattern2, 'buyPattern2', avg, count)     
    return buyIndiaAvg, flag

def buy_all_rule(regression_data, regressionResult, buyIndiaAvg, ws_buyAll):
    if(is_algo_buy(regression_data)
        and (BUY_VERY_LESS_DATA or ((regression_data['PCT_day_change_pre1'] < 0) or (regression_data['forecast_day_VOL_change'] > 0))) #Uncomment1 If very less data
        and (regression_data['high']-regression_data['bar_high']) < (regression_data['bar_high']-regression_data['bar_low'])
        and 'P@[' not in str(regression_data['sellIndia'])
        and buyIndiaAvg >= -.70
        and (BUY_VERY_LESS_DATA or (last_4_day_all_up(regression_data) == False)) #Uncomment0 If very less data
        and (BUY_VERY_LESS_DATA or high_tail_pct(regression_data) < 0.7)
        ):
        tail_pct_filter(regression_data, regressionResult)
        buy_all_rule_filter(regression_data, regressionResult, None)
        add_in_csv(regression_data, regressionResult, ws_buyAll, None)
        if(0 < regression_data['yearLowChange'] < 10):
            if(regression_data['PCT_day_change'] < -1):
                return True
        else:
            return True
    return False

def buy_all_rule_classifier(regression_data, regressionResult, buyIndiaAvg, ws_buyAll):
    if(is_algo_buy_classifier(regression_data)
        and ((regression_data['PCT_day_change_pre1'] < 0) or (regression_data['forecast_day_VOL_change'] > 0)) #Uncomment1 If very less data
        and (regression_data['high']-regression_data['bar_high']) < (regression_data['bar_high']-regression_data['bar_low'])
        and 'P@[' not in str(regression_data['sellIndia'])
        and buyIndiaAvg >= -.5
        and (BUY_VERY_LESS_DATA or (last_4_day_all_up(regression_data) == False)) #Uncomment0 If very less data
        and (BUY_VERY_LESS_DATA or high_tail_pct(regression_data) < 0.7)
        ):
        tail_pct_filter(regression_data, regressionResult)
        buy_all_rule_filter(regression_data, regressionResult, None)
        add_in_csv(regression_data, regressionResult, ws_buyAll, None)
        if(0 < regression_data['yearLowChange'] < 10):
            if(regression_data['PCT_day_change'] < -1):
                return True
        else:
            return True
    return False

def buy_year_high(regression_data, regressionResult, ws_buyYearHigh):
    if(float(regression_data['forecast_day_VOL_change']) > 70
       and regression_data['PCT_day_change_pre1'] > -0.5
       and no_doji_or_spinning_buy_india(regression_data)
       ):
        if(-15 < regression_data['yearHighChange'] < -5 and regression_data['yearLowChange'] > 30
            and -0.5 < regression_data['PCT_day_change'] < 2 and regression_data['forecast_day_PCT2_change'] <= 2
            ):
            add_in_csv(regression_data, regressionResult, ws_buyYearHigh, 'buyYearHigh-0')
            return True
    if(float(regression_data['forecast_day_VOL_change']) > 35
       and regression_data['PCT_day_change_pre1'] > -0.5
       and no_doji_or_spinning_buy_india(regression_data)
       ):
        if(-15 < regression_data['yearHighChange'] < -5 and regression_data['yearLowChange'] > 30
            and -0.5 < regression_data['PCT_day_change'] < 2 and regression_data['forecast_day_PCT2_change'] <= 2
            ):
            add_in_csv(regression_data, regressionResult, ws_buyYearHigh, 'buyYearHigh-1')
            return True
    if(float(regression_data['forecast_day_VOL_change']) > 50
       and regression_data['PCT_day_change_pre1'] > -0.5
       and no_doji_or_spinning_buy_india(regression_data)
       ):
        if(-5 <= regression_data['yearHighChange'] < -1 and regression_data['yearLowChange'] > 15 
            and -0.5 < regression_data['PCT_day_change'] < 2 and regression_data['forecast_day_PCT2_change'] <= 2
            ):
            add_in_csv(regression_data, regressionResult, ws_buyYearHigh, 'buyYearHigh-2')
            return True
    
    return False

def buy_year_low(regression_data, regressionResult, ws_buyYearLow, ws_buyYearLow1):
    if(1 < regression_data['yearLowChange'] < 5 and regression_data['yearHighChange'] < -30 
        and 2 < regression_data['PCT_day_change'] < 6 and 2 < regression_data['PCT_day_change'] < 6
        and regression_data['forecast_day_PCT2_change'] > 0 and regression_data['forecast_day_PCT_change'] > 0
        and float(regression_data['forecast_day_VOL_change']) > 35
        ):
        add_in_csv(regression_data, regressionResult, ws_buyYearLow, 'buyYearLow')
        return True
    elif(5 < regression_data['yearLowChange'] < 15 and regression_data['yearHighChange'] < -25 
        and 2 < regression_data['PCT_day_change'] < 5 and 2 < regression_data['PCT_day_change'] < 5
        and 5 > regression_data['forecast_day_PCT2_change'] > -0.5 and regression_data['forecast_day_PCT_change'] > 0
        and float(regression_data['forecast_day_VOL_change']) > 35
        ):
        add_in_csv(regression_data, regressionResult, ws_buyYearLow1, 'buyYearLow1')
        return True
    return False

def buy_up_trend(regression_data, regressionResult, ws_buyUpTrend):
    if((regression_data['yearHighChange'] < -9 or regression_data['yearLowChange'] < 15)
       and regression_data['forecast_day_PCT_change'] > 0
       and regression_data['forecast_day_PCT2_change'] > 0
       and regression_data['forecast_day_PCT3_change'] > 0
       ):
        if(abs_yearHigh_more_than_yearLow(regression_data)
           and 2 < regression_data['PCT_day_change'] < 3 and 2 < regression_data['forecast_day_PCT_change'] < 3
           and regression_data['PCT_change'] < regression_data['PCT_day_change'] + .2
           and regression_data['forecast_day_PCT_change'] < regression_data['PCT_day_change'] + .2
           and regression_data['series_trend'] != 'downTrend'
           and regression_data['score'] != '0-1' 
           and ten_days_less_than_minus_ten(regression_data)
           ):
            add_in_csv(regression_data, regressionResult, None, 'buyUpTrend-0')
            return True
        if(abs_yearHigh_more_than_yearLow(regression_data)
           and regression_data['yearHighChange'] < -10
           and 2 < regression_data['PCT_day_change'] < 3 and 2 < regression_data['forecast_day_PCT_change'] < 3
           and regression_data['PCT_change'] < regression_data['PCT_day_change'] + .2
           and regression_data['forecast_day_PCT_change'] < regression_data['PCT_day_change'] + .2
           and regression_data['series_trend'] != 'downTrend'
           and regression_data['score'] != '0-1' 
           and regression_data['forecast_day_PCT7_change'] < 0 and regression_data['forecast_day_PCT10_change'] < 0
           ):
            add_in_csv(regression_data, regressionResult, None, 'buyUpTrend-00')
            return True
        if(abs_yearHigh_more_than_yearLow(regression_data)
           and regression_data['yearHighChange'] < -10
           and 2 < regression_data['PCT_day_change'] < 3 and regression_data['PCT_change'] < 4
           and regression_data['forecast_day_PCT_change'] < regression_data['PCT_change']
           and regression_data['series_trend'] != 'downTrend'
           and regression_data['score'] != '0-1'
           and (regression_data['forecast_day_PCT7_change'] < 5 and regression_data['forecast_day_PCT10_change'] < 7)
           ):
            add_in_csv(regression_data, regressionResult, None, 'buyUpTrend-1')
            return True
        if(2 < regression_data['PCT_day_change'] < 3 and regression_data['PCT_change'] < 4
           and regression_data['forecast_day_PCT_change'] < regression_data['PCT_change']
           and regression_data['series_trend'] != 'downTrend'
           and regression_data['score'] != '0-1'
           and (regression_data['forecast_day_PCT7_change'] < 5 and regression_data['forecast_day_PCT10_change'] < 7)
           ):
            add_in_csv(regression_data, regressionResult, None, '##buyUpTrend-NotUpLastDay(checkBase)')
            return True
        if(2 < regression_data['PCT_day_change'] < 3 and regression_data['PCT_change'] < 4
           and regression_data['forecast_day_PCT_change'] < regression_data['PCT_change']
           and regression_data['series_trend'] != 'downTrend'
           and regression_data['score'] != '0-1'
           and (regression_data['forecast_day_PCT7_change'] < 10 and regression_data['forecast_day_PCT10_change'] < 10)
           ):
            #add_in_csv(regression_data, regressionResult, None, 'buyUpTrend-onlyNews')
            return False
    elif((regression_data['yearHighChange'] < -9 or regression_data['yearLowChange'] < 15)
       and regression_data['forecast_day_PCT_change'] > 0
       and regression_data['forecast_day_PCT2_change'] > 0
       and regression_data['forecast_day_PCT3_change'] > 0    
       ):
        if(2 < regression_data['PCT_day_change'] < 3 and regression_data['PCT_change'] < 3
               and regression_data['forecast_day_PCT_change'] < regression_data['PCT_change']
               and regression_data['series_trend'] != 'downTrend'
               and regression_data['score'] != '0-1'
               and (regression_data['forecast_day_PCT7_change'] < 5 or regression_data['forecast_day_PCT10_change'] < 7)
               ):
                ##add_in_csv(regression_data, regressionResult, None, '##buyUpTrend-1-YearHigh')
                return False    
    if(all_day_pct_change_positive(regression_data) and 0 < regression_data['PCT_day_change'] < 5 and regression_data['yearHighChange'] < -10
        and regression_data['forecast_day_PCT10_change'] >= regression_data['PCT_change'] + 2
        and regression_data['forecast_day_PCT10_change'] >= regression_data['PCT_day_change'] + 2
        and float(regression_data['forecast_day_VOL_change']) > 30
        and regression_data['PCT_day_change_pre1'] > -0.5 
        and float(regression_data['contract']) > 10
        and no_doji_or_spinning_buy_india(regression_data)):
        add_in_csv(regression_data, regressionResult, ws_buyUpTrend, '##buyUpTrend-Risky')
        return True
    return False

def buy_down_trend(regression_data, regressionResult, ws_buyDownTrend):
    if(all_day_pct_change_negative_except_today(regression_data) 
        and regression_data['forecast_day_PCT_change'] > 0 
        and 0 < regression_data['PCT_day_change'] < 5 and 0 < regression_data['PCT_change']
        and regression_data['yearHighChange'] < -10 
        and high_tail_pct(regression_data) < 0.5
       ):
        if(ten_days_less_than_minus_ten(regression_data)
            ):
            add_in_csv(regression_data, regressionResult, ws_buyDownTrend, 'buyDownTrend-0')
            return True
        elif(last_5_day_all_down_except_today(regression_data)
            and regression_data['forecast_day_PCT7_change'] < -4
            and regression_data['forecast_day_PCT10_change'] < -4
            ):
            add_in_csv(regression_data, regressionResult, ws_buyDownTrend, '##buyDownTrend-1')
            return True
        elif(regression_data['forecast_day_PCT7_change'] < -4
            and regression_data['forecast_day_PCT10_change'] < -4
            ):
            add_in_csv(regression_data, regressionResult, ws_buyDownTrend, '##buyDownTrend-1-downLastDay')
            return True
        
    return False

def buy_final(regression_data, regressionResult, ws_buyFinal, ws_buyFinal1):
    if(regression_data['yearHighChange'] < -10 and regression_data['score'] != '0-1'
        and 4 > regression_data['PCT_day_change'] > 1 and 4 > regression_data['PCT_change'] > 1
        and abs(regression_data['PCT_day_CH']) < 0.3
        and regression_data['forecast_day_VOL_change'] > 0
        and high_tail_pct(regression_data) < 0.5
        ):   
        if(str(regression_data['sellIndia']) == '' and -90 < regression_data['yearHighChange'] < -10
            and(ten_days_less_than_minus_ten(regression_data)
                 or last_5_day_all_down_except_today(regression_data)
            ) 
            and regression_data['forecast_day_PCT7_change'] < -5 
            and regression_data['forecast_day_PCT5_change'] < 0.5 
            and regression_data['forecast_day_PCT4_change'] < 0.5 
            and 5 > regression_data['forecast_day_PCT2_change'] > -0.5 
            and regression_data['forecast_day_PCT_change'] > 0
            ):
            add_in_csv(regression_data, regressionResult, ws_buyFinal, 'buyFinal')
        elif(str(regression_data['sellIndia']) == '' and -90 < regression_data['yearHighChange'] < -10
            and(ten_days_less_than_minus_ten(regression_data)
                 or last_5_day_all_down_except_today(regression_data)
            ) 
            and regression_data['forecast_day_PCT7_change'] <= -1 
            and regression_data['forecast_day_PCT5_change'] <= 1  
            and regression_data['forecast_day_PCT2_change'] > 0 
            and regression_data['forecast_day_PCT_change'] > 0
            ):
            add_in_csv(regression_data, regressionResult, ws_buyFinal, 'buyFinal1')
    if(regression_data['forecast_day_PCT4_change'] <= 0.5
       and regression_data['forecast_day_PCT5_change'] <= 0.5
       and regression_data['forecast_day_PCT7_change'] <= 0.5
       and (ten_days_less_than_minus_ten(regression_data)
            or last_5_day_all_down_except_today(regression_data)
            )
       and regression_data['yearLowChange'] > 5 and regression_data['yearHighChange'] < -5
       and high_tail_pct(regression_data) < 0.5
    ):
       if(regression_data['forecast_day_PCT_change'] > 0
          and regression_data['bar_high'] > regression_data['bar_high_pre']
          and regression_data['forecast_day_VOL_change'] > 0
          ):
           if(2 < regression_data['PCT_day_change'] < 4 and 2 < regression_data['PCT_change'] < 4
               and regression_data['PCT_day_change_pre1'] < 0
            ):
               add_in_csv(regression_data, regressionResult, ws_buyFinal, 'buyFinalCandidate-0')
               return True
           if(2 < regression_data['PCT_day_change'] < 5 and 2 < regression_data['PCT_change'] < 3
               and regression_data['PCT_day_change_pre1'] < 0
            ):
               add_in_csv(regression_data, regressionResult, ws_buyFinal, 'buyFinalCandidate-00')
               return True
           if(2 < regression_data['PCT_day_change'] < 6.5 and 2 < regression_data['PCT_change'] < 6.5
               and regression_data['PCT_day_change_pre1'] < 0
            ):
               add_in_csv(regression_data, regressionResult, ws_buyFinal, 'buyFinalCandidate-00HighChange')
               return True
           if(1 < regression_data['PCT_day_change'] < 2.5 and 1 < regression_data['PCT_change'] < 2.5
               and regression_data['PCT_day_change_pre1'] > 0
               and (regression_data['mlpValue'] > 1 or regression_data['kNeighboursValue'] > 1)
            ):
               add_in_csv(regression_data, regressionResult, ws_buyFinal, 'buyFinalCandidate-1')
               return True
           if(1 < regression_data['PCT_day_change'] < 4 and 1 < regression_data['PCT_change'] < 4
               and no_doji_or_spinning_buy_india(regression_data)
               and regression_data['PCT_day_change_pre1'] > 0
               and (regression_data['mlpValue'] > 1 or regression_data['kNeighboursValue'] > 1)
            ):
               add_in_csv(regression_data, regressionResult, ws_buyFinal, 'buyFinalCandidate-2')
               return True
           if(0.5 < regression_data['PCT_day_change'] < 2.5 and 0.5 < regression_data['PCT_change'] < 2.5
               and regression_data['PCT_day_change_pre1'] > 0
               and (regression_data['mlpValue'] > 1 or regression_data['kNeighboursValue'] > 1)
            ):
               add_in_csv(regression_data, regressionResult, ws_buyFinal, '##buyFinalCandidate-2-test')
               return True
       if((((regression_data['close'] - regression_data['open']) * 1.5 > regression_data['high'] - regression_data['low']) or (regression_data['forecast_day_PCT_change'] > 0 and regression_data['PCT_day_change'] > 1))
           and (regression_data['yearHighChange'] < -30 or regression_data['yearLowChange'] < 30)
           ):
           if(1 < regression_data['PCT_day_change'] < 2.5 and 1 < regression_data['PCT_change'] < 2.5 
               and no_doji_or_spinning_sell_india(regression_data) and no_doji_or_spinning_buy_india(regression_data)
               ):
               if(((regression_data['mlpValue'] > 0.5 and regression_data['kNeighboursValue'] > 0.5) or is_algo_buy(regression_data))
                   and regression_data['forecast_day_VOL_change'] > -20
                   ):
                   add_in_csv(regression_data, regressionResult, ws_buyFinal, 'buyFinalCandidate-3')
                   return True
           if(1 < regression_data['PCT_day_change'] < 5 and 1 < regression_data['PCT_change'] < 5 
               and no_doji_or_spinning_sell_india(regression_data) and no_doji_or_spinning_buy_india(regression_data)
               ):
               if(((regression_data['mlpValue'] > 0.5 and regression_data['kNeighboursValue'] > 0.5) or is_algo_buy(regression_data))
                   and regression_data['forecast_day_VOL_change'] > 0 
                   ):
                   add_in_csv(regression_data, regressionResult, ws_buyFinal, '##buyFinalCandidate-4')
                   return True
       if(0 < regression_data['PCT_day_change'] < 1 and 0 < regression_data['PCT_change'] < 1 
           and no_doji_or_spinning_sell_india(regression_data) and no_doji_or_spinning_buy_india(regression_data)
           and (regression_data['mlpValue'] > 1 or regression_data['kNeighboursValue'] > 1)
           ):
           add_in_csv(regression_data, regressionResult, ws_buyFinal, '##buyFinalCandidate-5-(downLastDayOrUp2to3)')
           return True
    return False

def buy_high_indicators(regression_data, regressionResult, ws_buyHighIndicators):
    if(regression_data['mlpValue'] > 1.0 and regression_data['kNeighboursValue'] > 1.0 and regression_data['yearLowChange'] < 16 and regression_data['yearHighChange'] < -35
        and (2.5 > regression_data['PCT_day_change'] > 0 and 2.5 > regression_data['PCT_change'] > -0.5)
        ):
        add_in_csv(regression_data, regressionResult, ws_buyHighIndicators, 'buyHighIndicators')
        return True
    return False
              
def buy_pattern(regression_data, regressionResult, ws_buyPattern, ws_buyPattern1):
    score = ''
    if(regression_data['score'] == '10' or regression_data['score'] == '1-1'):
        score = 'up'
    if(-1 < regression_data['PCT_day_change'] < 4 and regression_data['yearLowChange'] > 5 and regression_data['score'] != '0-1'
        #and regression_data['trend'] != 'up'
    ):
        if(('MARUBOZU' in str(regression_data['buyIndia']) and regression_data['forecast_day_PCT5_change'] <= 0 and regression_data['forecast_day_PCT10_change'] <= -5)
           or ('HAMMER' in str(regression_data['buyIndia']) and regression_data['PCT_day_change'] > 0)
           #or 'ENGULFING' in str(regression_data['buyIndia'])
           #or 'PIERCING' in str(regression_data['buyIndia'])
           or ('MORNINGSTAR' in str(regression_data['buyIndia']) and regression_data['forecast_day_PCT5_change'] <= 0 and regression_data['forecast_day_PCT10_change'] <= -5)
           #or ':DOJISTAR' in str(regression_data['buyIndia'])
           #or 'MORNINGDOJISTAR' in str(regression_data['buyIndia'])
           or 'ABANDONEDBABY' in str(regression_data['buyIndia'])
           or 'COUNTERATTACK' in str(regression_data['buyIndia'])
           or 'KICKING' in str(regression_data['buyIndia'])
           or 'BREAKAWAY' in str(regression_data['buyIndia'])
           #or 'TRISTAR' in str(regression_data['buyIndia'])
           #or '3WHITESOLDIERS' in str(regression_data['buyIndia'])
           #or '3INSIDE' in str(regression_data['buyIndia'])
           ):
            add_in_csv(regression_data, regressionResult, ws_buyPattern, 'buyPattern')
            return True
        elif(
           ('CCI:BOP' in str(regression_data['buyIndia']) and 'BELTHOLD' in str(regression_data['buyIndia']))
           or ('AROON:BOP' in str(regression_data['buyIndia']) and 'BELTHOLD' in str(regression_data['buyIndia']) and 'ENGULFING' in str(regression_data['buyIndia']))
           or ('BELTHOLD' == str(regression_data['buyIndia']) and score == 'up')
           #or ('3OUTSIDE' in str(regression_data['buyIndia']) and regression_data['forecast_day_PCT5_change'] <= 0 and score == 'up')
           #or ('HARAMI' in str(regression_data['buyIndia']) and regression_data['forecast_day_PCT5_change'] <= 0 and score == 'up')
           #or (regression_data['yearHighChange'] <= -35 and 'HARAMI' in str(regression_data['buyIndia']) and 'SHORTLINE' in str(regression_data['buyIndia']) and regression_data['PCT_day_change'] > 0)
           or ('DOJI' in str(regression_data['buyIndia']) and 'GRAVESTONEDOJI' in str(regression_data['buyIndia']) and 'LONGLEGGEDDOJI' in str(regression_data['buyIndia']) and regression_data['PCT_day_change'] > 0)
           #or ('P@[,HIKKAKE]' == str(regression_data['buyIndia']) and regression_data['PCT_day_change'] < 0)
           #or (regression_data['yearHighChange'] <= -35 and 'BELTHOLD' in str(regression_data['buyIndia']) and 'LONGLINE' in str(regression_data['buyIndia']))
           #or (regression_data['yearHighChange'] <= -35 and ',CCI:BOP' in str(regression_data['buyIndia']) and 'LONGLINE' in str(regression_data['buyIndia']))
           ) and ((regression_data['forecast_day_PCT5_change'] <= -5) or regression_data['yearHighChange'] < -50):
            add_in_csv(regression_data, regressionResult, ws_buyPattern1, 'buyPattern1')
            return True
        elif(
           ('MARUBOZU' in str(regression_data['buyIndia']) and regression_data['forecast_day_PCT5_change'] <= 0 and regression_data['forecast_day_PCT10_change'] <= 1)
           or ('HAMMER' in str(regression_data['buyIndia']) and regression_data['PCT_day_change'] > 0)
           or 'ENGULFING' in str(regression_data['buyIndia'])
           or 'PIERCING' in str(regression_data['buyIndia'])
           or ('MORNINGSTAR' in str(regression_data['buyIndia']) and regression_data['forecast_day_PCT5_change'] <= 0 and regression_data['forecast_day_PCT10_change'] <= 1)
           #or ':DOJISTAR' in str(regression_data['buyIndia'])
           or 'MORNINGDOJISTAR' in str(regression_data['buyIndia'])
           or 'ABANDONEDBABY' in str(regression_data['buyIndia'])
           or 'COUNTERATTACK' in str(regression_data['buyIndia'])
           or 'KICKING' in str(regression_data['buyIndia'])
           or 'BREAKAWAY' in str(regression_data['buyIndia'])
           or 'TRISTAR' in str(regression_data['buyIndia'])
           or '3WHITESOLDIERS' in str(regression_data['buyIndia'])
           or '3INSIDE' in str(regression_data['buyIndia'])
           ) and 'DOJI' not in str(regression_data['buyIndia']) and ((regression_data['forecast_day_PCT5_change'] <= -5) or regression_data['yearHighChange'] < -50): 
            add_in_csv(regression_data, regressionResult, ws_buyPattern1, 'buyPattern1')
            return True
    return False

def buy_morning_star_buy(regression_data, regressionResult, ws):
    if(-5 < regression_data['forecast_day_PCT_change'] < -2
        and regression_data['PCT_day_change_pre1'] < 0
        and (BUY_VERY_LESS_DATA or ten_days_less_than_minus_seven(regression_data))
        and regression_data['yearHighChange'] < -20
        and high_tail_pct(regression_data) < 0.5
        ):
        if(-1.5 < regression_data['PCT_day_change'] < 0 and -1.5 < regression_data['PCT_change'] < 0
            and (regression_data['close'] - regression_data['low']) >= ((regression_data['open'] - regression_data['close']) * 3)
            and (regression_data['close'] - regression_data['low']) >= ((regression_data['high'] - regression_data['open']) * 3)
            ):
            add_in_csv(regression_data, regressionResult, ws, 'morningStarBuy-0-NotUpSecondHalfAndUp2to3')
            return True
        if(0 < regression_data['PCT_day_change'] < 1
            and (regression_data['open'] - regression_data['low']) >= ((regression_data['open'] - regression_data['close']) * 3)
            and (regression_data['open'] - regression_data['low']) >= ((regression_data['high'] - regression_data['close']) * 3)
            ):
            add_in_csv(regression_data, regressionResult, ws, 'morningStarBuy-1-NotUpSecondHalfAndUp2to3')
            return True
    if(-8 < regression_data['forecast_day_PCT_change'] < -3
        and regression_data['PCT_day_change_pre1'] < -4
        and regression_data['yearHighChange'] < -20
        ):
        if(-3 < regression_data['PCT_day_change'] < -1 and -3 < regression_data['PCT_change'] < -1
            and (regression_data['close'] - regression_data['low']) > ((regression_data['open'] - regression_data['close']))
            and (regression_data['close'] - regression_data['low']) >= ((regression_data['high'] - regression_data['open']) * 3)
            ):
            add_in_csv(regression_data, regressionResult, ws, '##morningStarBuy-2-NotUpSecondHalfAndUp2to3(checkBase)')
            return True
    return False

def buy_evening_star_sell(regression_data, regressionResult, ws):
    if(5 > regression_data['forecast_day_PCT_change'] > 2
        and regression_data['PCT_day_change_pre1'] > 0
        and (SELL_VERY_LESS_DATA and ten_days_more_than_seven(regression_data))
        and regression_data['yearLowChange'] > 20
        and low_tail_pct(regression_data) < 0.5
        ):
        if(-1 < regression_data['PCT_day_change'] < 0 and -1 < regression_data['PCT_change'] < 0 
            and regression_data['kNeighboursValue'] < 0
            ):
            add_in_csv(regression_data, regressionResult, ws, 'eveningStarSell-0-NotDownSecondHalfAndDown2to3')
            return True
        if(1.5 > regression_data['PCT_day_change'] > 0 and 1.5 > regression_data['PCT_change'] > 0
            and (regression_data['high']-regression_data['close']) >= ((regression_data['close']-regression_data['open']) * 3)
            and (regression_data['high']-regression_data['close']) >= ((regression_data['open']-regression_data['low'])*3)
            ):
            add_in_csv(regression_data, regressionResult, ws, 'eveningStarSell-1-NotDownSecondHalfAndDown2to3')
            return True
    if(8 > regression_data['forecast_day_PCT_change'] > 3
        and regression_data['PCT_day_change_pre1'] > 4
        and regression_data['yearLowChange'] > 20
        ):
        if(3 > regression_data['PCT_day_change'] > 1 and 3 > regression_data['PCT_change'] > 1
            and (regression_data['high']-regression_data['close']) > ((regression_data['close']-regression_data['open']))
            and (regression_data['high']-regression_data['close']) >= ((regression_data['open']-regression_data['low'])*3)
            ):
            add_in_csv(regression_data, regressionResult, ws, '##eveningStarSell-2-NotDownSecondHalfAndDown2to3(checkBase)')
            return True
    return False

def buy_oi_negative(regression_data, regressionResult, ws):
    if(regression_data['redtrend'] == -1
        and regression_data['forecast_day_PCT_change'] < 0
        and regression_data['forecast_day_PCT2_change'] < -0.5
        and regression_data['forecast_day_PCT3_change'] < -0.5
        and regression_data['forecast_day_PCT4_change'] < -0.5
        and regression_data['forecast_day_PCT5_change'] < -0.5
        and regression_data['forecast_day_PCT7_change'] < -0.5
        and ten_days_less_than_minus_ten(regression_data)
        and float(regression_data['forecast_day_VOL_change']) < -30
        and regression_data['PCT_day_change_pre1'] < 0 
        and float(regression_data['contract']) < 0
        and float(regression_data['oi']) < 5
        and (regression_data['yearHighChange'] < -15 or regression_data['yearLowChange'] < 15)
        and ((regression_data['mlpValue'] > 0 and regression_data['kNeighboursValue'] > 0) or is_algo_buy(regression_data))
        ):
        if(((-1 < regression_data['PCT_day_change'] < 0 and -1 < regression_data['PCT_change'] < -0.5)
            or (-1 < regression_data['PCT_day_change'] < -0.5 and -1 < regression_data['PCT_change'] < 0))
            ):
            add_in_csv(regression_data, regressionResult, ws, 'buyNegativeOI-0-checkBase(1%down)')
            return True
        if(-2 < regression_data['PCT_day_change'] < 0 and -2 < regression_data['PCT_change'] < 0
            ):
            add_in_csv(regression_data, regressionResult, ws, 'buyNegativeOI-1-checkBase(1%down)')
            return True
    return False

def buy_day_low(regression_data, regressionResult, ws):
    if((regression_data['PCT_day_change'] < -6 or regression_data['PCT_change'] < -6)
       and float(regression_data['forecast_day_VOL_change']) < -30
       and ((regression_data['mlpValue'] > 0.3 and regression_data['kNeighboursValue'] > 0.3) or is_algo_buy(regression_data))
       and (regression_data['PCT_day_change_pre1'] < -1.5)
       and regression_data['PCT_day_change'] < regression_data['PCT_day_change_pre1'] < 0
       ):
        add_in_csv(regression_data, regressionResult, ws, 'dayLowBuy-ML')
        return True
    if((regression_data['PCT_day_change'] < -6 or regression_data['PCT_change'] < -6)
       and float(regression_data['forecast_day_VOL_change']) < -30
       and (regression_data['PCT_day_change_pre1'] < -1.5)
       and regression_data['PCT_day_change'] < regression_data['PCT_day_change_pre1'] < 0
       ):
        add_in_csv(regression_data, regressionResult, ws, 'dayLowVolLowBuy-0')
        return True
    if((regression_data['PCT_day_change'] < -6 or regression_data['PCT_change'] < -6)
       and float(regression_data['forecast_day_VOL_change']) < 0
       and (regression_data['PCT_day_change_pre1'] < -1.5)
       and regression_data['PCT_day_change'] < regression_data['PCT_day_change_pre1'] < 0
       ):
        add_in_csv(regression_data, regressionResult, ws, 'dayLowVolLowBuy-00')
        return True
    if((regression_data['PCT_day_change'] < -3 and regression_data['PCT_change'] < -3)
       and abs_yearHigh_less_than_yearLow(regression_data)
       and float(regression_data['forecast_day_VOL_change']) < -30
       and (regression_data['PCT_day_change_pre1'] < -1.5)
       and regression_data['PCT_day_change'] < regression_data['PCT_day_change_pre1'] < 0
       and regression_data['PCT_day_change_pre2'] > 1
       ):
        add_in_csv(regression_data, regressionResult, ws, 'dayLowVolLowBuy-1-checkMorningTrend(.5SL)-NotYearLow')
        return True
#     if((regression_data['PCT_day_change'] < -2 and regression_data['PCT_change'] < -2)
#        and float(regression_data['forecast_day_VOL_change']) < -30
#        and regression_data['PCT_day_change'] < regression_data['PCT_day_change_pre1'] < 0
#        and regression_data['forecast_day_PCT7_change'] > 7
#        and regression_data['forecast_day_PCT10_change'] > 10
#        ):
#         add_in_csv(regression_data, regressionResult, ws, '##dayLowVolLowBuy-2')
#         return True
    return False

def buy_year_high_oi(regression_data, regressionResult, ws):
    if((-1 < regression_data['PCT_day_change'] < 0 and -1 < regression_data['PCT_change'] < 0)
       and regression_data['PCT_day_change_pre1'] > -1.5
       and float(regression_data['forecast_day_VOL_change']) < -30
       and -5 < regression_data['forecast_day_PCT_change'] < 1
       and -5 < regression_data['forecast_day_PCT2_change'] < 1
       and -5 < regression_data['forecast_day_PCT3_change'] < 1
       and -5 < regression_data['forecast_day_PCT4_change'] < 1
       and -5 < regression_data['forecast_day_PCT5_change'] < 1
       and 0 < regression_data['forecast_day_PCT7_change'] < 5
       and 1 < regression_data['forecast_day_PCT10_change']
       and regression_data['yearHighChange'] > -7
       ):
        if(regression_data['forecast_day_PCT2_change'] < -1
           or regression_data['forecast_day_PCT3_change'] < -1
           or regression_data['forecast_day_PCT4_change'] < -1
           or regression_data['forecast_day_PCT5_change'] < -1
        ):
            add_in_csv(regression_data, regressionResult, ws, '##yearHighBuy-0')
            return True
    return False

def buy_vol_contract(regression_data, regressionResult, ws):
    if(((regression_data['mlpValue'] > 0.3 and regression_data['kNeighboursValue'] > 0.3) or is_algo_buy(regression_data))
       and regression_data['forecast_day_PCT10_change'] < 10  
       and (float(regression_data['contract']) != 0 or float(regression_data['oi']) != 0)
       and float(regression_data['contract']) > 10
       and (regression_data['PCT_day_change'] > 1 or regression_data['PCT_change'] > 1)
       and regression_data['forecast_day_PCT_change'] > 0.5
       and regression_data['forecast_day_PCT2_change'] > 0.5
       and regression_data['forecast_day_PCT3_change'] > 0
       and regression_data['forecast_day_PCT4_change'] > 0
       and (regression_data['PCT_day_change'] < 0
            or regression_data['PCT_day_change_pre1'] < 0
            or regression_data['PCT_day_change_pre2'] < 0
            or regression_data['PCT_day_change_pre3'] < 0
            or regression_data['PCT_day_change_pre4'] < 0
           )
       and regression_data['yearHighChange'] < -2
       and preDayPctChangeUp_orVolHigh(regression_data)
       and regression_data['open'] > 50
       and last_4_day_all_up(regression_data) == False
       and (BUY_VERY_LESS_DATA or high_tail_pct(regression_data) < 0.7)
       ):
        if((regression_data['forecast_day_VOL_change'] > 70 and 0.75 < regression_data['PCT_day_change'] < 2 and 0.5 < regression_data['PCT_change'] < 2)
            and float(regression_data['contract']) > 10
            ):
            add_in_csv(regression_data, regressionResult, ws, 'buyOI-0')
            return True
        elif((regression_data['forecast_day_VOL_change'] > 35 and 0.75 < regression_data['PCT_day_change'] < 2 and 0.5 < regression_data['PCT_change'] < 2)
            and float(regression_data['contract']) > 20
            #and regression_data['PCT_day_change_pre1'] > -0.5
            ):
            add_in_csv(regression_data, regressionResult, ws, 'buyOI-1')
            return True
        elif((regression_data['forecast_day_VOL_change'] > 150 and 0.75 < regression_data['PCT_day_change'] < 3 and 0.5 < regression_data['PCT_change'] < 3)
            #and regression_data['PCT_day_change_pre1'] > -0.5
            ):
            add_in_csv(regression_data, regressionResult, ws, 'buyOI-2-checkBase')
            return True
        elif(((regression_data['forecast_day_VOL_change'] > 400 and 0.75 < regression_data['PCT_day_change'] < 3.5 and 0.5 < regression_data['PCT_change'] < 3.5)
            or (regression_data['forecast_day_VOL_change'] > 500 and 0.75 < regression_data['PCT_day_change'] < 4.5 and 0.5 < regression_data['PCT_change'] < 4.5)
            )
            #and regression_data['PCT_day_change_pre1'] > -0.5
            ):
            add_in_csv(regression_data, regressionResult, ws, 'buyOI-3-checkBase')
            return True
                
        elif((regression_data['forecast_day_VOL_change'] > 300 and 0.75 < regression_data['PCT_day_change'] < 5 and 0.5 < regression_data['PCT_change'] < 5)
            and float(regression_data['contract']) > 50 
            and (regression_data['forecast_day_PCT10_change'] < -8 or regression_data['forecast_day_PCT7_change'] < -8)
            ):
            add_in_csv(regression_data, regressionResult, ws, 'buyOI-4-checkBase')
            return True    
    return False

def buy_vol_contract_contrarian(regression_data, regressionResult, ws):
    if((float(regression_data['contract']) != 0 or float(regression_data['oi']) != 0)
       and regression_data['forecast_day_PCT10_change'] > 10
       and float(regression_data['contract']) > 10
       and (regression_data['PCT_day_change'] > 1 or regression_data['PCT_change'] > 1)
       and regression_data['forecast_day_PCT_change'] > 0.5
       and regression_data['forecast_day_PCT2_change'] > 0.5
       and regression_data['forecast_day_PCT3_change'] > 0
       and regression_data['forecast_day_PCT4_change'] > 0
       and preDayPctChangeUp_orVolHigh(regression_data)
       and regression_data['open'] > 50
       #and last_7_day_all_up(regression_data) == False
       ):
        if((regression_data['forecast_day_VOL_change'] > 70 and 0.75 < regression_data['PCT_day_change'] < 2 and 0.5 < regression_data['PCT_change'] < 2)
            and float(regression_data['contract']) > 10
            ):
            add_in_csv(regression_data, regressionResult, ws, 'Test:sellReversalOI-0(openAroundLastCloseAnd5MinuteChart)')
            return True
        elif((regression_data['forecast_day_VOL_change'] > 35 and 0.75 < regression_data['PCT_day_change'] < 2 and 0.5 < regression_data['PCT_change'] < 2)
            and float(regression_data['contract']) > 20
            ):
            add_in_csv(regression_data, regressionResult, ws, 'Test:sellReversalOI-1(openAroundLastCloseAnd5MinuteChart)')
            return True
        elif((regression_data['forecast_day_VOL_change'] > 150 and 0.75 < regression_data['PCT_day_change'] < 3 and 0.5 < regression_data['PCT_change'] < 3)
            #and regression_data['PCT_day_change_pre1'] > -0.5
            ):
            add_in_csv(regression_data, regressionResult, ws, 'Test:sellReversalOI-2(openAroundLastCloseAnd5MinuteChart)')
            return True
        elif(((regression_data['forecast_day_VOL_change'] > 400 and 0.75 < regression_data['PCT_day_change'] < 3.5 and 0.5 < regression_data['PCT_change'] < 3.5)
            or (regression_data['forecast_day_VOL_change'] > 500 and 0.75 < regression_data['PCT_day_change'] < 4.5 and 0.5 < regression_data['PCT_change'] < 4.5)
            )
            and regression_data['forecast_day_PCT10_change'] > 15
            ):
            add_in_csv(regression_data, regressionResult, ws, 'Test:sellReversalOI-3-checkBase-(openAroundLastCloseAnd5MinuteChart)')
            return True
        elif((regression_data['forecast_day_VOL_change'] > 300 and 0.75 < regression_data['PCT_day_change'] < 5 and 0.5 < regression_data['PCT_change'] < 5)
            and float(regression_data['contract']) > 50 
            and (regression_data['forecast_day_PCT10_change'] < -8 or regression_data['forecast_day_PCT7_change'] < -8)
            and regression_data['forecast_day_PCT10_change'] > 15
            ):
            add_in_csv(regression_data, regressionResult, ws, 'Test:sellReversalOI-4-checkBase-(openAroundLastCloseAnd5MinuteChart)')
            return True
    return False

def buy_trend_reversal(regression_data, regressionResult, ws):
    if(regression_data['forecast_day_PCT4_change'] <= 0.5
       and regression_data['forecast_day_PCT5_change'] <= 0.5
       and regression_data['forecast_day_PCT7_change'] <= 0.5
       and (ten_days_less_than_minus_ten(regression_data)
            or last_5_day_all_down_except_today(regression_data)
            )
       and regression_data['yearLowChange'] > 5 and regression_data['yearHighChange'] < -5
    ):
       if(regression_data['forecast_day_PCT_change'] > 0 and regression_data['PCT_day_change'] > 0
            and (regression_data['PCT_day_change_pre1'] > 1)
            and regression_data['PCT_day_change'] > regression_data['PCT_day_change_pre1'] > 0
            and regression_data['forecast_day_VOL_change'] <= -40
            ):
           if(1 < regression_data['PCT_day_change'] < 5 and 1 < regression_data['PCT_change'] < 5
              and regression_data['forecast_day_VOL_change'] <= -50
            ):
               add_in_csv(regression_data, regressionResult, ws, '##finalSellContinue-00')
               return True
           if(3 < regression_data['PCT_day_change'] < 5 and 3 < regression_data['PCT_change'] < 5
            ):
               add_in_csv(regression_data, regressionResult, ws, '##finalSellContinue-01-checkMorningTrend(.5SL)')
               return True
#             elif(regression_data['forecast_day_PCT_change'] > 0
#                  and regression_data['forecast_day_VOL_change'] <= -30
#                 ):
#                     add_in_csv(regression_data, regressionResult, ws, '##finalSellContinue-1')
#                     return True    
       if((((regression_data['close'] - regression_data['open']) * 1.5 > regression_data['high'] - regression_data['low']) or (regression_data['forecast_day_PCT_change'] > 0 and regression_data['PCT_day_change'] > 1))
           and (regression_data['yearHighChange'] < -30 or regression_data['yearLowChange'] < 30)
           ):
           if(1 < regression_data['PCT_day_change'] < 2.5 and 1 < regression_data['PCT_change'] < 2.5 
               and no_doji_or_spinning_sell_india(regression_data) and no_doji_or_spinning_buy_india(regression_data)
               ):
               if(regression_data['forecast_day_VOL_change'] <= -50
                  and (regression_data['PCT_day_change_pre1'] > 1)
                  and regression_data['PCT_day_change'] > regression_data['PCT_day_change_pre1'] > 0
                  ):
                   add_in_csv(regression_data, regressionResult, ws, '##finalSellContinue-1')
                   return True
               elif(regression_data['forecast_day_VOL_change'] <= -40
                  and (regression_data['PCT_day_change_pre1'] > 1)
                  and regression_data['PCT_day_change'] > regression_data['PCT_day_change_pre1'] > 0
                  ):
                   add_in_csv(regression_data, regressionResult, ws, '##finalSellContinue-1-checkBase')
                   return True
           if(1 < regression_data['PCT_day_change'] < 5 and 1 < regression_data['PCT_change'] < 5 
               and no_doji_or_spinning_sell_india(regression_data) and no_doji_or_spinning_buy_india(regression_data)
               ):
               if(regression_data['forecast_day_VOL_change'] <= -30
                  and (regression_data['PCT_day_change_pre1'] > 1)
                  and regression_data['PCT_day_change'] > regression_data['PCT_day_change_pre1'] > 0
                  ):
                   add_in_csv(regression_data, regressionResult, ws, '##finalSellContinue-2')
                   return True
               elif(regression_data['forecast_day_VOL_change'] <= -15
                  and (regression_data['PCT_day_change_pre1'] > 1)
                  and regression_data['PCT_day_change'] > regression_data['PCT_day_change_pre1'] > 0
                  ):
                   add_in_csv(regression_data, regressionResult, ws, '##finalSellContinue-2-checkBase')
                   return True
    if(ten_days_less_than_minus_five(regression_data)
       and regression_data['yearLowChange'] > 5 and regression_data['yearHighChange'] < -5
    ):
       if(regression_data['forecast_day_PCT_change'] > 0 and regression_data['PCT_day_change'] > 0
           and (regression_data['PCT_day_change_pre1'] > 1)
           and regression_data['PCT_day_change'] > regression_data['PCT_day_change_pre1'] > 0
           and regression_data['forecast_day_VOL_change'] <= -20
           ):
           if(2 < regression_data['PCT_day_change'] < 5 and 2 < regression_data['PCT_change'] < 5):
               add_in_csv(regression_data, regressionResult, ws, '##finalSellContinue-test')
               return True
    return False            

def buy_trend_break(regression_data, regressionResult, ws):
#     if(regression_data['consolidation'] == 1
#        and regression_data['PCT_day_change'] > 2 and regression_data['PCT_change'] > 2
#        ):
#         add_in_csv(regression_data, regressionResult, ws, '##TestBreakOutBuyConsolidate-0')
#         return True
    
    if(ten_days_less_than_minus_five(regression_data)
       and last_7_day_all_down(regression_data)
       and regression_data['forecast_day_PCT10_change'] > -15
       ):
        add_in_csv(regression_data, regressionResult, ws, '##TEST:BreakOutBuyCandidate-(openAroundLastCloseAnd10MinuteChart)')
        return True
    
    if(ten_days_less_than_minus_five(regression_data)
       and regression_data['yearHighChange'] < -30
       ):
       if(regression_data['forecast_day_PCT_change'] > 2 and regression_data['PCT_day_change'] > 2 and regression_data['PCT_day_change_pre1'] < 0
           and abs(regression_data['PCT_day_change']) > abs(regression_data['PCT_day_change_pre1'])
           #and regression_data['open'] == regression_data['low']
           and regression_data['forecast_day_VOL_change'] >= -20
           ):
               add_in_csv(regression_data, regressionResult, ws, '##TEST:finalBreakOutBuy-0')
               return True
    if(regression_data['yearLowChange'] < 5):
       if(regression_data['forecast_day_PCT_change'] > 3 and regression_data['PCT_day_change'] > 3
           and abs(regression_data['PCT_day_change']) > abs(regression_data['PCT_day_change_pre1'])
           #and regression_data['open'] == regression_data['low']
           and regression_data['forecast_day_VOL_change'] >= -20
           and high_tail_pct(regression_data) < 0.5
           ):
               add_in_csv(regression_data, regressionResult, ws, '##finalBreakOutBuy-1test-atYearLow')
               return True
    if(5 < regression_data['yearLowChange'] < 10 and abs_yearHigh_more_than_yearLow(regression_data)
       and regression_data['forecast_day_PCT10_change'] < 10
       and last_7_day_all_up(regression_data) == False
       and high_tail_pct(regression_data) < 0.7
       ):
       if(3 > regression_data['forecast_day_PCT_change'] > 2 and 3 > regression_data['PCT_day_change'] > 2
           and regression_data['PCT_day_change_pre1'] > 0 and regression_data['PCT_day_change_pre2'] > 0 and regression_data['PCT_day_change_pre3'] > 0
           and (regression_data['open'] == regression_data['low'] or regression_data['forecast_day_VOL_change'] >= 0)
           and regression_data['forecast_day_VOL_change'] >= -50
           ):
               add_in_csv(regression_data, regressionResult, ws, '##finalBreakOutBuyContinue-00-test-atYearLow')
               return True
       if(2 > regression_data['forecast_day_PCT_change'] > 0 and 2 > regression_data['PCT_day_change'] > 0
           and regression_data['PCT_day_change_pre1'] > 0 and regression_data['PCT_day_change_pre2'] > 0 and regression_data['PCT_day_change_pre3'] > 0
           and (regression_data['forecast_day_PCT_change'] > 0.75 or regression_data['PCT_day_change_pre1'] > 0.75 or regression_data['PCT_day_change_pre2'] > 0.75 or regression_data['PCT_day_change_pre3'] > 0.75)
           and (regression_data['open'] == regression_data['low'] or regression_data['forecast_day_VOL_change'] >= 0)
           and regression_data['forecast_day_VOL_change'] >= -50
           ):
               add_in_csv(regression_data, regressionResult, ws, '##finalBreakOutBuyContinue-0-test-atYearLow')
               return True    
    if(5 < regression_data['yearLowChange'] < 12 and abs_yearHigh_more_than_yearLow(regression_data)
       and regression_data['forecast_day_PCT10_change'] < 10
       and last_7_day_all_up(regression_data) == False
       and high_tail_pct(regression_data) < 0.7
       ):
       if(3 > regression_data['forecast_day_PCT_change'] > 2 and 3 > regression_data['PCT_day_change'] > 2
           and regression_data['PCT_day_change_pre1'] > 0 and regression_data['PCT_day_change_pre2'] > 0 and regression_data['PCT_day_change_pre3'] > 0
           #and regression_data['open'] == regression_data['low']
           and regression_data['forecast_day_VOL_change'] >= 0
           ):
               add_in_csv(regression_data, regressionResult, ws, '##finalBreakOutBuyContinue-11-test-atYearLow')
               return True
       if(2 > regression_data['forecast_day_PCT_change'] > 0 and 2 > regression_data['PCT_day_change'] > 0
           and regression_data['PCT_day_change_pre1'] > 0 and regression_data['PCT_day_change_pre2'] > 0 and regression_data['PCT_day_change_pre3'] > 0
           and (regression_data['forecast_day_PCT_change'] > 0.75 or regression_data['PCT_day_change_pre1'] > 0.75 or regression_data['PCT_day_change_pre2'] > 0.75 or regression_data['PCT_day_change_pre3'] > 0.75)
           #and regression_data['open'] == regression_data['low']
           and regression_data['forecast_day_VOL_change'] >= 0
           ):
               add_in_csv(regression_data, regressionResult, ws, '##finalBreakOutBuyContinue-1-test-atYearLow')
               return True    
           
def buy_oi_candidate(regression_data, regressionResult, ws):
    tail_pct_filter(regression_data, regressionResult)
    flag = False
    if buy_evening_star_sell(regression_data, regressionResult, ws):
        flag = True
    if buy_morning_star_buy(regression_data, regressionResult, ws):
        flag = True
    if buy_oi_negative(regression_data, regressionResult, ws):
        flag = True
    if buy_day_low(regression_data, regressionResult, ws):
        flag = True
    if buy_year_high_oi(regression_data, regressionResult, ws):
        flag = True
    if buy_vol_contract(regression_data, regressionResult, ws):
        flag = True
    if buy_vol_contract_contrarian(regression_data, regressionResult, ws):
        flag = True
    if buy_trend_reversal(regression_data, regressionResult, ws):
        flag = True
    if buy_trend_break(regression_data, regressionResult, ws):
        flag = True    
    return flag

def buy_oi(regression_data, regressionResult, ws):
    if(regression_data['forecast_day_PCT_change'] > 0.5
        and regression_data['forecast_day_PCT2_change'] > 0.5
        and (regression_data['PCT_day_change'] < 0
             or regression_data['PCT_day_change_pre1'] < 0
             or regression_data['PCT_day_change_pre2'] < 0
             or regression_data['PCT_day_change_pre3'] < 0
             or regression_data['PCT_day_change_pre4'] < 0
            )
        and float(regression_data['forecast_day_VOL_change']) > 50 
        and float(regression_data['contract']) > 50
        and(regression_data['PCT_day_change_pre1'] > 0 
               or (regression_data['volume'] > regression_data['volume_pre2'] and regression_data['volume'] > regression_data['volume_pre3'])
            )
        and regression_data['yearHighChange'] < -5
        and regression_data['open'] > 50
        and (last_4_day_all_up(regression_data) == False)
        and (BUY_VERY_LESS_DATA or high_tail_pct(regression_data) < 0.7)
        ):
        if(1 < regression_data['PCT_day_change'] < 2.5 and 1 < regression_data['PCT_change'] < 2.5       
        ):
            if(regression_data['forecast_day_PCT10_change'] < 0 or regression_data['forecast_day_PCT7_change'] < 0):
                add_in_csv(regression_data, regressionResult, ws, 'openInterest-0')
                return True
            elif(regression_data['forecast_day_PCT10_change'] < 10 or regression_data['forecast_day_PCT7_change'] < 10):
                add_in_csv(regression_data, regressionResult, ws, 'openInterest-1')
                return True
            else:
                add_in_csv(regression_data, regressionResult, ws, 'openInterest-2-Risky')
                return True
        if(1 < regression_data['PCT_day_change'] < 4 and 1 < regression_data['PCT_change'] < 4 
        ):
            if(regression_data['forecast_day_PCT10_change'] < 0 or regression_data['forecast_day_PCT7_change'] < 0):
                add_in_csv(regression_data, regressionResult, ws, 'openInterest-0-checkConsolidation')
                return True
            elif(regression_data['forecast_day_PCT10_change'] < 10 or regression_data['forecast_day_PCT7_change'] < 10):
                add_in_csv(regression_data, regressionResult, ws, 'openInterest-1-checkConsolidation')
                return True
            else:
                add_in_csv(regression_data, regressionResult, ws, 'openInterest-2-checkConsolidation-Risky')
                return True    
    return False

def buy_all_rule_filter(regression_data, regressionResult, ws):
    if(-1 < regression_data['PCT_change'] < 4
        and (BUY_VERY_LESS_DATA or (last_4_day_all_up(regression_data) == False)) #Uncomment0 If very less data
        ):
        if(all_between_zero_and_five_up_score(regression_data)
           and regression_data['yearLowChange'] > 10 and regression_data['yearHighChange'] < -10
           and 1 < regression_data['PCT_day_change'] < 1
           and 1 < regression_data['PCT_change'] < 4
           ):
            add_in_csv(regression_data, regressionResult, ws, None, '##buyAllbetwen0AND5UpScore-0') 
        if(ten_days_less_than_five(regression_data) and regression_data['series_trend'] == "downTrend"
            and ((1 < regression_data['PCT_day_change'] < 3 and 0.5 < regression_data['PCT_change'] < 3))
            and regression_data['yearLowChange'] > 10
            and ( -5 < regression_data['forecast_day_PCT2_change'] < 5
                and -5 < regression_data['forecast_day_PCT3_change'] < 5
                and -5 < regression_data['forecast_day_PCT4_change'] < 5
                and -5 < regression_data['forecast_day_PCT5_change'] < 5
                and 0 < regression_data['forecast_day_PCT7_change'] < 5
                and 0 < regression_data['forecast_day_PCT10_change'] < 5
                )
           ):
            add_in_csv(regression_data, regressionResult, ws, None, '##buyDownTrendBetween-5+5')
        if(ten_days_more_than_minus_five(regression_data) and regression_data['series_trend'] == "upTrend"
            and ((1 < regression_data['PCT_day_change'] < 3 and 0.5 < regression_data['PCT_change'] < 3))
            and regression_data['yearLowChange'] > 10
            and ( -5 < regression_data['forecast_day_PCT2_change'] < 5
                and -5 < regression_data['forecast_day_PCT3_change'] < 5
                and -5 < regression_data['forecast_day_PCT4_change'] < 5
                and -5 < regression_data['forecast_day_PCT5_change'] < 5
                and -5 < regression_data['forecast_day_PCT7_change'] < 0
                and -5 < regression_data['forecast_day_PCT10_change'] < 0
                )
            and (regression_data['forecast_day_PCT2_change'] < regression_data['forecast_day_PCT3_change'] < regression_data['forecast_day_PCT4_change'])
           ):
            add_in_csv(regression_data, regressionResult, ws, None, '##buyUpTrendBetween-5+5')
        if((1 < regression_data['PCT_day_change'] < 3 and 0.5 < regression_data['PCT_change'] < 3)
            and regression_data['yearLowChange'] > 10
            and -5 < regression_data['forecast_day_PCT2_change'] < 0
            and -5 < regression_data['forecast_day_PCT3_change'] < 0
            and -5 < regression_data['forecast_day_PCT4_change'] < 0
            and -5 < regression_data['forecast_day_PCT5_change'] < 0
            and -5 < regression_data['forecast_day_PCT7_change'] < 0
            and -5 < regression_data['forecast_day_PCT10_change'] < 0
           ):
            add_in_csv(regression_data, regressionResult, ws, None, '##buyAllNegativeExceptToday')
        add_in_csv(regression_data, regressionResult, ws, None)
        return True
    return False

def buy_all_common(regression_data, classification_data, regressionResult, ws):
    if(-1 < regression_data['PCT_change'] < 4
        and (BUY_VERY_LESS_DATA or (last_4_day_all_up(regression_data) == False)) #Uncomment0 If very less data
        ):
        if((1 < regression_data['PCT_day_change'] < 3.5 and 1 < regression_data['PCT_change'] < 3.5)
            and regression_data['yearLowChange'] > 10
            and 0 < regression_data['forecast_day_PCT2_change'] < 5
            and 0 < regression_data['forecast_day_PCT3_change'] < 5
            and 0 < regression_data['forecast_day_PCT4_change'] < 5
            and 0 < regression_data['forecast_day_PCT5_change'] < 5
            and 0 < regression_data['forecast_day_PCT7_change'] < 5
            and 0 < regression_data['forecast_day_PCT10_change'] < 5
           ):
            add_in_csv(regression_data, regressionResult, ws, None, '##buyAllPositiveExceptToday')
        if(ten_days_less_than_ten(regression_data)
            and ((1 < regression_data['PCT_day_change'] < 3.5 and 0.5 < regression_data['PCT_change'] < 3.5))
            and -1 < regression_data['forecast_day_PCT_change'] < 5
            and -1 < regression_data['forecast_day_PCT2_change'] < 5
            and 0 < regression_data['forecast_day_PCT3_change'] < 5
            and 0 < regression_data['forecast_day_PCT4_change'] < 5
            and 0 < regression_data['forecast_day_PCT5_change'] < 10
            and 0 < regression_data['forecast_day_PCT7_change'] < 10
            and 0 < regression_data['forecast_day_PCT10_change'] < 10
           ):
            add_in_csv(regression_data, regressionResult, ws, None, '##buyAllLessThan+10(DownLastDay)')
        add_in_csv(regression_data, regressionResult, ws, None)
        return True
    return False

def buy_all_filter(regression_data, regressionResult, ws_buyAllFilter):
    flag = False
    if buy_year_high(regression_data, regressionResult, None):
        add_in_csv(regression_data, regressionResult, ws_buyAllFilter, None)
        flag = True
    if buy_year_low(regression_data, regressionResult, None, None):
        add_in_csv(regression_data, regressionResult, ws_buyAllFilter, None)
        flag = True
    if buy_up_trend(regression_data, regressionResult, None):
        add_in_csv(regression_data, regressionResult, ws_buyAllFilter, None)
        flag = True
    if buy_down_trend(regression_data, regressionResult, None):
        add_in_csv(regression_data, regressionResult, ws_buyAllFilter, None)
        flag = True
    if buy_final(regression_data, regressionResult, None, None):
        add_in_csv(regression_data, regressionResult, ws_buyAllFilter, None)
        flag = True
    if buy_high_indicators(regression_data, regressionResult, None):
        add_in_csv(regression_data, regressionResult, ws_buyAllFilter, None)
        flag = True
#     if buy_pattern(regression_data, regressionResult, None, None):
#         ws_buyAllFilter.append(regressionResult) if (ws_buyAllFilter is not None) else False
#         return True
    if buy_oi(regression_data, regressionResult, None):
        add_in_csv(regression_data, regressionResult, ws_buyAllFilter, None)
        flag = True
    return flag

def sell_pattern_without_mlalgo(regression_data, regressionResult, ws_buyPattern2, ws_sellPattern2):
    sellPatternsDict=scrip_patterns_to_dict('../../data-import/nselist/all-buy-filter-by-PCT-Change.csv')
    if regression_data['sellIndia'] != '' and regression_data['sellIndia'] in sellPatternsDict:
        if (abs(float(sellPatternsDict[regression_data['sellIndia']]['avg'])) >= .1 and float(sellPatternsDict[regression_data['sellIndia']]['count']) >= 2):
            if(-3 < regression_data['PCT_day_change'] < 0.5 and float(sellPatternsDict[regression_data['sellIndia']]['avg']) < -1):
                avg = sellPatternsDict[regression_data['sellIndia']]['avg']
                count = sellPatternsDict[regression_data['sellIndia']]['count']
                #add_in_csv_hist_pattern(regression_data, regressionResult, ws_sellPattern2, 'wml_sell', avg, count)
            if(-0.5 < regression_data['PCT_day_change'] < 3 and float(sellPatternsDict[regression_data['sellIndia']]['avg']) > 1): 
                avg = sellPatternsDict[regression_data['sellIndia']]['avg']
                count = sellPatternsDict[regression_data['sellIndia']]['count']
                #add_in_csv_hist_pattern(regression_data, regressionResult, ws_buyPattern2, 'wml_sell', avg, count)

def sell_pattern_from_history(regression_data, regressionResult, ws_sellPattern2):
    sellPatternsDict=scrip_patterns_to_dict('../../data-import/nselist/patterns-sell.csv')
    sellIndiaAvg = 0
    flag = False
    if regression_data['sellIndia'] != '' and regression_data['sellIndia'] in sellPatternsDict: 
        if (abs(float(sellPatternsDict[regression_data['sellIndia']]['avg'])) >= .1):
            sellIndiaAvg = float(sellPatternsDict[regression_data['sellIndia']]['avg'])
            if(int(sellPatternsDict[regression_data['sellIndia']]['count']) >= 2):
                if(is_algo_sell(regression_data)
                    and 'P@[' not in str(regression_data['buyIndia'])
                    and regression_data['trend'] != 'down'
                    and -3 < regression_data['PCT_day_change'] < 0.5):
                    avg = sellPatternsDict[regression_data['sellIndia']]['avg']
                    count = sellPatternsDict[regression_data['sellIndia']]['count']
                    if(float(sellPatternsDict[regression_data['sellIndia']]['avg']) < -1 and int(sellPatternsDict[regression_data['sellIndia']]['count']) >= 5):
                        flag = True
                        add_in_csv_hist_pattern(regression_data, regressionResult, ws_sellPattern2, 'sellPattern2', avg, count) 
                    if(float(sellPatternsDict[regression_data['sellIndia']]['avg']) < -0.5 
                        or (float(sellPatternsDict[regression_data['sellIndia']]['avg']) < -0.3 and (ten_days_more_than_ten(regression_data) or regression_data['yearLowChange'] > 40))):
                        if(regression_data['forecast_day_PCT10_change'] > 0 and regression_data['forecast_day_PCT_change'] <= 0):
                            flag = True
                            add_in_csv_hist_pattern(regression_data, regressionResult, ws_sellPattern2, 'sellPattern2', avg, count)
                        elif(regression_data['forecast_day_PCT10_change'] < 0):    
                            flag = True
                            add_in_csv_hist_pattern(regression_data, regressionResult, ws_sellPattern2, 'sellPattern2', avg, count)
    return sellIndiaAvg, flag

def sell_all_rule(regression_data, regressionResult, sellIndiaAvg, ws_sellAll):
    if(is_algo_sell(regression_data)
        and (SELL_VERY_LESS_DATA or ((regression_data['PCT_day_change_pre1'] > 0) or (regression_data['forecast_day_VOL_change'] > 0))) #Uncomment1 If very less data
        and (regression_data['bar_low']-regression_data['low']) < (regression_data['bar_high']-regression_data['bar_low'])
        and 'P@[' not in str(regression_data['buyIndia'])
        and sellIndiaAvg <= 0.70
        and (SELL_VERY_LESS_DATA or (last_4_day_all_down(regression_data) == False)) #Uncomment0 If very less data
        and (SELL_VERY_LESS_DATA or low_tail_pct(regression_data) < 0.7)
        ):
        tail_pct_filter(regression_data, regressionResult)
        sell_all_rule_filter(regression_data, regressionResult, None)
        add_in_csv(regression_data, regressionResult, ws_sellAll, None)
        if(-10 < regression_data['yearHighChange'] < 0):
            if(regression_data['PCT_day_change'] > 1):    
                return True
        else:
            return True
    return False

def sell_all_rule_classifier(regression_data, regressionResult, sellIndiaAvg, ws_sellAll):
    if(is_algo_sell_classifier(regression_data)
        and ((regression_data['PCT_day_change_pre1'] > 0) or (regression_data['forecast_day_VOL_change'] > 0))
        and (regression_data['bar_low']-regression_data['low']) < (regression_data['bar_high']-regression_data['bar_low'])
        and 'P@[' not in str(regression_data['buyIndia'])
        and sellIndiaAvg <= 0.5
        and (SELL_VERY_LESS_DATA or (last_4_day_all_down(regression_data) == False)) #Uncomment0 If very less data
        and (SELL_VERY_LESS_DATA or low_tail_pct(regression_data) < 0.7)
        ):
        tail_pct_filter(regression_data, regressionResult)
        sell_all_rule_filter(regression_data, regressionResult, None)
        add_in_csv(regression_data, regressionResult, ws_sellAll, None)
        if(-10 < regression_data['yearHighChange'] < 0):
            if(regression_data['PCT_day_change'] > 1):
                return True
        else:
            return True
    return False
        
def sell_year_high(regression_data, regressionResult, ws_sellYearHigh, ws_sellYearHigh1):
    if(-10 < regression_data['yearHighChange'] < -1 and regression_data['yearLowChange'] > 30 and -5 < regression_data['PCT_day_change'] < -0.75 
        and ten_days_more_than_ten(regression_data) and regression_data['forecast_day_PCT7_change'] > 5 and regression_data['forecast_day_PCT5_change'] > -0.5 and regression_data['forecast_day_PCT4_change'] > -0.5
        and regression_data['forecast_day_PCT2_change'] < 0 and regression_data['forecast_day_PCT_change'] < 0
        and float(regression_data['forecast_day_VOL_change']) > 0
        ):
        add_in_csv(regression_data, regressionResult, ws_sellYearHigh, 'sellYearHigh')
        return True
    elif(-10 < regression_data['yearHighChange'] < 0 and regression_data['yearLowChange'] > 30 
        and (regression_data['PCT_day_change'] < 0 and regression_data['PCT_change'] < 0.5)
        and regression_data['forecast_day_PCT10_change'] > 5 and regression_data['forecast_day_PCT7_change'] > 3 and regression_data['forecast_day_PCT5_change'] > -0.5
        and regression_data['forecast_day_PCT2_change'] < 0 and regression_data['forecast_day_PCT_change'] < 0
        and float(regression_data['forecast_day_VOL_change']) > 0
        ):
        add_in_csv(regression_data, regressionResult, ws_sellYearHigh1, 'sellYearHigh1')
        return True
    elif(-10 < regression_data['yearHighChange'] < 0 and regression_data['yearLowChange'] > 30 
        and (regression_data['PCT_day_change'] < 0 and regression_data['PCT_change'] < 0.5)
        and regression_data['forecast_day_PCT10_change'] > 0 and regression_data['forecast_day_PCT7_change'] > 0 and regression_data['forecast_day_PCT5_change'] > 0
        and regression_data['forecast_day_PCT2_change'] < 0 and regression_data['forecast_day_PCT_change'] < 0
        and float(regression_data['forecast_day_VOL_change']) > 0
        ):
        add_in_csv(regression_data, regressionResult, ws_sellYearHigh1, 'sellYearHigh1')
        return True   
    return False

def sell_year_low(regression_data, regressionResult, ws_sellYearLow):
    if(0 < regression_data['yearLowChange'] < 2 and regression_data['yearHighChange'] < -30 
        and -2 < regression_data['PCT_day_change'] < 0 and regression_data['forecast_day_PCT_change'] < 0
        and (regression_data['score'] != '1-1' or regression_data['score'] != '10')
        and all_day_pct_change_negative(regression_data) and no_doji_or_spinning_sell_india(regression_data)
        and float(regression_data['forecast_day_VOL_change']) > 30
        and regression_data['PCT_day_change_pre1'] < 0.5
        ):
        add_in_csv(regression_data, regressionResult, ws_sellYearLow, 'sellYearLow')
        return True
    return False

def sell_up_trend(regression_data, regressionResult, ws_sellUpTrend):
    if(all_day_pct_change_positive_except_today(regression_data)
       and regression_data['forecast_day_PCT_change'] < 0 
       and -5 < regression_data['PCT_day_change'] < 0 and regression_data['PCT_change'] < 0
       and regression_data['yearLowChange'] > 30
       and low_tail_pct(regression_data) < 0.5
       ):
        if (ten_days_more_than_ten(regression_data)
            ):
            add_in_csv(regression_data, regressionResult, ws_sellUpTrend, 'sellUpTrend-0')
            return True
        elif(last_5_day_all_up_except_today(regression_data)
            and regression_data['forecast_day_PCT7_change'] > 4
            and regression_data['forecast_day_PCT10_change'] > 4
            ):
            add_in_csv(regression_data, regressionResult, ws_sellUpTrend, '##sellUpTrend-1')
            return True
        elif(regression_data['forecast_day_PCT7_change'] > 4
            and regression_data['forecast_day_PCT10_change'] > 4
            ):
            add_in_csv(regression_data, regressionResult, ws_sellUpTrend, '##sellUpTrend-1-upLastDay')
            return True
    return False

def sell_down_trend(regression_data, regressionResult, ws_sellDownTrend):
    if((regression_data['yearLowChange'] > 15 or regression_data['yearHighChange'] < -15)
       and regression_data['forecast_day_PCT_change'] < 0
       and regression_data['forecast_day_PCT2_change'] < 0
       and regression_data['forecast_day_PCT3_change'] < 0
       ):
        if(-3 < regression_data['PCT_day_change'] < -2 and -3 < regression_data['forecast_day_PCT_change'] < -2
           and regression_data['PCT_change'] < regression_data['PCT_day_change'] - 0.2
           and regression_data['forecast_day_PCT_change'] < regression_data['PCT_day_change'] - 0.2
           and regression_data['series_trend'] != 'upTrend'
           and regression_data['score'] != '10' 
           and ten_days_more_than_ten(regression_data)
           ):
            add_in_csv(regression_data, regressionResult, None, 'sellDownTrend-0')
            return True
        if(-3 < regression_data['PCT_day_change'] < -2 and -3 < regression_data['forecast_day_PCT_change'] < -2
           and regression_data['PCT_change'] < regression_data['PCT_day_change'] - 0.2
           and regression_data['forecast_day_PCT_change'] < regression_data['PCT_day_change'] - 0.2
           and regression_data['series_trend'] != 'upTrend'
           and regression_data['score'] != '10' 
           and (regression_data['forecast_day_PCT7_change'] > 0 and regression_data['forecast_day_PCT10_change'] > 0)
           ):
            add_in_csv(regression_data, regressionResult, None, 'sellDownTrend-00')
            return True
        if(abs_yearHigh_less_than_yearLow(regression_data)
           and regression_data['yearHighChange'] < -10 
           and -3 < regression_data['PCT_day_change'] < -2 and -4 < regression_data['forecast_day_PCT_change'] 
           and regression_data['forecast_day_PCT_change'] > regression_data['PCT_change']
           and regression_data['series_trend'] != 'upTrend'
           and regression_data['score'] != '10'
           and (regression_data['forecast_day_PCT7_change'] > -5 and regression_data['forecast_day_PCT10_change'] > -7) 
           ):
            add_in_csv(regression_data, regressionResult, None, 'sellDownTrend-1')
            return True
        if(-3 < regression_data['PCT_day_change'] < -2 and -4 < regression_data['forecast_day_PCT_change'] 
           and regression_data['forecast_day_PCT_change'] > regression_data['PCT_change']
           and regression_data['series_trend'] != 'upTrend'
           and regression_data['score'] != '10'
           and (regression_data['forecast_day_PCT7_change'] > -5 and regression_data['forecast_day_PCT10_change'] > -7) 
           ):
            add_in_csv(regression_data, regressionResult, None, '##sellDownTrend-NotDownLastDay(checkBase)')
            return True
        if(-3 < regression_data['PCT_day_change'] < -2 and -4 < regression_data['forecast_day_PCT_change'] 
           and regression_data['forecast_day_PCT_change'] > regression_data['PCT_change']
           and regression_data['series_trend'] != 'upTrend'
           and regression_data['score'] != '10'
           and (regression_data['forecast_day_PCT7_change'] > -10 and regression_data['forecast_day_PCT10_change'] > -10) 
           ):
            #add_in_csv(regression_data, regressionResult, None, 'sellDownTrend-2-onlyNews')
            return False
    if(all_day_pct_change_negative(regression_data) and -5 < regression_data['PCT_day_change'] < 0 and regression_data['yearLowChange'] > 30
        and regression_data['forecast_day_PCT10_change'] <= regression_data['PCT_change'] - 2
        and regression_data['forecast_day_PCT10_change'] <= regression_data['PCT_day_change'] - 2
        and float(regression_data['forecast_day_VOL_change']) > 30
        and regression_data['PCT_day_change_pre1'] < 0.5
        and float(regression_data['contract']) > 10
        and no_doji_or_spinning_sell_india(regression_data)):
        add_in_csv(regression_data, regressionResult, ws_sellDownTrend, '##sellDownTrend-Risky')
        return True
    return False

def sell_final(regression_data, regressionResult, ws_sellFinal, ws_sellFinal1):
    if(regression_data['yearLowChange'] > 10 and regression_data['score'] != '10'
       and -4 < regression_data['PCT_day_change'] < -1 and -4 < regression_data['PCT_change'] < -1
       and regression_data['forecast_day_VOL_change'] > 0
       and abs(regression_data['PCT_day_LC']) < 0.3
       and low_tail_pct(regression_data) < 0.5
       ):
        if(str(regression_data['buyIndia']) == '' and -90 < regression_data['yearHighChange'] < -10
            and (ten_days_more_than_ten(regression_data)
                 or last_5_day_all_up_except_today(regression_data)
            ) 
            and regression_data['forecast_day_PCT7_change'] > 5 
            and regression_data['forecast_day_PCT5_change'] > -0.5 
            and regression_data['forecast_day_PCT4_change'] > -0.5
            and regression_data['forecast_day_PCT2_change'] < 0 
            and regression_data['forecast_day_PCT_change'] < 0):
            add_in_csv(regression_data, regressionResult, ws_sellFinal, 'sellFinal')
        elif(str(regression_data['buyIndia']) == '' and -90 < regression_data['yearHighChange'] < -10
            and (ten_days_more_than_ten(regression_data)
                 or last_5_day_all_up_except_today(regression_data)
            ) 
            and regression_data['forecast_day_PCT7_change'] >= 1 
            and regression_data['forecast_day_PCT5_change'] >= -1
            and regression_data['forecast_day_PCT2_change'] < 0 
            and regression_data['forecast_day_PCT_change'] < 0
            and regression_data['trend'] != 'down'
            ):
            add_in_csv(regression_data, regressionResult, ws_sellFinal1, 'sellFinal1')
    if(regression_data['forecast_day_PCT4_change'] >= -0.5
        and regression_data['forecast_day_PCT5_change'] >= -0.5
        and regression_data['forecast_day_PCT7_change'] >= -0.5
        and regression_data['yearLowChange'] > 5 and regression_data['yearHighChange'] < -5
        and (ten_days_more_than_ten(regression_data)
             or last_5_day_all_up_except_today(regression_data)
             )
        #and abs(regression_data['PCT_day_LC']) < 0.5
        ):  
        if(regression_data['forecast_day_PCT_change'] < 0
            and regression_data['bar_low'] < regression_data['bar_low_pre']
            and regression_data['forecast_day_VOL_change'] > 0
            ):
            if(-4 < regression_data['PCT_day_change'] < -2 and -4 < regression_data['PCT_change'] < -2
               and regression_data['PCT_day_change_pre1'] > 0
                ):
                add_in_csv(regression_data, regressionResult, ws_sellFinal, 'sellFinalCandidate-0')
                return True
            if(-5 < regression_data['PCT_day_change'] < -2 and -5 < regression_data['PCT_change'] < -2
               and regression_data['PCT_day_change_pre1'] > 0
               and (regression_data['yearHighChange'] > -30 or regression_data['yearLowChange'] > 30)
                ):
                add_in_csv(regression_data, regressionResult, ws_sellFinal, 'sellFinalCandidate-00')
                return True
            if(-6.5 < regression_data['PCT_day_change'] < -2 and -6.5 < regression_data['PCT_change'] < -2
               and regression_data['PCT_day_change_pre1'] > 0
               and (regression_data['yearHighChange'] > -30 or regression_data['yearLowChange'] > 30)
                ):
                add_in_csv(regression_data, regressionResult, ws_sellFinal, 'sellFinalCandidate-00HighChange')
                return True
            if(-2.5 < regression_data['PCT_day_change'] < -1 and -2.5 < regression_data['PCT_change'] < -1
                and regression_data['PCT_day_change_pre1'] < 0
                and (regression_data['mlpValue'] < -1 or regression_data['kNeighboursValue'] < -1)
                ):
                add_in_csv(regression_data, regressionResult, ws_sellFinal, 'sellFinalCandidate-1')
                return True
            if(-4 < regression_data['PCT_day_change'] < -1 and -4 < regression_data['PCT_change'] < -1 
                and no_doji_or_spinning_sell_india(regression_data)
                and regression_data['PCT_day_change_pre1'] < 0
                and (regression_data['mlpValue'] < -1 or regression_data['kNeighboursValue'] < -1)
                ):   
                add_in_csv(regression_data, regressionResult, ws_sellFinal, 'sellFinalCandidate-2')
                return True
            if(-2.5 < regression_data['PCT_day_change'] < -0.5 and -2.5 < regression_data['PCT_change'] < -0.5
                and regression_data['PCT_day_change_pre1'] < 0
                and (regression_data['mlpValue'] < -1 or regression_data['kNeighboursValue'] < -1)
                ):
                add_in_csv(regression_data, regressionResult, ws_sellFinal, '##sellFinalCandidate-2-test')
                return True
        if((((regression_data['open'] - regression_data['close']) * 1.5 > regression_data['high'] - regression_data['low']) or (regression_data['forecast_day_PCT_change'] < 0 and regression_data['PCT_day_change'] < -1))
            and (regression_data['yearHighChange'] > -30 or regression_data['yearLowChange'] > 30)
            ):
            if(-2.5 < regression_data['PCT_day_change'] < -1 and -2.5 < regression_data['PCT_change'] < -1 
                and no_doji_or_spinning_sell_india(regression_data) and no_doji_or_spinning_buy_india(regression_data)
                ):
                if(((regression_data['mlpValue'] < -0.5 and regression_data['kNeighboursValue'] < -0.5) or is_algo_sell(regression_data))
                    and regression_data['forecast_day_VOL_change'] > -20
                    ):    
                    add_in_csv(regression_data, regressionResult, ws_sellFinal, 'sellFinalCandidate-3')
                    return True
            if(-5 < regression_data['PCT_day_change'] < -1 and -5 < regression_data['PCT_change'] < -1 
                and no_doji_or_spinning_sell_india(regression_data) and no_doji_or_spinning_buy_india(regression_data)
                ):
                if(((regression_data['mlpValue'] < -0.5 and regression_data['kNeighboursValue'] < -0.5) or is_algo_sell(regression_data))
                    and regression_data['forecast_day_VOL_change'] > 0
                    ):    
                    add_in_csv(regression_data, regressionResult, ws_sellFinal, '##sellFinalCandidate-4')
                    return True
        if(-1 < regression_data['PCT_day_change'] < 0 and -1 < regression_data['PCT_change'] < 0 
            and no_doji_or_spinning_sell_india(regression_data) and no_doji_or_spinning_buy_india(regression_data)
            and (regression_data['mlpValue'] < -1 or regression_data['kNeighboursValue'] < -1)
            ):   
            add_in_csv(regression_data, regressionResult, ws_sellFinal, '##sellFinalCandidate-5-(upLastDayOrDown2to3)')
            return True
    return False

def sell_high_indicators(regression_data, regressionResult, ws_sellHighIndicators):
    if(regression_data['mlpValue'] < -1.0 and regression_data['kNeighboursValue'] < -1.0 and regression_data['yearHighChange'] > -10 and regression_data['yearLowChange'] > 30
        and (-2.5 < regression_data['PCT_day_change'] < 0 and -2.5 < regression_data['PCT_change'] < 0.5)
        ):
        add_in_csv(regression_data, regressionResult, ws_sellHighIndicators, 'sellHighIndicators')
        return True         
    return False

def sell_pattern(regression_data, regressionResult, ws_sellPattern, ws_sellPattern1):
    score = ''
    if(regression_data['score'] == '1-1' or regression_data['score'] == '0-1'):
        score = 'down'
    if(-4 < regression_data['PCT_day_change'] < 1 and regression_data['yearHighChange'] < -5 and regression_data['score'] != '10'
        and regression_data['trend'] != 'down'
        ):
        if(('HANGINGMAN' in str(regression_data['sellIndia'])
           #or 'MARUBOZU' in str(regression_data['sellIndia'])
           #or 'ENGULFING' in str(regression_data['sellIndia'])
           or 'EVENINGSTAR' in str(regression_data['sellIndia'])
           #or ':DOJISTAR' in str(regression_data['sellIndia'])
           #or 'EVENINGDOJISTAR' in str(regression_data['sellIndia'])
           or 'ABANDONEDBABY' in str(regression_data['sellIndia'])
           or 'COUNTERATTACK' in str(regression_data['sellIndia'])
           or 'KICKING' in str(regression_data['sellIndia'])
           or 'BREAKAWAY' in str(regression_data['sellIndia'])
           #or 'TRISTAR' in str(regression_data['sellIndia'])
           or ('SHOOTINGSTAR' in str(regression_data['sellIndia']) and regression_data['PCT_day_change'] < 0)
           or 'DARKCLOUDCOVER' in str(regression_data['sellIndia'])
           #or '3INSIDE' in str(regression_data['sellIndia'])
           #or '3OUTSIDE' in str(regression_data['sellIndia'])
           #or '2CROWS' in str(regression_data['sellIndia'])
           #or '3BLACKCROWS' in str(regression_data['sellIndia'])
           ) and (regression_data['forecast_day_PCT5_change'] >= 0)):
            add_in_csv(regression_data, regressionResult, ws_sellPattern, 'sellPattern')
            return True
        elif(
           ('HARAMI' in str(regression_data['sellIndia']) and regression_data['forecast_day_PCT5_change'] >= 0 and score == 'down')
           or ('ENGULFING' in str(regression_data['sellIndia']) and 'LONGLINE' in str(regression_data['sellIndia']) and score == 'down')
           ) and ((regression_data['forecast_day_PCT5_change'] >= 5) or regression_data['yearLowChange'] > 50):
            add_in_csv(regression_data, regressionResult, ws_sellPattern, 'sellPattern')
            return True
        elif(
           'HANGINGMAN' in str(regression_data['sellIndia'])
           or 'MARUBOZU' in str(regression_data['sellIndia'])
           #or 'ENGULFING' in str(regression_data['sellIndia'])
           or 'EVENINGSTAR' in str(regression_data['sellIndia'])
           #or ':DOJISTAR' in str(regression_data['sellIndia'])
           #or 'EVENINGDOJISTAR' in str(regression_data['sellIndia'])
           or 'ABANDONEDBABY' in str(regression_data['sellIndia'])
           or 'COUNTERATTACK' in str(regression_data['sellIndia'])
           or 'KICKING' in str(regression_data['sellIndia'])
           or 'BREAKAWAY' in str(regression_data['sellIndia'])
           or 'TRISTAR' in str(regression_data['sellIndia'])
           or ('SHOOTINGSTAR' in str(regression_data['sellIndia']) and regression_data['PCT_day_change'] < 0)
           or 'DARKCLOUDCOVER' in str(regression_data['sellIndia'])
           #or '3INSIDE' in str(regression_data['sellIndia'])
           #or '3OUTSIDE' in str(regression_data['sellIndia'])
           or '2CROWS' in str(regression_data['sellIndia'])
           or '3BLACKCROWS' in str(regression_data['sellIndia'])
           or ('CLOSINGMARUBOZU' in str(regression_data['sellIndia']) and 'LONGLINE' in str(regression_data['sellIndia']))
           or ('M@[,CROSSOVER-MACD]' in str(regression_data['sellIndia']) and 'LONGLINE' in str(regression_data['sellIndia']))
           or ('3OUTSIDE' in str(regression_data['sellIndia']) and 'SPINNINGTOP' not in str(regression_data['sellIndia']) and 'LONGLINE' not in str(regression_data['sellIndia']))
           ) and ((regression_data['forecast_day_PCT5_change'] >= 5) or regression_data['yearLowChange'] > 50):
            add_in_csv(regression_data, regressionResult, ws_sellPattern1, 'sellPattern1')
            return True
    return False

def sell_morning_star_buy(regression_data, regressionResult, ws):
    if(-5 < regression_data['forecast_day_PCT_change'] < -2
        and regression_data['PCT_day_change_pre1'] < 0
        and (BUY_VERY_LESS_DATA or ten_days_less_than_minus_seven(regression_data))
        and regression_data['yearHighChange'] < -20
        and high_tail_pct(regression_data) < 0.5
        ):
        if(0 < regression_data['PCT_day_change'] < 1 and 0 < regression_data['PCT_change'] < 1 
            and regression_data['kNeighboursValue'] > 0
            ):
            add_in_csv(regression_data, regressionResult, ws, 'morningStarBuy-0-NotUpSecondHalfAndUp2to3')
            return True
        if(-1.5 < regression_data['PCT_day_change'] < 0 and -1.5 < regression_data['PCT_change'] < 0
            and (regression_data['close'] - regression_data['low']) >= ((regression_data['open'] - regression_data['close']) * 3)
            and (regression_data['close'] - regression_data['low']) >= ((regression_data['high'] - regression_data['open']) * 3)
            ):
            add_in_csv(regression_data, regressionResult, ws, 'morningStarBuy-1-NotUpSecondHalfAndUp2to3')
            return True
    if(-8 < regression_data['forecast_day_PCT_change'] < -3
        and regression_data['PCT_day_change_pre1'] < -4
        and regression_data['yearHighChange'] < -20
        ):
        if(-3 < regression_data['PCT_day_change'] < -1 and -3 < regression_data['PCT_change'] < -1
            and (regression_data['close'] - regression_data['low']) > ((regression_data['open'] - regression_data['close']))
            and (regression_data['close'] - regression_data['low']) >= ((regression_data['high'] - regression_data['open']) * 3)
            ):
            add_in_csv(regression_data, regressionResult, ws, '##morningStarBuy-2-NotUpSecondHalfAndUp2to3(checkBase)')
            return True
    return False

def sell_evening_star_sell(regression_data, regressionResult, ws):
    if(5 > regression_data['forecast_day_PCT_change'] > 2
        and regression_data['PCT_day_change_pre1'] > 0
        and (SELL_VERY_LESS_DATA or ten_days_more_than_seven(regression_data))
        and regression_data['yearLowChange'] > 20
        and low_tail_pct(regression_data) < 0.5
        ):
        if(1.5 > regression_data['PCT_day_change'] > 0 and 1.5 > regression_data['PCT_change'] > 0
            and (regression_data['high']-regression_data['close']) >= ((regression_data['close']-regression_data['open'])*3)
            and (regression_data['high']-regression_data['close']) >= ((regression_data['open']-regression_data['low'])*3)
            ):
            add_in_csv(regression_data, regressionResult, ws, 'eveningStarSell-0-NotDownSecondHalfAndDown2to3')
            return True
        if(0 > regression_data['PCT_day_change'] > -1
            and (regression_data['high']-regression_data['open']) >= ((regression_data['open']-regression_data['close'])*3)
            and (regression_data['high']-regression_data['open']) >= ((regression_data['close']-regression_data['low'])*3)
            ):
            add_in_csv(regression_data, regressionResult, ws, 'eveningStarSell-1-NotDownSecondHalfAndDown2to3')
            return True
    if(8 > regression_data['forecast_day_PCT_change'] > 3
        and regression_data['PCT_day_change_pre1'] > 4
        and regression_data['yearLowChange'] > 20
        ):
        if(3 > regression_data['PCT_day_change'] > 1 and 3 > regression_data['PCT_change'] > 1
            and (regression_data['high']-regression_data['close']) >= ((regression_data['close']-regression_data['open']))
            and (regression_data['high']-regression_data['close']) >= ((regression_data['open']-regression_data['low'])*3)
            ):
            add_in_csv(regression_data, regressionResult, ws, '##eveningStarSell-2-NotDownSecondHalfAndDown2to3(checkBase)')
            return True   
    return False

def sell_oi_negative(regression_data, regressionResult, ws):
    if(regression_data['greentrend'] == 1
        and regression_data['forecast_day_PCT_change'] > 0.5
        and regression_data['forecast_day_PCT2_change'] > 0.5
        and regression_data['forecast_day_PCT3_change'] > 0.5
        and regression_data['forecast_day_PCT4_change'] > 0.5
        and regression_data['forecast_day_PCT5_change'] > 0.5
        and regression_data['forecast_day_PCT7_change'] > 0.5
        and ten_days_more_than_ten(regression_data)
        and float(regression_data['forecast_day_VOL_change']) < -30 
        and regression_data['PCT_day_change_pre1'] > 0
        and float(regression_data['contract']) < 0
        and float(regression_data['oi']) < 5
        and (regression_data['yearLowChange'] > 15 or regression_data['yearHighChange'] > -15) 
        and ((regression_data['mlpValue'] < 0 and regression_data['kNeighboursValue'] < 0) or is_algo_sell(regression_data))
        ):
        if(((0 < regression_data['PCT_day_change'] < 1 and 0.5 < regression_data['PCT_change'] < 1)
            or (0.5 < regression_data['PCT_day_change'] < 1 and 0 < regression_data['PCT_change'] < 1))
           ):
            add_in_csv(regression_data, regressionResult, ws, 'sellNegativeOI-0-checkBase(1%up)')
            return True
        if(0 < regression_data['PCT_day_change'] < 2 and 0 < regression_data['PCT_change'] < 2 
            ):
            add_in_csv(regression_data, regressionResult, ws, 'sellNegativeOI-1-checkBase(1%up)')
            return True
    return False

def sell_day_high(regression_data, regressionResult, ws):
    if((regression_data['PCT_day_change'] > 6 or regression_data['PCT_change'] > 6) 
       and float(regression_data['forecast_day_VOL_change']) < -30  
       and ((regression_data['mlpValue'] < -0.3 and regression_data['kNeighboursValue'] < -0.3) or is_algo_sell(regression_data))
       and (regression_data['PCT_day_change_pre1'] > 1.5)
       and regression_data['PCT_day_change'] > regression_data['PCT_day_change_pre1'] > 0
       ):
        add_in_csv(regression_data, regressionResult, ws, 'dayHighSell-ML')
        return True
    elif((regression_data['PCT_day_change'] > 6 or regression_data['PCT_change'] > 6)
       and float(regression_data['forecast_day_VOL_change']) < -30
       and (regression_data['PCT_day_change_pre1'] > 1.5)
       and regression_data['PCT_day_change'] > regression_data['PCT_day_change_pre1'] > 0
       ):
        add_in_csv(regression_data, regressionResult, ws, 'dayHighVolLowSell-0')
        return True
    elif((regression_data['PCT_day_change'] > 6 or regression_data['PCT_change'] > 6)
       and float(regression_data['forecast_day_VOL_change']) < 0
       and (regression_data['PCT_day_change_pre1'] > 1.5)
       and regression_data['PCT_day_change'] > regression_data['PCT_day_change_pre1'] > 0
       ):
        add_in_csv(regression_data, regressionResult, ws, 'dayHighVolLowSell-00')
        return True
    elif((regression_data['PCT_day_change'] > 3 and regression_data['PCT_change'] > 3) 
       and abs_yearHigh_more_than_yearLow(regression_data)
       and float(regression_data['forecast_day_VOL_change']) < -30  
       and (regression_data['PCT_day_change_pre1'] > 1.5)
       and regression_data['PCT_day_change'] > regression_data['PCT_day_change_pre1'] > 0
       and regression_data['PCT_day_change_pre2'] < -1
       ):
        add_in_csv(regression_data, regressionResult, ws, 'dayHighVolLowSell-1-checkMorningTrend(.5SL)-NotYearHigh')
        return True
#     if((regression_data['PCT_day_change'] > 2 and regression_data['PCT_change'] > 2) 
#        and float(regression_data['forecast_day_VOL_change']) < -50  
#        and regression_data['PCT_day_change_pre1'] > 0
#        ):
#         add_in_csv(regression_data, regressionResult, ws, '##dayHighVolLowSell-2')
#         return True
    return False

def sell_year_low_oi(regression_data, regressionResult, ws):
    if((0 < regression_data['PCT_day_change'] < 1 and 0 < regression_data['PCT_change'] < 1)
       and regression_data['PCT_day_change_pre1'] < 1.5
       and float(regression_data['forecast_day_VOL_change']) < -30
       and -1 < regression_data['forecast_day_PCT_change'] < 5
       and -1 < regression_data['forecast_day_PCT2_change'] < 5
       and -1 < regression_data['forecast_day_PCT3_change'] < 5
       and -1 < regression_data['forecast_day_PCT4_change'] < 5
       and -1 < regression_data['forecast_day_PCT5_change'] < 5
       and -5 < regression_data['forecast_day_PCT7_change'] < 0
       and regression_data['forecast_day_PCT10_change'] < -1
       and regression_data['yearLowChange'] < 7
       ):
        if(regression_data['forecast_day_PCT2_change'] > 1
           or regression_data['forecast_day_PCT3_change'] > 1
           or regression_data['forecast_day_PCT4_change'] > 1
           or regression_data['forecast_day_PCT5_change'] > 1
        ):
            add_in_csv(regression_data, regressionResult, ws, '##yearLowSell-0')
            return True
    return False

def sell_vol_contract(regression_data, regressionResult, ws):
    if(((regression_data['mlpValue'] < -0.3 and regression_data['kNeighboursValue'] < -0.3) or is_algo_sell(regression_data))
        and regression_data['forecast_day_PCT10_change'] > -10
        and (float(regression_data['contract']) != 0 or float(regression_data['oi']) != 0)
        and float(regression_data['contract']) > 10
        and (regression_data['PCT_day_change'] < -1 or regression_data['PCT_change'] < -1)
        and regression_data['forecast_day_PCT_change'] < -0.5
        and regression_data['forecast_day_PCT2_change'] < -0.5
        and regression_data['forecast_day_PCT3_change'] < 0
        and regression_data['forecast_day_PCT4_change'] < 0
        and (regression_data['PCT_day_change'] > 0
            or regression_data['PCT_day_change_pre1'] > 0
            or regression_data['PCT_day_change_pre2'] > 0
            or regression_data['PCT_day_change_pre3'] > 0
            or regression_data['PCT_day_change_pre4'] > 0
            )
        and preDayPctChangeDown_orVolHigh(regression_data)
        and regression_data['open'] > 50
        and last_4_day_all_down(regression_data) == False
        and (SELL_VERY_LESS_DATA or low_tail_pct(regression_data) < 0.7)
        ):
        if((regression_data['forecast_day_VOL_change'] > 70 and -2 < regression_data['PCT_day_change'] < -0.75 and -2 < regression_data['PCT_change'] < -0.5)
            and float(regression_data['contract']) > 10
            ):
            add_in_csv(regression_data, regressionResult, ws, 'oiSell-0')
            return True
        elif((regression_data['forecast_day_VOL_change'] > 35 and -2 < regression_data['PCT_day_change'] < -0.75 and -2 < regression_data['PCT_change'] < -0.5)
            and float(regression_data['contract']) > 20
            ):
            add_in_csv(regression_data, regressionResult, ws, 'oiSell-1')
            return True
        elif((regression_data['forecast_day_VOL_change'] > 150 and -3 < regression_data['PCT_day_change'] < -0.75 and -3 < regression_data['PCT_change'] < -0.5)
            ):
            add_in_csv(regression_data, regressionResult, ws, 'oiSell-2-checkBase')
            return True
        elif(((regression_data['forecast_day_VOL_change'] > 400 and -3.5 < regression_data['PCT_day_change'] < -0.75 and -3.5 < regression_data['PCT_change'] < -0.5)
            or (regression_data['forecast_day_VOL_change'] > 500 and -4.5 < regression_data['PCT_day_change'] < -0.75 and -4.5 < regression_data['PCT_change'] < -0.5)
            )
            ):
            add_in_csv(regression_data, regressionResult, ws, 'oiSell-3-checkBase')
            return True
        elif((regression_data['forecast_day_VOL_change'] > 300 and -5 < regression_data['PCT_day_change'] < -0.75 and -5 < regression_data['PCT_change'] < -0.5)
            and float(regression_data['contract']) > 50
            and (regression_data['forecast_day_PCT10_change'] > 8 or regression_data['forecast_day_PCT7_change'] > 8)
            ):
            add_in_csv(regression_data, regressionResult, ws, 'oiSell-4-checkBase')
            return True
    return False

def sell_vol_contract_contrarian(regression_data, regressionResult, ws):
    if((float(regression_data['contract']) != 0 or float(regression_data['oi']) != 0)
        and regression_data['forecast_day_PCT10_change'] < -10
        and float(regression_data['contract']) > 10
        and (regression_data['PCT_day_change'] < -1 or regression_data['PCT_change'] < -1)
        and regression_data['forecast_day_PCT_change'] < -0.5
        and regression_data['forecast_day_PCT2_change'] < -0.5
        and regression_data['forecast_day_PCT3_change'] < 0
        and regression_data['forecast_day_PCT4_change'] < 0
        and preDayPctChangeDown_orVolHigh(regression_data)
        and regression_data['open'] > 50
        #and last_7_day_all_down(regression_data) == False
        ):
        if((regression_data['forecast_day_VOL_change'] > 70 and -2 < regression_data['PCT_day_change'] < -0.75 and -2 < regression_data['PCT_change'] < -0.5)
            and float(regression_data['contract']) > 10
            ):
            add_in_csv(regression_data, regressionResult, ws, 'Test:buyReversalOI-0')
            return True
        elif((regression_data['forecast_day_VOL_change'] > 35 and -2 < regression_data['PCT_day_change'] < -0.75 and -2 < regression_data['PCT_change'] < -0.5)
            and float(regression_data['contract']) > 20
            ):
            add_in_csv(regression_data, regressionResult, ws, 'Test:buyReversalOI-1')
            return True
        elif((regression_data['forecast_day_VOL_change'] > 150 and -3 < regression_data['PCT_day_change'] < -0.75 and -3 < regression_data['PCT_change'] < -0.5)
            ):
            add_in_csv(regression_data, regressionResult, ws, 'Test:buyReversalOI-2')
            return True
        elif(((regression_data['forecast_day_VOL_change'] > 400 and -3.5 < regression_data['PCT_day_change'] < -0.75 and -3.5 < regression_data['PCT_change'] < -0.5)
            or (regression_data['forecast_day_VOL_change'] > 500 and -4.5 < regression_data['PCT_day_change'] < -0.75 and -4.5 < regression_data['PCT_change'] < -0.5)
            )
            and regression_data['forecast_day_PCT10_change'] > -15
            ):
            add_in_csv(regression_data, regressionResult, ws, 'Test:buyReversalOI-4-checkBase-(openAroundLastCloseAnd5MinuteChart)')
            return True
        elif((regression_data['forecast_day_VOL_change'] > 300 and -5 < regression_data['PCT_day_change'] < -0.75 and -5 < regression_data['PCT_change'] < -0.5)
            and float(regression_data['contract']) > 50
            and (regression_data['forecast_day_PCT10_change'] > 8 or regression_data['forecast_day_PCT7_change'] > 8)
            and regression_data['forecast_day_PCT10_change'] > -15
            ):
            add_in_csv(regression_data, regressionResult, ws, 'Test:buyReversalOI-4-checkBase-(openAroundLastCloseAnd5MinuteChart)')
            return True
            
    return False

def sell_trend_reversal(regression_data, regressionResult, ws):
    if(regression_data['forecast_day_PCT4_change'] >= -0.5
        and regression_data['forecast_day_PCT5_change'] >= -0.5
        and regression_data['forecast_day_PCT7_change'] >= -0.5
        and regression_data['yearLowChange'] > 5 and regression_data['yearHighChange'] < -5
        and (ten_days_more_than_ten(regression_data)
             or last_5_day_all_up_except_today(regression_data)
             )
        ):  
        if(regression_data['forecast_day_PCT_change'] < 0 and regression_data['PCT_day_change'] < 0
             and (regression_data['PCT_day_change_pre1'] < -1)
             and regression_data['PCT_day_change'] < regression_data['PCT_day_change_pre1'] < 0
             and regression_data['forecast_day_VOL_change'] <= -40
            ):
            if(-5 < regression_data['PCT_day_change'] < -1 and -5 < regression_data['PCT_change'] < -1
               and regression_data['forecast_day_VOL_change'] <= -50
              ):
                add_in_csv(regression_data, regressionResult, ws, '##finalBuyContinue-00')
                return True
            if(-5 < regression_data['PCT_day_change'] < -1 and -5 < regression_data['PCT_change'] < -1
              ):
                add_in_csv(regression_data, regressionResult, ws, '##finalBuyContinue-01-checkMorningTrend(.5SL)')
                return True
#             elif(regression_data['forecast_day_PCT_change'] < 0
#                  and regression_data['forecast_day_VOL_change'] <= -30
#                 ):
#                     #add_in_csv(regression_data, regressionResult, ws, '##finalBuyContinue-1')
#                     return False
        if((((regression_data['open'] - regression_data['close']) * 1.5 > regression_data['high'] - regression_data['low']) or (regression_data['forecast_day_PCT_change'] < 0 and regression_data['PCT_day_change'] < -1))
            and (regression_data['yearHighChange'] > -30 or regression_data['yearLowChange'] > 30)
            ):
            if(-2.5 < regression_data['PCT_day_change'] < -1 and -2.5 < regression_data['PCT_change'] < -1 
                and no_doji_or_spinning_sell_india(regression_data) and no_doji_or_spinning_buy_india(regression_data)
                ):
                if(regression_data['forecast_day_VOL_change'] <= -50
                    and (regression_data['PCT_day_change_pre1'] < -1)
                    and regression_data['PCT_day_change'] < regression_data['PCT_day_change_pre1'] < 0
                    ):
                    add_in_csv(regression_data, regressionResult, ws, '##finalBuyContinue-1')
                    return True
                elif(regression_data['forecast_day_VOL_change'] <= -30
                    and (regression_data['PCT_day_change_pre1'] < -1)
                    and regression_data['PCT_day_change'] < regression_data['PCT_day_change_pre1'] < 0
                    ):
                    add_in_csv(regression_data, regressionResult, ws, '##finalBuyContinue-1-checkBase')
                    return True
            if(-5 < regression_data['PCT_day_change'] < -1 and -5 < regression_data['PCT_change'] < -1 
                and no_doji_or_spinning_sell_india(regression_data) and no_doji_or_spinning_buy_india(regression_data)
                ):
                if(regression_data['forecast_day_VOL_change'] <= -30
                    and (regression_data['PCT_day_change_pre1'] < -1)
                    and regression_data['PCT_day_change'] < regression_data['PCT_day_change_pre1'] < 0
                    ):
                    add_in_csv(regression_data, regressionResult, ws, '##finalBuyContinue-2')
                    return True
                elif(regression_data['forecast_day_VOL_change'] <= -15
                    and (regression_data['PCT_day_change_pre1'] < -1)
                    and regression_data['PCT_day_change'] < regression_data['PCT_day_change_pre1'] < 0
                    ):
                    add_in_csv(regression_data, regressionResult, ws, '##finalBuyContinue-2-checkBase')
                    return True
    if(regression_data['yearLowChange'] > 5 and regression_data['yearHighChange'] < -5
        and ten_days_more_than_five(regression_data)
        ):
        if(regression_data['forecast_day_PCT_change'] < 0 and regression_data['PCT_day_change'] < 0 
            and (regression_data['PCT_day_change_pre1'] < -1)
            and regression_data['PCT_day_change'] < regression_data['PCT_day_change_pre1'] < 0
            and regression_data['forecast_day_VOL_change'] <= -20
            ):
            if(-5 < regression_data['PCT_day_change'] < -2 and -5 < regression_data['PCT_change'] < -2):
                add_in_csv(regression_data, regressionResult, ws, '##finalBuyContinue-test')
                return True 
    return False   

def sell_trend_break(regression_data, regressionResult, ws):
#     if(regression_data['consolidation'] == 1
#        and regression_data['PCT_day_change'] < -2 and regression_data['PCT_change'] < -2
#        ):
#         add_in_csv(regression_data, regressionResult, ws, '##TestBreakOutSellConsolidate-0')
#         return True
    
    if(ten_days_more_than_five(regression_data)
       and last_7_day_all_up(regression_data)
       and regression_data['forecast_day_PCT10_change'] < 15
       ):
        add_in_csv(regression_data, regressionResult, ws, '##TEST:BreakOutSellCandidate-(openAroundLastCloseAnd10MinuteChart)')
        return True
    
    if(ten_days_more_than_five(regression_data)
      and regression_data['yearLowChange'] > 30
    ):
       if(regression_data['forecast_day_PCT_change'] < -2 and regression_data['PCT_day_change'] < -2 and regression_data['PCT_day_change_pre1'] > 0
           and abs(regression_data['PCT_day_change']) > abs(regression_data['PCT_day_change_pre1'])
           #and regression_data['open'] == regression_data['high']
           and regression_data['forecast_day_VOL_change'] >= -20
           ):
               add_in_csv(regression_data, regressionResult, ws, '##TEST:finalBreakOutSell-0')
               return True
    if(regression_data['yearHighChange'] > -5
    ):
       if(regression_data['forecast_day_PCT_change'] < -3 and regression_data['PCT_day_change'] < -3
           #and regression_data['open'] == regression_data['high']
           and regression_data['forecast_day_VOL_change'] >= -20
           and low_tail_pct(regression_data) < 0.5
           ):
               add_in_csv(regression_data, regressionResult, ws, '##finalBreakOutSell-1test-atYearHigh')
               return True
    if(-5 > regression_data['yearHighChange'] > -10 and abs_yearHigh_less_than_yearLow(regression_data)
       and regression_data['forecast_day_PCT10_change'] > -10
       and last_7_day_all_down(regression_data) == False
       and low_tail_pct(regression_data) < 0.7
    ):
       if(-3 < regression_data['forecast_day_PCT_change'] < -2 and -3 < regression_data['PCT_day_change'] < -2
           and regression_data['PCT_day_change_pre1'] < 0 and regression_data['PCT_day_change_pre2'] < 0 and regression_data['PCT_day_change_pre3'] < 0
           and (regression_data['open'] == regression_data['high'] or regression_data['forecast_day_VOL_change'] >= 0)
           and regression_data['forecast_day_VOL_change'] >= -50
           ):
               add_in_csv(regression_data, regressionResult, ws, '##finalBreakOutSellContinue-00-test-atYearHigh')
               return True
       if(-2 < regression_data['forecast_day_PCT_change'] < 0 and -2 < regression_data['PCT_day_change'] < 0
           and regression_data['PCT_day_change_pre1'] < 0 and regression_data['PCT_day_change_pre2'] < 0 and regression_data['PCT_day_change_pre3'] < 0
           and (regression_data['forecast_day_PCT_change'] < -0.75 or regression_data['PCT_day_change_pre1'] < -0.75 or regression_data['PCT_day_change_pre2'] < -0.75 or regression_data['PCT_day_change_pre3'] < -0.75)
           and (regression_data['open'] == regression_data['high'] or regression_data['forecast_day_VOL_change'] >= 0)
           and regression_data['forecast_day_VOL_change'] >= -50
           ):
               add_in_csv(regression_data, regressionResult, ws, '##finalBreakOutSellContinue-0-test-atYearHigh')
               return True
    if(-5 > regression_data['yearHighChange'] > -12 and abs_yearHigh_less_than_yearLow(regression_data)
       and regression_data['forecast_day_PCT10_change'] > -10
       and last_7_day_all_down(regression_data) == False
       and low_tail_pct(regression_data) < 0.7
    ):
       if(-3 < regression_data['forecast_day_PCT_change'] < -2 and -3 < regression_data['PCT_day_change'] < -2
           and regression_data['PCT_day_change_pre1'] < 0 and regression_data['PCT_day_change_pre2'] < 0 and regression_data['PCT_day_change_pre3'] < 0
           #and regression_data['open'] == regression_data['high']
           and regression_data['forecast_day_VOL_change'] >= 0
           ):
               add_in_csv(regression_data, regressionResult, ws, '##finalBreakOutSellContinue-11-test-atYearHigh')
               return True
       if(-2 < regression_data['forecast_day_PCT_change'] < 0 and -2 < regression_data['PCT_day_change'] < 0
           and regression_data['PCT_day_change_pre1'] < 0 and regression_data['PCT_day_change_pre2'] < 0 and regression_data['PCT_day_change_pre3'] < 0
           and (regression_data['forecast_day_PCT_change'] < -0.75 or regression_data['PCT_day_change_pre1'] < -0.75 or regression_data['PCT_day_change_pre2'] < -0.75 or regression_data['PCT_day_change_pre3'] < -0.75)
           #and regression_data['open'] == regression_data['high']
           and regression_data['forecast_day_VOL_change'] >= 0
           ):
               add_in_csv(regression_data, regressionResult, ws, '##finalBreakOutSellContinue-1-test-atYearHigh')
               return True
    
def sell_oi_candidate(regression_data, regressionResult, ws):
    tail_pct_filter(regression_data, regressionResult)
    flag = False
    if sell_morning_star_buy(regression_data, regressionResult, ws): 
        flag = True
    if sell_evening_star_sell(regression_data, regressionResult, ws): 
        flag = True
    if sell_oi_negative(regression_data, regressionResult, ws):
        flag = True
    if sell_day_high(regression_data, regressionResult, ws):
        flag = True
    if sell_year_low_oi(regression_data, regressionResult, ws):
        flag = True
    if sell_vol_contract(regression_data, regressionResult, ws):
        flag = True
    if sell_vol_contract_contrarian(regression_data, regressionResult, ws):
        flag = True
    if sell_trend_reversal(regression_data, regressionResult, ws):
        flag = True
    if sell_trend_break(regression_data, regressionResult, ws):
        flag = True
    return flag

def sell_oi(regression_data, regressionResult, ws):
    if(regression_data['forecast_day_PCT_change'] < -0.5
        and regression_data['forecast_day_PCT2_change'] < -0.5
        and (regression_data['PCT_day_change'] > 0
            or regression_data['PCT_day_change_pre1'] > 0
            or regression_data['PCT_day_change_pre2'] > 0
            or regression_data['PCT_day_change_pre3'] > 0
            or regression_data['PCT_day_change_pre4'] > 0
            )
        and float(regression_data['forecast_day_VOL_change']) > 50 
        and float(regression_data['contract']) > 50
        and(regression_data['PCT_day_change_pre1'] < 0 
               or (regression_data['volume'] > regression_data['volume_pre2'] and regression_data['volume'] > regression_data['volume_pre3'])
            )
        and regression_data['open'] > 50
        and (last_4_day_all_down(regression_data) == False) #Uncomment0 If very less data
        and (SELL_VERY_LESS_DATA or low_tail_pct(regression_data) < 0.7)
        ):
        if(-3 < regression_data['PCT_day_change'] < -1 and -3 < regression_data['PCT_change'] < -1 
            ):
            if(regression_data['forecast_day_PCT10_change'] > 0 or regression_data['forecast_day_PCT7_change'] > 0):
                add_in_csv(regression_data, regressionResult, ws, 'openInterest-0')
                return True
            elif(regression_data['forecast_day_PCT10_change'] > -10 or regression_data['forecast_day_PCT7_change'] > -10):
                add_in_csv(regression_data, regressionResult, ws, 'openInterest-1')
                return True
            else:
                add_in_csv(regression_data, regressionResult, ws, 'openInterest-1-Risky')
                return True
        if(-6 < regression_data['PCT_day_change'] < -1 and -6 < regression_data['PCT_change'] < -1 
            ):
            if(regression_data['forecast_day_PCT10_change'] > 0 or regression_data['forecast_day_PCT7_change'] > 0
               ):
                add_in_csv(regression_data, regressionResult, ws, 'openInterest-0-checkConsolidation')
                return True
            elif(regression_data['forecast_day_PCT10_change'] > -10 or regression_data['forecast_day_PCT7_change'] > -10
                -4 < regression_data['PCT_day_change'] < -1 and -4 < regression_data['PCT_change'] < -1
                ):
                add_in_csv(regression_data, regressionResult, ws, 'openInterest-1-checkConsolidation')
                return True
            else:
                add_in_csv(regression_data, regressionResult, ws, 'openInterest-1-Risky')
                return True 
    return False

def sell_all_rule_filter(regression_data, regressionResult, ws):
    if(-4 < regression_data['PCT_change'] < 1
       and (SELL_VERY_LESS_DATA or (last_4_day_all_down(regression_data) == False)) #Uncomment0 If very less data
        ):
        if(all_between_zero_and_five_down_score(regression_data)
           and regression_data['yearLowChange'] > 20 and regression_data['yearHighChange'] < -10
           and -4 < regression_data['PCT_day_change'] < -1
           and -4 < regression_data['PCT_change'] < -1
           ):
            add_in_csv(regression_data, regressionResult, ws, None, '##sellAllbetwen0AND-5DownScore-0')
        if(ten_days_more_than_minus_five(regression_data) and regression_data['series_trend'] == "upTrend"
            and ((-3 < regression_data['PCT_day_change'] < -1 and -3 < regression_data['PCT_change'] < -0.5))
            and regression_data['yearHighChange'] < -10
            and ( -5 < regression_data['forecast_day_PCT2_change'] < 5
                and -5 < regression_data['forecast_day_PCT3_change'] < 5
                and -5 < regression_data['forecast_day_PCT4_change'] < 5
                and -5 < regression_data['forecast_day_PCT5_change'] < 5
                and -5 < regression_data['forecast_day_PCT7_change'] < 0
                and -5 < regression_data['forecast_day_PCT10_change'] < 0
                )
           ):
            add_in_csv(regression_data, regressionResult, ws, None, '##sellUpTrendBetween-5+5')
        if(ten_days_less_than_five(regression_data) and regression_data['series_trend'] == "downTrend"
            and ((-3 < regression_data['PCT_day_change'] < -1 and -3 < regression_data['PCT_change'] < -0.5))
            and regression_data['yearHighChange'] < -10
            and ( -5 < regression_data['forecast_day_PCT2_change'] < 5
                and -5 < regression_data['forecast_day_PCT3_change'] < 5
                and -5 < regression_data['forecast_day_PCT4_change'] < 5
                and -5 < regression_data['forecast_day_PCT5_change'] < 5
                and 0 < regression_data['forecast_day_PCT7_change'] < 5
                and 0 < regression_data['forecast_day_PCT10_change'] < 5
                )
            and (regression_data['forecast_day_PCT2_change'] > regression_data['forecast_day_PCT3_change'] > regression_data['forecast_day_PCT4_change'])
           ):
            add_in_csv(regression_data, regressionResult, ws, None, '##sellDownTrendBetween-5+5')
        if((-3 < regression_data['PCT_day_change'] < -1 and -2.5 < regression_data['PCT_change'] < -0.5)
            and regression_data['yearHighChange'] < -10
            and 0 < regression_data['forecast_day_PCT2_change'] < 5
            and 0 < regression_data['forecast_day_PCT3_change'] < 5
            and 0 < regression_data['forecast_day_PCT4_change'] < 5
            and 0 < regression_data['forecast_day_PCT5_change'] < 5
            and 0 < regression_data['forecast_day_PCT7_change'] < 5
            and 0 < regression_data['forecast_day_PCT10_change'] < 5
            ):
            add_in_csv(regression_data, regressionResult, ws, None, '##sellAllPositiveExceptToday')
        add_in_csv(regression_data, regressionResult, ws, None)
        return True
    return False

def sell_all_common(regression_data, classification_data, regressionResult, ws):
    if(-4 < regression_data['PCT_change'] < 1
        and (SELL_VERY_LESS_DATA or (last_4_day_all_down(regression_data) == False)) #Uncomment0 If very less data
        ):
        if((-3.5 < regression_data['PCT_day_change'] < -1 and -3.5 < regression_data['PCT_change'] < -0.5)
            and regression_data['yearHighChange'] < -10
            and -5 < regression_data['forecast_day_PCT2_change'] < 0
            and -5 < regression_data['forecast_day_PCT3_change'] < 0
            and -5 < regression_data['forecast_day_PCT4_change'] < 0
            and -5 < regression_data['forecast_day_PCT5_change'] < 0
            and -5 < regression_data['forecast_day_PCT7_change'] < 0
            and -5 < regression_data['forecast_day_PCT10_change'] < 0
            ):
            add_in_csv(regression_data, regressionResult, ws, None, '##sellAllNegativeExceptToday')
        if(ten_days_more_than_minus_ten(regression_data)
            and ((-3.5 < regression_data['PCT_day_change'] < -1 and -3.5 < regression_data['PCT_change'] < -1))
            and regression_data['yearHighChange'] < -10
            and -5 < regression_data['forecast_day_PCT_change'] < 1
            and -5 < regression_data['forecast_day_PCT2_change'] < 1
            and -5 < regression_data['forecast_day_PCT3_change'] < 0
            and -5 < regression_data['forecast_day_PCT4_change'] < 0
            and -10 < regression_data['forecast_day_PCT5_change'] < 0
            and -10 < regression_data['forecast_day_PCT7_change'] < 0
            and -10 < regression_data['forecast_day_PCT10_change'] < 0
            ):
            add_in_csv(regression_data, regressionResult, ws, None, '##sellAllMoreThan-10(UpLastDay)')
        add_in_csv(regression_data, regressionResult, ws, None)
        return True
    return False

def sell_all_filter(regression_data, regressionResult, ws_sellAllFilter):
    flag = False
    if sell_year_high(regression_data, regressionResult, None, None):
        add_in_csv(regression_data, regressionResult, ws_sellAllFilter, None)
        flag = True
    if sell_year_low(regression_data, regressionResult, None):
        add_in_csv(regression_data, regressionResult, ws_sellAllFilter, None)
        flag = True
    if sell_up_trend(regression_data, regressionResult, None):
        add_in_csv(regression_data, regressionResult, ws_sellAllFilter, None)
        flag = True
    if sell_down_trend(regression_data, regressionResult, None):
        add_in_csv(regression_data, regressionResult, ws_sellAllFilter, None)
        flag = True
    if sell_final(regression_data, regressionResult, None, None):
        add_in_csv(regression_data, regressionResult, ws_sellAllFilter, None)
        flag = True
    if sell_high_indicators(regression_data, regressionResult, None):
        add_in_csv(regression_data, regressionResult, ws_sellAllFilter, None)
        flag = True
#     if sell_pattern(regression_data, regressionResult, None, None):
#         ws_sellAllFilter.append(regressionResult) if (ws_sellAllFilter is not None) else False
#         return True
    if sell_oi(regression_data, regressionResult, None):
        add_in_csv(regression_data, regressionResult, ws_sellAllFilter, None)
        flag = True
    return flag
