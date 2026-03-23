use super::{Connector, ConnectorState, NormalizedTick, Symbol, InstrumentKind};
use crate::transport::ReconnectingWebSocket;
use async_trait::async_trait;
use rust_decimal::Decimal;
use serde::Deserialize;
use std::str::FromStr;
use std::sync::{Arc, atomic::{AtomicU8, Ordering}};
use tokio::sync::mpsc;

const DISCONNECTED: u8 = 0;
const CONNECTING:   u8 = 1;
const CONNECTED:    u8 = 2;

pub struct BinanceConnector {
    api_key: Option<String>,
    state:   Arc<AtomicU8>,
}

impl BinanceConnector {
    pub fn new(api_key: Option<String>) -> Self {
        Self {
            api_key,
            state: Arc::new(AtomicU8::new(DISCONNECTED)),
        }
    }

    fn stream_name(symbol: &Symbol) -> String {
        format!("{}{}@bookTicker",
            symbol.base.to_lowercase(),
            symbol.quote.to_lowercase())
    }
}

#[derive(Deserialize)]
struct BookTicker {
    #[serde(rename = "s")] symbol:    String,
    #[serde(rename = "b")] bid_price: String,
    #[serde(rename = "B")] bid_qty:   String,
    #[serde(rename = "a")] ask_price: String,
    #[serde(rename = "A")] ask_qty:   String,
    #[serde(rename = "T", default)] timestamp: u64,
}

#[async_trait]
impl Connector for BinanceConnector {
    fn id(&self) -> &'static str { "binance" }

    async fn subscribe(
        &self,
        symbols: Vec<Symbol>,
        tick_tx: mpsc::Sender<NormalizedTick>,
    ) -> anyhow::Result<()> {
        let streams: Vec<String> = symbols.iter().map(Self::stream_name).collect();
        let stream_param = streams.join("/");
        let url = format!("wss://stream.binance.com:9443/stream?streams={stream_param}");

        let sub_msg = serde_json::json!({
            "method": "SUBSCRIBE",
            "params": streams,
            "id": 1
        }).to_string();

        let (raw_tx, mut raw_rx) = mpsc::channel::<String>(8192);
        let (stop_tx, stop_rx)   = tokio::sync::oneshot::channel();
        let _ = stop_tx; // keep alive

        let state_c  = Arc::clone(&self.state);
        let symbols_c = symbols.clone();

        let ws = ReconnectingWebSocket::new(url, Default::default());
        tokio::spawn(async move {
            state_c.store(CONNECTING, Ordering::Relaxed);
            ws.run(vec![sub_msg], raw_tx, stop_rx).await;
            state_c.store(DISCONNECTED, Ordering::Relaxed);
        });

        let state_c2 = Arc::clone(&self.state);
        tokio::spawn(async move {
            while let Some(raw) = raw_rx.recv().await {
                if let Ok(v) = serde_json::from_str::<serde_json::Value>(&raw) {
                    if let Some(data) = v.get("data") {
                        if let Ok(t) = serde_json::from_value::<BookTicker>(data.clone()) {
                            state_c2.store(CONNECTED, Ordering::Relaxed);
                            let sym_upper = t.symbol.to_uppercase();
                            let symbol = symbols_c.iter()
                                .find(|s| format!("{}{}", s.base, s.quote) == sym_upper)
                                .cloned()
                                .unwrap_or(Symbol {
                                    exchange: "binance".into(),
                                    base:  sym_upper[..3].to_string(),
                                    quote: sym_upper[3..].to_string(),
                                    kind:  InstrumentKind::Spot,
                                });

                            let now = std::time::SystemTime::now()
                                .duration_since(std::time::UNIX_EPOCH)
                                .unwrap_or_default()
                                .as_nanos() as u64;

                            let tick = NormalizedTick {
                                symbol,
                                timestamp_ns: t.timestamp.saturating_mul(1_000_000),
                                received_ns:  now,
                                bid_price:  Decimal::from_str(&t.bid_price).unwrap_or_default(),
                                bid_size:   Decimal::from_str(&t.bid_qty).unwrap_or_default(),
                                ask_price:  Decimal::from_str(&t.ask_price).unwrap_or_default(),
                                ask_size:   Decimal::from_str(&t.ask_qty).unwrap_or_default(),
                                last_price: Decimal::from_str(&t.bid_price).unwrap_or_default(),
                                last_size:  Decimal::ZERO,
                                volume_24h: Decimal::ZERO,
                                sequence:   None,
                            };

                            if tick_tx.send(tick).await.is_err() { break; }
                        }
                    }
                }
            }
        });

        Ok(())
    }

    async fn fetch_snapshot(&self, symbol: &Symbol) -> anyhow::Result<NormalizedTick> {
        let pair = format!("{}{}", symbol.base, symbol.quote).to_uppercase();
        let url  = format!("https://api.binance.com/api/v3/ticker/bookTicker?symbol={pair}");
        let v: serde_json::Value = reqwest::get(&url).await?.json().await?;
        let now = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)?
            .as_nanos() as u64;
        Ok(NormalizedTick {
            symbol:       symbol.clone(),
            timestamp_ns: now,
            received_ns:  now,
            bid_price: Decimal::from_str(v["bidPrice"].as_str().unwrap_or("0"))?,
            bid_size:  Decimal::from_str(v["bidQty"].as_str().unwrap_or("0"))?,
            ask_price: Decimal::from_str(v["askPrice"].as_str().unwrap_or("0"))?,
            ask_size:  Decimal::from_str(v["askQty"].as_str().unwrap_or("0"))?,
            last_price: Decimal::ZERO,
            last_size:  Decimal::ZERO,
            volume_24h: Decimal::ZERO,
            sequence:   None,
        })
    }

    async fn unsubscribe(&self, _symbols: &[Symbol]) -> anyhow::Result<()> {
        Ok(())
    }

    fn state(&self) -> ConnectorState {
        match self.state.load(Ordering::Relaxed) {
            CONNECTING => ConnectorState::Connecting,
            CONNECTED  => ConnectorState::Connected,
            _          => ConnectorState::Disconnected,
        }
    }
}
