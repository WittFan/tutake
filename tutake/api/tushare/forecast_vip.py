"""
This file is auto generator by CodeGenerator. Don't modify it directly, instead alter tushare_api.tmpl of it.

Tushare forecast_vip接口
获取业绩预告数据
数据接口-沪深股票-财务数据-业绩预告  https://tushare.pro/document/2?doc_id=4500

@author: rmfish
"""
import pandas as pd
import tushare as ts
from sqlalchemy import Integer, String, Float, Column, create_engine
from sqlalchemy.orm import sessionmaker

from tutake.api.process import DataProcess
from tutake.api.process_report import ProcessException
from tutake.api.tushare.forecast_vip_ext import *
from tutake.api.tushare.base_dao import BaseDao, Base
from tutake.api.tushare.dao import DAO
from tutake.api.tushare.tushare_base import TuShareBase
from tutake.utils.config import TutakeConfig
from tutake.utils.utils import project_root


class TushareForecastVip(Base):
    __tablename__ = "tushare_forecast_vip"
    id = Column(Integer, primary_key=True, autoincrement=True)
    ts_code = Column(String, index=True, comment='TS股票代码')
    ann_date = Column(String, index=True, comment='公告日期')
    end_date = Column(String, index=True, comment='报告期')
    type = Column(String, index=True, comment='业绩预告类型')
    p_change_min = Column(Float, comment='预告净利润变动幅度下限（%）')
    p_change_max = Column(Float, comment='预告净利润变动幅度上限（%）')
    net_profit_min = Column(Float, comment='预告净利润下限（万元）')
    net_profit_max = Column(Float, comment='预告净利润上限（万元）')
    last_parent_net = Column(Float, comment='上年同期归属母公司净利润')
    notice_times = Column(Integer, comment='公布次数')
    first_ann_date = Column(String, comment='首次公告日')
    summary = Column(String, comment='业绩预告摘要')
    change_reason = Column(String, comment='业绩变动原因')


class ForecastVip(BaseDao, TuShareBase, DataProcess):
    instance = None

    def __new__(cls, *args, **kwargs):
        if cls.instance is None:
            cls.instance = super().__new__(cls)
        return cls.instance

    def __init__(self, config):
        self.engine = create_engine("%s/%s" % (config.get_data_sqlite_driver_url(), 'tushare_forecast_vip.db'),
                                    connect_args={'check_same_thread': False})
        session_factory = sessionmaker()
        session_factory.configure(bind=self.engine)
        TushareForecastVip.__table__.create(bind=self.engine, checkfirst=True)

        query_fields = ['ts_code', 'ann_date', 'start_date', 'end_date', 'period', 'type', 'limit', 'offset']
        entity_fields = [
            "ts_code", "ann_date", "end_date", "type", "p_change_min", "p_change_max", "net_profit_min",
            "net_profit_max", "last_parent_net", "notice_times", "first_ann_date", "summary", "change_reason"
        ]
        BaseDao.__init__(self, self.engine, session_factory, TushareForecastVip, 'tushare_forecast_vip', query_fields,
                         entity_fields)
        DataProcess.__init__(self, "forecast_vip", config)
        TuShareBase.__init__(self, "forecast_vip", config, 5000)
        self.dao = DAO()

    def forecast_vip(self, fields='', **kwargs):
        """
        获取业绩预告数据
        | Arguments:
        | ts_code(str):   股票代码
        | ann_date(str):   公告日期
        | start_date(str):   公告开始日期
        | end_date(str):   公告结束日期
        | period(str):   报告期
        | type(str):   预告类型
        | limit(int):   单次返回数据长度
        | offset(int):   请求数据的开始位移量
        
        :return: DataFrame
         ts_code(str)  TS股票代码
         ann_date(str)  公告日期
         end_date(str)  报告期
         type(str)  业绩预告类型
         p_change_min(float)  预告净利润变动幅度下限（%）
         p_change_max(float)  预告净利润变动幅度上限（%）
         net_profit_min(float)  预告净利润下限（万元）
         net_profit_max(float)  预告净利润上限（万元）
         last_parent_net(float)  上年同期归属母公司净利润
         notice_times(int)  公布次数
         first_ann_date(str)  首次公告日
         summary(str)  业绩预告摘要
         change_reason(str)  业绩变动原因
        
        """
        return super().query(fields, **kwargs)

    def process(self, process_type: ProcessType = ProcessType.INCREASE):
        """
        同步历史数据
        :return:
        """
        return super()._process(process_type, self.fetch_and_append)

    def fetch_and_append(self, **kwargs):
        """
        获取tushare数据并append到数据库中
        :return: 数量行数
        """
        init_args = {
            "ts_code": "",
            "ann_date": "",
            "start_date": "",
            "end_date": "",
            "period": "",
            "type": "",
            "limit": "",
            "offset": ""
        }
        if len(kwargs.keys()) == 0:
            kwargs = init_args
        # 初始化offset和limit
        if not kwargs.get("limit"):
            kwargs['limit'] = self.default_limit()
        init_offset = 0
        offset = 0
        if kwargs.get('offset'):
            offset = int(kwargs['offset'])
            init_offset = offset

        kwargs = {key: kwargs[key] for key in kwargs.keys() & init_args.keys()}

        def fetch_save(offset_val=0):
            try:
                kwargs['offset'] = str(offset_val)
                self.logger.debug("Invoke pro.forecast_vip with args: {}".format(kwargs))
                res = self.tushare_query('forecast_vip', fields=self.entity_fields, **kwargs)
                res.to_sql('tushare_forecast_vip',
                           con=self.engine,
                           if_exists='append',
                           index=False,
                           index_label=['ts_code'])
                return res
            except Exception as err:
                raise ProcessException(kwargs, err)

        df = fetch_save(offset)
        offset += df.shape[0]
        while kwargs['limit'] != "" and str(df.shape[0]) == kwargs['limit']:
            df = fetch_save(offset)
            offset += df.shape[0]
        return offset - init_offset


setattr(ForecastVip, 'default_limit', default_limit_ext)
setattr(ForecastVip, 'default_cron_express', default_cron_express_ext)
setattr(ForecastVip, 'default_order_by', default_order_by_ext)
setattr(ForecastVip, 'prepare', prepare_ext)
setattr(ForecastVip, 'tushare_parameters', tushare_parameters_ext)
setattr(ForecastVip, 'param_loop_process', param_loop_process_ext)

if __name__ == '__main__':
    pd.set_option('display.max_columns', 50)    # 显示列数
    pd.set_option('display.width', 100)
    config = TutakeConfig(project_root())
    pro = ts.pro_api(config.get_tushare_token())
    print(pro.forecast_vip())

    api = ForecastVip(config)
    api.process()    # 同步增量数据
    print(api.forecast_vip())    # 数据查询接口
