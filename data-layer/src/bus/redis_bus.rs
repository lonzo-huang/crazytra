/// Redis 消息总线实现
/// 负责将标准化的 tick 数据发送到 Redis Streams

use redis::aio::MultiplexedConnection;
use redis::{AsyncCommands, RedisResult};
use serde_json;
use std::time::Duration;

use crate::connector::NormalizedTick;

pub struct RedisBus {
    connection: MultiplexedConnection,
    stream_prefix: String,
}

impl RedisBus {
    /// 创建新的 Redis 消息总线连接
    pub async fn new(redis_url: &str) -> anyhow::Result<Self> {
        let client = redis::Client::open(redis_url)?;
        let connection = client.get_multiplexed_tokio_connection().await?;

        tracing::info!("Connected to Redis at {}", redis_url);

        Ok(Self {
            connection,
            stream_prefix: "market".to_string(),
        })
    }

    /// 发布 tick 到 Redis Stream
    /// stream 名称格式: market.tick.{exchange}.{symbol}
    pub async fn publish_tick(&mut self, tick: &NormalizedTick) -> RedisResult<()> {
        let stream_key = format!(
            "{}.tick.{}.{}-{}",
            self.stream_prefix,
            tick.symbol.exchange,
            tick.symbol.base,
            tick.symbol.quote
        );

        // 将 tick 序列化为 JSON
        let tick_json = serde_json::to_string(tick).map_err(|e| {
            redis::RedisError::from((
                redis::ErrorKind::Serialize,
                "Failed to serialize tick",
                e.to_string(),
            ))
        })?;

        // 添加到 Stream
        let _: redis::Value = self
            .connection
            .xadd(
                &stream_key,
                "*", // 自动生成 ID
                &[("data", tick_json), ("received_ns", tick.received_ns.to_string())],
            )
            .await?;

        tracing::debug!(
            stream = %stream_key,
            symbol = %tick.symbol.base,
            price = %tick.last_price,
            "Published tick to Redis"
        );

        Ok(())
    }

    /// 批量发布 ticks
    pub async fn publish_ticks_batch(&mut self, ticks: &[NormalizedTick]) -> RedisResult<()> {
        // 使用 pipeline 提高性能
        let mut pipe = redis::pipe();

        for tick in ticks {
            let stream_key = format!(
                "{}.tick.{}.{}-{}",
                self.stream_prefix,
                tick.symbol.exchange,
                tick.symbol.base,
                tick.symbol.quote
            );

            let tick_json = match serde_json::to_string(tick) {
                Ok(json) => json,
                Err(e) => {
                    tracing::warn!("Failed to serialize tick: {}", e);
                    continue;
                }
            };

            pipe.xadd(
                &stream_key,
                "*",
                &[("data", tick_json), ("received_ns", tick.received_ns.to_string())],
            );
        }

        pipe.query_async(&mut self.connection).await?;
        Ok(())
    }

    /// 创建消费者组（用于策略层消费）
    pub async fn create_consumer_group(
        &mut self,
        stream_pattern: &str,
        group_name: &str,
    ) -> RedisResult<()> {
        // 先创建 stream（如果不存在）
        let _: RedisResult<()> = self
            .connection
            .xgroup_create_mkstream(stream_pattern, group_name, "$")
            .await;

        tracing::info!(
            stream = %stream_pattern,
            group = %group_name,
            "Created consumer group"
        );

        Ok(())
    }

    /// 健康检查
    pub async fn health_check(&mut self) -> bool {
        match redis::cmd("PING")
            .query_async::<_, String>(&mut self.connection)
            .await
        {
            Ok(response) => response == "PONG",
            Err(e) => {
                tracing::error!("Redis health check failed: {}", e);
                false
            }
        }
    }

    /// 设置 stream 过期时间（防止无限增长）
    pub async fn set_stream_ttl(&mut self, stream_key: &str, seconds: i64) -> RedisResult<()> {
        self.connection.expire(stream_key, seconds as i64).await?;
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::connector::{InstrumentKind, Symbol};
    use rust_decimal::Decimal;

    // 注意：这些测试需要本地 Redis 实例
    // 运行: docker run -d -p 6379:6379 redis:alpine

    #[tokio::test]
    #[ignore] // 需要 Redis 实例
    async fn test_publish_tick() {
        let mut bus = RedisBus::new("redis://127.0.0.1:6379").await.unwrap();

        let tick = NormalizedTick {
            symbol: Symbol {
                exchange: "polymarket".to_string(),
                base: "test-market".to_string(),
                quote: "USDC".to_string(),
                kind: InstrumentKind::PredictionMarket,
            },
            timestamp_ns: 1704067200000000000,
            received_ns: 1704067200000000001,
            bid_price: Decimal::from_f64(0.65).unwrap(),
            bid_size: Decimal::from_f64(1000.0).unwrap(),
            ask_price: Decimal::from_f64(0.66).unwrap(),
            ask_size: Decimal::from_f64(800.0).unwrap(),
            last_price: Decimal::from_f64(0.655).unwrap(),
            last_size: Decimal::ZERO,
            volume_24h: Decimal::ZERO,
            sequence: None,
        };

        let result = bus.publish_tick(&tick).await;
        assert!(result.is_ok());

        // 验证健康检查
        assert!(bus.health_check().await);
    }
}
