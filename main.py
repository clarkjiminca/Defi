
# 这是一个自动生成的Python文件
def hello_world():
    print("Hello, world! Time is 'Fri Nov 10 15:10:10 2023'")


if __name__ == "__main__":
    hello_world()
    a = 1
             * \project	WonderTrader
 *
 * \author Wesley
 * \date 2020/03/30
 * 
 * \brief 
 */
#include "ParserYD.h"

#include "../Includes/WTSDataDef.hpp"
#include "../Includes/WTSContractInfo.hpp"
#include "../Includes/WTSVariant.hpp"
#include "../Includes/IBaseDataMgr.h"

#include "../Share/ModuleHelper.hpp"
#include "../Share/TimeUtils.hpp"
#include "../Share/StdUtils.hpp"

#include <boost/filesystem.hpp>

 //By Wesley @ 2022.01.05
#include "../Share/fmtlib.h"
template<typename... Args>
inline void write_log(IParserSpi* sink, WTSLogLevel ll, const char* format, const Args&... args)
{
	if (sink == NULL)
		return;

	static thread_local char buffer[512] = { 0 };
	memset(buffer, 0, 512);
	fmt::format_to(buffer, format, args...);

	sink->handleParserLog(ll, buffer);
}

extern "C"
{
	EXPORT_FLAG IParserApi* createParser()
	{
		ParserYD* parser = new ParserYD();
		return parser;
	}

	EXPORT_FLAG void deleteParser(IParserApi* &parser)
	{
		if (NULL != parser)
		{
			delete parser;
			parser = NULL;
		}
	}
};


ParserYD::ParserYD()
	: m_pUserAPI(NULL)
	, m_uTradingDate(0)
	, m_bApiInited(false)
{
}


ParserYD::~ParserYD()
{
	m_pUserAPI = NULL;
}

void ParserYD::notifyReadyForLogin(bool hasLoginFailed)
{
	if (m_sink)
	{
		write_log(m_sink, LL_INFO, "[ParserYD] Market data server connected");
		m_sink->handleEvent(WPE_Connect, 0);
	}

	DoLogin();
}


void ParserYD::notifyLogin(int errorNo, int maxOrderRef, bool isMonitor)
{
	if (errorNo == 0)
	{
		write_log(m_sink, LL_INFO, "[ParserYD] {} login successfully", m_strUserID);

		m_uTradingDate = m_pUserAPI->getTradingDay();
		if (m_sink)
		{
			m_sink->handleEvent(WPE_Login, 0);
		}

		//如果API初始化过了，就直接订阅
		//这种一般是断线重连
		if (m_bApiInited)
		{
			//订阅行情数据
			DoSubscribe();
		}
	}
	else
	{
		write_log(m_sink, LL_INFO, "[ParserYD] {} login failed, error no: {}", m_strUserID, errorNo);
	}
}


void ParserYD::notifyFinishInit(void)
{
	if (m_sink) m_sink->handleParserLog(LL_INFO, "[ParserYD] All things ready");

	//如果API没有初始化过，说明这个回调是第一次触发
	//则需要触发一些订阅等操作
	if(!m_bApiInited)
	{
		//订阅行情数据
		DoSubscribe();
		m_bApiInited = true;
	}
}


void ParserYD::notifyMarketData(const YDMarketData *pDepthMarketData)
{
	if (m_pBaseDataMgr == NULL)
		return;

	const YDInstrument* instInfo = pDepthMarketData->m_pInstrument;
	const YDExchange* exchgInfo = instInfo->m_pExchange;
	uint32_t actDate = pDepthMarketData->TradingDay;
	uint32_t actTime = pDepthMarketData->TimeStamp;
	uint32_t actHour = actTime / 10000000;

	WTSContractInfo* contract = m_pBaseDataMgr->getContract(instInfo->InstrumentID, exchgInfo->ExchangeID);
	if (contract == NULL)
		return;

	WTSTickData* tick = WTSTickData::create(instInfo->InstrumentID);
	WTSTickStruct& quote = tick->getTickStruct();
	wt_strcpy(quote.exchg, contract->getExchg());
	tick->setContractInfo(contract);

	quote.action_date = actDate;
	quote.action_time = actTime;

	quote.price = pDepthMarketData->LastPrice;
	quote.total_volume = pDepthMarketData->Volume;
	quote.trading_date = m_uTradingDate;
	quote.total_turnover = pDepthMarketData->Turnover;

	quote.open_interest = pDepthMarketData->OpenInterest;

	quote.upper_limit = pDepthMarketData->UpperLimitPrice;
	quote.lower_limit = pDepthMarketData->LowerLimitPrice;

	quote.pre_close = pDepthMarketData->PreClosePrice;
	quote.pre_settle = pDepthMarketData->PreSettlementPrice;
	quote.pre_interest = pDepthMarketData->PreOpenInterest;

	//委卖价格
	quote.ask_prices[0] = pDepthMarketData->AskPrice;
	//委买价格
	quote.bid_prices[0] = pDepthMarketData->BidPrice;
	//委卖量
	quote.ask_qty[0] = pDepthMarketData->AskVolume;
	//委买量
	quote.bid_qty[0] = pDepthMarketData->BidVolume;

	if (m_sink)
		m_sink->handleQuote(tick, 1);

	tick->release();
}

bool ParserYD::init(WTSVariant* config)
{
	m_strCfgFile = config->getCString("config");
	m_strUserID = config->getCString("user");
	m_strPassword = config->getCString("pass");

	std::string module = config->getCString("ydmodule");
	if (module.empty())
