# -*- coding: utf-8 -*-
"""
Created on Sun Mar  8 20:56:37 2020

@author: lijinxuan
"""

import traceback
import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import datetime
import warnings


获取最近的交易日(该日及之后)
def get_newest_tradeday(date):
    date2 = pd.to_datetime(date)
    count = 0
    while (date2 + datetime.timedelta(count)) not in trade_days and count < 100:
        count += 1
    if count == 100:
        return trade_days[-1]
    newest_tradeday = date2 + datetime.timedelta(count)
    return newest_tradeday


# 获取存在且离窗口结束日最近的交易日
def get_latest_tradeday(date, end_window):
    date2 = pd.to_datetime(date)
    count = end_window
    while trade_days.index(date2) + count >= len(trade_days):
        count -= 1
    return trade_days[trade_days.index(date2) + count]


warnings.filterwarnings("ignore")

plt.rcParams['font.sans-serif'] = ['SimHei']
plt.rcParams['axes.unicode_minus'] = False

os.chdir('D:/算法文件/算法文件/eventinf/eventinf') #文件夹保存地址

f = open("eventMsgs.txt", "r", encoding='UTF-8')
f_list = f.readlines()

# 处理事件信息
null = ''
event_data = pd.DataFrame()
for i in range(len(f_list)):
    i_dict = eval(f_list[i])
    if len(i_dict['risks'][0]['event_sentiments']) == 0:  # 无事件类型,跳过
        continue
    event_data[i] = [i_dict['risks'][0]['stock_code'], i_dict['publish_time'], \
                     i_dict['risks'][0]['event_sentiments'][0].split(':')[0], \
                     i_dict['risks'][0]['event_sentiments'][0].split(':')[1]]
event_data = event_data.T
event_data = event_data.replace('', np.nan)
event_data.columns = ['stk', 'date', 'event', 'direc']
event_data = event_data.dropna()  # 剔除未上市公司
event_data = event_data[[len(i) == 6 for i in event_data['stk']]]  # 剔除非沪深股
event_data = event_data[[i.isdigit() for i in event_data['stk']]]  # 剔除非沪深股
event_data['type'] = event_data['event'] + event_data['direc']  # 事件类型为事件加上正面/负面/中性

# 处理收盘价信息 处理为columns为股票code,index为日期的面板数据
df = pd.read_csv("ashare_prices.txt", sep='\t', header=None)
df.columns = ['stk', 'date', 'close']
df = df.set_index(['date', 'stk'])
df = df.to_xarray()['close']
df = df.to_pandas()

df.columns = [i[:6] for i in df.columns]
df.index = pd.to_datetime([str(i) for i in list(df.index)])
# 计算收益率
ret_df = df / df.shift(1) - 1
trade_days = list(df.index)

# 再次剔除非A股
event_data = event_data[[i in list(df.columns) for i in event_data['stk']]]

# 沪深300
hs300 = pd.read_excel('沪深300行情数据.xls', index_col=2)['收盘价(元)']
# 计算收益率
ret_hs300 = hs300 / hs300.shift(1) - 1

# 事件研究 回测窗口 (这里是20天)
event_window = [-180, 180]
tp_ret = {}
# car为累积异常收益率
# caar为平均累积异常收益率
# prop为对股价影响为正的统计概率
car_df = pd.DataFrame()
caar_df = pd.DataFrame()
prop_df = pd.DataFrame()
count_event = {}
for tp in event_data['type'].unique():
    # 获取相应期收益率
    event_temp = event_data[event_data['type'] == tp]
    ret_temp = []

    for i in event_temp.index:
        stk = event_temp.loc[i, 'stk']
        t = get_newest_tradeday(event_temp.loc[i, 'date'][:8])
        t_start = trade_days[trade_days.index(t) + event_window[0]]  # 获取回测窗口开始日
        t_end = get_latest_tradeday(t, event_window[1])  # 获取存在且离窗口结束日最近的交易日，因为可能窗口结束日还没有沪深300数据
        ret_window = ret_df.loc[t_start:t_end, stk] - ret_hs300.loc[t_start:t_end]
        ret_temp.append(list(ret_window))
    ret_temp = pd.DataFrame(ret_temp)
    ret_temp = ret_temp.dropna(how='all')  # 排除了全阶段停牌股
    print(tp, '有事件', len(ret_temp), '例')
    count_event[tp] = len(ret_temp)
    ret_temp.columns = [i + event_window[0] for i in ret_temp.columns]
    # 事件窗口净值
    caar_temp = ret_temp.median().cumsum()
    new_df = pd.DataFrame(caar_temp)
    new_df.columns = [tp]
    caar_df = pd.concat([caar_df, new_df], axis=1)
    # 画图
    tp_ret[tp] = caar_temp
    plt.figure(figsize=(8, 6))
    plt.plot(caar_temp)
    plt.title('CAAR——' + tp)
    car_temp = ret_temp.cumsum(1)
    prop = []
    for i in range(0, len(car_temp.T)):
        pos = 0
        for j in range(0, len(car_temp)):
            if car_temp.iloc[j, i] > 0:
                pos = pos + 1
        if len(car_temp)>0:
            prop.append(pos / len(car_temp))
        else:
            prop.append(0)
    new_prop = pd.DataFrame([prop], columns=list(car_temp)).T
    new_prop.columns = [tp]
    prop_df = pd.concat([prop_df, new_prop], axis=1)
    plt.figure(figsize=(8, 6))
    plt.plot(list(car_temp), prop)
    plt.title('AAR为正概率——' + tp)
    plt.show()

count_event = pd.DataFrame.from_dict(count_event, orient='index', columns=['案例数'])
event_result = pd.concat([count_event, caar_df.T], axis=1)
prop_result = pd.concat([count_event, prop_df.T], axis=1)
event_result.to_excel('event_result.xls')
prop_result.to_excel('prop_result.xls')

#以上是每周运行的脚本 event_data可以存入数据库 之后仿真股价直接从数据库取数
# 股价仿真：当某家公司出现某一事件之后 根据计算出的事件caar模拟预测这家公司的股价变动情况
# 举例 ：例如 股票code,发生事件为：业绩披露，事件影响：正面,事件发生时间为 20200803,发生时股价为p

p=3.45 #事件发生时股价为p
df=(event_result['业绩披露正面']+1)*p    # event_data可以存入数据库 之后仿真股价直接从数据库取数
df[df.index.isin([i for i in range(180)])] # 事件发生后180天code1的股价变动情况为



# 查询某个事件的图
def picture(tp):
    event_temp = event_data[event_data['type'] == tp]
    ret_temp = []

    for i in event_temp.index:
        stk = event_temp.loc[i, 'stk']
        t = get_newest_tradeday(event_temp.loc[i, 'date'][:8])
        t_start = trade_days[trade_days.index(t) + event_window[0]]
        t_end = get_latest_tradeday(t, event_window[1])
        ret_window = ret_df.loc[t_start:t_end, stk] - ret_hs300.loc[t_start:t_end]
        ret_temp.append(list(ret_window))
    ret_temp = pd.DataFrame(ret_temp)
    ret_temp = ret_temp.dropna(how='all')  # 排除了全阶段停牌股
    print(tp, '有事件', len(ret_temp), '例')
    ret_temp.columns = [i + event_window[0] for i in ret_temp.columns]
    # 事件窗口净值
    caar_temp = ret_temp.mean().cumsum()
    # 画图
    tp_ret[tp] = caar_temp
    plt.figure(figsize=(8, 6))
    plt.plot(caar_temp)
    plt.title('CAAR——' + tp)
    car_temp = ret_temp.cumsum(1)
    prop = []
    for i in range(0, len(car_temp.T)):
        pos = 0
        for j in range(0, len(car_temp)):
            if car_temp.iloc[j, i] > 0:
                pos = pos + 1
        prop.append(pos / len(car_temp))
    plt.figure(figsize=(8, 6))
    plt.plot(list(car_temp), prop)
    plt.title('AAR为正概率——' + tp)
    plt.show()


picture('关联交易风险中性')

