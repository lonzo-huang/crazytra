use std::sync::Arc;
use std::sync::atomic::{AtomicU32, Ordering};
use std::time::Duration;
use tokio::sync::mpsc;
use tokio::time::sleep;
use tokio_tungstenite::{connect_async, tungstenite::Message};
use futures_util::{SinkExt, StreamExt};
use rand::Rng;

#[derive(Debug, Clone)]
pub struct ReconnectConfig {
    pub initial_backoff: Duration,
    pub max_backoff:     Duration,
    pub backoff_factor:  f64,
    pub jitter_ratio:    f64,
    pub max_attempts:    Option<u32>,
    pub ping_interval:   Duration,
    pub pong_timeout:    Duration,
}

impl Default for ReconnectConfig {
    fn default() -> Self {
        Self {
            initial_backoff: Duration::from_secs(1),
            max_backoff:     Duration::from_secs(60),
            backoff_factor:  2.0,
            jitter_ratio:    0.3,
            max_attempts:    None,
            ping_interval:   Duration::from_secs(20),
            pong_timeout:    Duration::from_secs(5),
        }
    }
}

pub struct ReconnectingWebSocket {
    url:           String,
    config:        ReconnectConfig,
    attempt_count: Arc<AtomicU32>,
}

impl ReconnectingWebSocket {
    pub fn new(url: String, config: ReconnectConfig) -> Self {
        Self { url, config, attempt_count: Arc::new(AtomicU32::new(0)) }
    }

    fn backoff_duration(&self, attempt: u32) -> Duration {
        let base  = self.config.initial_backoff.as_secs_f64()
                  * self.config.backoff_factor.powi(attempt as i32);
        let capped = base.min(self.config.max_backoff.as_secs_f64());
        let jitter = rand::thread_rng()
            .gen_range(0.0..capped * self.config.jitter_ratio);
        Duration::from_secs_f64(capped - jitter)
    }

    pub async fn run(
        &self,
        init_messages: Vec<String>,
        raw_tx:  mpsc::Sender<String>,
        mut stop_rx: tokio::sync::oneshot::Receiver<()>,
    ) {
        loop {
            let attempt = self.attempt_count.load(Ordering::Relaxed);
            if let Some(max) = self.config.max_attempts {
                if attempt >= max { return; }
            }

            if attempt > 0 {
                let wait = self.backoff_duration(attempt - 1);
                tracing::warn!(url = %self.url, attempt, wait_ms = wait.as_millis(),
                    "WebSocket reconnecting");
                tokio::select! {
                    _ = sleep(wait) => {}
                    _ = &mut stop_rx => return,
                }
            }

            let ws_stream = match connect_async(&self.url).await {
                Ok((s, _)) => {
                    self.attempt_count.store(0, Ordering::Relaxed);
                    tracing::info!(url = %self.url, "WebSocket connected");
                    s
                }
                Err(e) => {
                    tracing::error!(url = %self.url, error = %e, "Connect failed");
                    self.attempt_count.fetch_add(1, Ordering::Relaxed);
                    continue;
                }
            };

            let (mut write, mut read) = ws_stream.split();

            for msg in &init_messages {
                if write.send(Message::Text(msg.clone())).await.is_err() { break; }
            }

            let ping_iv = self.config.ping_interval;
            let pong_to = self.config.pong_timeout;

            let result = tokio::select! {
                _ = &mut stop_rx => return,
                r = Self::read_loop(&mut read, &raw_tx, &mut write, ping_iv, pong_to) => r,
            };

            if let Err(e) = result {
                tracing::warn!(url = %self.url, error = %e, "Read loop ended");
            }
            self.attempt_count.fetch_add(1, Ordering::Relaxed);
        }
    }

    async fn read_loop(
        read:  &mut (impl StreamExt<Item = Result<Message,
              tokio_tungstenite::tungstenite::Error>> + Unpin),
        raw_tx: &mpsc::Sender<String>,
        write:  &mut (impl SinkExt<Message> + Unpin),
        ping_interval: Duration,
        pong_timeout:  Duration,
    ) -> anyhow::Result<()> {
        let mut ticker       = tokio::time::interval(ping_interval);
        let mut waiting_pong = false;
        let mut pong_deadline: Option<tokio::time::Instant> = None;

        loop {
            tokio::select! {
                msg = read.next() => {
                    match msg {
                        Some(Ok(Message::Text(t))) => {
                            if raw_tx.send(t).await.is_err() { return Ok(()); }
                        }
                        Some(Ok(Message::Ping(d))) => {
                            let _ = write.send(Message::Pong(d)).await;
                        }
                        Some(Ok(Message::Pong(_))) => {
                            waiting_pong = false;
                            pong_deadline = None;
                        }
                        Some(Ok(Message::Close(_))) | None => {
                            anyhow::bail!("Connection closed");
                        }
                        Some(Err(e)) => anyhow::bail!("{e}"),
                        _ => {}
                    }
                }
                _ = ticker.tick() => {
                    if waiting_pong {
                        if pong_deadline.map_or(false, |d| tokio::time::Instant::now() > d) {
                            anyhow::bail!("Pong timeout");
                        }
                    } else {
                        let _ = write.send(Message::Ping(vec![])).await;
                        waiting_pong  = true;
                        pong_deadline = Some(tokio::time::Instant::now() + pong_timeout);
                    }
                }
            }
        }
    }
}
