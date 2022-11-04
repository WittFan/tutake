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
Tushare stock_basic接口
数据接口-沪深股票-基础数据-股票列表  https://tushare.pro/document/2?doc_id=25
"""

engine = create_engine("%s/%s" % (config['database']['driver_url'], 'tushare_basic_data.db'))
session_factory = sessionmaker()
session_factory.configure(bind=engine)
Base = declarative_base()
logger = logging.getLogger('api.tushare.stock_basic')


class TushareStockBasic(Base):
    __tablename__ = "tushare_stock_basic"
    ts_code = Column(String, primary_key=True, comment='TS代码')
    symbol = Column(String, comment='股票代码')
    name = Column(String, comment='股票名称')
    area = Column(String, comment='地域')
    industry = Column(String, comment='所属行业')
    fullname = Column(String, comment='股票全称')
    enname = Column(String, comment='英文全称')
    cnspell = Column(String, comment='拼音缩写')
    market = Column(String, comment='市场类型')
    exchange = Column(String, comment='交易所代码')
    curr_type = Column(String, comment='交易货币')
    list_status = Column(String, comment='上市状态 L上市 D退市 P暂停上市')
    list_date = Column(String, comment='上市日期')
    delist_date = Column(String, comment='退市日期')
    is_hs = Column(String, comment='是否沪深港通标的，N否 H沪股通 S深股通')


TushareStockBasic.__table__.create(bind=engine, checkfirst=True)


class StockBasic(BaseDao, TuShareBase):
    instance = None

    def __new__(cls, *args, **kwargs):
        if cls.instance is None:
            cls.instance = super().__new__(cls)
        return cls.instance

    def __init__(self):
        BaseDao.__init__(self, engine, session_factory, TushareStockBasic, 'tushare_stock_basic')
        TuShareBase.__init__(self)
        self.dao = DAO()

    def stock_basic(self, **kwargs):
        """
        

        | Arguments:
        | ts_code(str):   TS股票代码
        | name(str):   名称
        | exchange(str):   交易所 SSE上交所 SZSE深交所 HKEX港交所
        | market(str):   市场类别
        | is_hs(str):   是否沪深港通标的，N否 H沪股通 S深股通
        | list_status(str):   上市状态 L上市 D退市 P暂停上市
        | limit(int):   单次返回数据长度
        | offset(int):   请求数据的开始位移量
        

        :return: DataFrame
         ts_code(str)  TS代码
         symbol(str)  股票代码
         name(str)  股票名称
         area(str)  地域
         industry(str)  所属行业
         fullname(str)  股票全称
         enname(str)  英文全称
         cnspell(str)  拼音缩写
         market(str)  市场类型
         exchange(str)  交易所代码
         curr_type(str)  交易货币
         list_status(str)  上市状态 L上市 D退市 P暂停上市
         list_date(str)  上市日期
         delist_date(str)  退市日期
         is_hs(str)  是否沪深港通标的，N否 H沪股通 S深股通
        
        """
        args = [
            n for n in [
                'ts_code',
                'name',
                'exchange',
                'market',
                'is_hs',
                'list_status',
                'limit',
                'offset',
            ] if n not in ['limit', 'offset']
        ]
        params = {key: kwargs[key] for key in kwargs.keys() & args}
        query = session_factory().query(TushareStockBasic).filter_by(**params)
        query = query.order_by(text("ts_code"))
        input_limit = 10000    # 默认10000条 避免导致数据库压力过大
        if kwargs.get('limit') and str(kwargs.get('limit')).isnumeric():
            input_limit = int(kwargs.get('limit'))
            query = query.limit(input_limit)
        if "" != "":
            default_limit = int("")
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
        logger.warning("Delete all data of {}")
        self.delete_all()

    def tushare_parameters(self, process_type: ProcessType):
        """
        同步历史数据调用的参数
        :return: list(dict)
        """
        return [{}]

    def param_loop_process(self, process_type: ProcessType, **params):
        """
        每执行一次fetch_and_append前，做一次参数的处理，如果返回None就中断这次执行
        """
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
                    logger.debug("Fetch and append {} data, cnt is {}".format("daily", cnt))
                except Exception as err:
                    if err.args[0].startswith("抱歉，您没有访问该接口的权限") or err.args[0].startswith("抱歉，您每天最多访问该接口"):
                        logger.error("Throw exception with param: {} err:{}".format(new_param, err))
                        return
                    else:
                        logger.error("Execute fetch_and_append throw exp. {}".format(err))
                        continue

    def fetch_and_append(self, process_type: ProcessType, **kwargs):
        """
        获取tushare数据并append到数据库中
        :return: 数量行数
        """
        if len(kwargs.keys()) == 0:
            kwargs = {
                "ts_code": "",
                "name": "",
                "exchange": "",
                "market": "",
                "is_hs": "",
                "list_status": "",
                "limit": "",
                "offset": ""
            }
        # 初始化offset和limit
        if not kwargs.get("limit"):
            kwargs['limit'] = ""
        init_offset = 0
        offset = 0
        if kwargs.get('offset'):
            offset = int(kwargs['offset'])
            init_offset = offset

        kwargs = {
            key: kwargs[key] for key in kwargs.keys() & list([
                'ts_code',
                'name',
                'exchange',
                'market',
                'is_hs',
                'list_status',
                'limit',
                'offset',
            ])
        }

        def fetch_save(offset_val=0):
            kwargs['offset'] = str(offset_val)
            logger.debug("Invoke pro.stock_basic with args: {}".format(kwargs))
            fields = [
                "ts_code", "symbol", "name", "area", "industry", "fullname", "enname", "cnspell", "market", "exchange",
                "curr_type", "list_status", "list_date", "delist_date", "is_hs"
            ]
            res = pro.stock_basic(**kwargs, fields=fields)
            res.to_sql('tushare_stock_basic', con=engine, if_exists='append', index=False, index_label=['ts_code'])
            return res

        pro = self.tushare_api()
        df = fetch_save(offset)
        offset += df.shape[0]
        while kwargs['limit'] != "" and str(df.shape[0]) == kwargs['limit']:
            df = fetch_save(offset)
            offset += df.shape[0]
        return offset - init_offset


if __name__ == '__main__':
    logger.setLevel(logging.DEBUG)
    api = StockBasic()
    # api.process(ProcessType.HISTORY)  # 同步历史数据
    # api.process(ProcessType.INCREASE)  # 同步增量数据
    print(api.stock_basic())    # 数据查询接口
