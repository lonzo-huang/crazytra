//! Nautilus Core - Rust DataEngine for MirrorQuant
//! 
//! This module provides high-performance data processing for external market data sources,
//! including Polymarket, Binance, and other trading platforms.

use pyo3::prelude::*;
use pyo3::types::PyModule;

pub mod models;
pub mod data_polymarket;

// Re-export main components
pub use data_polymarket::PolymarketDataEngine;
pub use models::*;

/// Python module initialization
#[pymodule]
fn nautilus_core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<PolymarketDataEngine>()?;
    m.add_class::<MarketData>()?;
    m.add_class::<QuoteTick>()?;
    m.add_class::<TradeTick>()?;
    m.add_class::<OrderBook>()?;
    Ok(())
}
