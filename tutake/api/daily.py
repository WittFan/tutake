import pandas as pd
import logging
from sqlalchemy import Integer, String, Float, Column, create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from tutake.api.base_dao import BaseDao
from tutake.api.dao import DAO
from tutake.api.process_type import ProcessType
from tutake.api.tushare_base import TuShareBase
from tutake.utils.config import config
"""
Tushare daily接口
数据接口-沪深股票-行情数据-日线行情  https://tushare.pro/document/2?doc_id=27
"""

engine = create_engine("%s/%s" %
                       (config['database']['driver_url'], 'tushare_daily.db'))
session_factory = sessionmaker()
session_factory.configure(bind=engine)
Base = declarative_base()
logger = logging.getLogger('api.tushare.daily')


class TushareDaily(Base):
    __tablename__ = "tushare_daily"
    id = Column(Integer, primary_key=True, autoincrement=True)
    ts_code = Column(String, comment='股票代码')
    trade_date = Column(String, comment='交易日期')
    open = Column(Float, comment='开盘价')
    high = Column(Float, comment='最高价')
    low = Column(Float, comment='最低价')
    close = Column(Float, comment='收盘价')
    pre_close = Column(Float, comment='昨收价')
    change = Column(Float, comment='涨跌额')
    pct_chg = Column(Float, comment='涨跌幅')
    vol = Column(Float, comment='成交量')
    amount = Column(Float, comment='成交额')


TushareDaily.__table__.create(bind=engine, checkfirst=True)


class Daily(BaseDao, TuShareBase):
    instance = None

    def __new__(cls, *args, **kwargs):
        if cls.instance is None:
            cls.instance = super().__new__(cls)
        return cls.instance

    def __init__(self):
        BaseDao.__init__(self, engine, session_factory, TushareDaily,
                         'tushare_daily')
        TuShareBase.__init__(self)
        self.dao = DAO()

    def daily(self, **kwargs):
        """
        日线行情

        | Arguments:
        | ts_code(str):   股票代码
        | trade_date(str):   交易日期
        | start_date(str):   开始日期
        | end_date(str):   结束日期
        | offset(str):   开始行数
        | limit(str):   最大行数
        

        :return: DataFrame
         ts_code(str)  股票代码
         trade_date(str)  交易日期
         open(float)  开盘价
         high(float)  最高价
         low(float)  最低价
         close(float)  收盘价
         pre_close(float)  昨收价
         change(float)  涨跌额
         pct_chg(float)  涨跌幅
         vol(float)  成交量
         amount(float)  成交额
        
        """
        args = [
            n for n in [
                'ts_code',
                'trade_date',
                'start_date',
                'end_date',
                'offset',
                'limit',
            ] if n not in ['limit', 'offset']
        ]
        params = {key: kwargs[key] for key in kwargs.keys() & args}
        query = session_factory().query(TushareDaily).filter_by(**params)
        query = query.order_by(text("trade_date desc,ts_code"))
        input_limit = 10000  # 默认10000条 避免导致数据库压力过大
        if kwargs.get('limit') and str(kwargs.get('limit')).isnumeric():
            input_limit = int(kwargs.get('limit'))
            query = query.limit(input_limit)
        if "6000" != "":
            default_limit = int("6000")
            if default_limit < input_limit:
                query = query.limit(default_limit)
        if kwargs.get('offset') and str(kwargs.get('offset')).isnumeric():
            query = query.offset(int(kwargs.get('offset')))
        return pd.read_sql(query.statement, query.session.bind)

    def prepare(self, process_type: ProcessType):
        """
        同步历史数据准备工作
        :return:
        """

    def tushare_parameters(self, process_type: ProcessType):
        """
        同步历史数据调用的参数
        :return: list(dict)
        """
        return self.dao.stock_basic.column_data(['ts_code', 'list_date'])

    def param_loop_process(self, process_type: ProcessType, **params):
        """
        每执行一次fetch_and_append前，做一次参数的处理，如果返回None就中断这次执行
        """
        from datetime import datetime, timedelta
        date_format = '%Y%m%d'
        if process_type == ProcessType.HISTORY:
            min_date = self.min("trade_date",
                                "ts_code = '%s'" % params['ts_code'])
            if min_date is None:
                params['end_date'] = ""
            elif params.get('list_date') and params.get(
                    'list_date') == min_date:
                # 如果时间相等不用执行
                return None
            else:
                min_date = datetime.strptime(min_date, date_format)
                end_date = min_date - timedelta(days=1)
                params['end_date'] = end_date.strftime(date_format)
            return params
        else:
            max_date = self.max("trade_date",
                                "ts_code = '%s'" % params['ts_code'])
            if max_date is None:
                params['start_date'] = ""
            elif max_date == datetime.now().strftime(date_format):
                # 如果已经是最新时间
                return None
            else:
                max_date = datetime.strptime(max_date, date_format)
                start_date = max_date + timedelta(days=1)
                params['start_date'] = start_date.strftime(date_format)
            return params

    def process(self, process_type: ProcessType):
        """
        同步历史数据
        :return:
        """
        self.prepare(process_type)
        params = self.tushare_parameters(process_type)
        logger.debug("Process tushare params is {}".format(params))
        if params:
            for param in params:
                new_param = self.param_loop_process(process_type, **param)
                if new_param is None:
                    logger.debug("Skip exec param: {}".format(param))
                    continue
                try:
                    cnt = self.fetch_and_append(process_type, **new_param)
                    logger.debug("Fetch and append {} data, cnt is {}".format(
                        "daily", cnt))
                except Exception as err:
                    if err.args[0].startswith("抱歉，您没有访问该接口的权限") or err.args[
                            0].startswith("抱歉，您每天最多访问该接口"):
                        logger.error(
                            "Throw exception with param: {} err:{}".format(
                                new_param, err))
                        return
                    continue

    def fetch_and_append(self, process_type: ProcessType, **kwargs):
        """
        获取tushare数据并append到数据库中
        :return: 数量行数
        """
        if len(kwargs.keys()) == 0:
            kwargs = {
                "ts_code": "",
                "trade_date": "",
                "start_date": "",
                "end_date": "",
                "offset": "",
                "limit": ""
            }
        # 初始化offset和limit
        if not kwargs.get("limit"):
            kwargs['limit'] = "6000"
        init_offset = 0
        offset = 0
        if kwargs.get('offset') and kwargs.get('offset').isnumeric():
            offset = int(kwargs['offset'])
            init_offset = offset

        kwargs = {
            key: kwargs[key]
            for key in kwargs.keys() & list([
                'ts_code',
                'trade_date',
                'start_date',
                'end_date',
                'offset',
                'limit',
            ])
        }

        def fetch_save(offset_val=0):
            kwargs['offset'] = str(offset_val)
            logger.debug("Invoke pro.daily with args: {}".format(kwargs))
            fields = [
                "ts_code", "trade_date", "open", "high", "low", "close",
                "pre_close", "change", "pct_chg", "vol", "amount"
            ]
            res = pro.daily(**kwargs, fields=fields)
            res.to_sql('tushare_daily',
                       con=engine,
                       if_exists='append',
                       index=False,
                       index_label=['ts_code'])
            return res

        pro = self.tushare_api()
        df = fetch_save(offset)
        offset += df.shape[0]
        while kwargs['limit'] != "" and df.shape[0] == kwargs['limit']:
            df = fetch_save(offset)
            offset += df.shape[0]
        return offset - init_offset


if __name__ == '__main__':
    logger.setLevel(logging.DEBUG)
    api = Daily()
    # api.process(ProcessType.HISTORY)  # 同步历史数据
    # api.process(ProcessType.INCREASE)  # 同步增量数据
    print(api.daily())  # 数据查询接口
