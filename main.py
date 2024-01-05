
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
