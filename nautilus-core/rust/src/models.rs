//! Data models for Nautilus Core
//! 
//! Standardized data structures that can be passed between Rust and Python

use pyo3::prelude::*;
use serde::{Deserialize, Serialize};
use uuid::Uuid;

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[pyclass]
pub struct MarketData {
    #[pyo3(get)]
    pub id: String,
    #[pyo3(get)]
    pub condition_id: String,
    #[pyo3(get)]
    pub question: String,
    #[pyo3(get)]
    pub volume: f64,
    #[pyo3(get)]
    pub liquidity: f64,
    #[pyo3(get)]
    pub end_date: String,
    #[pyo3(get)]
    pub active: bool,
    #[pyo3(get)]
    pub category: String,
    #[pyo3(get)]
    pub asset_ids: Vec<String>,
}

#[pymethods]
impl MarketData {
    #[new]
    fn new(
        id: String,
        condition_id: String,
        question: String,
        volume: f64,
        liquidity: f64,
        end_date: String,
        active: bool,
        category: String,
        asset_ids: Vec<String>,
    ) -> Self {
        Self {
            id,
            condition_id,
            question,
            volume,
            liquidity,
            end_date,
            active,
            category,
            asset_ids,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[pyclass]
pub struct QuoteTick {
    #[pyo3(get)]
    pub instrument_id: String,
    #[pyo3(get)]
    pub bid: f64,
    #[pyo3(get)]
    pub ask: f64,
    #[pyo3(get)]
    pub bid_size: f64,
    #[pyo3(get)]
    pub ask_size: f64,
    #[pyo3(get)]
    pub ts_event: i64,  // Unix timestamp in nanoseconds
    #[pyo3(get)]
    pub ts_init: i64,   // Unix timestamp in nanoseconds
}

#[pymethods]
impl QuoteTick {
    #[new]
    fn new(
        instrument_id: String,
        bid: f64,
        ask: f64,
        bid_size: f64,
        ask_size: f64,
        ts_event: i64,  // Unix timestamp in nanoseconds
        ts_init: i64,   // Unix timestamp in nanoseconds
    ) -> Self {
        Self {
            instrument_id,
            bid,
            ask,
            bid_size,
            ask_size,
            ts_event,
            ts_init,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[pyclass]
pub struct TradeTick {
    #[pyo3(get)]
    pub instrument_id: String,
    #[pyo3(get)]
    pub price: f64,
    #[pyo3(get)]
    pub size: f64,
    #[pyo3(get)]
    pub side: String,
    #[pyo3(get)]
    pub trade_id: String,
    #[pyo3(get)]
    pub ts_event: i64,  // Unix timestamp in nanoseconds
    #[pyo3(get)]
    pub ts_init: i64,   // Unix timestamp in nanoseconds
}

#[pymethods]
impl TradeTick {
    #[new]
    fn new(
        instrument_id: String,
        price: f64,
        size: f64,
        side: String,
        trade_id: String,
        ts_event: i64,  // Unix timestamp in nanoseconds
        ts_init: i64,   // Unix timestamp in nanoseconds
    ) -> Self {
        Self {
            instrument_id,
            price,
            size,
            side,
            trade_id,
            ts_event,
            ts_init,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[pyclass]
pub struct OrderBook {
    #[pyo3(get)]
    pub instrument_id: String,
    #[pyo3(get)]
    pub bids: Vec<(f64, f64)>,
    #[pyo3(get)]
    pub asks: Vec<(f64, f64)>,
    #[pyo3(get)]
    pub last_update: i64,  // Unix timestamp in nanoseconds
}

#[pymethods]
impl OrderBook {
    #[new]
    fn new(
        instrument_id: String,
        bids: Vec<(f64, f64)>,
        asks: Vec<(f64, f64)>,
        last_update: i64,  // Unix timestamp in nanoseconds
    ) -> Self {
        Self {
            instrument_id,
            bids,
            asks,
            last_update,
        }
    }
}
