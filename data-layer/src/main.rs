mod connector;
mod transport;
mod buffer;
mod bus;

use std::sync::Arc;
use connector::{ConnectorRegistry, InstrumentKind, Symbol};
use connector::binance::BinanceConnector;
use connector::polymarket::PolymarketConnector;
use bus::RedisBus;

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    dotenvy::dotenv().ok();
    tracing_subscriber::fmt()
        .with_env_filter(tracing_subscriber::EnvFilter::from_default_env())
        .init();

    tracing::info!("Starting data layer");

    let redis_url = std::env::var("REDIS_URL")
        .unwrap_or_else(|_| "redis://127.0.0.1:6379".into());

    let registry = Arc::new(ConnectorRegistry::new());

    // 注册 Binance 连接器
    let binance_key = std::env::var("BINANCE_API_KEY").ok();
    registry.register(Arc::new(BinanceConnector::new(binance_key)));

    // 注册 Polymarket 连接器
    let polymarket_key = std::env::var("POLYMARKET_API_KEY").ok();
    registry.register(Arc::new(PolymarketConnector::new(polymarket_key)));

    tracing::info!("Registered connectors: {:?}", registry.health_report());

    // 创建多个 tick 通道
    let (binance_tx, mut binance_rx) = tokio::sync::mpsc::channel(8192);
    let (poly_tx, mut poly_rx) = tokio::sync::mpsc::channel(8192);

    // Binance 市场
    let btc = Symbol {
        exchange: "binance".into(),
        base:     "BTC".into(),
        quote:    "USDT".into(),
        kind:     InstrumentKind::Spot,
    };
    let eth = Symbol {
        exchange: "binance".into(),
        base:     "ETH".into(),
        quote:    "USDT".into(),
        kind:     InstrumentKind::Spot,
    };

    // Polymarket 市场
    // 格式: condition_id:asset_id:slug
    let btc_100k = Symbol {
        exchange: "polymarket".into(),
        base:     "0x...:0x...:will-btc-hit-100k-2024".into(), // 替换为实际 ID
        quote:    "USDC".into(),
        kind:     InstrumentKind::PredictionMarket,
    };

    // 启动连接器
    let binance_connector = registry.get("binance").unwrap();
    let binance_task = tokio::spawn(async move {
        binance_connector.subscribe(vec![btc, eth], binance_tx).await
    });

    let poly_connector = registry.get("polymarket").unwrap();
    let poly_task = tokio::spawn(async move {
        // 注意：需要替换为实际的 condition_id 和 asset_id
        poly_connector.subscribe(vec![btc_100k], poly_tx).await
    });

    let mut bus = RedisBus::new(&redis_url).await?;
    tracing::info!("Data layer running — publishing to Redis");

    // 合并处理两个交易所的数据
    loop {
        tokio::select! {
            Some(tick) = binance_rx.recv() => {
                if let Err(e) = bus.publish_tick(&tick).await {
                    tracing::warn!("Redis publish error (binance): {e}");
                }
            }
            Some(tick) = poly_rx.recv() => {
                if let Err(e) = bus.publish_tick(&tick).await {
                    tracing::warn!("Redis publish error (polymarket): {e}");
                }
            }
            else => {
                tracing::info!("All channels closed, shutting down");
                break;
            }
        }
    }

    // 等待任务完成
    let _ = binance_task.await;
    let _ = poly_task.await;

    Ok(())
}
