pub mod binance;
pub mod polymarket;

use async_trait::async_trait;
use rust_decimal::Decimal;
use std::sync::Arc;
use tokio::sync::mpsc;
use dashmap::DashMap;

#[derive(Debug, Clone, PartialEq, Eq, Hash)]
pub struct Symbol {
    pub exchange: String,
    pub base:     String,
    pub quote:    String,
    pub kind:     InstrumentKind,
}

#[derive(Debug, Clone, PartialEq, Eq, Hash)]
pub enum InstrumentKind {
    Spot,
    PerpetualFuture,
    PredictionMarket,
    Option { expiry: String, strike: String },
}

#[derive(Debug, Clone)]
pub struct NormalizedTick {
    pub symbol:       Symbol,
    pub timestamp_ns: u64,
    pub received_ns:  u64,
    pub bid_price:    Decimal,
    pub bid_size:     Decimal,
    pub ask_price:    Decimal,
    pub ask_size:     Decimal,
    pub last_price:   Decimal,
    pub last_size:    Decimal,
    pub volume_24h:   Decimal,
    pub sequence:     Option<u64>,
}

impl NormalizedTick {
    pub fn mid_price(&self) -> Decimal {
        (self.bid_price + self.ask_price) / Decimal::TWO
    }

    pub fn spread_bps(&self) -> Decimal {
        let mid = self.mid_price();
        if mid.is_zero() { return Decimal::ZERO; }
        (self.ask_price - self.bid_price) / mid * Decimal::from(10000)
    }

    pub fn latency_us(&self) -> u64 {
        self.received_ns.saturating_sub(self.timestamp_ns) / 1000
    }
}

#[derive(Debug, Clone, PartialEq)]
pub enum ConnectorState {
    Disconnected,
    Connecting,
    Connected,
    Reconnecting { attempt: u32 },
    Failed(String),
}

#[async_trait]
pub trait Connector: Send + Sync + 'static {
    fn id(&self) -> &'static str;

    async fn subscribe(
        &self,
        symbols: Vec<Symbol>,
        tick_tx: mpsc::Sender<NormalizedTick>,
    ) -> anyhow::Result<()>;

    async fn fetch_snapshot(&self, symbol: &Symbol) -> anyhow::Result<NormalizedTick>;

    async fn unsubscribe(&self, symbols: &[Symbol]) -> anyhow::Result<()>;

    fn state(&self) -> ConnectorState;
}

pub struct ConnectorRegistry {
    connectors: DashMap<String, Arc<dyn Connector>>,
}

impl ConnectorRegistry {
    pub fn new() -> Self {
        Self { connectors: DashMap::new() }
    }

    pub fn register(&self, connector: Arc<dyn Connector>) {
        let id = connector.id().to_string();
        tracing::info!(connector = %id, "Connector registered");
        self.connectors.insert(id, connector);
    }

    pub fn get(&self, id: &str) -> Option<Arc<dyn Connector>> {
        self.connectors.get(id).map(|v| Arc::clone(&*v))
    }

    pub fn health_report(&self) -> Vec<(String, ConnectorState)> {
        self.connectors
            .iter()
            .map(|e| (e.key().clone(), e.value().state()))
            .collect()
    }
}
