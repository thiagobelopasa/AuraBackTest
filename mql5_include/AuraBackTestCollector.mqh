//+------------------------------------------------------------------+
//|  AuraBackTestCollector.mqh                                       |
//|  Copie este arquivo para:                                        |
//|    <MT5 Data Folder>\MQL5\Include\AuraBackTestCollector.mqh      |
//|                                                                  |
//|  Uso no seu EA:                                                  |
//|    #include <AuraBackTestCollector.mqh>                          |
//|                                                                  |
//|    double OnTester()                                             |
//|    {                                                             |
//|       string params = "";                                        |
//|       AuraAddParam(params, "StopLoss", StopLoss);                |
//|       AuraAddParam(params, "TakeProfit", TakeProfit);            |
//|       // ... um AuraAddParam pra cada input que interessa        |
//|       AuraCollect(params);                                       |
//|       return TesterStatistics(STAT_COMPLEX_CRITERION);           |
//|    }                                                             |
//|                                                                  |
//|  Os arquivos são gravados em:                                    |
//|    %APPDATA%\MetaQuotes\Terminal\Common\Files\AuraBackTest\      |
//|                                                                  |
//|  O AuraBackTest (app) roda um watcher nesse diretório e coleta   |
//|  cada pass em tempo real durante a otimização.                   |
//+------------------------------------------------------------------+
#property strict

#define AURA_DIR "AuraBackTest"

//--- Helpers para montar o bloco JSON de parâmetros do EA
void AuraAddParam(string &buf, string name, double value)
{
   if(StringLen(buf) > 0) buf += ",";
   buf += StringFormat("\"%s\":%.6f", name, value);
}

void AuraAddParam(string &buf, string name, long value)
{
   if(StringLen(buf) > 0) buf += ",";
   buf += StringFormat("\"%s\":%I64d", name, value);
}

void AuraAddParam(string &buf, string name, int value)
{
   if(StringLen(buf) > 0) buf += ",";
   buf += StringFormat("\"%s\":%d", name, value);
}

void AuraAddParam(string &buf, string name, bool value)
{
   if(StringLen(buf) > 0) buf += ",";
   buf += StringFormat("\"%s\":%s", name, value ? "true" : "false");
}

void AuraAddParam(string &buf, string name, string value)
{
   if(StringLen(buf) > 0) buf += ",";
   buf += StringFormat("\"%s\":\"%s\"", name, value);
}

//--- Gera ID único por pass usando hash dos parâmetros + timestamp
string AuraBuildPassId()
{
   ulong ms = (ulong)GetMicrosecondCount();
   return StringFormat("%I64u_%d", ms, MathRand());
}

//--- Exporta os deals do backtest atual para arquivo JSON na pasta comum
//    `parameters_json` deve ser o conteúdo dentro de {} — use AuraAddParam() pra construir.
void AuraCollect(string parameters_json = "")
{
   string pass_id = AuraBuildPassId();
   string filename = AURA_DIR + "\\pass_" + pass_id + ".json";

   int h = FileOpen(filename, FILE_WRITE | FILE_TXT | FILE_ANSI | FILE_COMMON);
   if(h == INVALID_HANDLE)
   {
      PrintFormat("[AuraCollect] Falha ao criar %s, erro=%d", filename, GetLastError());
      return;
   }

   // Header JSON
   FileWriteString(h, "{\n");
   FileWriteString(h, StringFormat("  \"pass_id\": \"%s\",\n", pass_id));
   FileWriteString(h, StringFormat("  \"timestamp\": \"%s\",\n", TimeToString(TimeCurrent(), TIME_DATE|TIME_SECONDS)));
   FileWriteString(h, StringFormat("  \"symbol\": \"%s\",\n", _Symbol));
   FileWriteString(h, StringFormat("  \"period\": %d,\n", (int)_Period));
   FileWriteString(h, StringFormat("  \"initial_deposit\": %.2f,\n", TesterStatistics(STAT_INITIAL_DEPOSIT)));
   FileWriteString(h, StringFormat("  \"parameters\": {%s},\n", parameters_json));

   // Métricas agregadas (o backend também recalcula, mas serve como sanity check)
   FileWriteString(h, StringFormat("  \"net_profit\": %.2f,\n", TesterStatistics(STAT_PROFIT)));
   FileWriteString(h, StringFormat("  \"profit_factor\": %.4f,\n", TesterStatistics(STAT_PROFIT_FACTOR)));
   FileWriteString(h, StringFormat("  \"expected_payoff\": %.4f,\n", TesterStatistics(STAT_EXPECTED_PAYOFF)));
   FileWriteString(h, StringFormat("  \"sharpe_ratio\": %.4f,\n", TesterStatistics(STAT_SHARPE_RATIO)));
   FileWriteString(h, StringFormat("  \"trades_count\": %d,\n", (int)TesterStatistics(STAT_TRADES)));

   // Lista de TODOS os deals (IN + OUT) com position_id e entry para parear no backend.
   // entry: 0=IN (abertura), 1=OUT (fechamento), 2=INOUT (reversão), 3=OUT_BY (close-by)
   // O Python usa position_id para parear IN↔OUT e reconstruir time_in/entry_price corretos.
   HistorySelect(0, TimeCurrent());
   int deals_total = HistoryDealsTotal();
   FileWriteString(h, "  \"deals\": [\n");

   bool first = true;
   for(int i = 0; i < deals_total; i++)
   {
      ulong ticket = HistoryDealGetTicket(i);
      if(ticket == 0) continue;

      long entry = HistoryDealGetInteger(ticket, DEAL_ENTRY);
      // Ignora depósitos/retiradas (DEAL_ENTRY_IN com profit != 0 e sem posição) —
      // apenas negociações reais (entry 0, 1, 2, 3)
      if(entry < 0 || entry > 3) continue;

      long type = HistoryDealGetInteger(ticket, DEAL_TYPE);
      // Ignora deals de balance/crédito (tipos >= 2 são não-trade no MT5)
      if(type >= 2) continue;

      long position_id = HistoryDealGetInteger(ticket, DEAL_POSITION_ID);
      datetime time    = (datetime)HistoryDealGetInteger(ticket, DEAL_TIME);
      double price      = HistoryDealGetDouble(ticket, DEAL_PRICE);
      double volume     = HistoryDealGetDouble(ticket, DEAL_VOLUME);
      double profit     = HistoryDealGetDouble(ticket, DEAL_PROFIT);
      double swap       = HistoryDealGetDouble(ticket, DEAL_SWAP);
      double commission = HistoryDealGetDouble(ticket, DEAL_COMMISSION);

      if(!first) FileWriteString(h, ",\n");
      FileWriteString(h, StringFormat(
         "    {\"position_id\":%I64d,\"entry\":%d,\"time\":\"%s\",\"type\":%d,\"price\":%.5f,\"volume\":%.2f,\"profit\":%.2f,\"swap\":%.2f,\"commission\":%.2f}",
         position_id, (int)entry, TimeToString(time, TIME_DATE|TIME_SECONDS),
         (int)type, price, volume, profit, swap, commission
      ));
      first = false;
   }
   FileWriteString(h, "\n  ]\n");
   FileWriteString(h, "}\n");

   FileClose(h);
}
