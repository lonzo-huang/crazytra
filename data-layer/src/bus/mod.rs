use crate::connector::NormalizedTick;
use redis::aio::MultiplexedConnection;
use redis::AsyncCommands;

pub struct RedisBus {
    conn: MultiplexedConnection,
}

impl RedisBus {
    pub async fn new(redis_url: &str) -> anyhow::Result<Self> {
        let client = redis::Client::open(redis_url)?;
        let conn   = client.get_multiplexed_tokio_connection().await?;
        Ok(Self { conn })
    }

    pub async fn publish_tick(&mut self, tick: &NormalizedTick) -> anyhow::Result<()> {
        let topic = format!("market.tick.{}.{}{}", 
            tick.symbol.exchange,
            tick.symbol.base,
            tick.symbol.quote);

        let payload = serde_json::json!({
            "symbol":       format!("{}-{}", tick.symbol.base, tick.symbol.quote),
            "exchange":     tick.symbol.exchange,
            "timestamp_ns": tick.timestamp_ns,
            "received_ns":  tick.received_ns,
            "bid":          tick.bid_price.to_string(),
            "ask":          tick.ask_price.to_string(),
            "last":         tick.last_price.to_string(),
            "bid_size":     tick.bid_size.to_string(),
            "ask_size":     tick.ask_size.to_string(),
            "volume_24h":   tick.volume_24h.to_string(),
            "latency_us":   tick.latency_us(),
        }).to_string();

        redis::cmd("XADD")
            .arg(&topic)
            .arg("MAXLEN").arg("~").arg(50_000u32)
            .arg("*")
            .arg("data").arg(&payload)
            .arg("sym").arg(format!("{}-{}", tick.symbol.base, tick.symbol.quote))
            .query_async::<_, String>(&mut self.conn)
            .await?;

        Ok(())
    }
}
