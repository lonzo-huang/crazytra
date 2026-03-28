// MirrorQuant Tick 标准类型定义（Rust）
// 用于 NautilusTrader Runner 的桥接层

use serde::{Deserialize, Serialize};

/// 订单簿档位
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OrderBookLevel {
    pub price: f64,
    pub size: f64,
}

/// 完整订单簿
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OrderBook {
    pub bids: Vec<OrderBookLevel>,
    pub asks: Vec<OrderBookLevel>,
}

/// Polymarket 专用扩展字段
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PolymarketExtension {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub outcome: Option<String>, // "YES" or "NO"
    
    #[serde(skip_serializing_if = "Option::is_none")]
    pub liquidity: Option<f64>,
    
    #[serde(skip_serializing_if = "Option::is_none")]
    pub probability: Option<f64>,
    
    #[serde(skip_serializing_if = "Option::is_none")]
    pub market_type: Option<String>, // "binary" or "categorical"
}

/// MQ Tick 核心数据
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MQTickPayload {
    /// MQ 统一符号格式，如 POLY:TRUMP_WIN
    pub symbol: String,
    
    /// 交易所原始市场 ID
    pub market_id: String,
    
    /// 资产类型：prediction, spot, future, option, swap
    pub instrument_type: String,
    
    /// 交易所名称
    pub exchange: String,
    
    // 最佳买卖价
    #[serde(skip_serializing_if = "Option::is_none")]
    pub bid: Option<f64>,
    
    #[serde(skip_serializing_if = "Option::is_none")]
    pub ask: Option<f64>,
    
    #[serde(skip_serializing_if = "Option::is_none")]
    pub mid: Option<f64>,
    
    // 最佳买卖量
    #[serde(skip_serializing_if = "Option::is_none")]
    pub bid_size: Option<f64>,
    
    #[serde(skip_serializing_if = "Option::is_none")]
    pub ask_size: Option<f64>,
    
    // 最新成交
    #[serde(skip_serializing_if = "Option::is_none")]
    pub last_price: Option<f64>,
    
    #[serde(skip_serializing_if = "Option::is_none")]
    pub last_size: Option<f64>,
    
    #[serde(skip_serializing_if = "Option::is_none")]
    pub last_side: Option<String>, // "buy" or "sell"
    
    // 市场统计
    #[serde(skip_serializing_if = "Option::is_none")]
    pub volume_24h: Option<f64>,
    
    #[serde(skip_serializing_if = "Option::is_none")]
    pub open_interest: Option<f64>,
    
    // 完整订单簿（可选）
    #[serde(skip_serializing_if = "Option::is_none")]
    pub orderbook: Option<OrderBook>,
    
    // Polymarket 专用扩展
    #[serde(skip_serializing_if = "Option::is_none")]
    pub polymarket: Option<PolymarketExtension>,
}

/// MQ Tick 完整事件（顶层 Envelope）
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MQTickEvent {
    /// 事件类型，固定为 "market_tick"
    #[serde(rename = "type")]
    pub event_type: String,
    
    /// MQ 接收时间戳（毫秒）
    pub ts_event: i64,
    
    /// 交易所事件时间戳（毫秒）
    pub ts_exchange: i64,
    
    /// 数据来源：polymarket, binance, trading212, tiger, okx, bybit
    pub source: String,
    
    /// Tick 核心数据
    pub payload: MQTickPayload,
}

impl MQTickEvent {
    /// 创建新的 MQ Tick 事件
    pub fn new(source: &str, payload: MQTickPayload) -> Self {
        let now = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_millis() as i64;
        
        Self {
            event_type: "market_tick".to_string(),
            ts_event: now,
            ts_exchange: now,
            source: source.to_string(),
            payload,
        }
    }
    
    /// 序列化为 JSON 字符串
    pub fn to_json(&self) -> Result<String, serde_json::Error> {
        serde_json::to_string(self)
    }
    
    /// 从 JSON 字符串反序列化
    pub fn from_json(json: &str) -> Result<Self, serde_json::Error> {
        serde_json::from_str(json)
    }
}

/// NT Tick → MQ Tick 转换器
pub struct NTToMQTickConverter;

impl NTToMQTickConverter {
    /// 将 Polymarket 市场数据转换为 MQ Tick
    pub fn convert_polymarket_market(
        market_id: &str,
        bid: Option<f64>,
        ask: Option<f64>,
        volume: f64,
        liquidity: f64,
    ) -> MQTickEvent {
        let mid = match (bid, ask) {
            (Some(b), Some(a)) => Some((b + a) / 2.0),
            _ => None,
        };
        
        let payload = MQTickPayload {
            symbol: format!("POLY:{}", market_id),
            market_id: market_id.to_string(),
            instrument_type: "prediction".to_string(),
            exchange: "polymarket".to_string(),
            bid,
            ask,
            mid,
            bid_size: Some(1000.0), // 默认值
            ask_size: Some(1000.0), // 默认值
            last_price: mid,
            last_size: None,
            last_side: None,
            volume_24h: Some(volume),
            open_interest: None,
            orderbook: None,
            polymarket: Some(PolymarketExtension {
                outcome: None,
                liquidity: Some(liquidity),
                probability: mid,
                market_type: Some("binary".to_string()),
            }),
        };
        
        MQTickEvent::new("polymarket", payload)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn test_mq_tick_creation() {
        let tick = NTToMQTickConverter::convert_polymarket_market(
            "TRUMP_WIN",
            Some(0.62),
            Some(0.63),
            120000.0,
            50000.0,
        );
        
        assert_eq!(tick.event_type, "market_tick");
        assert_eq!(tick.source, "polymarket");
        assert_eq!(tick.payload.symbol, "POLY:TRUMP_WIN");
        assert_eq!(tick.payload.bid, Some(0.62));
        assert_eq!(tick.payload.ask, Some(0.63));
        assert_eq!(tick.payload.mid, Some(0.625));
    }
    
    #[test]
    fn test_json_serialization() {
        let tick = NTToMQTickConverter::convert_polymarket_market(
            "TRUMP_WIN",
            Some(0.62),
            Some(0.63),
            120000.0,
            50000.0,
        );
        
        let json = tick.to_json().unwrap();
        assert!(json.contains("market_tick"));
        assert!(json.contains("POLY:TRUMP_WIN"));
        
        let restored = MQTickEvent::from_json(&json).unwrap();
        assert_eq!(restored.payload.symbol, "POLY:TRUMP_WIN");
    }
}
