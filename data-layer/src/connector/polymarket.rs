/// Polymarket connector — 完整的 CLOB API 实现
/// 支持从 Polymarket 预测市场获取实时订单簿数据
///
/// 架构位置：数据获取层 (Rust)
/// 下游：通过 Redis Streams 发送到消息总线

use super::{Connector, ConnectorState, InstrumentKind, NormalizedTick, Symbol};
use async_trait::async_trait;
use rust_decimal::Decimal;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::atomic::{AtomicU8, Ordering};
use std::sync::Arc;
use std::time::Duration;
use tokio::sync::mpsc;
use tokio::time::{interval, Instant};

const DISCONNECTED: u8 = 0;
const CONNECTING: u8 = 1;
const CONNECTED: u8 = 2;
const RECONNECTING: u8 = 3;

/// Polymarket CLOB API 基础 URL
const CLOB_API_BASE: &str = "https://clob.polymarket.com";
/// 轮询间隔（5秒）
const POLL_INTERVAL_SECS: u64 = 5;

/// Polymarket 连接器
pub struct PolymarketConnector {
    clob_api_key: Option<String>,
    state: Arc<AtomicU8>,
    http_client: reqwest::Client,
}

/// Polymarket 订单簿响应
#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct PolymarketOrderBook {
    #[serde(rename = "market")]
    pub market_id: String,
    #[serde(rename = "asset_id")]
    pub asset_id: String,
    pub bids: Vec<PolymarketOrder>,
    pub asks: Vec<PolymarketOrder>,
    #[serde(rename = "timestamp")]
    pub timestamp_ms: Option<u64>,
}

/// Polymarket 订单
#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct PolymarketOrder {
    /// 价格（0.00 ~ 1.00，表示概率）
    #[serde(with = "rust_decimal::serde::str")]
    pub price: Decimal,
    /// 数量（USDC）
    #[serde(with = "rust_decimal::serde::str")]
    pub size: Decimal,
    /// 用户地址
    pub maker_address: Option<String>,
}

/// Polymarket 市场信息
#[derive(Debug, Clone)]
pub struct PolymarketMarket {
    /// 市场 ID (condition_id)
    pub condition_id: String,
    /// 资产 ID (token_id for Yes outcome)
    pub asset_id: String,
    /// 市场标识符
    pub slug: String,
    /// 市场名称
    pub name: String,
}

impl PolymarketConnector {
    pub fn new(clob_api_key: Option<String>) -> Self {
        let http_client = reqwest::Client::builder()
            .timeout(Duration::from_secs(10))
            .pool_idle_timeout(Duration::from_secs(30))
            .build()
            .expect("Failed to create HTTP client");

        Self {
            clob_api_key,
            state: Arc::new(AtomicU8::new(DISCONNECTED)),
            http_client,
        }
    }

    /// 获取订单簿
    async fn fetch_orderbook(
        &self,
        market: &PolymarketMarket,
    ) -> anyhow::Result<PolymarketOrderBook> {
        let url = format!(
            "{}/book?market={}&asset_id={}&side=all",
            CLOB_API_BASE, market.condition_id, market.asset_id
        );

        let mut request = self.http_client.get(&url);

        // 如果有 API Key，添加到请求头
        if let Some(api_key) = &self.clob_api_key {
            request = request.header("POLYMARKET_API_KEY", api_key);
        }

        let response = request.send().await?;

        if !response.status().is_success() {
            let status = response.status();
            let text = response.text().await.unwrap_or_default();
            anyhow::bail!("CLOB API error: {} - {}", status, text);
        }

        let orderbook: PolymarketOrderBook = response.json().await?;
        Ok(orderbook)
    }

    /// 轮询循环
    async fn poll_loop(
        &self,
        markets: Vec<PolymarketMarket>,
        tick_tx: mpsc::Sender<NormalizedTick>,
    ) -> anyhow::Result<()> {
        let mut ticker = interval(Duration::from_secs(POLL_INTERVAL_SECS));

        // 立即执行第一次
        ticker.tick().await;

        loop {
            ticker.tick().await;

            for market in &markets {
                match self.fetch_orderbook(market).await {
                    Ok(orderbook) => {
                        let tick = self.normalize_orderbook(market, &orderbook);

                        if let Err(e) = tick_tx.send(tick).await {
                            tracing::error!("Failed to send tick: {}", e);
                            return Ok(());
                        }

                        tracing::debug!(
                            market = %market.slug,
                            bid = %orderbook.bids.first().map(|o| o.price.to_string()).unwrap_or_default(),
                            ask = %orderbook.asks.first().map(|o| o.price.to_string()).unwrap_or_default(),
                            "Polymarket tick sent"
                        );
                    }
                    Err(e) => {
                        tracing::warn!(market = %market.slug, "Failed to fetch orderbook: {}", e);
                    }
                }
            }
        }
    }

    /// 将 Polymarket 订单簿标准化为 NormalizedTick
    ///
    /// 在预测市场中：
    /// - bid_price = Yes 代币的最高买单价格（市场对Yes的估值）
    /// - ask_price = Yes 代币的最低卖单价格
    /// - 隐含概率 = (bid + ask) / 2
    fn normalize_orderbook(
        &self,
        market: &PolymarketMarket,
        orderbook: &PolymarketOrderBook,
    ) -> NormalizedTick {
        let now_ns = current_timestamp_ns();
        let timestamp_ns = orderbook
            .timestamp_ms
            .map(|ms| ms * 1_000_000)
            .unwrap_or(now_ns);

        // 获取最优买卖价（Polymarket 订单簿已经按价格排序）
        let best_bid = orderbook
            .bids
            .first()
            .map(|o| o.price)
            .unwrap_or(Decimal::ZERO);

        let best_ask = orderbook
            .asks
            .first()
            .map(|o| o.price)
            .unwrap_or(Decimal::ONE);

        // 聚合深度（计算前5档总数量）
        let bid_size: Decimal = orderbook.bids.iter().take(5).map(|o| o.size).sum();
        let ask_size: Decimal = orderbook.asks.iter().take(5).map(|o| o.size).sum();

        // 中间价作为 last_price
        let last_price = if best_bid > Decimal::ZERO && best_ask > Decimal::ZERO {
            (best_bid + best_ask) / Decimal::TWO
        } else {
            Decimal::ZERO
        };

        NormalizedTick {
            symbol: Symbol {
                exchange: "polymarket".to_string(),
                base: market.slug.clone(),
                quote: "USDC".to_string(),
                kind: InstrumentKind::PredictionMarket,
            },
            timestamp_ns,
            received_ns: now_ns,
            bid_price: best_bid,
            bid_size,
            ask_price: best_ask,
            ask_size,
            last_price,
            last_size: Decimal::ZERO, // CLOB 不直接提供 last trade
            volume_24h: Decimal::ZERO, // TODO: 从其他 API 获取
            sequence: None,
        }
    }

    /// 解析 symbol 为 Polymarket 市场
    fn parse_symbol(symbol: &Symbol) -> Option<PolymarketMarket> {
        // 预期格式：condition_id:asset_id:slug
        // 例如：0x123...:0x456...:will-bitcoin-hit-100k
        let parts: Vec<&str> = symbol.base.split(':').collect();
        if parts.len() >= 2 {
            Some(PolymarketMarket {
                condition_id: parts[0].to_string(),
                asset_id: parts[1].to_string(),
                slug: parts.get(2).unwrap_or(&"unknown").to_string(),
                name: symbol.base.clone(),
            })
        } else {
            None
        }
    }

    fn set_state(&self, new_state: u8) {
        self.state.store(new_state, Ordering::Relaxed);
    }
}

#[async_trait]
impl Connector for PolymarketConnector {
    fn id(&self) -> &'static str {
        "polymarket"
    }

    async fn subscribe(
        &self,
        symbols: Vec<Symbol>,
        tick_tx: mpsc::Sender<NormalizedTick>,
    ) -> anyhow::Result<()> {
        self.set_state(CONNECTING);
        tracing::info!(symbols = ?symbols.len(), "Polymarket connector starting");

        // 解析 symbols 为 Polymarket 市场
        let markets: Vec<PolymarketMarket> = symbols
            .iter()
            .filter_map(|s| Self::parse_symbol(s))
            .collect();

        if markets.is_empty() {
            anyhow::bail!("No valid Polymarket markets found in symbols");
        }

        tracing::info!(markets = ?markets.len(), "Parsed Polymarket markets");

        self.set_state(CONNECTED);

        // 启动轮询循环
        self.poll_loop(markets, tick_tx).await?;

        self.set_state(DISCONNECTED);
        Ok(())
    }

    async fn fetch_snapshot(&self, symbol: &Symbol) -> anyhow::Result<NormalizedTick> {
        let market = Self::parse_symbol(symbol)
            .ok_or_else(|| anyhow::anyhow!("Invalid Polymarket symbol format"))?;

        let orderbook = self.fetch_orderbook(&market).await?;
        Ok(self.normalize_orderbook(&market, &orderbook))
    }

    async fn unsubscribe(&self, _symbols: &[Symbol]) -> anyhow::Result<()> {
        // 轮询模式不需要显式取消订阅
        Ok(())
    }

    fn state(&self) -> ConnectorState {
        match self.state.load(Ordering::Relaxed) {
            CONNECTED => ConnectorState::Connected,
            CONNECTING => ConnectorState::Connecting,
            RECONNECTING => ConnectorState::Reconnecting { attempt: 1 },
            _ => ConnectorState::Disconnected,
        }
    }
}

/// 获取当前纳秒时间戳
fn current_timestamp_ns() -> u64 {
    use std::time::SystemTime;
    SystemTime::now()
        .duration_since(SystemTime::UNIX_EPOCH)
        .unwrap_or_default()
        .as_nanos() as u64
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_symbol() {
        let symbol = Symbol {
            exchange: "polymarket".to_string(),
            base: "0x123:0x456:will-btc-hit-100k".to_string(),
            quote: "USDC".to_string(),
            kind: InstrumentKind::PredictionMarket,
        };

        let market = PolymarketConnector::parse_symbol(&symbol).unwrap();
        assert_eq!(market.condition_id, "0x123");
        assert_eq!(market.asset_id, "0x456");
        assert_eq!(market.slug, "will-btc-hit-100k");
    }

    #[test]
    fn test_normalize_orderbook() {
        let connector = PolymarketConnector::new(None);
        let market = PolymarketMarket {
            condition_id: "0x123".to_string(),
            asset_id: "0x456".to_string(),
            slug: "test-market".to_string(),
            name: "Test Market".to_string(),
        };

        let orderbook = PolymarketOrderBook {
            market_id: "0x123".to_string(),
            asset_id: "0x456".to_string(),
            bids: vec![
                PolymarketOrder {
                    price: Decimal::from_f64(0.65).unwrap(),
                    size: Decimal::from_f64(1000.0).unwrap(),
                    maker_address: None,
                },
                PolymarketOrder {
                    price: Decimal::from_f64(0.64).unwrap(),
                    size: Decimal::from_f64(500.0).unwrap(),
                    maker_address: None,
                },
            ],
            asks: vec![
                PolymarketOrder {
                    price: Decimal::from_f64(0.66).unwrap(),
                    size: Decimal::from_f64(800.0).unwrap(),
                    maker_address: None,
                },
            ],
            timestamp_ms: Some(1704067200000),
        };

        let tick = connector.normalize_orderbook(&market, &orderbook);

        assert_eq!(tick.bid_price, Decimal::from_f64(0.65).unwrap());
        assert_eq!(tick.ask_price, Decimal::from_f64(0.66).unwrap());
        assert_eq!(tick.symbol.exchange, "polymarket");
        assert_eq!(tick.symbol.base, "test-market");
    }
}
