//! Polymarket DataEngine - Rust implementation for high-performance data processing
//! 
//! This module provides:
//! - Gamma API client for market data
//! - CLOB client for trading operations
//! - WebSocket client for real-time updates
//! - Data normalization into standard Nautilus format

use pyo3::prelude::*;
use pyo3::types::PyDict;
use tokio_tungstenite::{connect_async, tungstenite::Message};
use futures_util::StreamExt;
use reqwest::Client;
use serde::{Deserialize, Serialize};
use serde_json::Value;
use chrono::{DateTime, Utc};
use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::{Mutex, RwLock};
use tracing::{info, warn, error, debug};
use uuid::Uuid;

use crate::models::{MarketData, QuoteTick, TradeTick, OrderBook};

/// Configuration for Polymarket DataEngine
#[derive(Debug, Clone)]
pub struct PolymarketConfig {
    pub gamma_api_url: String,
    pub clob_api_url: String,
    pub ws_url: String,
    pub timeout_seconds: u64,
}

impl Default for PolymarketConfig {
    fn default() -> Self {
        Self {
            gamma_api_url: "https://gamma-api.polymarket.com".to_string(),
            clob_api_url: "https://clob.polymarket.com".to_string(),
            ws_url: "wss://ws-subscriptions-clob.polymarket.com/ws/market".to_string(),
            timeout_seconds: 30,
        }
    }
}

/// Polymarket market data from Gamma API
#[derive(Debug, Deserialize)]
struct GammaMarket {
    id: String,
    #[serde(rename = "conditionId")]
    condition_id: String,
    slug: String,
    question: String,
    description: Option<String>,
    #[serde(deserialize_with = "deserialize_f64_from_string")]
    volume: f64,
    #[serde(deserialize_with = "deserialize_f64_from_string")]
    liquidity: f64,
    #[serde(rename = "endDateIso")]
    end_date_iso: String,
    active: bool,
    closed: bool,
    resolved: bool,
    #[serde(rename = "clobTokenIds")]
    clob_token_ids: Option<String>,  // API returns string, not array
    category: Option<String>,
    #[serde(rename = "startDateIso")]
    start_date_iso: Option<String>,
    
    // 捕获所有其他字段
    #[serde(flatten)]
    other: std::collections::HashMap<String, serde_json::Value>,
}

/// Helper function to deserialize f64 from string
fn deserialize_f64_from_string<'de, D>(deserializer: D) -> Result<f64, D::Error>
where
    D: serde::Deserializer<'de>,
{
    let s = String::deserialize(deserializer)?;
    s.parse().map_err(serde::de::Error::custom)
}

/// CLOB order book data
#[derive(Debug, Deserialize)]
struct ClobOrderBook {
    market_id: String,
    bids: Vec<[f64; 2]>,
    asks: Vec<[f64; 2]>,
    last_update: i64,
}

/// WebSocket message from Polymarket
#[derive(Debug, Deserialize)]
#[serde(tag = "type")]
enum WsMessage {
    Book {
        asset_id: String,
        bids: Vec<[f64; 2]>,
        asks: Vec<[f64; 2]>,
        timestamp: i64,
    },
    Trade {
        asset_id: String,
        price: f64,
        size: f64,
        side: String,
        timestamp: i64,
    },
    PriceChange {
        asset_id: String,
        price: f64,
        timestamp: i64,
    },
    #[serde(other)]
    Unknown,
}

/// High-performance Polymarket DataEngine in Rust
#[pyclass]
pub struct PolymarketDataEngine {
    config: PolymarketConfig,
    client: Client,
    order_books: Arc<RwLock<HashMap<String, OrderBook>>>,
    subscribed_assets: Arc<RwLock<HashMap<String, bool>>>,
    markets_cache: Arc<RwLock<Vec<MarketData>>>,
}

#[pymethods]
impl PolymarketDataEngine {
    /// Create new Polymarket DataEngine
    #[new]
    fn new() -> PyResult<Self> {
        let config = PolymarketConfig::default();
        
        Ok(Self {
            config,
            client: Client::new(),
            order_books: Arc::new(RwLock::new(HashMap::new())),
            subscribed_assets: Arc::new(RwLock::new(HashMap::new())),
            markets_cache: Arc::new(RwLock::new(Vec::new())),
        })
    }

    /// Fetch markets from Gamma API
    fn fetch_markets(&self, py: Python) -> PyResult<Vec<MarketData>> {
        py.allow_threads(|| {
            let rt = tokio::runtime::Runtime::new()
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(format!("Failed to create runtime: {}", e)))?;
            
            rt.block_on(self._fetch_markets_async())
        })
    }

    /// Get order book for specific asset
    fn get_order_book(&self, asset_id: String, py: Python) -> PyResult<Option<OrderBook>> {
        py.allow_threads(|| {
            let rt = tokio::runtime::Runtime::new()
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(format!("Failed to create runtime: {}", e)))?;
            
            rt.block_on(self._get_order_book_async(asset_id))
        })
    }

    /// Start WebSocket connection for real-time data
    fn start_realtime(&mut self, py: Python) -> PyResult<bool> {
        py.allow_threads(|| {
            let rt = tokio::runtime::Runtime::new()
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(format!("Failed to create runtime: {}", e)))?;
            
            rt.block_on(self._start_websocket())
        })
    }

    /// Subscribe to asset updates
    fn subscribe_asset(&self, asset_id: String) -> PyResult<()> {
        let mut subscribed = self.subscribed_assets.try_write().unwrap();
        subscribed.insert(asset_id.clone(), true);
        info!("Subscribed to asset: {}", asset_id);
        Ok(())
    }

    /// Get cached markets
    fn get_cached_markets(&self) -> PyResult<Vec<MarketData>> {
        let cache = self.markets_cache.try_read().unwrap();
        Ok(cache.clone())
    }
}

impl PolymarketDataEngine {
    /// Async implementation for fetching markets
    async fn _fetch_markets_async(&self) -> PyResult<Vec<MarketData>> {
        info!("Fetching markets from Gamma API: {}", self.config.gamma_api_url);
        
        let response = self.client
            .get(&format!("{}/markets", self.config.gamma_api_url))
            .query(&[
                ("active", "true"),
                ("closed", "false"),
                ("limit", "1000"),
                ("sort", "volume24hr"),
                ("order", "desc"),
            ])
            .send()
            .await
            .map_err(|e| pyo3::exceptions::PyConnectionError::new_err(format!("Failed to fetch markets: {}", e)))?;

        let raw_data: Value = response
            .json()
            .await
            .map_err(|e| pyo3::exceptions::PyValueError::new_err(format!("Failed to parse response: {}", e)))?;

        let markets: Vec<GammaMarket> = if raw_data.is_array() {
            // 直接解析数组
            raw_data.as_array()
                .ok_or_else(|| pyo3::exceptions::PyValueError::new_err("Failed to convert to array"))?
                .iter()
                .map(|market_value| {
                    // 手动解析每个字段
                    let obj = market_value.as_object().ok_or_else(|| {
                        pyo3::exceptions::PyValueError::new_err("Expected object")
                    })?;
                    
                    let id = obj.get("id").and_then(|v| v.as_str()).unwrap_or("").to_string();
                    let condition_id = obj.get("conditionId").and_then(|v| v.as_str()).unwrap_or("").to_string();
                    let question = obj.get("question").and_then(|v| v.as_str()).unwrap_or("").to_string();
                    let description = obj.get("description").and_then(|v| v.as_str()).map(|s| s.to_string());
                    
                    // 解析字符串为 f64
                    let volume = obj.get("volume")
                        .and_then(|v| v.as_str())
                        .and_then(|s| s.parse().ok())
                        .unwrap_or(0.0);
                    
                    let liquidity = obj.get("liquidity")
                        .and_then(|v| v.as_str())
                        .and_then(|s| s.parse().ok())
                        .unwrap_or(0.0);
                    
                    let end_date_iso = obj.get("endDateIso").and_then(|v| v.as_str()).unwrap_or("").to_string();
                    let active = obj.get("active").and_then(|v| v.as_bool()).unwrap_or(false);
                    let closed = obj.get("closed").and_then(|v| v.as_bool()).unwrap_or(false);
                    let resolved = obj.get("resolved").and_then(|v| v.as_bool()).unwrap_or(false);
                    let clob_token_ids = obj.get("clobTokenIds").and_then(|v| v.as_str()).map(|s| s.to_string());
                    let category = obj.get("category").and_then(|v| v.as_str()).map(|s| s.to_string());
                    let start_date_iso = obj.get("startDateIso").and_then(|v| v.as_str()).map(|s| s.to_string());
                    
                    Ok(GammaMarket {
                        id,
                        condition_id,
                        slug: String::new(), // 不使用
                        question,
                        description,
                        volume,
                        liquidity,
                        end_date_iso,
                        active,
                        closed,
                        resolved,
                        clob_token_ids,
                        category,
                        start_date_iso,
                        other: std::collections::HashMap::new(),
                    })
                })
                .collect::<PyResult<Vec<GammaMarket>>>()?
        } else if let Some(markets_array) = raw_data.get("markets").and_then(|v| v.as_array()) {
            // 解析嵌套的 markets 字段
            markets_array
                .iter()
                .map(|v| serde_json::from_value(v.clone())
                    .map_err(|e| pyo3::exceptions::PyValueError::new_err(format!("Failed to parse market: {}", e))))
                .collect::<PyResult<Vec<GammaMarket>>>()?
        } else {
            return Err(pyo3::exceptions::PyValueError::new_err("Invalid market data format: expected array or object with 'markets' field"));
        };

        let mut result = Vec::new();
        for market in markets {
            let market_data = MarketData {
                id: market.id,
                condition_id: market.condition_id,
                question: market.question,
                volume: market.volume,
                liquidity: market.liquidity,
                end_date: market.end_date_iso,
                active: market.active,
                category: market.category.unwrap_or_else(|| "other".to_string()),
                asset_ids: market.clob_token_ids
                    .and_then(|s| {
                        if s.is_empty() {
                            None
                        } else {
                            // Parse JSON string array
                            serde_json::from_str::<Vec<String>>(&s).ok()
                        }
                    })
                    .unwrap_or_default(),
            };
            result.push(market_data);
        }

        // Update cache
        {
            let mut cache = self.markets_cache.try_write().unwrap();
            *cache = result.clone();
        }

        info!("Fetched {} markets", result.len());
        Ok(result)
    }

    /// Async implementation for getting order book
    async fn _get_order_book_async(&self, asset_id: String) -> PyResult<Option<OrderBook>> {
        info!("Getting order book for asset: {}", asset_id);
        
        let response = self.client
            .get(&format!("{}/book", self.config.clob_api_url))
            .query(&[("token_id", &asset_id)])
            .send()
            .await
            .map_err(|e| pyo3::exceptions::PyConnectionError::new_err(format!("Failed to get order book: {}", e)))?;

        if response.status() != 200 {
            warn!("Order book not found for asset: {}", asset_id);
            return Ok(None);
        }

        let book_data: ClobOrderBook = response
            .json()
            .await
            .map_err(|e| pyo3::exceptions::PyValueError::new_err(format!("Failed to parse order book: {}", e)))?;

        let bids: Vec<(f64, f64)> = book_data.bids.into_iter()
            .map(|[price, size]| (price, size))
            .collect();

        let asks: Vec<(f64, f64)> = book_data.asks.into_iter()
            .map(|[price, size]| (price, size))
            .collect();

        let order_book = OrderBook {
            instrument_id: asset_id.clone(),
            bids,
            asks,
            last_update: book_data.last_update,
        };

        // Update cache
        {
            let mut books = self.order_books.try_write().unwrap();
            books.insert(asset_id.clone(), order_book.clone());
        }

        Ok(Some(order_book))
    }

    /// Start WebSocket connection
    async fn _start_websocket(&self) -> PyResult<bool> {
        info!("Starting WebSocket connection to: {}", self.config.ws_url);
        
        let (_ws_stream, _) = connect_async(&self.config.ws_url)
            .await
            .map_err(|e| pyo3::exceptions::PyConnectionError::new_err(format!("Failed to connect WebSocket: {}", e)))?;

        info!("WebSocket connected successfully");
        
        // In a real implementation, we would handle the WebSocket stream here
        // For now, just return success
        Ok(true)
    }
}
